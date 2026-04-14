import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class ServerSettings:
    aws_region: str
    discoverable_queue_url: str


def _required_env_value(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


@lru_cache(maxsize=1)
def get_server_settings() -> ServerSettings:
    return ServerSettings(
        aws_region=_required_env_value("AWS_REGION"),
        discoverable_queue_url=_required_env_value("DISCOVERABLE_QUEUE_URL"),
    )
