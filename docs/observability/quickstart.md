# Quickstart

Get observability set up in your Django Matt application in 5 minutes.

## Step 1: Install Dependencies

```bash
# Minimal (uses fallbacks if dependencies not available)
pip install django-matt

# Recommended: Full observability stack
pip install django-matt[observability]

# Manual installation
pip install opentelemetry-sdk
pip install opentelemetry-exporter-otlp  # For OTLP exporter
pip install prometheus-client             # For Prometheus metrics
pip install orjson                        # Faster JSON logging (optional)
```

## Step 2: Configure Settings

Add to your `settings.py`:

```python
# settings.py

# ============================================================
# OBSERVABILITY CONFIGURATION
# ============================================================

# Tracing - distributed tracing with OpenTelemetry
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "my-django-app",
    "EXPORTER": "otlp",
    "ENDPOINT": "http://localhost:4317",
    "SAMPLE_RATE": 1.0,  # 1.0 = 100% of requests traced
}

# Metrics - Prometheus-compatible metrics
DJANGO_MATT_METRICS = {
    "ENABLED": True,
    "PREFIX": "myapp",
    "EXCLUDE_PATHS": ["/_matt/metrics", "/health", "/ready"],
}

# Logging - structured JSON logging
DJANGO_MATT_LOGGING = {
    "ENABLED": True,
    "FORMAT": "json",  # Use "pretty" for development
    "LEVEL": "INFO",
    "INCLUDE_TIMESTAMP": True,
    "INCLUDE_CORRELATION_ID": True,
    "INCLUDE_REQUEST_ID": True,
    "INCLUDE_USER": True,
    "SENSITIVE_FIELDS": ["password", "token", "secret", "api_key"],
}

# Use the logging config generator for Django's LOGGING setting
from django_matt.observability import get_logging_config
LOGGING = get_logging_config(format="json", level="INFO")
```

## Step 3: Add Middleware

```python
# settings.py

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',

    # Add observability middleware
    'django_matt.observability.TracingMiddleware',
    'django_matt.observability.MetricsMiddleware',
    'django_matt.observability.LoggingMiddleware',

    # Or use the combined middleware (does all three):
    # 'django_matt.observability.ObservabilityMiddleware',
]
```

## Step 4: Add URL Patterns

```python
# urls.py

from django.urls import path, include
from django_matt.observability import observability_urlpatterns

urlpatterns = [
    # Your existing routes...
    path("api/", include("myapp.urls")),

    # Add observability endpoints
    path("", include(observability_urlpatterns)),
]
```

## Step 5: Initialize Tracing (Optional)

If you want to set up tracing programmatically:

```python
# myapp/apps.py

from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = 'myapp'

    def ready(self):
        from django_matt.observability import setup_tracing
        setup_tracing()  # Uses settings from DJANGO_MATT_TRACING
```

## Step 6: Verify Setup

Start your server and check the endpoints:

```bash
# Start Django
python manage.py runserver

# Check health endpoint
curl http://localhost:8000/health
# {"status": "healthy", "timestamp": 1705315800.123}

# Check readiness endpoint
curl http://localhost:8000/ready
# {"ready": true, "checks": {"database": {"ready": true, "message": "Database connected"}}, "timestamp": 1705315800.123}

# Check metrics endpoint
curl http://localhost:8000/_matt/metrics
# # HELP myapp_http_requests_total Total HTTP requests
# # TYPE myapp_http_requests_total counter
# myapp_http_requests_total{method="GET",endpoint="/health",status="200"} 1.0

# Check info endpoint
curl http://localhost:8000/_matt/info
# {"python_version": "3.12.0", "django_version": "5.0", ...}
```

## Development vs Production

### Development Configuration

```python
# settings/development.py

DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp-dev",
    "EXPORTER": "console",  # Print spans to console
    "SAMPLE_RATE": 1.0,
}

DJANGO_MATT_LOGGING = {
    "ENABLED": True,
    "FORMAT": "pretty",  # Pretty-printed JSON
    "LEVEL": "DEBUG",
}

LOGGING = get_logging_config(format="pretty", level="DEBUG")
```

### Production Configuration

```python
# settings/production.py

DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": os.environ.get("SERVICE_NAME", "myapp"),
    "EXPORTER": "otlp",
    "ENDPOINT": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
    "SAMPLE_RATE": 0.1,  # Sample 10% of requests
    "HEADERS": {
        "api-key": os.environ.get("OTEL_API_KEY", ""),
    },
}

DJANGO_MATT_METRICS = {
    "ENABLED": True,
    "PREFIX": "myapp",
    "EXCLUDE_PATHS": ["/_matt/metrics", "/health", "/ready", "/static/"],
}

DJANGO_MATT_LOGGING = {
    "ENABLED": True,
    "FORMAT": "json",
    "LEVEL": "INFO",
    "EXTRA_FIELDS": {
        "environment": "production",
        "version": os.environ.get("APP_VERSION", "unknown"),
    },
}

LOGGING = get_logging_config(format="json", level="INFO")
```

## Quick Usage Examples

### Structured Logging

```python
from django_matt.observability import get_logger

logger = get_logger(__name__)

def create_order(request, order_data):
    logger.info(
        "Creating order",
        customer_id=order_data["customer_id"],
        items=len(order_data["items"]),
        total=order_data["total"],
    )

    try:
        order = Order.objects.create(**order_data)
        logger.info("Order created", order_id=order.id)
        return order
    except Exception as e:
        logger.error("Failed to create order", exc_info=True, error=str(e))
        raise
```

### Using Decorators

```python
from django_matt.observability import trace, metric, timed, counted

@trace("fetch_user")
@timed()
async def fetch_user(user_id: int):
    """Automatically traced and timed."""
    return await User.objects.aget(pk=user_id)

@counted("api_calls", labels={"endpoint": "/orders"})
@metric("orders_created", labels=["status"])
async def create_order(request, data):
    """Automatically counted with labels."""
    order = await Order.objects.acreate(**data)
    return {"order_id": order.id, "status": "created"}
```

### Custom Metrics

```python
from django_matt.observability import metrics_manager

# Create custom metrics
payment_counter = metrics_manager.counter(
    "payments_total",
    "Total payment transactions",
    labelnames=["method", "status"]
)

order_value = metrics_manager.histogram(
    "order_value_dollars",
    "Order value in dollars",
    buckets=[10, 25, 50, 100, 250, 500, 1000]
)

# Use metrics
def process_payment(order, method):
    try:
        result = payment_gateway.charge(order.total, method)
        payment_counter.labels(method=method, status="success").inc()
        order_value.observe(float(order.total))
        return result
    except PaymentError:
        payment_counter.labels(method=method, status="failed").inc()
        raise
```

## Docker Compose for Local Development

Here's a complete local observability stack:

```yaml
# docker-compose.observability.yml
version: "3.8"

services:
  # Your Django app
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DJANGO_MATT_TRACING__ENABLED=true
      - DJANGO_MATT_TRACING__EXPORTER=otlp
      - DJANGO_MATT_TRACING__ENDPOINT=http://otel-collector:4317
    depends_on:
      - otel-collector
      - prometheus
      - jaeger

  # OpenTelemetry Collector
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP

  # Jaeger for tracing
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "14268:14268"  # HTTP collector

  # Prometheus for metrics
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  # Grafana for dashboards
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

Run the stack:

```bash
docker-compose -f docker-compose.observability.yml up -d

# Access UIs:
# - Grafana: http://localhost:3000 (admin/admin)
# - Jaeger: http://localhost:16686
# - Prometheus: http://localhost:9090
# - Your app: http://localhost:8000
```

## Next Steps

Now that you have observability set up:

1. **[Configure Tracing](tracing.md)** - Learn about distributed tracing and exporters
2. **[Set Up Metrics](metrics.md)** - Create custom metrics and dashboards
3. **[Structured Logging](logging.md)** - Best practices for production logging
4. **[Use Decorators](decorators.md)** - Add observability to specific functions
5. **[Integrate with Datadog/New Relic](integrations.md)** - Connect to observability platforms
