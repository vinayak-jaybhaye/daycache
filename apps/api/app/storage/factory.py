"""Storage backend factory.

Use ``get_storage()`` as a FastAPI dependency or call it directly.
The correct backend is selected from ``settings.STORAGE_BACKEND``.

Usage::

    from app.storage.factory import get_storage

    # As a FastAPI dependency:
    @router.post("/upload")
    async def upload(storage: StorageBackend = Depends(get_storage)):
        ...
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import StorageBackend
from app.storage.local import LocalStorageBackend
from app.storage.s3 import S3StorageBackend


@lru_cache
def get_storage() -> StorageBackend:
    """Return the configured storage backend singleton.

    Returns:
        A ``StorageBackend`` instance based on ``settings.STORAGE_BACKEND``.

    Raises:
        ValueError: If an unknown backend is configured.
    """
    backend = get_settings().STORAGE_BACKEND
    match backend:
        case "local":
            return LocalStorageBackend()
        case "s3":
            return S3StorageBackend()
        case _:
            msg = f"Unknown storage backend: {backend!r}"
            raise ValueError(msg)
