import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from shared.db.engine import get_database_url
from shared.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    """Run Alembic migrations against an already-open connection.

    Extracted so both the async path (run_sync) and the programmatic
    connection-sharing path can reuse the same logic.
    """
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Generate SQL scripts without a live database connection."""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine, open a connection, and bridge into sync Alembic.

    async_engine_from_config understands the +asyncpg dialect natively.
    connection.run_sync() executes sync migration code inside the async
    connection — same DB socket, no second driver needed.
    """
    config_section = config.get_section(config.config_ini_section, {})
    config_section["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations.

    Two paths:
    1. Programmatic (migrate.py passes a connection via config.attributes)
       — reuses the caller's connection, avoids asyncio.run() loop conflicts.
    2. CLI (alembic upgrade head) — spins up its own async engine.
    """
    connectable = config.attributes.get("connection", None)

    if connectable is not None:
        do_run_migrations(connectable)
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
