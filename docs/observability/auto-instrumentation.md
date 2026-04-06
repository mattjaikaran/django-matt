# Auto-Instrumentation

Django Matt's auto-instrumentation provides zero-config observability by automatically wrapping controllers, services, database queries, cache operations, and outbound HTTP calls with spans and metrics collection.

## Overview

The `AutoInstrumentor` monkey-patches key subsystems at startup so every operation is traced and metered without touching application code.

```
                  setup_observability()
                         |
               +---------v---------+
               |  AutoInstrumentor |
               +---------+---------+
                         |
     +--------+----------+----------+---------+
     |        |          |          |         |
Controllers Services   Database   Cache     HTTP
  (spans)   (spans)   (metrics   (metrics  (spans)
                       + slow     + hit/miss
                       queries)   rates)
```

## Quick Start (Zero-Config)

Call `setup_observability()` in your `AppConfig.ready()` and everything is instrumented automatically:

```python
# myapp/apps.py
from django.apps import AppConfig


class MyAppConfig(AppConfig):
    name = "myapp"

    def ready(self):
        from django_matt.observability.setup import setup_observability
        setup_observability()
```

By default:

- **DEBUG=True**: spans print to stderr with color (ConsoleExporter)
- **DEBUG=False**: spans emit as JSON lines to stdout (JSONExporter)

No settings required. Override via `DJANGO_MATT_OBSERVABILITY` in your settings if needed.

## Settings

```python
# settings.py
DJANGO_MATT_OBSERVABILITY = {
    "ENABLED": True,

    # Exporter configuration (list of exporter specs)
    "EXPORTERS": [
        "console",                              # string shorthand
        {"type": "json", "file_path": "/var/log/spans.jsonl"},  # dict with options
        "prometheus",                            # requires prometheus_client
        {"type": "opentelemetry", "service_name": "myapp"},  # requires opentelemetry-sdk
    ],

    # Service modules to auto-instrument (classes ending in "Service")
    "SERVICE_MODULES": [
        "myapp.services",
        "myapp.payment.services",
    ],

    "SERVICE_NAME": "my-django-app",
}
```

If `EXPORTERS` is omitted, the default exporter is chosen based on `DEBUG`.

## AutoInstrumentor

The `AutoInstrumentor` class provides granular control over what gets instrumented.

### instrument_all()

Instruments everything in one call. This is what `setup_observability(auto=True)` uses internally.

```python
from django_matt.observability.auto import AutoInstrumentor

instrumentor = AutoInstrumentor()
instrumentor.instrument_all(service_modules=["myapp.services"])
```

### Individual Instrumentation

```python
instrumentor = AutoInstrumentor()

# Controllers: wraps every public method on APIController subclasses
instrumentor.instrument_controllers()

# Services: wraps public functions and methods on *Service classes
instrumentor.instrument_services("myapp.services", "myapp.billing.services")

# Database: wraps cursor.execute/executemany, tracks operation/table/duration
instrumentor.instrument_db()

# Cache: wraps django.core.cache get/set/delete, tracks hit/miss rates
instrumentor.instrument_cache()

# HTTP: wraps urllib.request.urlopen with outbound spans
instrumentor.instrument_http()
```

Each subsystem is instrumented at most once (tracked via a module-level `_instrumented` set). Calling the same method twice is a no-op.

### What Gets Instrumented

| Subsystem | What happens | Span name pattern |
|-----------|-------------|-------------------|
| Controllers | Every public method on `APIController` subclasses is wrapped in a span | `controller.{ClassName}.{method}` |
| Services | Public functions in specified modules + methods on `*Service` classes | `service.{module}.{func}` or `service.{ClassName}.{method}` |
| Database | `cursor.execute()` and `cursor.executemany()` record operation, table, and duration | N/A (metrics only) |
| Cache | `cache.get/set/delete` record hit/miss/set/delete counts and latencies | N/A (metrics only) |
| HTTP | `urllib.request.urlopen` is wrapped in a span | `http.outbound` |

### Accessing Collectors

The instrumentor exposes its collectors for direct metric reads:

```python
instrumentor = get_instrumentor()

# Request metrics (registered with metrics_registry)
request_data = instrumentor.request_collector.collect()

# Database metrics
db_data = instrumentor.db_collector.collect()

# Cache metrics
cache_data = instrumentor.cache_collector.collect()
```

## setup_observability()

The high-level entry point that wires exporters, span listeners, and auto-instrumentation together.

```python
from django_matt.observability.setup import setup_observability

# Full auto setup from settings
instrumentor = setup_observability()

# Disable auto-instrumentation (just wire exporters)
instrumentor = setup_observability(auto=False)

# Pass custom exporters
from django_matt.observability.exporters import ConsoleExporter, JSONExporter
instrumentor = setup_observability(
    exporters=[ConsoleExporter(color=False), JSONExporter(file_path="/tmp/spans.jsonl")],
    service_modules=["myapp.services"],
)
```

### Helper Functions

```python
from django_matt.observability.setup import (
    get_instrumentor,       # Returns the active AutoInstrumentor or None
    get_exporter,           # Returns the active MultiExporter or None
    get_metrics_snapshot,   # Returns all collector data as a dict
    shutdown_observability,  # Shuts down exporters and clears state
)

# Get a snapshot of all registered metrics
snapshot = get_metrics_snapshot()
# {"requests": {...}, "database": {...}, "cache": {...}}
```

## Resetting (Testing)

```python
from django_matt.observability.auto import reset_instrumentation

# Clear the instrumented set so subsystems can be re-instrumented
reset_instrumentation()
```

## How It Works

1. `setup_observability()` reads `DJANGO_MATT_OBSERVABILITY` from settings
2. It builds a `MultiExporter` from the configured exporters
3. The exporter is registered as a span listener via `add_span_listener()`
4. `AutoInstrumentor.instrument_all()` patches controllers, services, DB, cache, and HTTP
5. Every patched operation creates a `Span` (or records metrics directly for DB/cache)
6. When a root span finishes, all listeners are notified and exporters receive the span tree
