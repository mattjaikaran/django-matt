"""
File validation utilities.

Provides validators for file uploads including size, type, and extension checks.
"""

import mimetypes
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .upload import UploadedFile


class ValidationError(Exception):
    """Base exception for file validation errors."""

    def __init__(self, message: str, code: str = "validation_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class FileTooLargeError(ValidationError):
    """Raised when a file exceeds the maximum allowed size."""

    def __init__(self, size: int, max_size: int):
        self.size = size
        self.max_size = max_size
        message = (
            f"File size ({self._human_size(size)}) exceeds maximum "
            f"allowed size ({self._human_size(max_size)})"
        )
        super().__init__(message, code="file_too_large")

    @staticmethod
    def _human_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


class InvalidFileTypeError(ValidationError):
    """Raised when a file has an invalid content type."""

    def __init__(self, content_type: str, allowed_types: Sequence[str]):
        self.content_type = content_type
        self.allowed_types = allowed_types
        message = (
            f"File type '{content_type}' is not allowed. Allowed types: {', '.join(allowed_types)}"
        )
        super().__init__(message, code="invalid_file_type")


class InvalidExtensionError(ValidationError):
    """Raised when a file has an invalid extension."""

    def __init__(self, extension: str, allowed_extensions: Sequence[str]):
        self.extension = extension
        self.allowed_extensions = allowed_extensions
        message = (
            f"File extension '.{extension}' is not allowed. "
            f"Allowed extensions: {', '.join('.' + e for e in allowed_extensions)}"
        )
        super().__init__(message, code="invalid_extension")


class FileValidator:
    """
    Validates uploaded files against configurable rules.

    Usage:
        validator = FileValidator(
            max_size=10 * 1024 * 1024,  # 10MB
            allowed_types=["image/jpeg", "image/png", "image/gif"],
            allowed_extensions=["jpg", "jpeg", "png", "gif"],
        )

        try:
            validator.validate(uploaded_file)
        except ValidationError as e:
            return {"error": e.message, "code": e.code}
    """

    # Common file type groups
    IMAGE_TYPES = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        "image/bmp",
        "image/tiff",
    ]

    DOCUMENT_TYPES = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
    ]

    VIDEO_TYPES = [
        "video/mp4",
        "video/webm",
        "video/ogg",
        "video/quicktime",
        "video/x-msvideo",
    ]

    AUDIO_TYPES = [
        "audio/mpeg",
        "audio/ogg",
        "audio/wav",
        "audio/webm",
        "audio/aac",
        "audio/flac",
    ]

    ARCHIVE_TYPES = [
        "application/zip",
        "application/x-rar-compressed",
        "application/x-7z-compressed",
        "application/gzip",
        "application/x-tar",
    ]

    def __init__(
        self,
        max_size: int = None,
        min_size: int = None,
        allowed_types: Sequence[str] = None,
        allowed_extensions: Sequence[str] = None,
        denied_types: Sequence[str] = None,
        denied_extensions: Sequence[str] = None,
        require_extension: bool = False,
        check_content: bool = False,
    ):
        """
        Initialize the validator.

        Args:
            max_size: Maximum file size in bytes
            min_size: Minimum file size in bytes
            allowed_types: List of allowed MIME types (e.g., ["image/jpeg", "image/png"])
            allowed_extensions: List of allowed extensions without dot (e.g., ["jpg", "png"])
            denied_types: List of denied MIME types (blacklist approach)
            denied_extensions: List of denied extensions (blacklist approach)
            require_extension: Whether the file must have an extension
            check_content: Whether to verify content type matches extension
        """
        self.max_size = max_size
        self.min_size = min_size
        self.allowed_types = [t.lower() for t in (allowed_types or [])]
        self.allowed_extensions = [e.lower().lstrip(".") for e in (allowed_extensions or [])]
        self.denied_types = [t.lower() for t in (denied_types or [])]
        self.denied_extensions = [e.lower().lstrip(".") for e in (denied_extensions or [])]
        self.require_extension = require_extension
        self.check_content = check_content

    def validate(self, file: "UploadedFile") -> None:
        """
        Validate an uploaded file.

        Args:
            file: The UploadedFile to validate

        Raises:
            ValidationError: If validation fails
        """
        self._validate_size(file)
        self._validate_extension(file)
        self._validate_type(file)

        if self.check_content:
            self._validate_content_matches_extension(file)

    def _validate_size(self, file: "UploadedFile") -> None:
        """Validate file size."""
        if self.max_size is not None and file.size > self.max_size:
            raise FileTooLargeError(file.size, self.max_size)

        if self.min_size is not None and file.size < self.min_size:
            raise ValidationError(
                f"File size ({file.size} bytes) is below minimum "
                f"required size ({self.min_size} bytes)",
                code="file_too_small",
            )

    def _validate_extension(self, file: "UploadedFile") -> None:
        """Validate file extension."""
        extension = file.extension

        if self.require_extension and not extension:
            raise ValidationError(
                "File must have an extension",
                code="missing_extension",
            )

        if extension:
            # Check denied list
            if self.denied_extensions and extension in self.denied_extensions:
                raise InvalidExtensionError(extension, [])

            # Check allowed list
            if self.allowed_extensions and extension not in self.allowed_extensions:
                raise InvalidExtensionError(extension, self.allowed_extensions)

    def _validate_type(self, file: "UploadedFile") -> None:
        """Validate content type."""
        content_type = file.content_type.lower()

        # Check denied list
        if self.denied_types:
            for denied in self.denied_types:
                if self._type_matches(content_type, denied):
                    raise InvalidFileTypeError(content_type, [])

        # Check allowed list
        if self.allowed_types:
            for allowed in self.allowed_types:
                if self._type_matches(content_type, allowed):
                    return
            raise InvalidFileTypeError(content_type, self.allowed_types)

    def _type_matches(self, content_type: str, pattern: str) -> bool:
        """Check if content type matches a pattern (supports wildcards)."""
        if pattern == "*/*":
            return True

        if pattern.endswith("/*"):
            # Match type category (e.g., "image/*")
            category = pattern[:-2]
            return content_type.startswith(category + "/")

        return content_type == pattern

    def _validate_content_matches_extension(self, file: "UploadedFile") -> None:
        """Verify that content type matches the file extension."""
        if not file.extension:
            return

        # Get expected content type from extension
        expected_type, _ = mimetypes.guess_type(f"file.{file.extension}")

        if expected_type and file.content_type.lower() != expected_type.lower():
            raise ValidationError(
                f"Content type '{file.content_type}' doesn't match "
                f"extension '.{file.extension}' (expected '{expected_type}')",
                code="content_type_mismatch",
            )

    @classmethod
    def images(
        cls,
        max_size: int = 10 * 1024 * 1024,  # 10MB
        allowed_types: Sequence[str] = None,
    ) -> "FileValidator":
        """
        Create a validator for image files.

        Args:
            max_size: Maximum file size (default 10MB)
            allowed_types: Override allowed image types

        Returns:
            Configured FileValidator
        """
        return cls(
            max_size=max_size,
            allowed_types=allowed_types or cls.IMAGE_TYPES,
            allowed_extensions=["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "tiff"],
        )

    @classmethod
    def documents(
        cls,
        max_size: int = 50 * 1024 * 1024,  # 50MB
        allowed_types: Sequence[str] = None,
    ) -> "FileValidator":
        """
        Create a validator for document files.

        Args:
            max_size: Maximum file size (default 50MB)
            allowed_types: Override allowed document types

        Returns:
            Configured FileValidator
        """
        return cls(
            max_size=max_size,
            allowed_types=allowed_types or cls.DOCUMENT_TYPES,
            allowed_extensions=["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv"],
        )

    @classmethod
    def videos(
        cls,
        max_size: int = 500 * 1024 * 1024,  # 500MB
        allowed_types: Sequence[str] = None,
    ) -> "FileValidator":
        """
        Create a validator for video files.

        Args:
            max_size: Maximum file size (default 500MB)
            allowed_types: Override allowed video types

        Returns:
            Configured FileValidator
        """
        return cls(
            max_size=max_size,
            allowed_types=allowed_types or cls.VIDEO_TYPES,
            allowed_extensions=["mp4", "webm", "ogg", "mov", "avi"],
        )

    @classmethod
    def audio(
        cls,
        max_size: int = 100 * 1024 * 1024,  # 100MB
        allowed_types: Sequence[str] = None,
    ) -> "FileValidator":
        """
        Create a validator for audio files.

        Args:
            max_size: Maximum file size (default 100MB)
            allowed_types: Override allowed audio types

        Returns:
            Configured FileValidator
        """
        return cls(
            max_size=max_size,
            allowed_types=allowed_types or cls.AUDIO_TYPES,
            allowed_extensions=["mp3", "ogg", "wav", "webm", "aac", "flac"],
        )
