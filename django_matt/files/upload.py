"""
File upload handling.

Provides utilities for parsing multipart form data and handling file uploads.
"""

import io
import re
from dataclasses import dataclass, field
from typing import BinaryIO, Iterator, Union, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest


@dataclass
class UploadedFile:
    """
    Represents an uploaded file.

    Attributes:
        filename: Original filename from the upload
        content_type: MIME type of the file
        size: File size in bytes
        file: File-like object containing the data
        field_name: Form field name the file was uploaded under
    """

    filename: str
    content_type: str
    size: int
    file: BinaryIO
    field_name: str = ""
    headers: dict = field(default_factory=dict)

    @classmethod
    def from_request(
        cls,
        request: "HttpRequest",
        field_name: str = "file",
    ) -> Optional["UploadedFile"]:
        """
        Extract an uploaded file from a Django request.

        Args:
            request: The Django HttpRequest
            field_name: The form field name to look for

        Returns:
            UploadedFile or None if no file was uploaded
        """
        if not hasattr(request, "FILES"):
            return None

        django_file = request.FILES.get(field_name)
        if django_file is None:
            return None

        return cls(
            filename=django_file.name,
            content_type=django_file.content_type,
            size=django_file.size,
            file=django_file.file,
            field_name=field_name,
        )

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        field_name: str = "file",
    ) -> "UploadedFile":
        """
        Create an UploadedFile from raw bytes.

        Args:
            data: The file content as bytes
            filename: The filename to use
            content_type: MIME type
            field_name: Form field name

        Returns:
            UploadedFile instance
        """
        return cls(
            filename=filename,
            content_type=content_type,
            size=len(data),
            file=io.BytesIO(data),
            field_name=field_name,
        )

    def read(self, size: int = -1) -> bytes:
        """Read data from the file."""
        return self.file.read(size)

    def seek(self, position: int, whence: int = 0) -> int:
        """Seek to a position in the file."""
        return self.file.seek(position, whence)

    def tell(self) -> int:
        """Return current position in the file."""
        return self.file.tell()

    def chunks(self, chunk_size: int = 8192) -> Iterator[bytes]:
        """
        Iterate over file content in chunks.

        Args:
            chunk_size: Size of each chunk in bytes

        Yields:
            Chunks of file data
        """
        self.seek(0)
        while True:
            chunk = self.file.read(chunk_size)
            if not chunk:
                break
            yield chunk

    @property
    def extension(self) -> str:
        """Get the file extension (lowercase, without dot)."""
        if "." in self.filename:
            return self.filename.rsplit(".", 1)[-1].lower()
        return ""

    def __repr__(self):
        return f"UploadedFile(filename={self.filename!r}, size={self.size}, type={self.content_type!r})"


class MultipartParser:
    """
    Parser for multipart/form-data requests.

    This is a lightweight parser for extracting files from multipart requests.
    For most use cases, Django's built-in handling is sufficient, but this
    provides more control for streaming and async scenarios.
    """

    def __init__(
        self,
        content_type: str,
        body: Union[bytes, BinaryIO],
        max_size: int = None,
    ):
        """
        Initialize the parser.

        Args:
            content_type: The Content-Type header value
            body: Request body as bytes or file-like object
            max_size: Maximum allowed size in bytes
        """
        self.content_type = content_type
        self.body = body if isinstance(body, bytes) else body.read()
        self.max_size = max_size

        # Extract boundary from content type
        self.boundary = self._extract_boundary(content_type)

    def _extract_boundary(self, content_type: str) -> bytes:
        """Extract the boundary string from Content-Type header."""
        match = re.search(r'boundary=([^;\s]+)', content_type)
        if not match:
            raise ValueError("No boundary found in Content-Type header")

        boundary = match.group(1)
        # Remove quotes if present
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]

        return boundary.encode()

    def parse(self) -> tuple[dict, list[UploadedFile]]:
        """
        Parse the multipart data.

        Returns:
            Tuple of (form_data dict, list of UploadedFile)
        """
        form_data = {}
        files = []

        # Split by boundary
        delimiter = b"--" + self.boundary
        parts = self.body.split(delimiter)

        for part in parts[1:]:  # Skip preamble
            if part.startswith(b"--"):
                # End boundary
                break

            # Remove leading CRLF
            if part.startswith(b"\r\n"):
                part = part[2:]

            # Split headers and body
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue

            headers_raw = part[:header_end].decode("utf-8", errors="replace")
            body = part[header_end + 4:]

            # Remove trailing CRLF
            if body.endswith(b"\r\n"):
                body = body[:-2]

            # Parse headers
            headers = self._parse_headers(headers_raw)
            content_disposition = headers.get("content-disposition", "")

            # Extract field name and filename
            field_name = self._extract_param(content_disposition, "name")
            filename = self._extract_param(content_disposition, "filename")

            if filename:
                # It's a file
                content_type = headers.get("content-type", "application/octet-stream")
                files.append(
                    UploadedFile(
                        filename=filename,
                        content_type=content_type,
                        size=len(body),
                        file=io.BytesIO(body),
                        field_name=field_name or "file",
                        headers=headers,
                    )
                )
            else:
                # It's a form field
                if field_name:
                    form_data[field_name] = body.decode("utf-8", errors="replace")

        return form_data, files

    def _parse_headers(self, headers_raw: str) -> dict:
        """Parse header string into dictionary."""
        headers = {}
        for line in headers_raw.split("\r\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        return headers

    def _extract_param(self, header: str, param: str) -> Optional[str]:
        """Extract a parameter value from a header."""
        # Try quoted value first
        match = re.search(rf'{param}="([^"]*)"', header)
        if match:
            return match.group(1)

        # Try unquoted value
        match = re.search(rf'{param}=([^;\s]+)', header)
        if match:
            return match.group(1)

        return None


def parse_multipart(request: "HttpRequest") -> tuple[dict, list[UploadedFile]]:
    """
    Parse multipart form data from a request.

    This is a convenience function that uses Django's built-in parsing
    when available, falling back to MultipartParser for edge cases.

    Args:
        request: The Django HttpRequest

    Returns:
        Tuple of (form_data dict, list of UploadedFile)
    """
    # Use Django's built-in parsing if available
    if hasattr(request, "POST") and hasattr(request, "FILES"):
        form_data = dict(request.POST)
        files = []

        for field_name, file_list in request.FILES.lists():
            for django_file in file_list:
                files.append(
                    UploadedFile(
                        filename=django_file.name,
                        content_type=django_file.content_type,
                        size=django_file.size,
                        file=django_file.file,
                        field_name=field_name,
                    )
                )

        return form_data, files

    # Fall back to manual parsing
    content_type = request.content_type or request.META.get("CONTENT_TYPE", "")
    if "multipart/form-data" in content_type:
        parser = MultipartParser(content_type, request.body)
        return parser.parse()

    return {}, []


def get_uploaded_files(
    request: "HttpRequest",
    field_name: str = None,
) -> list[UploadedFile]:
    """
    Get all uploaded files from a request.

    Args:
        request: The Django HttpRequest
        field_name: Optional field name to filter by

    Returns:
        List of UploadedFile objects
    """
    _, files = parse_multipart(request)

    if field_name:
        return [f for f in files if f.field_name == field_name]

    return files
