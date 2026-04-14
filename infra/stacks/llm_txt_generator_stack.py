from aws_cdk import CfnOutput, Stack
from constructs import Construct

from components.discoverability_queue_service import DiscoverabilityQueueService
from components.generate_api_service import GenerateApiService
from components.generation_data_storage import GenerationDataStorage


class LlmTxtGeneratorStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        discoverability_queue_service = DiscoverabilityQueueService(
            self, "DiscoverabilityQueueService"
        )
        generation_data_storage = GenerationDataStorage(self, "GenerationDataStorage")
        generate_api_service = GenerateApiService(
            self,
            "GenerateApiService",
            discoverable_queue_url=discoverability_queue_service.discoverable_queue.queue_url,
            database_url=generation_data_storage.database_url,
            server_runtime_role_arn=discoverability_queue_service.server_runtime_role.role_arn,
            region_name=self.region,
        )

        CfnOutput(
            self,
            "ServerServiceUrl",
            value=f"https://{generate_api_service.server_service.attr_service_url}",
            description="Public URL for the App Runner server",
        )
        CfnOutput(
            self,
            "DiscoverableQueueUrl",
            value=discoverability_queue_service.discoverable_queue.queue_url,
            description="Set as DISCOVERABLE_QUEUE_URL in server runtime env",
        )
        CfnOutput(
            self,
            "DiscoverableQueueArn",
            value=discoverability_queue_service.discoverable_queue.queue_arn,
            description="Discoverable queue ARN for IAM/ops references",
        )
        CfnOutput(
            self,
            "DiscoverableDeadLetterQueueArn",
            value=discoverability_queue_service.discoverable_dead_letter_queue.queue_arn,
            description="DLQ ARN for alarms and dead-letter inspections",
        )
        CfnOutput(
            self,
            "ServerRuntimeRoleArn",
            value=discoverability_queue_service.server_runtime_role.role_arn,
            description="App Runner instance role ARN",
        )
        CfnOutput(
            self,
            "DatabaseEndpointAddress",
            value=generation_data_storage.database_instance.db_instance_endpoint_address,
            description="PostgreSQL endpoint hostname",
        )
        CfnOutput(
            self,
            "DatabasePort",
            value=generation_data_storage.database_instance.db_instance_endpoint_port,
            description="PostgreSQL endpoint port",
        )
        CfnOutput(
            self,
            "DatabaseName",
            value=generation_data_storage.database_name,
            description="Database name used by the server",
        )
        CfnOutput(
            self,
            "DatabaseSecretArn",
            value=generation_data_storage.database_secret.secret_arn,
            description="Secrets Manager ARN containing DB credentials",
        )
