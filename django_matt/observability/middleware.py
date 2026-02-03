"""
Observability middleware for Django Matt.

This module provides middleware for automatic tracing, metrics collection,
and request logging.

Add to MIDDLEWARE in settings.py:

    MIDDLEWARE = [
        ...
        'django_matt.observability.TracingMiddleware',
        'django_matt.observability.MetricsMiddleware',
        'django_matt.observability.LoggingMiddleware',
    ]
"""

import logging
import time
import uuid
from typing import Any, Callable, Optional

from django.http import HttpRequest, HttpResponse

from django_matt.observability.logging import (
    clear_context,
    get_correlation_id,
    set_correlation_id,
    set_request_id,
    set_user_id,
)
from django_matt.observability.metrics import (
    decrement_active_requests,
    increment_active_requests,
    metrics_config,
    record_db_query,
    record_request,
)
from django_matt.observability.tracing import (
    HAS_OPENTELEMETRY,
    correlation_id_var,
    get_current_span,
    tracing_config,
    tracing_manager,
)

logger = logging.getLogger("django_matt.observability.middleware")


def _normalize_path(path: str) -> str:
    """
    Normalize a request path for use as a metric/span label.

    Replaces numeric path segments with placeholders to avoid high cardinality.
    """
    parts = path.strip("/").split("/")
    normalized = []

    for part in parts:
        # Replace numeric IDs with placeholder
        if part.isdigit():
            normalized.append("{id}")
        # Replace UUIDs with placeholder
        elif len(part) == 36 and part.count("-") == 4:
            try:
                uuid.UUID(part)
                normalized.append("{uuid}")
            except ValueError:
                normalized.append(part)
        # Replace hex strings (like short IDs)
        elif len(part) >= 8 and all(c in "0123456789abcdef" for c in part.lower()):
            normalized.append("{id}")
        else:
            normalized.append(part)

    return "/" + "/".join(normalized) if normalized else "/"


class TracingMiddleware:
    """
    Middleware for distributed tracing using OpenTelemetry.

    Creates spans for each request and propagates trace context.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        self.enabled = tracing_config.enabled

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self.enabled:
            return self.get_response(request)

        # Extract trace context from headers
        carrier = {
            key.replace("HTTP_", "").replace("_", "-").lower(): value
            for key, value in request.META.items()
            if key.startswith("HTTP_")
        }
        context = tracing_manager.extract_context(carrier)

        # Generate or extract correlation ID
        correlation_id = (
            carrier.get("x-correlation-id")
            or carrier.get("x-request-id")
            or str(uuid.uuid4())
        )
        correlation_id_var.set(correlation_id)

        # Create span name
        span_name = f"{request.method} {_normalize_path(request.path)}"

        # Span attributes
        attributes = {
            "http.method": request.method,
            "http.url": request.build_absolute_uri(),
            "http.path": request.path,
            "http.host": request.get_host(),
            "http.scheme": request.scheme,
            "http.user_agent": request.META.get("HTTP_USER_AGENT", ""),
            "correlation_id": correlation_id,
        }

        # Add user info if authenticated
        if hasattr(request, "user") and request.user.is_authenticated:
            attributes["user.id"] = str(request.user.pk)

        with tracing_manager.span(span_name, kind="server", attributes=attributes) as span:
            try:
                response = self.get_response(request)

                # Add response attributes
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.response_content_length", len(response.content) if hasattr(response, "content") else 0)

                # Set span status based on HTTP status
                if HAS_OPENTELEMETRY:
                    from opentelemetry.trace import Status, StatusCode

                    if response.status_code >= 500:
                        span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                    elif response.status_code >= 400:
                        span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                    else:
                        span.set_status(Status(StatusCode.OK))

                # Add trace headers to response
                response["X-Correlation-ID"] = correlation_id
                if HAS_OPENTELEMETRY and span.get_span_context():
                    span_context = span.get_span_context()
                    if hasattr(span_context, "trace_id"):
                        response["X-Trace-ID"] = format(span_context.trace_id, "032x")

                return response

            except Exception as e:
                # Record exception in span
                span.record_exception(e)
                if HAS_OPENTELEMETRY:
                    from opentelemetry.trace import Status, StatusCode

                    span.set_status(Status(StatusCode.ERROR, str(e)))
                raise


class MetricsMiddleware:
    """
    Middleware for collecting Prometheus metrics.

    Records request latency, count, and error rate.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        self.enabled = metrics_config.enabled

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self.enabled:
            return self.get_response(request)

        # Skip excluded paths
        for excluded in metrics_config.exclude_paths:
            if request.path.startswith(excluded):
                return self.get_response(request)

        method = request.method
        endpoint = _normalize_path(request.path)

        # Increment active requests
        increment_active_requests(method, endpoint)

        start_time = time.time()
        response = None
        status_code = 500

        try:
            response = self.get_response(request)
            status_code = response.status_code
            return response

        except Exception as e:
            # Record error
            status_code = 500
            raise

        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Decrement active requests
            decrement_active_requests(method, endpoint)

            # Record request metric
            record_request(method, endpoint, status_code, duration)

            # Add timing header to response
            if response is not None:
                response["X-Response-Time"] = f"{duration * 1000:.2f}ms"


class LoggingMiddleware:
    """
    Middleware for structured request logging.

    Logs request/response information with correlation IDs.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        self._logger = logging.getLogger("django_matt.observability.requests")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Generate request ID
        request_id = str(uuid.uuid4())
        set_request_id(request_id)

        # Get or generate correlation ID
        correlation_id = (
            request.META.get("HTTP_X_CORRELATION_ID")
            or request.META.get("HTTP_X_REQUEST_ID")
            or get_correlation_id()
            or request_id
        )
        set_correlation_id(correlation_id)

        # Set user ID if authenticated
        if hasattr(request, "user") and hasattr(request.user, "pk"):
            if request.user.is_authenticated:
                set_user_id(str(request.user.pk))

        # Store request info
        request._observability_start_time = time.time()
        request._observability_request_id = request_id
        request._observability_correlation_id = correlation_id

        # Log request
        self._logger.info(
            "Request started",
            extra={
                "extra": {
                    "method": request.method,
                    "path": request.path,
                    "query_string": request.META.get("QUERY_STRING", ""),
                    "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                    "remote_addr": self._get_client_ip(request),
                }
            },
        )

        try:
            response = self.get_response(request)

            # Calculate duration
            duration = time.time() - request._observability_start_time

            # Log response
            self._logger.info(
                "Request completed",
                extra={
                    "extra": {
                        "method": request.method,
                        "path": request.path,
                        "status_code": response.status_code,
                        "duration_ms": duration * 1000,
                        "content_length": response.get("Content-Length", 0),
                    }
                },
            )

            # Add headers to response
            response["X-Request-ID"] = request_id
            response["X-Correlation-ID"] = correlation_id

            return response

        except Exception as e:
            # Calculate duration
            duration = time.time() - request._observability_start_time

            # Log error
            self._logger.error(
                "Request failed",
                exc_info=True,
                extra={
                    "extra": {
                        "method": request.method,
                        "path": request.path,
                        "duration_ms": duration * 1000,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                },
            )
            raise

        finally:
            # Clear context
            clear_context()

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get the client IP address from the request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")


class DatabaseQueryMiddleware:
    """
    Middleware for tracking database queries.

    Records query count and timing for each request.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        self.enabled = metrics_config.enabled

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self.enabled:
            return self.get_response(request)

        from django.db import connection

        # Get initial query count
        initial_queries = len(connection.queries)

        response = self.get_response(request)

        # Get queries made during request
        queries = connection.queries[initial_queries:]

        # Record metrics for each query
        for query in queries:
            sql = query.get("sql", "")
            time_str = query.get("time", "0")
            try:
                duration = float(time_str)
            except ValueError:
                duration = 0.0

            # Determine operation type
            operation = "OTHER"
            sql_upper = sql.upper().strip()
            if sql_upper.startswith("SELECT"):
                operation = "SELECT"
            elif sql_upper.startswith("INSERT"):
                operation = "INSERT"
            elif sql_upper.startswith("UPDATE"):
                operation = "UPDATE"
            elif sql_upper.startswith("DELETE"):
                operation = "DELETE"

            # Extract table name (simplified)
            table = "unknown"
            if " FROM " in sql.upper():
                parts = sql.upper().split(" FROM ")
                if len(parts) > 1:
                    table_part = parts[1].split()[0]
                    table = table_part.strip('`"[]').lower()
            elif " INTO " in sql.upper():
                parts = sql.upper().split(" INTO ")
                if len(parts) > 1:
                    table_part = parts[1].split()[0]
                    table = table_part.strip('`"[]').lower()

            record_db_query(operation, table, duration)

        # Add query count to response header
        response["X-DB-Query-Count"] = str(len(queries))

        return response


class ObservabilityMiddleware:
    """
    Combined observability middleware.

    Includes tracing, metrics, and logging in a single middleware.
    Use this for convenience, or add individual middlewares for more control.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

        # Chain the middlewares
        self._logging = LoggingMiddleware(get_response)
        self._metrics = MetricsMiddleware(self._logging)
        self._tracing = TracingMiddleware(self._metrics)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self._tracing(request)


__all__ = [
    "TracingMiddleware",
    "MetricsMiddleware",
    "LoggingMiddleware",
    "DatabaseQueryMiddleware",
    "ObservabilityMiddleware",
]
