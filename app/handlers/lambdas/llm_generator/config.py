import os
from dataclasses import dataclass

from shared.config.env import required_env_value


@dataclass(frozen=True)
class LlmGeneratorRuntimeConfig:
    aws_region: str
    generated_output_bucket_name: str
    openai_api_key: str
    openai_model_name: str
    openai_timeout_seconds: float
    openai_max_retries: int


def load_runtime_config() -> LlmGeneratorRuntimeConfig:
    required_env_value("DATABASE_URL")
    return LlmGeneratorRuntimeConfig(
        aws_region=required_env_value("AWS_REGION"),
        generated_output_bucket_name=required_env_value("GENERATED_OUTPUT_BUCKET_NAME"),
        openai_api_key=required_env_value("OPENAI_API_KEY"),
        openai_model_name=required_env_value("OPENAI_MODEL_NAME"),
        openai_timeout_seconds=_optional_float_env(
            "OPENAI_TIMEOUT_SECONDS",
            default_value=20.0,
        ),
        openai_max_retries=_optional_int_env(
            "OPENAI_MAX_RETRIES",
            default_value=2,
        ),
    )


def _optional_float_env(environment_key: str, *, default_value: float) -> float:
    raw_value = os.getenv(environment_key)
    if raw_value is None or raw_value.strip() == "":
        return default_value
    return float(raw_value)


def _optional_int_env(environment_key: str, *, default_value: int) -> int:
    raw_value = os.getenv(environment_key)
    if raw_value is None or raw_value.strip() == "":
        return default_value
    return int(raw_value)
