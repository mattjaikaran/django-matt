# Response Caching

Django Matt provides comprehensive caching utilities for API responses, function results, and distributed caching scenarios.

## Overview

Caching is one of the most effective ways to improve API performance. Django Matt offers:

- **Response Caching** - Cache entire API responses
- **Result Caching** - Cache function return values
- **Distributed Caching** - Multi-node caching with stampede prevention
- **Cache Invalidation** - Smart cache invalidation strategies

## CacheManager

The `CacheManager` class provides decorators for caching responses and results.

### Response Caching

Cache entire API responses:

```python
from django_matt.utils.performance import cache_manager

@api.get("/products")
@cache_manager.cache_response(timeout=300)  # 5 minutes
async def list_products(request):
    return [p async for p in Product.objects.all()]
```

### Result Caching

Cache function return values:

```python
from django_matt.utils.performance import cache_manager

@cache_manager.cache_result(timeout=3600)  # 1 hour
async def get_expensive_calculation(user_id: int):
    # This result is cached based on function arguments
    return await compute_analytics(user_id)
```

### Cache Key Generation

Keys are automatically generated from function name and arguments:

```python
@cache_manager.cache_result(timeout=300, key_prefix="user_stats")
async def get_user_stats(user_id: int, period: str = "month"):
    return await calculate_stats(user_id, period)

# Cache keys generated:
# - get_user_stats(1, "month") -> "django_matt:user_stats:<hash>"
# - get_user_stats(1, "year")  -> "django_matt:user_stats:<different_hash>"
```

### Manual Cache Operations

```python
from django_matt.utils.performance import cache_manager

# Get value
value = cache_manager.get("my_key")

# Set value
cache_manager.set("my_key", {"data": "value"}, timeout=300)

# Delete value
cache_manager.delete("my_key")

# Invalidate by prefix and args
cache_manager.invalidate("user_stats", user_id=1, period="month")
```

### Pattern Invalidation

```python
# Invalidate all keys matching pattern (requires Redis)
cache_manager.invalidate_pattern("user_stats")
```

## DistributedCacheManager

For multi-node deployments, use `DistributedCacheManager` which provides:

- Namespace isolation
- Cache stampede prevention
- Bulk operations
- Atomic counters

### Basic Usage

```python
from django_matt.utils.performance import distributed_cache

# Get or compute with stampede prevention
value = distributed_cache.get_or_set(
    "expensive_query",
    lambda: compute_expensive_result(),
    timeout=300,
)
```

### Stampede Prevention

When a cached value expires, multiple concurrent requests might all try to compute the value simultaneously. `DistributedCacheManager` prevents this:

```python
# Only one process computes the value
# Others wait for the result
value = distributed_cache.get_or_set(
    "popular_key",
    lambda: slow_database_query(),  # Only called once
    timeout=300,
)
```

### Async Support

```python
# Async version
value = await distributed_cache.aget_or_set(
    "async_key",
    async_compute_function,
    timeout=300,
)
```

### Namespace Isolation

```python
from django_matt.utils.performance import DistributedCacheManager

# Create namespaced cache for multi-tenant apps
tenant_cache = DistributedCacheManager(namespace="tenant_123")

# Keys are prefixed with namespace
tenant_cache.set("user_count", 100)  # Stored as "tenant_123:user_count"
```

### Bulk Operations

```python
# Get multiple keys at once
values = distributed_cache.get_many(["key1", "key2", "key3"])
# Returns: {"key1": "value1", "key2": "value2"}

# Set multiple keys at once
distributed_cache.set_many({
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}, timeout=300)

# Delete multiple keys
distributed_cache.delete_many(["key1", "key2", "key3"])
```

### Atomic Counters

```python
# Increment counter (atomic operation)
new_count = distributed_cache.incr("page_views")

# Increment by specific amount
distributed_cache.incr("total_sales", delta=100)

# Decrement counter
distributed_cache.decr("inventory", delta=1)
```

### Touch (Extend TTL)

```python
# Extend TTL without changing value
distributed_cache.touch("important_key", timeout=600)
```

### Clear Namespace

```python
# Clear all keys in namespace (requires Redis pattern support)
distributed_cache.clear_namespace()
```

## Configuration

### Django Settings

```python
# settings.py

# Cache backend configuration
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://localhost:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# Django Matt cache settings
DJANGO_MATT_CACHE_ENABLED = True
DJANGO_MATT_CACHE_TIMEOUT = 300  # Default 5 minutes
DJANGO_MATT_CACHE_LOCK_TIMEOUT = 10  # Stampede lock timeout
```

### Disabling Cache

```python
# Disable caching globally (e.g., for testing)
DJANGO_MATT_CACHE_ENABLED = False
```

### Custom Cache Backend

```python
from django.core.cache import caches
from django_matt.utils.performance import CacheManager

# Use specific cache backend
session_cache = caches["sessions"]
session_manager = CacheManager(cache=session_cache)
```

## Caching Strategies

### 1. Time-Based Caching

Cache data for a fixed duration:

```python
@cache_manager.cache_response(timeout=60)  # 1 minute
async def get_live_data(request):
    return await fetch_live_data()
```

### 2. Request-Based Caching

Cache based on request parameters:

```python
@api.get("/users")
async def list_users(request, page: int = 1, limit: int = 20):
    # Cache key includes all parameters
    cache_key = f"users:page:{page}:limit:{limit}"

    cached = cache_manager.get(cache_key)
    if cached:
        return cached

    result = await User.objects.all()[(page-1)*limit:page*limit]
    cache_manager.set(cache_key, result, timeout=300)
    return result
```

### 3. User-Specific Caching

Cache data per user:

```python
@api.get("/profile")
async def get_profile(request):
    user_id = request.user.id
    cache_key = f"profile:{user_id}"

    cached = cache_manager.get(cache_key)
    if cached:
        return cached

    profile = await Profile.objects.get(user_id=user_id)
    cache_manager.set(cache_key, profile, timeout=3600)
    return profile
```

### 4. Computed Caching

Cache expensive computations:

```python
@cache_manager.cache_result(timeout=3600)
def compute_report(start_date, end_date, metrics):
    # This expensive computation is cached
    return generate_analytics_report(start_date, end_date, metrics)
```

## Cache Invalidation

### Manual Invalidation

```python
# After updating data
@api.put("/products/{product_id}")
async def update_product(request, product_id: int, data: ProductUpdate):
    await Product.objects.filter(id=product_id).update(**data.model_dump())

    # Invalidate related caches
    cache_manager.delete(f"product:{product_id}")
    cache_manager.invalidate_pattern("products:*")

    return {"status": "updated"}
```

### Model Signal Invalidation

```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):
    cache_manager.delete(f"product:{instance.id}")
    cache_manager.invalidate_pattern("products:*")
```

### Decorator-Based Invalidation

```python
def invalidates_cache(*patterns):
    """Decorator to invalidate cache after function execution."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            for pattern in patterns:
                cache_manager.invalidate_pattern(pattern)
            return result
        return wrapper
    return decorator

@api.post("/products")
@invalidates_cache("products:*")
async def create_product(request, data: ProductCreate):
    return await Product.objects.create(**data.model_dump())
```

## Performance Benchmarks

Cache operation performance with Redis:

| Operation | Time | Ops/s |
|-----------|------|-------|
| GET (hit) | 0.2ms | 5,000 |
| GET (miss) | 0.2ms | 5,000 |
| SET | 0.3ms | 3,300 |
| DELETE | 0.2ms | 5,000 |
| get_or_set (hit) | 0.2ms | 5,000 |
| get_or_set (miss) | 0.5ms | 2,000 |

### Run Benchmarks

```bash
python manage.py benchmark --scenario caching
```

## Best Practices

### 1. Cache at the Right Level

```python
# Bad: Cache too granular
@cache_manager.cache_result(timeout=60)
def get_user_name(user_id):
    return User.objects.get(id=user_id).name

# Good: Cache complete responses
@cache_manager.cache_response(timeout=300)
async def get_user_profile(request, user_id: int):
    return await UserProfile.objects.select_related("user").get(user_id=user_id)
```

### 2. Set Appropriate Timeouts

```python
# Frequently changing data - short timeout
@cache_manager.cache_response(timeout=60)  # 1 minute
async def get_live_prices(request):
    pass

# Rarely changing data - long timeout
@cache_manager.cache_response(timeout=86400)  # 24 hours
async def get_categories(request):
    pass
```

### 3. Use Namespaces for Multi-Tenant

```python
def get_tenant_cache(tenant_id: str) -> DistributedCacheManager:
    return DistributedCacheManager(namespace=f"tenant:{tenant_id}")

@api.get("/data")
async def get_data(request):
    tenant_id = request.headers.get("X-Tenant-ID")
    cache = get_tenant_cache(tenant_id)
    return cache.get_or_set("data", compute_data)
```

### 4. Handle Cache Failures Gracefully

```python
@api.get("/products")
async def list_products(request):
    try:
        cached = cache_manager.get("products")
        if cached:
            return cached
    except Exception:
        # Log and continue without cache
        pass

    products = [p async for p in Product.objects.all()]

    try:
        cache_manager.set("products", products, timeout=300)
    except Exception:
        # Log cache write failure
        pass

    return products
```

### 5. Monitor Cache Performance

```python
from django_matt.utils.performance import performance_suggester

# Log cache observations
@api.get("/data")
async def get_data(request):
    cache_key = "data"
    cached = cache_manager.get(cache_key)

    performance_suggester.observe("cache", {
        "hit": cached is not None,
        "key": cache_key,
    })

    if cached:
        return cached
    # ...

# Review suggestions
suggestions = performance_suggester.get_suggestions()
```

## Troubleshooting

### Cache Not Working

1. Check if caching is enabled:
   ```python
   from django.conf import settings
   print(settings.DJANGO_MATT_CACHE_ENABLED)  # Should be True
   ```

2. Verify cache backend connection:
   ```python
   from django.core.cache import cache
   cache.set("test", "value")
   print(cache.get("test"))  # Should print "value"
   ```

### High Cache Miss Rate

Review cache key generation:

```python
# Bad: Cache key doesn't include relevant parameters
@cache_manager.cache_response(timeout=300)
async def get_items(request, category: str, sort: str):
    pass  # Different params use same cache key!

# Good: Use custom key prefix
@cache_manager.cache_response(timeout=300, key_prefix="items")
async def get_items(request, category: str, sort: str):
    pass  # Includes all args in cache key
```

### Pattern Invalidation Not Working

Requires Redis backend with pattern support:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        # ...
    }
}
```

LocMem cache doesn't support pattern invalidation.

### Cache Stampede

If you're seeing multiple computations for expired keys:

```python
# Use distributed cache with stampede prevention
from django_matt.utils.performance import distributed_cache

value = distributed_cache.get_or_set(
    "expensive_key",
    compute_function,
    timeout=300,
)
```
