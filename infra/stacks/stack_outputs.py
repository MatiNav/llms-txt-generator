from typing import Any

from aws_cdk import CfnOutput, Stack


def emit_stack_outputs(
    *,
    stack: Stack,
    domain_service: Any,
    discoverability_queue_service: Any,
    raw_html_storage: Any,
    generated_output_storage: Any,
    generation_data_storage: Any,
) -> None:
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
        "RawHtmlBucketName",
        value=raw_html_storage.raw_html_bucket.bucket_name,
        description="Raw HTML artifact bucket name",
    )
    CfnOutput(
        stack,
        "GeneratedOutputBucketName",
        value=generated_output_storage.generated_output_bucket.bucket_name,
        description="Generated llms.txt output bucket name",
    )
    CfnOutput(
        stack,
        "DatabaseSecretArn",
        value=generation_data_storage.database_secret.secret_arn,
        description="Secrets Manager ARN containing DB credentials",
    )
