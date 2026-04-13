from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class ServerMessagingStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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

        server_runtime_role = iam.Role(
            self,
            "ServerRuntimeRole",
            role_name="llmstxt-server-runtime-role",
            assumed_by=iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
        )

        self.discoverable_dead_letter_queue = discoverable_dead_letter_queue
        self.discoverable_queue = discoverable_queue
        self.server_runtime_role = server_runtime_role

        discoverable_queue.grant_send_messages(server_runtime_role)

        CfnOutput(
            self,
            "DiscoverableQueueUrl",
            value=discoverable_queue.queue_url,
            description="Set as DISCOVERABLE_QUEUE_URL in server runtime env",
        )

        CfnOutput(
            self,
            "AwsRegion",
            value=self.region,
            description="Set as AWS_REGION in server runtime env",
        )

        CfnOutput(
            self,
            "DiscoverableQueueArn",
            value=discoverable_queue.queue_arn,
            description="Discoverable queue ARN for IAM/ops references",
        )

        CfnOutput(
            self,
            "DiscoverableDeadLetterQueueArn",
            value=discoverable_dead_letter_queue.queue_arn,
            description="DLQ ARN for alarms and dead-letter inspections",
        )

        CfnOutput(
            self,
            "ServerRuntimeRoleArn",
            value=server_runtime_role.role_arn,
            description="Attach this role to App Runner instance configuration",
        )
