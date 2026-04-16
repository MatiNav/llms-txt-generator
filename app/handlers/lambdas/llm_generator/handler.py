import logging
from typing import Any

from handlers.lambdas.llm_generator.openai_client import (
    FatalLlmError,
    RetriableLlmError,
)
from handlers.lambdas.llm_generator.runtime import build_llm_generator_runtime
from handlers.shared.lambda_runtime.base_handler import BaseLambdaHandler
from shared.logging import log_event
from shared.pipeline.llm_generation_message import (
    parse_llm_generation_requested_message,
)
from shared.pipeline.json_payload import parse_json_object_payload


logger = logging.getLogger(__name__)


class LlmGeneratorLambdaHandler(BaseLambdaHandler):
    def __init__(self) -> None:
        self.runtime = None

    async def process(
        self, event: dict[str, Any], context: Any
    ) -> dict[str, list[dict[str, str]]]:
        self.runtime = build_llm_generator_runtime()
        batch_failures: list[dict[str, str]] = []

        records = event.get("Records", [])
        for record in records:
            message_id = str(record.get("messageId", ""))
            try:
                await self._process_record(record=record, message_id=message_id)
            except Exception as processing_error:
                if isinstance(processing_error, FatalLlmError):
                    await self.runtime.repository.database_session.commit()
                else:
                    await self.runtime.repository.database_session.rollback()
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

        return {"batchItemFailures": batch_failures}

    async def _process_record(self, *, record: dict[str, Any], message_id: str) -> None:
        raw_body = str(record.get("body", "{}"))
        payload = parse_json_object_payload(raw_body)

        message = parse_llm_generation_requested_message(payload)
        run_id = message["run_id"]
        site_id = message["site_id"]

        await self.runtime.service.process_run(run_id=run_id, site_id=site_id)
        await self.runtime.repository.database_session.commit()

        log_event(
            logger,
            logging.INFO,
            "llm_generator.record.completed",
            message_id=message_id,
            run_id=run_id,
            site_id=site_id,
        )

    async def cleanup(self) -> None:
        if self.runtime is None:
            return
        await self.runtime.repository.database_session.close()


llm_generator_lambda_handler = LlmGeneratorLambdaHandler()


def handler(event: dict[str, Any], context: Any) -> dict[str, list[dict[str, str]]]:
    return llm_generator_lambda_handler.run(event=event, context=context)
