"""AI Summary service orchestrator."""

from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.enums import SummaryKind, SummaryScope
from app.db.models.ai import Summary
from app.db.models.journal import Day, JournalEntry
from app.db.repositories.journal import JournalRepository
from app.db.repositories.settings import SettingsRepository
from app.db.repositories.summary import SummaryRepository
from app.modules.ai.schemas import SummaryCreateInternal, SummaryOutput
from app.services.llm import get_llm_provider
from app.services.llm.prompts import (
    DAY_SUMMARY_PROMPT_VERSION,
    ENTRY_SUMMARY_PROMPT_VERSION,
    MONTH_SUMMARY_PROMPT_VERSION,
    WEEK_SUMMARY_PROMPT_VERSION,
    YEAR_SUMMARY_PROMPT_VERSION,
    build_day_summary_prompt,
    build_entry_summary_prompt,
    build_month_summary_prompt,
    build_week_summary_prompt,
    build_year_summary_prompt,
)

logger = logging.getLogger(__name__)


def truncate_to_ceiling(text: str, max_chars: int = 24000) -> tuple[str, bool]:
    """Truncate text at the last complete sentence boundary before the max_chars ceiling.

    Returns a tuple of (truncated_text, was_truncated).
    """
    if len(text) <= max_chars:
        return text, False

    candidate = text[:max_chars]
    last_period = max(
        candidate.rfind("."),
        candidate.rfind("!"),
        candidate.rfind("?"),
    )

    if last_period != -1:
        return candidate[: last_period + 1].strip(), True

    return candidate.strip(), True


def get_week_bounds(d: date) -> tuple[date, date]:
    """Force any date to ISO 8601 week boundaries (Monday to Sunday)."""
    period_start = d - timedelta(days=d.weekday())  # Monday
    period_end = period_start + timedelta(days=6)  # Sunday
    return period_start, period_end


class AISummaryService:
    """Service to orchestrate AI summary generation and DB storage."""

    @staticmethod
    async def has_entries_in_range(
        db: AsyncSession, user_id: UUID, start_date: date, end_date: date
    ) -> bool:
        """Check if user has any non-deleted journal entries within the given date range."""
        stmt = (
            select(JournalEntry.id)
            .join(Day, JournalEntry.day_id == Day.id)
            .where(
                Day.user_id == str(user_id),
                Day.date >= start_date,
                Day.date <= end_date,
                JournalEntry.deleted_at.is_(None),
            )
            .limit(1)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none() is not None

    @staticmethod
    async def generate_summary(
        db: AsyncSession,
        user_id: UUID,
        scope: SummaryScope,
        kind: SummaryKind = SummaryKind.SUMMARY,
        *,
        journal_entry_id: UUID | None = None,
        day_id: UUID | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> Summary | None:
        """Fetch content, generate AI summary, and save it to the database."""
        # 1. Enforce validation of incoming arguments
        _ = SummaryCreateInternal(
            user_id=user_id,
            scope=scope,
            kind=kind,
            journal_entry_id=journal_entry_id,
            day_id=day_id,
            period_start=period_start,
            period_end=period_end,
        )

        # 2. Check if user has AI settings enabled
        settings_repo = SettingsRepository(db)
        user_settings = await settings_repo.get_by_user_id(user_id)
        if user_settings is None or not user_settings.ai_enabled:
            logger.info("AI is disabled for user %s. Skipping summary.", user_id)
            return None

        # 3. Gather text content based on scope (with dependency checking & caching)
        journal_repo = JournalRepository(db)
        prompt_content = ""
        prompt_version = "v1"
        prompt = ""
        content_hash = ""

        if scope == SummaryScope.ENTRY:
            entry = await journal_repo.get_entry_by_id(journal_entry_id, user_id)  # type: ignore[arg-type]
            if entry is None or not entry.content_text:
                logger.info(
                    "Journal entry %s empty or not found. Skipping.", journal_entry_id
                )
                return None

            entry_text = entry.content_text.strip()
            if not entry.content_hash:
                entry.content_hash = hashlib.sha256(
                    entry_text.encode("utf-8")
                ).hexdigest()
                await db.flush()

            summary_repo = SummaryRepository(db)
            existing = await summary_repo.get_latest(
                user_id=user_id,
                scope=SummaryScope.ENTRY,
                kind=SummaryKind.SUMMARY,
                journal_entry_id=journal_entry_id,
            )
            if existing and existing.content_hash == entry.content_hash:
                return existing

            prompt_content = entry_text
            prompt = build_entry_summary_prompt(prompt_content)
            prompt_version = ENTRY_SUMMARY_PROMPT_VERSION
            content_hash = entry.content_hash

        elif scope == SummaryScope.DAY:
            summary_repo = SummaryRepository(db)
            existing = await summary_repo.get_latest(
                user_id=user_id,
                scope=SummaryScope.DAY,
                kind=SummaryKind.SUMMARY,
                day_id=day_id,
            )

            # Get entries to compute hash
            stmt = (
                select(JournalEntry)
                .where(
                    JournalEntry.day_id == str(day_id),
                    JournalEntry.deleted_at.is_(None),
                )
                .order_by(JournalEntry.created_at.asc(), JournalEntry.id.asc())
            )
            res = await db.execute(stmt)
            entries = res.scalars().all()
            valid_entries = [e for e in entries if (e.content_text or "").strip()]
            if not valid_entries:
                logger.info("No content for day %s. Skipping.", day_id)
                return None

            # Ensure hashes are set
            hashes_modified = False
            for e in valid_entries:
                if not e.content_hash:
                    e_text = (e.content_text or "").strip()
                    e.content_hash = hashlib.sha256(e_text.encode("utf-8")).hexdigest()
                    hashes_modified = True
            if hashes_modified:
                await db.flush()

            combined_hashes_text = "".join(
                e.content_hash for e in valid_entries if e.content_hash
            )
            day_hash = hashlib.sha256(combined_hashes_text.encode("utf-8")).hexdigest()

            if existing and existing.content_hash == day_hash:
                return existing

            # Else generate...
            texts = [
                e.content_text.strip()
                for e in valid_entries
                if e.content_text is not None
            ]
            prompt_content = "\n---\n".join(texts)
            prompt = build_day_summary_prompt(texts, str(period_start or ""))
            prompt_version = DAY_SUMMARY_PROMPT_VERSION
            content_hash = day_hash

        elif scope == SummaryScope.WEEK:
            if not period_start:
                logger.error("WEEK scope requires period_start.")
                return None
            period_start, period_end = get_week_bounds(period_start)

            # Get days in this range that have non-deleted journal entries
            stmt = (
                select(Day)
                .join(JournalEntry, JournalEntry.day_id == Day.id)
                .where(
                    Day.user_id == str(user_id),
                    Day.date >= period_start,
                    Day.date <= period_end,
                    JournalEntry.deleted_at.is_(None),
                )
                .group_by(Day.id)
                .order_by(Day.date.asc())
            )
            res = await db.execute(stmt)
            days_with_entries = res.scalars().all()

            if not days_with_entries:
                logger.info(
                    "No entries found for week %s - %s. Skipping.",
                    period_start,
                    period_end,
                )
                return None

            # Ensure day summaries for each of these days exist and are fresh
            day_summaries: list[tuple[date, Summary]] = []
            for d_val in days_with_entries:
                day_summary = await AISummaryService.generate_summary(
                    db,
                    user_id=user_id,
                    scope=SummaryScope.DAY,
                    day_id=d_val.id,
                    period_start=d_val.date,
                    period_end=d_val.date,
                )
                if not day_summary:
                    summary_repo = SummaryRepository(db)
                    day_summary = await summary_repo.get_latest(
                        user_id=user_id,
                        scope=SummaryScope.DAY,
                        kind=SummaryKind.SUMMARY,
                        day_id=d_val.id,
                    )
                if day_summary:
                    day_summaries.append((d_val.date, day_summary))

            if not day_summaries:
                logger.info(
                    "No day summaries available for week %s - %s. Skipping.",
                    period_start,
                    period_end,
                )
                return None

            # Sort chronologically by date
            day_summaries.sort(key=lambda x: x[0])

            # Compute combined hash of day summaries
            combined_hashes = "".join(
                s.content_hash for _, s in day_summaries if s.content_hash
            )
            week_hash = hashlib.sha256(combined_hashes.encode("utf-8")).hexdigest()

            summary_repo = SummaryRepository(db)
            existing = await summary_repo.get_latest(
                user_id=user_id,
                scope=SummaryScope.WEEK,
                kind=SummaryKind.SUMMARY,
                period_start=period_start,
            )
            if existing and existing.content_hash == week_hash:
                return existing

            # Else generate...
            texts = [
                f"Daily Summary for {d_date}: {s.content}"
                for d_date, s in day_summaries
            ]
            prompt_content = "\n---\n".join(texts)
            period_str = f"{period_start} to {period_end}"
            prompt = build_week_summary_prompt(texts, period_str)
            prompt_version = WEEK_SUMMARY_PROMPT_VERSION
            content_hash = week_hash

        elif scope == SummaryScope.MONTH:
            if not period_start or not period_end:
                logger.error("MONTH scope requires period_start and period_end.")
                return None

            # Calculate Monday-to-Sunday week ranges that overlap with this month
            first_monday = period_start - timedelta(days=period_start.weekday())
            curr_monday = first_monday

            week_summaries: list[tuple[date, Summary]] = []
            while curr_monday <= period_end:
                curr_sunday = curr_monday + timedelta(days=6)

                if await AISummaryService.has_entries_in_range(
                    db, user_id, curr_monday, curr_sunday
                ):
                    week_summary = await AISummaryService.generate_summary(
                        db,
                        user_id=user_id,
                        scope=SummaryScope.WEEK,
                        period_start=curr_monday,
                        period_end=curr_sunday,
                    )
                    if week_summary:
                        week_summaries.append((curr_monday, week_summary))

                curr_monday += timedelta(days=7)

            if not week_summaries:
                logger.info(
                    "No week summaries available for month %s - %s. Skipping.",
                    period_start,
                    period_end,
                )
                return None

            # Sort chronologically by week start
            week_summaries.sort(key=lambda x: x[0])

            # Compute combined hash of week summaries
            combined_hashes = "".join(
                s.content_hash for _, s in week_summaries if s.content_hash
            )
            month_hash = hashlib.sha256(combined_hashes.encode("utf-8")).hexdigest()

            summary_repo = SummaryRepository(db)
            existing = await summary_repo.get_latest(
                user_id=user_id,
                scope=SummaryScope.MONTH,
                kind=SummaryKind.SUMMARY,
                period_start=period_start,
            )
            if existing and existing.content_hash == month_hash:
                return existing

            # Else generate...
            texts = [
                f"Weekly Summary for {w_start} to {w_start + timedelta(days=6)}: {s.content}"
                for w_start, s in week_summaries
            ]
            prompt_content = "\n---\n".join(texts)
            period_str = f"{period_start} to {period_end}"
            prompt = build_month_summary_prompt(texts, period_str)
            prompt_version = MONTH_SUMMARY_PROMPT_VERSION
            content_hash = month_hash

        elif scope == SummaryScope.YEAR:
            if not period_start or not period_end:
                logger.error("YEAR scope requires period_start and period_end.")
                return None

            month_summaries: list[tuple[date, Summary]] = []
            for m in range(1, 13):
                month_start = date(period_start.year, m, 1)
                import calendar

                _, last_day = calendar.monthrange(period_start.year, m)
                month_end = date(period_start.year, m, last_day)

                if await AISummaryService.has_entries_in_range(
                    db, user_id, month_start, month_end
                ):
                    month_summary = await AISummaryService.generate_summary(
                        db,
                        user_id=user_id,
                        scope=SummaryScope.MONTH,
                        period_start=month_start,
                        period_end=month_end,
                    )
                    if month_summary:
                        month_summaries.append((month_start, month_summary))

            if not month_summaries:
                logger.info(
                    "No month summaries available for year %s. Skipping.",
                    period_start.year,
                )
                return None

            # Sort chronologically by month start
            month_summaries.sort(key=lambda x: x[0])

            # Compute combined hash of month summaries
            combined_hashes = "".join(
                s.content_hash for _, s in month_summaries if s.content_hash
            )
            year_hash = hashlib.sha256(combined_hashes.encode("utf-8")).hexdigest()

            summary_repo = SummaryRepository(db)
            existing = await summary_repo.get_latest(
                user_id=user_id,
                scope=SummaryScope.YEAR,
                kind=SummaryKind.SUMMARY,
                period_start=period_start,
            )
            if existing and existing.content_hash == year_hash:
                return existing

            # Else generate...
            texts = [
                f"Monthly Summary for {m_start.strftime('%B %Y')}: {s.content}"
                for m_start, s in month_summaries
            ]
            prompt_content = "\n---\n".join(texts)
            period_str = f"{period_start} to {period_end}"
            prompt = build_year_summary_prompt(texts, period_str)
            prompt_version = YEAR_SUMMARY_PROMPT_VERSION
            content_hash = year_hash

        # 4. Token budget validation (24,000 characters ceiling)
        truncated_content, was_truncated = truncate_to_ceiling(prompt_content)
        if was_truncated:
            logger.info(
                "Content for summary exceeded ceiling and was truncated at sentence boundary."
            )
            # Rebuild prompt with truncated text and append a notice if it was truncated
            if scope == SummaryScope.ENTRY:
                prompt = (
                    build_entry_summary_prompt(truncated_content)
                    + "\n\nNote: content was truncated to fit the context window."
                )
            elif scope == SummaryScope.DAY:
                prompt = (
                    build_day_summary_prompt(
                        [truncated_content], str(period_start or "")
                    )
                    + "\n\nNote: content was truncated to fit the context window."
                )
            else:
                period_str = f"{period_start} to {period_end}"
                if scope == SummaryScope.WEEK:
                    prompt = (
                        build_week_summary_prompt([truncated_content], period_str)
                        + "\n\nNote: content was truncated to fit the context window."
                    )
                elif scope == SummaryScope.MONTH:
                    prompt = (
                        build_month_summary_prompt([truncated_content], period_str)
                        + "\n\nNote: content was truncated to fit the context window."
                    )
                else:
                    prompt = (
                        build_year_summary_prompt([truncated_content], period_str)
                        + "\n\nNote: content was truncated to fit the context window."
                    )

        # 5. Call active LLM provider via the common interface
        llm = get_llm_provider()
        settings = get_settings()
        output: SummaryOutput = await llm.generate(prompt, SummaryOutput)

        # 6. Ensure content_hash is populated
        if not content_hash:
            content_hash = hashlib.sha256(prompt_content.encode("utf-8")).hexdigest()

        # 7. Save the summary in the DB (append-only)
        summary_repo = SummaryRepository(db)
        summary = await summary_repo.save(
            user_id=user_id,
            scope=scope,
            kind=kind,
            content=output.content,
            highlights=output.highlights,
            challenges=output.challenges,
            themes=output.themes,
            mood_analysis=output.mood_analysis,
            provider=settings.AI_LLM_PROVIDER,
            model=settings.AI_LLM_MODEL,
            prompt_version=prompt_version,
            content_hash=content_hash,
            journal_entry_id=journal_entry_id if scope == SummaryScope.ENTRY else None,
            day_id=day_id if scope == SummaryScope.DAY else None,
            period_start=period_start
            if scope in (SummaryScope.WEEK, SummaryScope.MONTH, SummaryScope.YEAR)
            else None,
            period_end=period_end
            if scope in (SummaryScope.WEEK, SummaryScope.MONTH, SummaryScope.YEAR)
            else None,
        )

        return summary
