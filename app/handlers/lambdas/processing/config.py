from dataclasses import dataclass

from shared.config.env import required_env_value


@dataclass(frozen=True)
class ProcessingRuntimeConfig:
    aws_region: str
    raw_html_bucket_name: str
    generated_output_bucket_name: str
    llm_generation_topic_arn: str


def load_runtime_config() -> ProcessingRuntimeConfig:
    required_env_value("DATABASE_URL")
    return ProcessingRuntimeConfig(
        aws_region=required_env_value("AWS_REGION"),
        raw_html_bucket_name=required_env_value("RAW_HTML_BUCKET_NAME"),
        generated_output_bucket_name=required_env_value("GENERATED_OUTPUT_BUCKET_NAME"),
        llm_generation_topic_arn=required_env_value("LLM_GENERATION_TOPIC_ARN"),
    )
