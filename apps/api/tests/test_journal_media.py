"""Integration tests for the journal entry media attachment endpoints and stale media prevention.

Exposed through entries endpoints:
  POST   /api/v1/entries/{id}/media/upload
  POST   /api/v1/entries/{id}/media/{media_id}/confirm
  DELETE /api/v1/entries/{id}/media/{media_id}
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool
from app.db.enums import MediaUploadStatus
from app.db.models import Media
from app.main import app
from app.storage.base import StorageBackend
from app.storage.factory import get_storage


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


@pytest_asyncio.fixture
async def storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest_asyncio.fixture
async def arq_pool() -> FakeArqPool:
    return FakeArqPool()


@pytest_asyncio.fixture
async def auth_headers(
    async_client: AsyncClient,
) -> dict[str, str]:
    """Register a user and return session cookie headers."""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"journal-media-test-{uuid.uuid4().hex[:8]}@example.com",
            "password": "Test1234!secure",
            "display_name": "Journal Media Tester",
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
    async def _get_storage() -> StorageBackend:
        return storage

    async def _get_arq_pool() -> FakeArqPool:
        return arq_pool

    app.dependency_overrides[get_storage] = _get_storage
    app.dependency_overrides[get_arq_pool] = _get_arq_pool
    yield
    app.dependency_overrides.pop(get_storage, None)
    app.dependency_overrides.pop(get_arq_pool, None)


async def _create_entry(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    resp = await client.post(
        "/api/v1/entries",
        json={
            "date": "2026-07-04",
            "title": "Test Entry for Media",
            "content": {
                "type": "doc",
                "content": [{"type": "paragraph", "text": "Hello world"}],
            },
            "is_favorite": False,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()


@pytest.mark.asyncio
async def test_journal_entry_media_upload_flow(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    arq_pool: FakeArqPool,
    db_session: AsyncSession,
) -> None:
    # 1. Create a journal entry
    entry = await _create_entry(async_client, auth_headers)
    entry_id = entry["id"]

    # 2. Request media upload presigned URL
    upload_req = await async_client.post(
        f"/api/v1/entries/{entry_id}/media/upload",
        json={
            "mime_type": "image/jpeg",
            "size": 50000,
            "media_type": "image",
            "filename": "test.jpg",
        },
        headers=auth_headers,
    )
    assert upload_req.status_code == 201, upload_req.json()
    upload_data = upload_req.json()
    assert "media_id" in upload_data
    assert "upload_url" in upload_data
    media_id = upload_data["media_id"]
    upload_url = upload_data["upload_url"]

    # Storage key has the nested journal entries pattern
    assert "/put/entries/" in upload_url

    # Retrieve media record to find storage key
    db_media = await db_session.get(Media, uuid.UUID(media_id))
    assert db_media is not None
    assert db_media.upload_status == MediaUploadStatus.PENDING

    # 3. Simulate uploading bytes to storage
    await storage.upload(db_media.storage_key, b"fake-jpeg-bytes", "image/jpeg")

    # 4. Confirm the upload
    confirm_resp = await async_client.post(
        f"/api/v1/entries/{entry_id}/media/{media_id}/confirm",
        headers=auth_headers,
    )
    assert confirm_resp.status_code == 200, confirm_resp.json()
    confirm_data = confirm_resp.json()

    # The entry now includes the media
    assert len(confirm_data["media"]) == 1
    media_response = confirm_data["media"][0]
    assert media_response["id"] == media_id
    assert media_response["upload_status"] == "uploaded"

    # Enqueued media processing job
    media_jobs = [job for job in arq_pool.enqueued if job[0] == "process_media"]
    assert len(media_jobs) == 1
    assert media_jobs[0][1] == (media_id,)

    # 5. Fetch entry and verify media ordering/urls
    get_resp = await async_client.get(
        f"/api/v1/entries/{entry_id}", headers=auth_headers
    )
    assert get_resp.status_code == 200, get_resp.json()
    get_data = get_resp.json()
    assert len(get_data["media"]) == 1
    assert get_data["media"][0]["id"] == media_id

    # 6. Detach/delete media and check storage cleanup (no stale media)
    delete_media_resp = await async_client.delete(
        f"/api/v1/entries/{entry_id}/media/{media_id}",
        headers=auth_headers,
    )
    assert delete_media_resp.status_code == 204

    # Verify media record deleted from DB
    db_session.expire_all()  # reset session cache
    db_media_deleted = await db_session.get(Media, uuid.UUID(media_id))
    assert db_media_deleted is None

    # Verify physical file deleted from storage
    exists = await storage.object_exists(db_media.storage_key)
    assert exists is False


@pytest.mark.asyncio
async def test_journal_entry_deletion_cleans_media(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    storage: InMemoryStorage,
    db_session: AsyncSession,
) -> None:
    # 1. Create a journal entry
    entry = await _create_entry(async_client, auth_headers)
    entry_id = entry["id"]

    # 2. Upload and confirm a media asset
    upload_req = await async_client.post(
        f"/api/v1/entries/{entry_id}/media/upload",
        json={
            "mime_type": "image/jpeg",
            "size": 10000,
            "media_type": "image",
            "filename": "test.jpg",
        },
        headers=auth_headers,
    )
    media_id = upload_req.json()["media_id"]
    db_media = await db_session.get(Media, uuid.UUID(media_id))
    assert db_media is not None
    await storage.upload(db_media.storage_key, b"bytes", "image/jpeg")

    confirm_resp = await async_client.post(
        f"/api/v1/entries/{entry_id}/media/{media_id}/confirm",
        headers=auth_headers,
    )
    assert confirm_resp.status_code == 200

    # Verify it exists in storage
    assert await storage.object_exists(db_media.storage_key) is True

    # 3. Soft-delete the journal entry
    delete_resp = await async_client.delete(
        f"/api/v1/entries/{entry_id}", headers=auth_headers
    )
    assert delete_resp.status_code == 204

    # Verify all media records and files are deleted to prevent stale media
    db_media_deleted = await db_session.get(Media, uuid.UUID(media_id))
    assert db_media_deleted is None

    assert await storage.object_exists(db_media.storage_key) is False
