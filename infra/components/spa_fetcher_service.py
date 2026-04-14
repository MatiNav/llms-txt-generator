from pathlib import Path

from aws_cdk import IgnoreMode
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class SpaFetcherService(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        database_security_group: ec2.ISecurityGroup,
        region_name: str,
        database_url: str,
        spa_fetch_queue: sqs.IQueue,
        raw_html_bucket: s3.IBucket,
        discoverable_topic: sns.ITopic,
    ) -> None:
        super().__init__(scope, construct_id)

        repository_root = Path(__file__).resolve().parents[2]
        spa_fetcher_image_asset = ecr_assets.DockerImageAsset(
            self,
            "SpaFetcherImageAsset",
            directory=str(repository_root),
            file="app/handlers/ecs_tasks/spa_fetcher/Dockerfile",
            platform=ecr_assets.Platform.LINUX_AMD64,
            ignore_mode=IgnoreMode.GLOB,
            exclude=[
                "infra/cdk.out",
                "infra/.venv",
                "**/__pycache__",
                "**/.pytest_cache",
            ],
        )

        spa_fetcher_cluster = ecs.Cluster(self, "SpaFetcherCluster", vpc=vpc)
        spa_fetcher_task_definition = ecs.FargateTaskDefinition(
            self,
            "SpaFetcherTaskDefinition",
            cpu=512,
            memory_limit_mib=1024,
        )

        spa_fetcher_task_definition.add_container(
            "SpaFetcherContainer",
            image=ecs.ContainerImage.from_docker_image_asset(spa_fetcher_image_asset),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="spa-fetcher"),
            environment={
                "AWS_REGION": region_name,
                "DATABASE_URL": database_url,
                "SPA_FETCH_QUEUE_URL": spa_fetch_queue.queue_url,
                "RAW_HTML_BUCKET_NAME": raw_html_bucket.bucket_name,
                "DISCOVERABLE_TOPIC_ARN": discoverable_topic.topic_arn,
            },
        )

        spa_fetch_queue.grant_consume_messages(spa_fetcher_task_definition.task_role)
        raw_html_bucket.grant_put(spa_fetcher_task_definition.task_role)
        discoverable_topic.grant_publish(spa_fetcher_task_definition.task_role)

        spa_fetcher_security_group = ec2.SecurityGroup(
            self,
            "SpaFetcherSecurityGroup",
            vpc=vpc,
            description="SPA fetcher ECS task security group",
            allow_all_outbound=True,
        )
        database_security_group.add_ingress_rule(
            peer=spa_fetcher_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow SPA fetcher ECS tasks to reach PostgreSQL",
        )

        # Challenge tradeoff: keep fixed worker count for simplicity/cost control.
        spa_fetcher_service = ecs.FargateService(
            self,
            "SpaFetcherEcsService",
            cluster=spa_fetcher_cluster,
            task_definition=spa_fetcher_task_definition,
            desired_count=1,
            assign_public_ip=True,
            security_groups=[spa_fetcher_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        self.cluster = spa_fetcher_cluster
        self.task_definition = spa_fetcher_task_definition
        self.service = spa_fetcher_service
