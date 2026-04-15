from pathlib import Path

from aws_cdk import BundlingOptions, Duration, IgnoreMode
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class LlmGeneratorService(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        database_url: str,
        llm_generation_queue: sqs.IQueue,
        generated_output_bucket: s3.IBucket,
        openai_api_key: str,
        openai_model_name: str,
    ) -> None:
        super().__init__(scope, construct_id)

        repository_root = Path(__file__).resolve().parents[2]
        llm_generator_function = lambda_.Function(
            self,
            "LlmGeneratorFunction",
            function_name="llmstxt-llm-generator",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="handlers.lambdas.llm_generator.handler.handler",
            timeout=Duration.seconds(120),
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
                "GENERATED_OUTPUT_BUCKET_NAME": generated_output_bucket.bucket_name,
                "OPENAI_API_KEY": openai_api_key,
                "OPENAI_MODEL_NAME": openai_model_name,
            },
        )

        llm_generator_function.add_event_source(
            lambda_event_sources.SqsEventSource(
                llm_generation_queue,
                batch_size=5,
                max_batching_window=Duration.seconds(5),
                report_batch_item_failures=True,
            )
        )

        llm_generation_queue.grant_consume_messages(llm_generator_function)
        generated_output_bucket.grant_read_write(llm_generator_function)

        self.function = llm_generator_function
