import json
import logging
from typing import Any

from orchestrator.adapters.fetch_queue_publisher_adapter import (
    normalize_strategy,
    publish_route_message,
)
from orchestrator.config import SERVICE_NAME
from orchestrator.message_types import DiscoverableMessage
from orchestrator.repositories.run_page_repository import (
    reserve_run_page_and_increment_pages_queued,
)
from shared.logging import log_event
from shared.queue.sns_client import SNSClient
from shared.queue.sqs_client import SQSClient


logger = logging.getLogger(__name__)


def parse_discoverable_message(raw_payload: dict[str, Any]) -> DiscoverableMessage:
    run_id = str(raw_payload["run_id"])
    site_id = str(raw_payload["site_id"])
    page_url = str(raw_payload["url"])
    page_depth = int(raw_payload["depth"])

    return {
        "run_id": run_id,
        "site_id": site_id,
        "url": page_url,
        "depth": page_depth,
    }


async def process_discoverable_message(
    discoverable_message: DiscoverableMessage,
    routing_topic_client: SNSClient,
    fetch_topic_arn: str,
) -> bool:
    run_id = discoverable_message["run_id"]
    site_id = discoverable_message["site_id"]
    page_url = discoverable_message["url"]
    page_depth = discoverable_message["depth"]

    log_event(
        logger,
        logging.INFO,
        "discoverable.message.received",
        service=SERVICE_NAME,
        component="orchestrator",
        run_id=run_id,
        site_id=site_id,
        url=page_url,
        depth=page_depth,
    )

    (
        reservation_outcome,
        strategy_name,
        strategy_reason_markers,
    ) = await reserve_run_page_and_increment_pages_queued(
        run_id=run_id,
        page_url=page_url,
        page_depth=page_depth,
    )

    if reservation_outcome == "deduplicated":
        log_event(
            logger,
            logging.INFO,
            "run_page.deduplicated",
            service=SERVICE_NAME,
            component="orchestrator",
            run_id=run_id,
            site_id=site_id,
            url=page_url,
        )
        return True

    if reservation_outcome in ("run_missing", "run_not_discovering"):
        log_event(
            logger,
            logging.INFO,
            "run_page.skipped",
            service=SERVICE_NAME,
            component="orchestrator",
            run_id=run_id,
            site_id=site_id,
            url=page_url,
            reason=reservation_outcome,
        )
        return True

    if strategy_reason_markers is not None:
        log_event(
            logger,
            logging.INFO,
            "probe.completed",
            service=SERVICE_NAME,
            component="orchestrator",
            run_id=run_id,
            site_id=site_id,
            url=page_url,
            strategy=strategy_name,
            reasons=strategy_reason_markers,
        )

    strategy_used = normalize_strategy(strategy_name)

    await publish_route_message(
        routing_topic_client=routing_topic_client,
        fetch_topic_arn=fetch_topic_arn,
        strategy_name=strategy_used,
        run_id=run_id,
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
        site_id=site_id,
        url=page_url,
        depth=page_depth,
        strategy=strategy_used,
        topic_arn=fetch_topic_arn,
    )
    return True


async def handle_raw_message(
    raw_message: dict[str, Any],
    discoverable_queue_client: SQSClient,
    routing_topic_client: SNSClient,
    fetch_topic_arn: str,
) -> None:
    receipt_handle = raw_message.get("ReceiptHandle")
    try:
        message_body = raw_message.get("Body", "{}")
        parsed_payload = json.loads(message_body)
        if not isinstance(parsed_payload, dict):
            raise ValueError("SQS message body must be a JSON object")

        discoverable_message = parse_discoverable_message(parsed_payload)
        processed_successfully = await process_discoverable_message(
            discoverable_message=discoverable_message,
            routing_topic_client=routing_topic_client,
            fetch_topic_arn=fetch_topic_arn,
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
