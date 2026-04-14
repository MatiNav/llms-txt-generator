import json
import logging
from typing import Any
from urllib.parse import urlparse

import aioboto3
from botocore.exceptions import ClientError

from shared.logging import log_event


logger = logging.getLogger(__name__)


class SQSClient:
    def __init__(self, region_name: str, queue_url: str) -> None:
        self.region_name = region_name
        self.queue_url = queue_url
        self.session = aioboto3.Session()

    async def send_message(
        self,
        queue_url: str,
        payload: dict[str, Any],
        request_id: str | None = None,
    ) -> str:
        message_body = json.dumps(payload)
        queue_name = _extract_queue_name(queue_url)
        run_id = payload.get("run_id")
        site_id = payload.get("site_id")

        try:
            async with self.session.client(
                "sqs", region_name=self.region_name
            ) as sqs_client:
                response = await sqs_client.send_message(
                    QueueUrl=queue_url,
                    MessageBody=message_body,
                )
        except ClientError as client_error:
            error_code = client_error.response.get("Error", {}).get("Code", "Unknown")
            log_event(
                logger,
                logging.ERROR,
                "discoverable.message.failed",
                service="server",
                component="sqs_client",
                request_id=request_id,
                queue_name=queue_name,
                run_id=run_id,
                site_id=site_id,
                error_code=error_code,
            )
            raise RuntimeError(
                f"Failed to send SQS message: {error_code}"
            ) from client_error

        message_id = str(response["MessageId"])
        log_event(
            logger,
            logging.INFO,
            "discoverable.message.sent",
            service="server",
            component="sqs_client",
            request_id=request_id,
            queue_name=queue_name,
            run_id=run_id,
            site_id=site_id,
            message_id=message_id,
        )
        return message_id

    async def receive_messages(
        self,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
        visibility_timeout: int | None = None,
    ) -> list[dict[str, Any]]:
        receive_parameters: dict[str, Any] = {
            "QueueUrl": self.queue_url,
            "MaxNumberOfMessages": max_messages,
            "WaitTimeSeconds": wait_time_seconds,
        }
        if visibility_timeout is not None:
            receive_parameters["VisibilityTimeout"] = visibility_timeout

        async with self.session.client(
            "sqs", region_name=self.region_name
        ) as sqs_client:
            response = await sqs_client.receive_message(**receive_parameters)

        return response.get("Messages", [])

    async def delete_message(self, receipt_handle: str) -> None:
        async with self.session.client(
            "sqs", region_name=self.region_name
        ) as sqs_client:
            await sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
            )


def _extract_queue_name(queue_url: str) -> str:
    parsed_url = urlparse(queue_url)
    return parsed_url.path.rsplit("/", maxsplit=1)[-1]
