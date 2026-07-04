"""Summary database repository."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from app.db.enums import SummaryKind, SummaryScope
from app.db.models.ai import Summary
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SummaryRepository(BaseRepository[Summary]):
    """Repository handling database operations for Summary model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Summary)

    async def get_latest(
        self,
        user_id: UUID,
        scope: SummaryScope,
        kind: SummaryKind,
        *,
        journal_entry_id: UUID | None = None,
        day_id: UUID | None = None,
        period_start: date | None = None,
    ) -> Summary | None:
        """Returns the most recently created summary matching the criteria.

        Always filters by user_id. Returns None if no match.
        """
        stmt = select(Summary).where(
            Summary.user_id == str(user_id),
            Summary.scope == scope,
            Summary.kind == kind,
        )

        if scope == SummaryScope.ENTRY:
            if not journal_entry_id:
                return None
            stmt = stmt.where(Summary.journal_entry_id == str(journal_entry_id))
        elif scope == SummaryScope.DAY:
            if not day_id:
                return None
            stmt = stmt.where(Summary.day_id == str(day_id))
        elif scope in (SummaryScope.WEEK, SummaryScope.MONTH, SummaryScope.YEAR):
            if not period_start:
                return None
            stmt = stmt.where(Summary.period_start == period_start)

        stmt = stmt.order_by(Summary.created_at.desc()).limit(1)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def save(
        self,
        user_id: UUID,
        scope: SummaryScope,
        kind: SummaryKind,
        content: str,
        highlights: list[str] | None,
        challenges: list[str] | None,
        themes: list[str] | None,
        mood_analysis: dict[str, Any] | None,
        provider: str,
        model: str,
        prompt_version: str,
        *,
        content_hash: str | None = None,
        journal_entry_id: UUID | None = None,
        day_id: UUID | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> Summary:
        """Inserts a new summary row. Never updates existing rows."""
        summary = Summary(
            user_id=str(user_id),
            scope=scope,
            kind=kind,
            content=content,
            highlights=highlights,
            challenges=challenges,
            themes=themes,
            mood_analysis=mood_analysis,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            content_hash=content_hash,
            journal_entry_id=str(journal_entry_id) if journal_entry_id else None,
            day_id=str(day_id) if day_id else None,
            period_start=period_start,
            period_end=period_end,
        )
        return await self.create(summary)
