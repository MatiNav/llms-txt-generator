from dataclasses import dataclass

from handlers.lambdas.site_refresher.config import load_runtime_config
from handlers.lambdas.site_refresher.repository import SiteRefresherRepository
from handlers.lambdas.site_refresher.service import SiteRefresherService
from shared.db.session import get_session_factory
from shared.queue.sns_client import SNSClient


@dataclass(frozen=True)
class SiteRefresherRuntime:
    site_refresher_service: SiteRefresherService


def build_site_refresher_runtime() -> SiteRefresherRuntime:
    runtime_config = load_runtime_config()
    database_session = get_session_factory()()
    repository = SiteRefresherRepository(database_session=database_session)
    site_refresher_publisher = SNSClient(
        region_name=runtime_config.aws_region,
        service_name="site_refresher",
    )
    site_refresher_service = SiteRefresherService(
        repository=repository,
        site_refresher_publisher=site_refresher_publisher,
        site_refresher_topic_arn=runtime_config.site_refresher_topic_arn,
    )
    return SiteRefresherRuntime(site_refresher_service=site_refresher_service)
