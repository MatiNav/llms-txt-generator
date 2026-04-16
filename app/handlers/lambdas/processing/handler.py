import logging
from typing import Any

from handlers.lambdas.processing.runtime import build_processing_runtime
from handlers.shared.lambda_runtime.base_handler import BaseLambdaHandler
from shared.constants.run_state import RUN_STATE_READY_FOR_LLM_GENERATION
from shared.logging import log_decision, log_event
from shared.pipeline.llm_generation_message import (
    build_llm_generation_requested_message,
)
from shared.pipeline.json_payload import parse_json_object_payload
from shared.pipeline.processing_message import parse_processing_requested_message


logger = logging.getLogger(__name__)


async def _publish_llm_generation_message(
    *,
    runtime,
    run_id: str,
    site_id: str,
    message_id: str,
) -> None:
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


async def _republish_if_run_is_ready_for_llm_generation(
    *,
    runtime,
    run_id: str,
    site_id: str,
    message_id: str,
) -> None:
    run_snapshot = await runtime.processing_service.repository.get_run_snapshot(run_id)
    if run_snapshot is None:
        return

    if run_snapshot.state != RUN_STATE_READY_FOR_LLM_GENERATION:
        return

    log_decision(
        logger,
        decision_name="processing.republish_llm_generation_after_commit",
        reason="run already committed to ready_for_llm_generation in earlier attempt",
        run_id=run_id,
        site_id=site_id,
        message_id=message_id,
    )
    await _publish_llm_generation_message(
        runtime=runtime,
        run_id=run_id,
        site_id=site_id,
        message_id=message_id,
    )


def _parse_processing_message(raw_body: str) -> dict[str, str]:
    parsed_payload = parse_json_object_payload(raw_body)
    return parse_processing_requested_message(parsed_payload)


class ProcessingLambdaHandler(BaseLambdaHandler):
    def __init__(self) -> None:
        self.runtime = None

    async def process(
        self, event: dict[str, Any], context: Any
    ) -> dict[str, list[dict[str, str]]]:
        self.runtime = build_processing_runtime()
        batch_failures: list[dict[str, str]] = []

        records = event.get("Records", [])
        for record in records:
            message_id = str(record.get("messageId", ""))
            try:
                await self._process_record(record=record, message_id=message_id)
            except Exception as processing_error:
                await self.runtime.processing_service.repository.database_session.rollback()
                log_event(
                    logger,
                    logging.ERROR,
                    "processing.record.failed",
                    message_id=message_id,
                    error_type=type(processing_error).__name__,
                    error_message=str(processing_error)[:500],
                )
                batch_failures.append({"itemIdentifier": message_id})

        return {"batchItemFailures": batch_failures}

    async def _process_record(self, *, record: dict[str, Any], message_id: str) -> None:
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

        processing_result = await self.runtime.processing_service.process_run(
            run_id=run_id,
            site_id=site_id,
        )
        await self.runtime.processing_service.repository.database_session.commit()

        if not processing_result.should_publish_llm_generation:
            log_decision(
                logger,
                decision_name="processing.skip_llm_generation_publish",
                reason="run did not complete successfully in this processing attempt",
                run_id=run_id,
                site_id=site_id,
                message_id=message_id,
            )
            await _republish_if_run_is_ready_for_llm_generation(
                runtime=self.runtime,
                run_id=run_id,
                site_id=site_id,
                message_id=message_id,
            )
            return

        await _publish_llm_generation_message(
            runtime=self.runtime,
            run_id=run_id,
            site_id=site_id,
            message_id=message_id,
        )

    async def cleanup(self) -> None:
        if self.runtime is None:
            return
        await self.runtime.processing_service.repository.database_session.close()


processing_lambda_handler = ProcessingLambdaHandler()


def handler(event: dict[str, Any], context: Any) -> dict[str, list[dict[str, str]]]:
    return processing_lambda_handler.run(event=event, context=context)
