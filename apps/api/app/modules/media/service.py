"""Media module business service."""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import MediaProcessingStatus, MediaUploadStatus
from app.db.models import Media
from app.db.repositories.media import MediaRepository
from app.exceptions import GoneError, NotFoundError, UnprocessableError
from app.modules.media.schemas import MediaStatusResponse, MediaUploadResponse

if TYPE_CHECKING:
    from arq import ArqRedis

    from app.core.config import Settings
    from app.modules.media.schemas import MediaUploadRequest
    from app.storage.base import StorageBackend


class MediaService:
    """Orchestrates media upload lifecycle and processing coordination."""

    @staticmethod
    async def request_upload(
        db: AsyncSession,
        storage: StorageBackend,
        user_id: UUID,
        data: MediaUploadRequest,
        settings: Settings,
    ) -> MediaUploadResponse:
        """Create a PENDING media record and return a presigned PUT URL.

        Validates file size and MIME type before writing to the database.
        The client uses ``upload_url`` to PUT the file bytes directly to
        storage — the API never proxies the bytes.

        Args:
            db: Active database session.
            storage: Configured storage backend.
            user_id: Authenticated user's UUID.
            data: Upload request payload.
            settings: Application settings.

        Returns:
            A ``MediaUploadResponse`` with ``media_id``, ``upload_url``,
            and ``upload_expires_at``.

        Raises:
            UnprocessableError: If file is too large or MIME type is invalid.
        """
        if data.size > settings.MEDIA_MAX_SIZE:
            max_mb = settings.MEDIA_MAX_SIZE // (1024 * 1024)
            raise UnprocessableError(f"File size exceeds the {max_mb} MB limit.")

        try:
            data.validate_mime_for_type()
        except ValueError as exc:
            raise UnprocessableError(str(exc)) from exc

        repo = MediaRepository(db)
        now = datetime.now(UTC)
        upload_expires_at = datetime.fromtimestamp(
            now.timestamp() + settings.MEDIA_UPLOAD_TTL, tz=UTC
        )

        # Derive a unique storage key scoped to the user.
        ext = (
            data.filename.rsplit(".", 1)[-1].lower() if "." in data.filename else "bin"
        )
        storage_key = f"media/{user_id}/{uuid.uuid4()}.{ext}"

        media = Media(
            user_id=str(user_id),
            storage_key=storage_key,
            media_type=data.media_type,
            mime_type=data.mime_type,
            size=data.size,
            upload_status=MediaUploadStatus.PENDING,
            upload_expires_at=upload_expires_at,
            processing_status=None,
        )
        await repo.create(media)

        upload_url = await storage.generate_presigned_put(
            storage_key,
            data.mime_type,
            expires_in=settings.MEDIA_UPLOAD_TTL,
        )

        return MediaUploadResponse(
            media_id=media.id,
            upload_url=upload_url,
            upload_expires_at=upload_expires_at,
        )

    @staticmethod
    async def confirm_upload(
        db: AsyncSession,
        storage: StorageBackend,
        arq_pool: ArqRedis,
        user_id: UUID,
        media_id: UUID,
    ) -> MediaStatusResponse:
        """Confirm that the client completed the presigned PUT upload.

        Validates that:
        1. The upload TTL has not elapsed (→ 410 Gone).
        2. The object actually exists in storage (→ 400 if missing).

        On success, transitions the record to UPLOADED / PENDING and
        enqueues an ARQ processing job.

        Args:
            db: Active database session.
            storage: Configured storage backend.
            arq_pool: ARQ Redis connection for job enqueueing.
            user_id: Authenticated user's UUID.
            media_id: UUID of the media record to confirm.

        Returns:
            Current ``MediaStatusResponse`` after the transition.

        Raises:
            NotFoundError: If the media record does not exist for this user.
            UnprocessableError: If the upload TTL expired (410-equivalent).
            UnprocessableError: If the object is not found in storage.
        """
        repo = MediaRepository(db)
        media = await repo.get_by_id_for_user(user_id, media_id)
        if media is None:
            raise NotFoundError("Media not found.")

        # Idempotent: already completed or active — return current state.
        if media.processing_status in [
            MediaProcessingStatus.COMPLETED,
            MediaProcessingStatus.PENDING,
            MediaProcessingStatus.PROCESSING,
        ]:
            return await MediaService._build_status_response(
                media, storage, settings=None
            )

        # Check upload TTL only if the upload has not been confirmed yet.
        if media.upload_status != MediaUploadStatus.UPLOADED:
            now = datetime.now(UTC)
            if now > media.upload_expires_at:
                raise GoneError(
                    "Upload window expired. Please request a new upload URL."
                )

        # Verify the object actually landed in storage.
        exists = await storage.object_exists(media.storage_key)
        if not exists:
            raise UnprocessableError(
                "Upload not found in storage. Ensure the PUT request completed successfully."
            )

        # Transition states (or reset if retrying).
        media.upload_status = MediaUploadStatus.UPLOADED
        media.processing_status = MediaProcessingStatus.PENDING
        media.processing_error = None
        await db.flush()

        # Enqueue the ARQ processing job.
        await arq_pool.enqueue_job(
            "process_media", str(media_id), _job_id=str(media_id)
        )

        return await MediaService._build_status_response(media, storage, settings=None)

    @staticmethod
    async def get_media(
        db: AsyncSession,
        storage: StorageBackend,
        user_id: UUID,
        media_id: UUID,
        settings: Settings,
    ) -> MediaStatusResponse:
        """Return the current state of a media record with signed read URLs.

        Args:
            db: Active database session.
            storage: Configured storage backend.
            user_id: Authenticated user's UUID.
            media_id: UUID of the media record.
            settings: Application settings (for read URL TTL).

        Returns:
            ``MediaStatusResponse`` with signed URLs if processing completed.

        Raises:
            NotFoundError: If the record does not exist or has expired.
        """
        repo = MediaRepository(db)
        media = await repo.get_by_id_for_user(user_id, media_id)
        if media is None:
            raise NotFoundError("Media not found.")
        return await MediaService._build_status_response(
            media, storage, settings=settings
        )

    @staticmethod
    async def delete_media(
        db: AsyncSession,
        storage: StorageBackend,
        user_id: UUID,
        media_id: UUID,
    ) -> None:
        """Delete a media record and its storage objects.

        Deletes the main object and thumbnail (if present) from storage
        before removing the database row. Safe to call at any upload state.

        Args:
            db: Active database session.
            storage: Configured storage backend.
            user_id: Authenticated user's UUID.
            media_id: UUID of the media record.

        Raises:
            NotFoundError: If the record does not exist for this user.
        """
        repo = MediaRepository(db)
        media = await repo.get_by_id_for_user(user_id, media_id)
        if media is None:
            raise NotFoundError("Media not found.")

        await MediaService.delete_media_by_id(db, storage, media.id)

    @staticmethod
    async def delete_media_by_id(
        db: AsyncSession,
        storage: StorageBackend,
        media_id: UUID,
    ) -> None:
        """Delete a media record and all its associated S3 storage objects by ID.

        Deletes the original S3 object, the thumbnail object (if set in DB), and
        the default thumbnail path (thumbnails/{storage_key}) from storage,
        before deleting the database row.

        Args:
            db: Active database session.
            storage: Configured storage backend.
            media_id: UUID of the media record to wipe out.
        """
        media = await db.get(Media, media_id)
        if media is None:
            return

        # Gather keys to delete from storage.
        keys = {
            media.storage_key,
            media.thumbnail_key,
            f"thumbnails/{media.storage_key}",
        }
        for key in keys:
            if key is None:
                continue
            with contextlib.suppress(Exception):
                await storage.delete(key)

        await db.delete(media)
        await db.flush()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    async def _build_status_response(
        media: Media,
        storage: StorageBackend,
        settings: Settings | None,
    ) -> MediaStatusResponse:
        """Build a ``MediaStatusResponse``, generating signed URLs if complete."""
        from app.db.enums import MediaProcessingStatus

        read_url: str | None = None
        thumbnail_url: str | None = None
        ttl = settings.MEDIA_READ_URL_TTL if settings else 3600

        if media.processing_status == MediaProcessingStatus.COMPLETED:
            read_url = await storage.get_url(media.storage_key, expires_in=ttl)
            if media.thumbnail_key:
                thumbnail_url = await storage.get_url(
                    media.thumbnail_key, expires_in=ttl
                )

        return MediaStatusResponse(
            id=media.id,
            media_type=media.media_type,
            mime_type=media.mime_type,
            size=media.size,
            upload_status=media.upload_status,
            processing_status=media.processing_status,
            width=media.width,
            height=media.height,
            duration_seconds=media.duration_seconds,
            blurhash=media.blurhash,
            caption=media.caption,
            alt_text=media.alt_text,
            created_at=media.created_at,
            read_url=read_url,
            thumbnail_url=thumbnail_url,
        )
