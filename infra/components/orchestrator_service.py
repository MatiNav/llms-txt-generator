from pathlib import Path

from aws_cdk import Duration, IgnoreMode
from aws_cdk import aws_applicationautoscaling as appscaling
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class OrchestratorService(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        database_security_group: ec2.ISecurityGroup,
        region_name: str,
        database_url: str,
        discoverable_queue: sqs.IQueue,
        fetch_events_topic: sns.ITopic,
    ) -> None:
        super().__init__(scope, construct_id)

        repository_root = Path(__file__).resolve().parents[2]
        orchestrator_image_asset = ecr_assets.DockerImageAsset(
            self,
            "OrchestratorImageAsset",
            directory=str(repository_root),
            file="app/handlers/ecs_tasks/orchestrator/Dockerfile",
            platform=ecr_assets.Platform.LINUX_AMD64,
            ignore_mode=IgnoreMode.GLOB,
            exclude=[
                "infra/cdk.out",
                "infra/.venv",
                "**/__pycache__",
                "**/.pytest_cache",
            ],
        )

        orchestrator_cluster = ecs.Cluster(self, "OrchestratorCluster", vpc=vpc)
        orchestrator_task_definition = ecs.FargateTaskDefinition(
            self,
            "OrchestratorTaskDefinition",
            cpu=256,
            memory_limit_mib=512,
        )

        orchestrator_task_definition.add_container(
            "OrchestratorContainer",
            image=ecs.ContainerImage.from_docker_image_asset(orchestrator_image_asset),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="orchestrator",
                log_retention=logs.RetentionDays.TWO_WEEKS,
            ),
            environment={
                "AWS_REGION": region_name,
                "DATABASE_URL": database_url,
                "DISCOVERABLE_QUEUE_URL": discoverable_queue.queue_url,
                "FETCH_TOPIC_ARN": fetch_events_topic.topic_arn,
            },
        )

        discoverable_queue.grant_consume_messages(
            orchestrator_task_definition.task_role
        )
        fetch_events_topic.grant_publish(orchestrator_task_definition.task_role)

        orchestrator_security_group = ec2.SecurityGroup(
            self,
            "OrchestratorSecurityGroup",
            vpc=vpc,
            description="Orchestrator ECS task security group",
            allow_all_outbound=True,
        )
        database_security_group.add_ingress_rule(
            peer=orchestrator_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow orchestrator ECS tasks to reach PostgreSQL",
        )

        orchestrator_service = ecs.FargateService(
            self,
            "OrchestratorEcsService",
            cluster=orchestrator_cluster,
            task_definition=orchestrator_task_definition,
            desired_count=1,
            assign_public_ip=True,
            security_groups=[orchestrator_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        # We scale on backlog-per-task, not raw queue depth.
        # Why: queue depth alone ignores active worker count.
        # Challenge cap: max_capacity=2 to control cost and complexity.
        scaling_target = orchestrator_service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=2,
        )

        visible_messages_metric = (
            discoverable_queue.metric_approximate_number_of_messages_visible(
                period=Duration.minutes(1),
                statistic="Maximum",
            )
        )
        running_tasks_metric = orchestrator_service.metric(
            metric_name="RunningTaskCount",
            period=Duration.minutes(1),
            statistic="Average",
        )
        backlog_per_task_metric = cloudwatch.MathExpression(
            expression="IF(m2 > 0, m1 / m2, m1)",
            using_metrics={
                "m1": visible_messages_metric,
                "m2": running_tasks_metric,
            },
        )

        scaling_target.scale_on_metric(
            "ScaleOnBacklogPerTask",
            metric=backlog_per_task_metric,
            scaling_steps=[
                appscaling.ScalingInterval(upper=2, change=-1),
                appscaling.ScalingInterval(lower=10, change=+1),
            ],
            adjustment_type=appscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            cooldown=Duration.seconds(60),
            evaluation_periods=2,
            datapoints_to_alarm=2,
        )

        self.cluster = orchestrator_cluster
        self.task_definition = orchestrator_task_definition
        self.service = orchestrator_service
