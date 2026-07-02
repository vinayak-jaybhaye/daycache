"""Media repository implementation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import MediaProcessingStatus, MediaUploadStatus
from app.db.models import Media
from app.db.repositories.base import BaseRepository


class MediaRepository(BaseRepository[Media]):
    """Repository handling persistence operations for the Media model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Media)

    async def get_by_id_for_user(self, user_id: UUID, media_id: UUID) -> Media | None:
        """Fetch a media record belonging to a specific user.

        Returns None for expired or non-existent records so callers
        always get a 404 — no state is leaked for records the user
        doesn't own.

        Args:
            user_id: The UUID of the owning user.
            media_id: The UUID of the media record.

        Returns:
            The Media instance if it exists and belongs to the user,
            or None otherwise.
        """
        result = await self._session.execute(
            select(Media).where(
                Media.id == media_id,
                Media.user_id == str(user_id),
                Media.upload_status != MediaUploadStatus.EXPIRED,
            )
        )
        return result.scalar_one_or_none()

    async def claim_for_processing(self, media_id: UUID) -> bool:
        """Atomically transition processing_status from PENDING to PROCESSING.

        Uses a compare-and-swap UPDATE so that only one worker can claim
        the job even if multiple workers race to process the same record.

        Args:
            media_id: The UUID of the media record to claim.

        Returns:
            True if this caller successfully claimed the record,
            False if another worker already claimed it or the record
            is in an unexpected state.
        """
        result = await self._session.execute(
            update(Media)
            .where(
                Media.id == media_id,
                Media.processing_status == MediaProcessingStatus.PENDING,
            )
            .values(processing_status=MediaProcessingStatus.PROCESSING)
            .returning(Media.id)
        )
        await self._session.flush()
        return result.scalar_one_or_none() is not None

    async def mark_completed(
        self,
        media: Media,
        *,
        width: int | None,
        height: int | None,
        duration_seconds: int | None,
        blurhash: str | None,
        thumbnail_key: str | None,
        processed_at: datetime,
    ) -> None:
        """Transition a media record to COMPLETED and persist metadata.

        Args:
            media: The Media instance to update.
            width: Image/video width in pixels.
            height: Image/video height in pixels.
            duration_seconds: Video duration (None for images).
            blurhash: Perceptual blurhash string.
            thumbnail_key: Storage key of the generated thumbnail.
            processed_at: Timestamp when processing finished.
        """
        media.processing_status = MediaProcessingStatus.COMPLETED
        media.width = width
        media.height = height
        media.duration_seconds = duration_seconds
        media.blurhash = blurhash
        media.thumbnail_key = thumbnail_key
        media.processed_at = processed_at
        media.processing_error = None
        await self._session.flush()

    async def mark_failed(self, media: Media, *, error: str) -> None:
        """Transition a media record to FAILED and record the error message.

        Args:
            media: The Media instance to update.
            error: Human-readable error description.
        """
        media.processing_status = MediaProcessingStatus.FAILED
        media.processing_error = error
        await self._session.flush()

    async def list_stale_pending(self, *, before: datetime) -> list[Media]:
        """Return PENDING upload records whose TTL has elapsed.

        Used by the cleanup cron job to find and delete expired rows.

        Args:
            before: Only return records with upload_expires_at before this
                    timestamp (typically ``datetime.now(UTC)``).

        Returns:
            A list of expired Media instances.
        """
        result = await self._session.execute(
            select(Media).where(
                Media.upload_status == MediaUploadStatus.PENDING,
                Media.upload_expires_at < before,
            )
        )
        return list(result.scalars().all())

    async def list_stuck_processing(self, *, before: datetime) -> list[Media]:
        """Return UPLOADED records stuck in PENDING/PROCESSING since before the timestamp.

        Used by the cleanup cron job to mark crashed/orphaned runs as FAILED.

        Args:
            before: Only return records with updated_at before this timestamp.

        Returns:
            A list of stuck Media instances.
        """
        result = await self._session.execute(
            select(Media).where(
                Media.upload_status == MediaUploadStatus.UPLOADED,
                Media.processing_status.in_(
                    [MediaProcessingStatus.PENDING, MediaProcessingStatus.PROCESSING]
                ),
                Media.updated_at < before,
            )
        )
        return list(result.scalars().all())

    async def get_by_storage_key(self, key: str) -> Media | None:
        """Return a Media record by its storage key.

        Args:
            key: The storage key to search for.

        Returns:
            The Media instance or None if not found.
        """
        result = await self._session.execute(
            select(Media).where(Media.storage_key == key)
        )
        return result.scalar_one_or_none()
