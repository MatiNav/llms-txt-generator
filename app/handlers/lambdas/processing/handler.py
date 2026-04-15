import asyncio
import json
import logging
from typing import Any

from handlers.lambdas.processing.runtime import build_processing_runtime
from shared.db.engine import get_engine
from shared.db.session import get_session_factory
from shared.logging import configure_json_logging, log_decision, log_event
from shared.pipeline.llm_generation_message import (
    build_llm_generation_requested_message,
)
from shared.pipeline.processing_message import parse_processing_requested_message


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
    processing_message = _parse_processing_message(raw_body)
    run_id = processing_message["run_id"]
    site_id = processing_message["site_id"]

    log_event(
        logger,
        logging.INFO,
        "processing.record.received",
        message_id=message_id,
        run_id=run_id,
        site_id=site_id,
    )

    processing_result = await runtime.processing_service.process_run(
        run_id=run_id,
        site_id=site_id,
    )
    await runtime.processing_service.repository.database_session.commit()

    if not processing_result.should_publish_llm_generation:
        log_decision(
            logger,
            decision_name="processing.skip_llm_generation_publish",
            reason="run did not complete successfully in this processing attempt",
            run_id=run_id,
            site_id=site_id,
            message_id=message_id,
        )
        return

    llm_generation_payload = build_llm_generation_requested_message(
        run_id=run_id,
        site_id=site_id,
    )
    await runtime.llm_generation_publisher.publish_message(
        topic_arn=runtime.llm_generation_topic_arn,
        payload=llm_generation_payload,
    )
    log_event(
        logger,
        logging.INFO,
        "processing.record.completed",
        message_id=message_id,
        run_id=run_id,
        site_id=site_id,
    )


def _parse_processing_message(raw_body: str) -> dict[str, str]:
    parsed_payload = json.loads(raw_body)
    if not isinstance(parsed_payload, dict):
        raise ValueError("SQS message body must be a JSON object")
    return parse_processing_requested_message(parsed_payload)


async def _process_batch(event: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    runtime = build_processing_runtime()
    batch_failures: list[dict[str, str]] = []

    try:
        records = event.get("Records", [])
        for record in records:
            message_id = str(record.get("messageId", ""))
            try:
                await _process_record(record, runtime)
            except Exception as processing_error:
                await runtime.processing_service.repository.database_session.rollback()
                log_event(
                    logger,
                    logging.ERROR,
                    "processing.record.failed",
                    message_id=message_id,
                    error_type=type(processing_error).__name__,
                    error_message=str(processing_error)[:500],
                )
                batch_failures.append({"itemIdentifier": message_id})
    finally:
        await runtime.processing_service.repository.database_session.close()
        await _dispose_cached_db_resources()

    return {"batchItemFailures": batch_failures}


def handler(event: dict[str, Any], context: Any) -> dict[str, list[dict[str, str]]]:
    configure_json_logging()
    return asyncio.run(_process_batch(event))
