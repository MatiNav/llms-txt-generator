from dataclasses import dataclass

from handlers.lambdas.processing.artifact_storage import ProcessingArtifactStorage
from handlers.lambdas.processing.config import load_runtime_config
from handlers.lambdas.processing.repository import ProcessingRepository
from handlers.lambdas.processing.service import ProcessingService
from shared.db.session import get_session_factory
from shared.queue.sns_client import SNSClient


@dataclass(frozen=True)
class ProcessingRuntime:
    processing_service: ProcessingService
    llm_generation_publisher: SNSClient
    llm_generation_topic_arn: str


def build_processing_runtime() -> ProcessingRuntime:
    runtime_config = load_runtime_config()
    database_session = get_session_factory()()

    repository = ProcessingRepository(database_session=database_session)
    artifact_storage = ProcessingArtifactStorage(
        region_name=runtime_config.aws_region,
        raw_html_bucket_name=runtime_config.raw_html_bucket_name,
        generated_output_bucket_name=runtime_config.generated_output_bucket_name,
    )
    processing_service = ProcessingService(
        repository=repository,
        artifact_storage=artifact_storage,
    )
    llm_generation_publisher = SNSClient(
        region_name=runtime_config.aws_region,
        service_name="processing",
    )

    return ProcessingRuntime(
        processing_service=processing_service,
        llm_generation_publisher=llm_generation_publisher,
        llm_generation_topic_arn=runtime_config.llm_generation_topic_arn,
    )
