"""Integration tests for the avatar upload flow and media internal service.

The public /media/* routes are unmounted (media is internal infrastructure).
These tests cover the avatar flow exposed through /users/me/avatar endpoints:

  POST   /users/me/avatar          (request presigned URL)
  POST   /users/me/avatar/confirm  (confirm upload, enqueue processing)
  DELETE /users/me/avatar          (clear avatar reference)

Internal service tests (worker, storage) remain in separate test modules.

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

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool
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
    app.dependency_overrides.pop(get_storage, None)
    app.dependency_overrides.pop(get_arq_pool, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _request_avatar_upload(
    client: AsyncClient,
    headers: dict[str, str],
    mime_type: str = "image/jpeg",
    size: int = 1024 * 100,  # 100 KB default
) -> dict[str, Any]:
    """POST /users/me/avatar and assert 201."""
    resp = await client.post(
        "/api/v1/users/me/avatar",
        json={"mime_type": mime_type, "size": size},
        headers=headers,
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()


async def _simulate_put(storage: InMemoryStorage, storage_key: str) -> None:
    """Simulate the client completing the presigned PUT to storage."""
    await storage.upload(storage_key, b"fake-image-bytes", "image/jpeg")


# ===========================================================================
# POST /users/me/avatar
# ===========================================================================


@pytest.mark.asyncio
async def test_avatar_upload_request_returns_presigned_url(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /users/me/avatar returns a presigned upload URL and media_id."""
    data = await _request_avatar_upload(async_client, auth_headers)

    assert "media_id" in data
    assert "upload_url" in data
    assert "upload_expires_at" in data
    assert data["upload_url"].startswith("http://fake-storage/put/avatars/")


@pytest.mark.asyncio
async def test_avatar_upload_request_no_auth(async_client: AsyncClient) -> None:
    """Unauthenticated request returns 401."""
    resp = await async_client.post(
        "/api/v1/users/me/avatar",
        json={"mime_type": "image/jpeg"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_avatar_upload_unsupported_mime_type(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Non-image MIME type returns 422."""
    resp = await async_client.post(
        "/api/v1/users/me/avatar",
        json={"mime_type": "video/mp4", "size": 1024},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_avatar_upload_size_too_large(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """File size exceeding 5 MB returns 422."""
    resp = await async_client.post(
        "/api/v1/users/me/avatar",
        json={"mime_type": "image/jpeg", "size": 6 * 1024 * 1024},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_avatar_upload_zero_size_rejected(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Size of zero returns 422."""
    resp = await async_client.post(
        "/api/v1/users/me/avatar",
        json={"mime_type": "image/jpeg", "size": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_avatar_upload_creates_pending_record(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """A media record is created in PENDING state with an avatars/ storage key."""
    from uuid import UUID

    data = await _request_avatar_upload(async_client, auth_headers)
    media_id = UUID(data["media_id"])

    media = await db_session.get(Media, media_id)
    assert media is not None
    assert media.upload_status == MediaUploadStatus.PENDING
    assert media.storage_key.startswith("avatars/")
    assert media.processing_status is None


@pytest.mark.asyncio
async def test_avatar_upload_png_uses_correct_extension(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """PNG MIME type generates a .png storage key."""
    from uuid import UUID

    data = await _request_avatar_upload(
        async_client, auth_headers, mime_type="image/png"
    )
    media_id = UUID(data["media_id"])

    media = await db_session.get(Media, media_id)
    assert media is not None
    assert media.storage_key.endswith(".png")


# ===========================================================================
# POST /users/me/avatar/confirm
# ===========================================================================


@pytest.mark.asyncio
async def test_avatar_confirm_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    arq_pool: FakeArqPool,
    db_session: AsyncSession,
) -> None:
    """Full happy path: upload → PUT → confirm sets avatar_media_id."""
    from uuid import UUID

    upload_data = await _request_avatar_upload(async_client, auth_headers)
    storage_key = upload_data["upload_url"].removeprefix("http://fake-storage/put/")
    await _simulate_put(storage, storage_key)

    resp = await async_client.post(
        "/api/v1/users/me/avatar/confirm",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.json()
    body = resp.json()

    # avatar_url is None in the response because processing is still PENDING
    # (worker not yet run) — avatar_url is only populated when COMPLETED.
    assert body["avatar_url"] is None

    # But the DB record should have avatar_media_id set and processing enqueued.
    media_id = UUID(upload_data["media_id"])
    media = await db_session.get(Media, media_id)
    assert media is not None
    assert media.upload_status == MediaUploadStatus.UPLOADED
    assert media.processing_status == MediaProcessingStatus.PENDING

    assert len(arq_pool.enqueued) == 1
    assert arq_pool.enqueued[0][0] == "process_media"


@pytest.mark.asyncio
async def test_avatar_confirm_no_pending_upload(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Confirm with no pending upload returns 404."""
    resp = await async_client.post(
        "/api/v1/users/me/avatar/confirm",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_avatar_confirm_object_not_in_storage(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Confirm before putting the file returns 422."""
    await _request_avatar_upload(async_client, auth_headers)

    resp = await async_client.post(
        "/api/v1/users/me/avatar/confirm",
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_avatar_confirm_expired_ttl(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    """Confirm after TTL expiry returns 410 Gone."""
    from uuid import UUID

    upload_data = await _request_avatar_upload(async_client, auth_headers)
    storage_key = upload_data["upload_url"].removeprefix("http://fake-storage/put/")
    await _simulate_put(storage, storage_key)

    # Manually expire the TTL.
    media = await db_session.get(Media, UUID(upload_data["media_id"]))
    assert media is not None
    media.upload_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    resp = await async_client.post(
        "/api/v1/users/me/avatar/confirm",
        headers=auth_headers,
    )
    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_avatar_confirm_no_auth(async_client: AsyncClient) -> None:
    """Unauthenticated confirm returns 401."""
    resp = await async_client.post("/api/v1/users/me/avatar/confirm")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_avatar_confirm_replaces_old_avatar_and_deletes_storage(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    arq_pool: FakeArqPool,
    db_session: AsyncSession,
) -> None:
    """Confirming a new avatar cleans up the old avatar's S3 files and DB record."""
    from uuid import UUID

    # 1. Upload and confirm the first avatar
    data1 = await _request_avatar_upload(async_client, auth_headers)
    key1 = data1["upload_url"].removeprefix("http://fake-storage/put/")
    await _simulate_put(storage, key1)
    await async_client.post("/api/v1/users/me/avatar/confirm", headers=auth_headers)

    # Verify first avatar is in DB and storage
    media_id1 = UUID(data1["media_id"])
    assert await db_session.get(Media, media_id1) is not None
    assert await storage.object_exists(key1)

    # 2. Upload and confirm a second avatar
    data2 = await _request_avatar_upload(async_client, auth_headers)
    key2 = data2["upload_url"].removeprefix("http://fake-storage/put/")
    await _simulate_put(storage, key2)
    await async_client.post("/api/v1/users/me/avatar/confirm", headers=auth_headers)

    # Verify first avatar is now deleted from DB and storage
    assert await db_session.get(Media, media_id1) is None
    assert not await storage.object_exists(key1)

    # Verify second avatar exists and is set
    media_id2 = UUID(data2["media_id"])
    assert await db_session.get(Media, media_id2) is not None
    assert await storage.object_exists(key2)


# ===========================================================================
# DELETE /users/me/avatar
# ===========================================================================


@pytest.mark.asyncio
async def test_avatar_remove_clears_reference(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    arq_pool: FakeArqPool,
    db_session: AsyncSession,
) -> None:
    """DELETE /users/me/avatar clears avatar_media_id and deletes the media file."""
    from uuid import UUID

    upload_data = await _request_avatar_upload(async_client, auth_headers)
    storage_key = upload_data["upload_url"].removeprefix("http://fake-storage/put/")
    await _simulate_put(storage, storage_key)
    await async_client.post("/api/v1/users/me/avatar/confirm", headers=auth_headers)

    # Verify object exists before delete.
    assert await storage.object_exists(storage_key)

    resp = await async_client.delete("/api/v1/users/me/avatar", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["avatar_url"] is None

    # Media record is deleted.
    media = await db_session.get(Media, UUID(upload_data["media_id"]))
    assert media is None

    # Storage object is also deleted.
    assert not await storage.object_exists(storage_key)


@pytest.mark.asyncio
async def test_avatar_remove_no_auth(async_client: AsyncClient) -> None:
    """Unauthenticated delete returns 401."""
    resp = await async_client.delete("/api/v1/users/me/avatar")
    assert resp.status_code == 401
