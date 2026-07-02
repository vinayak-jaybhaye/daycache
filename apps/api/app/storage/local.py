"""Local filesystem storage backend.

Stores files under ``settings.STORAGE_LOCAL_ROOT``.
Suitable for development and single-server deployments.
Switch to S3 for multi-instance or production use.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """Stores objects on the local filesystem."""

    def __init__(self) -> None:
        self._root = Path(get_settings().STORAGE_LOCAL_ROOT)
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        path = (self._root / key).resolve()
        # Guard against path traversal attacks.
        if not path.is_relative_to(self._root.resolve()):
            msg = f"Invalid storage key: {key!r}"
            raise ValueError(msg)
        return path

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return key

    async def download(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key!r}")
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key!r}")
        await asyncio.to_thread(path.unlink)

    async def get_url(self, key: str, *, expires_in: int = 3600) -> str:
        # Local storage serves files via the API's /media endpoint (future).
        # For now return a placeholder path-based URL.
        return f"/storage/{key}"
