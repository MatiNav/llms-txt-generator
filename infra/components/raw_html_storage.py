import re

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_s3 as s3
from constructs import Construct


class RawHtmlStorage(Construct):
    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        stack_name_fragment = self._build_stack_name_fragment()
        bucket_name = f"llmstxt-raw-html-{stack_name_fragment}"

        self.raw_html_bucket = s3.Bucket(
            self,
            "RawHtmlBucket",
            bucket_name=bucket_name,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

    def _build_stack_name_fragment(self) -> str:
        stack_name = Stack.of(self).stack_name
        normalized_stack_name = re.sub(r"[^a-z0-9-]", "-", stack_name.lower()).strip(
            "-"
        )
        return normalized_stack_name[:43]
