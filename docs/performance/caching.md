# Caching

Response caching and cache management.

## Response Caching

```python
from django_matt.utils import cache_manager

@api.get("/expensive")
@cache_manager.cache_response(timeout=300)
async def expensive_operation(request):
    return await compute_expensive_result()
```

## Distributed Caching

```python
from django_matt.utils import distributed_cache

# Get or compute with stampede prevention
value = distributed_cache.get_or_set(
    "expensive_query",
    lambda: expensive_computation(),
    timeout=300,
)
```

## Cache Invalidation

```python
from django_matt.utils import CacheInvalidationMixin

class Product(CacheInvalidationMixin, models.Model):
    name = models.CharField(max_length=100)

    class CacheMeta:
        cache_key_prefix = "product"
        invalidate_related = ["category"]
```
