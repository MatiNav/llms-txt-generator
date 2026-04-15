from pathlib import Path

from aws_cdk import IgnoreMode
from aws_cdk import aws_apprunner as apprunner
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from constructs import Construct


class GenerateApiService(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        discoverable_topic_arn: str,
        database_url: str,
        server_runtime_role_arn: str,
        region_name: str,
        frontend_origin: str,
        generated_output_bucket_name: str,
        download_url_ttl_seconds: int,
    ) -> None:
        super().__init__(scope, construct_id)

        repository_root = Path(__file__).resolve().parents[2]
        server_image_asset = ecr_assets.DockerImageAsset(
            self,
            "ServerImageAsset",
            directory=str(repository_root),
            file="app/server/Dockerfile",
            platform=ecr_assets.Platform.LINUX_AMD64,
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
                                value=region_name,
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="DISCOVERABLE_TOPIC_ARN",
                                value=discoverable_topic_arn,
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="DATABASE_URL",
                                value=database_url,
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="FRONTEND_ORIGIN",
                                value=frontend_origin,
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="GENERATED_OUTPUT_BUCKET_NAME",
                                value=generated_output_bucket_name,
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="DOWNLOAD_URL_TTL_SECONDS",
                                value=str(download_url_ttl_seconds),
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

        self.server_service = server_service
