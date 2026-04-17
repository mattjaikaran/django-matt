# Request Inspector

Development tool that captures HTTP requests and responses for debugging. Includes a lightweight toolbar, SQL query tracking, N+1 detection, and request/response body inspection.

## Quick Start

```python
# settings.py
MIDDLEWARE = [
    "django_matt.inspector.middleware.RequestCaptureMiddleware",
    "django_matt.inspector.toolbar.ToolbarMiddleware",
    ...
]

DJANGO_MATT_INSPECTOR = {
    "ENABLED": DEBUG,
    "TOOLBAR": True,
}
```

## Configuration

```python
# settings.py
DJANGO_MATT_INSPECTOR = {
    "ENABLED": DEBUG,                # Enable capture (default: DEBUG)
    "TOOLBAR": True,                 # Show dev toolbar on HTML pages
    "MAX_BODY_SIZE": 65536,          # Max request/response body to capture (bytes)
    "IGNORE_PATHS": [                # Paths to skip
        "/_matt/",
        "/static/",
        "/media/",
    ],
    "IGNORE_EXTENSIONS": [           # File extensions to skip
        ".css", ".js", ".png", ".jpg", ".gif",
        ".ico", ".woff", ".woff2", ".svg",
    ],
    "CAPTURE_HEADERS": True,         # Capture request/response headers
    "CAPTURE_BODY": True,            # Capture request/response bodies
    "CAPTURE_RESPONSE": True,        # Capture response data
}
```

## Key Features

### RequestCaptureMiddleware

Captures every request/response pair into a `CapturedRequest` dataclass:

```python
MIDDLEWARE = ["django_matt.inspector.middleware.RequestCaptureMiddleware"]
```

Captured data includes:
- Request: method, path, full URL, query string, headers, body, content type
- Response: status code, headers, body, content type
- Timing: duration in milliseconds
- User: user ID and email (if authenticated)
- SQL: query count, total query time, individual queries
- Errors: exception message and traceback (if any)
- N+1 warnings: detected N+1 query patterns

The middleware skips requests matching `IGNORE_PATHS` or `IGNORE_EXTENSIONS`.

### ToolbarMiddleware

Injects a collapsible panel at the bottom of HTML pages showing request metrics:

```python
MIDDLEWARE = ["django_matt.inspector.toolbar.ToolbarMiddleware"]
```

The toolbar displays:
- Request timing (total duration)
- SQL query count and total time
- Cache hit/miss stats
- N+1 query warnings
- Response status code

Only active when `DEBUG=True` and `DJANGO_MATT_INSPECTOR.TOOLBAR=True`. Dismiss with the toggle button.

### CapturedRequest

The dataclass storing captured request/response data:

```python
from django_matt.inspector.storage import CapturedRequest

# Fields
request = CapturedRequest(
    id="uuid",
    timestamp=1234567890.0,
    method="GET",
    path="/api/users/",
    full_url="http://localhost:8000/api/users/",
    query_string="page=1",
    request_headers={"Accept": "application/json"},
    request_body=None,
    request_content_type="application/json",
    response_status=200,
    response_headers={"Content-Type": "application/json"},
    response_body='[{"id": 1, "name": "Alice"}]',
    response_content_type="application/json",
    duration_ms=45.2,
    client_ip="127.0.0.1",
    user_id=1,
    user_email="admin@example.com",
    exception=None,
    traceback=None,
    db_queries=[{"sql": "SELECT ...", "time": 0.001}],
    db_query_count=3,
    db_query_time_ms=12.5,
    n_plus_one_warnings=[],
)

# Serialize
data = request.to_dict()

# Deserialize
request = CapturedRequest.from_dict(data)
```

### Storage Backends

Captured requests are stored via pluggable backends:

```python
from django_matt.inspector.storage import get_storage

storage = get_storage()

# Store a captured request
storage.store(captured_request)

# Retrieve recent requests
recent = storage.get_recent(limit=50)

# Get by ID
request = storage.get(request_id)

# Clear all
storage.clear()
```

**InMemoryStorage** (default): Uses a thread-safe deque with configurable max size. Data is lost on restart.

**RedisStorage**: Persists captured requests in Redis for cross-process access.

### Inspector Views and Controllers

Browse captured requests via a web interface:

```python
# urls.py
from django_matt.inspector.urls import urlpatterns as inspector_urls

urlpatterns = [
    path("_matt/inspector/", include(inspector_urls)),
]
```

### Export

Export captured requests for analysis:

```python
from django_matt.inspector.export import export_har, export_json

# Export as HAR (HTTP Archive) format
har_data = export_har(captured_requests)

# Export as JSON
json_data = export_json(captured_requests)
```

### Admin Integration

```python
# Auto-registered when django_matt is in INSTALLED_APPS
# Provides admin views for browsing captured requests
```

## Practical Example

Debug slow API endpoints:

```python
# settings.py
MIDDLEWARE = [
    "django_matt.inspector.middleware.RequestCaptureMiddleware",
    "django_matt.inspector.toolbar.ToolbarMiddleware",
    ...
]

DJANGO_MATT_INSPECTOR = {
    "ENABLED": True,
    "TOOLBAR": True,
    "MAX_BODY_SIZE": 131072,  # 128KB
    "IGNORE_PATHS": ["/static/", "/media/", "/health/"],
}
```

```python
# urls.py
from django_matt.inspector.urls import urlpatterns as inspector_urls

urlpatterns = [
    ...
    path("_matt/inspector/", include(inspector_urls)),
]
```

Visit `/_matt/inspector/` to browse captured requests with:
- Request/response headers and bodies
- SQL queries with timing
- N+1 query detection warnings
- Exception tracebacks
- Duration breakdown

The toolbar at the bottom of every HTML page gives at-a-glance metrics. Click to expand for details.
