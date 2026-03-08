"""
Notification model.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from django_matt.notifications.enums import (
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
)


class NotificationManager(models.Manager):
    """Custom manager for Notification model."""

    def unread(self):
        """Get unread notifications."""
        return self.filter(read_at__isnull=True, dismissed_at__isnull=True)

    def read(self):
        """Get read notifications."""
        return self.filter(read_at__isnull=False)

    def for_user(self, user):
        """Get notifications for a specific user."""
        return self.filter(recipient=user)

    def unread_for_user(self, user):
        """Get unread notifications for a user."""
        return self.for_user(user).unread()

    def by_type(self, notification_type: NotificationType):
        """Filter by notification type."""
        return self.filter(notification_type=notification_type)


class Notification(models.Model):
    """
    Notification model for in-app and multi-channel notifications.

    Supports:
    - Multiple delivery channels (in-app, email, push, SMS, webhook)
    - Generic relations to any model
    - Priority levels
    - Read/unread tracking
    - Grouping similar notifications
    - Action URLs and CTAs
    """

    # Recipient
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    # Sender (optional - for user-to-user notifications)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )

    # Notification content
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        default=NotificationType.CUSTOM,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL,
    )

    # Related object (generic relation)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    # Action URL
    action_url = models.URLField(blank=True)
    action_label = models.CharField(max_length=50, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Group key for collapsing similar notifications
    group_key = models.CharField(max_length=255, blank=True, db_index=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    # Expiration
    expires_at = models.DateTimeField(null=True, blank=True)

    objects = NotificationManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["recipient", "notification_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["group_key"]),
        ]

    def __str__(self):
        return f"Notification to {self.recipient}: {self.title}"

    @property
    def is_read(self) -> bool:
        """Check if notification is read."""
        return self.read_at is not None

    @property
    def is_dismissed(self) -> bool:
        """Check if notification is dismissed."""
        return self.dismissed_at is not None

    @property
    def is_expired(self) -> bool:
        """Check if notification is expired."""
        if not self.expires_at:
            return False
        from django.utils import timezone

        return timezone.now() > self.expires_at

    def mark_as_read(self) -> None:
        """Mark notification as read."""
        if not self.read_at:
            from django.utils import timezone

            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])

    def mark_as_unread(self) -> None:
        """Mark notification as unread."""
        if self.read_at:
            self.read_at = None
            self.save(update_fields=["read_at"])

    def dismiss(self) -> None:
        """Dismiss notification."""
        if not self.dismissed_at:
            from django.utils import timezone

            self.dismissed_at = timezone.now()
            self.save(update_fields=["dismissed_at"])


class NotificationDelivery(models.Model):
    """
    Tracks delivery status for each channel.

    One notification can be delivered via multiple channels,
    each with its own status and tracking.
    """

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
    )

    # Tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # External references (e.g., email ID, push notification ID)
    external_id = models.CharField(max_length=255, blank=True)

    # Retry tracking
    retry_count = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("notification", "channel")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification} via {self.channel}: {self.status}"

    def mark_sent(self, external_id: str = "") -> None:
        """Mark as sent."""
        from django.utils import timezone

        self.status = NotificationStatus.SENT
        self.sent_at = timezone.now()
        if external_id:
            self.external_id = external_id
        self.save(update_fields=["status", "sent_at", "external_id", "updated_at"])

    def mark_delivered(self) -> None:
        """Mark as delivered."""
        from django.utils import timezone

        self.status = NotificationStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at", "updated_at"])

    def mark_read(self) -> None:
        """Mark as read."""
        from django.utils import timezone

        self.status = NotificationStatus.READ
        self.read_at = timezone.now()
        self.save(update_fields=["status", "read_at", "updated_at"])

    def mark_failed(self, error: str = "") -> None:
        """Mark as failed."""
        from django.utils import timezone

        self.status = NotificationStatus.FAILED
        self.failed_at = timezone.now()
        self.error_message = error
        self.retry_count += 1
        self.save(
            update_fields=[
                "status",
                "failed_at",
                "error_message",
                "retry_count",
                "updated_at",
            ]
        )

    def schedule_retry(self, delay_seconds: int = 300) -> None:
        """Schedule a retry."""
        from datetime import timedelta

        from django.utils import timezone

        self.status = NotificationStatus.PENDING
        self.next_retry_at = timezone.now() + timedelta(seconds=delay_seconds)
        self.save(update_fields=["status", "next_retry_at", "updated_at"])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "channel": self.channel,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }


class PushToken(models.Model):
    """
    Per-device push notification token.

    Stores FCM, APNs, or Web Push tokens for push delivery.
    Users register tokens from their devices; PushDeliveryHandler
    queries active tokens to dispatch notifications.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_tokens",
    )
    token = models.CharField(max_length=512)
    platform = models.CharField(
        max_length=20,
        choices=[("fcm", "FCM"), ("apns", "APNs"), ("web", "Web Push")],
    )
    device_id = models.CharField(max_length=255, blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "token")]

    def __str__(self):
        return f"PushToken({self.platform}) for {self.user}"
