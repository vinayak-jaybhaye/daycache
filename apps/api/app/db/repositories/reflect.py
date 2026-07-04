"""Reflect feature database repository."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert

from app.db.models.reflect import ReflectEntry, ReflectMessage, ReflectSession
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ReflectRepository(BaseRepository[ReflectSession]):
    """Repository handling database operations for Reflect Session, Message and Entry entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ReflectSession)

    async def get_session_by_id(
        self, session_id: UUID, user_id: UUID
    ) -> ReflectSession | None:
        """Fetch active session by session_id and check user ownership."""
        stmt = select(ReflectSession).where(
            ReflectSession.id == session_id,
            ReflectSession.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_session_by_user_id(self, user_id: UUID) -> ReflectSession | None:
        """Fetch session by user_id."""
        stmt = select(ReflectSession).where(ReflectSession.user_id == user_id)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_or_create_session(self, user_id: UUID) -> ReflectSession:
        """Retrieve the existing session or insert a new one atomically."""
        # 1. Look for existing session
        stmt = select(ReflectSession).where(ReflectSession.user_id == user_id)
        res = await self._session.execute(stmt)
        session = res.scalar_one_or_none()
        if session:
            return session

        # 2. Insert with on conflict do update to handle any concurrent insert races
        insert_stmt = (
            insert(ReflectSession)
            .values(user_id=user_id)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"updated_at": func.now()},
            )
            .returning(ReflectSession)
        )
        res = await self._session.execute(
            select(ReflectSession).from_statement(insert_stmt)
        )
        await self._session.flush()
        return res.scalar_one()

    async def get_session_history(
        self,
        session_id: UUID,
        before: datetime | None = None,
        date_filter: date | None = None,
        limit: int = 50,
    ) -> list[ReflectMessage]:
        """Fetch message history for the session paginated or filtered by date.

        Returns messages in chronological order (created_at ASC, id ASC).
        """
        stmt = select(ReflectMessage).where(ReflectMessage.session_id == session_id)

        if date_filter:
            stmt = stmt.where(ReflectMessage.date == date_filter)

        if before:
            stmt = stmt.where(ReflectMessage.created_at < before)

        # Retrieve the most recent messages first, then reverse in memory to return chronological
        stmt = stmt.order_by(
            desc(ReflectMessage.created_at),
            desc(ReflectMessage.id),
        ).limit(limit)

        res = await self._session.execute(stmt)
        messages = list(res.scalars().all())
        messages.reverse()
        return messages

    async def get_today_messages(
        self, session_id: UUID, target_date: date
    ) -> list[ReflectMessage]:
        """Fetch today's messages in chronological order."""
        stmt = (
            select(ReflectMessage)
            .where(
                ReflectMessage.session_id == session_id,
                ReflectMessage.date == target_date,
            )
            .order_by(
                ReflectMessage.created_at.asc(),
                ReflectMessage.id.asc(),
            )
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def get_recent_messages(
        self, session_id: UUID, target_date: date, limit: int = 10
    ) -> list[ReflectMessage]:
        """Fetch recent messages from previous days in chronological order."""
        stmt = (
            select(ReflectMessage)
            .where(
                ReflectMessage.session_id == session_id,
                ReflectMessage.date < target_date,
            )
            .order_by(
                desc(ReflectMessage.created_at),
                desc(ReflectMessage.id),
            )
            .limit(limit)
        )
        res = await self._session.execute(stmt)
        messages = list(res.scalars().all())
        messages.reverse()
        return messages

    async def save_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        created_at_val: datetime | None = None,
    ) -> ReflectMessage:
        """Save a new message turn (user/assistant) to the database."""
        created_at = created_at_val or datetime.now(UTC)
        message = ReflectMessage(
            session_id=session_id,
            role=role,
            content=content,
            created_at=created_at,
            date=created_at.date(),
        )
        self._session.add(message)
        await self._session.flush()
        await self._session.refresh(message)
        return message

    async def get_reflect_entry_by_date(
        self, session_id: UUID, target_date: date
    ) -> ReflectEntry | None:
        """Fetch system-managed reflect entry pointer for session and date."""
        stmt = select(ReflectEntry).where(
            ReflectEntry.session_id == session_id,
            ReflectEntry.date == target_date,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_reflect_entry(
        self,
        session_id: UUID,
        journal_entry_id: UUID,
        target_date: date,
        last_message_id: UUID | None,
    ) -> ReflectEntry:
        """Create a linking row mapping ReflectSession to a JournalEntry."""
        reflect_entry = ReflectEntry(
            session_id=session_id,
            journal_entry_id=journal_entry_id,
            date=target_date,
            last_message_id=last_message_id,
        )
        self._session.add(reflect_entry)
        await self._session.flush()
        await self._session.refresh(reflect_entry)
        return reflect_entry
