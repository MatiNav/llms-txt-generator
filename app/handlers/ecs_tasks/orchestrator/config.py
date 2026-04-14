from dataclasses import dataclass

from shared.config.env import required_env_value


SERVICE_NAME = "orchestrator"
DISCOVERING_STATE = "discovering"


@dataclass(frozen=True)
class OrchestratorRuntimeConfig:
    aws_region: str
    discoverable_queue_url: str
    fetch_topic_arn: str
    processing_topic_arn: str


def load_runtime_config() -> OrchestratorRuntimeConfig:
    return OrchestratorRuntimeConfig(
        aws_region=required_env_value("AWS_REGION"),
        discoverable_queue_url=required_env_value("DISCOVERABLE_QUEUE_URL"),
        fetch_topic_arn=required_env_value("FETCH_TOPIC_ARN"),
        processing_topic_arn=required_env_value("PROCESSING_TOPIC_ARN"),
    )
