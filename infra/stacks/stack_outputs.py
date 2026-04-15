from typing import Any

from aws_cdk import CfnOutput, Stack


def emit_stack_outputs(
    *,
    stack: Stack,
    generate_api_service: Any,
    domain_service: Any,
    discoverability_queue_service: Any,
    raw_html_storage: Any,
    generated_output_storage: Any,
    llm_generation_queue_service: Any,
    orchestrator_service: Any,
    http_fetcher_service: Any,
    processing_service: Any,
    llm_generator_service: Any,
    site_refresher_service: Any,
    spa_fetcher_service: Any,
    generation_data_storage: Any,
) -> None:
    CfnOutput(
        stack,
        "ServerServiceUrl",
        value=f"https://{generate_api_service.server_service.attr_service_url}",
        description="Public URL for the App Runner server",
    )
    CfnOutput(
        stack,
        "FrontendPublicDomainUrl",
        value=f"https://{domain_service.domain_names.frontend_domain_name}",
        description="Public URL for the frontend domain",
    )
    CfnOutput(
        stack,
        "ApiPublicDomainUrl",
        value=f"https://{domain_service.domain_names.api_domain_name}",
        description="Public URL for the API custom domain",
    )
    CfnOutput(
        stack,
        "DiscoverableQueueUrl",
        value=discoverability_queue_service.discoverable_queue.queue_url,
        description="Discoverable queue URL for orchestrator consumer runtime",
    )
    CfnOutput(
        stack,
        "DiscoverableQueueArn",
        value=discoverability_queue_service.discoverable_queue.queue_arn,
        description="Discoverable queue ARN for IAM/ops references",
    )
    CfnOutput(
        stack,
        "DiscoverableTopicArn",
        value=discoverability_queue_service.discoverable_events_topic.topic_arn,
        description="Discoverable SNS topic ARN",
    )
    CfnOutput(
        stack,
        "DiscoverableDeadLetterQueueArn",
        value=discoverability_queue_service.discoverable_dead_letter_queue.queue_arn,
        description="DLQ ARN for alarms and dead-letter inspections",
    )
    CfnOutput(
        stack,
        "HttpFetchQueueUrl",
        value=discoverability_queue_service.http_fetch_queue.queue_url,
        description="HTTP fetch destination queue URL",
    )
    CfnOutput(
        stack,
        "SpaFetchQueueUrl",
        value=discoverability_queue_service.spa_fetch_queue.queue_url,
        description="SPA fetch destination queue URL",
    )
    CfnOutput(
        stack,
        "FetchTopicArn",
        value=discoverability_queue_service.fetch_events_topic.topic_arn,
        description="Fetch SNS topic ARN",
    )
    CfnOutput(
        stack,
        "ProcessingTopicArn",
        value=discoverability_queue_service.processing_events_topic.topic_arn,
        description="Processing SNS topic ARN",
    )
    CfnOutput(
        stack,
        "ProcessingQueueUrl",
        value=discoverability_queue_service.processing_queue.queue_url,
        description="Processing queue URL for downstream consumers",
    )
    CfnOutput(
        stack,
        "ProcessingDeadLetterQueueArn",
        value=discoverability_queue_service.processing_dead_letter_queue.queue_arn,
        description="Processing DLQ ARN for dead-letter inspections",
    )
    CfnOutput(
        stack,
        "RawHtmlBucketName",
        value=raw_html_storage.raw_html_bucket.bucket_name,
        description="Raw HTML artifact bucket name",
    )
    CfnOutput(
        stack,
        "RawHtmlBucketArn",
        value=raw_html_storage.raw_html_bucket.bucket_arn,
        description="Raw HTML artifact bucket ARN",
    )
    CfnOutput(
        stack,
        "GeneratedOutputBucketName",
        value=generated_output_storage.generated_output_bucket.bucket_name,
        description="Generated llms.txt output bucket name",
    )
    CfnOutput(
        stack,
        "GeneratedOutputBucketArn",
        value=generated_output_storage.generated_output_bucket.bucket_arn,
        description="Generated llms.txt output bucket ARN",
    )
    CfnOutput(
        stack,
        "LlmGenerationTopicArn",
        value=llm_generation_queue_service.llm_generation_events_topic.topic_arn,
        description="LLM generation SNS topic ARN",
    )
    CfnOutput(
        stack,
        "LlmGenerationQueueUrl",
        value=llm_generation_queue_service.llm_generation_queue.queue_url,
        description="LLM generation queue URL",
    )
    CfnOutput(
        stack,
        "LlmGenerationDeadLetterQueueArn",
        value=llm_generation_queue_service.llm_generation_dead_letter_queue.queue_arn,
        description="LLM generation dead-letter queue ARN",
    )
    CfnOutput(
        stack,
        "OrchestratorServiceArn",
        value=orchestrator_service.service.service_arn,
        description="ECS service ARN for orchestrator worker",
    )
    CfnOutput(
        stack,
        "HttpFetcherFunctionName",
        value=http_fetcher_service.function.function_name,
        description="Lambda function name for HTTP fetch consumer",
    )
    CfnOutput(
        stack,
        "ProcessingFunctionName",
        value=processing_service.function.function_name,
        description="Lambda function name for processing consumer",
    )
    CfnOutput(
        stack,
        "LlmGeneratorFunctionName",
        value=llm_generator_service.function.function_name,
        description="Lambda function name for llm generation consumer",
    )
    CfnOutput(
        stack,
        "SiteRefresherFunctionName",
        value=site_refresher_service.function.function_name,
        description="Lambda function name for site refresher producer",
    )
    CfnOutput(
        stack,
        "SiteRefresherTopicArn",
        value=site_refresher_service.topic.topic_arn,
        description="SNS topic ARN for site refresher events",
    )
    CfnOutput(
        stack,
        "SpaFetcherServiceArn",
        value=spa_fetcher_service.service.service_arn,
        description="ECS service ARN for SPA fetch worker",
    )
    CfnOutput(
        stack,
        "ServerRuntimeRoleArn",
        value=discoverability_queue_service.server_runtime_role.role_arn,
        description="App Runner instance role ARN",
    )
    CfnOutput(
        stack,
        "DatabaseEndpointAddress",
        value=generation_data_storage.database_instance.db_instance_endpoint_address,
        description="PostgreSQL endpoint hostname",
    )
    CfnOutput(
        stack,
        "DatabasePort",
        value=generation_data_storage.database_instance.db_instance_endpoint_port,
        description="PostgreSQL endpoint port",
    )
    CfnOutput(
        stack,
        "DatabaseName",
        value=generation_data_storage.database_name,
        description="Database name used by the server",
    )
    CfnOutput(
        stack,
        "DatabaseSecretArn",
        value=generation_data_storage.database_secret.secret_arn,
        description="Secrets Manager ARN containing DB credentials",
    )
