# Performance Configuration

Django Matt provides comprehensive performance tuning options including fast JSON serialization, response caching, query optimization, and benchmarking tools.

## Quick Start

=== "Development"

    ```python
    DJANGO_MATT = {
        "BENCHMARK_ENABLED": True,
        "CACHE_ENABLED": True,
        "N1_DETECTION_ENABLED": True,
        "QUERY_OPTIMIZATION_ENABLED": True,
    }
    ```

=== "Production"

    ```python
    DJANGO_MATT = {
        "BENCHMARK_ENABLED": False,
        "CACHE_ENABLED": True,
        "N1_DETECTION_ENABLED": False,
        "QUERY_OPTIMIZATION_ENABLED": True,
    }
    ```

## Fast JSON Serialization

Django Matt automatically uses the fastest available JSON library.

### Installation

```bash
# Best performance (recommended)
pip install orjson

# Alternative (still faster than stdlib)
pip install ujson
```

### Usage

```python
from django_matt.utils.performance import FastJSONRenderer, FastJsonResponse

# Direct serialization
renderer = FastJSONRenderer()
json_bytes = renderer.dumps({"key": "value"})
data = renderer.loads(json_bytes)

# HTTP Response
response = FastJsonResponse({"status": "ok", "data": [1, 2, 3]})
```

### Performance Comparison

| Library | Serialization | Deserialization |
|---------|---------------|-----------------|
| orjson | 1x (fastest) | 1x (fastest) |
| ujson | 2-3x slower | 2x slower |
| stdlib json | 10x slower | 5x slower |

### orjson Options

```python
import orjson
from django_matt.utils.performance import FastJSONRenderer

# Use orjson-specific options
data = FastJSONRenderer.dumps(
    {"date": datetime.now()},
    orjson_options=orjson.OPT_NAIVE_UTC | orjson.OPT_SERIALIZE_NUMPY,
)
```

## MessagePack Serialization

For binary serialization (smaller payloads, faster processing):

```bash
pip install msgpack
```

```python
from django_matt.utils.performance import MessagePackRenderer, MessagePackResponse

# Direct serialization
renderer = MessagePackRenderer()
packed = renderer.dumps({"key": "value"})
data = renderer.loads(packed)

# HTTP Response
response = MessagePackResponse({"status": "ok", "data": [1, 2, 3]})
```

### When to Use MessagePack

- Internal service-to-service communication
- Mobile app APIs (smaller payloads)
- Real-time data streams
- Binary data handling

## Response Caching

### Decorator-Based Caching

```python
from django_matt.utils import cache_manager

@api.get("/products")
@cache_manager.cache_response(timeout=300, key_prefix="products")
async def list_products(request):
    return await Product.objects.all()

# Works with both sync and async views
@cache_manager.cache_response(timeout=600)
def sync_view(request):
    return expensive_computation()
```

### Result Caching

```python
from django_matt.utils import cache_manager

@cache_manager.cache_result(timeout=600, key_prefix="user_stats")
async def compute_user_stats(user_id: int):
    # Expensive computation cached by arguments
    return await calculate_stats(user_id)

# Called with same arguments returns cached result
stats1 = await compute_user_stats(123)  # Computed
stats2 = await compute_user_stats(123)  # Cached
stats3 = await compute_user_stats(456)  # Computed (different args)
```

### Cache Invalidation

```python
from django_matt.utils import cache_manager

# Invalidate specific entry
cache_manager.invalidate("user_stats", user_id=123)

# Invalidate by pattern (requires Redis)
cache_manager.invalidate_pattern("products:*")
```

## Streaming Responses

For large datasets, use streaming to avoid memory issues:

```python
from django_matt.utils.performance import StreamingJsonResponse, stream_json_list

@api.get("/export")
def export_all_products(request):
    # Generator yields products one at a time
    def product_generator():
        for product in Product.objects.iterator():
            yield {
                "id": product.id,
                "name": product.name,
                "price": str(product.price),
            }

    return StreamingJsonResponse(
        stream_json_list(product_generator(), chunk_size=100)
    )
```

### Benefits

- Constant memory usage regardless of dataset size
- Faster time-to-first-byte
- Works with database cursors

## Query Optimization

### Automatic Optimization

```python
from django_matt.utils import optimize_queryset

# Automatically adds select_related and prefetch_related
users = optimize_queryset(User.objects.all())

# Include reverse relations
users = optimize_queryset(User.objects.all(), include_reverse=True)
```

### Query Analysis

```python
from django_matt.utils import query_analyzer

# Analyze a queryset for optimization opportunities
analysis = query_analyzer.analyze_queryset(User.objects.all())

print(analysis)
# {
#     "model": "User",
#     "current_optimizations": {
#         "select_related": [],
#         "prefetch_related": []
#     },
#     "relations": {
#         "foreign_keys": ["profile", "organization"],
#         "many_to_many": ["groups", "permissions"],
#         "reverse_relations": ["posts", "comments"]
#     },
#     "suggestions": [
#         {
#             "type": "select_related",
#             "fields": ["profile", "organization"],
#             "fix": ".select_related('profile', 'organization')"
#         },
#         {
#             "type": "prefetch_related",
#             "fields": ["groups", "permissions"],
#             "fix": ".prefetch_related('groups', 'permissions')"
#         }
#     ],
#     "query_count_estimate": {
#         "without_optimization": 201,
#         "with_optimization": 3,
#         "potential_savings": 198
#     }
# }
```

### Query Logging Middleware

Enable query logging to detect N+1 issues:

```python
MIDDLEWARE = [
    # ... other middleware
    "django_matt.utils.QueryLoggingMiddleware",
]

DJANGO_MATT = {
    "QUERY_ANALYSIS_ENABLED": True,
}
```

Response headers will include:

```
X-Django-Matt-Query-Count: 5
```

### Duplicate Query Detection

```python
from django_matt.utils import query_analyzer

# After processing a request
duplicates = query_analyzer.get_duplicate_queries()
# {"SELECT * FROM users WHERE id = ?": 15}  # N+1 detected!

slow_queries = query_analyzer.get_slow_queries(threshold_ms=100)

report = query_analyzer.get_report()
# {
#     "total_queries": 23,
#     "total_time_ms": 156.7,
#     "avg_time_ms": 6.8,
#     "slow_queries": 2,
#     "potential_n_plus_1": 1
# }
```

## Benchmarking

### Response Timing

```python
# Enable in settings
DJANGO_MATT = {
    "BENCHMARK_ENABLED": True,
    "BENCHMARK_HEADER": "X-Django-Matt-Timing",
}

# Add middleware
MIDDLEWARE = [
    # ... other middleware
    "django_matt.utils.BenchmarkMiddleware",
]
```

Responses will include:

```
X-Django-Matt-Timing: 23.45ms
```

### Manual Benchmarking

```python
from django_matt.utils import benchmark

# As decorator
@benchmark.measure("my_operation")
def my_function():
    do_something()

# As context manager
with benchmark.measure("expensive_query"):
    result = expensive_query()

# Get report
report = benchmark.get_report()
# {
#     "my_operation": {
#         "count": 10,
#         "total_time": 234.5,
#         "avg_time": 23.45,
#         "min_time": 15.2,
#         "max_time": 45.6
#     }
# }

# Reset measurements
benchmark.reset()
```

## Performance Suggestions

Django Matt can analyze your application and provide recommendations:

```python
from django_matt.utils import performance_suggester

# Enable in settings
DJANGO_MATT = {
    "SUGGESTIONS_ENABLED": True,
}

# After processing requests, get suggestions
suggestions = performance_suggester.get_suggestions()

# [
#     {
#         "category": "serialization",
#         "priority": "high",
#         "title": "Slow JSON serialization",
#         "description": "Average serialization time is 52.3ms",
#         "recommendations": [
#             "Install orjson for 10x faster serialization"
#         ]
#     },
#     {
#         "category": "database",
#         "priority": "high",
#         "title": "High query count per request",
#         "description": "Average of 45.2 queries per request",
#         "recommendations": [
#             "Use select_related() for foreign key relationships",
#             "Consider using optimize_queryset() helper"
#         ]
#     }
# ]

summary = performance_suggester.get_summary()
```

### Observation Categories

| Category | What It Tracks |
|----------|----------------|
| `serialization` | Response size, serialization time |
| `query` | Query count, duplicates, slow queries |
| `cache` | Hit rate, miss rate |
| `dependencies` | Missing optimization libraries |

## Upload Size Limits

```python
# Maximum memory for data upload (2.5MB default)
DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440

# Maximum memory for file upload (2.5MB default)
FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440

# Maximum number of form fields
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000
```

### Environment Variables

```bash
export DATA_UPLOAD_MAX_MEMORY_SIZE=5242880  # 5MB
export FILE_UPLOAD_MAX_MEMORY_SIZE=10485760  # 10MB
export DATA_UPLOAD_MAX_NUMBER_FIELDS=2000
```

## Template Caching

For production, enable template caching:

```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ],
                ),
            ],
        },
    },
]
```

## Static Files

### Production Static Files

```python
# Use ManifestStaticFilesStorage for cache busting
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
```

### Environment Variable

```bash
export STATICFILES_STORAGE=django.contrib.staticfiles.storage.ManifestStaticFilesStorage
```

## Compression Middleware

Enable gzip compression:

```python
MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    # ... other middleware
]
```

## Database Connection Optimization

See [Database Configuration](database.md) for connection pooling settings.

Quick summary:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        # Persistent connections
        "CONN_MAX_AGE": None,
        # Health checks (Django 5.1+)
        "CONN_HEALTH_CHECKS": True,
        # Connection pool (Django 5.2+ with psycopg3)
        "OPTIONS": {
            "pool": {
                "min_size": 5,
                "max_size": 20,
            }
        },
    }
}
```

## Complete Performance Configuration

### Development

```python
# Prioritize debugging and visibility
DJANGO_MATT = {
    "BENCHMARK_ENABLED": True,
    "BENCHMARK_HEADER": "X-Django-Matt-Timing",
    "CACHE_ENABLED": True,
    "CACHE_TIMEOUT": 60,
    "QUERY_OPTIMIZATION_ENABLED": True,
    "N1_DETECTION_ENABLED": True,
    "QUERY_ANALYSIS_ENABLED": True,
    "SUGGESTIONS_ENABLED": True,
}

MIDDLEWARE = [
    "django_matt.utils.BenchmarkMiddleware",
    "django_matt.utils.QueryLoggingMiddleware",
    # ... other middleware
]

# SQL logging
LOGGING = {
    "loggers": {
        "django.db.backends": {
            "level": "DEBUG",  # See all SQL queries
        }
    }
}
```

### Staging

```python
# Balance between visibility and performance
DJANGO_MATT = {
    "BENCHMARK_ENABLED": True,
    "CACHE_ENABLED": True,
    "CACHE_TIMEOUT": 600,
    "QUERY_OPTIMIZATION_ENABLED": True,
    "N1_DETECTION_ENABLED": True,
    "QUERY_ANALYSIS_ENABLED": False,  # Disable for performance
    "SUGGESTIONS_ENABLED": False,
}

MIDDLEWARE = [
    "django_matt.utils.BenchmarkMiddleware",
    # ... other middleware
]
```

### Production

```python
# Maximum performance
DJANGO_MATT = {
    "BENCHMARK_ENABLED": False,  # Disable timing overhead
    "CACHE_ENABLED": True,
    "CACHE_TIMEOUT": 3600,
    "QUERY_OPTIMIZATION_ENABLED": True,
    "N1_DETECTION_ENABLED": False,  # Disable for performance
    "QUERY_ANALYSIS_ENABLED": False,
    "SUGGESTIONS_ENABLED": False,
}

# Enable compression
MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    # ... other middleware
]

# Template caching
TEMPLATES = [
    {
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [...],
                ),
            ],
        },
    },
]

# Static file hashing
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

# Persistent database connections
DATABASES["default"]["CONN_MAX_AGE"] = None
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
```

## Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_MATT_BENCHMARK_ENABLED` | `False` | Enable benchmarking |
| `DJANGO_MATT_BENCHMARK_HEADER` | `X-Django-Matt-Timing` | Timing header |
| `DJANGO_MATT_CACHE_ENABLED` | `True` | Enable caching |
| `DJANGO_MATT_QUERY_ANALYSIS_ENABLED` | `False` | Enable query analysis |
| `DJANGO_MATT_SUGGESTIONS_ENABLED` | `False` | Enable suggestions |
| `DATA_UPLOAD_MAX_MEMORY_SIZE` | `2621440` | Max upload memory |
| `FILE_UPLOAD_MAX_MEMORY_SIZE` | `2621440` | Max file memory |
| `DATA_UPLOAD_MAX_NUMBER_FIELDS` | `1000` | Max form fields |
| `STATICFILES_STORAGE` | `StaticFilesStorage` | Static storage backend |

## Performance Monitoring Integration

### New Relic

```python
import newrelic.agent
newrelic.agent.initialize('newrelic.ini')

# In WSGI/ASGI
application = newrelic.agent.WSGIApplicationWrapper(application)
```

### Sentry Performance

```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,  # 10% of transactions
)
```

### Prometheus Metrics

```python
# django-prometheus integration
INSTALLED_APPS += ["django_prometheus"]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    # ... other middleware
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]
```

## Profiling

### Django Silk

```python
# Development only
INSTALLED_APPS += ["silk"]

MIDDLEWARE = [
    "silk.middleware.SilkyMiddleware",
    # ... other middleware
]
```

### cProfile

```python
# For specific code paths
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here
result = expensive_operation()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats("cumulative")
stats.print_stats(20)
```
