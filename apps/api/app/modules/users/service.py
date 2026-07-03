"""Users module business service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import MediaProcessingStatus, MediaUploadStatus
from app.db.models import Media, User
from app.db.repositories import SessionRepository, UserRepository
from app.exceptions import GoneError, NotFoundError, UnprocessableError

if TYPE_CHECKING:
    from arq import ArqRedis

    from app.core.config import Settings
    from app.modules.users.schemas import UpdateProfileRequest, UserProfileResponse
    from app.storage.base import StorageBackend


class UserService:
    """Orchestrates user profile management and account lifecycle."""

    @staticmethod
    async def build_profile_response(
        db: AsyncSession,
        user: User,
        storage: StorageBackend,
        url_ttl: int = 3600,
    ) -> UserProfileResponse:
        """Construct a ``UserProfileResponse``, resolving a signed avatar URL.

        If the user has an ``avatar_media_id``, fetches the media record and
        generates a short-lived signed URL for the thumbnail.  The thumbnail
        key is derived from the media ``storage_key`` at response time so that
        changes to thumbnail conventions only require updating this method.

        Args:
            db: Active database session.
            user: The User ORM instance.
            storage: Configured storage backend.
            url_ttl: Signed URL TTL in seconds (default 1 hour).

        Returns:
            A populated ``UserProfileResponse``.
        """
        from app.modules.users.schemas import UserProfileResponse

        avatar_url: str | None = None

        if user.avatar_media_id:
            media: Media | None = await db.get(Media, user.avatar_media_id)
            if (
                media is not None
                and media.processing_status == MediaProcessingStatus.COMPLETED
            ):
                thumbnail_key = f"thumbnails/{media.storage_key}"
                avatar_url = await storage.get_url(thumbnail_key, expires_in=url_ttl)

        return UserProfileResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            avatar_url=avatar_url,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    @staticmethod
    async def request_avatar_upload(
        db: AsyncSession,
        storage: StorageBackend,
        user_id: UUID,
        mime_type: str,
        size: int,
        settings: Settings,
    ) -> tuple[UUID, str, datetime]:
        """Create a PENDING avatar media record and return a presigned PUT URL.

        Mime type and size validation are performed at the schema layer
        (``AvatarUploadRequest``) before this method is called.

        Args:
            db: Active database session.
            storage: Configured storage backend.
            user_id: Authenticated user's UUID.
            mime_type: Already-validated image MIME type.
            size: Declared file size in bytes (validated ≤ 5 MB by schema).
            settings: Application settings.

        Returns:
            Tuple of (media_id, upload_url, upload_expires_at).
        """
        from app.db.enums import MediaType
        from app.db.models.media import Media
        from app.db.repositories.media import MediaRepository

        _EXT_MAP: dict[str, str] = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }
        ext = _EXT_MAP[mime_type]
        repo = MediaRepository(db)
        now = datetime.now(UTC)
        upload_expires_at = datetime.fromtimestamp(
            now.timestamp() + settings.MEDIA_UPLOAD_TTL, tz=UTC
        )

        # The avatars/ prefix is the server-controlled proof that this media
        # was created through the avatar upload flow, not picked from general media.
        storage_key = f"avatars/{user_id}/{uuid.uuid4()}.{ext}"

        media = Media(
            user_id=str(user_id),
            storage_key=storage_key,
            media_type=MediaType.IMAGE,
            mime_type=mime_type,
            size=size,
            upload_status=MediaUploadStatus.PENDING,
            upload_expires_at=upload_expires_at,
            processing_status=None,
        )
        await repo.create(media)

        upload_url = await storage.generate_presigned_put(
            storage_key,
            mime_type,
            expires_in=settings.MEDIA_UPLOAD_TTL,
        )

        return media.id, upload_url, upload_expires_at

    @staticmethod
    async def confirm_avatar_upload(
        db: AsyncSession,
        storage: StorageBackend,
        arq_pool: ArqRedis,
        user: User,
        settings: Settings,
    ) -> User:
        """Confirm the avatar upload, set avatar_media_id, and enqueue processing.

        The client passes no ``media_id`` — the server finds the most recent
        ``PENDING`` avatar upload for this user by querying on the
        ``avatars/`` storage key prefix.  This ensures:

        - The client never controls which media becomes the avatar.
        - Only media created through ``POST /users/me/avatar`` can be confirmed.
        - The ``avatars/`` prefix is server-set and unforgeable by the client.

        On success, sets ``users.avatar_media_id`` and enqueues the ARQ
        processing job.  The worker is unaware of the avatar relationship —
        it simply processes the media record.

        Args:
            db: Active database session.
            storage: Configured storage backend.
            arq_pool: ARQ Redis connection for job enqueueing.
            user: The authenticated User ORM instance.
            settings: Application settings.

        Returns:
            The updated User instance.

        Raises:
            NotFoundError: If no pending avatar upload exists for this user.
            GoneError: If the upload TTL has expired.
            UnprocessableError: If the object is missing from storage.
        """
        from app.db.repositories.media import MediaRepository

        repo = MediaRepository(db)
        media = await repo.get_pending_avatar_upload(user.id)
        if media is None:
            raise NotFoundError(
                "No pending avatar upload found. "
                "Request a new upload URL via POST /users/me/avatar."
            )

        now = datetime.now(UTC)
        if now > media.upload_expires_at:
            raise GoneError(
                "Avatar upload window expired. Please request a new upload URL."
            )

        # Verify the object actually landed in storage.
        exists = await storage.object_exists(media.storage_key)
        if not exists:
            raise UnprocessableError(
                "Avatar not found in storage. "
                "Ensure the PUT request completed successfully."
            )

        # Transition media state and enqueue worker.
        media.upload_status = MediaUploadStatus.UPLOADED
        media.processing_status = MediaProcessingStatus.PENDING
        await db.flush()

        await arq_pool.enqueue_job(
            "process_media", str(media.id), _job_id=str(media.id)
        )

        # Delete the previous avatar's storage objects before switching the
        # reference — avoids orphaned S3 objects accumulating over time.
        await UserService._delete_avatar_storage(db, storage, user)

        # Set the avatar reference — worker is unaware of this relationship.
        user.avatar_media_id = str(media.id)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def remove_avatar(
        db: AsyncSession, user: User, storage: StorageBackend
    ) -> User:
        """Clear the user's avatar reference and delete its storage objects.

        Deletes the media record and both the original and thumbnail objects
        from storage so no orphaned S3 objects accumulate.

        Args:
            db: Active database session.
            user: The authenticated User ORM instance.
            storage: Configured storage backend.

        Returns:
            The updated User instance.
        """
        await UserService._delete_avatar_storage(db, storage, user)
        user.avatar_media_id = None
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def _delete_avatar_storage(
        db: AsyncSession,
        storage: StorageBackend,
        user: User,
    ) -> None:
        """Delete the current avatar media record and its S3 objects.

        Safe to call when ``user.avatar_media_id`` is ``None`` — no-op in
        that case.  Delegates deletion logic directly to the media service.

        Args:
            db: Active database session.
            storage: Configured storage backend.
            user: User whose current avatar should be cleaned up.
        """
        if not user.avatar_media_id:
            return

        from app.modules.media.service import MediaService

        await MediaService.delete_media_by_id(db, storage, UUID(user.avatar_media_id))

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

        await session_repo.delete_all_sessions(user_id)
        user.deleted_at = datetime.now(UTC)
        await db.flush()
