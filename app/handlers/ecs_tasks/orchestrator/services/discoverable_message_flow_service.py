import json
import logging
from typing import Any

from orchestrator.adapters.fetch_queue_publisher_adapter import (
    publish_route_message,
)
from orchestrator.config import SERVICE_NAME
from orchestrator.message_types import DiscoverableMessage, PageCompletedMessage
from orchestrator.services.processing_completion_service import (
    try_emit_processing_requested,
)
from shared.db.session import get_session_factory
from shared.constants.render_mode import ALLOWED_RENDER_MODES
from shared.logging import log_event
from shared.queue.sns_client import SNSClient
from shared.queue.sqs_client import SQSClient


logger = logging.getLogger(__name__)


def parse_discoverable_message(raw_payload: dict[str, Any]) -> DiscoverableMessage:
    run_id = str(raw_payload["run_id"])
    page_id = str(raw_payload["page_id"])
    site_id = str(raw_payload["site_id"])
    page_url = str(raw_payload["url"])
    page_depth = int(raw_payload["depth"])
    render_mode = str(raw_payload["render_mode"]).strip().lower()
    if render_mode not in ALLOWED_RENDER_MODES:
        supported_modes = ", ".join(ALLOWED_RENDER_MODES)
        raise ValueError(f"render_mode must be one of: {supported_modes}")

    return {
        "run_id": run_id,
        "page_id": page_id,
        "site_id": site_id,
        "url": page_url,
        "depth": page_depth,
        "render_mode": render_mode,
    }


def parse_page_completed_message(raw_payload: dict[str, Any]) -> PageCompletedMessage:
    return {
        "run_id": str(raw_payload["run_id"]),
        "page_id": str(raw_payload["page_id"]),
        "site_id": str(raw_payload["site_id"]),
    }


async def process_discoverable_message(
    discoverable_message: DiscoverableMessage,
    routing_topic_client: SNSClient,
    processing_topic_client: SNSClient,
    fetch_topic_arn: str,
    processing_topic_arn: str,
) -> bool:
    run_id = discoverable_message["run_id"]
    page_id = discoverable_message["page_id"]
    site_id = discoverable_message["site_id"]
    page_url = discoverable_message["url"]
    page_depth = discoverable_message["depth"]
    render_mode = discoverable_message["render_mode"]

    log_event(
        logger,
        logging.INFO,
        "discoverable.message.received",
        service=SERVICE_NAME,
        component="orchestrator",
        run_id=run_id,
        page_id=page_id,
        site_id=site_id,
        url=page_url,
        depth=page_depth,
        render_mode=render_mode,
    )

    await publish_route_message(
        routing_topic_client=routing_topic_client,
        fetch_topic_arn=fetch_topic_arn,
        render_mode=render_mode,
        run_id=run_id,
        page_id=page_id,
        site_id=site_id,
        page_url=page_url,
        page_depth=page_depth,
    )

    log_event(
        logger,
        logging.INFO,
        "fetch.route.selected",
        service=SERVICE_NAME,
        component="orchestrator",
        run_id=run_id,
        page_id=page_id,
        site_id=site_id,
        url=page_url,
        depth=page_depth,
        render_mode=render_mode,
        topic_arn=fetch_topic_arn,
    )

    session_factory = get_session_factory()
    async with session_factory() as database_session:
        await try_emit_processing_requested(
            database_session=database_session,
            processing_topic_client=processing_topic_client,
            processing_topic_arn=processing_topic_arn,
            run_id=run_id,
            site_id=site_id,
            page_id=page_id,
        )

    return True


async def process_page_completed_message(
    page_completed_message: PageCompletedMessage,
    processing_topic_client: SNSClient,
    processing_topic_arn: str,
) -> bool:
    run_id = page_completed_message["run_id"]
    page_id = page_completed_message["page_id"]
    site_id = page_completed_message["site_id"]

    log_event(
        logger,
        logging.INFO,
        "completion.page_completed.received",
        service=SERVICE_NAME,
        component="orchestrator",
        run_id=run_id,
        page_id=page_id,
        site_id=site_id,
    )

    session_factory = get_session_factory()
    async with session_factory() as database_session:
        await try_emit_processing_requested(
            database_session=database_session,
            processing_topic_client=processing_topic_client,
            processing_topic_arn=processing_topic_arn,
            run_id=run_id,
            site_id=site_id,
            page_id=page_id,
        )

    return True


async def handle_raw_message(
    raw_message: dict[str, Any],
    discoverable_queue_client: SQSClient,
    routing_topic_client: SNSClient,
    processing_topic_client: SNSClient,
    fetch_topic_arn: str,
    processing_topic_arn: str,
) -> None:
    receipt_handle = raw_message.get("ReceiptHandle")
    try:
        message_body = raw_message.get("Body", "{}")
        parsed_payload = json.loads(message_body)
        if not isinstance(parsed_payload, dict):
            raise ValueError("SQS message body must be a JSON object")

        event_type = str(parsed_payload.get("event_type", "discoverable"))
        if event_type == "page_completed":
            page_completed_message = parse_page_completed_message(parsed_payload)
            processed_successfully = await process_page_completed_message(
                page_completed_message=page_completed_message,
                processing_topic_client=processing_topic_client,
                processing_topic_arn=processing_topic_arn,
            )
        else:
            discoverable_message = parse_discoverable_message(parsed_payload)
            processed_successfully = await process_discoverable_message(
                discoverable_message=discoverable_message,
                routing_topic_client=routing_topic_client,
                processing_topic_client=processing_topic_client,
                fetch_topic_arn=fetch_topic_arn,
                processing_topic_arn=processing_topic_arn,
            )

        if processed_successfully and receipt_handle:
            await discoverable_queue_client.delete_message(
                receipt_handle=receipt_handle
            )
    except Exception as processing_error:
        log_event(
            logger,
            logging.ERROR,
            "discoverable.message.failed",
            service=SERVICE_NAME,
            component="orchestrator",
            receipt_handle=receipt_handle,
            error_type=type(processing_error).__name__,
            error_message=str(processing_error)[:500],
        )
