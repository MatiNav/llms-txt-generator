from aws_cdk import Duration
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class DiscoverabilityQueueService(Construct):
    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        discoverable_dead_letter_queue = sqs.Queue(
            self,
            "DiscoverableDeadLetterQueue",
            queue_name="llmstxt-discoverable-dlq",
            retention_period=Duration.days(14),
        )

        discoverable_queue = sqs.Queue(
            self,
            "DiscoverableQueue",
            queue_name="llmstxt-discoverable",
            visibility_timeout=Duration.seconds(60),
            receive_message_wait_time=Duration.seconds(20),
            dead_letter_queue=sqs.DeadLetterQueue(
                queue=discoverable_dead_letter_queue,
                max_receive_count=5,
            ),
        )

        http_fetch_dead_letter_queue = sqs.Queue(
            self,
            "HttpFetchDeadLetterQueue",
            queue_name="llmstxt-http-fetch-dlq",
            retention_period=Duration.days(14),
        )

        http_fetch_queue = sqs.Queue(
            self,
            "HttpFetchQueue",
            queue_name="llmstxt-http-fetch",
            visibility_timeout=Duration.seconds(120),
            receive_message_wait_time=Duration.seconds(20),
            dead_letter_queue=sqs.DeadLetterQueue(
                queue=http_fetch_dead_letter_queue,
                max_receive_count=5,
            ),
        )

        spa_fetch_dead_letter_queue = sqs.Queue(
            self,
            "SpaFetchDeadLetterQueue",
            queue_name="llmstxt-spa-fetch-dlq",
            retention_period=Duration.days(14),
        )

        spa_fetch_queue = sqs.Queue(
            self,
            "SpaFetchQueue",
            queue_name="llmstxt-spa-fetch",
            visibility_timeout=Duration.seconds(180),
            receive_message_wait_time=Duration.seconds(20),
            dead_letter_queue=sqs.DeadLetterQueue(
                queue=spa_fetch_dead_letter_queue,
                max_receive_count=5,
            ),
        )

        discoverable_events_topic = sns.Topic(
            self,
            "DiscoverableEventsTopic",
            topic_name="llmstxt-discoverable-events",
        )
        fetch_events_topic = sns.Topic(
            self,
            "FetchEventsTopic",
            topic_name="llmstxt-fetch-events",
        )
        processing_events_topic = sns.Topic(
            self,
            "ProcessingEventsTopic",
            topic_name="llmstxt-processing-events",
        )

        discoverable_events_topic.add_subscription(
            sns_subscriptions.SqsSubscription(
                discoverable_queue,
                raw_message_delivery=True,
            )
        )
        fetch_events_topic.add_subscription(
            sns_subscriptions.SqsSubscription(
                http_fetch_queue,
                raw_message_delivery=True,
                filter_policy={
                    "render_mode": sns.SubscriptionFilter.string_filter(
                        allowlist=["http"]
                    )
                },
            )
        )
        fetch_events_topic.add_subscription(
            sns_subscriptions.SqsSubscription(
                spa_fetch_queue,
                raw_message_delivery=True,
                filter_policy={
                    "render_mode": sns.SubscriptionFilter.string_filter(
                        allowlist=["spa"]
                    )
                },
            )
        )

        server_runtime_role = iam.Role(
            self,
            "ServerRuntimeRole",
            role_name="llmstxt-server-runtime-role",
            assumed_by=iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
        )
        discoverable_events_topic.grant_publish(server_runtime_role)

        self.discoverable_dead_letter_queue = discoverable_dead_letter_queue
        self.discoverable_queue = discoverable_queue
        self.http_fetch_dead_letter_queue = http_fetch_dead_letter_queue
        self.http_fetch_queue = http_fetch_queue
        self.spa_fetch_dead_letter_queue = spa_fetch_dead_letter_queue
        self.spa_fetch_queue = spa_fetch_queue
        self.discoverable_events_topic = discoverable_events_topic
        self.fetch_events_topic = fetch_events_topic
        self.processing_events_topic = processing_events_topic
        self.server_runtime_role = server_runtime_role
