"""
Background tasks for analytics processing.

Provides Celery/Django-Q compatible tasks for:
- Daily/weekly/monthly rollup generation
- Session expiration
- Data cleanup and retention
- Funnel conversion tracking
- Real-time metrics updates

Usage with Celery:
    # celery.py
    from django_matt.analytics.tasks import (
        create_daily_rollups,
        expire_sessions,
        cleanup_old_data,
    )

    # Schedule periodic tasks
    app.conf.beat_schedule = {
        'create-daily-rollups': {
            'task': 'django_matt.analytics.tasks.create_daily_rollups',
            'schedule': crontab(hour=1, minute=0),  # 1 AM daily
        },
        'expire-sessions': {
            'task': 'django_matt.analytics.tasks.expire_sessions',
            'schedule': crontab(minute='*/5'),  # Every 5 minutes
        },
        'cleanup-old-data': {
            'task': 'django_matt.analytics.tasks.cleanup_old_data',
            'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Weekly
        },
    }

Usage with Django-Q:
    from django_q.tasks import schedule

    schedule(
        'django_matt.analytics.tasks.create_daily_rollups_sync',
        schedule_type='D',  # Daily
        minutes=60,  # 1 AM
    )
"""

import asyncio
import logging
from datetime import datetime, timedelta

from django.utils import timezone

logger = logging.getLogger("django_matt.analytics")


# =============================================================================
# Rollup Tasks
# =============================================================================


async def create_daily_rollups_async(date: datetime | None = None) -> dict[str, int]:
    """
    Create daily rollups for user metrics.

    Aggregates events and page views into UserMetric records.

    Args:
        date: Date to create rollups for (defaults to yesterday)

    Returns:
        Dict with counts of created/updated records
    """
    from .aggregations import get_aggregator

    if date is None:
        date = timezone.now() - timedelta(days=1)

    logger.info(f"Creating daily rollups for {date.date()}")

    aggregator = get_aggregator()
    result = await aggregator.create_daily_rollup(date)

    logger.info(f"Daily rollups complete: {result}")
    return result


def create_daily_rollups(date: datetime | None = None) -> dict[str, int]:
    """Sync wrapper for create_daily_rollups_async."""
    return asyncio.run(create_daily_rollups_async(date))


# Make compatible with task runners
create_daily_rollups_sync = create_daily_rollups


async def create_weekly_rollups_async(week_start: datetime | None = None) -> dict[str, int]:
    """
    Create weekly rollups for user metrics.

    Args:
        week_start: Start of the week (defaults to last week)

    Returns:
        Dict with counts of created/updated records
    """
    from .models import UserMetric

    if week_start is None:
        # Get start of last week (Monday)
        today = timezone.now().date()
        days_since_monday = today.weekday()
        week_start = timezone.make_aware(
            datetime.combine(today - timedelta(days=days_since_monday + 7), datetime.min.time())
        )

    week_end = week_start + timedelta(days=7)

    logger.info(f"Creating weekly rollups for {week_start.date()} to {week_end.date()}")

    # Get daily metrics for the week
    daily_metrics = UserMetric.objects.filter(
        period=UserMetric.Period.DAY,
        period_start__gte=week_start.date(),
        period_start__lt=week_end.date(),
    )

    # Aggregate by user
    from collections import defaultdict

    user_data: dict[str, dict] = defaultdict(
        lambda: {
            "total_events": 0,
            "total_page_views": 0,
            "total_sessions": 0,
            "total_time_seconds": 0,
            "events_by_name": defaultdict(int),
        }
    )

    async for metric in daily_metrics:
        user_id = str(metric.user_id)
        user_data[user_id]["total_events"] += metric.total_events
        user_data[user_id]["total_page_views"] += metric.total_page_views
        user_data[user_id]["total_sessions"] += metric.total_sessions
        user_data[user_id]["total_time_seconds"] += metric.total_time_seconds

        for name, count in metric.events_by_name.items():
            user_data[user_id]["events_by_name"][name] += count

    # Create/update weekly metrics
    created_count = 0
    updated_count = 0

    for user_id, data in user_data.items():
        metric, created = await UserMetric.objects.aupdate_or_create(
            user_id=user_id,
            period=UserMetric.Period.WEEK,
            period_start=week_start.date(),
            defaults={
                "period_end": week_end.date(),
                "total_events": data["total_events"],
                "total_page_views": data["total_page_views"],
                "total_sessions": data["total_sessions"],
                "total_time_seconds": data["total_time_seconds"],
                "events_by_name": dict(data["events_by_name"]),
            },
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    result = {"created": created_count, "updated": updated_count}
    logger.info(f"Weekly rollups complete: {result}")
    return result


def create_weekly_rollups(week_start: datetime | None = None) -> dict[str, int]:
    """Sync wrapper for create_weekly_rollups_async."""
    return asyncio.run(create_weekly_rollups_async(week_start))


create_weekly_rollups_sync = create_weekly_rollups


async def create_monthly_rollups_async(month_start: datetime | None = None) -> dict[str, int]:
    """
    Create monthly rollups for user metrics.

    Args:
        month_start: Start of the month (defaults to last month)

    Returns:
        Dict with counts of created/updated records
    """
    from .models import UserMetric

    if month_start is None:
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        month_start = timezone.make_aware(
            datetime.combine(last_month_end.replace(day=1), datetime.min.time())
        )

    # Calculate month end
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)

    logger.info(f"Creating monthly rollups for {month_start.date()} to {month_end.date()}")

    # Get daily metrics for the month
    daily_metrics = UserMetric.objects.filter(
        period=UserMetric.Period.DAY,
        period_start__gte=month_start.date(),
        period_start__lt=month_end.date(),
    )

    # Aggregate by user
    from collections import defaultdict

    user_data: dict[str, dict] = defaultdict(
        lambda: {
            "total_events": 0,
            "total_page_views": 0,
            "total_sessions": 0,
            "total_time_seconds": 0,
            "events_by_name": defaultdict(int),
        }
    )

    async for metric in daily_metrics:
        user_id = str(metric.user_id)
        user_data[user_id]["total_events"] += metric.total_events
        user_data[user_id]["total_page_views"] += metric.total_page_views
        user_data[user_id]["total_sessions"] += metric.total_sessions
        user_data[user_id]["total_time_seconds"] += metric.total_time_seconds

        for name, count in metric.events_by_name.items():
            user_data[user_id]["events_by_name"][name] += count

    # Create/update monthly metrics
    created_count = 0
    updated_count = 0

    for user_id, data in user_data.items():
        metric, created = await UserMetric.objects.aupdate_or_create(
            user_id=user_id,
            period=UserMetric.Period.MONTH,
            period_start=month_start.date(),
            defaults={
                "period_end": month_end.date(),
                "total_events": data["total_events"],
                "total_page_views": data["total_page_views"],
                "total_sessions": data["total_sessions"],
                "total_time_seconds": data["total_time_seconds"],
                "events_by_name": dict(data["events_by_name"]),
            },
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    result = {"created": created_count, "updated": updated_count}
    logger.info(f"Monthly rollups complete: {result}")
    return result


def create_monthly_rollups(month_start: datetime | None = None) -> dict[str, int]:
    """Sync wrapper for create_monthly_rollups_async."""
    return asyncio.run(create_monthly_rollups_async(month_start))


create_monthly_rollups_sync = create_monthly_rollups


# =============================================================================
# Session Management Tasks
# =============================================================================


async def expire_sessions_async(timeout_minutes: int = 30) -> int:
    """
    Expire inactive sessions.

    Args:
        timeout_minutes: Minutes of inactivity before expiration

    Returns:
        Number of sessions expired
    """
    from .models import AnalyticsSession

    count = await AnalyticsSession.objects.expire_old_sessions_async(timeout_minutes)
    logger.info(f"Expired {count} sessions")
    return count


def expire_sessions(timeout_minutes: int = 30) -> int:
    """Expire inactive sessions (sync version)."""
    from .models import AnalyticsSession

    count = AnalyticsSession.objects.expire_old_sessions(timeout_minutes)
    logger.info(f"Expired {count} sessions")
    return count


expire_sessions_sync = expire_sessions


# =============================================================================
# Data Cleanup Tasks
# =============================================================================


async def cleanup_old_data_async(
    events_days: int = 90,
    sessions_days: int = 90,
    page_views_days: int = 90,
) -> dict[str, int]:
    """
    Clean up old analytics data for data retention compliance.

    Args:
        events_days: Delete events older than this
        sessions_days: Delete sessions older than this
        page_views_days: Delete page views older than this

    Returns:
        Dict with counts of deleted records
    """
    from .models import AnalyticsEvent, AnalyticsSession, PageView

    now = timezone.now()
    events_cutoff = now - timedelta(days=events_days)
    sessions_cutoff = now - timedelta(days=sessions_days)
    page_views_cutoff = now - timedelta(days=page_views_days)

    # Delete old events
    events_result = await AnalyticsEvent.objects.filter(timestamp__lt=events_cutoff).adelete()
    events_deleted = events_result[0] if events_result else 0

    # Delete old sessions
    sessions_result = await AnalyticsSession.objects.filter(
        started_at__lt=sessions_cutoff
    ).adelete()
    sessions_deleted = sessions_result[0] if sessions_result else 0

    # Delete old page views
    page_views_result = await PageView.objects.filter(timestamp__lt=page_views_cutoff).adelete()
    page_views_deleted = page_views_result[0] if page_views_result else 0

    result = {
        "events_deleted": events_deleted,
        "sessions_deleted": sessions_deleted,
        "page_views_deleted": page_views_deleted,
    }

    logger.info(f"Data cleanup complete: {result}")
    return result


def cleanup_old_data(
    events_days: int = 90,
    sessions_days: int = 90,
    page_views_days: int = 90,
) -> dict[str, int]:
    """Sync wrapper for cleanup_old_data_async."""
    return asyncio.run(cleanup_old_data_async(events_days, sessions_days, page_views_days))


cleanup_old_data_sync = cleanup_old_data


async def anonymize_old_sessions_async(days: int = 30) -> int:
    """
    Anonymize sessions older than specified days.

    Removes PII from old sessions for GDPR compliance.

    Args:
        days: Anonymize sessions older than this

    Returns:
        Number of sessions anonymized
    """
    from .models import AnalyticsSession, AnonymizationLevel

    cutoff = timezone.now() - timedelta(days=days)

    count = await AnalyticsSession.objects.filter(
        started_at__lt=cutoff,
        anonymization_level=AnonymizationLevel.NONE.value,
    ).aupdate(
        anonymization_level=AnonymizationLevel.PARTIAL.value,
        ip_address=None,
        user_agent="",
    )

    logger.info(f"Anonymized {count} sessions")
    return count


def anonymize_old_sessions(days: int = 30) -> int:
    """Sync wrapper for anonymize_old_sessions_async."""
    return asyncio.run(anonymize_old_sessions_async(days))


anonymize_old_sessions_sync = anonymize_old_sessions


# =============================================================================
# Funnel Processing Tasks
# =============================================================================


async def process_funnel_conversions_async(funnel_id: str | None = None) -> dict[str, int]:
    """
    Process funnel conversions.

    Analyzes events to track user progress through funnels.

    Args:
        funnel_id: Specific funnel to process (all if None)

    Returns:
        Dict with processing counts
    """
    from .models import (
        AnalyticsEvent,
        Funnel,
        FunnelConversion,
        FunnelStep,
        PageView,
    )

    if funnel_id:
        funnels = Funnel.objects.filter(id=funnel_id, is_active=True)
    else:
        funnels = Funnel.objects.filter(is_active=True)

    started_count = 0
    converted_count = 0
    updated_count = 0

    async for funnel in funnels.prefetch_related("steps"):
        steps = [s async for s in funnel.steps.all().order_by("order")]
        if not steps:
            continue

        # Get conversion window
        window_start = timezone.now() - timedelta(hours=funnel.conversion_window_hours)

        # Find users who completed the first step
        first_step = steps[0]

        if first_step.match_type == FunnelStep.MatchType.EVENT:
            first_step_users = set()
            async for event in AnalyticsEvent.objects.filter(
                name=first_step.event_name,
                timestamp__gte=window_start,
                user__isnull=False,
            ).values("user_id"):
                first_step_users.add(event["user_id"])

        elif first_step.match_type == FunnelStep.MatchType.PAGE_VIEW:
            first_step_users = set()
            async for pv in PageView.objects.filter(
                path__startswith=first_step.page_path,
                timestamp__gte=window_start,
                user__isnull=False,
            ).values("user_id"):
                first_step_users.add(pv["user_id"])

        else:
            first_step_users = set()

        # Process each user
        for user_id in first_step_users:
            # Get or create conversion record
            conversion, created = await FunnelConversion.objects.aget_or_create(
                funnel=funnel,
                user_id=user_id,
                is_converted=False,
                defaults={
                    "current_step": 1,
                    "completed_steps": [{"step": 1, "timestamp": timezone.now().isoformat()}],
                },
            )

            if created:
                started_count += 1
            else:
                # Check progress through remaining steps
                current_step_order = conversion.current_step

                for step in steps[current_step_order:]:
                    completed = False

                    if step.match_type == FunnelStep.MatchType.EVENT:
                        completed = await AnalyticsEvent.objects.filter(
                            name=step.event_name,
                            user_id=user_id,
                            timestamp__gte=conversion.started_at,
                        ).aexists()

                    elif step.match_type == FunnelStep.MatchType.PAGE_VIEW:
                        completed = await PageView.objects.filter(
                            path__startswith=step.page_path,
                            user_id=user_id,
                            timestamp__gte=conversion.started_at,
                        ).aexists()

                    if completed:
                        conversion.current_step = step.order
                        conversion.completed_steps.append(
                            {
                                "step": step.order,
                                "timestamp": timezone.now().isoformat(),
                            }
                        )
                        updated_count += 1
                    else:
                        break

                # Check if fully converted
                if conversion.current_step == len(steps):
                    conversion.is_converted = True
                    conversion.converted_at = timezone.now()
                    conversion.total_time_seconds = int(
                        (conversion.converted_at - conversion.started_at).total_seconds()
                    )
                    converted_count += 1

                await conversion.asave()

    result = {
        "started": started_count,
        "converted": converted_count,
        "updated": updated_count,
    }

    logger.info(f"Funnel processing complete: {result}")
    return result


def process_funnel_conversions(funnel_id: str | None = None) -> dict[str, int]:
    """Sync wrapper for process_funnel_conversions_async."""
    return asyncio.run(process_funnel_conversions_async(funnel_id))


process_funnel_conversions_sync = process_funnel_conversions


# =============================================================================
# Redis Flush Tasks
# =============================================================================


async def flush_redis_buffer_async() -> dict[str, int]:
    """
    Flush Redis analytics buffer to database.

    For use with RedisBackend when buffering events.

    Returns:
        Dict with counts of flushed records
    """
    from .backends import get_backend

    backend = get_backend()

    if hasattr(backend, "_flush_to_database"):
        # Assuming Redis backend
        events_flushed = 0
        page_views_flushed = 0

        try:
            backend._flush_to_database("events")
            events_flushed = backend.client.llen(backend._get_key("events", "buffer"))
        except Exception as e:
            logger.error(f"Error flushing events: {e}")

        try:
            backend._flush_to_database("pageviews")
            page_views_flushed = backend.client.llen(backend._get_key("pageviews", "buffer"))
        except Exception as e:
            logger.error(f"Error flushing page views: {e}")

        return {
            "events_flushed": events_flushed,
            "page_views_flushed": page_views_flushed,
        }

    return {"events_flushed": 0, "page_views_flushed": 0}


def flush_redis_buffer() -> dict[str, int]:
    """Sync wrapper for flush_redis_buffer_async."""
    return asyncio.run(flush_redis_buffer_async())


flush_redis_buffer_sync = flush_redis_buffer


__all__ = [
    # Rollup tasks
    "create_daily_rollups",
    "create_daily_rollups_async",
    "create_daily_rollups_sync",
    "create_weekly_rollups",
    "create_weekly_rollups_async",
    "create_weekly_rollups_sync",
    "create_monthly_rollups",
    "create_monthly_rollups_async",
    "create_monthly_rollups_sync",
    # Session tasks
    "expire_sessions",
    "expire_sessions_async",
    "expire_sessions_sync",
    # Cleanup tasks
    "cleanup_old_data",
    "cleanup_old_data_async",
    "cleanup_old_data_sync",
    "anonymize_old_sessions",
    "anonymize_old_sessions_async",
    "anonymize_old_sessions_sync",
    # Funnel tasks
    "process_funnel_conversions",
    "process_funnel_conversions_async",
    "process_funnel_conversions_sync",
    # Redis tasks
    "flush_redis_buffer",
    "flush_redis_buffer_async",
    "flush_redis_buffer_sync",
]
