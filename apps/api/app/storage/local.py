"""Local filesystem storage backend.

Stores files under ``settings.STORAGE_LOCAL_ROOT``.
Suitable for development and single-server deployments.
Switch to S3 for multi-instance or production use.

Presigned PUT simulation
------------------------
S3 lets clients upload directly via a presigned URL. To replicate this locally
without proxying bytes through the main API, we issue a short-lived HMAC-signed
token that grants write access to a specific key. The ``LocalUploadRouter``
(mounted at ``/internal``) validates the token and writes the file to disk.

Token format: ``<base64url(key)>.<expires_at_unix>.<hmac_sha256>``
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.storage.base import StorageBackend

if TYPE_CHECKING:
    pass


class LocalStorageBackend(StorageBackend):
    """Stores objects on the local filesystem."""

    def __init__(self) -> None:
        settings = get_settings()
        self._root = Path(settings.STORAGE_LOCAL_ROOT)
        self._root.mkdir(parents=True, exist_ok=True)
        self._secret = settings.SECRET_KEY.get_secret_value().encode()

    def _resolve(self, key: str) -> Path:
        path = (self._root / key).resolve()
        # Guard against path traversal attacks.
        if not path.is_relative_to(self._root.resolve()):
            msg = f"Invalid storage key: {key!r}"
            raise ValueError(msg)
        return path

    # ------------------------------------------------------------------
    # Internal token helpers
    # ------------------------------------------------------------------

    def _sign_token(self, key: str, expires_at: int) -> str:
        """Return a signed upload token for a given key and expiry timestamp."""
        encoded_key = urlsafe_b64encode(key.encode()).decode()
        payload = f"{encoded_key}.{expires_at}"
        sig = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{sig}"

    def _verify_token(self, token: str, key: str) -> bool:
        """Verify a signed upload token. Returns False if invalid or expired."""
        try:
            parts = token.split(".", 2)
            if len(parts) != 3:
                return False
            encoded_key, expires_at_str, sig = parts
            decoded_key = urlsafe_b64decode(encoded_key.encode()).decode()
            if decoded_key != key:
                return False
            expires_at = int(expires_at_str)
            if time.time() > expires_at:
                return False
            payload = f"{encoded_key}.{expires_at_str}"
            expected = hmac.new(
                self._secret, payload.encode(), hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, sig)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # StorageBackend interface
    # ------------------------------------------------------------------

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
        """Return a signed local read URL served by the internal router."""
        expires_at = int(time.time()) + expires_in
        token = self._sign_token(key, expires_at)
        return f"/internal/storage/download/{key}?token={token}"

    async def generate_presigned_put(
        self,
        key: str,
        mime_type: str,
        *,
        expires_in: int = 300,
    ) -> str:
        """Return a signed local upload URL the client can PUT bytes to."""
        expires_at = int(time.time()) + expires_in
        token = self._sign_token(key, expires_at)
        return f"/internal/storage/upload/{key}?token={token}"

    async def object_exists(self, key: str) -> bool:
        path = self._resolve(key)
        return await asyncio.to_thread(path.exists)

    def make_internal_router(self) -> APIRouter:
        """Return a FastAPI router for local upload/download endpoints.

        Mount this at ``/internal`` — outside of ``/api/v1``. Only active when
        ``STORAGE_BACKEND=local``. Not accessible in production.
        """
        router = APIRouter()
        backend = self

        from fastapi import Depends
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.api.deps import get_db

        @router.put(
            "/storage/upload/{key:path}",
            status_code=status.HTTP_204_NO_CONTENT,
            include_in_schema=False,
        )
        async def local_upload(  # type: ignore[reportUnusedFunction]
            key: str,
            request: Request,
            token: str,
            content_type: str = Header(default="application/octet-stream"),
            db: AsyncSession = Depends(get_db),
        ) -> None:
            """Accept a raw PUT upload for local storage (dev only)."""
            if not backend._verify_token(token, key):
                raise HTTPException(
                    status_code=401, detail="Invalid or expired upload token."
                )

            # Prevent overwriting once upload is already confirmed/completed
            from app.db.enums import MediaUploadStatus
            from app.db.repositories.media import MediaRepository

            repo = MediaRepository(db)
            media = await repo.get_by_storage_key(key)
            if media and media.upload_status == MediaUploadStatus.UPLOADED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Upload has already been confirmed. Overwriting is not permitted.",
                )

            data = await request.body()
            await backend.upload(key, data, content_type)

        @router.get(
            "/storage/download/{key:path}",
            include_in_schema=False,
        )
        async def local_download(key: str, token: str) -> Response:  # type: ignore[reportUnusedFunction]
            """Serve a stored file for local storage (dev only)."""
            if not backend._verify_token(token, key):
                raise HTTPException(
                    status_code=401, detail="Invalid or expired download token."
                )
            try:
                data = await backend.download(key)
                return Response(content=data, media_type="application/octet-stream")
            except FileNotFoundError:
                raise HTTPException(
                    status_code=404, detail="Object not found."
                ) from None

        return router
