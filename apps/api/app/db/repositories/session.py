"""Session repository implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import Device, Session
from app.db.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    """Repository handling persistence operations for the Session model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Session)

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        """Fetch a session by token hash, preloading its device and user.

        Args:
            token_hash: SHA-256 hash of the session token.

        Returns:
            The Session instance with preloaded relationships, or None.
        """
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(Session)
            .options(joinedload(Session.device).joinedload(Device.user))
            .where(
                Session.token_hash == token_hash,
                Session.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def list_active_by_user(self, user_id: UUID) -> list[Session]:
        """Fetch all active (unexpired) sessions for a specific user.

        Args:
            user_id: The UUID of the user.

        Returns:
            A list of Session instances.
        """
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(Session)
            .join(Device)
            .options(joinedload(Session.device))
            .where(
                Device.user_id == user_id,
                Session.expires_at > now,
            )
            .order_by(Session.last_used_at.desc())
        )
        return list(result.scalars().all())

    async def delete_by_id_for_user(self, user_id: UUID, session_id: UUID) -> bool:
        """Delete a specific session belonging to a user.

        Args:
            user_id: The UUID of the user.
            session_id: The UUID of the session to delete.

        Returns:
            True if a session was deleted, False otherwise.
        """
        # Resolve target session first to verify it belongs to user
        session_to_delete = await self._session.execute(
            select(Session)
            .join(Device)
            .where(
                Session.id == session_id,
                Device.user_id == user_id,
            )
        )
        obj = session_to_delete.scalar_one_or_none()
        if obj:
            await self._session.delete(obj)
            await self._session.flush()
            return True
        return False

    async def delete_other_sessions(
        self, user_id: UUID, current_session_id: UUID
    ) -> None:
        """Delete all active sessions for a user except the current one.

        Args:
            user_id: The UUID of the user.
            current_session_id: The UUID of the session to preserve.
        """
        # Fetch active sessions to delete
        result = await self._session.execute(
            select(Session)
            .join(Device)
            .where(
                Device.user_id == user_id,
                Session.id != current_session_id,
            )
        )
        objs = result.scalars().all()
        for obj in objs:
            await self._session.delete(obj)
        await self._session.flush()

    async def delete_all_sessions(self, user_id: UUID) -> None:
        """Delete all active sessions for a user.

        Args:
            user_id: The UUID of the user.
        """
        result = await self._session.execute(
            select(Session).join(Device).where(Device.user_id == user_id)
        )
        objs = result.scalars().all()
        for obj in objs:
            await self._session.delete(obj)
        await self._session.flush()
