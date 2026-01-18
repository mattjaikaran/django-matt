"""
Attachment model for messages.

Handles file attachments with storage integration and validation.
"""

import mimetypes
from pathlib import Path
from typing import ClassVar

from django.conf import settings
from django.db import models

from django_matt.messaging.enums import AttachmentType


def get_attachment_type(content_type: str) -> AttachmentType:
    """Determine attachment type from content type."""
    if content_type.startswith("image/"):
        return AttachmentType.IMAGE
    if content_type.startswith("video/"):
        return AttachmentType.VIDEO
    if content_type.startswith("audio/"):
        return AttachmentType.AUDIO
    if content_type in (
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/csv",
    ):
        return AttachmentType.DOCUMENT
    if content_type in (
        "application/zip",
        "application/x-rar-compressed",
        "application/x-7z-compressed",
        "application/gzip",
        "application/x-tar",
    ):
        return AttachmentType.ARCHIVE
    return AttachmentType.OTHER


class AttachmentManager(models.Manager):
    """Custom manager for Attachment model."""

    def for_message(self, message):
        """Get attachments for a message."""
        return self.filter(message=message)

    def images(self):
        """Get only image attachments."""
        return self.filter(attachment_type=AttachmentType.IMAGE)

    def documents(self):
        """Get only document attachments."""
        return self.filter(attachment_type=AttachmentType.DOCUMENT)


class Attachment(models.Model):
    """
    File attachment for messages.

    Supports various file types with automatic type detection,
    thumbnails for images, and integration with storage backends.
    """

    # Maximum file sizes by type (in bytes)
    MAX_SIZES: ClassVar[dict[AttachmentType, int]] = {
        AttachmentType.IMAGE: 10 * 1024 * 1024,  # 10MB
        AttachmentType.VIDEO: 100 * 1024 * 1024,  # 100MB
        AttachmentType.AUDIO: 50 * 1024 * 1024,  # 50MB
        AttachmentType.DOCUMENT: 25 * 1024 * 1024,  # 25MB
        AttachmentType.ARCHIVE: 50 * 1024 * 1024,  # 50MB
        AttachmentType.OTHER: 10 * 1024 * 1024,  # 10MB
    }

    id = models.BigAutoField(primary_key=True)

    message = models.ForeignKey(
        "messaging.Message",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_attachments",
    )

    # File info
    filename = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    attachment_type = models.CharField(
        max_length=20,
        choices=[(t.value, t.name) for t in AttachmentType],
        default=AttachmentType.OTHER,
    )
    file_size = models.BigIntegerField()

    # Storage
    storage_path = models.CharField(max_length=500)
    storage_backend = models.CharField(max_length=50, default="default")

    # URLs (can be pre-signed for cloud storage)
    url = models.URLField(max_length=1000, blank=True, default="")
    thumbnail_url = models.URLField(max_length=1000, blank=True, default="")

    # Image-specific metadata
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)

    # Video/Audio metadata
    duration = models.PositiveIntegerField(null=True, blank=True)  # in seconds

    # Processing status
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True, default="")

    # Security
    is_scanned = models.BooleanField(default=False)
    is_safe = models.BooleanField(default=True)
    scan_result = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Custom manager
    objects = AttachmentManager()

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["message"]),
            models.Index(fields=["attachment_type"]),
            models.Index(fields=["uploaded_by"]),
        ]

    def __str__(self):
        return f"{self.original_filename} ({self.attachment_type})"

    def save(self, *args, **kwargs):
        # Auto-detect attachment type if not set
        if not self.attachment_type or self.attachment_type == AttachmentType.OTHER:
            self.attachment_type = get_attachment_type(self.content_type)
        super().save(*args, **kwargs)

    @property
    def extension(self) -> str:
        """Get file extension."""
        return Path(self.original_filename).suffix.lower()

    @property
    def is_image(self) -> bool:
        """Check if attachment is an image."""
        return self.attachment_type == AttachmentType.IMAGE

    @property
    def is_video(self) -> bool:
        """Check if attachment is a video."""
        return self.attachment_type == AttachmentType.VIDEO

    @property
    def is_audio(self) -> bool:
        """Check if attachment is audio."""
        return self.attachment_type == AttachmentType.AUDIO

    @property
    def is_document(self) -> bool:
        """Check if attachment is a document."""
        return self.attachment_type == AttachmentType.DOCUMENT

    @property
    def human_readable_size(self) -> str:
        """Get human-readable file size."""
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def validate_size(self) -> bool:
        """Validate file size against limits."""
        max_size = self.MAX_SIZES.get(
            AttachmentType(self.attachment_type),
            self.MAX_SIZES[AttachmentType.OTHER],
        )
        return self.file_size <= max_size

    def get_max_size(self) -> int:
        """Get maximum allowed size for this attachment type."""
        return self.MAX_SIZES.get(
            AttachmentType(self.attachment_type),
            self.MAX_SIZES[AttachmentType.OTHER],
        )

    @classmethod
    def from_upload(
        cls,
        message,
        file,
        uploaded_by=None,
        storage_path=None,
        **kwargs,
    ):
        """
        Create an attachment from an uploaded file.

        Args:
            message: The message to attach to
            file: The uploaded file object
            uploaded_by: The user who uploaded the file
            storage_path: Path where file is stored
            **kwargs: Additional fields

        Returns:
            Attachment instance
        """
        # Determine content type
        content_type = getattr(file, "content_type", None)
        if not content_type:
            content_type, _ = mimetypes.guess_type(file.name)
            content_type = content_type or "application/octet-stream"

        # Get file size
        file_size = file.size if hasattr(file, "size") else 0

        return cls(
            message=message,
            uploaded_by=uploaded_by,
            filename=Path(storage_path).name if storage_path else file.name,
            original_filename=file.name,
            content_type=content_type,
            file_size=file_size,
            storage_path=storage_path or "",
            **kwargs,
        )

    def mark_as_processed(self, thumbnail_url=None, metadata=None):
        """Mark attachment as processed."""
        self.is_processed = True
        if thumbnail_url:
            self.thumbnail_url = thumbnail_url
        if metadata:
            self.metadata.update(metadata)
        self.save(update_fields=["is_processed", "thumbnail_url", "metadata", "updated_at"])

    def mark_scan_result(self, is_safe, scan_result=None):
        """Mark attachment with scan results."""
        self.is_scanned = True
        self.is_safe = is_safe
        if scan_result:
            self.scan_result = scan_result
        self.save(update_fields=["is_scanned", "is_safe", "scan_result", "updated_at"])
