from datetime import timedelta

from django.db.models import Avg, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError, NotFoundAPIError
from django_matt.streaming import event, sse_response

from apps.analytics.models import DailyMetric
from apps.analytics.schemas import DailyMetricSchema
from apps.organizations.controllers.utils import get_membership
from apps.projects.models import Project


class AnalyticsController(APIController):
    tags = ["Analytics"]

    @staticmethod
    @jwt_required
    async def get_usage_summary(request, org_id: str, project_id: str) -> dict:
        """Aggregate usage summary for a project over a given period."""
        await get_membership(request.user, org_id)

        try:
            await Project.objects.aget(id=project_id, organization_id=org_id)
        except Project.DoesNotExist:
            raise NotFoundAPIError("Project not found")

        days = int(request.GET.get("days", "30"))
        now = timezone.now()
        period_start = now - timedelta(days=days)

        qs = DailyMetric.objects.filter(
            project_id=project_id,
            date__gte=period_start.date(),
            date__lte=now.date(),
        )

        aggregates = await qs.aaggregate(
            total_requests=Sum("total_requests"),
            total_successful=Sum("successful_requests"),
            total_failed=Sum("failed_requests"),
            total_bandwidth=Sum("total_bandwidth_bytes"),
            avg_response_time=Avg("avg_response_time_ms"),
        )

        total_requests = aggregates["total_requests"] or 0
        total_failed = aggregates["total_failed"] or 0
        error_rate = round(total_failed / total_requests * 100, 2) if total_requests > 0 else 0.0

        return {
            "total_requests": total_requests,
            "total_bandwidth": aggregates["total_bandwidth"] or 0,
            "avg_response_time": round(aggregates["avg_response_time"] or 0, 2),
            "error_rate": error_rate,
            "period_start": period_start.isoformat(),
            "period_end": now.isoformat(),
        }

    @staticmethod
    @jwt_required
    async def get_daily_metrics(request, org_id: str, project_id: str) -> dict:
        """Return daily metric entries for a project within a date range."""
        await get_membership(request.user, org_id)

        try:
            await Project.objects.aget(id=project_id, organization_id=org_id)
        except Project.DoesNotExist:
            raise NotFoundAPIError("Project not found")

        qs = DailyMetric.objects.filter(project_id=project_id)

        start_date = request.GET.get("start_date")
        if start_date:
            parsed = parse_date(start_date)
            if parsed:
                qs = qs.filter(date__gte=parsed)

        end_date = request.GET.get("end_date")
        if end_date:
            parsed = parse_date(end_date)
            if parsed:
                qs = qs.filter(date__lte=parsed)

        metrics = []
        async for m in qs:
            metrics.append(DailyMetricSchema.model_validate(m).model_dump())

        return {"items": metrics}

    @staticmethod
    @jwt_required
    async def get_time_series(request, org_id: str, project_id: str) -> dict:
        """Return time series data for a specific metric."""
        await get_membership(request.user, org_id)

        try:
            await Project.objects.aget(id=project_id, organization_id=org_id)
        except Project.DoesNotExist:
            raise NotFoundAPIError("Project not found")

        metric = request.GET.get("metric", "total_requests")
        days = int(request.GET.get("days", "30"))

        valid_metrics = {
            "total_requests",
            "successful_requests",
            "failed_requests",
            "avg_response_time_ms",
            "p95_response_time_ms",
            "total_bandwidth_bytes",
            "unique_ips",
        }
        if metric not in valid_metrics:
            raise APIError(
                status_code=400,
                message=f"Invalid metric. Must be one of: {', '.join(sorted(valid_metrics))}",
            )

        now = timezone.now()
        since = now - timedelta(days=days)

        qs = DailyMetric.objects.filter(
            project_id=project_id,
            date__gte=since.date(),
            date__lte=now.date(),
        ).order_by("date")

        data = []
        async for m in qs:
            data.append(
                {
                    "timestamp": m.date.isoformat(),
                    "value": float(getattr(m, metric)),
                }
            )

        return {
            "metric": metric,
            "data": data,
        }

    @staticmethod
    @jwt_required
    async def stream_metrics(request, org_id: str, project_id: str):
        """Stream live metrics updates via SSE."""
        import asyncio

        await get_membership(request.user, org_id)

        try:
            await Project.objects.aget(id=project_id, organization_id=org_id)
        except Project.DoesNotExist:
            raise NotFoundAPIError("Project not found")

        async def generate():
            while True:
                now = timezone.now()
                qs = DailyMetric.objects.filter(
                    project_id=project_id,
                    date=now.date(),
                )
                aggregates = await qs.aaggregate(
                    total_requests=Sum("total_requests"),
                    avg_response_time=Avg("avg_response_time_ms"),
                )
                yield event(
                    {
                        "total_requests": aggregates["total_requests"] or 0,
                        "avg_response_time": round(aggregates["avg_response_time"] or 0, 2),
                        "timestamp": now.isoformat(),
                    },
                    event_type="metrics",
                )
                await asyncio.sleep(5)

        return sse_response(generate())
