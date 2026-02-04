"""
Notification service.

Business logic for creating and managing notifications.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from django_matt.notifications.enums import (
    NotificationChannel,
    NotificationPriority,
    NotificationType,
)
from django_matt.notifications.models import (
    Notification,
    NotificationDelivery,
    NotificationPreferences,
)


class NotificationService:
    """Service for managing notifications."""

    @staticmethod
    @transaction.atomic
    def create_notification(
        recipient,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.CUSTOM,
        sender=None,
        content_object=None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        action_url: str = "",
        action_label: str = "",
        metadata: dict[str, Any] | None = None,
        group_key: str = "",
        expires_at=None,
        channels: list[NotificationChannel] | None = None,
        send_immediately: bool = True,
    ) -> Notification:
        """
        Create a notification.

        Args:
            recipient: User to notify
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            sender: Optional sender (for user-to-user notifications)
            content_object: Optional related object
            priority: Priority level
            action_url: Optional action URL
            action_label: Optional action button label
            metadata: Additional metadata
            group_key: Key for grouping similar notifications
            expires_at: Optional expiration datetime
            channels: Specific channels to use (None = use preferences)
            send_immediately: Whether to trigger delivery immediately

        Returns:
            Created notification
        """
        # Build notification data
        notification_data = {
            "recipient": recipient,
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "priority": priority,
            "action_url": action_url,
            "action_label": action_label,
            "metadata": metadata or {},
            "group_key": group_key,
            "expires_at": expires_at,
        }

        if sender:
            notification_data["sender"] = sender

        if content_object:
            notification_data["content_type"] = ContentType.objects.get_for_model(content_object)
            notification_data["object_id"] = content_object.pk

        notification = Notification.objects.create(**notification_data)

        # Create delivery records
        if channels is None:
            channels = NotificationService._get_channels_for_user(recipient, notification_type)

        for channel in channels:
            NotificationDelivery.objects.create(
                notification=notification,
                channel=channel,
            )

        # Trigger delivery
        if send_immediately and channels:
            from django_matt.notifications.services.delivery import DeliveryService

            DeliveryService.deliver_notification(notification)

        return notification

    @staticmethod
    def create_bulk_notifications(
        recipients: list,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.CUSTOM,
        **kwargs,
    ) -> list[Notification]:
        """
        Create notifications for multiple recipients.

        Returns list of created notifications.
        """
        notifications = []
        for recipient in recipients:
            notification = NotificationService.create_notification(
                recipient=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                **kwargs,
            )
            notifications.append(notification)
        return notifications

    @staticmethod
    def _get_channels_for_user(
        user,
        notification_type: NotificationType,
    ) -> list[NotificationChannel]:
        """Get enabled channels for a user and notification type."""
        try:
            preferences = NotificationPreferences.objects.get(user=user)
        except NotificationPreferences.DoesNotExist:
            # Default channels
            return [NotificationChannel.IN_APP, NotificationChannel.EMAIL]

        if preferences.unsubscribed:
            return []

        # Check for type-specific rules
        try:
            rule = preferences.rules.get(notification_type=notification_type)
            if rule.is_muted():
                return []
        except Exception:
            rule = None

        # Check quiet hours for non-urgent notifications
        # Always allow in-app notifications
        channels = []

        # In-app is always allowed unless explicitly disabled
        in_app_enabled = (
            rule.in_app_enabled
            if rule and rule.in_app_enabled is not None
            else preferences.in_app_enabled
        )
        if in_app_enabled:
            channels.append(NotificationChannel.IN_APP)

        # Other channels respect quiet hours
        if not preferences.is_in_quiet_hours():
            email_enabled = (
                rule.email_enabled
                if rule and rule.email_enabled is not None
                else preferences.email_enabled
            )
            if email_enabled:
                channels.append(NotificationChannel.EMAIL)

            push_enabled = (
                rule.push_enabled
                if rule and rule.push_enabled is not None
                else preferences.push_enabled
            )
            if push_enabled:
                channels.append(NotificationChannel.PUSH)

            sms_enabled = (
                rule.sms_enabled
                if rule and rule.sms_enabled is not None
                else preferences.sms_enabled
            )
            if sms_enabled:
                channels.append(NotificationChannel.SMS)

        return channels

    @staticmethod
    def get_notifications(
        user,
        unread_only: bool = False,
        notification_type: NotificationType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """Get notifications for a user."""
        qs = Notification.objects.filter(
            recipient=user,
            dismissed_at__isnull=True,
        )

        # Filter expired
        qs = qs.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))

        if unread_only:
            qs = qs.filter(read_at__isnull=True)

        if notification_type:
            qs = qs.filter(notification_type=notification_type)

        return list(qs[offset : offset + limit])

    @staticmethod
    def get_unread_count(user) -> int:
        """Get count of unread notifications."""
        return (
            Notification.objects.filter(
                recipient=user,
                read_at__isnull=True,
                dismissed_at__isnull=True,
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .count()
        )

    @staticmethod
    def get_unread_counts_by_type(user) -> dict[str, int]:
        """Get unread counts grouped by notification type."""
        counts = (
            Notification.objects.filter(
                recipient=user,
                read_at__isnull=True,
                dismissed_at__isnull=True,
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .values("notification_type")
            .annotate(count=Count("id"))
        )
        return {item["notification_type"]: item["count"] for item in counts}

    @staticmethod
    def mark_as_read(notification: Notification) -> None:
        """Mark a single notification as read."""
        notification.mark_as_read()

    @staticmethod
    def mark_all_as_read(user, notification_type: NotificationType | None = None) -> int:
        """Mark all notifications as read for a user."""
        qs = Notification.objects.filter(
            recipient=user,
            read_at__isnull=True,
        )

        if notification_type:
            qs = qs.filter(notification_type=notification_type)

        count = qs.count()
        qs.update(read_at=timezone.now())
        return count

    @staticmethod
    def dismiss_notification(notification: Notification) -> None:
        """Dismiss a notification."""
        notification.dismiss()

    @staticmethod
    def dismiss_all(user) -> int:
        """Dismiss all notifications for a user."""
        count = Notification.objects.filter(
            recipient=user,
            dismissed_at__isnull=True,
        ).count()

        Notification.objects.filter(
            recipient=user,
            dismissed_at__isnull=True,
        ).update(dismissed_at=timezone.now())

        return count

    @staticmethod
    @transaction.atomic
    def delete_old_notifications(days: int = 90) -> int:
        """Delete notifications older than specified days."""
        cutoff = timezone.now() - timedelta(days=days)
        deleted_count, _ = Notification.objects.filter(created_at__lt=cutoff).delete()
        return deleted_count

    @staticmethod
    def collapse_similar_notifications(
        user,
        group_key: str,
        keep_count: int = 1,
    ) -> int:
        """
        Collapse similar notifications by group key.

        Keeps the most recent ones and dismisses the rest.
        Returns count of collapsed notifications.
        """
        notifications = Notification.objects.filter(
            recipient=user,
            group_key=group_key,
            dismissed_at__isnull=True,
        ).order_by("-created_at")

        ids_to_keep = list(notifications.values_list("id", flat=True)[:keep_count])
        count = notifications.exclude(id__in=ids_to_keep).update(dismissed_at=timezone.now())

        return count


# Convenience functions for common notification types


def notify_mention(
    recipient,
    sender,
    content_object,
    context: str = "",
) -> Notification:
    """Send a mention notification."""
    return NotificationService.create_notification(
        recipient=recipient,
        sender=sender,
        title=f"{sender.get_full_name() or sender.email} mentioned you",
        message=context or "You were mentioned in a discussion",
        notification_type=NotificationType.MENTION,
        content_object=content_object,
        group_key=f"mention:{content_object._meta.model_name}:{content_object.pk}",
    )


def notify_message(
    recipient,
    sender,
    conversation,
    message_preview: str = "",
) -> Notification:
    """Send a new message notification."""
    return NotificationService.create_notification(
        recipient=recipient,
        sender=sender,
        title=f"New message from {sender.get_full_name() or sender.email}",
        message=message_preview[:200] if message_preview else "You have a new message",
        notification_type=NotificationType.MESSAGE,
        content_object=conversation,
        group_key=f"message:conversation:{conversation.pk}",
    )


def notify_invitation(
    recipient,
    sender,
    organization,
    role: str = "member",
) -> Notification:
    """Send an invitation notification."""
    return NotificationService.create_notification(
        recipient=recipient,
        sender=sender,
        title=f"Invitation to join {organization.name}",
        message=f"You've been invited to join {organization.name} as a {role}",
        notification_type=NotificationType.INVITATION,
        content_object=organization,
        priority=NotificationPriority.HIGH,
    )


def notify_system(
    recipient,
    title: str,
    message: str,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    action_url: str = "",
) -> Notification:
    """Send a system notification."""
    return NotificationService.create_notification(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=NotificationType.SYSTEM,
        priority=priority,
        action_url=action_url,
    )
