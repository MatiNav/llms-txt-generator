import aioboto3
from botocore.exceptions import ClientError


class LlmGeneratorArtifactStorage:
    def __init__(self, *, region_name: str, generated_output_bucket_name: str) -> None:
        self.region_name = region_name
        self.generated_output_bucket_name = generated_output_bucket_name
        self.session = aioboto3.Session()

    async def list_generated_keys(self, run_id: str) -> list[str]:
        prefix = self.generated_prefix(run_id)
        keys: list[str] = []
        async with self.session.client("s3", region_name=self.region_name) as s3_client:
            paginator = s3_client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(
                Bucket=self.generated_output_bucket_name,
                Prefix=prefix,
            ):
                for entry in page.get("Contents", []):
                    key_value = entry.get("Key")
                    if isinstance(key_value, str):
                        keys.append(key_value)
        return sorted(keys)

    async def read_text(self, generated_key: str) -> str:
        async with self.session.client("s3", region_name=self.region_name) as s3_client:
            try:
                response = await s3_client.get_object(
                    Bucket=self.generated_output_bucket_name,
                    Key=generated_key,
                )
            except ClientError as client_error:
                raise RuntimeError(
                    f"Failed to read generated artifact: {generated_key}"
                ) from client_error

            body_bytes = await response["Body"].read()
            return body_bytes.decode("utf-8", errors="replace")

    async def write_text(
        self, generated_key: str, content: str, *, run_id: str
    ) -> None:
        async with self.session.client("s3", region_name=self.region_name) as s3_client:
            await s3_client.put_object(
                Bucket=self.generated_output_bucket_name,
                Key=generated_key,
                Body=content.encode("utf-8"),
                ContentType="text/markdown; charset=utf-8",
                Metadata={"run_id": run_id, "enriched": "true"},
            )

    @staticmethod
    def generated_prefix(run_id: str) -> str:
        return f"runs/{run_id}/generated/"
