from dataclasses import dataclass

from shared.config.env import required_env_value


@dataclass(frozen=True)
class HttpFetcherRuntimeConfig:
    aws_region: str
    raw_html_bucket_name: str
    discoverable_topic_arn: str


def load_runtime_config() -> HttpFetcherRuntimeConfig:
    return HttpFetcherRuntimeConfig(
        aws_region=required_env_value("AWS_REGION"),
        raw_html_bucket_name=required_env_value("RAW_HTML_BUCKET_NAME"),
        discoverable_topic_arn=required_env_value("DISCOVERABLE_TOPIC_ARN"),
    )
