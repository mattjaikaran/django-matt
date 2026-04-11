"""
Interceptors for tenant-scoped requests.

Demonstrates django-matt's interceptor system for cross-cutting concerns:
- Tenant resolution from request headers
- Feature flag gating per tenant plan
"""

import logging

from django.http import HttpRequest, JsonResponse

from django_matt.interceptors.base import Interceptor

from tenants.models import Organization

logger = logging.getLogger(__name__)


class TenantInterceptor(Interceptor):
    """Resolve tenant from X-Tenant-Slug header and attach to request."""

    async def before(self, request: HttpRequest):
        slug = request.headers.get("X-Tenant-Slug")
        if not slug:
            return JsonResponse(
                {"detail": "X-Tenant-Slug header required"}, status=400
            )
        try:
            request.tenant = await Organization.objects.aget(slug=slug)
        except Organization.DoesNotExist:
            return JsonResponse({"detail": "Tenant not found"}, status=404)
        return None

    async def after(self, request: HttpRequest, response):
        if hasattr(request, "tenant"):
            response["X-Tenant-Id"] = str(request.tenant.id)
            response["X-Tenant-Plan"] = request.tenant.plan
        return response


class FeatureGateInterceptor(Interceptor):
    """Gate endpoints by tenant plan using feature flags."""

    def __init__(self, required_plans: list[str] | None = None):
        self.required_plans = required_plans or ["pro", "enterprise"]

    async def before(self, request: HttpRequest):
        tenant = getattr(request, "tenant", None)
        if tenant and tenant.plan not in self.required_plans:
            return JsonResponse(
                {
                    "detail": f"This feature requires one of: {', '.join(self.required_plans)}",
                    "current_plan": tenant.plan,
                    "upgrade_url": "/billing/upgrade",
                },
                status=403,
            )
        return None
