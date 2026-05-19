# Fast Serialization

Django Matt provides high-performance serialization using orjson as the base JSON library and optional binary formats via MessagePack.

## JSON Library

Django Matt uses **orjson** as a base dependency — it is always installed and always used. There is no fallback to stdlib `json` or `ujson`.

| Library | Speed | Status |
|---------|-------|--------|
| **orjson** | Fastest (3-10x vs stdlib) | Always available — base dependency |
| **msgpack** | Binary, ~30% smaller | Optional: `uv add msgpack` |
| **stdlib json** | Baseline | Not used by django-matt |

orjson natively handles `datetime`, `UUID`, `Decimal`, and numpy arrays without custom encoders.

## FastJSONRenderer

The `FastJSONRenderer` class automatically uses the best available JSON library.

### Basic Usage

```python
from django_matt.utils.performance import FastJSONRenderer

# Serialize to bytes
data = {"name": "John", "age": 30}
json_bytes = FastJSONRenderer.dumps(data)

# Deserialize
parsed = FastJSONRenderer.loads(json_bytes)
```

### Library Name

```python
renderer = FastJSONRenderer()
print(f"Using: {renderer.library_name}")  # always "orjson"
```

### orjson Options

When using orjson, you can pass additional options:

```python
import orjson

# Pretty print
json_bytes = FastJSONRenderer.dumps(
    data,
    orjson_options=orjson.OPT_INDENT_2
)

# Sort keys
json_bytes = FastJSONRenderer.dumps(
    data,
    orjson_options=orjson.OPT_SORT_KEYS
)

# Handle numpy arrays
json_bytes = FastJSONRenderer.dumps(
    data,
    orjson_options=orjson.OPT_SERIALIZE_NUMPY
)

# Combine options
json_bytes = FastJSONRenderer.dumps(
    data,
    orjson_options=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
)
```

## FastJsonResponse

HTTP response class using fast JSON serialization.

### Basic Usage

```python
from django_matt.utils.performance import FastJsonResponse

@api.get("/users")
async def list_users(request):
    users = [u async for u in User.objects.all()]
    return FastJsonResponse({"users": users})
```

### With Status Code

```python
@api.post("/users")
async def create_user(request, data: UserCreate):
    user = await User.objects.create(**data.model_dump())
    return FastJsonResponse({"user": user}, status=201)
```

### With Custom Headers

```python
@api.get("/data")
async def get_data(request):
    return FastJsonResponse(
        {"data": "value"},
        headers={"X-Custom-Header": "value"}
    )
```

## MessagePack Serialization

MessagePack is a binary serialization format that's more compact than JSON.

### When to Use MessagePack

- Internal service-to-service communication
- Mobile apps with limited bandwidth
- WebSocket messages
- Storing serialized data

### Installation

```bash
uv add msgpack
```

### Basic Usage

```python
from django_matt.utils.performance import MessagePackRenderer

# Serialize
data = {"name": "John", "items": [1, 2, 3]}
packed = MessagePackRenderer.dumps(data)

# Deserialize
unpacked = MessagePackRenderer.loads(packed)
```

### MessagePackResponse

```python
from django_matt.utils.performance import MessagePackResponse

@api.get("/binary-data")
async def get_binary_data(request):
    data = {"values": list(range(1000))}
    return MessagePackResponse(data)
```

Clients must send `Accept: application/x-msgpack` header.

### Size Comparison

```python
import json
from django_matt.utils.performance import FastJSONRenderer, MessagePackRenderer

data = {
    "users": [
        {"id": i, "name": f"User {i}", "active": True, "score": 99.5}
        for i in range(100)
    ]
}

json_size = len(FastJSONRenderer.dumps(data))
msgpack_size = len(MessagePackRenderer.dumps(data))

print(f"JSON: {json_size} bytes")
print(f"MessagePack: {msgpack_size} bytes")
print(f"Reduction: {(1 - msgpack_size/json_size) * 100:.1f}%")

# Typical output:
# JSON: 5432 bytes
# MessagePack: 3876 bytes
# Reduction: 28.6%
```

## Streaming Responses

For large datasets, stream JSON instead of loading everything into memory.

### StreamingJsonResponse

```python
from django_matt.utils.performance import StreamingJsonResponse, stream_json_list

@api.get("/large-export")
async def export_data(request):
    # Use iterator to avoid loading all into memory
    items = Product.objects.all().iterator()

    # Stream as JSON array
    return StreamingJsonResponse(
        stream_json_list(items, chunk_size=100)
    )
```

### How Streaming Works

```python
from django_matt.utils.performance import stream_json_list

items = [{"id": 1}, {"id": 2}, {"id": 3}]

# Yields chunks:
# "[" -> first
# '{"id":1}' -> item
# ',{"id":2}' -> item with comma
# ',{"id":3}' -> item with comma
# "]" -> last

for chunk in stream_json_list(items):
    print(repr(chunk))
```

### Custom Streaming

```python
def stream_custom_json(items):
    """Stream items with custom formatting."""
    yield '{"items": ['

    first = True
    for item in items:
        if not first:
            yield ","
        first = False

        # Serialize each item
        yield FastJSONRenderer.dumps(item).decode("utf-8")

    yield '], "total": ' + str(count) + '}'

@api.get("/export")
async def export(request):
    items = get_items_iterator()
    return StreamingJsonResponse(stream_custom_json(items))
```

## Performance Benchmarks

Typical performance on modern hardware (Apple M1, Python 3.12):

### Small Object (4 fields)

| Library | Serialize | Deserialize | Ops/s |
|---------|-----------|-------------|-------|
| orjson | 0.002ms | 0.002ms | 500K |
| ujson | 0.004ms | 0.004ms | 250K |
| json | 0.015ms | 0.012ms | 67K |

### Medium Object (nested, ~1KB)

| Library | Serialize | Deserialize | Ops/s |
|---------|-----------|-------------|-------|
| orjson | 0.008ms | 0.010ms | 125K |
| ujson | 0.020ms | 0.025ms | 50K |
| json | 0.045ms | 0.040ms | 22K |

### Large Object (100 nested items, ~50KB)

| Library | Serialize | Deserialize | Ops/s |
|---------|-----------|-------------|-------|
| orjson | 0.250ms | 0.300ms | 4K |
| ujson | 0.600ms | 0.700ms | 1.7K |
| json | 1.200ms | 1.000ms | 0.8K |

### Run Your Own Benchmarks

```bash
python manage.py benchmark --scenario json
```

## Best Practices

### 1. Always Install orjson in Production

```bash
# requirements.txt
orjson>=3.9.0
```

### 2. Use FastJsonResponse for API Responses

```python
# Instead of JsonResponse
from django.http import JsonResponse

# Use FastJsonResponse
from django_matt.utils.performance import FastJsonResponse
```

### 3. Stream Large Responses

```python
# Bad: Load 100K items into memory
@api.get("/export")
async def export(request):
    items = [i async for i in Item.objects.all()]  # 100K items
    return FastJsonResponse({"items": items})

# Good: Stream items
@api.get("/export")
async def export(request):
    items = Item.objects.all().iterator()
    return StreamingJsonResponse(stream_json_list(items))
```

### 4. Consider MessagePack for Internal APIs

```python
# Internal microservice communication
from django_matt.utils.performance import MessagePackResponse

@api.get("/internal/data")
async def internal_data(request):
    # 30% smaller, 2x faster parsing
    return MessagePackResponse(large_data)
```

### 5. Profile Before Optimizing

```python
from django_matt.utils.performance import benchmark

@api.get("/data")
@benchmark.measure("data_endpoint")
async def get_data(request):
    data = await expensive_query()
    return FastJsonResponse(data)

# Check if serialization is the bottleneck
report = benchmark.get_report()
```

## Handling Special Types

### Datetime Objects

orjson handles datetime natively:

```python
from datetime import datetime

data = {"created_at": datetime.now()}

# orjson: Works automatically
FastJSONRenderer.dumps(data)  # '{"created_at":"2024-01-15T10:30:00"}'

# stdlib json: Requires encoder
import json
json.dumps(data, default=str)  # Fallback
```

### UUID Objects

```python
from uuid import uuid4

data = {"id": uuid4()}

# orjson: Works automatically
FastJSONRenderer.dumps(data)  # '{"id":"550e8400-e29b-41d4-a716-446655440000"}'
```

### Decimal Objects

```python
from decimal import Decimal

data = {"price": Decimal("99.99")}

# orjson: Works automatically
FastJSONRenderer.dumps(data)  # '{"price":99.99}'
```

### NumPy Arrays

```python
import numpy as np
import orjson

data = {"values": np.array([1, 2, 3])}

# Use OPT_SERIALIZE_NUMPY
FastJSONRenderer.dumps(
    data,
    orjson_options=orjson.OPT_SERIALIZE_NUMPY
)
```

### Pydantic Models

```python
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str

user = User(id=1, name="John")

# Convert to dict first
FastJSONRenderer.dumps(user.model_dump())

# Or use model_dump_json() for pydantic's native serialization
json_str = user.model_dump_json()
```

## Troubleshooting

### "MessagePack is not installed"

```bash
uv add msgpack
```

### High Memory Usage with Large Responses

Use streaming:

```python
# Stream instead of loading all into memory
return StreamingJsonResponse(stream_json_list(items))
```

### Serialization Errors

Check for unsupported types:

```python
# Common issues:
# - Custom objects without __dict__
# - Generators (must convert to list)
# - Complex numbers

# Solution: Convert to serializable types
data = {
    "custom_obj": custom_obj.__dict__,
    "generator": list(generator),
}
```

### Checking Optional Library Availability

```python
from django_matt.utils.performance import HAS_MSGPACK

# orjson is always available (base dependency) — no flag needed
# msgpack is optional
print(f"msgpack: {HAS_MSGPACK}")
```
