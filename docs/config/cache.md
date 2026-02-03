# Cache Configuration

Django Matt provides comprehensive caching support with Redis (recommended), Memcached, and local memory backends, including distributed caching features with stampede prevention.

## Quick Start

=== "Redis (Recommended)"

    ```bash
    export CACHE_BACKEND=redis
    export REDIS_URL=redis://localhost:6379/0
    ```

=== "Memcached"

    ```bash
    export CACHE_BACKEND=memcached
    export MEMCACHED_LOCATION=127.0.0.1:11211
    ```

=== "Local Memory"

    ```bash
    export CACHE_BACKEND=locmem
    ```

=== "Auto-detect"

    ```bash
    # Automatically detects Redis > Memcached > Local Memory
    export CACHE_BACKEND=auto
    ```

## Redis Configuration

Redis is the recommended cache backend for production.

### Basic Configuration

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://localhost:6379/0",
        "KEY_PREFIX": "myapp",
        "TIMEOUT": 300,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
                "socket_timeout": 5,
                "socket_connect_timeout": 5,
                "retry_on_timeout": True,
            },
        },
    }
}
```

### Using the Helper Function

```python
from django_matt.config.components.cache import get_redis_cache_config

CACHES = {
    "default": get_redis_cache_config(
        url="redis://localhost:6379/0",
        key_prefix="myapp",
        timeout=300,
        max_connections=50,
        socket_timeout=5,
        socket_connect_timeout=5,
        retry_on_timeout=True,
    )
}
```

### Redis with Password

```bash
export REDIS_URL=redis://:password@localhost:6379/0
```

Or with URL encoding:

```bash
export REDIS_URL=redis://user:p%40ssw0rd@localhost:6379/0
```

### Redis SSL/TLS

```bash
export REDIS_URL=rediss://localhost:6379/0
```

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "rediss://localhost:6379/0",
        "OPTIONS": {
            "ssl_cert_reqs": "required",
        },
    }
}
```

## Redis Sentinel (High Availability)

Redis Sentinel provides automatic failover for Redis.

```python
from django_matt.config.components.cache import get_redis_sentinel_config

CACHES = {
    "default": get_redis_sentinel_config(
        sentinels=[
            ("sentinel1.example.com", 26379),
            ("sentinel2.example.com", 26379),
            ("sentinel3.example.com", 26379),
        ],
        master_name="mymaster",
        key_prefix="myapp",
        timeout=300,
        password="your-redis-password",  # Optional
    )
}
```

### Sentinel Configuration Details

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://mymaster/0",
        "KEY_PREFIX": "myapp",
        "TIMEOUT": 300,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.SentinelClient",
            "SENTINELS": [
                ("sentinel1.example.com", 26379),
                ("sentinel2.example.com", 26379),
                ("sentinel3.example.com", 26379),
            ],
            "SENTINEL_KWARGS": {
                "socket_timeout": 1,
            },
            "PASSWORD": "your-redis-password",
        },
    }
}
```

## Redis Cluster

For horizontal scaling with Redis Cluster:

```python
from django_matt.config.components.cache import get_redis_cluster_config

CACHES = {
    "default": get_redis_cluster_config(
        startup_nodes=[
            {"host": "node1.example.com", "port": 6379},
            {"host": "node2.example.com", "port": 6379},
            {"host": "node3.example.com", "port": 6379},
        ],
        key_prefix="myapp",
        timeout=300,
        skip_full_coverage_check=True,
    )
}
```

### Cluster Configuration Details

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://cluster",
        "KEY_PREFIX": "myapp",
        "TIMEOUT": 300,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "REDIS_CLIENT_CLASS": "redis.cluster.RedisCluster",
            "REDIS_CLIENT_KWARGS": {
                "startup_nodes": [
                    {"host": "node1.example.com", "port": 6379},
                    {"host": "node2.example.com", "port": 6379},
                    {"host": "node3.example.com", "port": 6379},
                ],
                "skip_full_coverage_check": True,
            },
        },
    }
}
```

## Memcached Configuration

```python
from django_matt.config.components.cache import get_memcached_config

CACHES = {
    "default": get_memcached_config(
        location=["memcached1:11211", "memcached2:11211"],
        key_prefix="myapp",
        timeout=300,
    )
}
```

### Environment Variable

```bash
export CACHE_BACKEND=memcached
export MEMCACHED_LOCATION=memcached1:11211,memcached2:11211
```

### Memcached with pymemcache

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
        "LOCATION": ["memcached1:11211", "memcached2:11211"],
        "KEY_PREFIX": "myapp",
        "TIMEOUT": 300,
    }
}
```

## Local Memory Cache

Good for development and single-server deployments:

```python
from django_matt.config.components.cache import get_locmem_config

CACHES = {
    "default": get_locmem_config(
        name="django_matt_cache",
        key_prefix="myapp",
        timeout=300,
        max_entries=1000,
    )
}
```

### Configuration

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-cache-name",
        "KEY_PREFIX": "myapp",
        "TIMEOUT": 300,
        "OPTIONS": {
            "MAX_ENTRIES": 1000,
        },
    }
}
```

## File-Based Cache

Useful for persistent caching without external services:

```python
from django_matt.config.components.cache import get_file_cache_config

CACHES = {
    "default": get_file_cache_config(
        location="/var/cache/django",
        key_prefix="myapp",
        timeout=300,
        max_entries=10000,
    )
}
```

## Auto-Detection

The `configure_cache` function automatically detects the best available backend:

```python
from django_matt.config.components.cache import configure_cache

CACHES = {
    "default": configure_cache(
        backend="auto",  # Detects: Redis > Memcached > Local Memory
        key_prefix="myapp",
        timeout=300,
    )
}
```

Detection order:

1. If `REDIS_URL` is set, use Redis
2. If `MEMCACHED_LOCATION` is set, use Memcached
3. Otherwise, use Local Memory

## Distributed Cache Manager

Django Matt provides a `DistributedCacheManager` for advanced caching scenarios.

### Basic Usage

```python
from django_matt.utils import distributed_cache

# Get or compute with stampede prevention
value = distributed_cache.get_or_set(
    "expensive_query",
    lambda: compute_expensive_result(),
    timeout=300,
)

# Async version
value = await distributed_cache.aget_or_set(
    "async_query",
    async_compute_function,
    timeout=300,
)
```

### Bulk Operations

```python
from django_matt.utils import distributed_cache

# Get multiple values
values = distributed_cache.get_many(["key1", "key2", "key3"])

# Set multiple values
distributed_cache.set_many({
    "key1": "value1",
    "key2": "value2",
    "key3": "value3",
}, timeout=300)

# Delete multiple values
distributed_cache.delete_many(["key1", "key2", "key3"])
```

### Atomic Operations

```python
from django_matt.utils import distributed_cache

# Increment counter
new_value = distributed_cache.incr("page_views", delta=1)

# Decrement counter
new_value = distributed_cache.decr("stock_count", delta=1)

# Refresh timeout without changing value
distributed_cache.touch("my_key", timeout=600)
```

### Namespaced Caching

```python
from django_matt.utils.performance import DistributedCacheManager

# Create namespaced cache for multi-tenancy
tenant_cache = DistributedCacheManager(namespace="tenant_123")

# Keys are automatically prefixed
tenant_cache.set("user_data", data)  # Actually stores "tenant_123:user_data"

# Clear all keys in namespace
tenant_cache.clear_namespace()
```

### Stampede Prevention

The `get_or_set` method includes built-in stampede prevention:

```python
# Only one process computes the value
# Others wait and get the cached result
value = distributed_cache.get_or_set(
    "popular_endpoint",
    expensive_computation,
    timeout=300,
)
```

How it works:

1. Process A finds cache miss
2. Process A acquires lock
3. Process B finds cache miss, sees lock, waits
4. Process A computes value, stores in cache, releases lock
5. Process B gets value from cache

## Cache Decorators

### Response Caching

```python
from django_matt.utils import cache_manager

@api.get("/products")
@cache_manager.cache_response(timeout=300, key_prefix="products")
async def list_products(request):
    return await Product.objects.all()
```

### Result Caching

```python
from django_matt.utils import cache_manager

@cache_manager.cache_result(timeout=600)
async def get_user_stats(user_id: int):
    # Expensive computation
    return compute_stats(user_id)
```

### Cache Invalidation

```python
from django_matt.utils import cache_manager

# Invalidate specific cache entry
cache_manager.invalidate("products", category_id=5)

# Invalidate by pattern (requires Redis)
cache_manager.invalidate_pattern("products:*")
```

## Multiple Caches

```python
CACHES = {
    "default": get_redis_cache_config(
        url="redis://localhost:6379/0",
        key_prefix="default",
    ),
    "sessions": get_redis_cache_config(
        url="redis://localhost:6379/1",
        key_prefix="sessions",
        timeout=1209600,  # 2 weeks
    ),
    "throttling": get_redis_cache_config(
        url="redis://localhost:6379/2",
        key_prefix="throttle",
        timeout=60,
    ),
}
```

### Using Specific Cache

```python
from django.core.cache import caches

sessions_cache = caches["sessions"]
sessions_cache.set("session_123", session_data)

throttle_cache = caches["throttling"]
throttle_cache.incr("api_calls:user_123")
```

## Session Storage with Redis

```python
# Cache configuration
CACHES = {
    "default": get_redis_cache_config(
        url=os.environ.get("REDIS_URL"),
        key_prefix="myapp",
    ),
}

# Use cache for sessions
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = 1209600  # 2 weeks
```

## Cache Middleware

Django Matt configures cache middleware settings automatically:

```python
# Set via environment or in settings
CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = 600
CACHE_MIDDLEWARE_KEY_PREFIX = "myapp"
```

### View Caching

```python
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)  # Cache for 15 minutes
def my_view(request):
    return render(request, "template.html")
```

## Best Practices

### Development

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "dev-cache",
        "TIMEOUT": 60,  # Short timeout for development
    }
}
```

### Production

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["REDIS_URL"],
        "KEY_PREFIX": os.environ.get("CACHE_KEY_PREFIX", "prod"),
        "TIMEOUT": 3600,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
            },
        },
    }
}
```

### Testing

```python
# Disable caching in tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}
```

### Cache Key Design

```python
# Good: Hierarchical keys with version
cache_key = f"api:v1:users:{user_id}:profile"
cache_key = f"api:v1:products:category:{category_id}:page:{page}"

# Include version for easy invalidation
CACHE_VERSION = 2  # Bump to invalidate all caches
cache_key = f"v{CACHE_VERSION}:users:{user_id}"
```

## Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_BACKEND` | `auto` | Backend type |
| `CACHE_TIMEOUT` | `300` | Default timeout |
| `CACHE_KEY_PREFIX` | `django_matt` | Key prefix |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL |
| `REDIS_MAX_CONNECTIONS` | `50` | Max connections |
| `MEMCACHED_LOCATION` | `127.0.0.1:11211` | Memcached location |
| `CACHE_MIDDLEWARE_SECONDS` | `600` | Middleware timeout |

## DJANGO_MATT Cache Settings

```python
DJANGO_MATT = {
    "CACHE_ENABLED": True,        # Enable/disable caching
    "CACHE_TIMEOUT": 300,         # Default timeout
    "CACHE_KEY_PREFIX": "django_matt:",  # Key prefix
    "CACHE_LOCK_TIMEOUT": 10,     # Stampede prevention lock timeout
}
```
