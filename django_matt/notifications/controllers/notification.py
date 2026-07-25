# file-length-max: 500
"""
Notification controller.

REST API endpoints for notification operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.http import HttpRequest

from pydantic import BaseModel, Field

from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError
from django_matt.notifications.enums import NotificationType
from django_matt.notifications.models import (
    Notification,
    NotificationPreferences,
    NotificationRule,
)
from django_matt.notifications.services import NotificationService
from django_matt.permissions import IsAuthenticated


# Request/Response Schemas
class NotificationSchema(BaseModel):
    """Schema for notification response."""

    id: int
    notification_type: str
    title: str
    message: str
    priority: str
    action_url: str
    action_label: str
    sender_id: int | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None
    metadata: dict[str, Any]

    model_config = {"from_attributes": True}


class NotificationListSchema(BaseModel):
    """Schema for notification list response."""

    notifications: list[NotificationSchema]
    unread_count: int
    total: int


class MarkReadSchema(BaseModel):
    """Schema for marking notifications as read."""

    notification_ids: list[int] | None = None
    notification_type: str | None = None
    all: bool = False


class PreferencesSchema(BaseModel):
    """Schema for notification preferences."""

    in_app_enabled: bool = True
    email_enabled: bool = True
    push_enabled: bool = True
    sms_enabled: bool = False
    email_frequency: str = "instant"
    email_digest_time: str | None = None
    quiet_hours_enabled: bool = False
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    push_sound_enabled: bool = True
    push_vibration_enabled: bool = True


class UpdatePreferencesSchema(BaseModel):
    """Schema for updating notification preferences."""

    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    push_enabled: bool | None = None
    sms_enabled: bool | None = None
    email_frequency: str | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    push_sound_enabled: bool | None = None
    push_vibration_enabled: bool | None = None


class NotificationRuleSchema(BaseModel):
    """Schema for notification rule."""

    notification_type: str
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    push_enabled: bool | None = None
    sms_enabled: bool | None = None
    muted: bool = False
    muted_until: datetime | None = None


class UnreadCountSchema(BaseModel):
    """Schema for unread count response."""

    total: int
    by_type: dict[str, int] = Field(default_factory=dict)


class NotificationController(APIController):
    """Controller for notification operations."""

    tags = ["Notifications"]
    permission_classes = [IsAuthenticated]

    def list(self, request: HttpRequest) -> NotificationListSchema:
        """
        List notifications for the current user.

        Query params:
        - unread_only: Only return unread notifications
        - type: Filter by notification type
        - limit: Maximum number to return (default 50)
        - offset: Pagination offset
        """
        unread_only = request.GET.get("unread_only", "false").lower() == "true"
        notification_type = request.GET.get("type")
        limit = min(int(request.GET.get("limit", 50)), 100)
        offset = int(request.GET.get("offset", 0))

        type_filter = None
        if notification_type:
            try:
                type_filter = NotificationType(notification_type)
            except ValueError:
                pass

        notifications = NotificationService.get_notifications(
            user=request.user,
            unread_only=unread_only,
            notification_type=type_filter,
            limit=limit,
            offset=offset,
        )

        unread_count = NotificationService.get_unread_count(request.user)

        return NotificationListSchema(
            notifications=[self._notification_to_schema(n) for n in notifications],
            unread_count=unread_count,
            total=len(notifications),
        )

    def get(self, request: HttpRequest, notification_id: int) -> NotificationSchema:
        """Get a specific notification."""
        notification = self._get_notification(notification_id, request.user)
        return self._notification_to_schema(notification)

    def mark_read(self, request: HttpRequest, data: MarkReadSchema) -> dict[str, Any]:
        """
        Mark notifications as read.

        Can mark:
        - Specific notifications by ID
        - All notifications of a type
        - All notifications
        """
        count = 0

        if data.all:
            count = NotificationService.mark_all_as_read(request.user)
        elif data.notification_type:
            try:
                type_filter = NotificationType(data.notification_type)
                count = NotificationService.mark_all_as_read(request.user, type_filter)
            except ValueError:
                pass
        elif data.notification_ids:
            for nid in data.notification_ids:
                try:
                    notification = Notification.objects.get(
                        id=nid,
                        recipient=request.user,
                    )
                    notification.mark_as_read()
                    count += 1
                except Notification.DoesNotExist:
                    pass

        return {"success": True, "marked_count": count}

    def dismiss(
        self,
        request: HttpRequest,
        notification_id: int,
    ) -> dict[str, bool]:
        """Dismiss a notification."""
        notification = self._get_notification(notification_id, request.user)
        notification.dismiss()
        return {"success": True}

    def dismiss_all(self, request: HttpRequest) -> dict[str, Any]:
        """Dismiss all notifications."""
        count = NotificationService.dismiss_all(request.user)
        return {"success": True, "dismissed_count": count}

    def unread_count(self, request: HttpRequest) -> UnreadCountSchema:
        """Get unread notification counts."""
        total = NotificationService.get_unread_count(request.user)
        by_type = NotificationService.get_unread_counts_by_type(request.user)

        return UnreadCountSchema(
            total=total,
            by_type=by_type,
        )

    def get_preferences(self, request: HttpRequest) -> PreferencesSchema:
        """Get notification preferences for the current user."""
        prefs = NotificationPreferences.get_or_create_for_user(request.user)

        return PreferencesSchema(
            in_app_enabled=prefs.in_app_enabled,
            email_enabled=prefs.email_enabled,
            push_enabled=prefs.push_enabled,
            sms_enabled=prefs.sms_enabled,
            email_frequency=prefs.email_frequency,
            email_digest_time=(
                prefs.email_digest_time.isoformat() if prefs.email_digest_time else None
            ),
            quiet_hours_enabled=prefs.quiet_hours_enabled,
            quiet_hours_start=(
                prefs.quiet_hours_start.isoformat() if prefs.quiet_hours_start else None
            ),
            quiet_hours_end=(prefs.quiet_hours_end.isoformat() if prefs.quiet_hours_end else None),
            push_sound_enabled=prefs.push_sound_enabled,
            push_vibration_enabled=prefs.push_vibration_enabled,
        )

    def update_preferences(
        self,
        request: HttpRequest,
        data: UpdatePreferencesSchema,
    ) -> PreferencesSchema:
        """Update notification preferences."""
        prefs = NotificationPreferences.get_or_create_for_user(request.user)

        # Update fields that are provided
        update_fields = []

        if data.in_app_enabled is not None:
            prefs.in_app_enabled = data.in_app_enabled
            update_fields.append("in_app_enabled")

        if data.email_enabled is not None:
            prefs.email_enabled = data.email_enabled
            update_fields.append("email_enabled")

        if data.push_enabled is not None:
            prefs.push_enabled = data.push_enabled
            update_fields.append("push_enabled")

        if data.sms_enabled is not None:
            prefs.sms_enabled = data.sms_enabled
            update_fields.append("sms_enabled")

        if data.email_frequency is not None:
            prefs.email_frequency = data.email_frequency
            update_fields.append("email_frequency")

        if data.quiet_hours_enabled is not None:
            prefs.quiet_hours_enabled = data.quiet_hours_enabled
            update_fields.append("quiet_hours_enabled")

        if data.quiet_hours_start is not None:
            from datetime import time

            prefs.quiet_hours_start = time.fromisoformat(data.quiet_hours_start)
            update_fields.append("quiet_hours_start")

        if data.quiet_hours_end is not None:
            from datetime import time

            prefs.quiet_hours_end = time.fromisoformat(data.quiet_hours_end)
            update_fields.append("quiet_hours_end")

        if data.push_sound_enabled is not None:
            prefs.push_sound_enabled = data.push_sound_enabled
            update_fields.append("push_sound_enabled")

        if data.push_vibration_enabled is not None:
            prefs.push_vibration_enabled = data.push_vibration_enabled
            update_fields.append("push_vibration_enabled")

        if update_fields:
            update_fields.append("updated_at")
            prefs.save(update_fields=update_fields)

        return self.get_preferences(request)

    def get_rules(self, request: HttpRequest) -> list[NotificationRuleSchema]:
        """Get notification rules for the current user."""
        prefs = NotificationPreferences.get_or_create_for_user(request.user)
        rules = prefs.rules.all()

        return [
            NotificationRuleSchema(
                notification_type=rule.notification_type,
                in_app_enabled=rule.in_app_enabled,
                email_enabled=rule.email_enabled,
                push_enabled=rule.push_enabled,
                sms_enabled=rule.sms_enabled,
                muted=rule.muted,
                muted_until=rule.muted_until,
            )
            for rule in rules
        ]

    def set_rule(
        self,
        request: HttpRequest,
        data: NotificationRuleSchema,
    ) -> NotificationRuleSchema:
        """Create or update a notification rule."""
        prefs = NotificationPreferences.get_or_create_for_user(request.user)

        rule, _ = NotificationRule.objects.update_or_create(
            preferences=prefs,
            notification_type=data.notification_type,
            defaults={
                "in_app_enabled": data.in_app_enabled,
                "email_enabled": data.email_enabled,
                "push_enabled": data.push_enabled,
                "sms_enabled": data.sms_enabled,
                "muted": data.muted,
                "muted_until": data.muted_until,
            },
        )

        return NotificationRuleSchema(
            notification_type=rule.notification_type,
            in_app_enabled=rule.in_app_enabled,
            email_enabled=rule.email_enabled,
            push_enabled=rule.push_enabled,
            sms_enabled=rule.sms_enabled,
            muted=rule.muted,
            muted_until=rule.muted_until,
        )

    def delete_rule(
        self,
        request: HttpRequest,
        notification_type: str,
    ) -> dict[str, bool]:
        """Delete a notification rule."""
        prefs = NotificationPreferences.get_or_create_for_user(request.user)

        deleted, _ = NotificationRule.objects.filter(
            preferences=prefs,
            notification_type=notification_type,
        ).delete()

        return {"success": deleted > 0}

    def unsubscribe(self, request: HttpRequest) -> dict[str, bool]:
        """Unsubscribe from all notifications."""
        from django.utils import timezone

        prefs = NotificationPreferences.get_or_create_for_user(request.user)
        prefs.unsubscribed = True
        prefs.unsubscribed_at = timezone.now()
        prefs.save(update_fields=["unsubscribed", "unsubscribed_at", "updated_at"])

        return {"success": True}

    def resubscribe(self, request: HttpRequest) -> dict[str, bool]:
        """Resubscribe to notifications."""
        prefs = NotificationPreferences.get_or_create_for_user(request.user)
        prefs.unsubscribed = False
        prefs.unsubscribed_at = None
        prefs.save(update_fields=["unsubscribed", "unsubscribed_at", "updated_at"])

        return {"success": True}

    # Helper methods

    def _get_notification(self, notification_id: int, user) -> Notification:
        """Get notification and verify ownership."""
        try:
            return Notification.objects.get(id=notification_id, recipient=user)
        except Notification.DoesNotExist:
            raise NotFoundAPIError("Notification not found", resource_type="Notification")

    def _notification_to_schema(self, notification: Notification) -> NotificationSchema:
        """Convert notification to schema."""
        return NotificationSchema(
            id=notification.id,
            notification_type=notification.notification_type,
            title=notification.title,
            message=notification.message,
            priority=notification.priority,
            action_url=notification.action_url,
            action_label=notification.action_label,
            sender_id=notification.sender_id if notification.sender else None,
            is_read=notification.is_read,
            created_at=notification.created_at,
            read_at=notification.read_at,
            metadata=notification.metadata,
        )
