"""
Health check API controller.

Provides health and readiness endpoints for monitoring.
"""

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django_matt.core import APIController, api_controller
from django_matt.permissions import AllowAny


@api_controller("/health", tags=["Health"])
class HealthController(APIController):
    """Health check endpoints."""

    @APIController.get("/", permissions=[AllowAny])
    async def health_check(self, request):
        """
        Basic health check.

        Returns 200 if the application is running.
        """
        return {
            "status": "healthy",
            "version": "1.0.0",
        }

    @APIController.get("/ready", permissions=[AllowAny])
    async def readiness_check(self, request):
        """
        Readiness check for Kubernetes.

        Checks database and cache connectivity.
        """
        checks = {}
        healthy = True

        # Check database
        try:
            connection.ensure_connection()
            checks["database"] = "healthy"
        except Exception as e:
            checks["database"] = f"unhealthy: {str(e)}"
            healthy = False

        # Check cache
        try:
            cache.set("health_check", "ok", timeout=10)
            if cache.get("health_check") == "ok":
                checks["cache"] = "healthy"
            else:
                checks["cache"] = "unhealthy: could not read value"
                healthy = False
        except Exception as e:
            checks["cache"] = f"unhealthy: {str(e)}"
            healthy = False

        status_code = 200 if healthy else 503

        return {
            "status": "healthy" if healthy else "unhealthy",
            "checks": checks,
        }, status_code

    @APIController.get("/live", permissions=[AllowAny])
    async def liveness_check(self, request):
        """
        Liveness check for Kubernetes.

        Returns 200 if the process is alive.
        """
        return {"status": "alive"}

    @APIController.get("/info", permissions=[AllowAny])
    async def get_info(self, request):
        """
        Get application information.
        """
        import sys

        import django

        return {
            "name": "SaaS Starter API",
            "version": "1.0.0",
            "environment": "development" if settings.DEBUG else "production",
            "python_version": sys.version,
            "django_version": django.__version__,
        }
