import asyncio

from orchestrator.config import load_runtime_config
from orchestrator.services.discoverable_message_flow_service import handle_raw_message
from shared.logging import configure_json_logging
from shared.queue.sns_client import SNSClient
from shared.queue.sqs_client import SQSClient


async def main_async() -> None:
    configure_json_logging()
    runtime_config = load_runtime_config()

    discoverable_queue_client = SQSClient(
        region_name=runtime_config.aws_region,
        queue_url=runtime_config.discoverable_queue_url,
    )
    routing_topic_client = SNSClient(
        region_name=runtime_config.aws_region,
        service_name="orchestrator",
    )
    processing_topic_client = SNSClient(
        region_name=runtime_config.aws_region,
        service_name="orchestrator",
    )

    while True:
        messages = await discoverable_queue_client.receive_messages(
            max_messages=10,
            wait_time_seconds=20,
        )
        if not messages:
            continue

        batch_tasks = [
            handle_raw_message(
                raw_message=raw_message,
                discoverable_queue_client=discoverable_queue_client,
                routing_topic_client=routing_topic_client,
                processing_topic_client=processing_topic_client,
                fetch_topic_arn=runtime_config.fetch_topic_arn,
                processing_topic_arn=runtime_config.processing_topic_arn,
            )
            for raw_message in messages
        ]
        await asyncio.gather(*batch_tasks)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
