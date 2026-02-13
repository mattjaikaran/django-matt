"""
S3-compatible storage backends.

Provides storage backends for:
- AWS S3
- Cloudflare R2
- MinIO
- DigitalOcean Spaces
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, BinaryIO, Union

from .storage import (
    BaseStorage,
    FileExistsError,
    FileInfo,
    FileNotFoundError,
    PresignedUrl,
    StorageError,
)
from .utils import generate_unique_filename, get_content_type, sanitize_filename

if TYPE_CHECKING:
    from .upload import UploadedFile


class S3Storage(BaseStorage):
    """
    Amazon S3 storage backend.

    Also works with S3-compatible services like Cloudflare R2, MinIO,
    and DigitalOcean Spaces by providing a custom endpoint.

    Usage:
        # AWS S3
        storage = S3Storage(
            bucket="my-bucket",
            region="us-east-1",
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )

        # Cloudflare R2
        storage = S3Storage(
            bucket="my-bucket",
            access_key="...",
            secret_key="...",
            endpoint="https://<account_id>.r2.cloudflarestorage.com",
            region="auto",
        )

        # MinIO
        storage = S3Storage(
            bucket="my-bucket",
            access_key="minioadmin",
            secret_key="minioadmin",
            endpoint="http://localhost:9000",
            region="us-east-1",
        )

        # Save a file
        key = await storage.save(uploaded_file, folder="images")

        # Get pre-signed URL
        url = await storage.presigned_download_url(key, expires=3600)

    Requires:
        pip install boto3
    """

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        access_key: str = None,
        secret_key: str = None,
        endpoint: str = None,
        public_url: str = None,
        use_ssl: bool = True,
        signature_version: str = "s3v4",
        addressing_style: str = "auto",
    ):
        """
        Initialize S3 storage.

        Args:
            bucket: S3 bucket name
            region: AWS region (e.g., "us-east-1")
            access_key: AWS access key ID
            secret_key: AWS secret access key
            endpoint: Custom endpoint URL (for R2, MinIO, etc.)
            public_url: Custom public URL for files
            use_ssl: Whether to use HTTPS
            signature_version: Signature version ("s3v4" recommended)
            addressing_style: "auto", "path", or "virtual"
        """
        self.bucket = bucket
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint = endpoint
        self.public_url = public_url
        self.use_ssl = use_ssl
        self.signature_version = signature_version
        self.addressing_style = addressing_style

        self._client = None
        self._resource = None

    @property
    def client(self):
        """Get or create the boto3 client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self):
        """Create a boto3 S3 client."""
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise ImportError("boto3 is required for S3 storage. Install with: pip install boto3")

        config = Config(
            signature_version=self.signature_version,
            s3={"addressing_style": self.addressing_style},
        )

        client_kwargs = {
            "service_name": "s3",
            "region_name": self.region,
            "config": config,
            "use_ssl": self.use_ssl,
        }

        if self.access_key and self.secret_key:
            client_kwargs["aws_access_key_id"] = self.access_key
            client_kwargs["aws_secret_access_key"] = self.secret_key

        if self.endpoint:
            client_kwargs["endpoint_url"] = self.endpoint

        return boto3.client(**client_kwargs)

    async def save(
        self,
        file: Union["UploadedFile", BinaryIO, bytes],
        key: str = None,
        folder: str = None,
        content_type: str = None,
        metadata: dict = None,
        overwrite: bool = True,
    ) -> str:
        """Save a file to S3."""
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

        # Check if file exists
        if not overwrite:
            if await self.exists(key):
                raise FileExistsError(key)

        # Get content and content type
        if isinstance(file, bytes):
            content = file
            if content_type is None:
                content_type = "application/octet-stream"
        elif hasattr(file, "read"):
            if hasattr(file, "seek"):
                file.seek(0)
            content = file.read()
            if hasattr(file, "content_type") and content_type is None:
                content_type = file.content_type
            if content_type is None:
                content_type = get_content_type(getattr(file, "filename", key))
        else:
            raise ValueError(f"Unsupported file type: {type(file)}")

        # Prepare upload parameters
        extra_args = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}

        # Upload to S3 (run in thread pool for async)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                **extra_args,
            ),
        )

        return key

    async def get(self, key: str) -> bytes:
        """Get a file's contents from S3."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.get_object(
                    Bucket=self.bucket,
                    Key=key,
                ),
            )
            return response["Body"].read()
        except self.client.exceptions.NoSuchKey:
            raise FileNotFoundError(key)
        except Exception as e:
            if "NoSuchKey" in str(e) or "404" in str(e):
                raise FileNotFoundError(key)
            raise StorageError(f"Failed to get file: {e}")

    async def get_stream(self, key: str, chunk_size: int = 8192) -> Iterator[bytes]:
        """Get a file's contents as a stream."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.get_object(
                    Bucket=self.bucket,
                    Key=key,
                ),
            )

            body = response["Body"]
            while True:
                chunk = body.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        except Exception as e:
            if "NoSuchKey" in str(e) or "404" in str(e):
                raise FileNotFoundError(key)
            raise StorageError(f"Failed to get file: {e}")

    async def delete(self, key: str) -> None:
        """Delete a file from S3."""
        # Check if exists first
        if not await self.exists(key):
            raise FileNotFoundError(key)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.delete_object(
                Bucket=self.bucket,
                Key=key,
            ),
        )

    async def exists(self, key: str) -> bool:
        """Check if a file exists in S3."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.client.head_object(
                    Bucket=self.bucket,
                    Key=key,
                ),
            )
            return True
        except Exception:
            return False

    async def info(self, key: str) -> FileInfo:
        """Get information about a file."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.head_object(
                    Bucket=self.bucket,
                    Key=key,
                ),
            )

            return FileInfo(
                key=key,
                size=response.get("ContentLength", 0),
                content_type=response.get("ContentType", "application/octet-stream"),
                last_modified=response.get("LastModified"),
                etag=response.get("ETag", "").strip('"'),
                metadata=response.get("Metadata", {}),
            )
        except Exception as e:
            if "404" in str(e) or "NoSuchKey" in str(e):
                raise FileNotFoundError(key)
            raise StorageError(f"Failed to get file info: {e}")

    async def list(
        self,
        prefix: str = "",
        limit: int = None,
        cursor: str = None,
    ) -> tuple[list[FileInfo], str | None]:
        """List files in S3."""
        loop = asyncio.get_event_loop()

        params = {
            "Bucket": self.bucket,
            "Prefix": prefix,
        }

        if limit:
            params["MaxKeys"] = limit

        if cursor:
            params["ContinuationToken"] = cursor

        response = await loop.run_in_executor(
            None,
            lambda: self.client.list_objects_v2(**params),
        )

        files = []
        for obj in response.get("Contents", []):
            files.append(
                FileInfo(
                    key=obj["Key"],
                    size=obj["Size"],
                    content_type="application/octet-stream",  # Not available in list
                    last_modified=obj.get("LastModified"),
                    etag=obj.get("ETag", "").strip('"'),
                )
            )

        next_cursor = response.get("NextContinuationToken")
        return files, next_cursor

    def url(self, key: str) -> str:
        """Get the public URL for a file."""
        if self.public_url:
            return f"{self.public_url.rstrip('/')}/{key}"

        if self.endpoint:
            return f"{self.endpoint.rstrip('/')}/{self.bucket}/{key}"

        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

    async def presigned_upload_url(
        self,
        key: str,
        expires: int = 3600,
        content_type: str = None,
        content_length_range: tuple[int, int] = None,
        metadata: dict = None,
    ) -> PresignedUrl:
        """Generate a pre-signed URL for direct upload."""
        expires_at = datetime.now(UTC) + timedelta(seconds=expires)

        conditions = []
        fields = {"key": key}

        if content_type:
            conditions.append({"Content-Type": content_type})
            fields["Content-Type"] = content_type

        if content_length_range:
            conditions.append(
                ["content-length-range", content_length_range[0], content_length_range[1]]
            )

        if metadata:
            for k, v in metadata.items():
                meta_key = f"x-amz-meta-{k}"
                conditions.append({meta_key: str(v)})
                fields[meta_key] = str(v)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.generate_presigned_post(
                Bucket=self.bucket,
                Key=key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expires,
            ),
        )

        return PresignedUrl(
            url=response["url"],
            expires_at=expires_at,
            method="POST",
            fields=response["fields"],
        )

    async def presigned_download_url(
        self,
        key: str,
        expires: int = 3600,
        filename: str = None,
    ) -> PresignedUrl:
        """Generate a pre-signed URL for direct download."""
        expires_at = datetime.now(UTC) + timedelta(seconds=expires)

        params = {
            "Bucket": self.bucket,
            "Key": key,
        }

        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None,
            lambda: self.client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires,
            ),
        )

        return PresignedUrl(
            url=url,
            expires_at=expires_at,
            method="GET",
        )

    async def copy(
        self,
        source_key: str,
        dest_key: str,
        overwrite: bool = True,
    ) -> str:
        """Copy a file within S3 (server-side copy)."""
        if not overwrite and await self.exists(dest_key):
            raise FileExistsError(dest_key)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.copy_object(
                Bucket=self.bucket,
                Key=dest_key,
                CopySource={"Bucket": self.bucket, "Key": source_key},
            ),
        )

        return dest_key

    async def delete_many(self, keys: list[str]) -> list[str]:
        """Delete multiple files (batch delete)."""
        if not keys:
            return []

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.delete_objects(
                Bucket=self.bucket,
                Delete={
                    "Objects": [{"Key": key} for key in keys],
                    "Quiet": True,
                },
            ),
        )

        # Return keys that were deleted (not in Errors)
        errors = {e["Key"] for e in response.get("Errors", [])}
        return [key for key in keys if key not in errors]


class R2Storage(S3Storage):
    """
    Cloudflare R2 storage backend.

    R2 is S3-compatible object storage from Cloudflare.

    Usage:
        storage = R2Storage(
            bucket="my-bucket",
            account_id="your-account-id",
            access_key="...",
            secret_key="...",
        )

    Note:
        R2 doesn't support all S3 features. Check Cloudflare docs for details.
    """

    def __init__(
        self,
        bucket: str,
        account_id: str,
        access_key: str,
        secret_key: str,
        public_url: str = None,
    ):
        """
        Initialize R2 storage.

        Args:
            bucket: R2 bucket name
            account_id: Cloudflare account ID
            access_key: R2 access key
            secret_key: R2 secret key
            public_url: Custom domain or R2.dev URL for public access
        """
        super().__init__(
            bucket=bucket,
            region="auto",
            access_key=access_key,
            secret_key=secret_key,
            endpoint=f"https://{account_id}.r2.cloudflarestorage.com",
            public_url=public_url,
        )
        self.account_id = account_id


class MinIOStorage(S3Storage):
    """
    MinIO storage backend.

    MinIO is a self-hosted S3-compatible object storage.

    Usage:
        storage = MinIOStorage(
            bucket="my-bucket",
            endpoint="http://localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
        )
    """

    def __init__(
        self,
        bucket: str,
        endpoint: str = "http://localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        region: str = "us-east-1",
        public_url: str = None,
        use_ssl: bool = None,
    ):
        """
        Initialize MinIO storage.

        Args:
            bucket: MinIO bucket name
            endpoint: MinIO server endpoint
            access_key: MinIO access key
            secret_key: MinIO secret key
            region: Region (MinIO doesn't use this but it's required)
            public_url: Public URL for files
            use_ssl: Whether to use HTTPS (auto-detected from endpoint)
        """
        if use_ssl is None:
            use_ssl = endpoint.startswith("https://")

        super().__init__(
            bucket=bucket,
            region=region,
            access_key=access_key,
            secret_key=secret_key,
            endpoint=endpoint,
            public_url=public_url,
            use_ssl=use_ssl,
            addressing_style="path",  # MinIO uses path-style
        )


class DOSpacesStorage(S3Storage):
    """
    DigitalOcean Spaces storage backend.

    Spaces is S3-compatible object storage from DigitalOcean.

    Usage:
        storage = DOSpacesStorage(
            bucket="my-space",
            region="nyc3",
            access_key="...",
            secret_key="...",
        )
    """

    def __init__(
        self,
        bucket: str,
        region: str,
        access_key: str,
        secret_key: str,
        public_url: str = None,
    ):
        """
        Initialize DO Spaces storage.

        Args:
            bucket: Spaces bucket/space name
            region: DO region (e.g., "nyc3", "sfo3", "ams3")
            access_key: Spaces access key
            secret_key: Spaces secret key
            public_url: Custom CDN URL (optional)
        """
        super().__init__(
            bucket=bucket,
            region=region,
            access_key=access_key,
            secret_key=secret_key,
            endpoint=f"https://{region}.digitaloceanspaces.com",
            public_url=public_url or f"https://{bucket}.{region}.digitaloceanspaces.com",
        )
