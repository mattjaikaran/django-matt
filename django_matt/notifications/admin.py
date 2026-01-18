"""
Django admin configuration for notification models.
"""

from django.contrib import admin
from django.utils.html import format_html

from django_matt.notifications.models import (
    Notification,
    NotificationDelivery,
    NotificationPreferences,
    NotificationRule,
)


class NotificationDeliveryInline(admin.TabularInline):
    """Inline for notification deliveries."""

    model = NotificationDelivery
    extra = 0
    readonly_fields = (
        "sent_at",
        "delivered_at",
        "read_at",
        "failed_at",
        "retry_count",
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin for Notification model."""

    list_display = (
        "id",
        "recipient",
        "notification_type",
        "title_preview",
        "priority",
        "read_status",
        "created_at",
    )
    list_filter = (
        "notification_type",
        "priority",
        ("read_at", admin.EmptyFieldListFilter),
        ("dismissed_at", admin.EmptyFieldListFilter),
        "created_at",
    )
    search_fields = (
        "title",
        "message",
        "recipient__email",
        "recipient__first_name",
        "recipient__last_name",
    )
    raw_id_fields = ("recipient", "sender", "content_type")
    readonly_fields = (
        "created_at",
        "read_at",
        "dismissed_at",
    )
    inlines = [NotificationDeliveryInline]
    date_hierarchy = "created_at"

    @admin.display(description="Title")
    def title_preview(self, obj):
        """Display truncated title."""
        title = obj.title
        if len(title) > 40:
            return title[:40] + "..."
        return title

    @admin.display(description="Status")
    def read_status(self, obj):
        """Display read/unread status."""
        if obj.dismissed_at:
            return format_html(
                '<span style="color: #999;">Dismissed</span>'
            )
        if obj.read_at:
            return format_html(
                '<span style="color: #28a745;">Read</span>'
            )
        return format_html(
            '<span style="color: #007bff; font-weight: bold;">Unread</span>'
        )

    actions = ["mark_as_read", "mark_as_dismissed"]

    @admin.action(description="Mark selected notifications as read")
    def mark_as_read(self, request, queryset):
        from django.utils import timezone

        count = queryset.filter(read_at__isnull=True).update(read_at=timezone.now())
        self.message_user(request, f"Marked {count} notifications as read")

    @admin.action(description="Dismiss selected notifications")
    def mark_as_dismissed(self, request, queryset):
        from django.utils import timezone

        count = queryset.filter(dismissed_at__isnull=True).update(
            dismissed_at=timezone.now()
        )
        self.message_user(request, f"Dismissed {count} notifications")


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    """Admin for NotificationDelivery model."""

    list_display = (
        "id",
        "notification",
        "channel",
        "status",
        "sent_at",
        "delivered_at",
        "retry_count",
    )
    list_filter = (
        "channel",
        "status",
        "sent_at",
    )
    raw_id_fields = ("notification",)
    readonly_fields = (
        "sent_at",
        "delivered_at",
        "read_at",
        "failed_at",
        "created_at",
        "updated_at",
    )


class NotificationRuleInline(admin.TabularInline):
    """Inline for notification rules."""

    model = NotificationRule
    extra = 0


@admin.register(NotificationPreferences)
class NotificationPreferencesAdmin(admin.ModelAdmin):
    """Admin for NotificationPreferences model."""

    list_display = (
        "id",
        "user",
        "channel_summary",
        "email_frequency",
        "quiet_hours_enabled",
        "unsubscribed",
    )
    list_filter = (
        "in_app_enabled",
        "email_enabled",
        "push_enabled",
        "sms_enabled",
        "email_frequency",
        "quiet_hours_enabled",
        "unsubscribed",
    )
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
    )
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at", "unsubscribed_at")
    inlines = [NotificationRuleInline]

    @admin.display(description="Channels")
    def channel_summary(self, obj):
        """Display enabled channels."""
        channels = []
        if obj.in_app_enabled:
            channels.append("In-App")
        if obj.email_enabled:
            channels.append("Email")
        if obj.push_enabled:
            channels.append("Push")
        if obj.sms_enabled:
            channels.append("SMS")

        if obj.unsubscribed:
            return format_html('<span style="color: #dc3545;">Unsubscribed</span>')
        return ", ".join(channels) if channels else "None"


@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    """Admin for NotificationRule model."""

    list_display = (
        "id",
        "preferences",
        "notification_type",
        "channel_overrides",
        "muted",
    )
    list_filter = (
        "notification_type",
        "muted",
    )
    raw_id_fields = ("preferences",)

    @admin.display(description="Overrides")
    def channel_overrides(self, obj):
        """Display channel overrides."""
        overrides = []
        if obj.in_app_enabled is not None:
            overrides.append(f"In-App: {'✓' if obj.in_app_enabled else '✗'}")
        if obj.email_enabled is not None:
            overrides.append(f"Email: {'✓' if obj.email_enabled else '✗'}")
        if obj.push_enabled is not None:
            overrides.append(f"Push: {'✓' if obj.push_enabled else '✗'}")
        if obj.sms_enabled is not None:
            overrides.append(f"SMS: {'✓' if obj.sms_enabled else '✗'}")
        return ", ".join(overrides) if overrides else "None"
