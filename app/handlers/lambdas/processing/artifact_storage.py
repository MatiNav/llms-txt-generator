import aioboto3
from botocore.exceptions import ClientError


class ProcessingArtifactStorage:
    def __init__(
        self,
        *,
        region_name: str,
        raw_html_bucket_name: str,
        generated_output_bucket_name: str,
    ) -> None:
        self.region_name = region_name
        self.raw_html_bucket_name = raw_html_bucket_name
        self.generated_output_bucket_name = generated_output_bucket_name
        self.session = aioboto3.Session()

    async def read_raw_html(self, raw_html_key: str) -> str:
        async with self.session.client("s3", region_name=self.region_name) as s3_client:
            try:
                response = await s3_client.get_object(
                    Bucket=self.raw_html_bucket_name,
                    Key=raw_html_key,
                )
            except ClientError as client_error:
                raise RuntimeError(
                    f"Failed to read raw html key: {raw_html_key}"
                ) from client_error

            payload_bytes = await response["Body"].read()
            return payload_bytes.decode("utf-8", errors="replace")

    async def write_generated_file(
        self, *, run_id: str, relative_path: str, content: str
    ) -> str:
        generated_key = self.build_generated_key(
            run_id=run_id,
            relative_path=relative_path,
        )
        async with self.session.client("s3", region_name=self.region_name) as s3_client:
            await s3_client.put_object(
                Bucket=self.generated_output_bucket_name,
                Key=generated_key,
                Body=content.encode("utf-8"),
                ContentType="text/markdown; charset=utf-8",
                Metadata={"run_id": run_id},
            )
        return generated_key

    @staticmethod
    def build_generated_key(*, run_id: str, relative_path: str) -> str:
        normalized_relative_path = relative_path.lstrip("/")
        return f"runs/{run_id}/generated/{normalized_relative_path}"

    @staticmethod
    def generated_bundle_prefix(run_id: str) -> str:
        return f"runs/{run_id}/generated/"
