"""
OpenTelemetry tracing for Django Matt.

This module provides OpenTelemetry integration for distributed tracing,
with support for various exporters including Jaeger, Datadog, and more.

Configuration in settings.py:

    DJANGO_MATT_TRACING = {
        "ENABLED": True,
        "SERVICE_NAME": "myapp",
        "EXPORTER": "jaeger",  # jaeger, otlp, datadog, newrelic, zipkin, console
        "ENDPOINT": "http://localhost:4317",
        "SAMPLE_RATE": 1.0,
        "PROPAGATORS": ["tracecontext", "baggage"],
    }
"""

import functools
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Optional, TypeVar

from django.conf import settings

logger = logging.getLogger("django_matt.observability.tracing")

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.context import get_current
    from opentelemetry.propagate import set_global_textmap
    from opentelemetry.propagators.composite import CompositePropagator
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    from opentelemetry.trace import SpanKind, Status, StatusCode

    HAS_OPENTELEMETRY = True
except ImportError:
    HAS_OPENTELEMETRY = False
    trace = None
    TracerProvider = None
    BatchSpanProcessor = None
    SimpleSpanProcessor = None
    SpanKind = None
    Status = None
    StatusCode = None

# Try to import specific exporters
try:
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter

    HAS_JAEGER = True
except ImportError:
    HAS_JAEGER = False
    JaegerExporter = None

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    HAS_OTLP = True
except ImportError:
    HAS_OTLP = False
    OTLPSpanExporter = None

try:
    from opentelemetry.exporter.zipkin.json import ZipkinExporter

    HAS_ZIPKIN = True
except ImportError:
    HAS_ZIPKIN = False
    ZipkinExporter = None

# Datadog integration
try:
    from ddtrace import tracer as dd_tracer
    from ddtrace.opentelemetry import TracerProvider as DDTracerProvider

    HAS_DATADOG = True
except ImportError:
    HAS_DATADOG = False
    dd_tracer = None
    DDTracerProvider = None

# New Relic integration
try:
    import newrelic.agent

    HAS_NEWRELIC = True
except ImportError:
    HAS_NEWRELIC = False
    newrelic = None


F = TypeVar("F", bound=Callable[..., Any])


class TracingConfig:
    """Configuration for tracing."""

    def __init__(self):
        self._config = getattr(settings, "DJANGO_MATT_TRACING", {})

    @property
    def enabled(self) -> bool:
        return self._config.get("ENABLED", False)

    @property
    def service_name(self) -> str:
        return self._config.get("SERVICE_NAME", "django-matt-app")

    @property
    def exporter(self) -> str:
        return self._config.get("EXPORTER", "console")

    @property
    def endpoint(self) -> Optional[str]:
        return self._config.get("ENDPOINT")

    @property
    def sample_rate(self) -> float:
        return self._config.get("SAMPLE_RATE", 1.0)

    @property
    def propagators(self) -> list[str]:
        return self._config.get("PROPAGATORS", ["tracecontext", "baggage"])

    @property
    def debug(self) -> bool:
        return self._config.get("DEBUG", False)

    @property
    def headers(self) -> Optional[dict[str, str]]:
        """Custom headers for OTLP exporter (e.g., API keys)."""
        return self._config.get("HEADERS")


tracing_config = TracingConfig()


class NullSpan:
    """A no-op span for when tracing is disabled."""

    def __init__(self, name: str = ""):
        self.name = name
        self._attributes: dict[str, Any] = {}
        self._events: list[tuple[str, dict]] = []

    def set_attribute(self, key: str, value: Any) -> "NullSpan":
        self._attributes[key] = value
        return self

    def set_attributes(self, attributes: dict[str, Any]) -> "NullSpan":
        self._attributes.update(attributes)
        return self

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None) -> "NullSpan":
        self._events.append((name, attributes or {}))
        return self

    def set_status(self, status: Any, description: Optional[str] = None) -> "NullSpan":
        return self

    def record_exception(
        self, exception: Exception, attributes: Optional[dict] = None
    ) -> "NullSpan":
        return self

    def end(self, end_time: Optional[int] = None) -> None:
        pass

    def __enter__(self) -> "NullSpan":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def is_recording(self) -> bool:
        return False

    def get_span_context(self) -> Any:
        return None


class NullTracer:
    """A no-op tracer for when tracing is disabled."""

    def start_span(
        self,
        name: str,
        context: Any = None,
        kind: Any = None,
        attributes: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> NullSpan:
        return NullSpan(name)

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        context: Any = None,
        kind: Any = None,
        attributes: Optional[dict[str, Any]] = None,
        **kwargs,
    ):
        yield NullSpan(name)


class TracingManager:
    """
    Manager for OpenTelemetry tracing.

    Handles tracer setup, span creation, and integration with various exporters.
    """

    def __init__(self):
        self._tracer: Optional[Any] = None
        self._initialized = False

    def setup(
        self,
        service_name: Optional[str] = None,
        exporter: Optional[str] = None,
        endpoint: Optional[str] = None,
        sample_rate: Optional[float] = None,
    ) -> bool:
        """
        Set up OpenTelemetry tracing.

        Args:
            service_name: Name of the service for tracing
            exporter: Exporter type (jaeger, otlp, datadog, newrelic, zipkin, console)
            endpoint: Exporter endpoint URL
            sample_rate: Trace sampling rate (0.0 to 1.0)

        Returns:
            True if setup was successful, False otherwise
        """
        if not tracing_config.enabled and service_name is None:
            logger.debug("Tracing is disabled")
            return False

        if not HAS_OPENTELEMETRY:
            logger.warning(
                "OpenTelemetry is not installed. Install with: uv add opentelemetry-sdk"
            )
            return False

        service_name = service_name or tracing_config.service_name
        exporter = exporter or tracing_config.exporter
        endpoint = endpoint or tracing_config.endpoint

        try:
            # Create resource with service info
            resource = Resource.create({SERVICE_NAME: service_name})

            # Create tracer provider
            provider = TracerProvider(resource=resource)

            # Set up sampling if needed
            if sample_rate is not None or tracing_config.sample_rate < 1.0:
                from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

                rate = sample_rate if sample_rate is not None else tracing_config.sample_rate
                sampler = TraceIdRatioBased(rate)
                provider = TracerProvider(resource=resource, sampler=sampler)

            # Configure exporter
            span_exporter = self._create_exporter(exporter, endpoint)
            if span_exporter:
                processor = BatchSpanProcessor(span_exporter)
                provider.add_span_processor(processor)

            # Set as global provider
            trace.set_tracer_provider(provider)

            # Configure propagators
            self._setup_propagators()

            self._tracer = trace.get_tracer(service_name)
            self._initialized = True

            logger.info(f"Tracing initialized: service={service_name}, exporter={exporter}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize tracing: {e}")
            return False

    def _create_exporter(self, exporter_type: str, endpoint: Optional[str]) -> Any:
        """Create the appropriate span exporter."""
        if exporter_type == "console":
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            return ConsoleSpanExporter()

        if exporter_type == "jaeger":
            if not HAS_JAEGER:
                logger.warning(
                    "Jaeger exporter not installed. Install with: "
                    "uv add opentelemetry-exporter-jaeger"
                )
                return None
            return JaegerExporter(
                agent_host_name=endpoint.split(":")[0] if endpoint else "localhost",
                agent_port=int(endpoint.split(":")[1]) if endpoint and ":" in endpoint else 6831,
            )

        if exporter_type == "otlp":
            if not HAS_OTLP:
                logger.warning(
                    "OTLP exporter not installed. Install with: "
                    "uv add opentelemetry-exporter-otlp"
                )
                return None
            kwargs = {}
            if endpoint:
                kwargs["endpoint"] = endpoint
            if tracing_config.headers:
                kwargs["headers"] = tracing_config.headers
            return OTLPSpanExporter(**kwargs)

        if exporter_type == "zipkin":
            if not HAS_ZIPKIN:
                logger.warning(
                    "Zipkin exporter not installed. Install with: "
                    "uv add opentelemetry-exporter-zipkin-json"
                )
                return None
            return ZipkinExporter(endpoint=endpoint or "http://localhost:9411/api/v2/spans")

        if exporter_type == "datadog":
            if not HAS_DATADOG:
                logger.warning("Datadog not installed. Install with: uv add ddtrace")
                return None
            # Datadog uses its own tracer, return None for OTEL exporter
            return None

        if exporter_type == "newrelic":
            if not HAS_NEWRELIC:
                logger.warning("New Relic not installed. Install with: uv add newrelic")
                return None
            # New Relic has its own agent, OTEL integration is separate
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            nr_endpoint = endpoint or "https://otlp.nr-data.net:4317"
            nr_headers = tracing_config.headers or {}
            return OTLPSpanExporter(endpoint=nr_endpoint, headers=nr_headers)

        logger.warning(f"Unknown exporter type: {exporter_type}")
        return None

    def _setup_propagators(self) -> None:
        """Set up context propagators."""
        if not HAS_OPENTELEMETRY:
            return

        propagators = []
        for prop_name in tracing_config.propagators:
            if prop_name == "tracecontext":
                from opentelemetry.propagators.textmap import TraceContextTextMapPropagator

                propagators.append(TraceContextTextMapPropagator())
            elif prop_name == "baggage":
                from opentelemetry.baggage.propagation import W3CBaggagePropagator

                propagators.append(W3CBaggagePropagator())
            elif prop_name == "b3":
                try:
                    from opentelemetry.propagators.b3 import B3MultiFormat

                    propagators.append(B3MultiFormat())
                except ImportError:
                    logger.warning("B3 propagator not installed")

        if propagators:
            set_global_textmap(CompositePropagator(propagators))

    @property
    def tracer(self) -> Any:
        """Get the tracer instance."""
        if not self._initialized or self._tracer is None:
            return NullTracer()
        return self._tracer

    def get_current_span(self) -> Any:
        """Get the current active span."""
        if not HAS_OPENTELEMETRY or not self._initialized:
            return NullSpan()
        return trace.get_current_span()

    def start_span(
        self,
        name: str,
        kind: Optional[Any] = None,
        attributes: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """
        Start a new span.

        Args:
            name: Span name
            kind: Span kind (client, server, internal, producer, consumer)
            attributes: Span attributes

        Returns:
            The created span
        """
        if not HAS_OPENTELEMETRY or not self._initialized:
            return NullSpan(name)

        span_kind = kind
        if kind is None:
            span_kind = SpanKind.INTERNAL
        elif isinstance(kind, str):
            span_kind = getattr(SpanKind, kind.upper(), SpanKind.INTERNAL)

        return self.tracer.start_span(name, kind=span_kind, attributes=attributes, **kwargs)

    @contextmanager
    def span(
        self,
        name: str,
        kind: Optional[Any] = None,
        attributes: Optional[dict[str, Any]] = None,
    ):
        """
        Context manager for creating a span.

        Args:
            name: Span name
            kind: Span kind
            attributes: Span attributes

        Yields:
            The created span
        """
        if not HAS_OPENTELEMETRY or not self._initialized:
            yield NullSpan(name)
            return

        span_kind = kind
        if kind is None:
            span_kind = SpanKind.INTERNAL
        elif isinstance(kind, str):
            span_kind = getattr(SpanKind, kind.upper(), SpanKind.INTERNAL)

        with self.tracer.start_as_current_span(name, kind=span_kind, attributes=attributes) as span:
            yield span

    def inject_context(self, carrier: dict) -> dict:
        """
        Inject trace context into a carrier (e.g., HTTP headers).

        Args:
            carrier: Dictionary to inject context into

        Returns:
            The carrier with injected context
        """
        if not HAS_OPENTELEMETRY or not self._initialized:
            return carrier

        from opentelemetry.propagate import inject

        inject(carrier)
        return carrier

    def extract_context(self, carrier: dict) -> Any:
        """
        Extract trace context from a carrier.

        Args:
            carrier: Dictionary containing trace context

        Returns:
            The extracted context
        """
        if not HAS_OPENTELEMETRY or not self._initialized:
            return None

        from opentelemetry.propagate import extract

        return extract(carrier)


# Global tracing manager instance
tracing_manager = TracingManager()


def setup_tracing(
    service_name: Optional[str] = None,
    exporter: Optional[str] = None,
    endpoint: Optional[str] = None,
    sample_rate: Optional[float] = None,
) -> bool:
    """
    Set up OpenTelemetry tracing.

    This is the main entry point for configuring tracing in your application.

    Args:
        service_name: Name of the service
        exporter: Exporter type (jaeger, otlp, datadog, newrelic, zipkin, console)
        endpoint: Exporter endpoint URL
        sample_rate: Trace sampling rate (0.0 to 1.0)

    Returns:
        True if setup was successful

    Example:
        # In settings.py or app startup
        from django_matt.observability import setup_tracing

        setup_tracing(
            service_name="myapp",
            exporter="jaeger",
            endpoint="localhost:6831"
        )
    """
    return tracing_manager.setup(service_name, exporter, endpoint, sample_rate)


def get_tracer() -> Any:
    """Get the global tracer instance."""
    return tracing_manager.tracer


def get_current_span() -> Any:
    """Get the current active span."""
    return tracing_manager.get_current_span()


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context."""
    correlation_id_var.set(correlation_id)


def inject_headers(headers: dict) -> dict:
    """Inject trace context into HTTP headers."""
    return tracing_manager.inject_context(headers)


def extract_context(headers: dict) -> Any:
    """Extract trace context from HTTP headers."""
    return tracing_manager.extract_context(headers)


# Datadog-specific helpers
def get_datadog_tracer():
    """Get the Datadog tracer if available."""
    if HAS_DATADOG:
        return dd_tracer
    return None


def datadog_trace(name: str, service: Optional[str] = None, resource: Optional[str] = None):
    """
    Decorator for Datadog tracing.

    Args:
        name: Operation name
        service: Service name (optional)
        resource: Resource name (optional)

    Returns:
        Decorated function
    """

    def decorator(func: F) -> F:
        if not HAS_DATADOG:
            return func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with dd_tracer.trace(name, service=service, resource=resource):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with dd_tracer.trace(name, service=service, resource=resource):
                return await func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


# New Relic-specific helpers
def newrelic_trace(name: str):
    """
    Decorator for New Relic tracing.

    Args:
        name: Transaction name

    Returns:
        Decorated function
    """

    def decorator(func: F) -> F:
        if not HAS_NEWRELIC:
            return func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with newrelic.agent.BackgroundTask(newrelic.agent.application(), name=name):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with newrelic.agent.BackgroundTask(newrelic.agent.application(), name=name):
                return await func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


# Export flags for optional dependencies
__all__ = [
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
]
