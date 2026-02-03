# Performance Optimization

Django Matt is designed for high performance out of the box. This guide covers the performance features available and how to optimize your API for maximum throughput.

## Performance Philosophy

Django Matt follows these performance principles:

1. **Fast by default** - Sensible defaults that work well without configuration
2. **Opt-in complexity** - Advanced features available when needed
3. **Measure, then optimize** - Built-in benchmarking to guide decisions
4. **No hidden costs** - Predictable performance characteristics

## Quick Wins

Get immediate performance benefits with minimal effort:

### 1. Install orjson

```bash
pip install orjson
```

Django Matt automatically uses orjson when available, providing 3-10x faster JSON serialization.

### 2. Enable Response Caching

```python
from django_matt.utils import cache_manager

@api.get("/products")
@cache_manager.cache_response(timeout=60)
async def list_products(request):
    return await Product.objects.all()
```

### 3. Use Query Optimization

```python
from django_matt.utils import optimize_queryset

# Automatically adds select_related/prefetch_related
products = optimize_queryset(Product.objects.all())
```

### 4. Use Async Views

```python
# Async views handle more concurrent requests
@api.get("/users")
async def list_users(request):
    return await User.objects.all()
```

## Performance Features Overview

| Feature | Purpose | Speed Improvement |
|---------|---------|-------------------|
| [Fast Serialization](serialization.md) | JSON/MessagePack encoding | 3-10x |
| [Response Caching](caching.md) | Cache API responses | 10-100x |
| [Query Optimization](database.md) | Eliminate N+1 queries | 2-50x |
| [Async Views](async.md) | Handle more concurrency | 2-5x throughput |

## Performance Utilities

Django Matt provides these performance utilities:

### Serialization

```python
from django_matt.utils.performance import (
    FastJSONRenderer,      # Auto-selects fastest JSON library
    MessagePackRenderer,   # Binary serialization
    FastJsonResponse,      # Fast JSON HTTP response
    MessagePackResponse,   # Binary HTTP response
    StreamingJsonResponse, # Stream large datasets
    stream_json_list,      # Stream list as JSON array
)
```

### Caching

```python
from django_matt.utils.performance import (
    CacheManager,              # Response and result caching
    DistributedCacheManager,   # Multi-node caching with stampede prevention
    cache_manager,             # Default singleton instance
    distributed_cache,         # Default distributed cache instance
)
```

### Query Analysis

```python
from django_matt.utils.performance import (
    QueryAnalyzer,         # Analyze queries for optimization
    optimize_queryset,     # Auto-optimize querysets
    query_analyzer,        # Default singleton instance
)
```

### Benchmarking

```python
from django_matt.utils.performance import (
    APIBenchmark,          # Measure operation timing
    BenchmarkMiddleware,   # Add timing headers to responses
    benchmark,             # Default singleton instance
)
```

### Suggestions

```python
from django_matt.utils.performance import (
    PerformanceSuggester,    # Runtime performance analysis
    performance_suggester,   # Default singleton instance
)
```

## Configuration

### Django Settings

```python
# settings.py

DJANGO_MATT = {
    # Caching
    "CACHE_ENABLED": True,           # Enable/disable all caching
    "CACHE_TIMEOUT": 300,            # Default cache timeout (5 min)
    "CACHE_LOCK_TIMEOUT": 10,        # Stampede prevention lock timeout

    # Query Analysis
    "QUERY_ANALYSIS_ENABLED": False, # Enable query logging (dev only)

    # Benchmarking
    "BENCHMARK_ENABLED": False,      # Enable timing measurements

    # Suggestions
    "SUGGESTIONS_ENABLED": False,    # Enable performance suggestions
}
```

### Middleware

```python
# settings.py

MIDDLEWARE = [
    # Add timing headers to responses
    "django_matt.utils.BenchmarkMiddleware",

    # Log queries for N+1 detection
    "django_matt.utils.QueryLoggingMiddleware",

    # ... other middleware
]
```

## Measuring Performance

### Using the Benchmark Command

```bash
# Run all benchmarks
python manage.py benchmark

# Run specific scenarios
python manage.py benchmark --scenario json schema

# Compare with previous run
python manage.py benchmark --compare --save
```

### Using the Benchmark Decorator

```python
from django_matt.utils.performance import benchmark

@api.get("/data")
@benchmark.measure("data_endpoint")
async def get_data(request):
    return await expensive_operation()

# Get timing report
report = benchmark.get_report()
# {
#     "data_endpoint": {
#         "count": 1000,
#         "total_time": 5234.5,
#         "avg_time": 5.23,
#         "min_time": 2.1,
#         "max_time": 45.2
#     }
# }
```

### Using the Performance Suggester

```python
from django_matt.utils.performance import performance_suggester

# Get optimization suggestions
suggestions = performance_suggester.get_suggestions()

for suggestion in suggestions:
    print(f"[{suggestion['priority']}] {suggestion['title']}")
    print(f"  {suggestion['description']}")
    for rec in suggestion['recommendations']:
        print(f"    - {rec}")
```

## Common Optimizations

### 1. Large List Responses

```python
# Bad: Load all into memory
@api.get("/items")
async def get_items(request):
    items = await Item.objects.all()
    return items  # May be thousands of items

# Good: Use pagination
@api.get("/items")
async def get_items(request, page: int = 1, limit: int = 20):
    offset = (page - 1) * limit
    items = await Item.objects.all()[offset:offset + limit]
    return items

# Good: Stream large datasets
from django_matt.utils import StreamingJsonResponse, stream_json_list

@api.get("/items/export")
async def export_items(request):
    items = Item.objects.all().iterator()
    return StreamingJsonResponse(stream_json_list(items))
```

### 2. Expensive Computations

```python
# Bad: Compute on every request
@api.get("/analytics")
async def get_analytics(request):
    return await compute_analytics()  # Takes 5 seconds

# Good: Cache results
from django_matt.utils import cache_manager

@api.get("/analytics")
@cache_manager.cache_response(timeout=3600)
async def get_analytics(request):
    return await compute_analytics()  # Cached for 1 hour
```

### 3. Related Data

```python
# Bad: N+1 queries
@api.get("/orders")
async def get_orders(request):
    orders = await Order.objects.all()
    # Accessing order.customer triggers N queries
    return [{"id": o.id, "customer": o.customer.name} for o in orders]

# Good: Select related
@api.get("/orders")
async def get_orders(request):
    orders = await Order.objects.select_related("customer").all()
    return [{"id": o.id, "customer": o.customer.name} for o in orders]

# Good: Auto-optimize
from django_matt.utils import optimize_queryset

@api.get("/orders")
async def get_orders(request):
    orders = optimize_queryset(Order.objects.all())
    return orders
```

### 4. Concurrent Operations

```python
# Bad: Sequential operations
@api.get("/dashboard")
async def get_dashboard(request):
    users = await User.objects.count()
    orders = await Order.objects.count()
    revenue = await Payment.objects.aggregate(Sum("amount"))
    return {"users": users, "orders": orders, "revenue": revenue}

# Good: Parallel operations
import asyncio

@api.get("/dashboard")
async def get_dashboard(request):
    users, orders, revenue = await asyncio.gather(
        User.objects.count(),
        Order.objects.count(),
        Payment.objects.aggregate(Sum("amount")),
    )
    return {"users": users, "orders": orders, "revenue": revenue}
```

## Performance Checklist

Before deploying to production:

- [ ] Install `orjson` for fast JSON serialization
- [ ] Enable response caching for read-heavy endpoints
- [ ] Add `select_related`/`prefetch_related` for related queries
- [ ] Use pagination for list endpoints
- [ ] Configure Redis for distributed caching
- [ ] Run benchmarks to establish baseline
- [ ] Enable N+1 detection in development
- [ ] Review performance suggestions

## Next Steps

- [Fast Serialization](serialization.md) - orjson, ujson, MessagePack
- [Response Caching](caching.md) - CacheManager, distributed caching
- [Database Optimization](database.md) - Query analysis, N+1 detection
- [Async Views](async.md) - Async handlers and concurrent operations
- [Benchmarking](../benchmarks/index.md) - Measuring and tracking performance
