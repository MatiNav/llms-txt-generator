import json
import logging
from typing import Any

import aioboto3
from botocore.exceptions import ClientError

from shared.logging import log_event


logger = logging.getLogger(__name__)


class SNSClient:
    def __init__(self, region_name: str, service_name: str = "server") -> None:
        self.region_name = region_name
        self.service_name = service_name
        self.session = aioboto3.Session()

    async def publish_message(
        self,
        topic_arn: str,
        payload: dict[str, Any],
        message_attributes: dict[str, dict[str, str]] | None = None,
        request_id: str | None = None,
    ) -> str:
        run_id = payload.get("run_id")
        site_id = payload.get("site_id")

        try:
            async with self.session.client(
                "sns", region_name=self.region_name
            ) as sns_client:
                response = await sns_client.publish(
                    TopicArn=topic_arn,
                    Message=json.dumps(payload),
                    MessageAttributes=message_attributes or {},
                )
        except ClientError as client_error:
            error_code = client_error.response.get("Error", {}).get("Code", "Unknown")
            log_event(
                logger,
                logging.ERROR,
                "sns.message.failed",
                service=self.service_name,
                component="sns_client",
                request_id=request_id,
                topic_arn=topic_arn,
                run_id=run_id,
                site_id=site_id,
                error_code=error_code,
            )
            raise RuntimeError(
                f"Failed to publish SNS message: {error_code}"
            ) from client_error

        message_id = str(response["MessageId"])
        log_event(
            logger,
            logging.INFO,
            "sns.message.published",
            service=self.service_name,
            component="sns_client",
            request_id=request_id,
            topic_arn=topic_arn,
            run_id=run_id,
            site_id=site_id,
            message_id=message_id,
        )
        return message_id
