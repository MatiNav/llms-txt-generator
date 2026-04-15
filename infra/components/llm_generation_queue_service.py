from aws_cdk import Duration
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class LlmGenerationQueueService(Construct):
    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        llm_generation_dead_letter_queue = sqs.Queue(
            self,
            "LlmGenerationDeadLetterQueue",
            queue_name="llmstxt-llm-generation-dlq",
            retention_period=Duration.days(14),
        )

        llm_generation_queue = sqs.Queue(
            self,
            "LlmGenerationQueue",
            queue_name="llmstxt-llm-generation",
            visibility_timeout=Duration.seconds(180),
            receive_message_wait_time=Duration.seconds(20),
            dead_letter_queue=sqs.DeadLetterQueue(
                queue=llm_generation_dead_letter_queue,
                max_receive_count=5,
            ),
        )

        llm_generation_events_topic = sns.Topic(
            self,
            "LlmGenerationEventsTopic",
            topic_name="llmstxt-llm-generation-events",
        )

        llm_generation_events_topic.add_subscription(
            sns_subscriptions.SqsSubscription(
                llm_generation_queue,
                raw_message_delivery=True,
            )
        )

        self.llm_generation_dead_letter_queue = llm_generation_dead_letter_queue
        self.llm_generation_queue = llm_generation_queue
        self.llm_generation_events_topic = llm_generation_events_topic
