"""
Analytics aggregation and metrics calculation.

Provides functions for computing:
- Daily/weekly/monthly rollups
- Funnel analysis
- Cohort analysis
- Retention calculations
- Real-time metrics

Usage:
    from django_matt.analytics.aggregations import get_aggregator

    aggregator = get_aggregator()

    # Get dashboard metrics
    metrics = await aggregator.get_event_metrics(start, end)

    # Analyze funnel
    analysis = await aggregator.analyze_funnel(funnel, start, end)

    # Cohort analysis
    cohorts = await aggregator.get_cohort_retention(start, end)
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.utils import timezone

if TYPE_CHECKING:
    from .models import Funnel

logger = logging.getLogger("django_matt.analytics")


class Aggregator:
    """
    Analytics aggregation engine.

    Computes metrics, rollups, and analyses from raw analytics data.
    """

    def __init__(self):
        """Initialize aggregator."""

    # =========================================================================
    # Event Metrics
    # =========================================================================

    async def get_event_metrics(
        self,
        start: datetime,
        end: datetime,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get aggregated event metrics.

        Returns:
            - total_events: Total event count
            - unique_users: Unique users who triggered events
            - events_by_name: Event counts by event name
            - events_by_category: Event counts by category
            - events_over_time: Time series of events
        """
        from .models import AnalyticsEvent

        # Base queryset
        qs = AnalyticsEvent.objects.filter(
            timestamp__gte=start,
            timestamp__lt=end,
        )

        if organization_id:
            qs = qs.filter(organization_id=organization_id)

        # Total events
        total_events = await qs.acount()

        # Unique users
        unique_users = await qs.exclude(user__isnull=True).values("user").distinct().acount()

        # Events by name
        events_by_name = {}
        async for item in qs.values("name").annotate(count=Count("id")).order_by("-count")[:20]:
            events_by_name[item["name"]] = item["count"]

        # Events by category
        events_by_category = {}
        async for item in qs.values("category").annotate(count=Count("id")):
            events_by_category[item["category"]] = item["count"]

        # Events over time (by day)
        events_over_time = []
        async for item in (
            qs.annotate(date=TruncDate("timestamp"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        ):
            events_over_time.append(
                {
                    "date": item["date"].isoformat() if item["date"] else None,
                    "count": item["count"],
                }
            )

        return {
            "total_events": total_events,
            "unique_users": unique_users,
            "events_by_name": events_by_name,
            "events_by_category": events_by_category,
            "events_over_time": events_over_time,
        }

    # =========================================================================
    # Page Metrics
    # =========================================================================

    async def get_page_metrics(
        self,
        start: datetime,
        end: datetime,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get aggregated page view metrics.

        Returns:
            - total_page_views: Total page view count
            - unique_visitors: Unique visitors
            - avg_time_on_page: Average time on page
            - bounce_rate: Bounce rate percentage
            - top_pages: Top pages by views
            - pages_over_time: Time series of page views
        """
        from .models import PageView

        qs = PageView.objects.filter(
            timestamp__gte=start,
            timestamp__lt=end,
        )

        if organization_id:
            qs = qs.filter(organization_id=organization_id)

        # Total page views
        total_page_views = await qs.acount()

        # Unique visitors (by user or anonymous_id)
        unique_by_user = await qs.exclude(user__isnull=True).values("user").distinct().acount()

        unique_by_anon = (
            await qs.filter(user__isnull=True)
            .exclude(anonymous_id="")
            .values("anonymous_id")
            .distinct()
            .acount()
        )

        unique_visitors = unique_by_user + unique_by_anon

        # Average time on page
        avg_time_result = await qs.filter(time_on_page__isnull=False).aaggregate(
            avg_time=Avg("time_on_page")
        )
        avg_time_on_page = avg_time_result.get("avg_time") or 0

        # Bounce rate
        total_entrances = await qs.filter(is_entrance=True).acount()
        bounces = await qs.filter(is_entrance=True, is_bounce=True).acount()
        bounce_rate = (bounces / total_entrances * 100) if total_entrances > 0 else 0

        # Top pages
        top_pages = []
        async for item in (
            qs.values("path")
            .annotate(
                count=Count("id"),
                avg_time=Avg("time_on_page"),
            )
            .order_by("-count")[:20]
        ):
            top_pages.append(
                {
                    "path": item["path"],
                    "views": item["count"],
                    "avg_time": item["avg_time"] or 0,
                }
            )

        # Pages over time
        pages_over_time = []
        async for item in (
            qs.annotate(date=TruncDate("timestamp"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        ):
            pages_over_time.append(
                {
                    "date": item["date"].isoformat() if item["date"] else None,
                    "count": item["count"],
                }
            )

        return {
            "total_page_views": total_page_views,
            "unique_visitors": unique_visitors,
            "avg_time_on_page": float(avg_time_on_page),
            "bounce_rate": float(bounce_rate),
            "top_pages": top_pages,
            "pages_over_time": pages_over_time,
        }

    # =========================================================================
    # Session Metrics
    # =========================================================================

    async def get_session_metrics(
        self,
        start: datetime,
        end: datetime,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get aggregated session metrics.

        Returns:
            - total_sessions: Total session count
            - unique_users: Unique users with sessions
            - avg_session_duration: Average session duration (seconds)
            - avg_pages_per_session: Average pages per session
            - bounce_rate: Session bounce rate
            - sessions_by_device: Sessions by device type
            - sessions_by_country: Sessions by country
            - sessions_over_time: Time series of sessions
        """
        from .models import AnalyticsSession

        qs = AnalyticsSession.objects.filter(
            started_at__gte=start,
            started_at__lt=end,
        )

        # Total sessions
        total_sessions = await qs.acount()

        # Unique users
        unique_users = await qs.exclude(user__isnull=True).values("user").distinct().acount()

        # Average session duration
        avg_duration_result = await qs.filter(duration_seconds__gt=0).aaggregate(
            avg_duration=Avg("duration_seconds")
        )
        avg_session_duration = avg_duration_result.get("avg_duration") or 0

        # Average pages per session
        avg_pages_result = await qs.aaggregate(avg_pages=Avg("page_views"))
        avg_pages_per_session = avg_pages_result.get("avg_pages") or 0

        # Bounce rate (sessions with only 1 page view)
        bounces = await qs.filter(page_views=1).acount()
        bounce_rate = (bounces / total_sessions * 100) if total_sessions > 0 else 0

        # Sessions by device
        sessions_by_device = {}
        async for item in (
            qs.exclude(device_type="").values("device_type").annotate(count=Count("id"))
        ):
            sessions_by_device[item["device_type"]] = item["count"]

        # Sessions by country
        sessions_by_country = {}
        async for item in (
            qs.exclude(country="")
            .values("country")
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        ):
            sessions_by_country[item["country"]] = item["count"]

        # Sessions over time
        sessions_over_time = []
        async for item in (
            qs.annotate(date=TruncDate("started_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        ):
            sessions_over_time.append(
                {
                    "date": item["date"].isoformat() if item["date"] else None,
                    "count": item["count"],
                }
            )

        return {
            "total_sessions": total_sessions,
            "unique_users": unique_users,
            "avg_session_duration": float(avg_session_duration),
            "avg_pages_per_session": float(avg_pages_per_session),
            "bounce_rate": float(bounce_rate),
            "sessions_by_device": sessions_by_device,
            "sessions_by_country": sessions_by_country,
            "sessions_over_time": sessions_over_time,
        }

    # =========================================================================
    # Traffic Metrics
    # =========================================================================

    async def get_traffic_metrics(
        self,
        start: datetime,
        end: datetime,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get traffic source metrics.

        Returns:
            - total_visits: Total visits
            - by_source: Visits by UTM source
            - by_medium: Visits by UTM medium
            - by_campaign: Visits by UTM campaign
            - by_referrer: Visits by referrer domain
        """
        from .models import AnalyticsSession

        qs = AnalyticsSession.objects.filter(
            started_at__gte=start,
            started_at__lt=end,
        )

        total_visits = await qs.acount()

        # By UTM source
        by_source = {}
        async for item in (
            qs.exclude(utm_source="")
            .values("utm_source")
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        ):
            by_source[item["utm_source"]] = item["count"]

        # By UTM medium
        by_medium = {}
        async for item in (
            qs.exclude(utm_medium="")
            .values("utm_medium")
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        ):
            by_medium[item["utm_medium"]] = item["count"]

        # By UTM campaign
        by_campaign = {}
        async for item in (
            qs.exclude(utm_campaign="")
            .values("utm_campaign")
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        ):
            by_campaign[item["utm_campaign"]] = item["count"]

        # By referrer domain
        by_referrer = {}
        async for item in (
            qs.exclude(referrer_domain="")
            .values("referrer_domain")
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        ):
            by_referrer[item["referrer_domain"]] = item["count"]

        return {
            "total_visits": total_visits,
            "by_source": by_source,
            "by_medium": by_medium,
            "by_campaign": by_campaign,
            "by_referrer": by_referrer,
        }

    # =========================================================================
    # Real-time Metrics
    # =========================================================================

    async def get_realtime_metrics(
        self,
        minutes: int = 30,
    ) -> dict[str, Any]:
        """
        Get real-time metrics for the last N minutes.

        Returns:
            - active_users: Currently active users
            - active_sessions: Currently active sessions
            - page_views_per_minute: Average page views per minute
            - events_per_minute: Average events per minute
            - top_pages: Current top pages
            - top_events: Current top events
            - users_by_country: Active users by country
            - users_by_device: Active users by device
        """
        from .models import AnalyticsEvent, AnalyticsSession, PageView, SessionStatus

        now = timezone.now()
        start = now - timedelta(minutes=minutes)

        # Active sessions
        active_sessions = await AnalyticsSession.objects.filter(
            status=SessionStatus.ACTIVE.value,
            last_activity_at__gte=start,
        ).acount()

        # Active users (approximation based on sessions)
        active_users = (
            await AnalyticsSession.objects.filter(
                status=SessionStatus.ACTIVE.value,
                last_activity_at__gte=start,
                user__isnull=False,
            )
            .values("user")
            .distinct()
            .acount()
        )

        # Page views in period
        pv_count = await PageView.objects.filter(
            timestamp__gte=start,
        ).acount()
        page_views_per_minute = pv_count / minutes if minutes > 0 else 0

        # Events in period
        event_count = await AnalyticsEvent.objects.filter(
            timestamp__gte=start,
        ).acount()
        events_per_minute = event_count / minutes if minutes > 0 else 0

        # Top pages right now
        top_pages = []
        async for item in (
            PageView.objects.filter(timestamp__gte=start)
            .values("path")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        ):
            top_pages.append(
                {
                    "path": item["path"],
                    "count": item["count"],
                }
            )

        # Top events right now
        top_events = []
        async for item in (
            AnalyticsEvent.objects.filter(timestamp__gte=start)
            .values("name")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        ):
            top_events.append(
                {
                    "name": item["name"],
                    "count": item["count"],
                }
            )

        # Users by country (from active sessions)
        users_by_country = {}
        async for item in (
            AnalyticsSession.objects.filter(
                status=SessionStatus.ACTIVE.value,
                last_activity_at__gte=start,
            )
            .exclude(country="")
            .values("country")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        ):
            users_by_country[item["country"]] = item["count"]

        # Users by device (from active sessions)
        users_by_device = {}
        async for item in (
            AnalyticsSession.objects.filter(
                status=SessionStatus.ACTIVE.value,
                last_activity_at__gte=start,
            )
            .exclude(device_type="")
            .values("device_type")
            .annotate(count=Count("id"))
        ):
            users_by_device[item["device_type"]] = item["count"]

        return {
            "active_users": active_users,
            "active_sessions": active_sessions,
            "page_views_per_minute": float(page_views_per_minute),
            "events_per_minute": float(events_per_minute),
            "top_pages": top_pages,
            "top_events": top_events,
            "users_by_country": users_by_country,
            "users_by_device": users_by_device,
        }

    # =========================================================================
    # Funnel Analysis
    # =========================================================================

    async def analyze_funnel(
        self,
        funnel: "Funnel",
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        """
        Analyze funnel conversion.

        Returns:
            - total_started: Users who started the funnel
            - total_converted: Users who completed the funnel
            - overall_conversion_rate: Overall conversion rate
            - avg_conversion_time: Average time to convert (seconds)
            - steps: Per-step analytics
        """
        from .models import AnalyticsEvent, FunnelStep, PageView

        # Get funnel steps
        steps = [s async for s in funnel.steps.all().order_by("order")]

        if not steps:
            return {
                "total_started": 0,
                "total_converted": 0,
                "overall_conversion_rate": 0,
                "steps": [],
            }

        # Track users through each step
        step_users: dict[int, set] = defaultdict(set)

        for step in steps:
            if step.match_type == FunnelStep.MatchType.EVENT:
                # Find users who triggered this event
                async for event in (
                    AnalyticsEvent.objects.filter(
                        name=step.event_name,
                        timestamp__gte=start,
                        timestamp__lt=end,
                    )
                    .exclude(user__isnull=True)
                    .values("user_id")
                ):
                    step_users[step.order].add(event["user_id"])

            elif step.match_type == FunnelStep.MatchType.PAGE_VIEW:
                # Find users who viewed this page
                async for pv in (
                    PageView.objects.filter(
                        path__startswith=step.page_path,
                        timestamp__gte=start,
                        timestamp__lt=end,
                    )
                    .exclude(user__isnull=True)
                    .values("user_id")
                ):
                    step_users[step.order].add(pv["user_id"])

        # Calculate funnel metrics
        step_analytics = []
        previous_users = None

        for step in steps:
            current_users = step_users[step.order]

            if funnel.strict_order and previous_users is not None:
                # Only count users who were in the previous step
                current_users = current_users & previous_users

            visitors = len(current_users)

            if step.order == 1:
                conversion_rate = 100.0
                drop_off_rate = 0.0
            else:
                prev_count = len(previous_users) if previous_users else 0
                conversion_rate = (visitors / prev_count * 100) if prev_count > 0 else 0
                drop_off_rate = 100 - conversion_rate

            step_analytics.append(
                {
                    "step_order": step.order,
                    "step_name": step.name,
                    "visitors": visitors,
                    "conversion_rate": conversion_rate,
                    "drop_off_rate": drop_off_rate,
                    "avg_time_to_complete": None,  # Would need more complex tracking
                }
            )

            previous_users = current_users

        # Overall metrics
        total_started = len(step_users.get(1, set()))
        total_converted = len(step_users.get(len(steps), set())) if steps else 0
        overall_conversion_rate = (
            (total_converted / total_started * 100) if total_started > 0 else 0
        )

        return {
            "total_started": total_started,
            "total_converted": total_converted,
            "overall_conversion_rate": float(overall_conversion_rate),
            "avg_conversion_time": None,  # Would need conversion tracking
            "steps": step_analytics,
        }

    # =========================================================================
    # Cohort Analysis
    # =========================================================================

    async def get_cohort_retention(
        self,
        start: datetime,
        end: datetime,
        cohort_period: str = "week",  # day, week, month
        retention_period: str = "week",
        event_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Calculate cohort retention.

        Groups users by signup date and tracks retention over time.

        Returns:
            - cohorts: List of cohort rows with retention percentages
            - periods: Period labels
        """
        from django.contrib.auth import get_user_model

        from .models import AnalyticsEvent

        User = get_user_model()

        # Get cohorts (users grouped by signup date)
        cohorts = []

        # Determine cohort boundaries
        current = start
        while current < end:
            if cohort_period == "day":
                next_period = current + timedelta(days=1)
            elif cohort_period == "week":
                next_period = current + timedelta(weeks=1)
            else:
                next_period = current + timedelta(days=30)

            # Get users in this cohort (async ORM iteration)
            cohort_users = [
                user_id
                async for user_id in User.objects.filter(
                    date_joined__gte=current,
                    date_joined__lt=next_period,
                ).values_list("id", flat=True)
            ]

            if cohort_users:
                cohort_size = len(cohort_users)

                # Calculate retention for each period
                retention = []
                period_start = current

                for i in range(12):  # Max 12 retention periods
                    if retention_period == "day":
                        period_end = period_start + timedelta(days=1)
                    elif retention_period == "week":
                        period_end = period_start + timedelta(weeks=1)
                    else:
                        period_end = period_start + timedelta(days=30)

                    if period_end > end:
                        break

                    # Count active users in this period
                    if event_name:
                        active_count = (
                            await AnalyticsEvent.objects.filter(
                                user_id__in=cohort_users,
                                name=event_name,
                                timestamp__gte=period_start,
                                timestamp__lt=period_end,
                            )
                            .values("user_id")
                            .distinct()
                            .acount()
                        )
                    else:
                        active_count = (
                            await AnalyticsEvent.objects.filter(
                                user_id__in=cohort_users,
                                timestamp__gte=period_start,
                                timestamp__lt=period_end,
                            )
                            .values("user_id")
                            .distinct()
                            .acount()
                        )

                    retention_rate = (active_count / cohort_size * 100) if cohort_size > 0 else 0
                    retention.append(retention_rate)

                    period_start = period_end

                cohorts.append(
                    {
                        "cohort": current.strftime("%Y-%m-%d"),
                        "cohort_start": current,
                        "cohort_size": cohort_size,
                        "retention": retention,
                    }
                )

            current = next_period

        # Generate period labels
        periods = [f"Period {i}" for i in range(12)]

        return {
            "cohorts": cohorts,
            "periods": periods,
        }

    # =========================================================================
    # Rollups (for scheduled aggregation)
    # =========================================================================

    async def create_daily_rollup(self, date: datetime) -> dict[str, int]:
        """
        Create daily rollup for the given date.

        Aggregates events and page views into UserMetric records.
        """
        from .models import AnalyticsEvent, PageView, UserMetric

        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        created_count = 0
        updated_count = 0

        # Get unique users with activity
        user_ids = set()

        async for event in (
            AnalyticsEvent.objects.filter(
                timestamp__gte=start,
                timestamp__lt=end,
                user__isnull=False,
            )
            .values("user_id")
            .distinct()
        ):
            user_ids.add(event["user_id"])

        async for pv in (
            PageView.objects.filter(
                timestamp__gte=start,
                timestamp__lt=end,
                user__isnull=False,
            )
            .values("user_id")
            .distinct()
        ):
            user_ids.add(pv["user_id"])

        # Create/update metrics for each user
        for user_id in user_ids:
            # Count events
            event_count = await AnalyticsEvent.objects.filter(
                user_id=user_id,
                timestamp__gte=start,
                timestamp__lt=end,
            ).acount()

            # Count page views
            pv_count = await PageView.objects.filter(
                user_id=user_id,
                timestamp__gte=start,
                timestamp__lt=end,
            ).acount()

            # Events by name
            events_by_name = {}
            async for item in (
                AnalyticsEvent.objects.filter(
                    user_id=user_id,
                    timestamp__gte=start,
                    timestamp__lt=end,
                )
                .values("name")
                .annotate(count=Count("id"))
            ):
                events_by_name[item["name"]] = item["count"]

            # Update or create metric
            metric, created = await UserMetric.objects.aupdate_or_create(
                user_id=user_id,
                period=UserMetric.Period.DAY,
                period_start=start.date(),
                defaults={
                    "period_end": end.date(),
                    "total_events": event_count,
                    "total_page_views": pv_count,
                    "events_by_name": events_by_name,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        return {
            "created": created_count,
            "updated": updated_count,
        }


# Global aggregator instance
_aggregator: Aggregator | None = None


def get_aggregator() -> Aggregator:
    """Get the default aggregator instance."""
    global _aggregator
    if _aggregator is None:
        _aggregator = Aggregator()
    return _aggregator


__all__ = [
    "Aggregator",
    "get_aggregator",
]
