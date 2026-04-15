from aws_cdk import Duration
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from components.python_lambda_factory import build_python_lambda


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

        llm_generator_function = build_python_lambda(
            scope=self,
            construct_id="LlmGeneratorFunction",
            function_name="llmstxt-llm-generator",
            handler="handlers.lambdas.llm_generator.handler.handler",
            timeout_seconds=120,
            memory_size=1024,
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
