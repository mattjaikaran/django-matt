"""
Metrics collection for the performance dashboard.

Collects and stores request metrics, database queries, cache statistics,
and other performance data.
"""

from __future__ import annotations

import statistics
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    pass


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    timestamp: datetime
    path: str
    method: str
    status_code: int
    duration_ms: float
    db_query_count: int = 0
    db_query_time_ms: float = 0
    cache_hits: int = 0
    cache_misses: int = 0
    memory_used_mb: float = 0
    user_id: int | None = None
    ip_address: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "path": self.path,
            "method": self.method,
            "status_code": self.status_code,
            "duration_ms": round(self.duration_ms, 2),
            "db_query_count": self.db_query_count,
            "db_query_time_ms": round(self.db_query_time_ms, 2),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "memory_used_mb": round(self.memory_used_mb, 2),
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "error": self.error,
        }


@dataclass
class EndpointStats:
    """Aggregated statistics for an endpoint."""

    path: str
    method: str
    request_count: int = 0
    total_duration_ms: float = 0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0
    avg_duration_ms: float = 0
    p50_duration_ms: float = 0
    p95_duration_ms: float = 0
    p99_duration_ms: float = 0
    error_count: int = 0
    error_rate: float = 0
    db_query_avg: float = 0
    durations: list[float] = field(default_factory=list)

    def add_request(self, metrics: RequestMetrics):
        """Add a request's metrics to the statistics."""
        self.request_count += 1
        self.total_duration_ms += metrics.duration_ms
        self.min_duration_ms = min(self.min_duration_ms, metrics.duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, metrics.duration_ms)
        self.avg_duration_ms = self.total_duration_ms / self.request_count

        if metrics.error or metrics.status_code >= 500:
            self.error_count += 1
            self.error_rate = (self.error_count / self.request_count) * 100

        # Store durations for percentile calculation (limit to last 1000)
        self.durations.append(metrics.duration_ms)
        if len(self.durations) > 1000:
            self.durations = self.durations[-1000:]

        # Calculate percentiles
        if len(self.durations) >= 10:
            sorted_durations = sorted(self.durations)
            self.p50_duration_ms = sorted_durations[len(sorted_durations) // 2]
            self.p95_duration_ms = sorted_durations[int(len(sorted_durations) * 0.95)]
            self.p99_duration_ms = sorted_durations[int(len(sorted_durations) * 0.99)]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "method": self.method,
            "request_count": self.request_count,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2) if self.min_duration_ms != float("inf") else 0,
            "max_duration_ms": round(self.max_duration_ms, 2),
            "p50_duration_ms": round(self.p50_duration_ms, 2),
            "p95_duration_ms": round(self.p95_duration_ms, 2),
            "p99_duration_ms": round(self.p99_duration_ms, 2),
            "error_count": self.error_count,
            "error_rate": round(self.error_rate, 2),
        }


class MetricsCollector:
    """
    Collects and stores performance metrics.

    Thread-safe collector that stores metrics in memory with configurable
    retention period.
    """

    def __init__(
        self,
        max_requests: int = 10000,
        retention_hours: int = 24,
    ):
        self.max_requests = max_requests
        self.retention_hours = retention_hours
        self._requests: deque[RequestMetrics] = deque(maxlen=max_requests)
        self._endpoint_stats: dict[str, EndpointStats] = {}
        self._lock = threading.Lock()
        self._start_time = timezone.now()

        # Aggregated counters
        self._total_requests = 0
        self._total_errors = 0
        self._status_codes: dict[int, int] = {}

        # Time-series data for charts (1-minute buckets)
        self._time_buckets: dict[str, dict[str, Any]] = {}

    def record(self, metrics: RequestMetrics):
        """Record a request's metrics."""
        with self._lock:
            self._requests.append(metrics)
            self._total_requests += 1

            # Update status code counts
            self._status_codes[metrics.status_code] = (
                self._status_codes.get(metrics.status_code, 0) + 1
            )

            if metrics.error or metrics.status_code >= 500:
                self._total_errors += 1

            # Update endpoint stats
            key = f"{metrics.method}:{metrics.path}"
            if key not in self._endpoint_stats:
                self._endpoint_stats[key] = EndpointStats(
                    path=metrics.path,
                    method=metrics.method,
                )
            self._endpoint_stats[key].add_request(metrics)

            # Update time bucket
            bucket_key = metrics.timestamp.strftime("%Y-%m-%d %H:%M")
            if bucket_key not in self._time_buckets:
                self._time_buckets[bucket_key] = {
                    "timestamp": bucket_key,
                    "request_count": 0,
                    "total_duration_ms": 0,
                    "error_count": 0,
                    "db_queries": 0,
                }
            bucket = self._time_buckets[bucket_key]
            bucket["request_count"] += 1
            bucket["total_duration_ms"] += metrics.duration_ms
            bucket["db_queries"] += metrics.db_query_count
            if metrics.error or metrics.status_code >= 500:
                bucket["error_count"] += 1

            # Clean old time buckets
            self._clean_old_buckets()

    def _clean_old_buckets(self):
        """Remove time buckets older than retention period."""
        cutoff = timezone.now() - timedelta(hours=self.retention_hours)
        cutoff_key = cutoff.strftime("%Y-%m-%d %H:%M")

        keys_to_remove = [k for k in self._time_buckets if k < cutoff_key]
        for key in keys_to_remove:
            del self._time_buckets[key]

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        with self._lock:
            uptime = (timezone.now() - self._start_time).total_seconds()

            # Calculate requests per minute
            if uptime > 0:
                rpm = (self._total_requests / uptime) * 60
            else:
                rpm = 0

            # Get recent requests for response time stats
            recent_durations = [r.duration_ms for r in list(self._requests)[-1000:]]

            if recent_durations:
                avg_response_time = statistics.mean(recent_durations)
                p50 = statistics.median(recent_durations)
                sorted_d = sorted(recent_durations)
                p95 = sorted_d[int(len(sorted_d) * 0.95)] if len(sorted_d) > 20 else 0
                p99 = sorted_d[int(len(sorted_d) * 0.99)] if len(sorted_d) > 100 else 0
            else:
                avg_response_time = p50 = p95 = p99 = 0

            return {
                "uptime_seconds": int(uptime),
                "uptime_formatted": self._format_uptime(uptime),
                "total_requests": self._total_requests,
                "total_errors": self._total_errors,
                "error_rate": round((self._total_errors / max(self._total_requests, 1)) * 100, 2),
                "requests_per_minute": round(rpm, 2),
                "avg_response_time_ms": round(avg_response_time, 2),
                "p50_response_time_ms": round(p50, 2),
                "p95_response_time_ms": round(p95, 2),
                "p99_response_time_ms": round(p99, 2),
                "status_codes": dict(self._status_codes),
            }

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime as human-readable string."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def get_endpoints(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get top endpoints by request count."""
        with self._lock:
            sorted_endpoints = sorted(
                self._endpoint_stats.values(),
                key=lambda e: e.request_count,
                reverse=True,
            )[:limit]
            return [e.to_dict() for e in sorted_endpoints]

    def get_slowest_endpoints(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get slowest endpoints by average response time."""
        with self._lock:
            sorted_endpoints = sorted(
                self._endpoint_stats.values(),
                key=lambda e: e.avg_duration_ms,
                reverse=True,
            )[:limit]
            return [e.to_dict() for e in sorted_endpoints]

    def get_error_endpoints(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get endpoints with highest error rates."""
        with self._lock:
            endpoints_with_errors = [
                e for e in self._endpoint_stats.values() if e.error_count > 0
            ]
            sorted_endpoints = sorted(
                endpoints_with_errors,
                key=lambda e: e.error_rate,
                reverse=True,
            )[:limit]
            return [e.to_dict() for e in sorted_endpoints]

    def get_recent_requests(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent requests."""
        with self._lock:
            recent = list(self._requests)[-limit:]
            return [r.to_dict() for r in reversed(recent)]

    def get_time_series(self, minutes: int = 60) -> list[dict[str, Any]]:
        """Get time series data for charts."""
        with self._lock:
            cutoff = timezone.now() - timedelta(minutes=minutes)
            cutoff_key = cutoff.strftime("%Y-%m-%d %H:%M")

            # Filter and sort buckets
            series = [
                {
                    **bucket,
                    "avg_duration_ms": round(
                        bucket["total_duration_ms"] / max(bucket["request_count"], 1), 2
                    ),
                }
                for key, bucket in sorted(self._time_buckets.items())
                if key >= cutoff_key
            ]
            return series

    def reset(self):
        """Reset all collected metrics."""
        with self._lock:
            self._requests.clear()
            self._endpoint_stats.clear()
            self._total_requests = 0
            self._total_errors = 0
            self._status_codes.clear()
            self._time_buckets.clear()
            self._start_time = timezone.now()


# Global collector instance
_collector: MetricsCollector | None = None
_collector_lock = threading.Lock()


def get_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _collector

    with _collector_lock:
        if _collector is None:
            config = getattr(settings, "DJANGO_MATT_DASHBOARD", {})
            _collector = MetricsCollector(
                max_requests=config.get("MAX_REQUESTS", 10000),
                retention_hours=config.get("RETENTION_HOURS", 24),
            )
        return _collector


__all__ = [
    "RequestMetrics",
    "EndpointStats",
    "MetricsCollector",
    "get_collector",
]
