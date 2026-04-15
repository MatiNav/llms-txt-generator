import asyncio
import json
import logging
from typing import Any

from handlers.lambdas.http_fetcher.runtime import build_http_fetcher_runtime
from shared.constants.render_mode import RENDER_MODE_HTTP
from shared.logging import configure_json_logging, log_event
from shared.pipeline.fetch_message import parse_fetch_requested_message


logger = logging.getLogger(__name__)


async def _process_record_body(raw_body: str, runtime) -> None:
    parsed_payload = json.loads(raw_body)
    if not isinstance(parsed_payload, dict):
        raise ValueError("SQS message body must be a JSON object")

    fetch_message = parse_fetch_requested_message(parsed_payload)
    if fetch_message["render_mode"] != RENDER_MODE_HTTP:
        raise ValueError("HTTP fetcher received non-http render_mode message")

    await runtime.fetcher_core.process(
        fetch_message=fetch_message,
        fetcher_adapter=runtime.fetcher_adapter,
    )


async def _process_batch(event: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    runtime = build_http_fetcher_runtime()
    batch_failures: list[dict[str, str]] = []

    try:
        records = event.get("Records", [])
        for record in records:
            message_id = str(record.get("messageId", ""))
            raw_body = str(record.get("body", "{}"))
            try:
                await _process_record_body(raw_body, runtime)
            except Exception as processing_error:
                log_event(
                    logger,
                    logging.ERROR,
                    "http_fetcher.message.failed",
                    service="http_fetcher",
                    message_id=message_id,
                    error_type=type(processing_error).__name__,
                    error_message=str(processing_error)[:500],
                )
                batch_failures.append({"itemIdentifier": message_id})
    finally:
        await runtime.fetcher_core.repository.database_session.close()

    return {"batchItemFailures": batch_failures}


def handler(event: dict[str, Any], context: Any) -> dict[str, list[dict[str, str]]]:
    configure_json_logging()
    return asyncio.run(_process_batch(event))
