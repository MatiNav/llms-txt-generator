from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import get_server_settings
from server.services.generation_service import GenerationService
from shared.db.session import get_db_session
from shared.queue.sqs_client import SQSClient


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_db_session() as database_session:
        yield database_session


def get_sqs_client() -> SQSClient:
    settings = get_server_settings()
    return SQSClient(
        region_name=settings.aws_region,
        queue_url=settings.discoverable_queue_url,
    )


def get_generation_service(
    database_session: AsyncSession = Depends(get_database_session),
    sqs_client: SQSClient = Depends(get_sqs_client),
) -> GenerationService:
    return GenerationService(database_session=database_session, sqs_client=sqs_client)
