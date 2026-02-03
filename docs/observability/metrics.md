# Prometheus Metrics

Django Matt provides Prometheus-compatible metrics collection for monitoring request rates, latencies, error rates, and custom business metrics.

## Overview

Metrics help you understand the health and performance of your application at a glance. They answer questions like:

- How many requests per second is my API handling?
- What's the 95th percentile latency?
- How many errors are occurring?
- How many orders were processed today?

## Configuration

### Basic Configuration

```python
# settings.py

DJANGO_MATT_METRICS = {
    # Enable/disable metrics collection
    "ENABLED": True,

    # Prefix for all metric names
    "PREFIX": "myapp",

    # Default histogram buckets (in seconds)
    "DEFAULT_BUCKETS": [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],

    # Include labels
    "INCLUDE_HOST": True,
    "INCLUDE_METHOD": True,
    "INCLUDE_PATH": True,
    "INCLUDE_STATUS": True,

    # Paths to exclude from metrics
    "EXCLUDE_PATHS": ["/_matt/metrics", "/health", "/ready", "/static/"],
}
```

### Environment-Based Configuration

```python
import os

DJANGO_MATT_METRICS = {
    "ENABLED": os.environ.get("METRICS_ENABLED", "true").lower() == "true",
    "PREFIX": os.environ.get("METRICS_PREFIX", "myapp"),
    "EXCLUDE_PATHS": [
        "/_matt/metrics",
        "/health",
        "/ready",
    ],
}
```

## Built-in Metrics

Django Matt automatically collects these metrics via `MetricsMiddleware`:

### HTTP Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `{prefix}_http_request_duration_seconds` | Histogram | method, endpoint, status | Request latency |
| `{prefix}_http_requests_total` | Counter | method, endpoint, status | Total requests |
| `{prefix}_http_errors_total` | Counter | method, endpoint, error_type | Error count |
| `{prefix}_http_requests_active` | Gauge | method, endpoint | Currently active requests |

### Database Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `{prefix}_db_queries_total` | Counter | operation, table | Total queries |
| `{prefix}_db_query_duration_seconds` | Histogram | operation, table | Query latency |

## Metric Types

### Counter

Counters track cumulative values that only increase:

```python
from django_matt.observability import metrics_manager

# Create a counter
orders_counter = metrics_manager.counter(
    "orders_total",
    "Total orders processed",
    labelnames=["status", "region"]
)

# Increment counter
orders_counter.labels(status="completed", region="us-east").inc()
orders_counter.labels(status="failed", region="us-east").inc()

# Increment by more than 1
orders_counter.labels(status="completed", region="eu-west").inc(5)
```

### Gauge

Gauges track values that can go up or down:

```python
from django_matt.observability import metrics_manager

# Create a gauge
active_users = metrics_manager.gauge(
    "active_users",
    "Number of active users",
    labelnames=["subscription"]
)

# Set value
active_users.labels(subscription="free").set(1500)
active_users.labels(subscription="premium").set(250)

# Increment/decrement
active_users.labels(subscription="free").inc()  # Add 1
active_users.labels(subscription="free").dec()  # Subtract 1
active_users.labels(subscription="premium").inc(10)  # Add 10
```

### Histogram

Histograms track distributions of values:

```python
from django_matt.observability import metrics_manager

# Create a histogram with custom buckets
response_size = metrics_manager.histogram(
    "response_size_bytes",
    "Response size in bytes",
    labelnames=["endpoint"],
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000]
)

# Observe values
response_size.labels(endpoint="/api/users").observe(1234)
response_size.labels(endpoint="/api/orders").observe(5678)

# Time operations
order_latency = metrics_manager.histogram(
    "order_processing_seconds",
    "Order processing time",
    labelnames=["type"]
)

with order_latency.labels(type="standard").time():
    process_order(order)
```

### Summary

Summaries calculate quantiles over a sliding time window:

```python
from django_matt.observability import metrics_manager

# Create a summary
request_latency = metrics_manager.summary(
    "request_latency_seconds",
    "Request latency in seconds",
    labelnames=["handler"]
)

# Observe values
request_latency.labels(handler="list_users").observe(0.05)
```

### Info

Info metrics expose static information:

```python
from django_matt.observability import metrics_manager

# Create an info metric
app_info = metrics_manager.info(
    "app_info",
    "Application information"
)

# Set info (typically done once at startup)
app_info.info({
    "version": "1.2.3",
    "python_version": "3.12",
    "django_version": "5.0",
})
```

## Using Decorators

### @timed

Time function execution:

```python
from django_matt.observability import timed

@timed()
def slow_operation():
    """Creates: function_slow_operation_duration_seconds histogram"""
    time.sleep(1)

@timed("api_call_duration", labels={"service": "payment"})
async def call_payment_api():
    """Creates: api_call_duration histogram with service label"""
    return await payment_service.charge(amount)

@timed(
    "batch_processing",
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0]
)
def process_batch(items):
    """Custom buckets for longer operations"""
    for item in items:
        process(item)
```

### @counted

Count function calls:

```python
from django_matt.observability import counted

@counted()
def process_item(item):
    """Creates: function_process_item_calls_total counter"""
    return transform(item)

@counted("api_requests", labels={"endpoint": "/orders"})
async def list_orders():
    """Creates: api_requests counter with endpoint label"""
    return await Order.objects.all()

@counted("webhook_received", labels={"provider": "stripe"}, count_exceptions=True)
def handle_webhook(payload):
    """Also counts calls that raise exceptions"""
    process_webhook(payload)
```

### @metric

Flexible metric decorator:

```python
from django_matt.observability import metric

@metric("orders_created", labels=["status"])
async def create_order(request, data):
    """Counter incremented on success, extracts 'status' from result"""
    order = await Order.objects.acreate(**data)
    return {"order_id": order.id, "status": "created"}

@metric(
    "payments_processed",
    metric_type="histogram",
    record_duration=True,
    labels=["method", "status"]
)
async def process_payment(method, amount):
    """Histogram that also records duration"""
    result = await payment_gateway.charge(method, amount)
    return {"method": method, "status": result.status}
```

### @observe

Observe values from function results:

```python
from django_matt.observability import observe

@observe("items_processed", lambda r: r["count"])
def process_batch(items):
    """Observes the count from the result"""
    processed = [process(i) for i in items]
    return {"items": processed, "count": len(processed)}

@observe(
    "order_value_dollars",
    lambda r: float(r["total"]),
    labels={"currency": "usd"}
)
async def create_order(data):
    order = await Order.objects.acreate(**data)
    return {"id": order.id, "total": str(order.total)}
```

## Recording Metrics Manually

### Request Metrics

```python
from django_matt.observability import record_request

# Record a request (typically done by middleware)
record_request(
    method="POST",
    endpoint="/api/orders",
    status=201,
    duration=0.125,
)
```

### Database Metrics

```python
from django_matt.observability import record_db_query

# Record a database query
record_db_query(
    operation="SELECT",
    table="orders",
    duration=0.015,
)
```

### Active Requests

```python
from django_matt.observability import increment_active_requests, decrement_active_requests

# Track active requests
increment_active_requests("GET", "/api/users")
try:
    response = process_request()
finally:
    decrement_active_requests("GET", "/api/users")
```

## Custom Business Metrics

Track business-specific metrics:

```python
from django_matt.observability import metrics_manager

# Revenue metrics
revenue = metrics_manager.counter(
    "revenue_total_cents",
    "Total revenue in cents",
    labelnames=["product", "region"]
)

def complete_order(order):
    # Process order...
    revenue.labels(
        product=order.product_category,
        region=order.shipping_region
    ).inc(order.total_cents)

# User metrics
signups = metrics_manager.counter(
    "user_signups_total",
    "Total user signups",
    labelnames=["plan", "source"]
)

def create_user(data, source):
    user = User.objects.create(**data)
    signups.labels(plan=user.plan, source=source).inc()
    return user

# Queue metrics
queue_depth = metrics_manager.gauge(
    "task_queue_depth",
    "Number of tasks in queue",
    labelnames=["queue_name"]
)

def update_queue_metrics():
    for queue in ["default", "high", "low"]:
        depth = get_queue_depth(queue)
        queue_depth.labels(queue_name=queue).set(depth)
```

## Exposing Metrics

### Via URL Pattern

```python
# urls.py
from django_matt.observability import observability_urlpatterns

urlpatterns = [
    path("", include(observability_urlpatterns)),
    # Metrics available at /_matt/metrics
]
```

### Manual View

```python
# urls.py
from django_matt.observability import metrics_view

urlpatterns = [
    path("metrics", metrics_view, name="metrics"),
]
```

### Prometheus Scrape Config

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'django-app'
    scrape_interval: 15s
    static_configs:
      - targets: ['app:8000']
    metrics_path: '/_matt/metrics'
```

## Percentiles

Get percentile values from histograms:

```python
from django_matt.observability import get_percentiles

# Get percentiles for a histogram
percentiles = get_percentiles("http_request_duration_seconds")
print(f"p50: {percentiles['p50']}s")
print(f"p95: {percentiles['p95']}s")
print(f"p99: {percentiles['p99']}s")
```

## Fallback Metrics

When `prometheus_client` is not installed, Django Matt uses fallback metrics that maintain the same API:

```python
from django_matt.observability import HAS_PROMETHEUS

if HAS_PROMETHEUS:
    print("Using prometheus_client")
else:
    print("Using fallback metrics (limited functionality)")
```

## Label Best Practices

### Good Labels

```python
# Clear, bounded cardinality
metrics_manager.counter(
    "http_requests_total",
    labelnames=["method", "endpoint", "status"]
)

# Bounded values
metrics_manager.counter(
    "payments_total",
    labelnames=["provider", "status"]  # provider: stripe, paypal; status: success, failed
)
```

### Avoid High Cardinality

```python
# Bad - user IDs have unlimited cardinality
metrics_manager.counter("requests_by_user", labelnames=["user_id"])  # Don't do this!

# Bad - URLs can have unlimited variations
metrics_manager.histogram("request_duration", labelnames=["full_url"])  # Don't do this!

# Good - normalized endpoint paths
metrics_manager.histogram("request_duration", labelnames=["endpoint"])  # /users/{id}
```

## Multiprocess Mode

For applications using multiple workers (gunicorn, uwsgi):

```python
# settings.py
import os

# Set prometheus multiprocess directory
os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus_multiproc")

# Ensure directory exists
import pathlib
pathlib.Path("/tmp/prometheus_multiproc").mkdir(parents=True, exist_ok=True)
```

```python
# wsgi.py
from prometheus_client import multiprocess, CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest

def metrics_view(request):
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return HttpResponse(
        generate_latest(registry),
        content_type=CONTENT_TYPE_LATEST
    )
```

## Example Dashboard Queries

### Request Rate

```promql
# Requests per second by endpoint
rate(myapp_http_requests_total[5m])

# Request rate by status code
sum by (status) (rate(myapp_http_requests_total[5m]))
```

### Latency

```promql
# Average latency
rate(myapp_http_request_duration_seconds_sum[5m])
/ rate(myapp_http_request_duration_seconds_count[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(myapp_http_request_duration_seconds_bucket[5m]))

# 99th percentile by endpoint
histogram_quantile(0.99,
  sum by (endpoint, le) (rate(myapp_http_request_duration_seconds_bucket[5m]))
)
```

### Error Rate

```promql
# Error rate percentage
100 * sum(rate(myapp_http_errors_total[5m]))
/ sum(rate(myapp_http_requests_total[5m]))

# Error rate by endpoint
sum by (endpoint) (rate(myapp_http_errors_total[5m]))
/ sum by (endpoint) (rate(myapp_http_requests_total[5m]))
```

### Active Requests

```promql
# Current active requests
myapp_http_requests_active

# Active requests by endpoint
sum by (endpoint) (myapp_http_requests_active)
```

## Testing

Disable metrics in tests:

```python
# conftest.py
@pytest.fixture(autouse=True)
def disable_metrics(settings):
    settings.DJANGO_MATT_METRICS = {"ENABLED": False}
```

Or use the fallback metrics for testing:

```python
from django_matt.observability import metrics_manager

def test_order_creation():
    # Clear any existing metrics
    metrics_manager._metrics.clear()

    # Run your code
    create_order(data)

    # Check that metrics were recorded
    counter = metrics_manager._metrics.get("myapp_orders_total")
    assert counter is not None
```
