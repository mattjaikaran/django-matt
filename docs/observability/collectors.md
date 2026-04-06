# Metrics Collectors

The `django_matt.observability.collectors` module provides thread-safe metrics collectors for requests, database queries, and cache operations. Collectors aggregate data in-memory and expose it via a `collect()` method.

## MetricsRegistry

All collectors register with a global `MetricsRegistry`:

```python
from django_matt.observability.collectors import metrics_registry

# Get a snapshot of all registered collectors
data = metrics_registry.collect_all()
# {"requests": {...}, "database": {...}, "cache": {...}}

# Access a specific collector
db = metrics_registry.get("database")

# Reset all collectors
metrics_registry.reset_all()
```

### Custom Collectors

Implement the `MetricsCollector` protocol to create your own:

```python
from django_matt.observability.collectors import MetricsCollector, metrics_registry

class QueueMetricsCollector:
    name: str = "queue"

    def collect(self) -> dict[str, Any]:
        return {"depth": get_queue_depth(), "workers": get_worker_count()}

    def reset(self) -> None:
        pass

metrics_registry.register(QueueMetricsCollector())
```

## RequestMetricsCollector

Tracks HTTP request counts, error rates, and latency distribution.

```python
from django_matt.observability.collectors import RequestMetricsCollector

collector = RequestMetricsCollector()
collector.record(method="GET", path="/api/users", status_code=200, duration=0.045)
collector.record(method="POST", path="/api/users", status_code=500, duration=1.2)

data = collector.collect()
```

### collect() Output

```python
{
    "total_requests": 2,
    "error_count": 1,          # status >= 400
    "error_rate": 0.5,
    "by_method": {"GET": 1, "POST": 1},
    "by_status": {200: 1, 500: 1},
    "duration": {
        "count": 2,
        "avg_ms": 622.5,
        "min_ms": 45.0,
        "max_ms": 1200.0,
        "p50_ms": 45.0,
        "p95_ms": 1200.0,
        "p99_ms": 1200.0,
    },
}
```

## DatabaseMetricsCollector

Tracks query counts by operation type, latency, and captures slow queries.

```python
from django_matt.observability.collectors import DatabaseMetricsCollector

collector = DatabaseMetricsCollector(slow_query_threshold_ms=100.0)
collector.record(operation="SELECT", table="users", duration=0.015, sql="SELECT * FROM users")
collector.record(operation="INSERT", table="orders", duration=0.250, sql="INSERT INTO orders ...")
```

### collect() Output

```python
{
    "total_queries": 2,
    "by_operation": {"SELECT": 1, "INSERT": 1},
    "duration": {
        "count": 2,
        "avg_ms": 132.5,
        "min_ms": 15.0,
        "max_ms": 250.0,
        "p50_ms": 15.0,
        "p95_ms": 250.0,
        "p99_ms": 250.0,
    },
    "slow_queries": [
        {
            "operation": "INSERT",
            "table": "orders",
            "duration_ms": 250.0,
            "sql": "INSERT INTO orders ...",  # truncated to 200 chars
            "timestamp": 1712345678.123,
        }
    ],
}
```

The slow query log keeps the most recent 100 entries. The default threshold is 100ms.

## CacheMetricsCollector

Tracks cache hit/miss rates, set/delete counts, and operation latencies.

```python
from django_matt.observability.collectors import CacheMetricsCollector

collector = CacheMetricsCollector()
collector.record_hit(duration=0.001)
collector.record_miss(duration=0.001)
collector.record_set(duration=0.002)
collector.record_delete(duration=0.001)
```

### collect() Output

```python
{
    "hits": 1,
    "misses": 1,
    "sets": 1,
    "deletes": 1,
    "hit_rate": 0.5,            # hits / (hits + misses)
    "total_operations": 4,
    "latency": {
        "count": 4,
        "avg_ms": 1.25,
        "p50_ms": 1.0,
        "p95_ms": 2.0,
    },
}
```

## Thread Safety

All collectors use `threading.Lock` internally. They are safe to use from multiple threads (e.g., gunicorn with sync workers). The `reset()` method on each collector clears all accumulated data.

## Usage with Auto-Instrumentation

When using `AutoInstrumentor`, collectors are created and registered automatically. You don't need to instantiate them manually:

```python
from django_matt.observability.setup import setup_observability, get_metrics_snapshot

setup_observability()

# Later, read the collected data
snapshot = get_metrics_snapshot()
print(snapshot["database"]["slow_queries"])
```
