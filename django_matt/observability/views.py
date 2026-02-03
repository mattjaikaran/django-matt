"""
Observability views for Django Matt.

This module provides HTTP endpoints for metrics exposure and health checks.

Add to urls.py:

    from django_matt.observability.views import metrics_view, health_view, ready_view

    urlpatterns = [
        ...
        path("_matt/metrics", metrics_view, name="observability-metrics"),
        path("health", health_view, name="observability-health"),
        path("ready", ready_view, name="observability-ready"),
    ]

Or use the included URL patterns:

    from django_matt.observability.views import urlpatterns as observability_urls

    urlpatterns = [
        ...
        path("", include(observability_urls)),
    ]
"""

import json
import logging
import time
from typing import Any, Callable, Optional

from django.http import HttpRequest, HttpResponse
from django.urls import path
from django.views.decorators.http import require_GET

from django_matt.observability.metrics import metrics_manager

logger = logging.getLogger("django_matt.observability.views")


@require_GET
def metrics_view(request: HttpRequest) -> HttpResponse:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format.

    URL: /_matt/metrics
    """
    try:
        content = metrics_manager.generate_metrics()
        content_type = metrics_manager.get_content_type()
        return HttpResponse(content, content_type=content_type)
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return HttpResponse(
            f"# Error generating metrics: {e}\n",
            content_type="text/plain",
            status=500,
        )


@require_GET
def health_view(request: HttpRequest) -> HttpResponse:
    """
    Health check endpoint.

    Returns a simple health status. Use this for liveness probes.

    URL: /health
    """
    return HttpResponse(
        json.dumps({"status": "healthy", "timestamp": time.time()}),
        content_type="application/json",
    )


class ReadinessChecker:
    """
    Manages readiness checks for the application.

    Register checks to verify that the application is ready to serve traffic.
    """

    def __init__(self):
        self._checks: dict[str, Callable[[], tuple[bool, str]]] = {}

    def register(
        self, name: str, check: Callable[[], tuple[bool, str]]
    ) -> None:
        """
        Register a readiness check.

        Args:
            name: Name of the check
            check: Callable that returns (is_ready, message)

        Example:
            def check_database():
                try:
                    connection.ensure_connection()
                    return True, "Database connected"
                except Exception as e:
                    return False, f"Database error: {e}"

            readiness_checker.register("database", check_database)
        """
        self._checks[name] = check

    def unregister(self, name: str) -> None:
        """Unregister a readiness check."""
        self._checks.pop(name, None)

    def run_checks(self) -> tuple[bool, dict[str, Any]]:
        """
        Run all readiness checks.

        Returns:
            Tuple of (all_ready, check_results)
        """
        results = {}
        all_ready = True

        for name, check in self._checks.items():
            try:
                is_ready, message = check()
                results[name] = {
                    "ready": is_ready,
                    "message": message,
                }
                if not is_ready:
                    all_ready = False
            except Exception as e:
                results[name] = {
                    "ready": False,
                    "message": f"Check failed: {e}",
                }
                all_ready = False

        return all_ready, results


# Global readiness checker
readiness_checker = ReadinessChecker()


# Register default checks
def _check_database() -> tuple[bool, str]:
    """Check database connectivity."""
    try:
        from django.db import connection

        connection.ensure_connection()
        return True, "Database connected"
    except Exception as e:
        return False, f"Database error: {e}"


def _check_cache() -> tuple[bool, str]:
    """Check cache connectivity."""
    try:
        from django.core.cache import cache

        cache.set("_health_check", "ok", 1)
        if cache.get("_health_check") == "ok":
            return True, "Cache connected"
        return False, "Cache read failed"
    except Exception as e:
        return False, f"Cache error: {e}"


# Register default checks (can be disabled via settings)
from django.conf import settings

if getattr(settings, "DJANGO_MATT_READINESS_CHECK_DATABASE", True):
    readiness_checker.register("database", _check_database)

if getattr(settings, "DJANGO_MATT_READINESS_CHECK_CACHE", False):
    readiness_checker.register("cache", _check_cache)


@require_GET
def ready_view(request: HttpRequest) -> HttpResponse:
    """
    Readiness check endpoint.

    Returns the status of all registered readiness checks.
    Use this for readiness probes in Kubernetes.

    URL: /ready
    """
    all_ready, results = readiness_checker.run_checks()

    response_data = {
        "ready": all_ready,
        "checks": results,
        "timestamp": time.time(),
    }

    status_code = 200 if all_ready else 503

    return HttpResponse(
        json.dumps(response_data),
        content_type="application/json",
        status=status_code,
    )


@require_GET
def info_view(request: HttpRequest) -> HttpResponse:
    """
    Application info endpoint.

    Returns information about the application and its dependencies.

    URL: /_matt/info
    """
    import sys

    import django

    from django_matt.observability.metrics import HAS_PROMETHEUS
    from django_matt.observability.tracing import (
        HAS_DATADOG,
        HAS_JAEGER,
        HAS_NEWRELIC,
        HAS_OPENTELEMETRY,
        HAS_OTLP,
        HAS_ZIPKIN,
    )

    info = {
        "python_version": sys.version,
        "django_version": django.__version__,
        "dependencies": {
            "opentelemetry": HAS_OPENTELEMETRY,
            "prometheus_client": HAS_PROMETHEUS,
            "jaeger": HAS_JAEGER,
            "otlp": HAS_OTLP,
            "zipkin": HAS_ZIPKIN,
            "datadog": HAS_DATADOG,
            "newrelic": HAS_NEWRELIC,
        },
        "timestamp": time.time(),
    }

    # Add app version if available
    app_version = getattr(settings, "APP_VERSION", None)
    if app_version:
        info["app_version"] = app_version

    # Add service name
    tracing_config = getattr(settings, "DJANGO_MATT_TRACING", {})
    info["service_name"] = tracing_config.get("SERVICE_NAME", "unknown")

    return HttpResponse(
        json.dumps(info, indent=2),
        content_type="application/json",
    )


@require_GET
def debug_view(request: HttpRequest) -> HttpResponse:
    """
    Debug endpoint for development.

    Returns detailed information about the current request and configuration.
    Only available when DEBUG=True.

    URL: /_matt/debug
    """
    from django.conf import settings

    if not settings.DEBUG:
        return HttpResponse(
            json.dumps({"error": "Debug endpoint only available in DEBUG mode"}),
            content_type="application/json",
            status=403,
        )

    from django_matt.observability.logging import (
        get_correlation_id,
        get_request_id,
        get_user_id,
    )

    debug_info = {
        "request": {
            "method": request.method,
            "path": request.path,
            "headers": dict(request.headers),
            "query_params": dict(request.GET),
        },
        "context": {
            "correlation_id": get_correlation_id(),
            "request_id": get_request_id(),
            "user_id": get_user_id(),
        },
        "settings": {
            "tracing": getattr(settings, "DJANGO_MATT_TRACING", {}),
            "metrics": getattr(settings, "DJANGO_MATT_METRICS", {}),
            "logging": getattr(settings, "DJANGO_MATT_LOGGING", {}),
        },
        "timestamp": time.time(),
    }

    return HttpResponse(
        json.dumps(debug_info, indent=2, default=str),
        content_type="application/json",
    )


# URL patterns for easy inclusion
urlpatterns = [
    path("_matt/metrics", metrics_view, name="observability-metrics"),
    path("_matt/info", info_view, name="observability-info"),
    path("_matt/debug", debug_view, name="observability-debug"),
    path("health", health_view, name="observability-health"),
    path("ready", ready_view, name="observability-ready"),
]


__all__ = [
    "metrics_view",
    "health_view",
    "ready_view",
    "info_view",
    "debug_view",
    "readiness_checker",
    "ReadinessChecker",
    "urlpatterns",
]
