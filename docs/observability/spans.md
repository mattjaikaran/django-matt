# Spans

The `django_matt.observability.spans` module provides a lightweight, dependency-free span system for tracing operations. Spans form a tree that tracks timing, tags, errors, and parent-child relationships using Python's `contextvars`.

## Span

A `Span` is a dataclass that records a named operation:

```python
from django_matt.observability.spans import Span

s = Span(name="my_operation")
s.set_tag("user_id", 42)
s.set_tags({"method": "GET", "path": "/api/users"})
s.finish()

print(s.duration_ms)  # elapsed time in milliseconds
print(s.to_dict())    # full serializable representation
```

### Properties and Methods

| Method | Description |
|--------|-------------|
| `set_tag(key, value)` | Set a single tag (returns self for chaining) |
| `set_tags(dict)` | Set multiple tags at once |
| `set_error(exc)` | Mark the span as errored, records exception type and message |
| `finish()` | Record the end time and set status to OK if unset |
| `duration_ms` | Elapsed time in milliseconds (live if not finished) |
| `to_dict()` | Serialize to a dict (includes children and error info) |

### SpanStatus

```python
from django_matt.observability.spans import SpanStatus

SpanStatus.OK      # Operation succeeded
SpanStatus.ERROR   # Operation failed
SpanStatus.UNSET   # Not yet determined (default)
```

## span() Context Manager

The `span()` context manager creates a span, sets it as the current span in the context, and automatically handles parent-child nesting:

```python
from django_matt.observability.spans import span

def process_order(order_id: int):
    with span("process_order", tags={"order_id": order_id}) as s:
        validate(order_id)
        charge(order_id)
        s.set_tag("result", "success")
        # span finishes automatically on exit
```

### Nested Spans

Spans nest automatically. The inner span becomes a child of the outer span:

```python
with span("request") as parent:
    with span("db_query") as child:
        # child is automatically added to parent.children
        run_query()
    with span("serialize") as child2:
        serialize_result()

# parent.children == [child, child2]
```

### Error Handling

Exceptions are recorded on the span and re-raised:

```python
with span("risky") as s:
    raise ValueError("something broke")
# s.status == SpanStatus.ERROR
# s.error == ValueError("something broke")
# s.tags == {"error": True, "error.type": "ValueError", "error.message": "something broke"}
```

## aspan() Async Context Manager

The async equivalent for use in `async` functions:

```python
from django_matt.observability.spans import aspan

async def fetch_data():
    async with aspan("fetch_data") as s:
        result = await external_api.get("/data")
        s.set_tag("response_size", len(result))
        return result
```

Nesting works identically to `span()` since both use the same `ContextVar`.

## @traced Decorator

The `@traced` decorator wraps a function (sync or async) in a span:

```python
from django_matt.observability.spans import traced

@traced("fetch_user")
async def fetch_user(user_id: int):
    return await User.objects.aget(pk=user_id)

@traced()  # uses func.__qualname__ as span name
def compute_total(items):
    return sum(i.price for i in items)

@traced("send_email", tags={"service": "ses"})
async def send_email(to: str, subject: str):
    await ses_client.send(to=to, subject=subject)
```

The decorator auto-detects sync vs async and wraps accordingly.

## Span Listeners

Register callbacks that fire when a root span (one with no parent) finishes:

```python
from django_matt.observability.spans import add_span_listener, remove_span_listener, Span

def my_listener(s: Span):
    if s.duration_ms > 500:
        print(f"Slow operation: {s.name} took {s.duration_ms:.1f}ms")

add_span_listener(my_listener)

# Later, to remove:
remove_span_listener(my_listener)
```

Listeners only fire for root spans. The full span tree (with all children) is passed to the listener. This is how exporters receive span data.

## get_current_span()

Access the currently active span from anywhere in the call stack:

```python
from django_matt.observability.spans import get_current_span

def add_context():
    current = get_current_span()
    if current:
        current.set_tag("extra_context", "value")
```

Returns `None` if no span is active.

## Integration with Exporters

Spans flow to exporters through the listener mechanism:

```python
from django_matt.observability.spans import add_span_listener
from django_matt.observability.exporters import ConsoleExporter

exporter = ConsoleExporter()
add_span_listener(exporter.export)

# Now every root span is printed to stderr
with span("my_operation"):
    do_work()
```

The `setup_observability()` function handles this wiring automatically.
