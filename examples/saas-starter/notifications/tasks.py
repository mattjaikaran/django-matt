"""
Celery tasks for notifications and analytics.

Includes:
- Email notifications
- Weekly digest
- Analytics aggregation
"""

from datetime import timedelta
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone


@shared_task(bind=True, max_retries=3)
def send_notification_email(self, notification_id: str):
    """
    Send email for a notification.

    Args:
        notification_id: UUID of the notification to send
    """
    from notifications.models import Notification, NotificationPreference

    try:
        notification = Notification.objects.select_related("user").get(id=notification_id)

        # Check if user wants email notifications
        try:
            prefs = NotificationPreference.objects.get(user=notification.user)
            if not prefs.email_enabled:
                return
            if not prefs.should_send(notification.type, "email"):
                return
        except NotificationPreference.DoesNotExist:
            pass  # Default to sending

        # Build email
        subject = notification.title
        context = {
            "notification": notification,
            "user": notification.user,
            "action_url": notification.action_url,
        }

        html_content = render_to_string("emails/notification.html", context)
        text_content = f"{notification.title}\n\n{notification.message}"

        # Send email
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.user.email],
            html_message=html_content,
            fail_silently=False,
        )

        # Mark as sent
        notification.email_sent = True
        notification.email_sent_at = timezone.now()
        notification.save(update_fields=["email_sent", "email_sent_at"])

    except Notification.DoesNotExist:
        pass  # Notification was deleted
    except Exception as exc:
        # Retry on failure
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task
def send_weekly_digest():
    """
    Send weekly digest emails to users.

    Runs every Monday at 9am.
    """
    from core.models import User
    from notifications.models import Notification, NotificationPreference

    # Get start of last week
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    # Get users who want weekly digest
    for user in User.objects.filter(is_active=True):
        try:
            prefs = NotificationPreference.objects.get(user=user)
            if prefs.email_digest != "weekly":
                continue
        except NotificationPreference.DoesNotExist:
            continue  # Skip users without preferences set to weekly

        # Get unread notifications from the past week
        notifications = Notification.objects.filter(
            user=user,
            created_at__gte=week_ago,
        ).order_by("-created_at")[:20]

        if not notifications.exists():
            continue

        # Build digest email
        context = {
            "user": user,
            "notifications": notifications,
            "notification_count": notifications.count(),
            "week_start": week_ago,
            "week_end": today,
        }

        html_content = render_to_string("emails/weekly_digest.html", context)
        text_content = f"Weekly Digest: {notifications.count()} notifications this week"

        send_mail(
            subject=f"Your weekly summary - {notifications.count()} updates",
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content,
            fail_silently=True,
        )


@shared_task
def aggregate_analytics():
    """
    Aggregate analytics data for dashboards.

    Runs daily at midnight.
    """
    from notifications.models import AnalyticsEvent, AggregatedMetric
    from core.models import Organization
    from django.db.models import Count, F
    from django.db.models.functions import TruncDay

    yesterday = timezone.now().date() - timedelta(days=1)
    period_start = timezone.make_aware(
        timezone.datetime.combine(yesterday, timezone.datetime.min.time())
    )
    period_end = timezone.make_aware(
        timezone.datetime.combine(yesterday, timezone.datetime.max.time())
    )

    # Aggregate by organization
    for org in Organization.objects.filter(is_active=True):
        events = AnalyticsEvent.objects.filter(
            organization=org,
            timestamp__gte=period_start,
            timestamp__lte=period_end,
        )

        # Total events
        total_events = events.count()
        AggregatedMetric.objects.update_or_create(
            organization=org,
            metric_name="total_events",
            period_type="day",
            period_start=period_start,
            defaults={
                "metric_value": total_events,
                "period_end": period_end,
            },
        )

        # Unique users
        unique_users = events.values("user").distinct().count()
        AggregatedMetric.objects.update_or_create(
            organization=org,
            metric_name="unique_users",
            period_type="day",
            period_start=period_start,
            defaults={
                "metric_value": unique_users,
                "period_end": period_end,
            },
        )

        # Page views
        page_views = events.filter(event_name="page_view").count()
        AggregatedMetric.objects.update_or_create(
            organization=org,
            metric_name="page_views",
            period_type="day",
            period_start=period_start,
            defaults={
                "metric_value": page_views,
                "period_end": period_end,
            },
        )

        # Events by type
        for event_stat in events.values("event_name").annotate(count=Count("id")):
            AggregatedMetric.objects.update_or_create(
                organization=org,
                metric_name=f"event_{event_stat['event_name']}",
                period_type="day",
                period_start=period_start,
                defaults={
                    "metric_value": event_stat["count"],
                    "period_end": period_end,
                },
            )


@shared_task
def cleanup_old_analytics():
    """
    Clean up old analytics events (keep last 90 days).

    Runs weekly.
    """
    from notifications.models import AnalyticsEvent

    cutoff = timezone.now() - timedelta(days=90)
    deleted, _ = AnalyticsEvent.objects.filter(timestamp__lt=cutoff).delete()

    return f"Deleted {deleted} old analytics events"


@shared_task(bind=True, max_retries=3)
def send_invitation_email(self, invitation_id: str):
    """
    Send organization invitation email.

    Args:
        invitation_id: UUID of the invitation
    """
    from core.models import Invitation

    try:
        invitation = Invitation.objects.select_related(
            "organization", "invited_by"
        ).get(id=invitation_id)

        if invitation.status != "pending":
            return

        # Build email
        context = {
            "invitation": invitation,
            "organization": invitation.organization,
            "invited_by": invitation.invited_by,
            "accept_url": f"{settings.FRONTEND_URL}/invitations/accept?token={invitation.token}",
        }

        html_content = render_to_string("emails/invitation.html", context)
        text_content = (
            f"You've been invited to join {invitation.organization.name}\n\n"
            f"Accept your invitation: {context['accept_url']}"
        )

        send_mail(
            subject=f"You've been invited to join {invitation.organization.name}",
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            html_message=html_content,
            fail_silently=False,
        )

    except Invitation.DoesNotExist:
        pass
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task
def send_overdue_task_notifications():
    """
    Send notifications for overdue tasks.

    Runs daily.
    """
    from projects.models import Task, TaskStatus
    from notifications.models import Notification, NotificationType

    today = timezone.now().date()

    # Find overdue tasks
    overdue_tasks = Task.objects.filter(
        due_date__lt=today,
        status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW],
    ).select_related("assignee", "project")

    for task in overdue_tasks:
        if task.assignee:
            # Check if we already sent this notification today
            existing = Notification.objects.filter(
                user=task.assignee,
                type=NotificationType.TASK_OVERDUE,
                resource_type="task",
                resource_id=str(task.id),
                created_at__date=today,
            ).exists()

            if not existing:
                Notification.objects.create(
                    user=task.assignee,
                    organization=task.project.organization,
                    type=NotificationType.TASK_OVERDUE,
                    title="Task is overdue",
                    message=f'"{task.title}" was due on {task.due_date}',
                    resource_type="task",
                    resource_id=str(task.id),
                    action_url=f"/projects/{task.project.slug}/tasks/{task.id}",
                )
