from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.db.engine import get_engine


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create and cache the session factory singleton.

    expire_on_commit=False prevents lazy-load traps after commit —
    model attributes stay readable without triggering implicit async I/O.
    """
    return async_sessionmaker(bind=get_engine(), expire_on_commit=False)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Scoped async session with auto-commit on success, rollback on error.

    Each request/job/task should get its own session — never share
    one AsyncSession across concurrent asyncio tasks.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
