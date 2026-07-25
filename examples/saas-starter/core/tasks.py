"""
Celery tasks for core app.

Includes:
- Token cleanup
- User activity tracking
"""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def cleanup_expired_tokens():
    """
    Clean up expired magic link and other tokens.

    Runs hourly.
    """
    from core.models import MagicLinkToken

    cutoff = timezone.now() - timedelta(hours=24)

    # Delete expired magic link tokens
    deleted, _ = MagicLinkToken.objects.filter(created_at__lt=cutoff).delete()

    return f"Deleted {deleted} expired tokens"


@shared_task
def cleanup_old_audit_logs():
    """
    Clean up old audit logs (keep last 1 year).

    Runs weekly.
    """
    from core.models import AuditLog

    cutoff = timezone.now() - timedelta(days=365)
    deleted, _ = AuditLog.objects.filter(created_at__lt=cutoff).delete()

    return f"Deleted {deleted} old audit logs"


@shared_task
def update_user_activity_stats():
    """
    Update aggregated user activity statistics.

    Runs daily.
    """
    from django.db.models import Count

    from core.models import User
    from notifications.models import AnalyticsEvent

    yesterday = timezone.now().date() - timedelta(days=1)

    # Get active users from yesterday
    active_users = (
        AnalyticsEvent.objects.filter(
            timestamp__date=yesterday,
            user__isnull=False,
        )
        .values("user")
        .annotate(event_count=Count("id"))
    )

    # Update last activity for these users
    for activity in active_users:
        User.objects.filter(id=activity["user"]).update(last_activity_at=timezone.now())

    return f"Updated activity for {len(active_users)} users"
