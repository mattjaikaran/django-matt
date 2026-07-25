# file-length-max: 550
"""
Chunked and resumable upload support.

Implements the tus resumable upload protocol (v1.0.0) and S3 native
multipart uploads for large file handling.

tus protocol spec: https://tus.io/protocols/resumable-upload
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views import View

logger = logging.getLogger("django_matt.files.chunked")

TUS_VERSION = "1.0.0"
TUS_EXTENSIONS = "creation,termination,creation-with-upload"

# Default limits
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB
DEFAULT_MAX_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB
DEFAULT_EXPIRY_SECONDS = 24 * 60 * 60  # 24 hours


@dataclass
class UploadSession:
    """Tracks state of an in-progress chunked upload."""

    upload_id: str
    size: int
    offset: int = 0
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    content_type: str = "application/octet-stream"
    path: str = ""
    completed: bool = False


class TusUploadHandler:
    """
    Server-side handler for tus resumable uploads.

    Stores partial uploads on disk in a configurable temp directory.
    On completion, moves the assembled file to the final location or
    returns the path for the caller to handle.

    Usage::

        handler = TusUploadHandler(upload_dir="/tmp/tus-uploads")

        # Client creates upload
        upload_id = await handler.create(metadata={"filename": "big.zip"}, size=1_000_000)

        # Client sends chunks
        new_offset = await handler.append(upload_id, chunk_bytes, offset=0)
        new_offset = await handler.append(upload_id, chunk_bytes2, offset=new_offset)

        # Client finalizes
        path = await handler.complete(upload_id)
    """

    def __init__(
        self,
        upload_dir: str | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_size: int = DEFAULT_MAX_SIZE,
        expiry_seconds: int = DEFAULT_EXPIRY_SECONDS,
    ) -> None:
        self.upload_dir = Path(upload_dir or tempfile.mkdtemp(prefix="tus_"))
        self.chunk_size = chunk_size
        self.max_size = max_size
        self.expiry_seconds = expiry_seconds
        self._sessions: dict[str, UploadSession] = {}

        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _generate_id(self) -> str:
        return hashlib.sha256(os.urandom(32)).hexdigest()[:24]

    def _session_path(self, upload_id: str) -> Path:
        return self.upload_dir / upload_id

    def _validate_session(self, upload_id: str) -> UploadSession:
        session = self._sessions.get(upload_id)
        if session is None:
            raise FileNotFoundError(f"Upload session not found: {upload_id}")
        if session.completed:
            raise ValueError(f"Upload already completed: {upload_id}")
        if time.time() - session.created_at > self.expiry_seconds:
            self._cleanup_session(upload_id)
            raise TimeoutError(f"Upload session expired: {upload_id}")
        return session

    def _cleanup_session(self, upload_id: str) -> None:
        path = self._session_path(upload_id)
        if path.exists():
            path.unlink(missing_ok=True)
        self._sessions.pop(upload_id, None)

    async def create(
        self,
        metadata: dict[str, str] | None = None,
        size: int = 0,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Create a new upload session. Returns upload_id."""
        if size > self.max_size:
            raise ValueError(f"File size {size} exceeds maximum {self.max_size}")

        upload_id = self._generate_id()
        path = self._session_path(upload_id)

        # Create empty file
        await asyncio.to_thread(path.touch)

        session = UploadSession(
            upload_id=upload_id,
            size=size,
            metadata=metadata or {},
            content_type=content_type,
            path=str(path),
        )
        self._sessions[upload_id] = session

        logger.info(
            "Created upload session %s (size=%d, type=%s)",
            upload_id,
            size,
            content_type,
        )
        return upload_id

    async def append(
        self,
        upload_id: str,
        chunk: bytes,
        offset: int,
    ) -> int:
        """Append a chunk at the given offset. Returns new offset."""
        session = self._validate_session(upload_id)

        if offset != session.offset:
            raise ValueError(f"Offset mismatch: expected {session.offset}, got {offset}")

        new_offset = session.offset + len(chunk)
        if session.size and new_offset > session.size:
            raise ValueError(f"Upload would exceed declared size: {new_offset} > {session.size}")

        path = self._session_path(upload_id)

        def _write() -> None:
            with open(path, "ab") as f:
                f.write(chunk)

        await asyncio.to_thread(_write)

        session.offset = new_offset
        return new_offset

    async def complete(self, upload_id: str) -> str:
        """Finalize an upload. Returns the file path."""
        session = self._validate_session(upload_id)

        if session.size and session.offset != session.size:
            raise ValueError(f"Upload incomplete: {session.offset}/{session.size} bytes")

        session.completed = True
        path = str(self._session_path(upload_id))

        logger.info("Completed upload session %s (%d bytes)", upload_id, session.offset)
        return path

    async def get_offset(self, upload_id: str) -> int:
        """Get the current offset for resuming."""
        session = self._validate_session(upload_id)
        return session.offset

    async def delete(self, upload_id: str) -> None:
        """Cancel and delete a partial upload."""
        self._cleanup_session(upload_id)
        logger.info("Deleted upload session %s", upload_id)

    async def cleanup_expired(self) -> int:
        """Remove expired upload sessions. Returns count removed."""
        now = time.time()
        expired = [
            uid for uid, s in self._sessions.items() if now - s.created_at > self.expiry_seconds
        ]
        for uid in expired:
            self._cleanup_session(uid)
        if expired:
            logger.info("Cleaned up %d expired upload sessions", len(expired))
        return len(expired)

    def get_session(self, upload_id: str) -> UploadSession | None:
        """Get session info (or None)."""
        return self._sessions.get(upload_id)


def _parse_tus_metadata(header: str) -> dict[str, str]:
    """Parse Upload-Metadata header: key b64val, key2 b64val2."""
    metadata: dict[str, str] = {}
    if not header:
        return metadata
    for pair in header.split(","):
        pair = pair.strip()
        if " " in pair:
            key, b64val = pair.split(" ", 1)
            try:
                metadata[key] = base64.b64decode(b64val).decode("utf-8")
            except Exception:
                metadata[key] = b64val
        else:
            metadata[pair] = ""
    return metadata


class TusUploadView(View):
    """
    Django view implementing the tus v1.0.0 resumable upload protocol.

    Mount in urls.py::

        from django_matt.files.chunked import TusUploadView

        urlpatterns = [
            path("upload/", TusUploadView.as_view(), name="tus-upload"),
            path("upload/<str:upload_id>", TusUploadView.as_view(), name="tus-upload-detail"),
        ]
    """

    handler: TusUploadHandler | None = None

    @classmethod
    def get_handler(cls) -> TusUploadHandler:
        if cls.handler is None:
            cls.handler = TusUploadHandler()
        return cls.handler

    @classmethod
    def configure(cls, **kwargs: Any) -> None:
        """Configure the shared handler instance."""
        cls.handler = TusUploadHandler(**kwargs)

    def _tus_headers(self) -> dict[str, str]:
        return {
            "Tus-Resumable": TUS_VERSION,
            "Tus-Version": TUS_VERSION,
            "Tus-Extension": TUS_EXTENSIONS,
        }

    def options(self, request: HttpRequest, **kwargs: Any) -> HttpResponse:
        """Return tus server capabilities."""
        response = HttpResponse(status=204)
        for k, v in self._tus_headers().items():
            response[k] = v
        response["Tus-Max-Size"] = str(self.get_handler().max_size)
        return response

    def post(self, request: HttpRequest, **kwargs: Any) -> HttpResponse:
        """Create a new upload (tus creation extension)."""
        handler = self.get_handler()
        upload_length = request.headers.get("Upload-Length")
        if upload_length is None:
            return JsonResponse({"error": "Upload-Length header required"}, status=400)

        try:
            size = int(upload_length)
        except ValueError:
            return JsonResponse({"error": "Invalid Upload-Length"}, status=400)

        metadata = _parse_tus_metadata(request.headers.get("Upload-Metadata", ""))
        content_type = metadata.get("content_type", "application/octet-stream")

        import asyncio as _asyncio

        try:
            upload_id = _asyncio.get_event_loop().run_until_complete(
                handler.create(metadata=metadata, size=size, content_type=content_type)
            )
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=413)

        response = HttpResponse(status=201)
        for k, v in self._tus_headers().items():
            response[k] = v
        response["Location"] = request.build_absolute_uri(f"{request.path}{upload_id}")
        response["Upload-Offset"] = "0"
        return response

    def patch(self, request: HttpRequest, upload_id: str = "", **kwargs: Any) -> HttpResponse:
        """Append chunk data (tus core protocol)."""
        handler = self.get_handler()

        ct = request.headers.get("Content-Type", "")
        if ct != "application/offset+octet-stream":
            return JsonResponse(
                {"error": "Content-Type must be application/offset+octet-stream"},
                status=415,
            )

        offset_header = request.headers.get("Upload-Offset")
        if offset_header is None:
            return JsonResponse({"error": "Upload-Offset header required"}, status=400)

        try:
            offset = int(offset_header)
        except ValueError:
            return JsonResponse({"error": "Invalid Upload-Offset"}, status=400)

        import asyncio as _asyncio

        try:
            new_offset = _asyncio.get_event_loop().run_until_complete(
                handler.append(upload_id, request.body, offset)
            )
        except FileNotFoundError:
            return JsonResponse({"error": "Upload not found"}, status=404)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=409)
        except TimeoutError:
            return JsonResponse({"error": "Upload expired"}, status=410)

        response = HttpResponse(status=204)
        for k, v in self._tus_headers().items():
            response[k] = v
        response["Upload-Offset"] = str(new_offset)
        return response

    def head(self, request: HttpRequest, upload_id: str = "", **kwargs: Any) -> HttpResponse:
        """Get current upload offset for resumption."""
        handler = self.get_handler()

        import asyncio as _asyncio

        try:
            offset = _asyncio.get_event_loop().run_until_complete(handler.get_offset(upload_id))
        except FileNotFoundError:
            return JsonResponse({"error": "Upload not found"}, status=404)
        except TimeoutError:
            return JsonResponse({"error": "Upload expired"}, status=410)

        session = handler.get_session(upload_id)
        response = HttpResponse(status=200)
        for k, v in self._tus_headers().items():
            response[k] = v
        response["Upload-Offset"] = str(offset)
        if session and session.size:
            response["Upload-Length"] = str(session.size)
        response["Cache-Control"] = "no-store"
        return response

    def delete(self, request: HttpRequest, upload_id: str = "", **kwargs: Any) -> HttpResponse:
        """Cancel and delete partial upload (tus termination extension)."""
        handler = self.get_handler()

        import asyncio as _asyncio

        _asyncio.get_event_loop().run_until_complete(handler.delete(upload_id))

        response = HttpResponse(status=204)
        for k, v in self._tus_headers().items():
            response[k] = v
        return response


class S3MultipartHandler:
    """
    S3 native multipart upload handler for large files.

    Uses the S3 CreateMultipartUpload / UploadPart / CompleteMultipartUpload
    API for efficient large-file uploads directly to S3-compatible storage.

    Usage::

        from django_matt.files.s3 import S3Storage

        handler = S3MultipartHandler(storage)

        upload_id = await handler.create_multipart("uploads/big.zip", "application/zip")
        etag1 = await handler.upload_part(upload_id, 1, chunk1)
        etag2 = await handler.upload_part(upload_id, 2, chunk2)
        await handler.complete_multipart(
            upload_id,
            [
                {"PartNumber": 1, "ETag": etag1},
                {"PartNumber": 2, "ETag": etag2},
            ],
        )
    """

    def __init__(self, storage: Any) -> None:
        """
        Args:
            storage: An S3Storage instance (or any S3-compatible storage with
                     a `.client` property and `.bucket` attribute).
        """
        self.storage = storage
        self._uploads: dict[str, str] = {}  # upload_id -> key

    async def create_multipart(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Start a multipart upload. Returns the S3 upload ID."""
        extra: dict[str, Any] = {"ContentType": content_type}
        if metadata:
            extra["Metadata"] = {k: str(v) for k, v in metadata.items()}

        response = await asyncio.to_thread(
            lambda: self.storage.client.create_multipart_upload(
                Bucket=self.storage.bucket,
                Key=key,
                **extra,
            )
        )

        upload_id: str = response["UploadId"]
        self._uploads[upload_id] = key
        logger.info("Created S3 multipart upload %s for key=%s", upload_id, key)
        return upload_id

    async def upload_part(
        self,
        upload_id: str,
        part_number: int,
        body: bytes,
    ) -> str:
        """Upload a single part. Returns the ETag."""
        key = self._uploads.get(upload_id)
        if key is None:
            raise ValueError(f"Unknown multipart upload: {upload_id}")

        response = await asyncio.to_thread(
            lambda: self.storage.client.upload_part(
                Bucket=self.storage.bucket,
                Key=key,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=body,
            )
        )

        etag: str = response["ETag"]
        return etag

    async def complete_multipart(
        self,
        upload_id: str,
        parts: list[dict[str, Any]],
    ) -> str:
        """
        Complete the multipart upload.

        Args:
            upload_id: The S3 upload ID from create_multipart.
            parts: List of {"PartNumber": int, "ETag": str} dicts.

        Returns:
            The final object key.
        """
        key = self._uploads.get(upload_id)
        if key is None:
            raise ValueError(f"Unknown multipart upload: {upload_id}")

        await asyncio.to_thread(
            lambda: self.storage.client.complete_multipart_upload(
                Bucket=self.storage.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        )

        self._uploads.pop(upload_id, None)
        logger.info("Completed S3 multipart upload %s (key=%s)", upload_id, key)
        return key

    async def abort_multipart(self, upload_id: str) -> None:
        """Abort (cancel) a multipart upload."""
        key = self._uploads.get(upload_id)
        if key is None:
            raise ValueError(f"Unknown multipart upload: {upload_id}")

        await asyncio.to_thread(
            lambda: self.storage.client.abort_multipart_upload(
                Bucket=self.storage.bucket,
                Key=key,
                UploadId=upload_id,
            )
        )

        self._uploads.pop(upload_id, None)
        logger.info("Aborted S3 multipart upload %s (key=%s)", upload_id, key)
