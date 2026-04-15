from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as events_targets
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from components.python_lambda_factory import build_python_lambda


class SiteRefresherService(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        database_url: str,
        discoverable_queue: sqs.IQueue,
    ) -> None:
        super().__init__(scope, construct_id)

        site_refresher_topic = sns.Topic(
            self,
            "SiteRefresherEventsTopic",
            topic_name="llmstxt-site-refresher-events",
        )
        site_refresher_topic.add_subscription(
            sns_subscriptions.SqsSubscription(
                discoverable_queue,
                raw_message_delivery=True,
            )
        )

        site_refresher_function = build_python_lambda(
            scope=self,
            construct_id="SiteRefresherFunction",
            function_name="llmstxt-site-refresher",
            handler="handlers.lambdas.site_refresher.handler.handler",
            timeout_seconds=120,
            memory_size=512,
            environment={
                "DATABASE_URL": database_url,
                "SITE_REFRESHER_TOPIC_ARN": site_refresher_topic.topic_arn,
            },
        )

        site_refresher_topic.grant_publish(site_refresher_function)

        daily_refresh_rule = events.Rule(
            self,
            "DailySiteRefresherRule",
            description="Daily site refresher trigger",
            schedule=events.Schedule.cron(
                minute="0",
                hour="3",
            ),
        )
        daily_refresh_rule.add_target(
            events_targets.LambdaFunction(site_refresher_function)
        )

        self.topic = site_refresher_topic
        self.function = site_refresher_function
        self.rule = daily_refresh_rule
