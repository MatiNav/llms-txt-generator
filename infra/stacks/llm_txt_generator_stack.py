import os

from aws_cdk import Stack
from constructs import Construct

from components.app_runner_domain_service import AppRunnerDomainService
from components.domain_service import DomainService
from components.discoverability_queue_service import DiscoverabilityQueueService
from components.frontend_hosting_service import FrontendHostingService
from components.generate_api_service import GenerateApiService
from components.generated_output_storage import GeneratedOutputStorage
from components.generation_data_storage import GenerationDataStorage
from components.http_fetcher_service import HttpFetcherService
from components.llm_generation_queue_service import LlmGenerationQueueService
from components.llm_generator_service import LlmGeneratorService
from components.orchestrator_service import OrchestratorService
from components.processing_service import ProcessingService
from components.raw_html_storage import RawHtmlStorage
from components.site_refresher_service import SiteRefresherService
from components.spa_fetcher_service import SpaFetcherService
from stacks.stack_outputs import emit_stack_outputs


class LlmTxtGeneratorStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        root_domain_name = "matiasnavarrodev.com"
        frontend_subdomain_name = "profound"
        api_subdomain_name = "profound-api"

        domain_service = DomainService(
            self,
            "DomainService",
            root_domain_name=root_domain_name,
            frontend_subdomain_name=frontend_subdomain_name,
            api_subdomain_name=api_subdomain_name,
        )

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
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is required")
        openai_model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4.1-mini")

        generation_data_storage = GenerationDataStorage(self, "GenerationDataStorage")
        generated_output_storage.generated_output_bucket.grant_read(
            discoverability_queue_service.server_runtime_role
        )
        generate_api_service = GenerateApiService(
            self,
            "GenerateApiService",
            discoverable_topic_arn=discoverability_queue_service.discoverable_events_topic.topic_arn,
            database_url=generation_data_storage.database_url,
            server_runtime_role_arn=discoverability_queue_service.server_runtime_role.role_arn,
            region_name=self.region,
            frontend_origin=f"https://{domain_service.domain_names.frontend_domain_name}",
            generated_output_bucket_name=generated_output_storage.generated_output_bucket.bucket_name,
            download_url_ttl_seconds=900,
        )
        frontend_hosting_service = FrontendHostingService(
            self,
            "FrontendHostingService",
            hosted_zone=domain_service.hosted_zone,
            frontend_domain_name=domain_service.domain_names.frontend_domain_name,
        )
        app_runner_domain_service = AppRunnerDomainService(
            self,
            "AppRunnerDomainService",
            hosted_zone=domain_service.hosted_zone,
            app_runner_service_arn=generate_api_service.server_service.attr_service_arn,
            api_domain_name=domain_service.domain_names.api_domain_name,
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
        llm_generator_service = LlmGeneratorService(
            self,
            "LlmGeneratorService",
            database_url=generation_data_storage.database_url,
            llm_generation_queue=llm_generation_queue_service.llm_generation_queue,
            generated_output_bucket=generated_output_storage.generated_output_bucket,
            openai_api_key=openai_api_key,
            openai_model_name=openai_model_name,
        )
        site_refresher_service = SiteRefresherService(
            self,
            "SiteRefresherService",
            database_url=generation_data_storage.database_url,
            discoverable_queue=discoverability_queue_service.discoverable_queue,
        )

        emit_stack_outputs(
            stack=self,
            generate_api_service=generate_api_service,
            domain_service=domain_service,
            discoverability_queue_service=discoverability_queue_service,
            raw_html_storage=raw_html_storage,
            generated_output_storage=generated_output_storage,
            llm_generation_queue_service=llm_generation_queue_service,
            orchestrator_service=orchestrator_service,
            http_fetcher_service=http_fetcher_service,
            processing_service=processing_service,
            llm_generator_service=llm_generator_service,
            site_refresher_service=site_refresher_service,
            spa_fetcher_service=spa_fetcher_service,
            generation_data_storage=generation_data_storage,
        )
