"""Integration tests for the Media V1 endpoints.

Covers all four routes:
  POST   /media/upload
  POST   /media/{id}/confirm
  GET    /media/{id}
  DELETE /media/{id}

Uses:
- ``InMemoryStorage`` — avoids real disk / S3 I/O.
- ``FakeArqPool``     — captures enqueued jobs without Redis.
- ``db_session``      — rolls back after every test (from conftest).
- ``auth_headers``    — registers a user and returns session cookie headers.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.media import get_arq_pool
from app.db.enums import MediaProcessingStatus, MediaUploadStatus
from app.db.models import Media
from app.main import app
from app.storage.base import StorageBackend
from app.storage.factory import get_storage

# ---------------------------------------------------------------------------
# Fake helpers
# ---------------------------------------------------------------------------


class InMemoryStorage(StorageBackend):
    """Thread-safe, dict-backed storage backend for tests."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        self._data[key] = data
        return key

    async def download(self, key: str) -> bytes:
        if key not in self._data:
            raise FileNotFoundError(f"Object not found: {key!r}")
        return self._data[key]

    async def delete(self, key: str) -> None:
        if key not in self._data:
            raise FileNotFoundError(f"Object not found: {key!r}")
        del self._data[key]

    async def get_url(self, key: str, *, expires_in: int = 3600) -> str:
        return f"http://fake-storage/{key}"

    async def generate_presigned_put(
        self, key: str, mime_type: str, *, expires_in: int = 300
    ) -> str:
        return f"http://fake-storage/put/{key}"

    async def object_exists(self, key: str) -> bool:
        return key in self._data


class FakeArqPool:
    """Captures enqueued ARQ jobs without touching Redis."""

    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def enqueue_job(self, function_name: str, *args: Any, **kwargs: Any) -> None:
        self.enqueued.append((function_name, args, kwargs))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def storage() -> InMemoryStorage:
    """Return a fresh in-memory storage backend per test."""
    return InMemoryStorage()


@pytest_asyncio.fixture
async def arq_pool() -> FakeArqPool:
    """Return a fresh fake ARQ pool per test."""
    return FakeArqPool()


@pytest_asyncio.fixture
async def auth_headers(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> dict[str, str]:
    """Register a user and return session cookie headers."""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"media-test-{uuid.uuid4().hex[:8]}@example.com",
            "password": "Test1234!secure",
            "display_name": "Media Tester",
        },
    )
    assert reg.status_code == 201, reg.json()

    login = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": reg.json()["email"],
            "password": "Test1234!secure",
            "installation_id": str(uuid.uuid4()),
            "device_name": "Test Device",
            "platform": "web",
        },
    )
    assert login.status_code == 200, login.json()
    cookie_header = login.headers.get("set-cookie", "")
    # Extract just the session cookie value for subsequent requests.
    return {"Cookie": cookie_header.split(";")[0]}


@pytest_asyncio.fixture(autouse=True)
async def override_deps(
    storage: InMemoryStorage,
    arq_pool: FakeArqPool,
    db_session: AsyncSession,
) -> AsyncGenerator[None, None]:
    """Override storage and ARQ pool dependencies for every test."""

    async def _get_storage() -> StorageBackend:
        return storage

    async def _get_arq_pool() -> FakeArqPool:
        return arq_pool

    app.dependency_overrides[get_storage] = _get_storage  # type: ignore[assignment]
    app.dependency_overrides[get_arq_pool] = _get_arq_pool  # type: ignore[assignment]
    yield
    # get_db is already overridden by the db_session conftest fixture.
    # Only remove the storage / arq overrides here.
    app.dependency_overrides.pop(get_storage, None)
    app.dependency_overrides.pop(get_arq_pool, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IMAGE_PAYLOAD = {
    "media_type": "image",
    "mime_type": "image/jpeg",
    "filename": "photo.jpg",
    "size": 1024 * 100,  # 100 KB
}


async def _request_upload(
    client: AsyncClient,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Helper: POST /media/upload and assert 201."""
    response = await client.post(
        "/api/v1/media/upload",
        json=payload or _IMAGE_PAYLOAD,
        headers=headers,
    )
    assert response.status_code == 201, response.json()
    return response.json()


async def _put_file(
    client: AsyncClient,
    storage: InMemoryStorage,
    storage_key: str,
) -> None:
    """Simulate the client completing the presigned PUT by writing to storage."""
    await storage.upload(storage_key, b"fake-image-bytes", "image/jpeg")


# ===========================================================================
# POST /media/upload
# ===========================================================================


@pytest.mark.asyncio
async def test_upload_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Valid image upload request returns 201 with a presigned URL."""
    data = await _request_upload(async_client, auth_headers)

    assert "media_id" in data
    assert "upload_url" in data
    assert "upload_expires_at" in data
    # Local fake backend returns a predictable URL prefix.
    assert "fake-storage" in data["upload_url"]


@pytest.mark.asyncio
async def test_upload_no_auth(async_client: AsyncClient) -> None:
    """Unauthenticated requests are rejected with 401."""
    response = await async_client.post("/api/v1/media/upload", json=_IMAGE_PAYLOAD)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_size_too_large(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Files exceeding the 50 MB limit are rejected with 422."""
    payload = {**_IMAGE_PAYLOAD, "size": 51 * 1024 * 1024}
    response = await async_client.post(
        "/api/v1/media/upload", json=payload, headers=auth_headers
    )
    assert response.status_code == 422
    assert "50 MB" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_invalid_mime_for_image(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Image media_type with a video MIME type is rejected with 422."""
    payload = {**_IMAGE_PAYLOAD, "mime_type": "video/mp4"}
    response = await async_client.post(
        "/api/v1/media/upload", json=payload, headers=auth_headers
    )
    assert response.status_code == 422
    assert "MIME" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_zero_size_rejected(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """size=0 is rejected by Pydantic (gt=0) before hitting the service."""
    payload = {**_IMAGE_PAYLOAD, "size": 0}
    response = await async_client.post(
        "/api/v1/media/upload", json=payload, headers=auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_missing_fields(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Missing required fields return 422 with validation errors."""
    response = await async_client.post(
        "/api/v1/media/upload", json={}, headers=auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_creates_pending_record(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """A successful upload request creates a PENDING media row in the DB."""
    from sqlalchemy import select

    data = await _request_upload(async_client, auth_headers)
    media_id = UUID(data["media_id"])

    result = await db_session.execute(select(Media).where(Media.id == media_id))
    media = result.scalar_one_or_none()

    assert media is not None
    assert media.upload_status == MediaUploadStatus.PENDING
    assert media.processing_status is None
    assert media.upload_expires_at is not None


# ===========================================================================
# POST /media/{id}/confirm
# ===========================================================================


@pytest.mark.asyncio
async def test_confirm_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    arq_pool: FakeArqPool,
    db_session: AsyncSession,
) -> None:
    """Confirm after a real upload → UPLOADED/PENDING, job enqueued."""
    from sqlalchemy import select

    upload_data = await _request_upload(async_client, auth_headers)
    media_id = upload_data["media_id"]

    # Derive the storage key from the DB record.
    result = await db_session.execute(select(Media).where(Media.id == UUID(media_id)))
    media = result.scalar_one()
    await _put_file(async_client, storage, media.storage_key)

    response = await async_client.post(
        f"/api/v1/media/{media_id}/confirm", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["upload_status"] == "uploaded"
    assert data["processing_status"] == "pending"

    # Worker job must have been enqueued.
    assert len(arq_pool.enqueued) == 1
    assert arq_pool.enqueued[0][0] == "process_media"
    assert arq_pool.enqueued[0][1][0] == media_id


@pytest.mark.asyncio
async def test_confirm_object_not_in_storage(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Confirm without uploading the file returns 422 (storage guard)."""
    upload_data = await _request_upload(async_client, auth_headers)
    # Do NOT write anything to storage.
    response = await async_client.post(
        f"/api/v1/media/{upload_data['media_id']}/confirm",
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "storage" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_confirm_expired_ttl(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    """Confirm after TTL has elapsed returns 410 Gone."""
    from sqlalchemy import select

    upload_data = await _request_upload(async_client, auth_headers)
    media_id = UUID(upload_data["media_id"])

    # Backdate upload_expires_at to simulate expiry.
    result = await db_session.execute(select(Media).where(Media.id == media_id))
    media = result.scalar_one()
    await _put_file(async_client, storage, media.storage_key)
    media.upload_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    response = await async_client.post(
        f"/api/v1/media/{media_id}/confirm", headers=auth_headers
    )
    assert response.status_code == 410
    assert "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_confirm_wrong_user(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    """Confirm on another user's media returns 404 (no info leakage)."""
    from sqlalchemy import select

    upload_data = await _request_upload(async_client, auth_headers)
    media_id = UUID(upload_data["media_id"])
    result = await db_session.execute(select(Media).where(Media.id == media_id))
    await _put_file(async_client, storage, result.scalar_one().storage_key)

    # Register a second user and confirm using their session.
    reg2 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"other-{uuid.uuid4().hex[:6]}@example.com",
            "password": "Test1234!secure",
            "display_name": "Other User",
        },
    )
    login2 = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": reg2.json()["email"],
            "password": "Test1234!secure",
            "installation_id": str(uuid.uuid4()),
            "device_name": "Device",
            "platform": "web",
        },
    )
    other_headers = {"Cookie": login2.headers["set-cookie"].split(";")[0]}

    response = await async_client.post(
        f"/api/v1/media/{media_id}/confirm", headers=other_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirm_not_found(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Confirm on a non-existent media_id returns 404."""
    response = await async_client.post(
        f"/api/v1/media/{uuid.uuid4()}/confirm", headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirm_idempotent(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    arq_pool: FakeArqPool,
    db_session: AsyncSession,
) -> None:
    """Calling confirm twice on an already-UPLOADED record is idempotent (200)."""
    from sqlalchemy import select

    upload_data = await _request_upload(async_client, auth_headers)
    media_id = upload_data["media_id"]
    result = await db_session.execute(select(Media).where(Media.id == UUID(media_id)))
    await _put_file(async_client, storage, result.scalar_one().storage_key)

    r1 = await async_client.post(
        f"/api/v1/media/{media_id}/confirm", headers=auth_headers
    )
    r2 = await async_client.post(
        f"/api/v1/media/{media_id}/confirm", headers=auth_headers
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Job enqueued only once.
    assert len(arq_pool.enqueued) == 1


@pytest.mark.asyncio
async def test_confirm_retry_failed_job(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    arq_pool: FakeArqPool,
    db_session: AsyncSession,
) -> None:
    """Calling confirm on a FAILED or stuck processing record allows manual retry."""
    from sqlalchemy import select

    from app.db.enums import MediaProcessingStatus

    upload_data = await _request_upload(async_client, auth_headers)
    media_id = upload_data["media_id"]
    result = await db_session.execute(select(Media).where(Media.id == UUID(media_id)))
    media = result.scalar_one()
    await _put_file(async_client, storage, media.storage_key)

    # 1. First confirmation succeeds
    r1 = await async_client.post(
        f"/api/v1/media/{media_id}/confirm", headers=auth_headers
    )
    assert r1.status_code == 200
    assert len(arq_pool.enqueued) == 1

    # 2. Simulate background task failing and setting state to FAILED
    media.processing_status = MediaProcessingStatus.FAILED
    media.processing_error = "Simulated OOM crash"
    await db_session.flush()

    # 3. Confirming again resets state and re-enqueues the job
    r2 = await async_client.post(
        f"/api/v1/media/{media_id}/confirm", headers=auth_headers
    )
    assert r2.status_code == 200

    # Reload from DB
    await db_session.refresh(media)
    assert media.processing_status == MediaProcessingStatus.PENDING
    assert media.processing_error is None
    # Job was enqueued a second time
    assert len(arq_pool.enqueued) == 2


# ===========================================================================
# GET /media/{id}
# ===========================================================================


@pytest.mark.asyncio
async def test_get_pending_state(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """PENDING media returns 200 with no read URLs."""
    upload_data = await _request_upload(async_client, auth_headers)
    response = await async_client.get(
        f"/api/v1/media/{upload_data['media_id']}", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["upload_status"] == "pending"
    assert data["processing_status"] is None
    assert data["read_url"] is None
    assert data["thumbnail_url"] is None


@pytest.mark.asyncio
async def test_get_completed_state(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    """COMPLETED media returns 200 with signed read URLs."""
    from sqlalchemy import select

    upload_data = await _request_upload(async_client, auth_headers)
    media_id = UUID(upload_data["media_id"])

    # Manually force to COMPLETED state.
    result = await db_session.execute(select(Media).where(Media.id == media_id))
    media = result.scalar_one()
    await _put_file(async_client, storage, media.storage_key)
    thumbnail_key = f"thumbnails/{media.storage_key}"
    await storage.upload(thumbnail_key, b"thumb", "image/jpeg")
    media.upload_status = MediaUploadStatus.UPLOADED
    media.processing_status = MediaProcessingStatus.COMPLETED
    media.thumbnail_key = thumbnail_key
    media.width = 800
    media.height = 600
    media.processed_at = datetime.now(UTC)
    await db_session.flush()

    response = await async_client.get(f"/api/v1/media/{media_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["processing_status"] == "completed"
    assert data["read_url"] is not None
    assert data["thumbnail_url"] is not None
    assert data["width"] == 800
    assert data["height"] == 600


@pytest.mark.asyncio
async def test_get_wrong_user_returns_404(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Getting another user's media returns 404."""
    upload_data = await _request_upload(async_client, auth_headers)

    reg2 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"get-other-{uuid.uuid4().hex[:6]}@example.com",
            "password": "Test1234!secure",
            "display_name": "Other",
        },
    )
    login2 = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": reg2.json()["email"],
            "password": "Test1234!secure",
            "installation_id": str(uuid.uuid4()),
            "device_name": "D",
            "platform": "web",
        },
    )
    other_headers = {"Cookie": login2.headers["set-cookie"].split(";")[0]}

    response = await async_client.get(
        f"/api/v1/media/{upload_data['media_id']}", headers=other_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_not_found(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Non-existent media_id returns 404."""
    response = await async_client.get(
        f"/api/v1/media/{uuid.uuid4()}", headers=auth_headers
    )
    assert response.status_code == 404


# ===========================================================================
# DELETE /media/{id}
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    """Delete removes the DB row and the storage object."""
    from sqlalchemy import select

    upload_data = await _request_upload(async_client, auth_headers)
    media_id = UUID(upload_data["media_id"])
    result = await db_session.execute(select(Media).where(Media.id == media_id))
    media = result.scalar_one()
    await _put_file(async_client, storage, media.storage_key)
    storage_key = media.storage_key

    response = await async_client.delete(
        f"/api/v1/media/{media_id}", headers=auth_headers
    )
    assert response.status_code == 204

    # Storage object gone.
    assert not await storage.object_exists(storage_key)

    # DB row gone (evict SQLAlchemy identity cache first).
    db_session.expire_all()
    result2 = await db_session.execute(select(Media).where(Media.id == media_id))
    assert result2.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_also_removes_thumbnail(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    """Delete removes both the main object and the thumbnail from storage."""
    from sqlalchemy import select

    upload_data = await _request_upload(async_client, auth_headers)
    media_id = UUID(upload_data["media_id"])
    result = await db_session.execute(select(Media).where(Media.id == media_id))
    media = result.scalar_one()

    await _put_file(async_client, storage, media.storage_key)
    thumb_key = f"thumbnails/{media.storage_key}"
    await storage.upload(thumb_key, b"thumbnail", "image/jpeg")
    media.thumbnail_key = thumb_key
    await db_session.flush()

    response = await async_client.delete(
        f"/api/v1/media/{media_id}", headers=auth_headers
    )
    assert response.status_code == 204
    assert not await storage.object_exists(media.storage_key)
    assert not await storage.object_exists(thumb_key)


@pytest.mark.asyncio
async def test_delete_wrong_user(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Deleting another user's media returns 404."""
    upload_data = await _request_upload(async_client, auth_headers)

    reg2 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"del-other-{uuid.uuid4().hex[:6]}@example.com",
            "password": "Test1234!secure",
            "display_name": "Other",
        },
    )
    login2 = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": reg2.json()["email"],
            "password": "Test1234!secure",
            "installation_id": str(uuid.uuid4()),
            "device_name": "D",
            "platform": "web",
        },
    )
    other_headers = {"Cookie": login2.headers["set-cookie"].split(";")[0]}

    response = await async_client.delete(
        f"/api/v1/media/{upload_data['media_id']}", headers=other_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_not_found(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Non-existent media_id returns 404."""
    response = await async_client.delete(
        f"/api/v1/media/{uuid.uuid4()}", headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_no_storage_object_still_succeeds(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Delete succeeds even when the storage object was never uploaded (PENDING)."""
    upload_data = await _request_upload(async_client, auth_headers)
    # Do NOT put anything in storage — delete should still return 204.
    response = await async_client.delete(
        f"/api/v1/media/{upload_data['media_id']}", headers=auth_headers
    )
    assert response.status_code == 204
