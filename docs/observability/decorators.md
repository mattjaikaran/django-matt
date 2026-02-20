# Observability Decorators

Django Matt provides decorators for adding tracing and metrics to individual functions and views.

## Available Decorators

| Decorator | Purpose |
|-----------|---------|
| `@trace` | Create a trace span for the function |
| `@metric` | Record metrics for the function |
| `@timed` | Time function execution (histogram) |
| `@counted` | Count function calls (counter) |
| `@observe` | Observe values from function results |
| `@with_span_attribute` | Add attributes to current span |

## @trace

Creates a trace span for the decorated function.

### Basic Usage

```python
from django_matt.observability import trace

@trace("fetch_user")
async def fetch_user(user_id: int):
    """Automatically traced with span name 'fetch_user'"""
    return await User.objects.aget(pk=user_id)

@trace()  # Uses function name as span name
def process_data(data):
    """Automatically traced with span name 'process_data'"""
    return transform(data)
```

### With Attributes

```python
from django_matt.observability import trace

@trace(
    "process_order",
    kind="internal",  # client, server, internal, producer, consumer
    attributes={
        "order.type": "standard",
        "service.name": "order-processor",
    }
)
def process_order(order_id: int):
    order = Order.objects.get(pk=order_id)
    return process(order)
```

### Span Kinds

| Kind | Use Case |
|------|----------|
| `client` | Outgoing requests (HTTP, gRPC, DB) |
| `server` | Incoming requests |
| `internal` | Internal operations (default) |
| `producer` | Message queue publishing |
| `consumer` | Message queue consuming |

### Exception Recording

By default, exceptions are recorded in the span:

```python
@trace("risky_operation", record_exception=True)  # True by default
def risky_operation():
    # If this raises, the exception is recorded in the span
    # with type, message, and traceback
    return do_something_dangerous()

@trace("another_operation", record_exception=False)
def another_operation():
    # Exceptions won't be recorded in the span
    return do_something()
```

### Async Support

All decorators support both sync and async functions:

```python
@trace("sync_function")
def sync_function():
    return "sync result"

@trace("async_function")
async def async_function():
    await asyncio.sleep(0.1)
    return "async result"
```

## @metric

Records metrics for the decorated function.

### Counter Metric

```python
from django_matt.observability import metric

@metric("orders_created", labels=["status"])
async def create_order(request, data):
    """Counter incremented on success, extracts 'status' from result"""
    order = await Order.objects.acreate(**data)
    return {"order_id": order.id, "status": "created"}
```

### Histogram Metric

```python
@metric(
    "payment_processing",
    metric_type="histogram",
    labels=["method"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
)
async def process_payment(method, amount):
    """Records execution time in histogram"""
    result = await payment_gateway.charge(method, amount)
    return {"method": method, "status": result.status}
```

### With Duration Recording

```python
@metric(
    "api_calls",
    metric_type="counter",
    record_duration=True,  # Also creates histogram
    labels=["endpoint"],
)
def call_external_api(endpoint):
    """Creates counter AND duration histogram"""
    return requests.get(endpoint).json()
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | Required | Metric name |
| `metric_type` | str | "counter" | counter, histogram, gauge |
| `labels` | list[str] | None | Label names to extract |
| `description` | str | "" | Metric description |
| `buckets` | list[float] | None | Histogram buckets |
| `increment_on_success` | bool | True | Record on success |
| `increment_on_error` | bool | True | Record on exception |
| `record_duration` | bool | False | Also record duration |

### Label Extraction

Labels are extracted from the function result (if dict) or kwargs:

```python
@metric("user_actions", labels=["action", "result"])
def user_action(user_id, action):
    # Labels extracted from result dict
    success = perform_action(user_id, action)
    return {
        "action": action,
        "result": "success" if success else "failure"
    }
```

## @timed

Times function execution and records as a histogram.

### Basic Usage

```python
from django_matt.observability import timed

@timed()
def slow_operation():
    """Creates: function_slow_operation_duration_seconds histogram"""
    time.sleep(1)
    return "done"

@timed("custom_metric_name")
async def async_operation():
    """Creates: custom_metric_name histogram"""
    await asyncio.sleep(0.5)
    return "done"
```

### With Labels

```python
@timed(
    "api_call_duration",
    labels={"service": "payment", "environment": "production"}
)
def call_payment_service():
    return payment_api.charge(amount)
```

### Custom Buckets

```python
@timed(
    "batch_processing",
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)
def process_large_batch(items):
    """Custom buckets for longer operations"""
    for item in items:
        process(item)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | None | Metric name (default: function_{name}_duration_seconds) |
| `labels` | dict | None | Static labels |
| `buckets` | list[float] | None | Histogram buckets |

## @counted

Counts function calls.

### Basic Usage

```python
from django_matt.observability import counted

@counted()
def process_item(item):
    """Creates: function_process_item_calls_total counter"""
    return transform(item)

@counted("custom_counter_name")
async def handle_request(request):
    """Creates: custom_counter_name counter"""
    return process(request)
```

### With Labels

```python
@counted(
    "api_requests",
    labels={"endpoint": "/orders", "version": "v2"}
)
def handle_orders_endpoint():
    return list_orders()
```

### Exception Handling

```python
@counted("operations", count_exceptions=True)
def risky_operation():
    """Counts calls even when exceptions are raised"""
    return do_something_risky()

@counted("safe_operations", count_exceptions=False)
def safe_operation():
    """Only counts successful calls"""
    return do_something_safe()
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | None | Metric name (default: function_{name}_calls_total) |
| `labels` | dict | None | Static labels |
| `count_exceptions` | bool | True | Count calls that raise |

## @observe

Observes values from function results.

### Basic Usage

```python
from django_matt.observability import observe

@observe("items_processed", lambda r: r["count"])
def process_batch(items):
    """Observes the count from the result"""
    processed = [process(i) for i in items]
    return {"items": processed, "count": len(processed)}
```

### Complex Value Extraction

```python
@observe(
    "order_value_dollars",
    lambda r: float(r.get("total", 0)),
    labels={"currency": "usd"},
    description="Order value in US dollars"
)
async def create_order(data):
    order = await Order.objects.acreate(**data)
    return {
        "id": order.id,
        "total": str(order.total),
        "currency": "usd"
    }
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | Required | Metric name |
| `value_extractor` | Callable | Required | Function to extract value from result |
| `labels` | dict | None | Static labels |
| `description` | str | "" | Metric description |

## @with_span_attribute

Adds an attribute to the current span from function result.

### Basic Usage

```python
from django_matt.observability import trace, with_span_attribute

@trace("get_user")
@with_span_attribute("user.email", lambda r: r.get("email"))
async def get_user(user_id):
    """Adds user.email attribute to the span"""
    user = await User.objects.aget(pk=user_id)
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
    }
```

### Multiple Attributes

```python
@trace("process_order")
@with_span_attribute("order.id", lambda r: r.get("order_id"))
@with_span_attribute("order.total", lambda r: r.get("total"))
@with_span_attribute("order.item_count", lambda r: r.get("item_count"))
async def process_order(data):
    order = await create_order(data)
    return {
        "order_id": order.id,
        "total": str(order.total),
        "item_count": len(order.items),
    }
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key` | str | Required | Attribute key |
| `value_extractor` | Callable | Required | Function to extract value from result |

## Combining Decorators

Decorators can be combined for comprehensive observability:

```python
from django_matt.observability import trace, metric, timed, counted, with_span_attribute

@trace("create_order", kind="internal")
@timed("order_creation_duration")
@counted("orders_created")
@metric("orders", labels=["status", "region"])
@with_span_attribute("order.customer_id", lambda r: r.get("customer_id"))
async def create_order(request, data):
    """
    This function:
    - Creates a trace span 'create_order'
    - Records duration histogram 'order_creation_duration'
    - Increments counter 'orders_created'
    - Records metric with status/region labels
    - Adds customer_id to span
    """
    order = await Order.objects.acreate(
        customer_id=data["customer_id"],
        region=data["region"],
        **data
    )
    return {
        "order_id": order.id,
        "customer_id": order.customer_id,
        "status": "created",
        "region": order.region,
    }
```

### Decorator Order

When combining decorators, order matters:

```python
# Recommended order (outer to inner):
@trace("operation")           # 1. Create span first
@with_span_attribute(...)     # 2. Add attributes to span
@timed("duration")            # 3. Record timing
@counted("calls")             # 4. Count calls
@metric("custom", ...)        # 5. Custom metrics
def my_function():
    pass
```

## Class Methods

Decorators work with class methods:

```python
class OrderService:
    @trace("fetch_order")
    async def get_order(self, order_id: int):
        return await Order.objects.aget(pk=order_id)

    @timed()
    @counted()
    async def create_order(self, data: dict):
        return await Order.objects.acreate(**data)

    @metric("order_updates", labels=["status"])
    async def update_order(self, order_id: int, data: dict):
        order = await self.get_order(order_id)
        for key, value in data.items():
            setattr(order, key, value)
        await order.asave()
        return {"status": "updated", "order_id": order_id}
```

## Django Views

Use decorators with Django views:

```python
from django.http import JsonResponse
from django_matt.observability import trace, timed

@trace("list_users_view")
@timed("users_list_duration")
def list_users(request):
    users = User.objects.all()
    return JsonResponse({"users": list(users.values())})

@trace("create_user_view")
@timed()
@counted("user_creates")
def create_user(request):
    data = json.loads(request.body)
    user = User.objects.create(**data)
    return JsonResponse({"id": user.id})
```

## API Controllers

With Django Matt controllers:

```python
from django_matt import MattAPI
from django_matt.core import APIController
from django_matt.observability import trace, metric, timed

api = MattAPI()

@api.controller("/orders", tags=["Orders"])
class OrderController(APIController):

    @api.get("/")
    @trace("list_orders")
    @timed("orders_list_duration")
    async def list_orders(self, request):
        return [o async for o in Order.objects.all()]

    @api.post("/")
    @trace("create_order")
    @metric("orders_created", labels=["status"])
    async def create_order(self, request, data: OrderCreateSchema):
        order = await Order.objects.acreate(**data.model_dump())
        return {"id": order.id, "status": "created"}
```

## Error Handling

Decorators handle errors gracefully:

```python
@trace("risky_operation")
@timed("risky_duration")
@counted("risky_calls", count_exceptions=True)
def risky_operation():
    try:
        return do_something_risky()
    except Exception as e:
        # Exception is recorded in trace span
        # Duration is still recorded
        # Call is still counted (if count_exceptions=True)
        raise
```

## Testing

Test decorated functions:

```python
import pytest
from unittest.mock import patch

def test_traced_function():
    # Function works normally even when tracing is disabled
    result = my_traced_function(data)
    assert result == expected

def test_with_mock_metrics():
    from django_matt.observability import metrics_manager

    # Clear metrics before test
    metrics_manager._metrics.clear()

    # Call decorated function
    result = my_metriced_function()

    # Verify metrics were recorded
    metric = metrics_manager._metrics.get("myapp_my_metric")
    assert metric is not None
```

Disable observability in tests:

```python
# conftest.py
@pytest.fixture(autouse=True)
def disable_observability(settings):
    settings.DJANGO_MATT_TRACING = {"ENABLED": False}
    settings.DJANGO_MATT_METRICS = {"ENABLED": False}
```

## Performance Considerations

### Minimal Overhead

Decorators are designed to have minimal overhead:

```python
# Overhead when tracing disabled: ~0.01ms
# Overhead when tracing enabled: ~0.1-0.5ms (depends on exporter)
```

### Conditional Decoration

For hot paths, consider conditional decoration:

```python
import os

# Only trace in non-production or sampled
if os.environ.get("ENABLE_TRACING", "false") == "true":
    @trace("hot_path")
    def hot_path_function():
        pass
else:
    def hot_path_function():
        pass
```

Or use sampling:

```python
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SAMPLE_RATE": 0.1,  # Only trace 10% of requests
}
```
