"""
Notification models for SaaS Starter.

Includes:
- In-app notifications
- Email notification preferences
- Notification templates
- Analytics events
"""

import uuid

from django.db import models
from django.utils import timezone

from core.models import Organization, User


class NotificationType(models.TextChoices):
    """Notification type categories."""

    # Task notifications
    TASK_ASSIGNED = "task_assigned", "Task Assigned"
    TASK_COMPLETED = "task_completed", "Task Completed"
    TASK_COMMENTED = "task_commented", "Task Commented"
    TASK_MENTIONED = "task_mentioned", "Mentioned in Task"
    TASK_DUE_SOON = "task_due_soon", "Task Due Soon"
    TASK_OVERDUE = "task_overdue", "Task Overdue"

    # Project notifications
    PROJECT_CREATED = "project_created", "Project Created"
    PROJECT_UPDATED = "project_updated", "Project Updated"
    PROJECT_MEMBER_ADDED = "project_member_added", "Added to Project"
    PROJECT_MEMBER_REMOVED = "project_member_removed", "Removed from Project"

    # Organization notifications
    ORG_INVITATION = "org_invitation", "Organization Invitation"
    ORG_MEMBER_JOINED = "org_member_joined", "Member Joined Organization"
    ORG_MEMBER_LEFT = "org_member_left", "Member Left Organization"
    ORG_ROLE_CHANGED = "org_role_changed", "Role Changed"

    # Billing notifications
    BILLING_INVOICE = "billing_invoice", "New Invoice"
    BILLING_PAYMENT_FAILED = "billing_payment_failed", "Payment Failed"
    BILLING_SUBSCRIPTION_EXPIRING = "billing_subscription_expiring", "Subscription Expiring"
    BILLING_PLAN_CHANGED = "billing_plan_changed", "Plan Changed"

    # System notifications
    SYSTEM_ANNOUNCEMENT = "system_announcement", "System Announcement"
    SYSTEM_MAINTENANCE = "system_maintenance", "Scheduled Maintenance"


class Notification(models.Model):
    """
    In-app notification model.

    Features:
    - User-targeted notifications
    - Organization context
    - Read/unread tracking
    - Action URLs
    - Rich metadata
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )

    # Notification content
    type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()

    # Actor (who triggered the notification)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_notifications",
    )

    # Related object
    resource_type = models.CharField(max_length=50, blank=True)  # "task", "project", etc.
    resource_id = models.CharField(max_length=255, blank=True)

    # Action
    action_url = models.CharField(max_length=500, blank=True)  # Deep link
    action_label = models.CharField(max_length=100, blank=True)

    # Additional data
    data = models.JSONField(default=dict)

    # Status
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Email status
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"]),
            models.Index(fields=["organization", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.type} for {self.user.email}"

    def mark_as_read(self):
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class NotificationPreference(models.Model):
    """
    User notification preferences.

    Features:
    - Per-type preferences
    - Channel selection (email, in-app, push)
    - Quiet hours
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="notification_preference"
    )

    # Email preferences
    email_enabled = models.BooleanField(default=True)
    email_digest = models.CharField(
        max_length=20,
        choices=[
            ("instant", "Instant"),
            ("daily", "Daily Digest"),
            ("weekly", "Weekly Digest"),
            ("none", "No Email"),
        ],
        default="instant",
    )

    # Push preferences
    push_enabled = models.BooleanField(default=True)

    # In-app preferences
    in_app_enabled = models.BooleanField(default=True)

    # Per-type preferences
    # Format: {"task_assigned": {"email": true, "push": true, "in_app": true}}
    type_preferences = models.JSONField(default=dict)

    # Quiet hours (no notifications between these times)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)  # e.g., 22:00
    quiet_hours_end = models.TimeField(null=True, blank=True)  # e.g., 08:00
    quiet_hours_timezone = models.CharField(max_length=50, default="UTC")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_preferences"

    def __str__(self):
        return f"Preferences for {self.user.email}"

    def should_send(self, notification_type: str, channel: str) -> bool:
        """Check if notification should be sent for type/channel."""
        # Check global settings
        if channel == "email" and not self.email_enabled:
            return False
        if channel == "push" and not self.push_enabled:
            return False
        if channel == "in_app" and not self.in_app_enabled:
            return False

        # Check type-specific settings
        type_pref = self.type_preferences.get(notification_type, {})
        return type_pref.get(channel, True)  # Default to True


class NotificationTemplate(models.Model):
    """
    Notification templates for consistent messaging.

    Features:
    - Type-based templates
    - Variable substitution
    - Multi-language support
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    type = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)

    # Templates
    title_template = models.CharField(max_length=500)
    message_template = models.TextField()

    # Email templates
    email_subject_template = models.CharField(max_length=255, blank=True)
    email_body_template = models.TextField(blank=True)

    # Push notification template
    push_title_template = models.CharField(max_length=100, blank=True)
    push_body_template = models.CharField(max_length=255, blank=True)

    # Variables documentation
    variables = models.JSONField(default=list)  # ["user_name", "task_title", etc.]

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_templates"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AnalyticsEvent(models.Model):
    """
    Analytics event tracking.

    Features:
    - User and session tracking
    - Event properties
    - Page views and actions
    - A/B test tracking
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # User context
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="analytics_events"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_events",
    )
    session_id = models.CharField(max_length=255, blank=True, db_index=True)
    anonymous_id = models.CharField(max_length=255, blank=True, db_index=True)

    # Event details
    event_name = models.CharField(max_length=100, db_index=True)
    event_category = models.CharField(max_length=50, blank=True)  # "page_view", "action", etc.

    # Properties
    properties = models.JSONField(default=dict)

    # Page context
    page_url = models.CharField(max_length=500, blank=True)
    page_title = models.CharField(max_length=255, blank=True)
    referrer = models.CharField(max_length=500, blank=True)

    # Device/browser context
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_type = models.CharField(max_length=20, blank=True)  # "desktop", "mobile", "tablet"
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=2, blank=True)  # ISO country code

    # A/B test context
    experiment_id = models.CharField(max_length=100, blank=True, db_index=True)
    variant = models.CharField(max_length=100, blank=True)

    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_events"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "event_name", "-timestamp"]),
            models.Index(fields=["organization", "event_name", "-timestamp"]),
            models.Index(fields=["experiment_id", "variant", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.event_name} - {self.user or self.anonymous_id}"


class AggregatedMetric(models.Model):
    """
    Pre-aggregated metrics for dashboards.

    Features:
    - Daily/weekly/monthly aggregations
    - Organization-level metrics
    - Fast dashboard queries
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="aggregated_metrics"
    )

    # Metric details
    metric_name = models.CharField(max_length=100, db_index=True)
    metric_value = models.DecimalField(max_digits=20, decimal_places=4)

    # Dimensions
    dimensions = models.JSONField(default=dict)  # {"project_id": "xxx", "status": "done"}

    # Time period
    period_type = models.CharField(
        max_length=20,
        choices=[
            ("hour", "Hourly"),
            ("day", "Daily"),
            ("week", "Weekly"),
            ("month", "Monthly"),
        ],
        db_index=True,
    )
    period_start = models.DateTimeField(db_index=True)
    period_end = models.DateTimeField()

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "aggregated_metrics"
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["organization", "metric_name", "period_type", "-period_start"]),
        ]
        unique_together = [
            ["organization", "metric_name", "period_type", "period_start", "dimensions"]
        ]

    def __str__(self):
        return f"{self.metric_name} - {self.period_type} - {self.period_start}"
