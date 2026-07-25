# file-length-max: 600
"""
Observability decorators for Django Matt.

This module provides decorators for adding tracing and metrics
to individual functions and views.

Example usage:

    from django_matt.observability import trace, metric

    @trace("get_users")
    @metric("users_fetched", labels=["status"])
    async def get_users(request):
        users = await User.objects.all()
        return {"users": users, "status": "success"}
"""

import functools
import logging
import time
from typing import Any, Callable, Optional, TypeVar

from django_matt.observability.metrics import metrics_manager
from django_matt.observability.tracing import HAS_OPENTELEMETRY, tracing_manager

logger = logging.getLogger("django_matt.observability.decorators")

F = TypeVar("F", bound=Callable[..., Any])


def trace(
    name: Optional[str] = None,
    kind: Optional[str] = None,
    attributes: Optional[dict[str, Any]] = None,
    record_exception: bool = True,
):
    """
    Decorator to create a trace span for a function.

    Args:
        name: Span name (defaults to function name)
        kind: Span kind (client, server, internal, producer, consumer)
        attributes: Additional span attributes
        record_exception: Whether to record exceptions in the span

    Returns:
        Decorated function

    Example:
        @trace("fetch_user_data")
        async def get_user(user_id: int):
            return await User.objects.get(pk=user_id)

        @trace("process_order", kind="internal", attributes={"order.type": "standard"})
        def process_order(order):
            ...
    """

    def decorator(func: F) -> F:
        span_name = name or func.__name__
        span_kind = kind or "internal"
        span_attributes = attributes or {}

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with tracing_manager.span(
                span_name, kind=span_kind, attributes=span_attributes
            ) as span:
                try:
                    result = func(*args, **kwargs)

                    # Add result info to span if it's a dict
                    if isinstance(result, dict) and "status" in result:
                        span.set_attribute("result.status", result["status"])

                    return result

                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                        span.set_attribute("error", True)
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))

                        if HAS_OPENTELEMETRY:
                            from opentelemetry.trace import Status, StatusCode

                            span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with tracing_manager.span(
                span_name, kind=span_kind, attributes=span_attributes
            ) as span:
                try:
                    result = await func(*args, **kwargs)

                    # Add result info to span if it's a dict
                    if isinstance(result, dict) and "status" in result:
                        span.set_attribute("result.status", result["status"])

                    return result

                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                        span.set_attribute("error", True)
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))

                        if HAS_OPENTELEMETRY:
                            from opentelemetry.trace import Status, StatusCode

                            span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def metric(
    name: str,
    metric_type: str = "counter",
    labels: Optional[list[str]] = None,
    description: str = "",
    buckets: Optional[list[float]] = None,
    increment_on_success: bool = True,
    increment_on_error: bool = True,
    record_duration: bool = False,
):
    """
    Decorator to record metrics for a function.

    Args:
        name: Metric name
        metric_type: Type of metric (counter, histogram, gauge)
        labels: Label names to extract from function result/kwargs
        description: Metric description
        buckets: Histogram buckets (for histogram type)
        increment_on_success: Increment counter on successful execution
        increment_on_error: Increment counter on exception
        record_duration: Also record execution duration as a histogram

    Returns:
        Decorated function

    Example:
        @metric("users_fetched", labels=["status"])
        async def get_users(request):
            return {"users": [], "status": "success"}

        @metric("api_calls", metric_type="histogram", record_duration=True)
        def call_external_api():
            ...
    """

    def decorator(func: F) -> F:
        # Create the main metric
        if metric_type == "counter":
            main_metric = metrics_manager.counter(name, description, labelnames=labels)
        elif metric_type == "histogram":
            main_metric = metrics_manager.histogram(
                name, description, labelnames=labels, buckets=buckets
            )
        elif metric_type == "gauge":
            main_metric = metrics_manager.gauge(name, description, labelnames=labels)
        else:
            main_metric = metrics_manager.counter(name, description, labelnames=labels)

        # Create duration metric if requested
        duration_metric = None
        if record_duration and metric_type != "histogram":
            duration_metric = metrics_manager.histogram(
                f"{name}_duration_seconds",
                f"Duration of {name}",
                labelnames=labels,
            )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            label_values: dict[str, str] = {}

            try:
                result = func(*args, **kwargs)

                # Extract label values from result or kwargs
                if labels:
                    if isinstance(result, dict):
                        label_values = {label: str(result.get(label, "")) for label in labels}
                    else:
                        label_values = {label: str(kwargs.get(label, "")) for label in labels}

                # Record metric
                if increment_on_success:
                    if labels and label_values:
                        if metric_type == "histogram":
                            main_metric.labels(**label_values).observe(time.time() - start_time)
                        else:
                            main_metric.labels(**label_values).inc()
                    elif metric_type == "histogram":
                        main_metric.observe(time.time() - start_time)
                    else:
                        main_metric.inc()

                # Record duration
                if duration_metric:
                    duration = time.time() - start_time
                    if labels and label_values:
                        duration_metric.labels(**label_values).observe(duration)
                    else:
                        duration_metric.observe(duration)

                return result

            except Exception as e:
                # Extract error labels
                if labels:
                    label_values = {label: kwargs.get(label, "") for label in labels}
                    if "error" in labels:
                        label_values["error"] = type(e).__name__

                # Record error metric
                if increment_on_error:
                    if labels and label_values:
                        main_metric.labels(**label_values).inc()
                    else:
                        main_metric.inc()

                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            label_values: dict[str, str] = {}

            try:
                result = await func(*args, **kwargs)

                # Extract label values from result or kwargs
                if labels:
                    if isinstance(result, dict):
                        label_values = {label: str(result.get(label, "")) for label in labels}
                    else:
                        label_values = {label: str(kwargs.get(label, "")) for label in labels}

                # Record metric
                if increment_on_success:
                    if labels and label_values:
                        if metric_type == "histogram":
                            main_metric.labels(**label_values).observe(time.time() - start_time)
                        else:
                            main_metric.labels(**label_values).inc()
                    elif metric_type == "histogram":
                        main_metric.observe(time.time() - start_time)
                    else:
                        main_metric.inc()

                # Record duration
                if duration_metric:
                    duration = time.time() - start_time
                    if labels and label_values:
                        duration_metric.labels(**label_values).observe(duration)
                    else:
                        duration_metric.observe(duration)

                return result

            except Exception as e:
                # Extract error labels
                if labels:
                    label_values = {label: kwargs.get(label, "") for label in labels}
                    if "error" in labels:
                        label_values["error"] = type(e).__name__

                # Record error metric
                if increment_on_error:
                    if labels and label_values:
                        main_metric.labels(**label_values).inc()
                    else:
                        main_metric.inc()

                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def timed(
    name: Optional[str] = None,
    labels: Optional[dict[str, str]] = None,
    buckets: Optional[list[float]] = None,
):
    """
    Decorator to time function execution.

    A simplified wrapper around @metric with histogram type.

    Args:
        name: Metric name (defaults to function_<name>_duration_seconds)
        labels: Static labels for the metric
        buckets: Histogram buckets

    Returns:
        Decorated function

    Example:
        @timed()
        def slow_operation():
            time.sleep(1)

        @timed("api_call_duration", labels={"service": "external"})
        async def call_api():
            ...
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


def counted(
    name: Optional[str] = None,
    labels: Optional[dict[str, str]] = None,
    count_exceptions: bool = True,
):
    """
    Decorator to count function calls.

    A simplified wrapper around @metric with counter type.

    Args:
        name: Metric name (defaults to function_<name>_calls_total)
        labels: Static labels for the metric
        count_exceptions: Whether to count calls that raise exceptions

    Returns:
        Decorated function

    Example:
        @counted()
        def process_item(item):
            ...

        @counted("api_requests", labels={"endpoint": "/users"})
        async def get_users():
            ...
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
            try:
                result = func(*args, **kwargs)
                if labels:
                    counter.labels(**labels).inc()
                else:
                    counter.inc()
                return result
            except Exception:
                if count_exceptions:
                    if labels:
                        counter.labels(**labels).inc()
                    else:
                        counter.inc()
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                if labels:
                    counter.labels(**labels).inc()
                else:
                    counter.inc()
                return result
            except Exception:
                if count_exceptions:
                    if labels:
                        counter.labels(**labels).inc()
                    else:
                        counter.inc()
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def observe(
    name: str,
    value_extractor: Callable[[Any], float],
    labels: Optional[dict[str, str]] = None,
    description: str = "",
):
    """
    Decorator to observe a value from function results.

    Args:
        name: Metric name
        value_extractor: Function to extract the value to observe from the result
        labels: Static labels for the metric
        description: Metric description

    Returns:
        Decorated function

    Example:
        @observe("items_processed", lambda r: r["count"])
        def process_batch(items):
            processed = [process(i) for i in items]
            return {"items": processed, "count": len(processed)}
    """

    def decorator(func: F) -> F:
        label_names = list(labels.keys()) if labels else []

        histogram = metrics_manager.histogram(
            name,
            description or f"Observed values from {func.__name__}",
            labelnames=label_names,
        )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            try:
                value = value_extractor(result)
                if labels:
                    histogram.labels(**labels).observe(value)
                else:
                    histogram.observe(value)
            except Exception as e:
                logger.warning(f"Failed to extract value for metric {name}: {e}")
            return result

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            try:
                value = value_extractor(result)
                if labels:
                    histogram.labels(**labels).observe(value)
                else:
                    histogram.observe(value)
            except Exception as e:
                logger.warning(f"Failed to extract value for metric {name}: {e}")
            return result

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def with_span_attribute(key: str, value_extractor: Callable[[Any], Any]):
    """
    Decorator to add an attribute to the current span from function result.

    Args:
        key: Attribute key
        value_extractor: Function to extract the value from the result

    Returns:
        Decorated function

    Example:
        @trace("get_user")
        @with_span_attribute("user.email", lambda r: r.get("email"))
        async def get_user(user_id):
            return await fetch_user(user_id)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            try:
                value = value_extractor(result)
                span = tracing_manager.get_current_span()
                span.set_attribute(key, value)
            except Exception as e:
                logger.warning(f"Failed to set span attribute {key}: {e}")
            return result

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            try:
                value = value_extractor(result)
                span = tracing_manager.get_current_span()
                span.set_attribute(key, value)
            except Exception as e:
                logger.warning(f"Failed to set span attribute {key}: {e}")
            return result

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


__all__ = [
    "trace",
    "metric",
    "timed",
    "counted",
    "observe",
    "with_span_attribute",
]
