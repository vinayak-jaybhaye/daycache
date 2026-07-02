"""S3-compatible storage backend stub.

Supports AWS S3, Cloudflare R2, and MinIO via the same interface.
Implementation is intentionally left as a stub until the media feature
is implemented. The interface contract is established here.

To implement, install ``aioboto3`` and wire the credentials from
``settings.S3_*`` fields.
"""

from __future__ import annotations

from app.storage.base import StorageBackend


class S3StorageBackend(StorageBackend):
    """S3-compatible object storage (AWS S3 / Cloudflare R2 / MinIO).

    Not yet implemented. Raises ``NotImplementedError`` on all methods.
    """

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        raise NotImplementedError("S3StorageBackend.upload is not yet implemented")

    async def download(self, key: str) -> bytes:
        raise NotImplementedError("S3StorageBackend.download is not yet implemented")

    async def delete(self, key: str) -> None:
        raise NotImplementedError("S3StorageBackend.delete is not yet implemented")

    async def get_url(self, key: str, *, expires_in: int = 3600) -> str:
        raise NotImplementedError("S3StorageBackend.get_url is not yet implemented")
