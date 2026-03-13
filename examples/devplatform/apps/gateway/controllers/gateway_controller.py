
from django.utils.dateparse import parse_datetime
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError

from apps.gateway.models import RequestLog
from apps.gateway.schemas import RequestLogSchema
from apps.organizations.controllers.utils import get_membership
from apps.projects.models import Project


class GatewayController(APIController):
    tags = ["Gateway"]

    @staticmethod
    @jwt_required
    async def list_request_logs(
        request, org_id: str, project_id: str
    ) -> dict:
        """List request logs for a project with filtering and pagination."""
        await get_membership(request.user, org_id)

        try:
            await Project.objects.aget(id=project_id, organization_id=org_id)
        except Project.DoesNotExist:
            raise NotFoundAPIError("Project not found")

        qs = RequestLog.objects.filter(project_id=project_id)

        # Apply filters from query params
        method = request.GET.get("method")
        if method:
            qs = qs.filter(method=method.upper())

        status_code = request.GET.get("status_code")
        if status_code:
            qs = qs.filter(status_code=int(status_code))

        path_contains = request.GET.get("path_contains")
        if path_contains:
            qs = qs.filter(path__icontains=path_contains)

        min_response_time = request.GET.get("min_response_time")
        if min_response_time:
            qs = qs.filter(response_time_ms__gte=int(min_response_time))

        max_response_time = request.GET.get("max_response_time")
        if max_response_time:
            qs = qs.filter(response_time_ms__lte=int(max_response_time))

        start_date = request.GET.get("start_date")
        if start_date:
            parsed = parse_datetime(start_date)
            if parsed:
                qs = qs.filter(created_at__gte=parsed)

        end_date = request.GET.get("end_date")
        if end_date:
            parsed = parse_datetime(end_date)
            if parsed:
                qs = qs.filter(created_at__lte=parsed)

        # Pagination
        limit = int(request.GET.get("limit", "50"))
        offset = int(request.GET.get("offset", "0"))
        total = await qs.acount()

        logs = []
        async for log in qs[offset : offset + limit]:
            logs.append(RequestLogSchema.model_validate(log).model_dump())

        return {
            "items": logs,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    @jwt_required
    async def get_request_log(
        request, org_id: str, project_id: str, log_id: str
    ) -> dict:
        """Get a single request log entry."""
        await get_membership(request.user, org_id)

        try:
            await Project.objects.aget(id=project_id, organization_id=org_id)
        except Project.DoesNotExist:
            raise NotFoundAPIError("Project not found")

        log = await RequestLog.objects.filter(
            id=log_id, project_id=project_id
        ).afirst()
        if not log:
            raise NotFoundAPIError("Request log not found")

        return RequestLogSchema.model_validate(log).model_dump()

    @staticmethod
    @jwt_required
    async def get_error_logs(
        request, org_id: str, project_id: str
    ) -> dict:
        """Get error logs (status_code >= 400) for a project."""
        await get_membership(request.user, org_id)

        try:
            await Project.objects.aget(id=project_id, organization_id=org_id)
        except Project.DoesNotExist:
            raise NotFoundAPIError("Project not found")

        qs = RequestLog.objects.filter(
            project_id=project_id, status_code__gte=400
        )

        # Pagination
        limit = int(request.GET.get("limit", "50"))
        offset = int(request.GET.get("offset", "0"))
        total = await qs.acount()

        logs = []
        async for log in qs[offset : offset + limit]:
            logs.append(RequestLogSchema.model_validate(log).model_dump())

        return {
            "items": logs,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
