"""
Base storage backend interface.

Defines the abstract interface that all storage backends must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, BinaryIO, Union

if TYPE_CHECKING:
    from .upload import UploadedFile


class StorageError(Exception):
    """Base exception for storage errors."""

    def __init__(self, message: str, code: str = "storage_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class FileNotFoundError(StorageError):
    """Raised when a file is not found in storage."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"File not found: {key}", code="file_not_found")


class FileExistsError(StorageError):
    """Raised when trying to overwrite a file without permission."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"File already exists: {key}", code="file_exists")


class PermissionError(StorageError):
    """Raised when an operation is not permitted."""

    def __init__(self, message: str):
        super().__init__(message, code="permission_denied")


@dataclass
class FileInfo:
    """Information about a stored file."""

    key: str
    size: int
    content_type: str
    last_modified: datetime | None = None
    etag: str | None = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PresignedUrl:
    """A pre-signed URL for direct upload/download."""

    url: str
    expires_at: datetime
    method: str = "GET"
    headers: dict = None
    fields: dict = None  # For multipart form uploads

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.fields is None:
            self.fields = {}


class BaseStorage(ABC):
    """
    Abstract base class for storage backends.

    All storage backends must implement this interface.

    Example:
        class MyStorage(BaseStorage):
            async def save(self, file, key=None, folder=None, ...):
                ...

            async def get(self, key):
                ...

            # ... implement other methods
    """

    @abstractmethod
    async def save(
        self,
        file: Union[UploadedFile, BinaryIO, bytes],
        key: str = None,
        folder: str = None,
        content_type: str = None,
        metadata: dict = None,
        overwrite: bool = True,
    ) -> str:
        """
        Save a file to storage.

        Args:
            file: The file to save (UploadedFile, file-like object, or bytes)
            key: The storage key/path (auto-generated if not provided)
            folder: Optional folder/prefix to put the file in
            content_type: MIME type (detected if not provided)
            metadata: Optional metadata to store with the file
            overwrite: Whether to overwrite existing files

        Returns:
            The storage key where the file was saved

        Raises:
            FileExistsError: If file exists and overwrite=False
            StorageError: On other storage errors
        """

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """
        Get a file's contents.

        Args:
            key: The storage key/path

        Returns:
            File contents as bytes

        Raises:
            FileNotFoundError: If the file doesn't exist
        """

    @abstractmethod
    async def get_stream(self, key: str, chunk_size: int = 8192) -> Iterator[bytes]:
        """
        Get a file's contents as a stream.

        Args:
            key: The storage key/path
            chunk_size: Size of chunks to yield

        Yields:
            Chunks of file data

        Raises:
            FileNotFoundError: If the file doesn't exist
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """
        Delete a file from storage.

        Args:
            key: The storage key/path

        Raises:
            FileNotFoundError: If the file doesn't exist
        """

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            key: The storage key/path

        Returns:
            True if the file exists
        """

    @abstractmethod
    async def info(self, key: str) -> FileInfo:
        """
        Get information about a file.

        Args:
            key: The storage key/path

        Returns:
            FileInfo object with file details

        Raises:
            FileNotFoundError: If the file doesn't exist
        """

    @abstractmethod
    async def list(
        self,
        prefix: str = "",
        limit: int = None,
        cursor: str = None,
    ) -> tuple[list[FileInfo], str | None]:
        """
        List files in storage.

        Args:
            prefix: Filter to files starting with this prefix
            limit: Maximum number of files to return
            cursor: Pagination cursor from previous call

        Returns:
            Tuple of (list of FileInfo, next cursor or None)
        """

    @abstractmethod
    def url(self, key: str) -> str:
        """
        Get the public URL for a file.

        Args:
            key: The storage key/path

        Returns:
            Public URL string

        Note:
            This may not work for private storage backends.
            Use presigned_download_url() for private files.
        """

    @abstractmethod
    async def presigned_upload_url(
        self,
        key: str,
        expires: int = 3600,
        content_type: str = None,
        content_length_range: tuple[int, int] = None,
        metadata: dict = None,
    ) -> PresignedUrl:
        """
        Generate a pre-signed URL for direct upload.

        Args:
            key: The storage key where the file will be uploaded
            expires: URL expiration time in seconds
            content_type: Required content type for the upload
            content_length_range: (min, max) file size in bytes
            metadata: Metadata to associate with the uploaded file

        Returns:
            PresignedUrl with upload URL and required fields/headers
        """

    @abstractmethod
    async def presigned_download_url(
        self,
        key: str,
        expires: int = 3600,
        filename: str = None,
    ) -> PresignedUrl:
        """
        Generate a pre-signed URL for direct download.

        Args:
            key: The storage key to download
            expires: URL expiration time in seconds
            filename: Suggested filename for download

        Returns:
            PresignedUrl with download URL
        """

    async def copy(
        self,
        source_key: str,
        dest_key: str,
        overwrite: bool = True,
    ) -> str:
        """
        Copy a file within storage.

        Args:
            source_key: Source file key
            dest_key: Destination file key
            overwrite: Whether to overwrite existing destination

        Returns:
            The destination key

        Note:
            Default implementation downloads and re-uploads.
            Override for more efficient backend-specific copy.
        """
        if not overwrite and await self.exists(dest_key):
            raise FileExistsError(dest_key)

        content = await self.get(source_key)
        info = await self.info(source_key)
        return await self.save(
            content,
            key=dest_key,
            content_type=info.content_type,
            metadata=info.metadata,
            overwrite=overwrite,
        )

    async def move(
        self,
        source_key: str,
        dest_key: str,
        overwrite: bool = True,
    ) -> str:
        """
        Move a file within storage.

        Args:
            source_key: Source file key
            dest_key: Destination file key
            overwrite: Whether to overwrite existing destination

        Returns:
            The destination key
        """
        dest = await self.copy(source_key, dest_key, overwrite=overwrite)
        await self.delete(source_key)
        return dest

    async def delete_many(self, keys: list[str]) -> list[str]:
        """
        Delete multiple files.

        Args:
            keys: List of storage keys to delete

        Returns:
            List of keys that were successfully deleted

        Note:
            Default implementation deletes one by one.
            Override for batch delete support.
        """
        deleted = []
        for key in keys:
            try:
                await self.delete(key)
                deleted.append(key)
            except FileNotFoundError:
                pass
        return deleted

    # Sync wrappers for convenience

    def save_sync(
        self,
        file: Union[UploadedFile, BinaryIO, bytes],
        key: str = None,
        folder: str = None,
        content_type: str = None,
        metadata: dict = None,
        overwrite: bool = True,
    ) -> str:
        """Synchronous version of save()."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self.save(file, key, folder, content_type, metadata, overwrite)
        )

    def get_sync(self, key: str) -> bytes:
        """Synchronous version of get()."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.get(key))

    def delete_sync(self, key: str) -> None:
        """Synchronous version of delete()."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.delete(key))
