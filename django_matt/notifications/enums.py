"""
Notification enums.
"""

from django.db.models import TextChoices


class NotificationType(TextChoices):
    """Type of notification."""

    # System notifications
    SYSTEM = "system", "System"
    ANNOUNCEMENT = "announcement", "Announcement"

    # User interactions
    MENTION = "mention", "Mention"
    FOLLOW = "follow", "Follow"
    LIKE = "like", "Like"
    COMMENT = "comment", "Comment"
    REPLY = "reply", "Reply"

    # Messaging
    MESSAGE = "message", "New Message"
    MESSAGE_REACTION = "message_reaction", "Message Reaction"

    # Team/Organization
    INVITATION = "invitation", "Invitation"
    MEMBER_ADDED = "member_added", "Member Added"
    MEMBER_REMOVED = "member_removed", "Member Removed"
    ROLE_CHANGED = "role_changed", "Role Changed"

    # Content
    CONTENT_SHARED = "content_shared", "Content Shared"
    CONTENT_UPDATED = "content_updated", "Content Updated"

    # Reminders
    REMINDER = "reminder", "Reminder"
    DEADLINE = "deadline", "Deadline"

    # Custom
    CUSTOM = "custom", "Custom"


class NotificationChannel(TextChoices):
    """Delivery channel for notifications."""

    IN_APP = "in_app", "In-App"
    EMAIL = "email", "Email"
    PUSH = "push", "Push Notification"
    SMS = "sms", "SMS"
    WEBHOOK = "webhook", "Webhook"


class NotificationPriority(TextChoices):
    """Priority level of notification."""

    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class NotificationStatus(TextChoices):
    """Delivery status of notification."""

    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    READ = "read", "Read"
    FAILED = "failed", "Failed"
    DISMISSED = "dismissed", "Dismissed"
