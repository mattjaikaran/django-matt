"""
Prometheus-compatible metrics for Django Matt.

This module provides Prometheus metrics collection and exposure,
with support for custom metrics, histograms, and counters.

Configuration in settings.py:

    DJANGO_MATT_METRICS = {
        "ENABLED": True,
        "PREFIX": "django_matt",
        "DEFAULT_BUCKETS": [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        "INCLUDE_HOST": True,
        "INCLUDE_METHOD": True,
        "INCLUDE_PATH": True,
        "INCLUDE_STATUS": True,
    }
"""

import functools
import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Callable, Optional, TypeVar

from django.conf import settings

logger = logging.getLogger("django_matt.observability.metrics")

# Try to import prometheus_client
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Info,
        Summary,
        generate_latest,
        multiprocess,
    )

    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"
    REGISTRY = None
    CollectorRegistry = None
    Counter = None
    Gauge = None
    Histogram = None
    Info = None
    Summary = None
    generate_latest = None
    multiprocess = None


F = TypeVar("F", bound=Callable[..., Any])


class MetricsConfig:
    """Configuration for metrics."""

    def __init__(self):
        self._config = getattr(settings, "DJANGO_MATT_METRICS", {})

    @property
    def enabled(self) -> bool:
        return self._config.get("ENABLED", True)

    @property
    def prefix(self) -> str:
        return self._config.get("PREFIX", "django_matt")

    @property
    def default_buckets(self) -> list[float]:
        return self._config.get(
            "DEFAULT_BUCKETS",
            [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )

    @property
    def include_host(self) -> bool:
        return self._config.get("INCLUDE_HOST", True)

    @property
    def include_method(self) -> bool:
        return self._config.get("INCLUDE_METHOD", True)

    @property
    def include_path(self) -> bool:
        return self._config.get("INCLUDE_PATH", True)

    @property
    def include_status(self) -> bool:
        return self._config.get("INCLUDE_STATUS", True)

    @property
    def exclude_paths(self) -> list[str]:
        return self._config.get("EXCLUDE_PATHS", ["/_matt/metrics", "/health", "/ready"])


metrics_config = MetricsConfig()


class FallbackMetric:
    """A fallback metric class when prometheus_client is not installed."""

    def __init__(self, name: str, description: str = "", labelnames: Optional[list[str]] = None):
        self.name = name
        self.description = description
        self.labelnames = labelnames or []
        self._values: dict[tuple, float] = defaultdict(float)
        self._label_values: dict[tuple, dict[str, str]] = {}

    def labels(self, **kwargs) -> "FallbackMetric":
        """Return a labeled metric instance."""
        label_values = tuple(kwargs.get(name, "") for name in self.labelnames)
        self._label_values[label_values] = kwargs
        return FallbackLabeledMetric(self, label_values)


class FallbackLabeledMetric:
    """A labeled version of the fallback metric."""

    def __init__(self, parent: FallbackMetric, label_values: tuple):
        self._parent = parent
        self._label_values = label_values

    def inc(self, amount: float = 1) -> None:
        self._parent._values[self._label_values] += amount

    def dec(self, amount: float = 1) -> None:
        self._parent._values[self._label_values] -= amount

    def set(self, value: float) -> None:
        self._parent._values[self._label_values] = value

    def observe(self, value: float) -> None:
        # For histograms/summaries, just store the latest value
        self._parent._values[self._label_values] = value


class FallbackCounter(FallbackMetric):
    """Fallback counter metric."""

    def inc(self, amount: float = 1) -> None:
        self._values[()] += amount


class FallbackGauge(FallbackMetric):
    """Fallback gauge metric."""

    def inc(self, amount: float = 1) -> None:
        self._values[()] += amount

    def dec(self, amount: float = 1) -> None:
        self._values[()] -= amount

    def set(self, value: float) -> None:
        self._values[()] = value


class FallbackHistogram(FallbackMetric):
    """Fallback histogram metric."""

    def __init__(
        self,
        name: str,
        description: str = "",
        labelnames: Optional[list[str]] = None,
        buckets: Optional[list[float]] = None,
    ):
        super().__init__(name, description, labelnames)
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._observations: dict[tuple, list[float]] = defaultdict(list)

    def observe(self, value: float) -> None:
        self._observations[()].append(value)

    @contextmanager
    def time(self):
        start = time.time()
        yield
        self.observe(time.time() - start)


class FallbackSummary(FallbackMetric):
    """Fallback summary metric."""

    def __init__(self, name: str, description: str = "", labelnames: Optional[list[str]] = None):
        super().__init__(name, description, labelnames)
        self._observations: dict[tuple, list[float]] = defaultdict(list)

    def observe(self, value: float) -> None:
        self._observations[()].append(value)


class MetricsManager:
    """
    Manager for Prometheus metrics.

    Handles metric creation, registration, and exposure.
    """

    def __init__(self):
        self._metrics: dict[str, Any] = {}
        self._registry = REGISTRY if HAS_PROMETHEUS else None
        self._initialized = False

    def setup(self, registry: Optional[Any] = None) -> bool:
        """
        Set up metrics collection.

        Args:
            registry: Optional custom Prometheus registry

        Returns:
            True if setup was successful
        """
        if not metrics_config.enabled:
            logger.debug("Metrics collection is disabled")
            return False

        if registry:
            self._registry = registry

        self._initialized = True
        logger.info("Metrics collection initialized")
        return True

    def _get_prefixed_name(self, name: str) -> str:
        """Get metric name with prefix."""
        prefix = metrics_config.prefix
        if prefix and not name.startswith(prefix):
            return f"{prefix}_{name}"
        return name

    def counter(
        self,
        name: str,
        description: str = "",
        labelnames: Optional[list[str]] = None,
    ) -> Any:
        """
        Create or get a counter metric.

        Args:
            name: Metric name
            description: Metric description
            labelnames: Label names for the metric

        Returns:
            Counter metric instance
        """
        full_name = self._get_prefixed_name(name)

        if full_name in self._metrics:
            return self._metrics[full_name]

        if HAS_PROMETHEUS:
            metric = Counter(
                full_name,
                description or f"Counter for {name}",
                labelnames=labelnames or [],
                registry=self._registry,
            )
        else:
            metric = FallbackCounter(full_name, description, labelnames)

        self._metrics[full_name] = metric
        return metric

    def gauge(
        self,
        name: str,
        description: str = "",
        labelnames: Optional[list[str]] = None,
    ) -> Any:
        """
        Create or get a gauge metric.

        Args:
            name: Metric name
            description: Metric description
            labelnames: Label names for the metric

        Returns:
            Gauge metric instance
        """
        full_name = self._get_prefixed_name(name)

        if full_name in self._metrics:
            return self._metrics[full_name]

        if HAS_PROMETHEUS:
            metric = Gauge(
                full_name,
                description or f"Gauge for {name}",
                labelnames=labelnames or [],
                registry=self._registry,
            )
        else:
            metric = FallbackGauge(full_name, description, labelnames)

        self._metrics[full_name] = metric
        return metric

    def histogram(
        self,
        name: str,
        description: str = "",
        labelnames: Optional[list[str]] = None,
        buckets: Optional[list[float]] = None,
    ) -> Any:
        """
        Create or get a histogram metric.

        Args:
            name: Metric name
            description: Metric description
            labelnames: Label names for the metric
            buckets: Histogram buckets

        Returns:
            Histogram metric instance
        """
        full_name = self._get_prefixed_name(name)

        if full_name in self._metrics:
            return self._metrics[full_name]

        bucket_values = buckets or metrics_config.default_buckets

        if HAS_PROMETHEUS:
            metric = Histogram(
                full_name,
                description or f"Histogram for {name}",
                labelnames=labelnames or [],
                buckets=bucket_values,
                registry=self._registry,
            )
        else:
            metric = FallbackHistogram(full_name, description, labelnames, bucket_values)

        self._metrics[full_name] = metric
        return metric

    def summary(
        self,
        name: str,
        description: str = "",
        labelnames: Optional[list[str]] = None,
    ) -> Any:
        """
        Create or get a summary metric.

        Args:
            name: Metric name
            description: Metric description
            labelnames: Label names for the metric

        Returns:
            Summary metric instance
        """
        full_name = self._get_prefixed_name(name)

        if full_name in self._metrics:
            return self._metrics[full_name]

        if HAS_PROMETHEUS:
            metric = Summary(
                full_name,
                description or f"Summary for {name}",
                labelnames=labelnames or [],
                registry=self._registry,
            )
        else:
            metric = FallbackSummary(full_name, description, labelnames)

        self._metrics[full_name] = metric
        return metric

    def info(
        self,
        name: str,
        description: str = "",
    ) -> Any:
        """
        Create or get an info metric.

        Args:
            name: Metric name
            description: Metric description

        Returns:
            Info metric instance
        """
        full_name = self._get_prefixed_name(name)

        if full_name in self._metrics:
            return self._metrics[full_name]

        if HAS_PROMETHEUS:
            metric = Info(
                full_name,
                description or f"Info for {name}",
                registry=self._registry,
            )
        else:
            metric = FallbackMetric(full_name, description)

        self._metrics[full_name] = metric
        return metric

    def generate_metrics(self) -> bytes:
        """
        Generate metrics output in Prometheus format.

        Returns:
            Metrics output as bytes
        """
        if HAS_PROMETHEUS:
            return generate_latest(self._registry)
        # Generate basic text format for fallback metrics
        lines = []
        for name, metric in self._metrics.items():
            if isinstance(metric, FallbackCounter) or isinstance(metric, FallbackGauge):
                for labels, value in metric._values.items():
                    lines.append(f"{name} {value}")
            elif isinstance(metric, FallbackHistogram):
                for labels, observations in metric._observations.items():
                    if observations:
                        count = len(observations)
                        total = sum(observations)
                        lines.append(f"{name}_count {count}")
                        lines.append(f"{name}_sum {total}")
        return "\n".join(lines).encode("utf-8")

    def get_content_type(self) -> str:
        """Get the content type for metrics output."""
        return CONTENT_TYPE_LATEST if HAS_PROMETHEUS else "text/plain; version=0.0.4"

    def remove_metric(self, name: str) -> bool:
        """
        Remove a metric from the registry.

        Args:
            name: Metric name

        Returns:
            True if metric was removed
        """
        full_name = self._get_prefixed_name(name)
        if full_name in self._metrics:
            del self._metrics[full_name]
            return True
        return False


# Global metrics manager instance
metrics_manager = MetricsManager()


# Default metrics
def _get_request_latency():
    """Get the request latency histogram."""
    return metrics_manager.histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds",
        labelnames=["method", "endpoint", "status"],
    )


def _get_request_count():
    """Get the request count counter."""
    return metrics_manager.counter(
        "http_requests_total",
        "Total HTTP requests",
        labelnames=["method", "endpoint", "status"],
    )


def _get_error_count():
    """Get the error count counter."""
    return metrics_manager.counter(
        "http_errors_total",
        "Total HTTP errors",
        labelnames=["method", "endpoint", "error_type"],
    )


def _get_db_query_count():
    """Get the database query count counter."""
    return metrics_manager.counter(
        "db_queries_total",
        "Total database queries",
        labelnames=["operation", "table"],
    )


def _get_db_query_duration():
    """Get the database query duration histogram."""
    return metrics_manager.histogram(
        "db_query_duration_seconds",
        "Database query duration in seconds",
        labelnames=["operation", "table"],
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    )


def _get_active_requests():
    """Get the active requests gauge."""
    return metrics_manager.gauge(
        "http_requests_active",
        "Currently active HTTP requests",
        labelnames=["method", "endpoint"],
    )


# Convenience functions
def record_request(
    method: str,
    endpoint: str,
    status: int,
    duration: float,
) -> None:
    """
    Record a request metric.

    Args:
        method: HTTP method
        endpoint: Request endpoint/path
        status: HTTP status code
        duration: Request duration in seconds
    """
    if not metrics_config.enabled:
        return

    status_str = str(status)

    # Record latency
    latency = _get_request_latency()
    latency.labels(method=method, endpoint=endpoint, status=status_str).observe(duration)

    # Record count
    count = _get_request_count()
    count.labels(method=method, endpoint=endpoint, status=status_str).inc()

    # Record error if status >= 400
    if status >= 400:
        error_type = "client_error" if status < 500 else "server_error"
        errors = _get_error_count()
        errors.labels(method=method, endpoint=endpoint, error_type=error_type).inc()


def record_db_query(
    operation: str,
    table: str,
    duration: float,
) -> None:
    """
    Record a database query metric.

    Args:
        operation: Query operation (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        duration: Query duration in seconds
    """
    if not metrics_config.enabled:
        return

    # Record count
    count = _get_db_query_count()
    count.labels(operation=operation, table=table).inc()

    # Record duration
    duration_metric = _get_db_query_duration()
    duration_metric.labels(operation=operation, table=table).observe(duration)


def increment_active_requests(method: str, endpoint: str) -> None:
    """Increment the active requests gauge."""
    if not metrics_config.enabled:
        return
    active = _get_active_requests()
    active.labels(method=method, endpoint=endpoint).inc()


def decrement_active_requests(method: str, endpoint: str) -> None:
    """Decrement the active requests gauge."""
    if not metrics_config.enabled:
        return
    active = _get_active_requests()
    active.labels(method=method, endpoint=endpoint).dec()


def get_percentiles(histogram_name: str) -> dict[str, float]:
    """
    Get percentile values for a histogram.

    Args:
        histogram_name: Name of the histogram

    Returns:
        Dictionary with p50, p95, p99 values
    """
    full_name = metrics_manager._get_prefixed_name(histogram_name)
    metric = metrics_manager._metrics.get(full_name)

    if metric is None:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    if isinstance(metric, FallbackHistogram):
        observations = metric._observations.get((), [])
        if not observations:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

        sorted_obs = sorted(observations)
        n = len(sorted_obs)
        return {
            "p50": sorted_obs[int(n * 0.5)] if n > 0 else 0.0,
            "p95": sorted_obs[int(n * 0.95)] if n > 0 else 0.0,
            "p99": sorted_obs[int(n * 0.99)] if n > 0 else 0.0,
        }

    # For actual Prometheus histograms, percentiles are calculated at query time
    # This function would need prometheus client's quantile support
    return {"p50": 0.0, "p95": 0.0, "p99": 0.0}


# Decorator for timing functions
def timed(
    name: Optional[str] = None,
    labels: Optional[dict[str, str]] = None,
    buckets: Optional[list[float]] = None,
):
    """
    Decorator to time function execution and record as a histogram.

    Args:
        name: Metric name (defaults to function name)
        labels: Static labels for the metric
        buckets: Histogram buckets

    Returns:
        Decorated function
    """

    def decorator(func: F) -> F:
        metric_name = name or f"function_{func.__name__}_duration_seconds"
        label_names = list(labels.keys()) if labels else []

        histogram = metrics_manager.histogram(
            metric_name,
            f"Duration of {func.__name__}",
            labelnames=label_names,
            buckets=buckets,
        )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start
                if labels:
                    histogram.labels(**labels).observe(duration)
                else:
                    histogram.observe(duration)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.time() - start
                if labels:
                    histogram.labels(**labels).observe(duration)
                else:
                    histogram.observe(duration)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


# Decorator for counting function calls
def counted(
    name: Optional[str] = None,
    labels: Optional[dict[str, str]] = None,
):
    """
    Decorator to count function calls.

    Args:
        name: Metric name (defaults to function name)
        labels: Static labels for the metric

    Returns:
        Decorated function
    """

    def decorator(func: F) -> F:
        metric_name = name or f"function_{func.__name__}_calls_total"
        label_names = list(labels.keys()) if labels else []

        counter = metrics_manager.counter(
            metric_name,
            f"Total calls to {func.__name__}",
            labelnames=label_names,
        )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if labels:
                counter.labels(**labels).inc()
            else:
                counter.inc()
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if labels:
                counter.labels(**labels).inc()
            else:
                counter.inc()
            return await func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


__all__ = [
    "MetricsConfig",
    "MetricsManager",
    "metrics_config",
    "metrics_manager",
    "record_request",
    "record_db_query",
    "increment_active_requests",
    "decrement_active_requests",
    "get_percentiles",
    "timed",
    "counted",
    "HAS_PROMETHEUS",
    "FallbackMetric",
    "FallbackCounter",
    "FallbackGauge",
    "FallbackHistogram",
    "FallbackSummary",
]
