"""Alembic migration environment — async SQLAlchemy 2.x.

This file is invoked by ``alembic upgrade/downgrade/revision``.

It:
1. Reads ``DATABASE_URL`` from the environment.
2. Imports all ORM models via ``app.db.models`` so autogenerate works.
3. Runs migrations synchronously inside the async engine using ``run_sync``.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Load the Alembic logging config from alembic.ini.
if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

# Import all ORM models so Base.metadata is fully populated for autogenerate.
from app.db.models import Base

target_metadata = Base.metadata

# Load database URL from unified Settings
from app.core.config import get_settings  # noqa: E402

DATABASE_URL = str(get_settings().DATABASE_URL)

if not DATABASE_URL:
    msg = "DATABASE_URL is not configured in Settings."
    raise RuntimeError(msg)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection required)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside run_sync."""
    connectable = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,  # Migrations never reuse connections.
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
