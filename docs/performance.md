# Performance Optimization in Django Matt

This document provides detailed information about the performance optimization features available in Django Matt.

## Table of Contents

1. [JSON Serialization](#json-serialization)
2. [MessagePack Serialization](#messagepack-serialization)
3. [Streaming Responses](#streaming-responses)
4. [Caching Mechanisms](#caching-mechanisms)
5. [Performance Benchmarking](#performance-benchmarking)
6. [Configuration](#configuration)
7. [Best Practices](#best-practices)

## JSON Serialization

Django Matt provides optimized JSON serialization using the fastest available JSON libraries.

### FastJSONRenderer

The `FastJSONRenderer` class automatically selects the fastest available JSON library in the following order:

1. `orjson` - The fastest Python JSON library, written in Rust
2. `ujson` - UltraJSON, a fast JSON encoder and decoder
3. `json` - Python's built-in JSON library (fallback)

```python
from django_matt.utils.performance import FastJSONRenderer

# Create a renderer instance
renderer = FastJSONRenderer()

# Serialize data
json_string = renderer.dumps({"key": "value"})

# Deserialize data
data = renderer.loads(json_string)
```

### FastJsonResponse

`FastJsonResponse` is a drop-in replacement for Django's `JsonResponse` that uses the `FastJSONRenderer` for improved performance.

```python
from django_matt import FastJsonResponse

def my_view(request):
    return FastJsonResponse({
        "data": my_data,
        "count": len(my_data)
    })
```

## MessagePack Serialization

MessagePack is a binary serialization format that is faster and more compact than JSON.

### MessagePackRenderer

The `MessagePackRenderer` class provides methods for serializing and deserializing data using MessagePack.

```python
from django_matt.utils.performance import MessagePackRenderer

# Create a renderer instance
renderer = MessagePackRenderer()

# Serialize data
msgpack_data = renderer.dumps({"key": "value"})

# Deserialize data
data = renderer.loads(msgpack_data)
```

### MessagePackResponse

`MessagePackResponse` is an HTTP response class that renders content as MessagePack.

```python
from django_matt import MessagePackResponse

def my_view(request):
    return MessagePackResponse({
        "data": my_data,
        "count": len(my_data)
    })
```

## Streaming Responses

For large datasets, Django Matt provides streaming response capabilities to avoid loading everything into memory.

### StreamingJsonResponse

`StreamingJsonResponse` allows you to stream large JSON datasets as they are generated.

```python
from django_matt import StreamingJsonResponse, stream_json_list

def my_view(request):
    def items_generator():
        for item in large_dataset:
            yield item
    
    return StreamingJsonResponse(
        streaming_content=stream_json_list(items_generator())
    )
```

### stream_json_list

The `stream_json_list` function is a helper that yields JSON chunks from an iterator, properly formatting them as a JSON array.

```python
from django_matt import stream_json_list

def items_generator():
    for i in range(1000000):
        yield {"id": i, "name": f"Item {i}"}

# In a view
response = StreamingJsonResponse(
    streaming_content=stream_json_list(items_generator())
)
```

## Caching Mechanisms

Django Matt includes a powerful caching system for API responses.

### CacheManager

The `CacheManager` class provides methods for caching API responses and function results.

```python
from django_matt import cache_manager

# Cache a value
cache_manager.set("my_key", my_value, timeout=60)

# Get a cached value
value = cache_manager.get("my_key")

# Delete a cached value
cache_manager.delete("my_key")

# Clear all cache
cache_manager.clear()
```

### cache_response Decorator

The `cache_response` decorator caches the entire HTTP response of a view function.

```python
from django_matt import cache_manager

@cache_manager.cache_response(timeout=60)  # Cache for 60 seconds
def my_view(request):
    # Expensive operation
    return FastJsonResponse({"data": expensive_operation()})
```

### cache_result Decorator

The `cache_result` decorator caches the result of a function.

```python
from django_matt import cache_manager

@cache_manager.cache_result(timeout=60)  # Cache for 60 seconds
def expensive_operation(param1, param2):
    # Expensive operation
    return result
```

## Performance Benchmarking

Django Matt provides tools to measure and optimize API performance.

### APIBenchmark

The `APIBenchmark` class measures the performance of API endpoints.

```python
from django_matt.utils.performance import APIBenchmark

# Create a benchmark instance
benchmark = APIBenchmark()

# Measure execution time
with benchmark.measure("my_operation"):
    # Code to benchmark
    result = expensive_operation()

# Get benchmark results
report = benchmark.get_report()
```

### benchmark Decorator

The `benchmark` decorator measures the execution time of a function.

```python
from django_matt import benchmark

@benchmark.measure('my_operation')
def expensive_operation():
    # Expensive operation
    return result

# Get benchmark results
benchmark_results = benchmark.get_report()
```

### BenchmarkMiddleware

The `BenchmarkMiddleware` automatically benchmarks all requests and adds timing information to the response headers.

```python
# In settings.py
MIDDLEWARE = [
    # ...
    'django_matt.utils.performance.BenchmarkMiddleware',
    # ...
]
```

## Configuration

Django Matt's performance features can be configured in your Django settings.

```python
# In settings.py

# Benchmarking
DJANGO_MATT_BENCHMARK_ENABLED = True  # Enable benchmarking
DJANGO_MATT_BENCHMARK_HEADER = 'X-Django-Matt-Timing'  # Header name for timing information

# Caching
DJANGO_MATT_CACHE_ENABLED = True  # Enable caching
DJANGO_MATT_CACHE_TIMEOUT = 60  # Default cache timeout in seconds
DJANGO_MATT_CACHE_KEY_PREFIX = 'django_matt:'  # Prefix for cache keys
```

## Best Practices

Here are some best practices for using Django Matt's performance features:

### JSON Serialization

- Use `FastJsonResponse` instead of Django's `JsonResponse` for better performance.
- Install `orjson` or `ujson` for maximum JSON serialization performance.

### MessagePack

- Use MessagePack for API endpoints that need maximum performance and don't need to be human-readable.
- Make sure clients support MessagePack deserialization.
- Install the `msgpack` package: `pip install msgpack`.

### Streaming Responses

- Use streaming responses for large datasets to avoid memory issues.
- Consider pagination for very large datasets.
- Use `StreamingJsonResponse` with `stream_json_list` for the best performance.

### Caching

- Cache expensive operations and database queries.
- Use appropriate cache timeouts based on how frequently data changes.
- Implement cache invalidation when data changes.
- Consider using Redis as a cache backend for production.

### Benchmarking

- Use the benchmarking tools to identify performance bottlenecks.
- Monitor the performance of critical endpoints over time.
- Use the `BenchmarkMiddleware` in development to identify slow requests.

### General Performance Tips

- Use database indexes for frequently queried fields.
- Use Django's `select_related` and `prefetch_related` to reduce database queries.
- Consider using Django's `cached_property` for expensive property calculations.
- Use Django's built-in caching framework for template caching.
- Use Django Debug Toolbar in development to identify performance issues. 