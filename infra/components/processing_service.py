from aws_cdk import Duration
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from components.python_lambda_factory import build_python_lambda


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

        processing_function = build_python_lambda(
            scope=self,
            construct_id="ProcessingFunction",
            function_name="llmstxt-processing",
            handler="handlers.lambdas.processing.handler.handler",
            timeout_seconds=90,
            memory_size=1024,
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
