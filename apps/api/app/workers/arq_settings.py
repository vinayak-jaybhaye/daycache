"""ARQ worker configuration.

Start workers with::

    uv run arq app.workers.arq_settings.WorkerSettings

For multiple concurrent workers, launch multiple processes::

    uv run arq app.workers.arq_settings.WorkerSettings &
    uv run arq app.workers.arq_settings.WorkerSettings &

Each process runs up to ``max_jobs`` coroutines simultaneously.
"""

from __future__ import annotations

from typing import ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.storage.factory import get_storage
from app.workers.media import clean_stale_media, process_media


async def startup(ctx: dict) -> None:  # type: ignore[type-arg]
    """Initialise shared resources injected into each job's ``ctx``."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.engine import create_engine

    engine = create_engine()
    ctx["session_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    ctx["storage"] = get_storage()


async def shutdown(ctx: dict) -> None:  # type: ignore[type-arg]
    """Clean up shared resources on worker shutdown."""
    from app.db.engine import get_engine

    await get_engine().dispose()


async def job_start(ctx: dict) -> None:  # type: ignore[type-arg]
    """Create a new AsyncSession for each job."""
    session_factory = ctx["session_factory"]
    ctx["db"] = session_factory()


async def job_end(ctx: dict) -> None:  # type: ignore[type-arg]
    """Dispose of the AsyncSession after the job completes."""
    db = ctx.get("db")
    if db:
        await db.close()


class WorkerSettings:
    """ARQ worker configuration.

    See https://arq-docs.helpmanual.io/ for all available options.
    """

    functions: ClassVar = [process_media]
    cron_jobs: ClassVar = [
        cron(
            clean_stale_media,
            # Run every 10 minutes.
            minute={0, 10, 20, 30, 40, 50},
        ),
    ]

    on_startup = startup
    on_shutdown = shutdown
    on_job_start = job_start
    on_job_end = job_end

    # Maximum number of concurrent jobs per worker process.
    # Scale horizontally by running more worker processes.
    max_jobs = 10

    redis_settings = RedisSettings.from_dsn(str(get_settings().REDIS_URL))
