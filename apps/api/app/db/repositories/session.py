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

    async def delete(self, obj: Session) -> None:
        """Soft-delete a Session by setting its revoked_at field.

        Args:
            obj: The Session instance to revoke.
        """
        obj.revoked_at = datetime.now(UTC)
        await self._session.flush()

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        """Fetch an active session by token hash, preloading its device and user.

        Active sessions are those that are not expired and not revoked.

        Args:
            token_hash: SHA-256 hash of the session token.

        Returns:
            The active Session instance with preloaded relationships, or None.
        """
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(Session)
            .options(joinedload(Session.device).joinedload(Device.user))
            .where(
                Session.token_hash == token_hash,
                Session.expires_at > now,
                Session.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_active_by_user(self, user_id: UUID) -> list[Session]:
        """Fetch all active (unexpired, unrevoked) sessions for a specific user.

        Args:
            user_id: The UUID of the user.

        Returns:
            A list of active Session instances.
        """
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(Session)
            .join(Device)
            .options(joinedload(Session.device))
            .where(
                Device.user_id == user_id,
                Session.expires_at > now,
                Session.revoked_at.is_(None),
            )
            .order_by(Session.last_used_at.desc())
        )
        return list(result.scalars().all())

    async def delete_by_id_for_user(self, user_id: UUID, session_id: UUID) -> bool:
        """Soft-delete (revoke) a specific session belonging to a user.

        Args:
            user_id: The UUID of the user.
            session_id: The UUID of the session to revoke.

        Returns:
            True if a session was revoked, False otherwise.
        """
        session_to_delete = await self._session.execute(
            select(Session)
            .join(Device)
            .where(
                Session.id == session_id,
                Device.user_id == user_id,
                Session.revoked_at.is_(None),
            )
        )
        obj = session_to_delete.scalar_one_or_none()
        if obj:
            obj.revoked_at = datetime.now(UTC)
            await self._session.flush()
            return True
        return False

    async def delete_other_sessions(
        self, user_id: UUID, current_session_id: UUID
    ) -> None:
        """Soft-delete (revoke) all active sessions for a user except the current one.

        Args:
            user_id: The UUID of the user.
            current_session_id: The UUID of the session to preserve.
        """
        result = await self._session.execute(
            select(Session)
            .join(Device)
            .where(
                Device.user_id == user_id,
                Session.id != current_session_id,
                Session.revoked_at.is_(None),
            )
        )
        objs = result.scalars().all()
        now = datetime.now(UTC)
        for obj in objs:
            obj.revoked_at = now
        await self._session.flush()

    async def delete_all_sessions(self, user_id: UUID) -> None:
        """Soft-delete (revoke) all active sessions for a user.

        Args:
            user_id: The UUID of the user.
        """
        result = await self._session.execute(
            select(Session)
            .join(Device)
            .where(
                Device.user_id == user_id,
                Session.revoked_at.is_(None),
            )
        )
        objs = result.scalars().all()
        now = datetime.now(UTC)
        for obj in objs:
            obj.revoked_at = now
        await self._session.flush()
