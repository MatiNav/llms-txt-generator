from pathlib import Path

from aws_cdk import CfnOutput, IgnoreMode, Stack
from aws_cdk import aws_apprunner as apprunner
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from constructs import Construct


class ServerRuntimeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        discoverable_queue_url: str,
        database_url: str,
        server_runtime_role_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repository_root = Path(__file__).resolve().parents[2]
        server_image_asset = ecr_assets.DockerImageAsset(
            self,
            "ServerImageAsset",
            directory=str(repository_root),
            file="app/server/Dockerfile",
            ignore_mode=IgnoreMode.GLOB,
            exclude=[
                "infra/cdk.out",
                "infra/.venv",
                "**/__pycache__",
                "**/.pytest_cache",
            ],
        )

        app_runner_ecr_access_role = iam.Role(
            self,
            "AppRunnerEcrAccessRole",
            assumed_by=iam.ServicePrincipal("build.apprunner.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSAppRunnerServicePolicyForECRAccess"
                )
            ],
        )
        server_image_asset.repository.grant_pull(app_runner_ecr_access_role)

        server_service = apprunner.CfnService(
            self,
            "ServerService",
            service_name="llmstxt-server",
            health_check_configuration=apprunner.CfnService.HealthCheckConfigurationProperty(
                protocol="HTTP",
                path="/health",
            ),
            source_configuration=apprunner.CfnService.SourceConfigurationProperty(
                auto_deployments_enabled=False,
                authentication_configuration=apprunner.CfnService.AuthenticationConfigurationProperty(
                    access_role_arn=app_runner_ecr_access_role.role_arn,
                ),
                image_repository=apprunner.CfnService.ImageRepositoryProperty(
                    image_repository_type="ECR",
                    image_identifier=server_image_asset.image_uri,
                    image_configuration=apprunner.CfnService.ImageConfigurationProperty(
                        port="8000",
                        runtime_environment_variables=[
                            apprunner.CfnService.KeyValuePairProperty(
                                name="AWS_REGION",
                                value=self.region,
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="DISCOVERABLE_QUEUE_URL",
                                value=discoverable_queue_url,
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="DATABASE_URL",
                                value=database_url,
                            ),
                        ],
                    ),
                ),
            ),
            instance_configuration=apprunner.CfnService.InstanceConfigurationProperty(
                cpu="0.25 vCPU",
                memory="0.5 GB",
                instance_role_arn=server_runtime_role_arn,
            ),
        )

        CfnOutput(
            self,
            "ServerServiceUrl",
            value=f"https://{server_service.attr_service_url}",
            description="Public URL for the App Runner server",
        )
