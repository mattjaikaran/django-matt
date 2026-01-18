"""
Notification preferences model.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from django_matt.notifications.enums import (
    NotificationChannel,
    NotificationType,
)


class NotificationPreferences(models.Model):
    """
    User notification preferences.

    Global settings for notification delivery channels.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )

    # Global channel enablement
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)

    # Email preferences
    email_frequency = models.CharField(
        max_length=20,
        choices=[
            ("instant", "Instant"),
            ("daily", "Daily Digest"),
            ("weekly", "Weekly Digest"),
            ("never", "Never"),
        ],
        default="instant",
    )
    email_digest_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Time of day to send digest (for daily/weekly)",
    )

    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    # Push preferences
    push_sound_enabled = models.BooleanField(default=True)
    push_vibration_enabled = models.BooleanField(default=True)

    # Unsubscribe from all
    unsubscribed = models.BooleanField(default=False)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Notification preferences"

    def __str__(self):
        return f"Notification preferences for {self.user}"

    def is_channel_enabled(self, channel: NotificationChannel) -> bool:
        """Check if a specific channel is enabled."""
        if self.unsubscribed:
            return False

        channel_map = {
            NotificationChannel.IN_APP: self.in_app_enabled,
            NotificationChannel.EMAIL: self.email_enabled,
            NotificationChannel.PUSH: self.push_enabled,
            NotificationChannel.SMS: self.sms_enabled,
        }
        return channel_map.get(channel, False)

    def is_in_quiet_hours(self) -> bool:
        """Check if currently in quiet hours."""
        if not self.quiet_hours_enabled:
            return False

        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False

        from django.utils import timezone

        now = timezone.localtime().time()

        # Handle overnight quiet hours (e.g., 22:00 - 08:00)
        if self.quiet_hours_start > self.quiet_hours_end:
            return now >= self.quiet_hours_start or now <= self.quiet_hours_end
        return self.quiet_hours_start <= now <= self.quiet_hours_end

    def get_enabled_channels(self) -> list[NotificationChannel]:
        """Get list of enabled notification channels."""
        if self.unsubscribed:
            return []

        channels = []
        if self.in_app_enabled:
            channels.append(NotificationChannel.IN_APP)
        if self.email_enabled and self.email_frequency != "never":
            channels.append(NotificationChannel.EMAIL)
        if self.push_enabled:
            channels.append(NotificationChannel.PUSH)
        if self.sms_enabled:
            channels.append(NotificationChannel.SMS)

        return channels

    @classmethod
    def get_or_create_for_user(cls, user) -> NotificationPreferences:
        """Get or create preferences for a user."""
        preferences, _ = cls.objects.get_or_create(user=user)
        return preferences


class NotificationRule(models.Model):
    """
    Per-type notification rules.

    Allows users to customize delivery for specific notification types.
    """

    preferences = models.ForeignKey(
        NotificationPreferences,
        on_delete=models.CASCADE,
        related_name="rules",
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
    )

    # Channel overrides (null = use global preference)
    in_app_enabled = models.BooleanField(null=True, blank=True)
    email_enabled = models.BooleanField(null=True, blank=True)
    push_enabled = models.BooleanField(null=True, blank=True)
    sms_enabled = models.BooleanField(null=True, blank=True)

    # Completely mute this type
    muted = models.BooleanField(default=False)
    muted_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("preferences", "notification_type")]

    def __str__(self):
        return f"Rule for {self.notification_type} ({self.preferences.user})"

    def is_muted(self) -> bool:
        """Check if this notification type is muted."""
        if not self.muted:
            return False

        if self.muted_until:
            from django.utils import timezone

            if timezone.now() > self.muted_until:
                # Mute has expired
                self.muted = False
                self.muted_until = None
                self.save(update_fields=["muted", "muted_until"])
                return False

        return True

    def is_channel_enabled(
        self,
        channel: NotificationChannel,
        global_enabled: bool,
    ) -> bool:
        """
        Check if channel is enabled for this notification type.

        Uses the rule-specific setting if set, otherwise falls back to global.
        """
        if self.is_muted():
            return False

        channel_field_map = {
            NotificationChannel.IN_APP: "in_app_enabled",
            NotificationChannel.EMAIL: "email_enabled",
            NotificationChannel.PUSH: "push_enabled",
            NotificationChannel.SMS: "sms_enabled",
        }

        field_name = channel_field_map.get(channel)
        if not field_name:
            return False

        rule_value = getattr(self, field_name, None)

        # If rule has explicit setting, use it; otherwise use global
        if rule_value is not None:
            return rule_value
        return global_enabled
