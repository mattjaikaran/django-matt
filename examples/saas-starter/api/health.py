"""
Health check API controller.

Provides health and readiness endpoints for monitoring.
"""

import sys

import django
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django_matt.core import APIController
from django_matt.core.router import get


class HealthController(APIController):
    prefix = "/health"
    tags = ["Health"]

    @get("/")
    async def health_check(self, request) -> dict:
        return {
            "status": "healthy",
            "version": "1.0.0",
        }

    @get("/ready")
    async def readiness_check(self, request) -> dict:
        checks = {}
        healthy = True

        # Check database
        try:
            connection.ensure_connection()
            checks["database"] = "healthy"
        except Exception as e:
            checks["database"] = f"unhealthy: {e!s}"
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
            checks["cache"] = f"unhealthy: {e!s}"
            healthy = False

        status_code = 200 if healthy else 503

        return {
            "status": "healthy" if healthy else "unhealthy",
            "checks": checks,
        }, status_code

    @get("/live")
    async def liveness_check(self, request) -> dict:
        return {"status": "alive"}

    @get("/info")
    async def get_info(self, request) -> dict:
        return {
            "name": "SaaS Starter API",
            "version": "1.0.0",
            "environment": "development" if settings.DEBUG else "production",
            "python_version": sys.version,
            "django_version": django.__version__,
        }
