from sqlalchemy.ext.asyncio import AsyncSession

from handlers.shared.fetcher_core.repository import FetcherRepository
from handlers.shared.fetcher_core.service import FetcherCoreService
from handlers.shared.fetcher_storage.raw_html_s3_storage import RawHtmlS3Storage
from shared.queue.sns_client import SNSClient


def build_fetcher_core(
    *,
    database_session: AsyncSession,
    aws_region: str,
    raw_html_bucket_name: str,
    discoverable_topic_arn: str,
    service_name: str,
) -> FetcherCoreService:
    repository = FetcherRepository(database_session=database_session)
    html_storage = RawHtmlS3Storage(
        bucket_name=raw_html_bucket_name,
        region_name=aws_region,
    )
    discoverable_publisher = SNSClient(
        region_name=aws_region,
        service_name=service_name,
    )

    return FetcherCoreService(
        repository=repository,
        html_storage=html_storage,
        discoverable_publisher=discoverable_publisher,
        discoverable_topic_arn=discoverable_topic_arn,
        service_name=service_name,
    )
