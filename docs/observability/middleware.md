# Observability Middleware

Django Matt provides middleware for automatic request tracing, metrics collection, and structured logging.

## Available Middleware

| Middleware | Purpose |
|------------|---------|
| `TracingMiddleware` | Distributed tracing with OpenTelemetry |
| `MetricsMiddleware` | Prometheus metrics collection |
| `LoggingMiddleware` | Structured request logging |
| `DatabaseQueryMiddleware` | Database query tracking |
| `ObservabilityMiddleware` | Combined (all of the above) |

## Quick Setup

### Individual Middleware

```python
# settings.py

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',

    # Observability middleware (add after auth middleware)
    'django_matt.observability.TracingMiddleware',
    'django_matt.observability.MetricsMiddleware',
    'django_matt.observability.LoggingMiddleware',
    # Optional: database query tracking (requires DEBUG=True)
    'django_matt.observability.DatabaseQueryMiddleware',
]
```

### Combined Middleware

For convenience, use `ObservabilityMiddleware` which combines tracing, metrics, and logging:

```python
MIDDLEWARE = [
    # ... Django middleware ...

    # Single middleware for all observability
    'django_matt.observability.ObservabilityMiddleware',
]
```

## TracingMiddleware

Creates distributed traces for each request using OpenTelemetry.

### What It Does

1. Extracts trace context from incoming request headers
2. Creates a span for the request
3. Sets correlation ID (from header or generates new one)
4. Adds request attributes to span
5. Records response status and size
6. Propagates trace context to response headers

### Configuration

```python
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "otlp",
    "ENDPOINT": "http://localhost:4317",
    "SAMPLE_RATE": 1.0,
}
```

### Span Attributes

The middleware automatically sets these attributes on request spans:

| Attribute | Description |
|-----------|-------------|
| `http.method` | HTTP method (GET, POST, etc.) |
| `http.url` | Full request URL |
| `http.path` | Request path |
| `http.host` | Request host |
| `http.scheme` | Protocol (http/https) |
| `http.user_agent` | User agent string |
| `http.status_code` | Response status code |
| `http.response_content_length` | Response body size |
| `correlation_id` | Request correlation ID |
| `user.id` | Authenticated user ID |

### Response Headers

The middleware adds these headers to responses:

| Header | Description |
|--------|-------------|
| `X-Correlation-ID` | Request correlation ID |
| `X-Trace-ID` | OpenTelemetry trace ID |

### Path Normalization

Request paths are normalized to avoid high-cardinality metrics:

```python
# Original paths → Normalized
/users/12345          → /users/{id}
/orders/abc-def-123   → /orders/{uuid}
/products/a1b2c3d4    → /products/{id}
```

### Example Span

```
Span: GET /users/{id}
├── Attributes
│   ├── http.method: GET
│   ├── http.url: https://api.example.com/users/123
│   ├── http.path: /users/123
│   ├── http.status_code: 200
│   ├── correlation_id: abc-123-def
│   └── user.id: 42
├── Events
│   └── exception (if error occurred)
└── Status: OK
```

## MetricsMiddleware

Collects Prometheus metrics for each request.

### What It Does

1. Tracks active requests (gauge)
2. Records request duration (histogram)
3. Counts total requests (counter)
4. Counts errors (counter)
5. Adds timing header to response

### Configuration

```python
DJANGO_MATT_METRICS = {
    "ENABLED": True,
    "PREFIX": "myapp",
    "DEFAULT_BUCKETS": [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    "EXCLUDE_PATHS": ["/_matt/metrics", "/health", "/ready"],
}
```

### Metrics Collected

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `{prefix}_http_request_duration_seconds` | Histogram | method, endpoint, status | Request latency |
| `{prefix}_http_requests_total` | Counter | method, endpoint, status | Total requests |
| `{prefix}_http_errors_total` | Counter | method, endpoint, error_type | Errors (4xx, 5xx) |
| `{prefix}_http_requests_active` | Gauge | method, endpoint | Active requests |

### Response Headers

| Header | Description |
|--------|-------------|
| `X-Response-Time` | Request duration (e.g., "125.50ms") |

### Excluding Paths

Exclude paths from metrics collection:

```python
DJANGO_MATT_METRICS = {
    "EXCLUDE_PATHS": [
        "/_matt/metrics",  # Don't record metrics endpoint
        "/health",          # Don't record health checks
        "/ready",           # Don't record readiness checks
        "/static/",         # Don't record static files
        "/media/",          # Don't record media files
    ],
}
```

## LoggingMiddleware

Provides structured request logging with correlation IDs.

### What It Does

1. Generates unique request ID
2. Sets correlation ID (from header or generates)
3. Sets user ID if authenticated
4. Logs request start with details
5. Logs request completion with duration
6. Logs errors with traceback
7. Adds context headers to response

### Configuration

```python
DJANGO_MATT_LOGGING = {
    "ENABLED": True,
    "FORMAT": "json",
    "LEVEL": "INFO",
    "INCLUDE_TIMESTAMP": True,
    "INCLUDE_CORRELATION_ID": True,
    "INCLUDE_REQUEST_ID": True,
    "INCLUDE_USER": True,
}
```

### Logged Information

**Request Start:**
```json
{
  "level": "INFO",
  "message": "Request started",
  "correlation_id": "abc123",
  "request_id": "req-456",
  "extra": {
    "method": "POST",
    "path": "/api/orders",
    "query_string": "page=1",
    "user_agent": "Mozilla/5.0...",
    "remote_addr": "192.168.1.100"
  }
}
```

**Request Completed:**
```json
{
  "level": "INFO",
  "message": "Request completed",
  "correlation_id": "abc123",
  "request_id": "req-456",
  "extra": {
    "method": "POST",
    "path": "/api/orders",
    "status_code": 201,
    "duration_ms": 125.5,
    "content_length": 1234
  }
}
```

**Request Failed:**
```json
{
  "level": "ERROR",
  "message": "Request failed",
  "correlation_id": "abc123",
  "request_id": "req-456",
  "exception": {
    "type": "ValueError",
    "message": "Invalid input",
    "traceback": ["..."]
  },
  "extra": {
    "method": "POST",
    "path": "/api/orders",
    "duration_ms": 50.2,
    "error": "Invalid input",
    "error_type": "ValueError"
  }
}
```

### Response Headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Unique request identifier |
| `X-Correlation-ID` | Correlation ID for distributed tracing |

### Client IP Detection

The middleware correctly handles proxied requests:

```python
# Checks headers in order:
# 1. X-Forwarded-For
# 2. REMOTE_ADDR
```

## DatabaseQueryMiddleware

Tracks database queries made during each request.

### What It Does

1. Counts queries per request
2. Records query duration
3. Identifies operation type (SELECT, INSERT, etc.)
4. Extracts table name
5. Adds query count header

### Configuration

Requires `DEBUG=True` in settings (uses Django's query logging).

```python
DEBUG = True  # Required for query tracking

DJANGO_MATT_METRICS = {
    "ENABLED": True,
}
```

### Metrics Collected

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `{prefix}_db_queries_total` | Counter | operation, table | Total queries |
| `{prefix}_db_query_duration_seconds` | Histogram | operation, table | Query duration |

### Operations Tracked

- SELECT
- INSERT
- UPDATE
- DELETE
- OTHER (for other SQL statements)

### Response Headers

| Header | Description |
|--------|-------------|
| `X-DB-Query-Count` | Number of queries executed |

## ObservabilityMiddleware

Combined middleware that chains all observability middleware together.

### What It Does

Applies middleware in this order:
1. LoggingMiddleware (innermost)
2. MetricsMiddleware
3. TracingMiddleware (outermost)

### Usage

```python
MIDDLEWARE = [
    # ... other middleware ...
    'django_matt.observability.ObservabilityMiddleware',
]
```

Equivalent to:
```python
MIDDLEWARE = [
    'django_matt.observability.TracingMiddleware',
    'django_matt.observability.MetricsMiddleware',
    'django_matt.observability.LoggingMiddleware',
]
```

## Middleware Order

The order of observability middleware matters:

```python
MIDDLEWARE = [
    # Security middleware first
    'django.middleware.security.SecurityMiddleware',

    # Session and CSRF
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',

    # Authentication
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    # Observability AFTER auth (so user is available)
    'django_matt.observability.TracingMiddleware',   # Creates trace
    'django_matt.observability.MetricsMiddleware',   # Records metrics
    'django_matt.observability.LoggingMiddleware',   # Logs request

    # Your custom middleware
    'myapp.middleware.CustomMiddleware',
]
```

## Response Headers Summary

All response headers added by observability middleware:

| Header | Middleware | Description |
|--------|------------|-------------|
| `X-Correlation-ID` | Tracing, Logging | Distributed tracing correlation ID |
| `X-Trace-ID` | Tracing | OpenTelemetry trace ID |
| `X-Request-ID` | Logging | Unique request identifier |
| `X-Response-Time` | Metrics | Request duration |
| `X-DB-Query-Count` | Database | Number of DB queries |

## Disabling Middleware

### Via Configuration

```python
# Disable individual features
DJANGO_MATT_TRACING = {"ENABLED": False}
DJANGO_MATT_METRICS = {"ENABLED": False}
DJANGO_MATT_LOGGING = {"ENABLED": False}
```

### Conditional Loading

```python
# settings.py
import os

MIDDLEWARE = [
    # ... base middleware ...
]

# Only add observability in production
if os.environ.get("ENABLE_OBSERVABILITY", "true").lower() == "true":
    MIDDLEWARE += [
        'django_matt.observability.TracingMiddleware',
        'django_matt.observability.MetricsMiddleware',
        'django_matt.observability.LoggingMiddleware',
    ]
```

## Testing

Disable middleware in tests:

```python
# conftest.py
@pytest.fixture(autouse=True)
def disable_observability(settings):
    settings.DJANGO_MATT_TRACING = {"ENABLED": False}
    settings.DJANGO_MATT_METRICS = {"ENABLED": False}
```

Or remove middleware entirely:

```python
@pytest.fixture(autouse=True)
def minimal_middleware(settings):
    settings.MIDDLEWARE = [
        'django.middleware.common.CommonMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
    ]
```

## Performance Impact

Middleware performance characteristics:

| Middleware | Typical Overhead | Notes |
|------------|-----------------|-------|
| TracingMiddleware | ~0.1-0.5ms | Depends on exporter |
| MetricsMiddleware | ~0.05ms | Very lightweight |
| LoggingMiddleware | ~0.1ms | Depends on log destination |
| DatabaseQueryMiddleware | ~0.1ms per query | Only in DEBUG mode |

### Optimization Tips

1. **Sample traces in production** - Use `SAMPLE_RATE < 1.0`
2. **Exclude static paths** - Configure `EXCLUDE_PATHS`
3. **Use async exporters** - BatchSpanProcessor for tracing
4. **Buffer logs** - Use async log handlers in production
