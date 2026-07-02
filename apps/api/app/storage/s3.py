"""S3-compatible storage backend.

Supports AWS S3, Cloudflare R2, and MinIO via the same interface.
Requires ``aioboto3`` — install via: ``uv add aioboto3``.

Configuration (from ``app.core.config.Settings``):
    S3_BUCKET           Target bucket name.
    S3_REGION           AWS/R2 region.
    S3_ACCESS_KEY_ID    Access key.
    S3_SECRET_ACCESS_KEY Secret key.
    S3_ENDPOINT_URL     Custom endpoint for R2/MinIO (leave empty for AWS).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.storage.base import StorageBackend

if TYPE_CHECKING:
    pass


class S3StorageBackend(StorageBackend):
    """S3-compatible object storage (AWS S3 / Cloudflare R2 / MinIO)."""

    def __init__(self) -> None:
        try:
            import aioboto3  # type: ignore[import-untyped]
        except ImportError as e:
            msg = (
                "aioboto3 is required for S3 storage. Install it with: uv add aioboto3"
            )
            raise ImportError(msg) from e

        settings = get_settings()
        self._bucket = settings.S3_BUCKET
        self._session = aioboto3.Session(
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY.get_secret_value(),
            region_name=settings.S3_REGION or None,
        )
        self._endpoint_url: str | None = settings.S3_ENDPOINT_URL or None

    def _client(self) -> Any:
        """Return an async S3 client context manager."""
        kwargs: dict[str, Any] = {}
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        return self._session.client("s3", **kwargs)

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Upload raw bytes to S3.

        Args:
            key: S3 object key.
            data: Raw bytes to upload.
            content_type: MIME type of the object.

        Returns:
            The object key.
        """
        async with self._client() as s3:
            await s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        return key

    async def download(self, key: str) -> bytes:
        """Download raw bytes from S3.

        Args:
            key: S3 object key.

        Returns:
            Raw bytes of the object.

        Raises:
            FileNotFoundError: If the object does not exist.
        """
        from botocore.exceptions import ClientError  # type: ignore[import-untyped]

        async with self._client() as s3:
            try:
                response = await s3.get_object(Bucket=self._bucket, Key=key)
                return await response["Body"].read()
            except ClientError as e:
                if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                    raise FileNotFoundError(f"Object not found: {key!r}") from e
                raise

    async def delete(self, key: str) -> None:
        """Delete an object from S3.

        Args:
            key: S3 object key.

        Raises:
            FileNotFoundError: If the object does not exist.
        """
        from botocore.exceptions import ClientError  # type: ignore[import-untyped]

        async with self._client() as s3:
            try:
                await s3.head_object(Bucket=self._bucket, Key=key)
            except ClientError as e:
                if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                    raise FileNotFoundError(f"Object not found: {key!r}") from e
                raise
            await s3.delete_object(Bucket=self._bucket, Key=key)

    async def get_url(self, key: str, *, expires_in: int = 3600) -> str:
        """Generate a presigned GET URL for an S3 object.

        Args:
            key: S3 object key.
            expires_in: URL lifetime in seconds.

        Returns:
            A presigned GET URL string.
        """
        async with self._client() as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )

    async def generate_presigned_put(
        self,
        key: str,
        mime_type: str,
        *,
        expires_in: int = 300,
    ) -> str:
        """Generate a presigned PUT URL so the client uploads directly to S3.

        The client must set ``Content-Type: <mime_type>`` on the PUT request.

        Args:
            key: S3 object key the client will write to.
            mime_type: Expected MIME type — enforced by the presigned URL.
            expires_in: URL lifetime in seconds.

        Returns:
            A presigned PUT URL string.
        """
        async with self._client() as s3:
            return await s3.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "ContentType": mime_type,
                },
                ExpiresIn=expires_in,
            )

    async def object_exists(self, key: str) -> bool:
        """Return True if an object exists at ``key``.

        Uses a HEAD request — does not download the object body.

        Args:
            key: S3 object key.

        Returns:
            True if the object exists, False otherwise.
        """
        from botocore.exceptions import ClientError  # type: ignore[import-untyped]

        async with self._client() as s3:
            try:
                await s3.head_object(Bucket=self._bucket, Key=key)
                return True
            except ClientError as e:
                if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                    return False
                raise
