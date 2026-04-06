# Exporters

Exporters receive finished span trees and send them to external systems. Django Matt ships with four built-in exporters plus a `MultiExporter` that fans out to multiple backends.

## ExporterProtocol

All exporters implement this protocol:

```python
class ExporterProtocol(Protocol):
    def export(self, span: Span) -> None: ...
    def shutdown(self) -> None: ...
```

## ConsoleExporter

Prints span trees to stderr with optional ANSI color. Best for local development.

```python
from django_matt.observability.exporters import ConsoleExporter

exporter = ConsoleExporter(color=True)  # color=True is the default
```

Output example:

```
[+] controller.UserController.list_users (12.34ms) component=controller
  [+] service.UserService.get_all (8.21ms) component=service
  [!] service.UserService.validate (2.10ms) error=ValueError: invalid input
```

Status icons: `+` = ok, `!` = error, `?` = unset.

### Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stream` | file-like | `sys.stderr` | Output stream |
| `color` | `bool` | `True` | Enable ANSI color codes |

## JSONExporter

Writes span trees as newline-delimited JSON (JSONL). Uses `orjson` for fast serialization.

```python
from django_matt.observability.exporters import JSONExporter

# Write to a file
exporter = JSONExporter(file_path="/var/log/app/spans.jsonl")

# Write to a stream
exporter = JSONExporter(stream=sys.stdout)

# Default: writes to sys.stdout
exporter = JSONExporter()
```

Each line is a complete JSON object with an `exported_at` timestamp appended:

```json
{"name":"request","start_time":1712345678.123,"end_time":1712345678.189,"duration_ms":66.0,"status":"ok","tags":{},"children":[...],"exported_at":1712345678.190}
```

Call `exporter.shutdown()` to close the file handle if using `file_path`.

## PrometheusExporter

Records span durations and counts as Prometheus metrics. Requires `prometheus_client`.

```python
from django_matt.observability.exporters import PrometheusExporter

exporter = PrometheusExporter()
```

Creates three Prometheus metrics:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `django_matt_span_duration_seconds` | Histogram | `span_name`, `status` | Span duration |
| `django_matt_spans_total` | Counter | `span_name`, `status` | Total span count |
| `django_matt_span_errors_total` | Counter | `span_name`, `error_type` | Error count by exception type |

Recursively exports child spans in addition to the root span. If `prometheus_client` is not installed, the exporter logs a warning and becomes a no-op.

## OpenTelemetryExporter

Bridges django-matt spans to OpenTelemetry. Requires `opentelemetry-sdk`.

```python
from django_matt.observability.exporters import OpenTelemetryExporter

exporter = OpenTelemetryExporter(service_name="my-django-app")
```

This creates an OTel `TracerProvider` with the given service name. Each django-matt `Span` is re-emitted as an OTel span with:

- All tags mapped to OTel attributes
- Errors recorded via `record_exception()` and `set_status(ERROR)`
- Child spans nested under the parent

Pair with an OTel span exporter (OTLP, Jaeger, etc.) configured via the standard OTel SDK APIs.

## MultiExporter

Fans out to multiple exporters. Used internally by `setup_observability()`.

```python
from django_matt.observability.exporters import MultiExporter, ConsoleExporter, JSONExporter

multi = MultiExporter([
    ConsoleExporter(),
    JSONExporter(file_path="/var/log/spans.jsonl"),
])

# Add more exporters later
multi.add(PrometheusExporter())

# Shut down all exporters
multi.shutdown()
```

If any individual exporter raises during `export()`, the error is logged and the remaining exporters still run.

## Configuration via Settings

The `setup_observability()` function builds exporters from `DJANGO_MATT_OBSERVABILITY["EXPORTERS"]`:

```python
DJANGO_MATT_OBSERVABILITY = {
    "EXPORTERS": [
        "console",                                         # ConsoleExporter()
        {"type": "json", "file_path": "/tmp/spans.jsonl"}, # JSONExporter(file_path=...)
        "prometheus",                                       # PrometheusExporter()
        {"type": "opentelemetry", "service_name": "myapp"}, # OpenTelemetryExporter(service_name=...)
    ],
}
```

If `EXPORTERS` is omitted:
- `DEBUG=True` -> `ConsoleExporter(color=True)`
- `DEBUG=False` -> `JSONExporter()` (writes to stdout)

## Writing a Custom Exporter

Implement `export()` and `shutdown()`:

```python
from django_matt.observability.exporters import ExporterProtocol
from django_matt.observability.spans import Span


class DatadogExporter:
    def export(self, span: Span) -> None:
        # Convert span tree to Datadog format and send
        ...

    def shutdown(self) -> None:
        # Flush any buffered data
        ...
```

Register it either via `setup_observability(exporters=[DatadogExporter()])` or add it to a `MultiExporter`.
