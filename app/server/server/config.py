from dataclasses import dataclass
from functools import lru_cache

from shared.config.env import required_env_value


@dataclass(frozen=True)
class ServerSettings:
    aws_region: str
    discoverable_topic_arn: str


@lru_cache(maxsize=1)
def get_server_settings() -> ServerSettings:
    return ServerSettings(
        aws_region=required_env_value("AWS_REGION"),
        discoverable_topic_arn=required_env_value("DISCOVERABLE_TOPIC_ARN"),
    )
