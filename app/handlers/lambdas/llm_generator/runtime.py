from dataclasses import dataclass

from handlers.lambdas.llm_generator.artifact_storage import LlmGeneratorArtifactStorage
from handlers.lambdas.llm_generator.config import load_runtime_config
from handlers.lambdas.llm_generator.openai_client import OpenAiSummaryClient
from handlers.lambdas.llm_generator.repository import LlmGeneratorRepository
from handlers.lambdas.llm_generator.service import LlmGeneratorService
from shared.db.session import get_session_factory


@dataclass(frozen=True)
class LlmGeneratorRuntime:
    repository: LlmGeneratorRepository
    service: LlmGeneratorService


def build_llm_generator_runtime() -> LlmGeneratorRuntime:
    runtime_config = load_runtime_config()
    database_session = get_session_factory()()

    repository = LlmGeneratorRepository(database_session=database_session)
    artifact_storage = LlmGeneratorArtifactStorage(
        region_name=runtime_config.aws_region,
        generated_output_bucket_name=runtime_config.generated_output_bucket_name,
    )
    openai_client = OpenAiSummaryClient(
        api_key=runtime_config.openai_api_key,
        model_name=runtime_config.openai_model_name,
        timeout_seconds=runtime_config.openai_timeout_seconds,
        max_retries=runtime_config.openai_max_retries,
    )
    service = LlmGeneratorService(
        repository=repository,
        artifact_storage=artifact_storage,
        openai_client=openai_client,
    )

    return LlmGeneratorRuntime(repository=repository, service=service)
