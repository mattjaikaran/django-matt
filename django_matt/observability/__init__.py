"""
Django Matt Observability - Tracing, Metrics, and Structured Logging.

This module provides comprehensive observability features including:
- OpenTelemetry distributed tracing
- Prometheus-compatible metrics
- Structured JSON logging
- Request correlation IDs
- Integration with Datadog, New Relic, Jaeger, and more

Configuration in settings.py:

    # Tracing configuration
    DJANGO_MATT_TRACING = {
        "ENABLED": True,
        "SERVICE_NAME": "myapp",
        "EXPORTER": "jaeger",  # jaeger, otlp, datadog, newrelic, zipkin, console
        "ENDPOINT": "http://localhost:4317",
        "SAMPLE_RATE": 1.0,
    }

    # Metrics configuration
    DJANGO_MATT_METRICS = {
        "ENABLED": True,
        "PREFIX": "myapp",
        "DEFAULT_BUCKETS": [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    }

    # Logging configuration
    DJANGO_MATT_LOGGING = {
        "ENABLED": True,
        "FORMAT": "json",  # json, pretty, or text
        "LEVEL": "INFO",
    }

    # Or use the logging config generator
    LOGGING = get_logging_config(format="json", level="INFO")

Add middleware:

    MIDDLEWARE = [
        ...
        'django_matt.observability.TracingMiddleware',
        'django_matt.observability.MetricsMiddleware',
        'django_matt.observability.LoggingMiddleware',
        # Or use the combined middleware:
        # 'django_matt.observability.ObservabilityMiddleware',
    ]

Add URL patterns:

    from django_matt.observability import observability_urlpatterns

    urlpatterns = [
        ...
        path("", include(observability_urlpatterns)),
    ]

Example usage:

    from django_matt.observability import trace, metric, setup_tracing, get_logger

    # Set up tracing (call once at startup)
    setup_tracing(service_name="myapp", exporter="jaeger")

    # Get a structured logger
    logger = get_logger(__name__)

    # Use decorators on views
    @trace("get_users")
    @metric("users_fetched", labels=["status"])
    async def get_users(request):
        logger.info("Fetching users", user_count=100)
        return {"users": [], "status": "success"}
"""

# Tracing
from django_matt.observability.tracing import (
    HAS_DATADOG,
    HAS_JAEGER,
    HAS_NEWRELIC,
    HAS_OPENTELEMETRY,
    HAS_OTLP,
    HAS_ZIPKIN,
    NullSpan,
    NullTracer,
    TracingConfig,
    TracingManager,
    datadog_trace,
    extract_context,
    get_correlation_id,
    get_current_span,
    get_datadog_tracer,
    get_tracer,
    inject_headers,
    newrelic_trace,
    set_correlation_id,
    setup_tracing,
    tracing_config,
    tracing_manager,
)

# Metrics
from django_matt.observability.metrics import (
    HAS_PROMETHEUS,
    MetricsConfig,
    MetricsManager,
    decrement_active_requests,
    get_percentiles,
    increment_active_requests,
    metrics_config,
    metrics_manager,
    record_db_query,
    record_request,
)

# Logging
from django_matt.observability.logging import (
    BoundLogger,
    ColoredTextFormatter,
    JSONFormatter,
    LoggingConfig,
    PrettyJSONFormatter,
    StructuredLogger,
    clear_context,
    configure_logging,
    get_logger,
    get_logging_config,
    get_request_id,
    get_user_id,
    logging_config,
    set_request_id,
    set_user_id,
)

# Middleware
from django_matt.observability.middleware import (
    DatabaseQueryMiddleware,
    LoggingMiddleware,
    MetricsMiddleware,
    ObservabilityMiddleware,
    TracingMiddleware,
)

# Decorators
from django_matt.observability.decorators import (
    counted,
    metric,
    observe,
    timed,
    trace,
    with_span_attribute,
)

# Views
from django_matt.observability.views import (
    ReadinessChecker,
    debug_view,
    health_view,
    info_view,
    metrics_view,
    readiness_checker,
    ready_view,
)
from django_matt.observability.views import urlpatterns as observability_urlpatterns

__all__ = [
    # Tracing
    "TracingConfig",
    "TracingManager",
    "tracing_config",
    "tracing_manager",
    "setup_tracing",
    "get_tracer",
    "get_current_span",
    "get_correlation_id",
    "set_correlation_id",
    "inject_headers",
    "extract_context",
    "NullSpan",
    "NullTracer",
    "HAS_OPENTELEMETRY",
    "HAS_JAEGER",
    "HAS_OTLP",
    "HAS_ZIPKIN",
    "HAS_DATADOG",
    "HAS_NEWRELIC",
    "get_datadog_tracer",
    "datadog_trace",
    "newrelic_trace",
    # Metrics
    "MetricsConfig",
    "MetricsManager",
    "metrics_config",
    "metrics_manager",
    "record_request",
    "record_db_query",
    "increment_active_requests",
    "decrement_active_requests",
    "get_percentiles",
    "HAS_PROMETHEUS",
    # Logging
    "LoggingConfig",
    "logging_config",
    "JSONFormatter",
    "PrettyJSONFormatter",
    "ColoredTextFormatter",
    "StructuredLogger",
    "BoundLogger",
    "get_logger",
    "configure_logging",
    "get_logging_config",
    "set_request_id",
    "get_request_id",
    "set_user_id",
    "get_user_id",
    "clear_context",
    # Middleware
    "TracingMiddleware",
    "MetricsMiddleware",
    "LoggingMiddleware",
    "DatabaseQueryMiddleware",
    "ObservabilityMiddleware",
    # Decorators
    "trace",
    "metric",
    "timed",
    "counted",
    "observe",
    "with_span_attribute",
    # Views
    "metrics_view",
    "health_view",
    "ready_view",
    "info_view",
    "debug_view",
    "readiness_checker",
    "ReadinessChecker",
    "observability_urlpatterns",
]
