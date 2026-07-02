"""Users module business service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories import SessionRepository, UserRepository
from app.exceptions import NotFoundError

if TYPE_CHECKING:
    from app.modules.users.schemas import UpdateProfileRequest


class UserService:
    """Orchestrates user profile management and account lifecycle."""

    @staticmethod
    async def get_profile(db: AsyncSession, user_id: UUID) -> User:
        """Return the user's profile by ID.

        Args:
            db: Active database session.
            user_id: The UUID of the authenticated user.

        Returns:
            The User instance.

        Raises:
            NotFoundError: If the user no longer exists.
        """
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        user_id: UUID,
        data: UpdateProfileRequest,
    ) -> User:
        """Apply partial profile updates for the authenticated user.

        Only fields explicitly provided in ``data`` are written; omitted
        fields are left unchanged.

        Args:
            db: Active database session.
            user_id: The UUID of the authenticated user.
            data: Partial profile update payload.

        Returns:
            The updated User instance.

        Raises:
            NotFoundError: If the user no longer exists.
        """
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        if data.display_name is not None:
            user.display_name = data.display_name

        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def delete_account(db: AsyncSession, user_id: UUID) -> None:
        """Soft-delete the user account and revoke all active sessions.

        Marks the user as deleted and revokes all their sessions
        atomically.  The caller controls the transaction boundary.

        Args:
            db: Active database session.
            user_id: The UUID of the authenticated user.

        Raises:
            NotFoundError: If the user no longer exists.
        """
        user_repo = UserRepository(db)
        session_repo = SessionRepository(db)

        user = await user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        # Revoke all active sessions before marking the account deleted
        await session_repo.delete_all_sessions(user_id)

        user.deleted_at = datetime.now(UTC)
        await db.flush()
