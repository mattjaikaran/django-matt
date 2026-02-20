# Observability

The `django_matt.observability` module provides comprehensive observability features for monitoring, debugging, and operating your Django applications in production. Built on industry-standard tools and practices, it implements the three pillars of observability.

## The Three Pillars

```
                    +------------------+
                    |  Observability   |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
    +----v----+        +-----v-----+       +-----v----+
    |  Logs   |        |  Metrics  |       |  Traces  |
    +---------+        +-----------+       +----------+
    | What    |        | How much? |       | Where?   |
    | happened|        | How fast? |       | Why slow?|
    +---------+        +-----------+       +----------+
```

### Logs

Structured JSON logging with automatic correlation IDs, request context, and sensitive data redaction. Logs answer **what happened** in your application.

```python
from django_matt.observability import get_logger

logger = get_logger(__name__)
logger.info("User created", user_id=123, plan="premium")
```

**Output:**
```json
{
  "level": "INFO",
  "logger": "myapp.users",
  "message": "User created",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "correlation_id": "abc123",
  "extra": {
    "user_id": 123,
    "plan": "premium"
  }
}
```

### Metrics

Prometheus-compatible metrics for tracking request rates, latencies, error rates, and custom business metrics. Metrics answer **how much** and **how fast**.

```python
from django_matt.observability import metrics_manager

# Create custom counter
orders_counter = metrics_manager.counter(
    "orders_total",
    "Total orders processed",
    labelnames=["status", "region"]
)
orders_counter.labels(status="completed", region="us-east").inc()
```

**Built-in metrics:**
- `http_request_duration_seconds` - Request latency histogram
- `http_requests_total` - Total request count
- `http_errors_total` - Error count by type
- `http_requests_active` - Currently active requests
- `db_queries_total` - Database query count
- `db_query_duration_seconds` - Database query latency

### Traces

Distributed tracing with OpenTelemetry for tracking requests across services. Traces answer **where** time is spent and **why** things are slow.

```python
from django_matt.observability import trace

@trace("process_order")
async def process_order(order_id: int):
    # This creates a span that shows up in your tracing UI
    order = await fetch_order(order_id)
    await validate_inventory(order)
    await charge_payment(order)
    return order
```

## Quick Start

### Installation

```bash
# Core observability (included with django-matt)
uv add django-matt

# Optional: Full observability stack
uv add django-matt[observability]

# Or install specific components
uv add opentelemetry-sdk opentelemetry-exporter-otlp
uv add prometheus-client
uv add orjson  # Faster JSON logging
```

### Basic Configuration

```python
# settings.py

# Tracing configuration
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "otlp",  # jaeger, otlp, datadog, newrelic, zipkin, console
    "ENDPOINT": "http://localhost:4317",
    "SAMPLE_RATE": 1.0,
}

# Metrics configuration
DJANGO_MATT_METRICS = {
    "ENABLED": True,
    "PREFIX": "myapp",
    "DEFAULT_BUCKETS": [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
}

# Logging configuration
DJANGO_MATT_LOGGING = {
    "ENABLED": True,
    "FORMAT": "json",  # json, pretty, text
    "LEVEL": "INFO",
}

# Or use the logging config generator
from django_matt.observability import get_logging_config
LOGGING = get_logging_config(format="json", level="INFO")

# Add middleware
MIDDLEWARE = [
    # ... other middleware
    'django_matt.observability.TracingMiddleware',
    'django_matt.observability.MetricsMiddleware',
    'django_matt.observability.LoggingMiddleware',
    # Or use combined middleware:
    # 'django_matt.observability.ObservabilityMiddleware',
]
```

### Add URL Patterns

```python
# urls.py
from django_matt.observability import observability_urlpatterns

urlpatterns = [
    # ... your routes
    path("", include(observability_urlpatterns)),
]
```

This adds the following endpoints:

| Endpoint | Description |
|----------|-------------|
| `/_matt/metrics` | Prometheus metrics |
| `/_matt/info` | Application info |
| `/_matt/debug` | Debug info (DEBUG=True only) |
| `/health` | Liveness check |
| `/ready` | Readiness check |

## Architecture Overview

```
                                 +-------------+
                                 |   Request   |
                                 +------+------+
                                        |
                    +-------------------v-------------------+
                    |         TracingMiddleware            |
                    |  - Extract/propagate trace context   |
                    |  - Create request span               |
                    |  - Set correlation ID                |
                    +-------------------+-------------------+
                                        |
                    +-------------------v-------------------+
                    |         MetricsMiddleware            |
                    |  - Record latency histogram          |
                    |  - Count requests/errors             |
                    |  - Track active requests             |
                    +-------------------+-------------------+
                                        |
                    +-------------------v-------------------+
                    |         LoggingMiddleware            |
                    |  - Set request/correlation IDs       |
                    |  - Log request start/end             |
                    |  - Capture user context              |
                    +-------------------+-------------------+
                                        |
                    +-------------------v-------------------+
                    |            Your Views                |
                    |  - @trace decorators                 |
                    |  - @metric decorators                |
                    |  - Structured logging                |
                    +-------------------+-------------------+
                                        |
            +-----------+---------------+---------------+-----------+
            |           |               |               |           |
    +-------v-------+   |       +-------v-------+       |   +-------v-------+
    |    Jaeger     |   |       |   Prometheus  |       |   |   Log Shipper |
    |    Datadog    |   |       |   Grafana     |       |   |   ELK/Loki    |
    |    etc.       |   |       |               |       |   |               |
    +---------------+   |       +---------------+       |   +---------------+
                        |                               |
                +-------v-------+               +-------v-------+
                |    /_matt/    |               |    /health    |
                |    metrics    |               |    /ready     |
                +---------------+               +---------------+
```

## Module Structure

```
django_matt/observability/
    __init__.py         # Public API exports
    tracing.py          # OpenTelemetry tracing
    metrics.py          # Prometheus metrics
    logging.py          # Structured JSON logging
    middleware.py       # Request middleware
    decorators.py       # @trace, @metric, @timed, @counted
    views.py            # Health check and metrics endpoints
```

## Feature Comparison

| Feature | Without django-matt | With django-matt |
|---------|--------------------|--------------------|
| Request tracing | Manual OpenTelemetry setup | Automatic via middleware |
| Metrics collection | Manual Prometheus integration | Automatic + decorators |
| Structured logging | Manual JSON formatting | Built-in formatters |
| Correlation IDs | Manual header parsing | Automatic propagation |
| Health checks | Manual implementation | Built-in endpoints |
| Error tracking | Manual exception handling | Automatic in spans |

## Next Steps

- [Quickstart Guide](quickstart.md) - Get up and running in 5 minutes
- [Tracing](tracing.md) - Deep dive into distributed tracing
- [Metrics](metrics.md) - Custom metrics and Prometheus integration
- [Logging](logging.md) - Structured logging best practices
- [Middleware](middleware.md) - Middleware configuration
- [Decorators](decorators.md) - Function-level observability
- [Endpoints](endpoints.md) - Health checks and metrics endpoints
- [Integrations](integrations.md) - Datadog, Jaeger, Grafana setup
