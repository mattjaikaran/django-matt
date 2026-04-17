# Notification Delivery

Multi-channel notification delivery pipeline supporting in-app, email, push (FCM/APNs), SMS, and webhook channels with per-user preferences, quiet hours, and per-type rules.

## Quick Start

```python
from django_matt.notifications.models import Notification, NotificationDelivery

# Create a notification
notification = await Notification.objects.acreate(
    recipient=user,
    notification_type="comment",
    title="New comment on your post",
    message="Alice commented: 'Great article!'",
    priority="normal",
)

# Delivery records are created per channel
delivery = await NotificationDelivery.objects.acreate(
    notification=notification,
    channel="in_app",
    status="sent",
)
```

## Configuration

Notification types and channels are defined by enums:

```python
# Available notification types
from django_matt.notifications.enums import NotificationType

NotificationType.SYSTEM        # System notifications
NotificationType.MENTION       # @mentions
NotificationType.FOLLOW        # New followers
NotificationType.LIKE          # Likes
NotificationType.COMMENT       # Comments
NotificationType.REPLY         # Replies
NotificationType.MESSAGE       # New messages
NotificationType.INVITATION    # Team invitations
NotificationType.REMINDER      # Reminders
NotificationType.CUSTOM        # Custom notifications

# Delivery channels
from django_matt.notifications.enums import NotificationChannel

NotificationChannel.IN_APP     # In-app notification bell
NotificationChannel.EMAIL      # Email delivery
NotificationChannel.PUSH       # Push notification (FCM/APNs)
NotificationChannel.SMS        # SMS delivery
NotificationChannel.WEBHOOK    # Webhook callback

# Priority levels
from django_matt.notifications.enums import NotificationPriority

NotificationPriority.LOW
NotificationPriority.NORMAL
NotificationPriority.HIGH
NotificationPriority.URGENT

# Delivery statuses
from django_matt.notifications.enums import NotificationStatus

NotificationStatus.PENDING
NotificationStatus.SENT
NotificationStatus.DELIVERED
NotificationStatus.READ
NotificationStatus.FAILED
NotificationStatus.DISMISSED
```

## Key Features

### Notification Model

The `Notification` model stores notification content and read state:

| Field | Type | Description |
|-------|------|-------------|
| `recipient` | `ForeignKey(User)` | Target user |
| `sender` | `ForeignKey(User)` | Optional sender |
| `notification_type` | `CharField` | Type from `NotificationType` |
| `title` | `CharField` | Notification title |
| `message` | `TextField` | Notification body |
| `priority` | `CharField` | Priority level |
| `read_at` | `DateTimeField` | When read (null = unread) |
| `dismissed_at` | `DateTimeField` | When dismissed |
| `content_type` | `ForeignKey` | Generic relation to source object |
| `object_id` | `PositiveIntegerField` | Source object ID |

### NotificationDelivery Model

Tracks delivery status per channel:

| Field | Type | Description |
|-------|------|-------------|
| `notification` | `ForeignKey` | Parent notification |
| `channel` | `CharField` | Delivery channel |
| `status` | `CharField` | Delivery status |
| `sent_at` | `DateTimeField` | When sent |
| `delivered_at` | `DateTimeField` | When delivered |
| `read_at` | `DateTimeField` | When read |
| `failed_at` | `DateTimeField` | When failed |
| `retry_count` | `PositiveIntegerField` | Number of retries |
| `error_message` | `TextField` | Error details on failure |

### NotificationPreferences Model

Per-user channel preferences with global toggles and per-type overrides:

| Field | Type | Description |
|-------|------|-------------|
| `user` | `OneToOneField(User)` | The user |
| `in_app_enabled` | `BooleanField` | In-app notifications |
| `email_enabled` | `BooleanField` | Email notifications |
| `push_enabled` | `BooleanField` | Push notifications |
| `sms_enabled` | `BooleanField` | SMS notifications |
| `email_frequency` | `CharField` | `instant`, `daily`, `weekly` |
| `quiet_hours_enabled` | `BooleanField` | Enable quiet hours |
| `quiet_hours_start` | `TimeField` | Quiet hours start |
| `quiet_hours_end` | `TimeField` | Quiet hours end |
| `unsubscribed` | `BooleanField` | Global unsubscribe |

### NotificationRule Model

Per-type channel overrides on user preferences:

| Field | Type | Description |
|-------|------|-------------|
| `preferences` | `ForeignKey` | Parent preferences |
| `notification_type` | `CharField` | Notification type to override |
| `in_app_enabled` | `NullBooleanField` | Override in-app (null = use default) |
| `email_enabled` | `NullBooleanField` | Override email |
| `push_enabled` | `NullBooleanField` | Override push |
| `sms_enabled` | `NullBooleanField` | Override SMS |
| `muted` | `BooleanField` | Mute this type entirely |

### Django Admin Integration

Full admin interface with:

- **NotificationAdmin**: List view with recipient, type, title preview, priority, read status. Bulk actions for mark-as-read and dismiss.
- **NotificationDeliveryAdmin**: Channel, status, timing, retry tracking with inline on notifications.
- **NotificationPreferencesAdmin**: Channel summary, frequency, quiet hours with inline rules.
- **NotificationRuleAdmin**: Per-type channel overrides with mute toggle.

## Practical Example

A notification service that respects user preferences:

```python
from django_matt.notifications.models import (
    Notification,
    NotificationDelivery,
    NotificationPreferences,
    NotificationRule,
)
from django_matt.notifications.enums import (
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)


async def send_notification(
    recipient,
    notification_type: str,
    title: str,
    message: str,
    sender=None,
    priority: str = "normal",
) -> Notification:
    # Create the notification
    notification = await Notification.objects.acreate(
        recipient=recipient,
        sender=sender,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
    )

    # Check user preferences
    prefs, _ = await NotificationPreferences.objects.aget_or_create(user=recipient)

    if prefs.unsubscribed:
        return notification

    # Determine which channels to use
    channels = []
    if prefs.in_app_enabled:
        channels.append(NotificationChannel.IN_APP)
    if prefs.email_enabled:
        channels.append(NotificationChannel.EMAIL)
    if prefs.push_enabled:
        channels.append(NotificationChannel.PUSH)

    # Check per-type overrides
    try:
        rule = await NotificationRule.objects.aget(
            preferences=prefs,
            notification_type=notification_type,
        )
        if rule.muted:
            return notification
        # Apply overrides (non-null values override global preference)
        if rule.email_enabled is False:
            channels = [c for c in channels if c != NotificationChannel.EMAIL]
    except NotificationRule.DoesNotExist:
        pass

    # Create delivery records for each channel
    for channel in channels:
        await NotificationDelivery.objects.acreate(
            notification=notification,
            channel=channel,
            status=NotificationStatus.PENDING,
        )

    return notification
```
