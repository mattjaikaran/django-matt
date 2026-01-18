"""
Django Matt Notifications System.

Full-featured notification system with multiple delivery channels
(in-app, email, push, SMS) and user preferences.
"""

from django_matt.notifications.enums import (
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
)
from django_matt.notifications.models import (
    Notification,
    NotificationDelivery,
    NotificationPreferences,
    NotificationRule,
)
from django_matt.notifications.services import (
    DeliveryService,
    NotificationService,
)

__all__ = [
    # Models
    "Notification",
    "NotificationDelivery",
    "NotificationPreferences",
    "NotificationRule",
    # Enums
    "NotificationType",
    "NotificationChannel",
    "NotificationPriority",
    "NotificationStatus",
    # Services
    "NotificationService",
    "DeliveryService",
]
