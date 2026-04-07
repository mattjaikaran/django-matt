# Performance Tuning Guide

Deep dive into maximizing django-matt performance. Covers Rust extensions, query optimization, serialization, caching, connection pooling, and profiling.

---

## Enabling Rust Extensions

django-matt includes optional Rust extensions compiled via PyO3+maturin. When installed, hot paths are automatically accelerated with zero code changes.

### What Gets Accelerated

| Hot Path | Pure Python | Rust Extension |
|---|---|---|
| URL routing | regex matching | `RadixRouter` radix tree |
| JWT encode | `encode_jwt()` | `jwt_encode_rust()` |
| JWT decode | `decode_jwt()` | `jwt_decode_rust()` |
| JWT verify | signature check | `jwt_verify_rust()` |
| JSON serialization | `orjson.dumps()` | `serialize_dicts_to_json()` |
| Query string parsing | `urllib.parse` | `parse_query_string_rust()` |
| Header parsing | Python dict build | `parse_headers_rust()` |
| camelCase mapping | Python loop | `build_camel_case_map()` |

### Installation

```bash
cd rust/
maturin develop --release
```

### Checking Availability

```python
from django_matt._accel import HAS_RUST

if HAS_RUST:
    print("Rust extensions active")
```

The `_accel` module handles dispatch transparently. When `HAS_RUST` is True, the accelerated implementations are used automatically by the router, JWT middleware, views, and serialization layer.

---

## Finding Bottlenecks with Auto-Instrumentation

Before optimizing, measure. django-matt provides auto-instrumentation that captures request timing, database queries, and cache operations.

### Setup

```python
from django_matt.observability import setup_observability, AutoInstrumentor

# One-time setup at app startup
setup_observability(
    service_name="myapp",
    tracing_enabled=True,
    metrics_enabled=True,
    logging_format="json",
)
```

### Middleware Stack

```python
MIDDLEWARE = [
    "django_matt.observability.ObservabilityMiddleware",
    # This single middleware combines:
    # - TracingMiddleware: distributed tracing spans
    # - MetricsMiddleware: request count, duration histograms
    # - LoggingMiddleware: structured request logs
    # ...
]
```

### Database Query Middleware

Find N+1 queries and slow queries:

```python
MIDDLEWARE = [
    "django_matt.observability.DatabaseQueryMiddleware",
    # ...
]
```

This logs all SQL queries with timing. In development, it warns about:
- Queries over a configurable threshold
- Duplicate queries (N+1 patterns)
- Missing indexes (sequential scans)

### Per-Function Profiling

```python
from django_matt.observability import trace, timed, counted

@trace("fetch_user_orders")
@timed("user_orders_duration")
@counted("user_orders_count")
async def fetch_user_orders(user_id: int):
    return [o async for o in Order.objects.filter(user_id=user_id)]
```

### Metrics Endpoint

Expose Prometheus-compatible metrics:

```python
from django_matt.observability import observability_urlpatterns

urlpatterns = [
    path("", include(observability_urlpatterns)),
    # GET /metrics/ returns Prometheus text format
]
```

---

## Query Optimization

### Auto-Optimization in Views

django-matt views automatically analyze your Pydantic schema to apply `select_related` and `prefetch_related`:

```python
class OrderSchema(BaseModel):
    id: int
    customer_name: str   # from order.customer.name -> auto select_related("customer")
    items: list[ItemSchema]  # reverse FK -> auto prefetch_related("items")

class OrderViewSet(APIViewSet):
    model = Order
    list = ListView(response_schema=OrderSchema)
    # QuerySet is auto-optimized based on schema fields
```

### Manual Optimization

For complex queries, override `get_queryset`:

```python
class OrderViewSet(APIViewSet):
    model = Order

    def get_queryset(self):
        return (
            Order.objects
            .select_related("customer", "customer__organization")
            .prefetch_related("items", "items__product")
            .only("id", "created_at", "status", "customer__name")
            .order_by("-created_at")
        )
```

### `.only()` for Partial Loading

Load only the columns you need:

```python
# Load 3 columns instead of 20
users = User.objects.only("id", "email", "name").filter(is_active=True)
```

### Async Iteration

Always use async iteration in async handlers:

```python
# Correct: streams results without loading all into memory
async for order in Order.objects.filter(status="pending"):
    await process(order)

# Also correct: materialize when you need a list
orders = [o async for o in Order.objects.filter(status="pending")]
```

### Aggregation at the Database

Push computation to the database instead of Python:

```python
from django.db.models import Avg, Count, Sum

stats = await Order.objects.filter(
    created_at__gte=last_month
).aaggregate(
    total_revenue=Sum("amount"),
    avg_order_value=Avg("amount"),
    order_count=Count("id"),
)
```

---

## Serialization Optimization

### orjson (Base Dependency)

orjson is always available -- it is a base dependency, not optional. It is 3-10x faster than stdlib `json`.

```python
import orjson

# Serialize
data = orjson.dumps({"users": users})  # returns bytes

# Deserialize
parsed = orjson.loads(request.body)
```

### model_construct for List Serialization

When serializing lists of ORM objects, `from_orm_fast()` uses Pydantic's `model_construct()` to skip re-validation (the data already comes from a validated source):

```python
from django_matt.core.schema import MattSchema

class UserSchema(MattSchema):
    id: int
    email: str
    name: str

# Fast path: constructs without validation
schema = UserSchema.from_orm_fast(user_instance)

# For lists, the views use this internally:
# [UserSchema.from_orm_fast(u) for u in queryset]
# This avoids re-validating every field for each object.
```

### FastJsonResponse

Use the optimized response class instead of Django's `JsonResponse`:

```python
from django_matt.utils.performance import FastJsonResponse

# Uses orjson internally -- 3x faster than JsonResponse
return FastJsonResponse({"users": user_list})
```

### MessagePack for Internal APIs

For service-to-service communication where human readability is not needed:

```python
from django_matt.utils.performance import MessagePackResponse

# ~30% smaller payload than JSON
return MessagePackResponse({"users": user_list})
```

### Rust-Accelerated Serialization

When Rust extensions are installed, list serialization for views uses `serialize_dicts_to_json()`:

```python
from django_matt._accel import HAS_RUST, serialize_dicts_to_json

if HAS_RUST:
    # Serializes a list of dicts to JSON bytes in Rust
    json_bytes = serialize_dicts_to_json(list_of_dicts)
```

This is used automatically by `ListView` and other views that return collections.

---

## Caching Layers

### Layer 1: In-Process (Interceptor)

Zero-latency cache for frequently accessed, rarely changing data:

```python
from django_matt.interceptors.builtins import CachingInterceptor
from django_matt.interceptors.decorators import intercept

@api.get("/config")
@intercept(CachingInterceptor(ttl=300.0))  # 5 minutes
async def get_config(request):
    return await load_app_config()
```

### Layer 2: Shared Cache (Redis)

Cross-process cache for data that must be consistent across workers:

```python
from django_matt.utils.performance import CacheManager

cache = CacheManager()  # uses Django cache backend (Redis)

key = f"user:{user_id}:profile"
profile = cache.get(key)
if profile is None:
    profile = await compute_profile(user_id)
    cache.set(key, profile, timeout=600)
```

### Layer 3: HTTP Cache Headers

Let CDNs and browsers cache responses:

```python
from django.views.decorators.cache import cache_control

@api.get("/products")
@cache_control(public=True, max_age=60)
async def list_products(request):
    ...
```

### Cache Key Generation

`CacheManager` generates keys by hashing the prefix + arguments:

```python
cache = CacheManager()
# Key: django_matt:user_profile:<md5 hash of args>
key = cache._get_cache_key("user_profile", user_id=123, include_orders=True)
```

---

## Connection Pooling Tuning

### Default Configuration

```python
configure(database="postgresql")
# Sets: MIN_SIZE=2, MAX_SIZE=10
```

### Production Tuning

```python
DJANGO_MATT = {
    "CONNECTION_POOL": {
        "ENABLED": True,
        "MIN_SIZE": 5,      # pre-warm 5 connections
        "MAX_SIZE": 20,      # peak concurrent queries
    },
}
```

### Sizing Formula

```
max_total_connections = pool_max_size * num_workers
```

| Workers | Pool Max | Total | PostgreSQL max_connections |
|---|---|---|---|
| 2 | 10 | 20 | 25 (with headroom) |
| 4 | 20 | 80 | 100 |
| 8 | 15 | 120 | 150 |

### PgBouncer for Large Deployments

When you have many workers or multiple services, use PgBouncer in transaction mode:

```ini
[pgbouncer]
pool_mode = transaction
max_client_conn = 500
default_pool_size = 25
reserve_pool_size = 5
```

Point Django at PgBouncer instead of PostgreSQL directly. This lets hundreds of worker connections share a small number of database connections.

---

## Benchmark Methodology

### Running Benchmarks

```bash
# JSON serialization benchmarks
uv run pytest tests/ -k "benchmark" -v

# Compare Rust vs Python paths
uv run python -m django_matt.benchmarks
```

### What to Measure

1. **Response time (p50, p95, p99)** -- use the metrics endpoint or tracing
2. **Throughput (requests/second)** -- use `wrk` or `hey`
3. **Database query count per request** -- `DatabaseQueryMiddleware`
4. **Memory usage** -- `tracemalloc` or container metrics
5. **Serialization time** -- `@timed` decorator on serialization functions

### Load Testing

```bash
# Install hey
brew install hey

# Baseline: 1000 requests, 10 concurrent
hey -n 1000 -c 10 http://localhost:8000/api/products/

# Stress: 10000 requests, 100 concurrent
hey -n 10000 -c 100 http://localhost:8000/api/products/
```

### Key Performance Patterns

These patterns are baked into django-matt's internals:

| Pattern | Where | Impact |
|---|---|---|
| Cache `get_type_hints()` at init | Controller, Schema | Eliminates per-request introspection |
| Cache `_meta.fields` as `_valid_filter_fields` frozenset | Views | Faster field validation |
| `orjson.loads()` everywhere | Controller, Router, Views | 3-10x faster JSON parsing |
| JWT: decode once, pass `_payload=` | Middleware -> View | No double-decode |
| Singleton `_ANONYMOUS_USER` | Auth middleware | No object creation for anon requests |
| Module-level `_error_config` cache | Error handling | Settings read once at import |
| Class-level `_error_handler` | APIController | Shared across instances |
| `model_construct()` for list serialization | Schema | Skip re-validation |
| Loop closure: `_method=method` default arg | Controller setup | Correct binding, no per-request lambda |
