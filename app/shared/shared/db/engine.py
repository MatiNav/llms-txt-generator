import os
from functools import lru_cache

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

ASYNC_DRIVER = "postgresql+asyncpg"


def _normalize_async_url(raw_url: str) -> str:
    """Ensure DATABASE_URL uses the asyncpg dialect.

    Accepts postgresql://, postgres://, or postgresql+asyncpg://
    and normalizes to postgresql+asyncpg:// so callers don't need
    to know which driver we use internally.
    """
    for prefix in ("postgres://", "postgresql://"):
        if raw_url.startswith(prefix):
            return raw_url.replace(prefix, f"{ASYNC_DRIVER}://", 1)
    return raw_url


@lru_cache(maxsize=1)
def get_database_url() -> str:
    """Build async PostgreSQL URL from environment variables.

    Supports two modes:
    - DATABASE_URL env var (local dev — auto-normalized to asyncpg dialect)
    - Individual DB_* env vars (deployed environments)
    """
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return _normalize_async_url(database_url)

    # URL.create handles special characters in credentials safely
    return URL.create(
        drivername=ASYNC_DRIVER,
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "llmstxt"),
    ).render_as_string(hide_password=False)


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Create and cache the async engine singleton.

    pool_pre_ping keeps connections healthy in long-lived servers (App Runner).
    """
    return create_async_engine(
        get_database_url(),
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
