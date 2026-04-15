from dataclasses import dataclass

from shared.config.env import required_env_value


@dataclass(frozen=True)
class SiteRefresherRuntimeConfig:
    aws_region: str
    site_refresher_topic_arn: str


def load_runtime_config() -> SiteRefresherRuntimeConfig:
    required_env_value("DATABASE_URL")
    return SiteRefresherRuntimeConfig(
        aws_region=required_env_value("AWS_REGION"),
        site_refresher_topic_arn=required_env_value("SITE_REFRESHER_TOPIC_ARN"),
    )
