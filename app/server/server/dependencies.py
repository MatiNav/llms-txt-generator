from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import get_server_settings
from server.repositories.run_repository import RunRepository
from server.services.download_service import DownloadService
from server.services.generation_service import GenerationService
from server.services.run_events_service import RunEventsService
from server.services.run_service import RunService
from shared.db.session import get_db_session
from shared.queue.sns_client import SNSClient


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_db_session() as database_session:
        yield database_session


def get_sns_client() -> SNSClient:
    settings = get_server_settings()
    return SNSClient(
        region_name=settings.aws_region,
    )


def get_generation_service(
    database_session: AsyncSession = Depends(get_database_session),
    sns_client: SNSClient = Depends(get_sns_client),
) -> GenerationService:
    settings = get_server_settings()
    return GenerationService(
        database_session=database_session,
        sns_client=sns_client,
        discoverable_topic_arn=settings.discoverable_topic_arn,
    )


def get_run_service(
    database_session: AsyncSession = Depends(get_database_session),
) -> RunService:
    run_repository = RunRepository(database_session=database_session)
    return RunService(run_repository=run_repository)


def get_download_service(
    run_service: RunService = Depends(get_run_service),
) -> DownloadService:
    settings = get_server_settings()
    return DownloadService(
        run_service=run_service,
        aws_region=settings.aws_region,
        generated_output_bucket_name=settings.generated_output_bucket_name,
        download_url_ttl_seconds=settings.download_url_ttl_seconds,
    )


def get_run_events_service() -> RunEventsService:
    return RunEventsService()
