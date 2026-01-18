"""
Middleware for collecting performance metrics.

Automatically collects metrics for each request including:
- Request timing
- Database query counts
- Cache statistics
- Memory usage
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import connection
from django.utils import timezone

from django_matt.dashboard.collector import RequestMetrics, get_collector

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


class MetricsMiddleware:
    """
    Middleware for collecting request metrics.

    Add to MIDDLEWARE in settings.py:
        'django_matt.dashboard.MetricsMiddleware'

    Configuration via DJANGO_MATT_DASHBOARD setting:
        DJANGO_MATT_DASHBOARD = {
            "ENABLED": True,
            "COLLECT_METRICS": True,
            "EXCLUDED_PATHS": ["/_dashboard/", "/static/", "/media/"],
            "TRACK_QUERIES": True,
            "TRACK_MEMORY": False,
        }
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._config = getattr(settings, "DJANGO_MATT_DASHBOARD", {})

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self._should_collect(request):
            return self.get_response(request)

        # Start timing
        start_time = time.perf_counter()
        start_queries = len(connection.queries) if self._track_queries else 0

        # Get memory usage before (if enabled)
        memory_before = self._get_memory_usage() if self._track_memory else 0

        # Process request
        error = None
        try:
            response = self.get_response(request)
        except Exception as e:
            error = str(e)
            raise
        finally:
            # Calculate metrics
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Database metrics
            if self._track_queries:
                end_queries = len(connection.queries)
                db_query_count = end_queries - start_queries
                db_query_time_ms = sum(
                    float(q.get("time", 0)) * 1000
                    for q in connection.queries[start_queries:end_queries]
                )
            else:
                db_query_count = 0
                db_query_time_ms = 0

            # Memory metrics
            if self._track_memory:
                memory_after = self._get_memory_usage()
                memory_used_mb = memory_after - memory_before
            else:
                memory_used_mb = 0

            # Get status code (use 500 if exception occurred)
            status_code = getattr(response, "status_code", 500) if "response" in dir() else 500

            # Create metrics record
            metrics = RequestMetrics(
                timestamp=timezone.now(),
                path=request.path,
                method=request.method,
                status_code=status_code,
                duration_ms=duration_ms,
                db_query_count=db_query_count,
                db_query_time_ms=db_query_time_ms,
                cache_hits=getattr(request, "_cache_hits", 0),
                cache_misses=getattr(request, "_cache_misses", 0),
                memory_used_mb=memory_used_mb,
                user_id=self._get_user_id(request),
                ip_address=self._get_client_ip(request),
                error=error,
            )

            # Record metrics
            try:
                collector = get_collector()
                collector.record(metrics)
            except Exception:
                # Don't let metrics collection break the request
                pass

        return response

    @property
    def _enabled(self) -> bool:
        """Check if metrics collection is enabled."""
        return self._config.get("ENABLED", True) and self._config.get(
            "COLLECT_METRICS", True
        )

    @property
    def _track_queries(self) -> bool:
        """Check if query tracking is enabled."""
        return self._config.get("TRACK_QUERIES", True)

    @property
    def _track_memory(self) -> bool:
        """Check if memory tracking is enabled."""
        return self._config.get("TRACK_MEMORY", False)

    @property
    def _excluded_paths(self) -> list[str]:
        """Get paths to exclude from metrics collection."""
        return self._config.get(
            "EXCLUDED_PATHS",
            ["/_dashboard/", "/static/", "/media/", "/favicon.ico"],
        )

    def _should_collect(self, request: HttpRequest) -> bool:
        """Check if metrics should be collected for this request."""
        if not self._enabled:
            return False

        path = request.path
        for excluded in self._excluded_paths:
            if path.startswith(excluded):
                return False

        return True

    def _get_user_id(self, request: HttpRequest) -> int | None:
        """Get the user ID from the request."""
        if hasattr(request, "user") and request.user.is_authenticated:
            return request.user.id
        return None

    def _get_client_ip(self, request: HttpRequest) -> str | None:
        """Get the client IP address from the request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF)
            return usage.ru_maxrss / 1024 / 1024  # Convert to MB
        except ImportError:
            try:
                import psutil

                process = psutil.Process()
                return process.memory_info().rss / 1024 / 1024  # Convert to MB
            except ImportError:
                return 0


__all__ = ["MetricsMiddleware"]
