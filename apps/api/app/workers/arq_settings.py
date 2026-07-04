"""ARQ worker configuration.

Start workers with::

    uv run arq app.workers.arq_settings.MediaWorkerSettings

For multiple concurrent workers, launch multiple processes::

    uv run arq app.workers.arq_settings.MediaWorkerSettings &
    uv run arq app.workers.arq_settings.MediaWorkerSettings &

Each process runs up to ``max_jobs`` coroutines simultaneously.
"""

from __future__ import annotations

from typing import ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.modules.ai.tasks import (
    generate_day_summary_task,
    generate_entry_summary_task,
    generate_monthly_summaries_task,
    generate_weekly_summaries_task,
    generate_yearly_summaries_task,
)
from app.modules.reflect.tasks import evaluate_reflect_entry
from app.storage.factory import get_storage
from app.workers.embedding import process_journal_entry_embeddings
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


class MediaWorkerSettings:
    """ARQ worker configuration for Media and general background jobs.

    Start worker with:
        uv run arq app.workers.arq_settings.MediaWorkerSettings
    """

    functions: ClassVar = [process_media]
    queue_name = "media_processing_queue"
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

    max_jobs = 10
    redis_settings = RedisSettings.from_dsn(str(get_settings().REDIS_URL))


class EmbeddingWorkerSettings:
    """ARQ worker configuration for Embedding generation background jobs.

    Start worker with:
        uv run arq app.workers.arq_settings.EmbeddingWorkerSettings
    """

    functions: ClassVar = [process_journal_entry_embeddings]
    queue_name = "embedding_queue"

    on_startup = startup
    on_shutdown = shutdown
    on_job_start = job_start
    on_job_end = job_end

    max_jobs = 10
    redis_settings = RedisSettings.from_dsn(str(get_settings().REDIS_URL))


class AIWorkerSettings:
    """ARQ worker configuration for AI Summaries and scheduling.

    Start worker with:
        uv run arq app.workers.arq_settings.AIWorkerSettings
    """

    functions: ClassVar = [
        generate_entry_summary_task,
        generate_day_summary_task,
        generate_weekly_summaries_task,
        generate_monthly_summaries_task,
        generate_yearly_summaries_task,
        evaluate_reflect_entry,
    ]
    queue_name = "ai_queue"

    cron_jobs: ClassVar = [
        cron(
            generate_weekly_summaries_task,
            weekday=0,
            hour=0,
            minute=0,
        ),
        cron(
            generate_monthly_summaries_task,
            day=1,
            hour=0,
            minute=0,
        ),
        cron(
            generate_yearly_summaries_task,
            month=1,
            day=1,
            hour=0,
            minute=0,
        ),
    ]

    on_startup = startup
    on_shutdown = shutdown
    on_job_start = job_start
    on_job_end = job_end

    max_jobs = 10
    redis_settings = RedisSettings.from_dsn(str(get_settings().REDIS_URL))
