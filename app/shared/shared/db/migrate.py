import os

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection

from shared.db.engine import get_engine


def _get_alembic_config(connection: Connection) -> Config:
    """Build Alembic config and inject the caller's connection.

    By passing the connection via config.attributes, env.py reuses it
    instead of creating its own engine — avoids asyncio.run() conflicts
    when called from an already-running event loop (FastAPI lifespan).
    """
    migrations_dir = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "migrations",
    )
    migrations_dir = os.path.normpath(migrations_dir)

    alembic_config = Config(os.path.join(migrations_dir, "alembic.ini"))
    alembic_config.set_main_option("script_location", migrations_dir)
    alembic_config.attributes["connection"] = connection

    return alembic_config


def _do_upgrade(connection: Connection) -> None:
    """Sync callback executed inside an async connection via run_sync()."""
    alembic_config = _get_alembic_config(connection)
    command.upgrade(alembic_config, "head")


async def run_migrations() -> None:
    """Run Alembic migrations to head. Idempotent — skips if already current.

    Uses the app's async engine singleton and bridges into sync Alembic
    via connection.run_sync(). Safe to call from FastAPI's async lifespan.
    """
    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(_do_upgrade)
