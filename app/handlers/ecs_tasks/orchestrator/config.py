import os
from dataclasses import dataclass


SERVICE_NAME = "orchestrator"
DISCOVERING_STATE = "discovering"


@dataclass(frozen=True)
class OrchestratorRuntimeConfig:
    aws_region: str
    discoverable_queue_url: str
    fetch_topic_arn: str


def required_env_value(environment_key: str) -> str:
    environment_value = os.getenv(environment_key)
    if not environment_value:
        raise RuntimeError(f"Missing required environment variable: {environment_key}")
    return environment_value


def load_runtime_config() -> OrchestratorRuntimeConfig:
    return OrchestratorRuntimeConfig(
        aws_region=required_env_value("AWS_REGION"),
        discoverable_queue_url=required_env_value("DISCOVERABLE_QUEUE_URL"),
        fetch_topic_arn=required_env_value("FETCH_TOPIC_ARN"),
    )
