# file-length-max: 500
"""
Health check endpoints for deployment monitoring.

Provides standardized health, readiness, and liveness endpoints
for Kubernetes, Docker, and cloud platform deployments.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


@dataclass
class CheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str = ""
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "name": self.name,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 2),
        }
        if self.message:
            result["message"] = self.message
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class HealthCheckResponse:
    """Complete health check response."""

    status: HealthStatus
    checks: list[CheckResult] = field(default_factory=list)
    version: str = ""
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "version": self.version,
            "uptime_seconds": round(self.uptime_seconds, 2),
        }


# Track application start time
_start_time = time.time()


def get_uptime() -> float:
    """Get application uptime in seconds."""
    return time.time() - _start_time


class HealthCheck:
    """
    Configurable health check system.

    Supports:
    - Database connectivity checks
    - Cache/Redis connectivity checks
    - Custom health checks
    - Async checks
    - Timeouts

    Usage:
        health = HealthCheck()
        health.add_check("custom", my_check_function)

        # In urls.py
        urlpatterns = [
            path("health/", health.health_view),
            path("ready/", health.readiness_view),
            path("live/", health.liveness_view),
        ]
    """

    def __init__(
        self,
        include_db: bool = True,
        include_cache: bool = True,
        include_migrations: bool = False,
        timeout: float = 5.0,
        version: str = "",
    ):
        self.include_db = include_db
        self.include_cache = include_cache
        self.include_migrations = include_migrations
        self.timeout = timeout
        self.version = version or getattr(settings, "VERSION", "")
        self._checks: dict[str, Callable] = {}
        self._async_checks: dict[str, Callable] = {}

    def add_check(self, name: str, check_func: Callable[[], CheckResult]):
        """Add a custom health check."""
        self._checks[name] = check_func

    def add_async_check(self, name: str, check_func: Callable[[], CheckResult]):
        """Add an async health check."""
        self._async_checks[name] = check_func

    def remove_check(self, name: str):
        """Remove a health check."""
        self._checks.pop(name, None)
        self._async_checks.pop(name, None)

    def check_database(self) -> CheckResult:
        """Check database connectivity."""
        start = time.time()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            duration = (time.time() - start) * 1000
            return CheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                duration_ms=duration,
                metadata={"engine": connection.vendor},
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return CheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=duration,
            )

    def check_cache(self) -> CheckResult:
        """Check cache connectivity."""
        start = time.time()
        try:
            test_key = "_health_check_test"
            test_value = str(time.time())

            cache.set(test_key, test_value, timeout=10)
            retrieved = cache.get(test_key)
            cache.delete(test_key)

            if retrieved != test_value:
                raise ValueError("Cache read/write mismatch")

            duration = (time.time() - start) * 1000
            return CheckResult(
                name="cache",
                status=HealthStatus.HEALTHY,
                message="Cache connection successful",
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return CheckResult(
                name="cache",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=duration,
            )

    def check_migrations(self) -> CheckResult:
        """Check if all migrations have been applied."""
        start = time.time()
        try:
            from django.db.migrations.executor import MigrationExecutor

            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())

            duration = (time.time() - start) * 1000

            if plan:
                return CheckResult(
                    name="migrations",
                    status=HealthStatus.DEGRADED,
                    message=f"{len(plan)} pending migrations",
                    duration_ms=duration,
                    metadata={"pending_count": len(plan)},
                )

            return CheckResult(
                name="migrations",
                status=HealthStatus.HEALTHY,
                message="All migrations applied",
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return CheckResult(
                name="migrations",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=duration,
            )

    def run_checks(self) -> HealthCheckResponse:
        """Run all health checks synchronously."""
        checks = []
        overall_status = HealthStatus.HEALTHY

        # Built-in checks
        if self.include_db:
            result = self.check_database()
            checks.append(result)
            if result.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED

        if self.include_cache:
            result = self.check_cache()
            checks.append(result)
            if result.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED

        if self.include_migrations:
            result = self.check_migrations()
            checks.append(result)
            if result.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED

        # Custom sync checks
        for name, check_func in self._checks.items():
            try:
                result = check_func()
                checks.append(result)
                if result.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif (
                    result.status == HealthStatus.DEGRADED
                    and overall_status == HealthStatus.HEALTHY
                ):
                    overall_status = HealthStatus.DEGRADED
            except Exception as e:
                checks.append(
                    CheckResult(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=str(e),
                    )
                )
                overall_status = HealthStatus.UNHEALTHY

        return HealthCheckResponse(
            status=overall_status,
            checks=checks,
            version=self.version,
            uptime_seconds=get_uptime(),
        )

    async def run_checks_async(self) -> HealthCheckResponse:
        """Run all health checks asynchronously."""
        # Run sync checks first
        response = self.run_checks()

        # Run async checks
        for name, check_func in self._async_checks.items():
            try:
                result = await asyncio.wait_for(
                    check_func(),
                    timeout=self.timeout,
                )
                response.checks.append(result)
                if result.status == HealthStatus.UNHEALTHY:
                    response.status = HealthStatus.UNHEALTHY
                elif (
                    result.status == HealthStatus.DEGRADED
                    and response.status == HealthStatus.HEALTHY
                ):
                    response.status = HealthStatus.DEGRADED
            except TimeoutError:
                response.checks.append(
                    CheckResult(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message="Check timed out",
                    )
                )
                response.status = HealthStatus.UNHEALTHY
            except Exception as e:
                response.checks.append(
                    CheckResult(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=str(e),
                    )
                )
                response.status = HealthStatus.UNHEALTHY

        return response

    def health_view(self, request: HttpRequest) -> JsonResponse:
        """Django view for full health check."""
        response = self.run_checks()
        status_code = 200 if response.status == HealthStatus.HEALTHY else 503
        return JsonResponse(response.to_dict(), status=status_code)

    def readiness_view(self, request: HttpRequest) -> JsonResponse:
        """
        Kubernetes readiness probe endpoint.

        Checks if the app is ready to receive traffic.
        """
        response = self.run_checks()
        status_code = 200 if response.status != HealthStatus.UNHEALTHY else 503
        return JsonResponse(response.to_dict(), status=status_code)

    def liveness_view(self, request: HttpRequest) -> JsonResponse:
        """
        Kubernetes liveness probe endpoint.

        Simple check to see if the app is alive.
        """
        return JsonResponse(
            {
                "status": "healthy",
                "uptime_seconds": round(get_uptime(), 2),
            }
        )

    async def async_health_view(self, request: HttpRequest) -> JsonResponse:
        """Async Django view for full health check."""
        response = await self.run_checks_async()
        status_code = 200 if response.status == HealthStatus.HEALTHY else 503
        return JsonResponse(response.to_dict(), status=status_code)


# Default health check instance
_default_health_check: HealthCheck | None = None


def get_health_check() -> HealthCheck:
    """Get or create the default health check instance."""
    global _default_health_check
    if _default_health_check is None:
        _default_health_check = HealthCheck()
    return _default_health_check


def configure_health_check(
    include_db: bool = True,
    include_cache: bool = True,
    include_migrations: bool = False,
    timeout: float = 5.0,
    version: str = "",
) -> HealthCheck:
    """Configure the default health check instance."""
    global _default_health_check
    _default_health_check = HealthCheck(
        include_db=include_db,
        include_cache=include_cache,
        include_migrations=include_migrations,
        timeout=timeout,
        version=version,
    )
    return _default_health_check


# Convenience view functions using the default health check
def health_check_view(request: HttpRequest) -> JsonResponse:
    """Full health check view."""
    return get_health_check().health_view(request)


def readiness_check_view(request: HttpRequest) -> JsonResponse:
    """Readiness probe view."""
    return get_health_check().readiness_view(request)


def liveness_check_view(request: HttpRequest) -> JsonResponse:
    """Liveness probe view."""
    return get_health_check().liveness_view(request)


async def async_health_check_view(request: HttpRequest) -> JsonResponse:
    """Async full health check view."""
    return await get_health_check().async_health_view(request)


# Decorator for adding custom health checks
def health_check(name: str):
    """
    Decorator to register a function as a health check.

    Usage:
        @health_check("my_service")
        def check_my_service():
            # Check service health
            return CheckResult(
                name="my_service",
                status=HealthStatus.HEALTHY,
                message="Service is up",
            )
    """

    def decorator(func: Callable[[], CheckResult]):
        if asyncio.iscoroutinefunction(func):
            get_health_check().add_async_check(name, func)
        else:
            get_health_check().add_check(name, func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


# URL patterns helper
def get_health_urls():
    """
    Get URL patterns for health check endpoints.

    Usage:
        from django_matt.deploy.health import get_health_urls

        urlpatterns = [
            ...
            *get_health_urls(),
        ]
    """
    from django.urls import path

    return [
        path("health/", health_check_view, name="health"),
        path("ready/", readiness_check_view, name="readiness"),
        path("live/", liveness_check_view, name="liveness"),
    ]


__all__ = [
    "CheckResult",
    "HealthCheck",
    "HealthCheckResponse",
    "HealthStatus",
    "async_health_check_view",
    "configure_health_check",
    "get_health_check",
    "get_health_urls",
    "get_uptime",
    "health_check",
    "health_check_view",
    "liveness_check_view",
    "readiness_check_view",
]
