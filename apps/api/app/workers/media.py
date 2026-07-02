"""Media background tasks.

Contains two ARQ task functions:

``process_media``
    Processes a confirmed media upload — extracts metadata, generates a
    thumbnail, computes the blurhash, and transitions the record to COMPLETED.
    Fully idempotent: safe to retry on failure or re-run on a crashed job.

``clean_stale_media``
    Cron job that deletes expired PENDING upload records and their storage
    objects. Runs every 10 minutes.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import MediaProcessingStatus, MediaType, MediaUploadStatus
from app.db.repositories.media import MediaRepository
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)


async def process_media(ctx: dict[str, Any], media_id: str) -> None:
    """Process a confirmed media upload.

    Idempotency & Crash Recovery Guarantees
    --------------------------------------
    - If the record is already COMPLETED, exits immediately.
    - If the record is not UPLOADED, exits immediately.
    - Uses a compare-and-swap UPDATE (PENDING → PROCESSING) so only one
      worker claims the job when multiple workers race.
    - If the worker crashed mid-run (status stuck at PROCESSING), re-entry
      is allowed and all processing steps overwrite safely.
    - Raises on failure so ARQ re-enqueues for retry.

    CRASH SCENARIOS:
    1. Temporary / External Failures (e.g., S3 timeout, DB dropout):
       - First run fails, catches the error, marks DB status as FAILED, commits, and re-raises.
       - ARQ retries the job. When the retry succeeds, it overwrites the state, resets
         processing_error to null, and transitions status to COMPLETED.
    2. Permanent Failures / Repeated Crashes (e.g., corrupt file or OOM):
       - Python Exception (e.g., Pillow error): Worker catches it, marks DB as FAILED, commits,
         and re-raises. ARQ retries up to 5 times, then drops it from Redis. DB remains FAILED.
       - Hard Process Crash (e.g., SIGKILL/OOM): Worker process killed instantly. DB state
         remains stuck at PROCESSING. ARQ retries 5 times, then drops it. DB stays stuck
         at PROCESSING (requires manual cleanup or restart sweep).

    Args:
        ctx: ARQ context — must contain ``db`` (AsyncSession) and
             ``storage`` (StorageBackend).
        media_id: UUID string of the media record to process.
    """
    db: AsyncSession = ctx["db"]
    storage: StorageBackend = ctx["storage"]
    repo = MediaRepository(db)

    media = await repo.get_by_id(UUID(media_id))

    # Guard 1 — record missing or already done.
    if media is None or media.processing_status == MediaProcessingStatus.COMPLETED:
        return

    # Guard 2 — upload not yet confirmed; do not process.
    if media.upload_status != MediaUploadStatus.UPLOADED:
        logger.warning("process_media called for non-uploaded media %s", media_id)
        return

    # Guard 3 — CAS: attempt PENDING → PROCESSING.
    # Returns False if another worker already claimed the job.
    # Re-entry is allowed when status is PROCESSING (crashed worker retry).
    if media.processing_status == MediaProcessingStatus.PENDING:
        claimed = await repo.claim_for_processing(UUID(media_id))
        if not claimed:
            logger.info("Media %s already claimed by another worker.", media_id)
            return
        # Refresh the instance to reflect the status change.
        await db.refresh(media)

    try:
        # --- Download ---------------------------------------------------
        data = await storage.download(media.storage_key)

        # --- MIME validation --------------------------------------------
        _validate_mime(data, media.mime_type)

        # --- Dimension / duration extraction ----------------------------
        width, height, duration_seconds = None, None, None

        if media.media_type == MediaType.IMAGE:
            width, height = _extract_image_dimensions(data)
        # Video duration extraction requires ffprobe — deferred for V1.

        # --- Blurhash ---------------------------------------------------
        blurhash: str | None = None
        if media.media_type == MediaType.IMAGE:
            blurhash = _compute_blurhash(data)

        # --- Thumbnail --------------------------------------------------
        thumbnail_key: str | None = None
        if media.media_type == MediaType.IMAGE:
            thumbnail_data = _generate_thumbnail(data, media.mime_type)
            thumbnail_key = f"thumbnails/{media.storage_key}"
            await storage.upload(thumbnail_key, thumbnail_data, media.mime_type)

        # --- Persist results --------------------------------------------
        await repo.mark_completed(
            media,
            width=width,
            height=height,
            duration_seconds=duration_seconds,
            blurhash=blurhash,
            thumbnail_key=thumbnail_key,
            processed_at=datetime.now(UTC),
        )
        await db.commit()
        logger.info("Media %s processed successfully.", media_id)

    except Exception as exc:
        await repo.mark_failed(media, error=str(exc))
        await db.commit()
        logger.exception("Media %s processing failed: %s", media_id, exc)
        raise  # Re-raise so ARQ retries the job.


async def clean_stale_media(ctx: dict[str, Any]) -> None:
    """Delete expired PENDING upload records and mark stuck processing jobs as FAILED.

    Runs as a cron job every 10 minutes.

    Args:
        ctx: ARQ context — must contain ``db`` (AsyncSession) and
             ``storage`` (StorageBackend).
    """
    from datetime import timedelta

    db: AsyncSession = ctx["db"]
    storage: StorageBackend = ctx["storage"]
    repo = MediaRepository(db)

    now = datetime.now(UTC)

    # 1. Sweep stale pending uploads (delete from DB/storage)
    stale = await repo.list_stale_pending(before=now)
    if stale:
        logger.info("Cleaning %d stale pending media records.", len(stale))
        for media in stale:
            try:
                await storage.delete(media.storage_key)
            except FileNotFoundError:
                pass
            except Exception as exc:
                logger.warning(
                    "Failed to delete storage object %s: %s", media.storage_key, exc
                )
            await db.delete(media)
        await db.commit()
        logger.info("Cleaned %d stale media records.", len(stale))

    # 2. Sweep stuck processing jobs (mark as FAILED if lost in Redis)
    stuck_threshold = now - timedelta(hours=1)
    stuck = await repo.list_stuck_processing(before=stuck_threshold)
    if stuck:
        redis_pool = ctx.get("redis")
        if redis_pool:
            from arq.jobs import Job, JobStatus

            marked_count = 0
            for media in stuck:
                job = Job(str(media.id), redis_pool)
                status = await job.status()
                # If the job status in Redis is not_found, it means the job has vanished
                # (either it was dropped after max retries, or lost completely).
                if status == JobStatus.not_found:
                    logger.warning(
                        "Marking stuck media %s as FAILED (job not found in Redis).",
                        media.id,
                    )
                    await repo.mark_failed(
                        media,
                        error="Processing stalled. Job lost or dropped from the queue.",
                    )
                    marked_count += 1

            if marked_count > 0:
                await db.commit()
                logger.info(
                    "Marked %d stuck processing media records as FAILED.",
                    marked_count,
                )


# ---------------------------------------------------------------------------
# Processing helpers (pure functions — easy to unit-test)
# ---------------------------------------------------------------------------


def _validate_mime(data: bytes, declared_mime: str) -> None:
    """Raise ValueError if the file magic bytes contradict the declared MIME type.

    Args:
        data: Raw file bytes (only the first few bytes are inspected).
        declared_mime: MIME type declared by the client at upload time.

    Raises:
        ValueError: If the detected type does not match the declared type.
    """
    # JPEG: FF D8 FF
    # PNG:  89 50 4E 47 0D 0A 1A 0A
    # GIF:  47 49 46 38
    # WEBP: 52 49 46 46 ... 57 45 42 50
    magic_map = {
        b"\xff\xd8\xff": "image/jpeg",
        b"\x89PNG": "image/png",
        b"GIF8": "image/gif",
    }
    detected: str | None = None
    for magic, mime in magic_map.items():
        if data[: len(magic)] == magic:
            detected = mime
            break
    # WEBP has the magic at bytes 8-12
    if detected is None and data[8:12] == b"WEBP":
        detected = "image/webp"

    if detected is not None and detected != declared_mime:
        msg = f"File content ({detected}) does not match declared MIME type ({declared_mime})."
        raise ValueError(msg)


def _extract_image_dimensions(data: bytes) -> tuple[int, int]:
    """Return (width, height) of an image using Pillow.

    Args:
        data: Raw image bytes.

    Returns:
        A (width, height) tuple in pixels.

    Raises:
        ValueError: If Pillow cannot identify the image format.
    """
    import io

    from PIL import Image, UnidentifiedImageError  # type: ignore[import-untyped]

    try:
        with Image.open(io.BytesIO(data)) as img:
            return img.width, img.height
    except UnidentifiedImageError as exc:
        raise ValueError(f"Cannot identify image format: {exc}") from exc


def _compute_blurhash(data: bytes) -> str:
    """Compute a blurhash string for an image.

    Args:
        data: Raw image bytes.

    Returns:
        A blurhash string.
    """
    import io

    import blurhash  # type: ignore[import-untyped]
    from PIL import Image  # type: ignore[import-untyped]

    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        return blurhash.encode(img, 4, 3)


def _generate_thumbnail(data: bytes, mime_type: str, max_size: int = 400) -> bytes:
    """Generate a square-cropped thumbnail and return JPEG bytes.

    Args:
        data: Raw image bytes.
        mime_type: Original MIME type (unused currently, reserved for future).
        max_size: Maximum pixel dimension for the thumbnail.

    Returns:
        JPEG-encoded thumbnail bytes.
    """
    import io

    from PIL import Image  # type: ignore[import-untyped]

    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue()
