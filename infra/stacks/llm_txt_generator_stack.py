from aws_cdk import CfnOutput, Stack
from constructs import Construct

from components.discoverability_queue_service import DiscoverabilityQueueService
from components.generate_api_service import GenerateApiService
from components.generated_output_storage import GeneratedOutputStorage
from components.generation_data_storage import GenerationDataStorage
from components.http_fetcher_service import HttpFetcherService
from components.llm_generation_queue_service import LlmGenerationQueueService
from components.orchestrator_service import OrchestratorService
from components.processing_service import ProcessingService
from components.raw_html_storage import RawHtmlStorage
from components.spa_fetcher_service import SpaFetcherService


class LlmTxtGeneratorStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        discoverability_queue_service = DiscoverabilityQueueService(
            self, "DiscoverabilityQueueService"
        )
        raw_html_storage = RawHtmlStorage(self, "RawHtmlStorage")
        generated_output_storage = GeneratedOutputStorage(
            self, "GeneratedOutputStorage"
        )
        llm_generation_queue_service = LlmGenerationQueueService(
            self, "LlmGenerationQueueService"
        )
        generation_data_storage = GenerationDataStorage(self, "GenerationDataStorage")
        generate_api_service = GenerateApiService(
            self,
            "GenerateApiService",
            discoverable_topic_arn=discoverability_queue_service.discoverable_events_topic.topic_arn,
            database_url=generation_data_storage.database_url,
            server_runtime_role_arn=discoverability_queue_service.server_runtime_role.role_arn,
            region_name=self.region,
        )
        orchestrator_service = OrchestratorService(
            self,
            "OrchestratorService",
            vpc=generation_data_storage.vpc,
            database_security_group=generation_data_storage.database_security_group,
            region_name=self.region,
            database_url=generation_data_storage.database_url,
            discoverable_queue=discoverability_queue_service.discoverable_queue,
            fetch_events_topic=discoverability_queue_service.fetch_events_topic,
            processing_events_topic=discoverability_queue_service.processing_events_topic,
        )
        http_fetcher_service = HttpFetcherService(
            self,
            "HttpFetcherService",
            database_url=generation_data_storage.database_url,
            http_fetch_queue=discoverability_queue_service.http_fetch_queue,
            raw_html_bucket=raw_html_storage.raw_html_bucket,
            discoverable_topic=discoverability_queue_service.discoverable_events_topic,
        )
        spa_fetcher_service = SpaFetcherService(
            self,
            "SpaFetcherService",
            vpc=generation_data_storage.vpc,
            database_security_group=generation_data_storage.database_security_group,
            region_name=self.region,
            database_url=generation_data_storage.database_url,
            spa_fetch_queue=discoverability_queue_service.spa_fetch_queue,
            raw_html_bucket=raw_html_storage.raw_html_bucket,
            discoverable_topic=discoverability_queue_service.discoverable_events_topic,
        )
        processing_service = ProcessingService(
            self,
            "ProcessingService",
            database_url=generation_data_storage.database_url,
            processing_queue=discoverability_queue_service.processing_queue,
            raw_html_bucket=raw_html_storage.raw_html_bucket,
            generated_output_bucket=generated_output_storage.generated_output_bucket,
            llm_generation_topic=llm_generation_queue_service.llm_generation_events_topic,
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
            description="Discoverable queue URL for orchestrator consumer runtime",
        )
        CfnOutput(
            self,
            "DiscoverableQueueArn",
            value=discoverability_queue_service.discoverable_queue.queue_arn,
            description="Discoverable queue ARN for IAM/ops references",
        )
        CfnOutput(
            self,
            "DiscoverableTopicArn",
            value=discoverability_queue_service.discoverable_events_topic.topic_arn,
            description="Discoverable SNS topic ARN",
        )
        CfnOutput(
            self,
            "DiscoverableDeadLetterQueueArn",
            value=discoverability_queue_service.discoverable_dead_letter_queue.queue_arn,
            description="DLQ ARN for alarms and dead-letter inspections",
        )
        CfnOutput(
            self,
            "HttpFetchQueueUrl",
            value=discoverability_queue_service.http_fetch_queue.queue_url,
            description="HTTP fetch destination queue URL",
        )
        CfnOutput(
            self,
            "SpaFetchQueueUrl",
            value=discoverability_queue_service.spa_fetch_queue.queue_url,
            description="SPA fetch destination queue URL",
        )
        CfnOutput(
            self,
            "FetchTopicArn",
            value=discoverability_queue_service.fetch_events_topic.topic_arn,
            description="Fetch SNS topic ARN",
        )
        CfnOutput(
            self,
            "ProcessingTopicArn",
            value=discoverability_queue_service.processing_events_topic.topic_arn,
            description="Processing SNS topic ARN",
        )
        CfnOutput(
            self,
            "ProcessingQueueUrl",
            value=discoverability_queue_service.processing_queue.queue_url,
            description="Processing queue URL for downstream consumers",
        )
        CfnOutput(
            self,
            "ProcessingDeadLetterQueueArn",
            value=discoverability_queue_service.processing_dead_letter_queue.queue_arn,
            description="Processing DLQ ARN for dead-letter inspections",
        )
        CfnOutput(
            self,
            "RawHtmlBucketName",
            value=raw_html_storage.raw_html_bucket.bucket_name,
            description="Raw HTML artifact bucket name",
        )
        CfnOutput(
            self,
            "RawHtmlBucketArn",
            value=raw_html_storage.raw_html_bucket.bucket_arn,
            description="Raw HTML artifact bucket ARN",
        )
        CfnOutput(
            self,
            "GeneratedOutputBucketName",
            value=generated_output_storage.generated_output_bucket.bucket_name,
            description="Generated llms.txt output bucket name",
        )
        CfnOutput(
            self,
            "GeneratedOutputBucketArn",
            value=generated_output_storage.generated_output_bucket.bucket_arn,
            description="Generated llms.txt output bucket ARN",
        )
        CfnOutput(
            self,
            "LlmGenerationTopicArn",
            value=llm_generation_queue_service.llm_generation_events_topic.topic_arn,
            description="LLM generation SNS topic ARN",
        )
        CfnOutput(
            self,
            "LlmGenerationQueueUrl",
            value=llm_generation_queue_service.llm_generation_queue.queue_url,
            description="LLM generation queue URL",
        )
        CfnOutput(
            self,
            "LlmGenerationDeadLetterQueueArn",
            value=llm_generation_queue_service.llm_generation_dead_letter_queue.queue_arn,
            description="LLM generation dead-letter queue ARN",
        )
        CfnOutput(
            self,
            "OrchestratorServiceArn",
            value=orchestrator_service.service.service_arn,
            description="ECS service ARN for orchestrator worker",
        )
        CfnOutput(
            self,
            "HttpFetcherFunctionName",
            value=http_fetcher_service.function.function_name,
            description="Lambda function name for HTTP fetch consumer",
        )
        CfnOutput(
            self,
            "ProcessingFunctionName",
            value=processing_service.function.function_name,
            description="Lambda function name for processing consumer",
        )
        CfnOutput(
            self,
            "SpaFetcherServiceArn",
            value=spa_fetcher_service.service.service_arn,
            description="ECS service ARN for SPA fetch worker",
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
