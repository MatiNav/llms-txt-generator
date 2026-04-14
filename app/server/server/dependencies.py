from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import get_server_settings
from server.services.generation_service import GenerationService
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
