import json
import logging
from typing import Any

from handlers.lambdas.http_fetcher.runtime import build_http_fetcher_runtime
from handlers.shared.lambda_runtime.base_handler import BaseLambdaHandler
from shared.constants.render_mode import RENDER_MODE_HTTP
from shared.logging import log_event
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


class HttpFetcherLambdaHandler(BaseLambdaHandler):
    def __init__(self) -> None:
        self.runtime = None

    async def process(
        self, event: dict[str, Any], context: Any
    ) -> dict[str, list[dict[str, str]]]:
        self.runtime = build_http_fetcher_runtime()
        batch_failures: list[dict[str, str]] = []

        records = event.get("Records", [])
        for record in records:
            message_id = str(record.get("messageId", ""))
            raw_body = str(record.get("body", "{}"))
            try:
                await _process_record_body(raw_body, self.runtime)
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

        return {"batchItemFailures": batch_failures}

    async def cleanup(self) -> None:
        if self.runtime is None:
            return
        await self.runtime.fetcher_core.repository.database_session.close()


http_fetcher_lambda_handler = HttpFetcherLambdaHandler()


def handler(event: dict[str, Any], context: Any) -> dict[str, list[dict[str, str]]]:
    return http_fetcher_lambda_handler.run(event=event, context=context)
