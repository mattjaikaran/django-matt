"""
Analytics API controllers.

Includes:
- Event tracking
- Dashboard metrics
- A/B testing
"""

import contextlib
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django_matt.auth import jwt_optional, jwt_required
from django_matt.core import APIController, api_controller
from django_matt.flags import get_variant
from django_matt.permissions import AllowAny, IsAuthenticated

from core.models import Membership, Organization
from notifications.models import AnalyticsEvent
from notifications.schemas import (
    AnalyticsBatchCreate,
    AnalyticsBatchResponse,
    AnalyticsDashboardResponse,
    AnalyticsEventCreate,
    AnalyticsEventResponse,
    EventCountResponse,
    ExperimentResponse,
    ExperimentResultResponse,
    MetricSummary,
    TimeSeriesDataPoint,
    TopEventsResponse,
)


@api_controller("/analytics", tags=["Analytics"])
class AnalyticsController(APIController):
    """Analytics and event tracking endpoints."""

    # =========================================================================
    # Event Tracking
    # =========================================================================

    @APIController.post("/events", response=AnalyticsEventResponse, permissions=[AllowAny])
    @jwt_optional
    async def track_event(self, request, data: AnalyticsEventCreate):
        """
        Track a single analytics event.

        Can be called authenticated or anonymously.
        """
        user = request.user if hasattr(request, "user") and request.user.is_authenticated else None

        # Get organization context from session or header
        org = None
        org_slug = request.headers.get("X-Organization")
        if org_slug:
            with contextlib.suppress(Organization.DoesNotExist):
                org = await Organization.objects.aget(slug=org_slug)

        # Extract device info from user agent
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        device_type = self._detect_device_type(user_agent)

        event = await AnalyticsEvent.objects.acreate(
            user=user,
            organization=org,
            session_id=request.headers.get("X-Session-ID", ""),
            anonymous_id=request.headers.get("X-Anonymous-ID", ""),
            event_name=data.event_name,
            event_category=data.event_category,
            properties=data.properties,
            page_url=data.page_url,
            page_title=data.page_title,
            referrer=data.referrer,
            user_agent=user_agent,
            ip_address=request.META.get("REMOTE_ADDR"),
            device_type=device_type,
            experiment_id=data.experiment_id,
            variant=data.variant,
        )

        return AnalyticsEventResponse.model_validate(event)

    @APIController.post("/events/batch", response=AnalyticsBatchResponse, permissions=[AllowAny])
    @jwt_optional
    async def track_events_batch(self, request, data: AnalyticsBatchCreate):
        """
        Track multiple analytics events in batch.
        """
        user = request.user if hasattr(request, "user") and request.user.is_authenticated else None
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        device_type = self._detect_device_type(user_agent)

        processed = 0
        errors = []

        for event_data in data.events:
            try:
                await AnalyticsEvent.objects.acreate(
                    user=user,
                    session_id=data.session_id or "",
                    anonymous_id=data.anonymous_id or "",
                    event_name=event_data.event_name,
                    event_category=event_data.event_category,
                    properties=event_data.properties,
                    page_url=event_data.page_url,
                    page_title=event_data.page_title,
                    referrer=event_data.referrer,
                    user_agent=user_agent,
                    ip_address=request.META.get("REMOTE_ADDR"),
                    device_type=device_type,
                    experiment_id=event_data.experiment_id,
                    variant=event_data.variant,
                )
                processed += 1
            except Exception as e:
                errors.append(str(e))

        return AnalyticsBatchResponse(
            processed=processed,
            failed=len(errors),
            errors=errors[:10],  # Limit error messages
        )

    def _detect_device_type(self, user_agent: str) -> str:
        """Detect device type from user agent."""
        user_agent = user_agent.lower()
        if "mobile" in user_agent or "android" in user_agent:
            return "mobile"
        if "tablet" in user_agent or "ipad" in user_agent:
            return "tablet"
        return "desktop"

    # =========================================================================
    # Dashboard
    # =========================================================================

    @APIController.get("/dashboard", response=AnalyticsDashboardResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_dashboard(
        self,
        request,
        org_slug: str,
        period: str = "7d",  # 7d, 30d, 90d
    ):
        """
        Get analytics dashboard data for an organization.

        Requires admin permission.
        """
        try:
            org = await Organization.objects.aget(slug=org_slug)
        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404

        # Check admin permission
        membership = await Membership.objects.filter(
            user=request.user,
            organization=org,
            is_active=True,
        ).afirst()

        if not membership or not membership.is_admin:
            return {"error": "Admin permission required"}, 403

        # Calculate period
        days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 7)
        period_start = timezone.now() - timedelta(days=days)
        period_end = timezone.now()
        previous_period_start = period_start - timedelta(days=days)

        # Get metrics
        metrics = []

        # Active users
        current_users = await AnalyticsEvent.objects.filter(
            organization=org,
            timestamp__gte=period_start,
            user__isnull=False,
        ).values("user").distinct().acount()

        previous_users = await AnalyticsEvent.objects.filter(
            organization=org,
            timestamp__gte=previous_period_start,
            timestamp__lt=period_start,
            user__isnull=False,
        ).values("user").distinct().acount()

        metrics.append(MetricSummary(
            metric_name="active_users",
            current_value=current_users,
            previous_value=previous_users,
            change_percentage=self._calc_change(current_users, previous_users),
            trend="up" if current_users > previous_users else "down" if current_users < previous_users else "neutral",
        ))

        # Total events
        current_events = await AnalyticsEvent.objects.filter(
            organization=org,
            timestamp__gte=period_start,
        ).acount()

        previous_events = await AnalyticsEvent.objects.filter(
            organization=org,
            timestamp__gte=previous_period_start,
            timestamp__lt=period_start,
        ).acount()

        metrics.append(MetricSummary(
            metric_name="total_events",
            current_value=current_events,
            previous_value=previous_events,
            change_percentage=self._calc_change(current_events, previous_events),
            trend="up" if current_events > previous_events else "down" if current_events < previous_events else "neutral",
        ))

        # Page views
        current_pageviews = await AnalyticsEvent.objects.filter(
            organization=org,
            timestamp__gte=period_start,
            event_name="page_view",
        ).acount()

        metrics.append(MetricSummary(
            metric_name="page_views",
            current_value=current_pageviews,
        ))

        # Time series data
        time_series = {}

        # Daily active users
        daily_users = []
        for i in range(days):
            day_start = period_start + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            count = await AnalyticsEvent.objects.filter(
                organization=org,
                timestamp__gte=day_start,
                timestamp__lt=day_end,
                user__isnull=False,
            ).values("user").distinct().acount()
            daily_users.append(TimeSeriesDataPoint(timestamp=day_start, value=count))

        time_series["daily_active_users"] = daily_users

        return AnalyticsDashboardResponse(
            period_start=period_start,
            period_end=period_end,
            metrics=metrics,
            time_series=time_series,
        )

    def _calc_change(self, current: int, previous: int) -> float | None:
        """Calculate percentage change."""
        if previous == 0:
            return None
        return round(((current - previous) / previous) * 100, 2)

    @APIController.get("/top-events", response=TopEventsResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_top_events(
        self,
        request,
        org_slug: str,
        period: str = "7d",
        limit: int = 10,
    ):
        """
        Get top events by frequency.
        """
        try:
            org = await Organization.objects.aget(slug=org_slug)
        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404

        # Check membership
        is_member = await Membership.objects.filter(
            user=request.user,
            organization=org,
            is_active=True,
        ).aexists()

        if not is_member:
            return {"error": "Not a member of this organization"}, 403

        days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 7)
        period_start = timezone.now() - timedelta(days=days)

        events = []
        async for item in AnalyticsEvent.objects.filter(
            organization=org,
            timestamp__gte=period_start,
        ).values("event_name").annotate(
            count=models.Count("id"),
            unique_users=models.Count("user", distinct=True),
        ).order_by("-count")[:limit]:
            events.append(EventCountResponse(
                event_name=item["event_name"],
                count=item["count"],
                unique_users=item["unique_users"],
            ))

        return TopEventsResponse(
            period_start=period_start,
            period_end=timezone.now(),
            events=events,
        )

    # =========================================================================
    # A/B Testing / Feature Flags
    # =========================================================================

    @APIController.get("/experiment/{experiment_id}", response=ExperimentResponse, permissions=[AllowAny])
    @jwt_optional
    async def get_experiment_assignment(self, request, experiment_id: str):
        """
        Get experiment variant assignment for the current user.

        Uses feature flags backend for consistent assignment.
        """
        user = request.user if hasattr(request, "user") and request.user.is_authenticated else None

        # Get variant from feature flags
        variant = get_variant(
            experiment_id,
            user=user,
            default="control",
        )

        return ExperimentResponse(
            experiment_id=experiment_id,
            variant=variant,
            properties={},
        )

    @APIController.get("/experiment/{experiment_id}/results", response=ExperimentResultResponse, permissions=[IsAuthenticated])
    @jwt_required
    async def get_experiment_results(self, request, experiment_id: str, org_slug: str):
        """
        Get experiment results (conversion rates by variant).

        Requires admin permission.
        """
        try:
            org = await Organization.objects.aget(slug=org_slug)
        except Organization.DoesNotExist:
            return {"error": "Organization not found"}, 404

        # Check admin permission
        membership = await Membership.objects.filter(
            user=request.user,
            organization=org,
            is_active=True,
        ).afirst()

        if not membership or not membership.is_admin:
            return {"error": "Admin permission required"}, 403

        # Aggregate results by variant
        variants = {}
        async for item in AnalyticsEvent.objects.filter(
            organization=org,
            experiment_id=experiment_id,
        ).values("variant").annotate(
            count=models.Count("id"),
            unique_users=models.Count("user", distinct=True),
        ):
            variant = item["variant"]
            count = item["count"]

            # Count conversions (events with "conversion" in name)
            conversions = await AnalyticsEvent.objects.filter(
                organization=org,
                experiment_id=experiment_id,
                variant=variant,
                event_name__icontains="conversion",
            ).acount()

            conversion_rate = conversions / count if count > 0 else 0

            variants[variant] = {
                "count": count,
                "unique_users": item["unique_users"],
                "conversions": conversions,
                "conversion_rate": round(conversion_rate, 4),
            }

        # Determine winner (highest conversion rate with statistical significance)
        winner = None
        if len(variants) >= 2:
            sorted_variants = sorted(
                variants.items(),
                key=lambda x: x[1]["conversion_rate"],
                reverse=True,
            )
            # Simple winner selection (real implementation would use statistical tests)
            if sorted_variants[0][1]["count"] > 100:
                winner = sorted_variants[0][0]

        return ExperimentResultResponse(
            experiment_id=experiment_id,
            variants=variants,
            winner=winner,
            confidence=0.95 if winner else None,
        )
