from aws_cdk import Duration
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from components.python_lambda_factory import build_python_lambda


class HttpFetcherService(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        database_url: str,
        http_fetch_queue: sqs.IQueue,
        raw_html_bucket: s3.IBucket,
        discoverable_topic: sns.ITopic,
    ) -> None:
        super().__init__(scope, construct_id)

        http_fetcher_function = build_python_lambda(
            scope=self,
            construct_id="HttpFetcherFunction",
            function_name="llmstxt-http-fetcher",
            handler="handlers.lambdas.http_fetcher.handler.handler",
            timeout_seconds=90,
            memory_size=512,
            environment={
                "DATABASE_URL": database_url,
                "RAW_HTML_BUCKET_NAME": raw_html_bucket.bucket_name,
                "DISCOVERABLE_TOPIC_ARN": discoverable_topic.topic_arn,
            },
        )

        http_fetcher_function.add_event_source(
            lambda_event_sources.SqsEventSource(
                http_fetch_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(5),
                report_batch_item_failures=True,
            )
        )

        http_fetch_queue.grant_consume_messages(http_fetcher_function)
        raw_html_bucket.grant_put(http_fetcher_function)
        discoverable_topic.grant_publish(http_fetcher_function)

        self.function = http_fetcher_function
