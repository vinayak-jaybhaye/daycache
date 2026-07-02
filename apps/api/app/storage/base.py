"""Abstract storage backend interface.

All storage implementations must satisfy this protocol.
Application code should never reference a concrete backend directly —
use ``storage.factory.get_storage()`` instead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Abstract base class for object storage backends.

    Implementations:
    - ``storage.local.LocalStorageBackend``
    - ``storage.s3.S3StorageBackend``
    """

    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Upload ``data`` and return the storage key.

        Args:
            key: Desired storage path / object key.
            data: Raw bytes to store.
            content_type: MIME type of the file.

        Returns:
            The final storage key (may differ from ``key`` if normalised).
        """

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Return the raw bytes stored at ``key``.

        Args:
            key: Storage path / object key.

        Raises:
            FileNotFoundError: If no object exists at ``key``.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete the object at ``key``.

        Args:
            key: Storage path / object key to remove.

        Raises:
            FileNotFoundError: If no object exists at ``key``.
        """

    @abstractmethod
    async def get_url(self, key: str, *, expires_in: int = 3600) -> str:
        """Return a URL for accessing the object.

        For local storage this is a file:// or served URL.
        For S3 this is a pre-signed URL.

        Args:
            key: Storage path / object key.
            expires_in: URL expiry in seconds (ignored for local).

        Returns:
            A URL string.
        """
