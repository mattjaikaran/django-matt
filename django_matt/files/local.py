"""
Local filesystem storage backend.

Provides file storage on the local filesystem.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Union

from django.core.exceptions import ImproperlyConfigured

import aiofiles
import aiofiles.os

from .storage import (
    BaseStorage,
    FileExistsError,
    FileInfo,
    FileNotFoundError,
    PresignedUrl,
)
from .utils import generate_unique_filename, get_content_type, sanitize_filename

if TYPE_CHECKING:
    from .upload import UploadedFile


class LocalStorage(BaseStorage):
    """
    Local filesystem storage backend.

    Stores files on the local filesystem with configurable base path
    and URL prefix.

    Usage:
        storage = LocalStorage(
            base_path="/var/uploads",
            base_url="/media",
        )

        # Save a file
        key = await storage.save(uploaded_file, folder="images")

        # Get URL
        url = storage.url(key)  # /media/images/filename.jpg

        # Read file
        content = await storage.get(key)

    Note:
        Pre-signed URLs are simulated using signed tokens.
        For production, consider using a proper CDN or S3-compatible storage.
    """

    def __init__(
        self,
        base_path: str,
        base_url: str = "/media",
        create_directories: bool = True,
        secret_key: str = None,
    ):
        """
        Initialize local storage.

        Args:
            base_path: Absolute path to storage directory
            base_url: URL prefix for serving files
            create_directories: Whether to create directories on save
            secret_key: Secret for signing URLs (uses Django secret if not provided)
        """
        self.base_path = Path(base_path).resolve()
        self.base_url = base_url.rstrip("/")
        self.create_directories = create_directories
        self._secret_key = secret_key

    @property
    def secret_key(self) -> str:
        """Get the secret key for signing URLs."""
        if self._secret_key:
            return self._secret_key

        try:
            from django.conf import settings

            key = getattr(settings, "SECRET_KEY", None)
            if not key:
                raise ImproperlyConfigured(
                    "django.conf.settings.SECRET_KEY is not set. "
                    "LocalStorage requires SECRET_KEY for signing URLs."
                )
            return key
        except ImportError:
            raise ImproperlyConfigured(
                "Django settings are not available. "
                "Either pass secret_key to LocalStorage or configure Django settings."
            )

    def _get_full_path(self, key: str) -> Path:
        """Get the full filesystem path for a key, preventing directory traversal."""
        # Sanitize key to prevent directory traversal
        safe_key = key.lstrip("/")
        full_path = (self.base_path / safe_key).resolve()

        # Verify the resolved path is under base_path
        try:
            full_path.relative_to(self.base_path)
        except ValueError:
            raise ValueError(
                f"Path traversal detected: resolved path {full_path} "
                f"is outside base directory {self.base_path}"
            )

        return full_path

    def _get_key_from_path(self, path: Path) -> str:
        """Get the storage key from a filesystem path."""
        return str(path.relative_to(self.base_path))

    async def save(
        self,
        file: Union[UploadedFile, BinaryIO, bytes],
        key: str = None,
        folder: str = None,
        content_type: str = None,
        metadata: dict = None,
        overwrite: bool = True,
    ) -> str:
        """Save a file to local storage."""
        # Determine filename and key
        if key is None:
            if hasattr(file, "filename"):
                filename = sanitize_filename(file.filename)
            else:
                filename = generate_unique_filename(extension="bin")

            filename = generate_unique_filename(filename)
            key = filename

        if folder:
            key = f"{folder.strip('/')}/{key}"

        full_path = self._get_full_path(key)

        # Check if file exists
        if not overwrite and full_path.exists():
            raise FileExistsError(key)

        # Create directories if needed
        if self.create_directories:
            await aiofiles.os.makedirs(full_path.parent, exist_ok=True)

        # Get content
        if isinstance(file, bytes):
            content = file
        elif hasattr(file, "read"):
            if hasattr(file, "seek"):
                file.seek(0)
            content = file.read()
            if hasattr(content, "__await__"):
                content = await content
        else:
            raise ValueError(f"Unsupported file type: {type(file)}")

        # Write file
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(content)

        # Store metadata if provided
        if metadata:
            meta_path = full_path.with_suffix(full_path.suffix + ".meta")
            import json

            async with aiofiles.open(meta_path, "w") as f:
                await f.write(json.dumps(metadata))

        return key

    async def get(self, key: str) -> bytes:
        """Get a file's contents."""
        full_path = self._get_full_path(key)

        if not full_path.exists():
            raise FileNotFoundError(key)

        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def get_stream(self, key: str, chunk_size: int = 8192) -> Iterator[bytes]:
        """Get a file's contents as a stream."""
        full_path = self._get_full_path(key)

        if not full_path.exists():
            raise FileNotFoundError(key)

        async with aiofiles.open(full_path, "rb") as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def delete(self, key: str) -> None:
        """Delete a file from storage."""
        full_path = self._get_full_path(key)

        if not full_path.exists():
            raise FileNotFoundError(key)

        await aiofiles.os.remove(full_path)

        # Also delete metadata file if exists
        meta_path = full_path.with_suffix(full_path.suffix + ".meta")
        if meta_path.exists():
            await aiofiles.os.remove(meta_path)

    async def exists(self, key: str) -> bool:
        """Check if a file exists."""
        full_path = self._get_full_path(key)
        return full_path.exists()

    async def info(self, key: str) -> FileInfo:
        """Get information about a file."""
        full_path = self._get_full_path(key)

        if not full_path.exists():
            raise FileNotFoundError(key)

        stat = full_path.stat()

        # Load metadata if exists
        metadata = {}
        meta_path = full_path.with_suffix(full_path.suffix + ".meta")
        if meta_path.exists():
            import json

            async with aiofiles.open(meta_path) as f:
                metadata = json.loads(await f.read())

        # Calculate etag
        async with aiofiles.open(full_path, "rb") as f:
            content = await f.read()
            etag = hashlib.md5(content).hexdigest()

        return FileInfo(
            key=key,
            size=stat.st_size,
            content_type=get_content_type(full_path.name),
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            etag=etag,
            metadata=metadata,
        )

    async def list(
        self,
        prefix: str = "",
        limit: int = None,
        cursor: str = None,
    ) -> tuple[list[FileInfo], str | None]:
        """List files in storage."""
        search_path = self.base_path
        if prefix:
            search_path = self._get_full_path(prefix)

        if not search_path.exists():
            return [], None

        files = []
        count = 0
        skip_until = cursor

        for root, _, filenames in os.walk(search_path):
            for filename in sorted(filenames):
                # Skip metadata files
                if filename.endswith(".meta"):
                    continue

                file_path = Path(root) / filename
                key = self._get_key_from_path(file_path)

                # Handle cursor-based pagination
                if skip_until:
                    if key == skip_until:
                        skip_until = None
                    continue

                # Get file info
                try:
                    info = await self.info(key)
                    files.append(info)
                    count += 1

                    if limit and count >= limit:
                        return files, key
                except Exception:
                    continue

        return files, None

    def url(self, key: str) -> str:
        """Get the public URL for a file."""
        return f"{self.base_url}/{key}"

    async def presigned_upload_url(
        self,
        key: str,
        expires: int = 3600,
        content_type: str = None,
        content_length_range: tuple[int, int] = None,
        metadata: dict = None,
    ) -> PresignedUrl:
        """
        Generate a pre-signed URL for upload.

        Note: Local storage doesn't support true pre-signed uploads.
        This returns a signed token that can be verified server-side.
        """
        import base64
        import hmac
        import json

        expires_at = datetime.now(UTC) + timedelta(seconds=expires)

        # Create signature payload
        payload = {
            "key": key,
            "expires": expires_at.isoformat(),
            "content_type": content_type,
            "content_length_range": content_length_range,
            "metadata": metadata,
        }

        payload_json = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            self.secret_key.encode(),
            payload_json.encode(),
            hashlib.sha256,
        ).hexdigest()

        token = base64.urlsafe_b64encode(payload_json.encode()).decode()

        # Return URL with signature
        upload_url = f"{self.base_url}/upload?token={token}&signature={signature}"

        return PresignedUrl(
            url=upload_url,
            expires_at=expires_at,
            method="POST",
            headers={"Content-Type": content_type} if content_type else {},
            fields={"key": key},
        )

    async def presigned_download_url(
        self,
        key: str,
        expires: int = 3600,
        filename: str = None,
    ) -> PresignedUrl:
        """
        Generate a pre-signed URL for download.

        Note: Local storage uses signed tokens for access control.
        You'll need to implement a view to verify and serve the file.
        """
        import base64
        import hmac
        import json

        expires_at = datetime.now(UTC) + timedelta(seconds=expires)

        # Create signature payload
        payload = {
            "key": key,
            "expires": expires_at.isoformat(),
            "filename": filename,
        }

        payload_json = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            self.secret_key.encode(),
            payload_json.encode(),
            hashlib.sha256,
        ).hexdigest()

        token = base64.urlsafe_b64encode(payload_json.encode()).decode()

        # Return URL with signature
        download_url = f"{self.base_url}/{key}?token={token}&signature={signature}"

        headers = {}
        if filename:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        return PresignedUrl(
            url=download_url,
            expires_at=expires_at,
            method="GET",
            headers=headers,
        )

    def verify_signature(self, token: str, signature: str) -> dict | None:
        """
        Verify a pre-signed URL signature.

        Args:
            token: The base64-encoded payload
            signature: The HMAC signature

        Returns:
            The payload dict if valid and not expired, None otherwise
        """
        import base64
        import hmac
        import json

        try:
            payload_json = base64.urlsafe_b64decode(token).decode()
            expected_signature = hmac.new(
                self.secret_key.encode(),
                payload_json.encode(),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                return None

            payload = json.loads(payload_json)

            # Check expiration
            expires = datetime.fromisoformat(payload["expires"])
            if datetime.now(UTC) > expires:
                return None

            return payload
        except Exception:
            return None
