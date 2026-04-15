import logging
from uuid import UUID

import aioboto3

from server.errors.run import RunNotCompletedError
from server.schemas.downloads import RunDownloadsResponse
from server.services.run_service import RunService
from shared.constants.run_state import RUN_STATE_COMPLETED
from shared.logging import log_event


logger = logging.getLogger(__name__)


class DownloadService:
    def __init__(
        self,
        *,
        run_service: RunService,
        aws_region: str,
        generated_output_bucket_name: str,
        download_url_ttl_seconds: int,
    ) -> None:
        self.run_service = run_service
        self.aws_region = aws_region
        self.generated_output_bucket_name = generated_output_bucket_name
        self.download_url_ttl_seconds = download_url_ttl_seconds

    async def get_run_download_links(self, run_id: UUID) -> RunDownloadsResponse | None:
        run_snapshot = await self.run_service.get_run_snapshot(run_id=run_id)
        if run_snapshot is None:
            return None

        if run_snapshot.run_state != RUN_STATE_COMPLETED:
            raise RunNotCompletedError(run_state=run_snapshot.run_state)

        if self.generated_output_bucket_name == "":
            raise RuntimeError("GENERATED_OUTPUT_BUCKET_NAME is not configured")

        llms_txt_url = await self._sign_if_present(run_snapshot.llms_txt_s3_key)
        bundle_zip_url = await self._sign_if_present(run_snapshot.bundle_s3_key)
        return RunDownloadsResponse(
            run_id=run_snapshot.run_id,
            llms_txt_url=llms_txt_url,
            bundle_zip_url=bundle_zip_url,
            expires_in_seconds=self.download_url_ttl_seconds,
        )

    async def _sign_if_present(self, object_key: str | None) -> str | None:
        if object_key is None:
            return None

        session = aioboto3.Session()
        async with session.client("s3", region_name=self.aws_region) as s3_client:
            await s3_client.head_object(
                Bucket=self.generated_output_bucket_name,
                Key=object_key,
            )
            signed_url = await s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.generated_output_bucket_name,
                    "Key": object_key,
                },
                ExpiresIn=self.download_url_ttl_seconds,
            )
            log_event(
                logger,
                logging.INFO,
                "download.presigned_url.generated",
                service="server",
                component="download_service",
                object_key=object_key,
                ttl_seconds=self.download_url_ttl_seconds,
            )
            return signed_url
