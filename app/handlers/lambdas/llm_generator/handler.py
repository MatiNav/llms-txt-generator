import asyncio
import json
import logging
from typing import Any

from handlers.lambdas.llm_generator.openai_client import (
    FatalLlmError,
    RetriableLlmError,
)
from handlers.lambdas.llm_generator.runtime import build_llm_generator_runtime
from shared.db.engine import get_engine
from shared.db.session import get_session_factory
from shared.logging import configure_json_logging, log_event
from shared.pipeline.llm_generation_message import (
    parse_llm_generation_requested_message,
)


logger = logging.getLogger(__name__)


async def _dispose_cached_db_resources() -> None:
    if get_engine.cache_info().currsize > 0:
        cached_engine = get_engine()
        await cached_engine.dispose()

    get_session_factory.cache_clear()
    get_engine.cache_clear()


async def _process_record(record: dict[str, Any], runtime) -> None:
    message_id = str(record.get("messageId", ""))
    raw_body = str(record.get("body", "{}"))
    payload = json.loads(raw_body)
    if not isinstance(payload, dict):
        raise ValueError("SQS message body must be a JSON object")

    message = parse_llm_generation_requested_message(payload)
    run_id = message["run_id"]
    site_id = message["site_id"]

    await runtime.service.process_run(run_id=run_id, site_id=site_id)
    await runtime.repository.database_session.commit()

    log_event(
        logger,
        logging.INFO,
        "llm_generator.record.completed",
        message_id=message_id,
        run_id=run_id,
        site_id=site_id,
    )


async def _process_batch(event: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    runtime = build_llm_generator_runtime()
    batch_failures: list[dict[str, str]] = []

    try:
        records = event.get("Records", [])
        for record in records:
            message_id = str(record.get("messageId", ""))
            try:
                await _process_record(record, runtime)
            except Exception as processing_error:
                if isinstance(processing_error, FatalLlmError):
                    await runtime.repository.database_session.commit()
                else:
                    await runtime.repository.database_session.rollback()
                log_event(
                    logger,
                    logging.ERROR,
                    "llm_generator.record.failed",
                    message_id=message_id,
                    error_type=type(processing_error).__name__,
                    error_message=str(processing_error)[:500],
                )
                if isinstance(processing_error, RetriableLlmError):
                    batch_failures.append({"itemIdentifier": message_id})
    finally:
        await runtime.repository.database_session.close()
        await _dispose_cached_db_resources()

    return {"batchItemFailures": batch_failures}


def handler(event: dict[str, Any], context: Any) -> dict[str, list[dict[str, str]]]:
    configure_json_logging()
    return asyncio.run(_process_batch(event))
