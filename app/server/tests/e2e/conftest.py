import os
import types

import pytest
from sqlalchemy import text

from server.dependencies import get_sns_client
from server.main import app
from shared.db.engine import get_engine
from shared.db.session import get_session_factory


@pytest.fixture(autouse=True)
def default_database_url() -> None:
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://llmstxt:llmstxt@localhost:5432/llmstxt",
    )


@pytest.fixture
async def clean_database() -> None:
    engine = get_engine()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE TABLE run_pages, site_pages, runs, sites RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture(autouse=True)
async def reset_cached_db_state() -> None:
    yield

    if get_session_factory.cache_info().currsize > 0:
        get_session_factory.cache_clear()

    if get_engine.cache_info().currsize > 0:
        engine = get_engine()
        await engine.dispose()
        get_engine.cache_clear()


@pytest.fixture
def mock_sqs_dependency() -> None:
    async def fake_publish_message(
        topic_arn, payload, request_id=None, message_attributes=None
    ):
        return "mock-message-id"

    app.dependency_overrides[get_sns_client] = lambda: types.SimpleNamespace(
        publish_message=fake_publish_message
    )
    yield
    app.dependency_overrides.pop(get_sns_client, None)
