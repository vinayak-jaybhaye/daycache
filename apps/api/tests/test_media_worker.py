"""Unit tests for the media background worker tasks.

Tests ``process_media`` idempotency guards and ``clean_stale_media``.
Uses an in-memory SQLAlchemy session and InMemoryStorage — no ARQ, no Redis.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from PIL import Image as PILImage
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import MediaProcessingStatus, MediaType, MediaUploadStatus
from app.db.models import Media
from app.workers.media import (
    _compute_blurhash,
    _extract_image_dimensions,
    _generate_thumbnail,
    _validate_mime,
    clean_stale_media,
    process_media,
)

# ---------------------------------------------------------------------------
# In-memory storage (same as test_media.py, kept local for isolation)
# ---------------------------------------------------------------------------


class InMemoryStorage:
    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        self._data[key] = data
        return key

    async def download(self, key: str) -> bytes:
        if key not in self._data:
            raise FileNotFoundError(key)
        return self._data[key]

    async def delete(self, key: str) -> None:
        if key not in self._data:
            raise FileNotFoundError(key)
        del self._data[key]

    async def get_url(self, key: str, *, expires_in: int = 3600) -> str:
        return f"http://fake/{key}"

    async def generate_presigned_put(
        self, key: str, mime_type: str, *, expires_in: int = 300
    ) -> str:
        return f"http://fake/put/{key}"

    async def object_exists(self, key: str) -> bool:
        return key in self._data


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_media(
    *,
    user_id: str | None = None,
    upload_status: MediaUploadStatus = MediaUploadStatus.UPLOADED,
    processing_status: MediaProcessingStatus | None = MediaProcessingStatus.PENDING,
    storage_key: str | None = None,
    expires_in: int = 300,
) -> Media:
    """Build a detached Media instance for testing."""
    media = Media()
    media.id = UUID(str(uuid.uuid4()))
    media.user_id = user_id or str(uuid.uuid4())
    media.storage_key = storage_key or f"media/{uuid.uuid4()}.jpg"
    media.media_type = MediaType.IMAGE
    media.mime_type = "image/jpeg"
    media.size = 1024
    media.upload_status = upload_status
    media.processing_status = processing_status
    media.upload_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    return media


def _make_jpeg(width: int = 10, height: int = 10) -> bytes:
    """Return minimal valid JPEG bytes via Pillow."""
    buf = io.BytesIO()
    img = PILImage.new("RGB", (width, height), color=(255, 0, 0))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_ctx(db: AsyncSession, storage: InMemoryStorage) -> dict[str, Any]:
    return {"db": db, "storage": storage}


# ===========================================================================
# process_media — idempotency guards
# ===========================================================================


@pytest.mark.asyncio
async def test_process_media_guard_already_completed(
    db_session: AsyncSession,
) -> None:
    """If media is already COMPLETED, process_media exits without touching anything."""
    storage = InMemoryStorage()
    media = _make_media(processing_status=MediaProcessingStatus.COMPLETED)

    with patch(
        "app.workers.media.MediaRepository.get_by_id",
        new=AsyncMock(return_value=media),
    ):
        # Should return without error and without touching storage.
        await process_media(_make_ctx(db_session, storage), str(media.id))

    # Storage untouched.
    assert len(storage._data) == 0


@pytest.mark.asyncio
async def test_process_media_guard_not_uploaded(
    db_session: AsyncSession,
) -> None:
    """If upload_status is PENDING (not yet uploaded), exits without processing."""
    storage = InMemoryStorage()
    media = _make_media(
        upload_status=MediaUploadStatus.PENDING,
        processing_status=MediaProcessingStatus.PENDING,
    )

    with patch(
        "app.workers.media.MediaRepository.get_by_id",
        new=AsyncMock(return_value=media),
    ):
        await process_media(_make_ctx(db_session, storage), str(media.id))

    assert len(storage._data) == 0


@pytest.mark.asyncio
async def test_process_media_guard_claim_fails(
    db_session: AsyncSession,
) -> None:
    """If claim_for_processing returns False, exits (another worker got it)."""
    storage = InMemoryStorage()
    media = _make_media()

    with (
        patch(
            "app.workers.media.MediaRepository.get_by_id",
            new=AsyncMock(return_value=media),
        ),
        patch(
            "app.workers.media.MediaRepository.claim_for_processing",
            new=AsyncMock(return_value=False),
        ),
    ):
        await process_media(_make_ctx(db_session, storage), str(media.id))

    assert len(storage._data) == 0


@pytest.mark.asyncio
async def test_process_media_guard_missing_record(
    db_session: AsyncSession,
) -> None:
    """If the media record is not found, exits gracefully."""
    storage = InMemoryStorage()

    with patch(
        "app.workers.media.MediaRepository.get_by_id",
        new=AsyncMock(return_value=None),
    ):
        await process_media(_make_ctx(db_session, storage), str(uuid.uuid4()))


# ===========================================================================
# process_media — success path
# ===========================================================================


@pytest.mark.asyncio
async def test_process_media_success_image(
    db_session: AsyncSession,
) -> None:
    """process_media: valid JPEG → COMPLETED with dimensions, blurhash, thumbnail."""
    storage = InMemoryStorage()
    jpeg_bytes = _make_jpeg(20, 10)
    media = _make_media(storage_key="media/test.jpg")
    await storage.upload(media.storage_key, jpeg_bytes, "image/jpeg")

    completed_media: Media | None = None

    async def fake_mark_completed(m: Media, **kwargs) -> None:  # type: ignore[override]
        nonlocal completed_media
        completed_media = m
        m.processing_status = MediaProcessingStatus.COMPLETED
        m.width = kwargs.get("width")
        m.height = kwargs.get("height")
        m.blurhash = kwargs.get("blurhash")
        m.thumbnail_key = kwargs.get("thumbnail_key")

    with (
        patch(
            "app.workers.media.MediaRepository.get_by_id",
            new=AsyncMock(return_value=media),
        ),
        patch(
            "app.workers.media.MediaRepository.claim_for_processing",
            new=AsyncMock(return_value=True),
        ),
        patch.object(db_session, "refresh", new=AsyncMock()),
        patch.object(db_session, "commit", new=AsyncMock()),
        patch(
            "app.workers.media.MediaRepository.mark_completed",
            new=AsyncMock(side_effect=fake_mark_completed),
        ),
    ):
        await process_media(_make_ctx(db_session, storage), str(media.id))

    assert completed_media is not None
    assert completed_media.width == 20
    assert completed_media.height == 10
    assert completed_media.blurhash is not None
    # Thumbnail should have been uploaded.
    assert await storage.object_exists(f"thumbnails/{media.storage_key}")


@pytest.mark.asyncio
async def test_process_media_invalid_mime_marks_failed(
    db_session: AsyncSession,
) -> None:
    """Non-image bytes with image/jpeg MIME → FAILED, re-raises for ARQ retry."""
    storage = InMemoryStorage()
    media = _make_media(storage_key="media/bad.jpg")
    # Upload clearly non-image bytes (PDF magic bytes).
    await storage.upload(media.storage_key, b"%PDF-1.4 fake content", "image/jpeg")

    failed_error: str | None = None

    async def fake_mark_failed(m: Media, *, error: str) -> None:
        nonlocal failed_error
        failed_error = error
        m.processing_status = MediaProcessingStatus.FAILED

    with (
        patch(
            "app.workers.media.MediaRepository.get_by_id",
            new=AsyncMock(return_value=media),
        ),
        patch(
            "app.workers.media.MediaRepository.claim_for_processing",
            new=AsyncMock(return_value=True),
        ),
        patch.object(db_session, "refresh", new=AsyncMock()),
        patch.object(db_session, "commit", new=AsyncMock()),
        patch(
            "app.workers.media.MediaRepository.mark_failed",
            new=AsyncMock(side_effect=fake_mark_failed),
        ),
        pytest.raises(ValueError),  # process_media re-raises so ARQ can retry
    ):
        await process_media(_make_ctx(db_session, storage), str(media.id))


# ===========================================================================
# clean_stale_media
# ===========================================================================


@pytest.mark.asyncio
async def test_clean_stale_media_deletes_expired_rows(
    db_session: AsyncSession,
) -> None:
    """Cleanup cron deletes stale storage objects and DB rows."""
    storage = InMemoryStorage()
    stale = _make_media(
        upload_status=MediaUploadStatus.PENDING,
        processing_status=None,
        expires_in=-60,  # Already expired.
    )
    await storage.upload(stale.storage_key, b"orphan", "image/jpeg")

    deleted_rows: list[Media] = []

    async def fake_db_delete(obj: object) -> None:
        if isinstance(obj, Media):
            deleted_rows.append(obj)

    with (
        patch(
            "app.workers.media.MediaRepository.list_stale_pending",
            new=AsyncMock(return_value=[stale]),
        ),
        patch.object(db_session, "delete", new=AsyncMock(side_effect=fake_db_delete)),
        patch.object(db_session, "commit", new=AsyncMock()),
    ):
        await clean_stale_media(_make_ctx(db_session, storage))

    assert stale in deleted_rows
    assert not await storage.object_exists(stale.storage_key)


@pytest.mark.asyncio
async def test_clean_stale_media_no_rows(db_session: AsyncSession) -> None:
    """Cleanup cron is a no-op when there are no stale records."""
    storage = InMemoryStorage()

    with (
        patch(
            "app.workers.media.MediaRepository.list_stale_pending",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(db_session, "commit", new=AsyncMock()) as mock_commit,
    ):
        await clean_stale_media(_make_ctx(db_session, storage))
        mock_commit.assert_not_called()


@pytest.mark.asyncio
async def test_clean_stale_media_missing_object_is_tolerated(
    db_session: AsyncSession,
) -> None:
    """Cleanup cron continues when a storage object is already gone."""
    storage = InMemoryStorage()
    stale = _make_media(upload_status=MediaUploadStatus.PENDING, processing_status=None)
    # Do NOT upload the object — simulates a partially-created record.

    deleted_rows: list[Media] = []

    with (
        patch(
            "app.workers.media.MediaRepository.list_stale_pending",
            new=AsyncMock(return_value=[stale]),
        ),
        patch.object(
            db_session,
            "delete",
            new=AsyncMock(side_effect=deleted_rows.append),
        ),
        patch.object(db_session, "commit", new=AsyncMock()),
    ):
        # Should not raise even though storage.delete raises FileNotFoundError.
        await clean_stale_media(_make_ctx(db_session, storage))

    assert stale in deleted_rows


# ===========================================================================
# Pure helper functions
# ===========================================================================


def test_validate_mime_jpeg_passes() -> None:
    """Valid JPEG magic bytes pass MIME validation."""
    _validate_mime(b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")


def test_validate_mime_png_passes() -> None:
    """Valid PNG magic bytes pass MIME validation."""
    _validate_mime(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, "image/png")


def test_validate_mime_mismatch_raises() -> None:
    """JPEG bytes declared as PNG raises ValueError."""
    with pytest.raises(ValueError, match="image/jpeg"):
        _validate_mime(b"\xff\xd8\xff" + b"\x00" * 100, "image/png")


def test_extract_image_dimensions_correct() -> None:
    """extract_image_dimensions returns correct width and height."""
    jpeg = _make_jpeg(30, 15)
    w, h = _extract_image_dimensions(jpeg)
    assert w == 30
    assert h == 15


def test_extract_image_dimensions_invalid_raises() -> None:
    """Invalid bytes raise ValueError."""
    with pytest.raises(ValueError, match="Cannot identify"):
        _extract_image_dimensions(b"not-an-image")


def test_compute_blurhash_returns_string() -> None:
    """compute_blurhash returns a non-empty string."""
    jpeg = _make_jpeg(8, 8)
    result = _compute_blurhash(jpeg)
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_thumbnail_returns_jpeg_bytes() -> None:
    """generate_thumbnail returns valid JPEG-encoded bytes."""
    jpeg = _make_jpeg(200, 200)
    thumb = _generate_thumbnail(jpeg, "image/jpeg", max_size=64)
    # Check JPEG magic bytes.
    assert thumb[:3] == b"\xff\xd8\xff"
    # Verify the thumbnail is a valid image with reduced dimensions.
    with PILImage.open(io.BytesIO(thumb)) as img:
        assert img.width <= 64
        assert img.height <= 64


def test_generate_thumbnail_respects_max_size() -> None:
    """Thumbnail dimensions do not exceed max_size on either axis."""
    jpeg = _make_jpeg(500, 300)
    thumb = _generate_thumbnail(jpeg, "image/jpeg", max_size=100)
    with PILImage.open(io.BytesIO(thumb)) as img:
        assert img.width <= 100
        assert img.height <= 100
