"""Recall feature database repository."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete, desc, func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.db.models.recall import RecallMessage, RecallSession
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RecallRepository(BaseRepository[RecallSession]):
    """Repository handling database operations for Recall Session and Message entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RecallSession)

    async def get_session_by_id(
        self, session_id: UUID, user_id: UUID
    ) -> RecallSession | None:
        """Fetch active session by session_id and check user ownership."""
        stmt = select(RecallSession).where(
            RecallSession.id == session_id,
            RecallSession.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_session_by_user_id(self, user_id: UUID) -> RecallSession | None:
        """Fetch session by user_id."""
        stmt = select(RecallSession).where(RecallSession.user_id == user_id)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_or_create_session(self, user_id: UUID) -> RecallSession:
        """Retrieve the existing session or insert a new one atomically."""
        # 1. Look for existing session
        stmt = select(RecallSession).where(RecallSession.user_id == user_id)
        res = await self._session.execute(stmt)
        session = res.scalar_one_or_none()
        if session:
            return session

        # 2. Insert with on conflict do update to handle any concurrent insert races
        insert_stmt = (
            insert(RecallSession)
            .values(user_id=user_id)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"updated_at": func.now()},
            )
            .returning(RecallSession)
        )
        res = await self._session.execute(
            select(RecallSession).from_statement(insert_stmt)
        )
        await self._session.flush()
        return res.scalar_one()

    async def get_session_history(
        self,
        session_id: UUID,
        before: datetime | None = None,
        date_filter: date | None = None,
        limit: int = 50,
    ) -> list[RecallMessage]:
        """Fetch message history for the session paginated or filtered by date.

        Returns messages in chronological order (created_at ASC, id ASC).
        """
        stmt = select(RecallMessage).where(RecallMessage.session_id == session_id)

        if date_filter:
            stmt = stmt.where(
                text("(created_at AT TIME ZONE 'UTC')::date = :date_filter").bindparams(
                    date_filter=date_filter
                )
            )

        if before:
            stmt = stmt.where(RecallMessage.created_at < before)

        # Retrieve the most recent messages first, then reverse in memory to return chronological
        stmt = stmt.order_by(
            desc(RecallMessage.created_at),
            desc(RecallMessage.id),
        ).limit(limit)

        res = await self._session.execute(stmt)
        messages = list(res.scalars().all())
        messages.reverse()
        return messages

    async def save_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        retrieved_entries: list[dict] | None = None,
    ) -> RecallMessage:
        """Save a new message turn (user/assistant) to the database."""

        message = RecallMessage(
            session_id=session_id,
            role=role,
            content=content,
            retrieved_entries=retrieved_entries,
            created_at=datetime.now(UTC),
        )
        self._session.add(message)
        await self._session.flush()
        await self._session.refresh(message)
        return message

    async def delete_paired_messages(self, message_id: UUID, user_id: UUID) -> bool:
        """Hard delete a single message with ownership check.

        If it's a user message, also deletes the immediately following assistant message.
        """
        # 1. Fetch message and verify ownership via session join
        stmt = (
            select(RecallMessage)
            .join(RecallSession, RecallMessage.session_id == RecallSession.id)
            .where(
                RecallMessage.id == message_id,
                RecallSession.user_id == user_id,
            )
        )
        res = await self._session.execute(stmt)
        msg = res.scalar_one_or_none()
        if not msg:
            return False

        # 2. If user message, find and delete the next assistant message
        if msg.role == "user":
            next_stmt = (
                select(RecallMessage)
                .where(
                    RecallMessage.session_id == msg.session_id,
                    RecallMessage.created_at >= msg.created_at,
                    RecallMessage.id != msg.id,
                )
                .order_by(
                    RecallMessage.created_at.asc(),
                    RecallMessage.id.asc(),
                )
                .limit(1)
            )
            next_res = await self._session.execute(next_stmt)
            next_msg = next_res.scalar_one_or_none()
            if next_msg and next_msg.role == "assistant":
                await self._session.delete(next_msg)

        # 3. Delete original message
        await self._session.delete(msg)
        await self._session.flush()
        return True

    async def delete_messages_by_date(self, session_id: UUID, target_date: date) -> int:
        """Delete all messages for a given calendar day in a session."""
        stmt = delete(RecallMessage).where(
            RecallMessage.session_id == session_id,
            text("(created_at AT TIME ZONE 'UTC')::date = :target_date").bindparams(
                target_date=target_date
            ),
        )
        res = await self._session.execute(stmt)
        await self._session.flush()
        return res.rowcount

    async def count_user_messages_since(
        self, session_id: UUID, start_time: datetime
    ) -> int:
        """Count user messages sent in the session since a given time."""
        stmt = select(func.count(RecallMessage.id)).where(
            RecallMessage.session_id == session_id,
            RecallMessage.role == "user",
            RecallMessage.created_at > start_time,
        )
        res = await self._session.execute(stmt)
        return res.scalar() or 0
