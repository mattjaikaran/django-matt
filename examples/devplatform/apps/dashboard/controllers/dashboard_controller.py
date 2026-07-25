from datetime import timedelta

from django.utils import timezone
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError

from apps.analytics.models import DailyMetric
from apps.gateway.models import RequestLog
from apps.keys.models import APIKey
from apps.organizations.controllers.utils import get_membership
from apps.projects.models import Project
from apps.webhooks.models import Webhook


class DashboardController(APIController):
    tags = ["Dashboard"]

    @staticmethod
    @jwt_required
    async def get_dashboard(request, org_id: str) -> dict:
        """Overview dashboard for an organization."""
        await get_membership(request.user, org_id)

        project_count = await Project.objects.filter(
            organization_id=org_id, is_active=True
        ).acount()

        active_keys = await APIKey.objects.filter(
            project__organization_id=org_id, is_active=True
        ).acount()

        active_webhooks = await Webhook.objects.filter(
            project__organization_id=org_id, is_active=True
        ).acount()

        # Last 24 hours stats
        since = timezone.now() - timedelta(hours=24)
        recent_requests = await RequestLog.objects.filter(
            project__organization_id=org_id,
            created_at__gte=since,
        ).acount()

        recent_errors = await RequestLog.objects.filter(
            project__organization_id=org_id,
            created_at__gte=since,
            status_code__gte=400,
        ).acount()

        return {
            "organization_id": org_id,
            "projects": project_count,
            "active_api_keys": active_keys,
            "active_webhooks": active_webhooks,
            "last_24h": {
                "total_requests": recent_requests,
                "errors": recent_errors,
                "error_rate": (
                    round(recent_errors / recent_requests * 100, 2) if recent_requests > 0 else 0.0
                ),
            },
        }

    @staticmethod
    @jwt_required
    async def get_project_dashboard(request, org_id: str, project_id: str) -> dict:
        """Dashboard for a specific project."""
        await get_membership(request.user, org_id)

        try:
            project = await Project.objects.aget(id=project_id, organization_id=org_id)
        except Project.DoesNotExist:
            raise APIError(status_code=404, message="Project not found")

        key_count = await APIKey.objects.filter(project=project, is_active=True).acount()

        webhook_count = await Webhook.objects.filter(project=project, is_active=True).acount()

        # Recent request logs
        since = timezone.now() - timedelta(hours=24)
        logs_qs = RequestLog.objects.filter(project=project, created_at__gte=since)
        total = await logs_qs.acount()
        errors = await logs_qs.filter(status_code__gte=400).acount()

        # Recent daily metrics
        recent_metrics = []
        async for m in DailyMetric.objects.filter(project=project).order_by("-date")[:7]:
            recent_metrics.append(
                {
                    "date": m.date.isoformat(),
                    "total_requests": m.total_requests,
                    "failed_requests": m.failed_requests,
                    "avg_response_time_ms": m.avg_response_time_ms,
                }
            )

        return {
            "project": {
                "id": str(project.id),
                "name": project.name,
                "environment": project.environment,
            },
            "api_keys": key_count,
            "webhooks": webhook_count,
            "last_24h": {
                "total_requests": total,
                "errors": errors,
                "error_rate": round(errors / total * 100, 2) if total > 0 else 0.0,
            },
            "daily_metrics": recent_metrics,
        }
