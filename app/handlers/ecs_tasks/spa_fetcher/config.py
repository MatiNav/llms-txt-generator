from dataclasses import dataclass

from shared.config.env import required_env_value


@dataclass(frozen=True)
class SpaFetcherRuntimeConfig:
    aws_region: str
    spa_fetch_queue_url: str
    raw_html_bucket_name: str
    discoverable_topic_arn: str


def load_runtime_config() -> SpaFetcherRuntimeConfig:
    return SpaFetcherRuntimeConfig(
        aws_region=required_env_value("AWS_REGION"),
        spa_fetch_queue_url=required_env_value("SPA_FETCH_QUEUE_URL"),
        raw_html_bucket_name=required_env_value("RAW_HTML_BUCKET_NAME"),
        discoverable_topic_arn=required_env_value("DISCOVERABLE_TOPIC_ARN"),
    )
