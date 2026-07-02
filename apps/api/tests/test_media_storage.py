# pyright: reportPrivateUsage=false

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.storage.local import LocalStorageBackend

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def tmp_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[LocalStorageBackend, None]:
    """Return a LocalStorageBackend rooted in a temporary directory."""
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path))
    monkeypatch.setenv("SECRET_KEY", "test-storage-secret-that-is-long-enough!")
    # Invalidate the lru_cache so the patched env is picked up.
    from app.core.config import get_settings

    get_settings.cache_clear()
    backend = LocalStorageBackend()
    yield backend
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def internal_client(
    tmp_storage: LocalStorageBackend,
) -> AsyncGenerator[AsyncClient, None]:
    """Async client wired to a minimal FastAPI app with just the internal router."""
    from fastapi import FastAPI

    mini_app = FastAPI()
    mini_app.include_router(tmp_storage.make_internal_router(), prefix="/internal")
    async with AsyncClient(
        transport=ASGITransport(app=mini_app), base_url="http://test"
    ) as client:
        yield client


# ===========================================================================
# Core storage operations
# ===========================================================================


@pytest.mark.asyncio
async def test_upload_and_download(tmp_storage: LocalStorageBackend) -> None:
    """Uploaded bytes are retrievable via download."""
    data = b"hello world"
    await tmp_storage.upload("test/file.txt", data, "text/plain")
    result = await tmp_storage.download("test/file.txt")
    assert result == data


@pytest.mark.asyncio
async def test_download_missing_raises(tmp_storage: LocalStorageBackend) -> None:
    """Downloading a missing key raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        await tmp_storage.download("does/not/exist.txt")


@pytest.mark.asyncio
async def test_delete_removes_file(tmp_storage: LocalStorageBackend) -> None:
    """Delete removes the file from disk."""
    await tmp_storage.upload("to_delete.bin", b"bye", "application/octet-stream")
    await tmp_storage.delete("to_delete.bin")
    with pytest.raises(FileNotFoundError):
        await tmp_storage.download("to_delete.bin")


@pytest.mark.asyncio
async def test_delete_missing_raises(tmp_storage: LocalStorageBackend) -> None:
    """Deleting a missing key raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        await tmp_storage.delete("ghost.bin")


@pytest.mark.asyncio
async def test_object_exists_true(tmp_storage: LocalStorageBackend) -> None:
    """object_exists returns True for an uploaded file."""
    await tmp_storage.upload("exists.jpg", b"\xff\xd8\xff", "image/jpeg")
    assert await tmp_storage.object_exists("exists.jpg") is True


@pytest.mark.asyncio
async def test_object_exists_false(tmp_storage: LocalStorageBackend) -> None:
    """object_exists returns False for a missing key."""
    assert await tmp_storage.object_exists("missing.jpg") is False


# ===========================================================================
# Presigned PUT URL
# ===========================================================================


@pytest.mark.asyncio
async def test_presigned_put_url_format(tmp_storage: LocalStorageBackend) -> None:
    """generate_presigned_put returns a URL pointing to the internal endpoint."""
    url = await tmp_storage.generate_presigned_put(
        "media/abc.jpg", "image/jpeg", expires_in=300
    )
    assert "/internal/storage/upload/media/abc.jpg" in url
    assert "token=" in url


@pytest.mark.asyncio
async def test_get_url_format(tmp_storage: LocalStorageBackend) -> None:
    """get_url returns a URL pointing to the internal download endpoint."""
    url = await tmp_storage.get_url("media/abc.jpg", expires_in=3600)
    assert "/internal/storage/download/media/abc.jpg" in url
    assert "token=" in url


# ===========================================================================
# Token verification
# ===========================================================================


def test_token_verify_valid(tmp_storage: LocalStorageBackend) -> None:
    """A freshly generated token verifies correctly."""
    expires_at = int(time.time()) + 300
    token = tmp_storage._sign_token("media/key.jpg", expires_at)
    assert tmp_storage._verify_token(token, "media/key.jpg") is True


def test_token_verify_expired(tmp_storage: LocalStorageBackend) -> None:
    """An expired token is rejected."""
    expires_at = int(time.time()) - 1  # Already expired.
    token = tmp_storage._sign_token("media/key.jpg", expires_at)
    assert tmp_storage._verify_token(token, "media/key.jpg") is False


def test_token_verify_wrong_key(tmp_storage: LocalStorageBackend) -> None:
    """A valid token for one key is rejected for a different key."""
    expires_at = int(time.time()) + 300
    token = tmp_storage._sign_token("media/correct.jpg", expires_at)
    assert tmp_storage._verify_token(token, "media/different.jpg") is False


def test_token_verify_tampered_sig(tmp_storage: LocalStorageBackend) -> None:
    """Tampering with the HMAC signature causes rejection."""
    expires_at = int(time.time()) + 300
    token = tmp_storage._sign_token("media/key.jpg", expires_at)
    # Flip the last character of the signature.
    parts = token.rsplit(".", 1)
    bad_token = parts[0] + "." + parts[1][:-1] + ("x" if parts[1][-1] != "x" else "y")
    assert tmp_storage._verify_token(bad_token, "media/key.jpg") is False


def test_token_verify_malformed(tmp_storage: LocalStorageBackend) -> None:
    """A completely malformed token is rejected without raising."""
    assert tmp_storage._verify_token("not.a.valid.token.at.all", "any/key") is False
    assert tmp_storage._verify_token("", "any/key") is False


# ===========================================================================
# Path traversal protection
# ===========================================================================


@pytest.mark.asyncio
async def test_path_traversal_rejected(tmp_storage: LocalStorageBackend) -> None:
    """Keys containing path traversal sequences are rejected."""
    with pytest.raises(ValueError, match="Invalid storage key"):
        await tmp_storage.upload("../../etc/passwd", b"bad", "text/plain")


# ===========================================================================
# Internal router — PUT (upload)
# ===========================================================================


@pytest.mark.asyncio
async def test_internal_upload_endpoint_success(
    tmp_storage: LocalStorageBackend,
    internal_client: AsyncClient,
) -> None:
    """PUT to the internal upload endpoint with a valid token writes the file."""
    key = "media/test-upload.jpg"
    url = await tmp_storage.generate_presigned_put(key, "image/jpeg", expires_in=60)
    # Extract just the path+query from the full URL.
    path_and_query = url.replace("http://", "").split("/", 1)[1]
    # Prefix with / for httpx.
    endpoint = f"/{path_and_query}"

    data = b"\xff\xd8\xff" + b"\x00" * 20
    response = await internal_client.put(
        endpoint,
        content=data,
        headers={"Content-Type": "image/jpeg"},
    )
    assert response.status_code == 204
    assert await tmp_storage.object_exists(key)
    stored = await tmp_storage.download(key)
    assert stored == data


@pytest.mark.asyncio
async def test_internal_upload_invalid_token(
    internal_client: AsyncClient,
) -> None:
    """PUT with an invalid token returns 401."""
    response = await internal_client.put(
        "/internal/storage/upload/media/bad.jpg?token=invalid",
        content=b"data",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_internal_upload_expired_token(
    tmp_storage: LocalStorageBackend,
    internal_client: AsyncClient,
) -> None:
    """PUT with an expired token returns 401."""
    key = "media/expired.jpg"
    # Generate a token that expired 1 second ago.
    expires_at = int(time.time()) - 1
    token = tmp_storage._sign_token(key, expires_at)
    response = await internal_client.put(
        f"/internal/storage/upload/{key}?token={token}",
        content=b"data",
    )
    assert response.status_code == 401


# ===========================================================================
# Internal router — GET (download)
# ===========================================================================


@pytest.mark.asyncio
async def test_internal_download_endpoint_success(
    tmp_storage: LocalStorageBackend,
    internal_client: AsyncClient,
) -> None:
    """GET the internal download endpoint with a valid token returns the file."""
    key = "media/test-download.jpg"
    data = b"\xff\xd8\xff" + b"\x00" * 20
    await tmp_storage.upload(key, data, "image/jpeg")

    url = await tmp_storage.get_url(key, expires_in=60)
    path_and_query = url.replace("http://", "").split("/", 1)[1]
    endpoint = f"/{path_and_query}"

    response = await internal_client.get(endpoint)
    assert response.status_code == 200
    assert response.content == data


@pytest.mark.asyncio
async def test_internal_download_invalid_token(
    internal_client: AsyncClient,
) -> None:
    """GET with an invalid token returns 401."""
    response = await internal_client.get(
        "/internal/storage/download/media/file.jpg?token=bad"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_internal_download_missing_file(
    tmp_storage: LocalStorageBackend,
    internal_client: AsyncClient,
) -> None:
    """GET with a valid token but missing file returns 404."""
    key = "media/ghost.jpg"
    url = await tmp_storage.get_url(key, expires_in=60)
    path_and_query = url.replace("http://", "").split("/", 1)[1]
    endpoint = f"/{path_and_query}"

    response = await internal_client.get(endpoint)
    assert response.status_code == 404
