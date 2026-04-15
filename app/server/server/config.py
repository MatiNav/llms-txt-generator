import os
from dataclasses import dataclass
from functools import lru_cache

from shared.config.env import required_env_value


@dataclass(frozen=True)
class ServerSettings:
    aws_region: str
    discoverable_topic_arn: str
    frontend_origin: str
    generated_output_bucket_name: str
    download_url_ttl_seconds: int


@lru_cache(maxsize=1)
def get_server_settings() -> ServerSettings:
    return ServerSettings(
        aws_region=required_env_value("AWS_REGION"),
        discoverable_topic_arn=required_env_value("DISCOVERABLE_TOPIC_ARN"),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        generated_output_bucket_name=os.getenv("GENERATED_OUTPUT_BUCKET_NAME", ""),
        download_url_ttl_seconds=int(os.getenv("DOWNLOAD_URL_TTL_SECONDS", "900")),
    )
