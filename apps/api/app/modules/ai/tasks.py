"""AI summary background tasks."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SummaryScope
from app.db.models.user import UserSettings
from app.modules.ai.service import AISummaryService

logger = logging.getLogger(__name__)


async def generate_entry_summary_task(ctx: dict[str, Any], entry_id: str) -> None:
    """Worker task to generate a summary for a single journal entry."""
    db: AsyncSession = ctx["db"]
    logger.info("Starting entry summary task for entry %s", entry_id)

    from app.db.repositories.journal import JournalRepository

    journal_repo = JournalRepository(db)
    entry = await journal_repo.get_entry_for_ai(UUID(entry_id))
    if not entry:
        logger.warning("Entry %s not found for AI summary generation.", entry_id)
        return

    user_id = UUID(str(entry.day.user_id))
    try:
        await AISummaryService.generate_summary(
            db,
            user_id=user_id,
            scope=SummaryScope.ENTRY,
            journal_entry_id=UUID(entry_id),
        )
        await db.commit()
    except Exception as exc:
        logger.exception(
            "Failed to generate entry summary for entry %s: %s", entry_id, exc
        )
        await db.rollback()
        raise exc


async def generate_day_summary_task(ctx: dict[str, Any], day_id: str) -> None:
    """Worker task to generate a daily summary."""
    db: AsyncSession = ctx["db"]
    logger.info("Starting day summary task for day %s", day_id)

    from app.db.repositories.journal import DayRepository

    day_repo = DayRepository(db)
    day = await day_repo.get_by_id(UUID(day_id))
    if not day:
        logger.warning("Day %s not found for daily summary generation.", day_id)
        return

    user_id = UUID(str(day.user_id))
    try:
        await AISummaryService.generate_summary(
            db,
            user_id=user_id,
            scope=SummaryScope.DAY,
            day_id=UUID(day_id),
            period_start=day.date,
            period_end=day.date,
        )
        await db.commit()
    except Exception as exc:
        logger.exception("Failed to generate daily summary for day %s: %s", day_id, exc)
        await db.rollback()
        raise exc


async def generate_weekly_summaries_task(ctx: dict[str, Any]) -> None:
    """Scheduled task (cron) to generate weekly summaries for all users."""
    db: AsyncSession = ctx["db"]
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    logger.info(
        "Starting weekly summaries task for period %s - %s", last_monday, last_sunday
    )

    # Query all users with AI enabled
    stmt = select(UserSettings.user_id).where(UserSettings.ai_enabled.is_(True))
    res = await db.execute(stmt)
    user_ids = res.scalars().all()

    for u_id_val in user_ids:
        u_id = UUID(str(u_id_val))
        try:
            await AISummaryService.generate_summary(
                db,
                user_id=u_id,
                scope=SummaryScope.WEEK,
                period_start=last_monday,
                period_end=last_sunday,
            )
            await db.commit()
        except Exception as exc:
            logger.exception(
                "Failed to generate weekly summary for user %s: %s", u_id, exc
            )
            await db.rollback()


async def generate_monthly_summaries_task(ctx: dict[str, Any]) -> None:
    """Scheduled task (cron) to generate monthly summaries for all users."""
    db: AsyncSession = ctx["db"]
    today = date.today()
    first_of_this_month = today.replace(day=1)
    last_day_of_prev_month = first_of_this_month - timedelta(days=1)
    first_day_of_prev_month = last_day_of_prev_month.replace(day=1)
    logger.info(
        "Starting monthly summaries task for period %s - %s",
        first_day_of_prev_month,
        last_day_of_prev_month,
    )

    # Query all users with AI enabled
    stmt = select(UserSettings.user_id).where(UserSettings.ai_enabled.is_(True))
    res = await db.execute(stmt)
    user_ids = res.scalars().all()

    for u_id_val in user_ids:
        u_id = UUID(str(u_id_val))
        try:
            await AISummaryService.generate_summary(
                db,
                user_id=u_id,
                scope=SummaryScope.MONTH,
                period_start=first_day_of_prev_month,
                period_end=last_day_of_prev_month,
            )
            await db.commit()
        except Exception as exc:
            logger.exception(
                "Failed to generate monthly summary for user %s: %s", u_id, exc
            )
            await db.rollback()


async def generate_yearly_summaries_task(ctx: dict[str, Any]) -> None:
    """Scheduled task (cron) to generate yearly summaries for all users."""
    db: AsyncSession = ctx["db"]
    today = date.today()
    prev_year = today.year - 1
    period_start = date(prev_year, 1, 1)
    period_end = date(prev_year, 12, 31)
    logger.info(
        "Starting yearly summaries task for period %s - %s", period_start, period_end
    )

    # Query all users with AI enabled
    stmt = select(UserSettings.user_id).where(UserSettings.ai_enabled.is_(True))
    res = await db.execute(stmt)
    user_ids = res.scalars().all()

    for u_id_val in user_ids:
        u_id = UUID(str(u_id_val))
        try:
            await AISummaryService.generate_summary(
                db,
                user_id=u_id,
                scope=SummaryScope.YEAR,
                period_start=period_start,
                period_end=period_end,
            )
            await db.commit()
        except Exception as exc:
            logger.exception(
                "Failed to generate yearly summary for user %s: %s", u_id, exc
            )
            await db.rollback()
