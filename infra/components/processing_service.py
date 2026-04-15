from pathlib import Path

from aws_cdk import BundlingOptions, Duration, IgnoreMode
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class ProcessingService(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        database_url: str,
        processing_queue: sqs.IQueue,
        raw_html_bucket: s3.IBucket,
        generated_output_bucket: s3.IBucket,
        llm_generation_topic: sns.ITopic,
    ) -> None:
        super().__init__(scope, construct_id)

        repository_root = Path(__file__).resolve().parents[2]
        processing_function = lambda_.Function(
            self,
            "ProcessingFunction",
            function_name="llmstxt-processing",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="handlers.lambdas.processing.handler.handler",
            timeout=Duration.seconds(90),
            memory_size=1024,
            code=lambda_.Code.from_asset(
                str(repository_root),
                ignore_mode=IgnoreMode.GLOB,
                exclude=[
                    "infra/cdk.out",
                    "infra/.venv",
                    "**/__pycache__",
                    "**/.pytest_cache",
                ],
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash",
                        "-lc",
                        "pip install --no-cache-dir ./app/shared -t /asset-output && cp -R app/handlers /asset-output/handlers",
                    ],
                ),
            ),
            environment={
                "DATABASE_URL": database_url,
                "RAW_HTML_BUCKET_NAME": raw_html_bucket.bucket_name,
                "GENERATED_OUTPUT_BUCKET_NAME": generated_output_bucket.bucket_name,
                "LLM_GENERATION_TOPIC_ARN": llm_generation_topic.topic_arn,
            },
        )

        processing_function.add_event_source(
            lambda_event_sources.SqsEventSource(
                processing_queue,
                batch_size=5,
                max_batching_window=Duration.seconds(5),
                report_batch_item_failures=True,
            )
        )

        processing_queue.grant_consume_messages(processing_function)
        raw_html_bucket.grant_read(processing_function)
        generated_output_bucket.grant_read_write(processing_function)
        llm_generation_topic.grant_publish(processing_function)

        self.function = processing_function
