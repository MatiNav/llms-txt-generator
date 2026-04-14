import aioboto3


class RawHtmlS3Storage:
    def __init__(self, *, bucket_name: str, region_name: str) -> None:
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.session = aioboto3.Session()

    async def save_raw_html(
        self,
        *,
        run_id: str,
        page_id: str,
        html_content: str,
    ) -> str:
        s3_key = f"runs/{run_id}/pages/{page_id}/raw.html"
        async with self.session.client("s3", region_name=self.region_name) as s3_client:
            await s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=html_content.encode("utf-8"),
                ContentType="text/html; charset=utf-8",
                Metadata={
                    "run_id": run_id,
                    "page_id": page_id,
                },
            )
        return s3_key
