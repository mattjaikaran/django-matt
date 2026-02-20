# Distributed Tracing

Django Matt provides comprehensive distributed tracing using OpenTelemetry, with support for multiple backends including Jaeger, OTLP, Datadog, New Relic, and Zipkin.

## Overview

Distributed tracing helps you understand how requests flow through your system, identify bottlenecks, and debug issues in production.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Trace: abc123                                      │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │ GET /api/orders/123                                   [250ms]│           │
│  └──────────────────────────────────────────────────────────────┘           │
│       │                                                                      │
│       ├──┌─────────────────────────────┐                                    │
│       │  │ fetch_order            [50ms]│                                    │
│       │  └─────────────────────────────┘                                    │
│       │       │                                                              │
│       │       └──┌───────────────────┐                                      │
│       │          │ DB Query     [20ms]│                                      │
│       │          └───────────────────┘                                      │
│       │                                                                      │
│       ├──┌───────────────────────────────────┐                              │
│       │  │ validate_inventory          [100ms]│                              │
│       │  └───────────────────────────────────┘                              │
│       │       │                                                              │
│       │       └──┌─────────────────────────┐                                │
│       │          │ External API call  [80ms]│                                │
│       │          └─────────────────────────┘                                │
│       │                                                                      │
│       └──┌─────────────────────────────────┐                                │
│          │ serialize_response        [10ms]│                                │
│          └─────────────────────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Configuration

### Basic Configuration

```python
# settings.py

DJANGO_MATT_TRACING = {
    # Enable/disable tracing
    "ENABLED": True,

    # Service name (appears in tracing UI)
    "SERVICE_NAME": "my-api-service",

    # Exporter type: jaeger, otlp, datadog, newrelic, zipkin, console
    "EXPORTER": "otlp",

    # Exporter endpoint
    "ENDPOINT": "http://localhost:4317",

    # Sampling rate (0.0 to 1.0)
    # 1.0 = trace all requests, 0.1 = trace 10% of requests
    "SAMPLE_RATE": 1.0,

    # Context propagators
    "PROPAGATORS": ["tracecontext", "baggage"],

    # Debug mode (verbose logging)
    "DEBUG": False,

    # Custom headers for OTLP (e.g., API keys)
    "HEADERS": {
        "api-key": "your-api-key",
    },
}
```

### Environment-Based Configuration

```python
import os

DJANGO_MATT_TRACING = {
    "ENABLED": os.environ.get("TRACING_ENABLED", "true").lower() == "true",
    "SERVICE_NAME": os.environ.get("SERVICE_NAME", "myapp"),
    "EXPORTER": os.environ.get("TRACING_EXPORTER", "otlp"),
    "ENDPOINT": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
    "SAMPLE_RATE": float(os.environ.get("TRACING_SAMPLE_RATE", "1.0")),
    "HEADERS": {
        "api-key": os.environ.get("OTEL_API_KEY", ""),
    },
}
```

## Exporters

### OTLP (Recommended)

The OpenTelemetry Protocol (OTLP) is the recommended exporter as it works with most observability backends.

```python
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "otlp",
    "ENDPOINT": "http://otel-collector:4317",  # gRPC endpoint
}
```

**Required package:**
```bash
uv add opentelemetry-exporter-otlp
```

### Jaeger

Direct export to Jaeger using the Thrift protocol.

```python
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "jaeger",
    "ENDPOINT": "localhost:6831",  # UDP agent endpoint
}
```

**Required package:**
```bash
uv add opentelemetry-exporter-jaeger
```

### Zipkin

Export traces to Zipkin.

```python
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "zipkin",
    "ENDPOINT": "http://localhost:9411/api/v2/spans",
}
```

**Required package:**
```bash
uv add opentelemetry-exporter-zipkin-json
```

### Datadog

Integration with Datadog APM.

```python
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "datadog",
}
```

**Required package:**
```bash
uv add ddtrace
```

See [Datadog Integration](integrations.md#datadog) for detailed setup.

### New Relic

Integration with New Relic.

```python
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "newrelic",
    "ENDPOINT": "https://otlp.nr-data.net:4317",
    "HEADERS": {
        "api-key": os.environ["NEW_RELIC_LICENSE_KEY"],
    },
}
```

**Required package:**
```bash
uv add newrelic
```

### Console (Development)

Print spans to console for debugging.

```python
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp-dev",
    "EXPORTER": "console",
}
```

## Programmatic Setup

You can also set up tracing programmatically:

```python
from django_matt.observability import setup_tracing

# In your app startup (e.g., apps.py ready())
setup_tracing(
    service_name="myapp",
    exporter="jaeger",
    endpoint="localhost:6831",
    sample_rate=0.5,
)
```

## Creating Spans

### Using the @trace Decorator

The simplest way to create spans:

```python
from django_matt.observability import trace

@trace("fetch_user_data")
async def fetch_user(user_id: int):
    """This function will be wrapped in a span."""
    return await User.objects.aget(pk=user_id)

@trace("process_order", kind="internal", attributes={"order.type": "standard"})
def process_order(order_id: int):
    """Span with custom kind and attributes."""
    order = Order.objects.get(pk=order_id)
    # Process order...
    return order
```

### Using the Context Manager

For more control over spans:

```python
from django_matt.observability import tracing_manager

async def complex_operation(data):
    with tracing_manager.span("validate_data") as span:
        span.set_attribute("data.size", len(data))
        validated = await validate(data)
        span.set_attribute("validation.passed", validated.is_valid)

    with tracing_manager.span("process_data", kind="internal") as span:
        for item in data:
            span.add_event("processing_item", {"item_id": item["id"]})
            await process_item(item)

    return {"status": "completed"}
```

### Manual Span Management

```python
from django_matt.observability import tracing_manager, get_current_span

def my_function():
    # Start a span manually
    span = tracing_manager.start_span(
        "my_operation",
        kind="client",
        attributes={"operation.type": "batch"}
    )

    try:
        # Your code here
        result = do_something()
        span.set_attribute("result.count", len(result))
        return result
    except Exception as e:
        span.record_exception(e)
        span.set_attribute("error", True)
        raise
    finally:
        span.end()

def nested_function():
    # Get the current active span
    current_span = get_current_span()
    current_span.add_event("nested_operation_started")
    # ...
```

## Span Attributes

Add attributes to provide context:

```python
from django_matt.observability import trace, with_span_attribute

@trace("get_order")
@with_span_attribute("order.total", lambda r: r.get("total"))
async def get_order(order_id: int):
    order = await Order.objects.aget(pk=order_id)
    return {
        "id": order.id,
        "total": str(order.total),
        "status": order.status,
    }
```

### Common Attribute Conventions

Follow OpenTelemetry semantic conventions:

```python
# HTTP attributes
span.set_attribute("http.method", "GET")
span.set_attribute("http.url", "https://api.example.com/users")
span.set_attribute("http.status_code", 200)
span.set_attribute("http.response_content_length", 1234)

# Database attributes
span.set_attribute("db.system", "postgresql")
span.set_attribute("db.name", "mydb")
span.set_attribute("db.operation", "SELECT")
span.set_attribute("db.statement", "SELECT * FROM users WHERE id = ?")

# User attributes
span.set_attribute("user.id", "12345")
span.set_attribute("user.email", "user@example.com")

# Custom attributes
span.set_attribute("order.id", "ORD-123")
span.set_attribute("cache.hit", True)
```

## Correlation IDs

Django Matt automatically propagates correlation IDs across requests:

```python
from django_matt.observability import get_correlation_id, set_correlation_id

def my_view(request):
    # Correlation ID is automatically set by TracingMiddleware
    correlation_id = get_correlation_id()

    # Include in external API calls
    response = requests.get(
        "https://api.example.com/data",
        headers={"X-Correlation-ID": correlation_id}
    )

    return JsonResponse({"correlation_id": correlation_id})
```

### Propagating Context to External Services

```python
from django_matt.observability import inject_headers

def call_external_service(data):
    headers = {"Content-Type": "application/json"}

    # Inject trace context into headers
    headers = inject_headers(headers)

    # Now headers contains trace propagation headers:
    # - traceparent
    # - tracestate
    # - X-Correlation-ID

    response = requests.post(
        "https://external-service.com/api",
        json=data,
        headers=headers
    )
    return response.json()
```

### Extracting Context from Incoming Requests

```python
from django_matt.observability import extract_context

def handle_message(headers, body):
    # Extract trace context from message headers
    context = extract_context(headers)

    # Create a span linked to the original trace
    with tracing_manager.span("process_message", context=context) as span:
        process(body)
```

## Sampling

Configure sampling to reduce trace volume in production:

```python
# Sample 10% of requests
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SAMPLE_RATE": 0.1,
    # ...
}
```

### Dynamic Sampling

For more control, implement custom sampling:

```python
from django_matt.observability import setup_tracing

# Sample based on endpoint importance
def should_sample(request):
    # Always sample errors and important endpoints
    if request.path.startswith("/api/payments"):
        return 1.0
    # Sample 10% of other requests
    return 0.1

# Note: Custom sampling requires manual implementation
# This is a conceptual example
```

## Span Events

Add events to track important moments within a span:

```python
from django_matt.observability import tracing_manager

async def process_batch(items):
    with tracing_manager.span("process_batch") as span:
        span.set_attribute("batch.size", len(items))

        for i, item in enumerate(items):
            # Add event for each item
            span.add_event("processing_item", {
                "item.index": i,
                "item.id": item["id"],
            })

            try:
                await process_item(item)
                span.add_event("item_processed", {"item.id": item["id"]})
            except Exception as e:
                span.add_event("item_failed", {
                    "item.id": item["id"],
                    "error": str(e),
                })

        span.add_event("batch_completed")
```

## Error Handling

Exceptions are automatically recorded in spans:

```python
from django_matt.observability import trace

@trace("risky_operation", record_exception=True)  # True by default
def risky_operation():
    try:
        return do_something_dangerous()
    except ValueError as e:
        # Exception will be recorded in the span
        # with type, message, and traceback
        raise
```

### Manual Error Recording

```python
from django_matt.observability import tracing_manager

def my_function():
    with tracing_manager.span("my_operation") as span:
        try:
            result = do_something()
        except Exception as e:
            # Record the exception
            span.record_exception(e)

            # Set error attributes
            span.set_attribute("error", True)
            span.set_attribute("error.type", type(e).__name__)
            span.set_attribute("error.message", str(e))

            # Set span status to error
            from opentelemetry.trace import Status, StatusCode
            span.set_status(Status(StatusCode.ERROR, str(e)))

            raise
```

## Testing with Tracing

Disable tracing in tests or use the console exporter:

```python
# conftest.py
import pytest

@pytest.fixture(autouse=True)
def disable_tracing(settings):
    settings.DJANGO_MATT_TRACING = {"ENABLED": False}
```

Or capture spans for assertions:

```python
from django_matt.observability import tracing_manager, NullSpan

def test_my_function():
    # Tracing is disabled, but functions still work
    result = my_traced_function()
    assert result == expected
```

## Best Practices

### 1. Use Meaningful Span Names

```python
# Good
@trace("orders.create")
@trace("users.fetch_by_email")
@trace("payments.process_stripe")

# Bad
@trace("function1")
@trace("do_stuff")
@trace("handler")
```

### 2. Add Relevant Attributes

```python
@trace("orders.create")
async def create_order(request, data):
    with tracing_manager.span("orders.create") as span:
        span.set_attribute("order.customer_id", data["customer_id"])
        span.set_attribute("order.item_count", len(data["items"]))
        span.set_attribute("order.total", str(data["total"]))
        # ...
```

### 3. Use Span Events for Important Steps

```python
async def checkout(cart):
    with tracing_manager.span("checkout") as span:
        span.add_event("validating_cart")
        await validate(cart)

        span.add_event("processing_payment")
        payment = await process_payment(cart)

        span.add_event("creating_order")
        order = await create_order(cart, payment)

        span.add_event("sending_confirmation")
        await send_email(order)

        return order
```

### 4. Sample Appropriately

- Development: 100% sampling
- Staging: 50-100% sampling
- Production: 1-10% sampling (adjust based on traffic)

### 5. Avoid High-Cardinality Attributes

```python
# Bad - user IDs have high cardinality
span.set_attribute("query", f"SELECT * FROM users WHERE id = {user_id}")

# Good - parameterized
span.set_attribute("db.statement", "SELECT * FROM users WHERE id = ?")
span.set_attribute("db.params", "[user_id]")
```

## Troubleshooting

### Spans Not Appearing

1. Check if tracing is enabled:
```python
from django_matt.observability import tracing_config
print(f"Tracing enabled: {tracing_config.enabled}")
```

2. Verify exporter is installed:
```python
from django_matt.observability import HAS_OPENTELEMETRY, HAS_OTLP
print(f"OpenTelemetry: {HAS_OPENTELEMETRY}, OTLP: {HAS_OTLP}")
```

3. Use console exporter for debugging:
```python
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "EXPORTER": "console",
}
```

### Missing Context Propagation

Ensure middleware is properly ordered:
```python
MIDDLEWARE = [
    # TracingMiddleware should be early in the chain
    'django_matt.observability.TracingMiddleware',
    # Other middleware...
]
```
