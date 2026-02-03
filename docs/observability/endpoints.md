# Observability Endpoints

Django Matt provides HTTP endpoints for metrics exposure, health checks, and debugging.

## Available Endpoints

| Endpoint | Description | Use Case |
|----------|-------------|----------|
| `/_matt/metrics` | Prometheus metrics | Metrics scraping |
| `/_matt/info` | Application info | Diagnostics |
| `/_matt/debug` | Debug information | Development |
| `/health` | Liveness check | Kubernetes liveness probe |
| `/ready` | Readiness check | Kubernetes readiness probe |

## Quick Setup

### Include All Endpoints

```python
# urls.py
from django.urls import path, include
from django_matt.observability import observability_urlpatterns

urlpatterns = [
    # Your routes...
    path("", include(observability_urlpatterns)),
]
```

### Include Specific Endpoints

```python
# urls.py
from django_matt.observability import (
    metrics_view,
    health_view,
    ready_view,
    info_view,
    debug_view,
)

urlpatterns = [
    path("_matt/metrics", metrics_view, name="metrics"),
    path("health", health_view, name="health"),
    path("ready", ready_view, name="ready"),
    path("_matt/info", info_view, name="info"),
    path("_matt/debug", debug_view, name="debug"),
]
```

## /_matt/metrics

Prometheus metrics endpoint.

### Response Format

```
# HELP myapp_http_requests_total Total HTTP requests
# TYPE myapp_http_requests_total counter
myapp_http_requests_total{method="GET",endpoint="/api/users",status="200"} 1523.0
myapp_http_requests_total{method="POST",endpoint="/api/orders",status="201"} 456.0
myapp_http_requests_total{method="GET",endpoint="/api/orders",status="500"} 12.0

# HELP myapp_http_request_duration_seconds HTTP request latency in seconds
# TYPE myapp_http_request_duration_seconds histogram
myapp_http_request_duration_seconds_bucket{method="GET",endpoint="/api/users",status="200",le="0.005"} 120.0
myapp_http_request_duration_seconds_bucket{method="GET",endpoint="/api/users",status="200",le="0.01"} 450.0
myapp_http_request_duration_seconds_bucket{method="GET",endpoint="/api/users",status="200",le="0.025"} 890.0
...

# HELP myapp_http_requests_active Currently active HTTP requests
# TYPE myapp_http_requests_active gauge
myapp_http_requests_active{method="GET",endpoint="/api/users"} 5.0
```

### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'django-app'
    scrape_interval: 15s
    metrics_path: '/_matt/metrics'
    static_configs:
      - targets: ['app:8000']
```

### Kubernetes ServiceMonitor

```yaml
# servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: django-app
spec:
  selector:
    matchLabels:
      app: django-app
  endpoints:
    - port: http
      path: /_matt/metrics
      interval: 30s
```

## /health

Simple liveness check for Kubernetes liveness probes.

### Response

```json
{
  "status": "healthy",
  "timestamp": 1705315800.123
}
```

**Status Code:** Always `200 OK`

### Kubernetes Liveness Probe

```yaml
# deployment.yaml
spec:
  containers:
    - name: app
      livenessProbe:
        httpGet:
          path: /health
          port: 8000
        initialDelaySeconds: 10
        periodSeconds: 10
        timeoutSeconds: 5
        failureThreshold: 3
```

### Usage

```bash
curl http://localhost:8000/health
# {"status": "healthy", "timestamp": 1705315800.123}
```

## /ready

Readiness check with configurable health checks.

### Response (Healthy)

```json
{
  "ready": true,
  "checks": {
    "database": {
      "ready": true,
      "message": "Database connected"
    },
    "cache": {
      "ready": true,
      "message": "Cache connected"
    }
  },
  "timestamp": 1705315800.123
}
```

**Status Code:** `200 OK`

### Response (Unhealthy)

```json
{
  "ready": false,
  "checks": {
    "database": {
      "ready": false,
      "message": "Database error: Connection refused"
    },
    "cache": {
      "ready": true,
      "message": "Cache connected"
    }
  },
  "timestamp": 1705315800.123
}
```

**Status Code:** `503 Service Unavailable`

### Kubernetes Readiness Probe

```yaml
# deployment.yaml
spec:
  containers:
    - name: app
      readinessProbe:
        httpGet:
          path: /ready
          port: 8000
        initialDelaySeconds: 5
        periodSeconds: 10
        timeoutSeconds: 5
        failureThreshold: 3
```

### Default Checks

Django Matt includes these default checks:

| Check | Default | Description |
|-------|---------|-------------|
| `database` | Enabled | Verifies database connectivity |
| `cache` | Disabled | Verifies cache connectivity |

### Configuration

```python
# settings.py

# Enable/disable default checks
DJANGO_MATT_READINESS_CHECK_DATABASE = True
DJANGO_MATT_READINESS_CHECK_CACHE = False
```

### Custom Readiness Checks

Register custom checks:

```python
# myapp/checks.py
from django_matt.observability import readiness_checker

def check_external_api():
    """Check external API availability."""
    try:
        response = requests.get("https://api.example.com/health", timeout=5)
        if response.status_code == 200:
            return True, "External API healthy"
        return False, f"External API returned {response.status_code}"
    except Exception as e:
        return False, f"External API error: {e}"

def check_message_queue():
    """Check message queue connectivity."""
    try:
        queue.ping()
        return True, "Message queue connected"
    except Exception as e:
        return False, f"Message queue error: {e}"

# Register checks
readiness_checker.register("external_api", check_external_api)
readiness_checker.register("message_queue", check_message_queue)
```

### Register Checks in AppConfig

```python
# myapp/apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = 'myapp'

    def ready(self):
        from django_matt.observability import readiness_checker
        from .checks import check_external_api, check_message_queue

        readiness_checker.register("external_api", check_external_api)
        readiness_checker.register("message_queue", check_message_queue)
```

### Unregister Checks

```python
from django_matt.observability import readiness_checker

# Remove a check
readiness_checker.unregister("external_api")
```

### Run Checks Manually

```python
from django_matt.observability import readiness_checker

# Run all checks
all_ready, results = readiness_checker.run_checks()

if all_ready:
    print("All systems operational")
else:
    for name, result in results.items():
        if not result["ready"]:
            print(f"Check failed: {name} - {result['message']}")
```

## /_matt/info

Application information endpoint.

### Response

```json
{
  "python_version": "3.12.0 (main, Oct 2 2023, 12:00:00) [Clang 14.0.0]",
  "django_version": "5.0",
  "dependencies": {
    "opentelemetry": true,
    "prometheus_client": true,
    "jaeger": false,
    "otlp": true,
    "zipkin": false,
    "datadog": false,
    "newrelic": false
  },
  "service_name": "myapp",
  "app_version": "1.2.3",
  "timestamp": 1705315800.123
}
```

### Configuration

```python
# settings.py

# Application version (shown in info endpoint)
APP_VERSION = "1.2.3"

# Service name from tracing config
DJANGO_MATT_TRACING = {
    "SERVICE_NAME": "myapp",
    # ...
}
```

### Usage

```bash
curl http://localhost:8000/_matt/info | jq .
```

## /_matt/debug

Debug information endpoint (only available when `DEBUG=True`).

### Response

```json
{
  "request": {
    "method": "GET",
    "path": "/_matt/debug",
    "headers": {
      "Host": "localhost:8000",
      "User-Agent": "curl/7.79.1",
      "Accept": "*/*"
    },
    "query_params": {}
  },
  "context": {
    "correlation_id": "abc123-def456",
    "request_id": "req-789",
    "user_id": null
  },
  "settings": {
    "tracing": {
      "ENABLED": true,
      "SERVICE_NAME": "myapp",
      "EXPORTER": "otlp"
    },
    "metrics": {
      "ENABLED": true,
      "PREFIX": "myapp"
    },
    "logging": {
      "ENABLED": true,
      "FORMAT": "json",
      "LEVEL": "INFO"
    }
  },
  "timestamp": 1705315800.123
}
```

### Access Control

The debug endpoint is only accessible when `DEBUG=True`:

```python
# settings.py
DEBUG = True  # Required for /_matt/debug
```

When `DEBUG=False`:
```json
{
  "error": "Debug endpoint only available in DEBUG mode"
}
```
**Status Code:** `403 Forbidden`

### Security Considerations

1. **Never enable DEBUG in production**
2. Consider restricting access via nginx/load balancer:

```nginx
location /_matt/debug {
    deny all;
    return 403;
}
```

## Custom Endpoints

### Custom Health Check View

```python
from django.http import JsonResponse
import time

def custom_health_view(request):
    """Custom health check with additional data."""
    return JsonResponse({
        "status": "healthy",
        "version": "1.2.3",
        "timestamp": time.time(),
        "hostname": socket.gethostname(),
    })
```

### Custom Metrics View

```python
from django.http import HttpResponse
from django_matt.observability import metrics_manager

def custom_metrics_view(request):
    """Custom metrics endpoint with authentication."""
    # Optional: Add authentication
    if not request.user.is_authenticated:
        return HttpResponse("Unauthorized", status=401)

    content = metrics_manager.generate_metrics()
    content_type = metrics_manager.get_content_type()
    return HttpResponse(content, content_type=content_type)
```

### Custom Readiness View

```python
from django.http import JsonResponse
from django_matt.observability import readiness_checker
import time

def custom_ready_view(request):
    """Custom readiness check with verbose output."""
    all_ready, results = readiness_checker.run_checks()

    # Add custom checks
    results["custom"] = {
        "ready": True,
        "message": "Custom check passed",
    }

    response_data = {
        "ready": all_ready,
        "checks": results,
        "timestamp": time.time(),
        "service": "myapp",
        "version": "1.2.3",
    }

    return JsonResponse(
        response_data,
        status=200 if all_ready else 503,
    )
```

## Load Balancer Configuration

### AWS ALB

```yaml
# Target Group health check
HealthCheckPath: /health
HealthCheckProtocol: HTTP
HealthyThresholdCount: 2
UnhealthyThresholdCount: 3
HealthCheckTimeoutSeconds: 5
HealthCheckIntervalSeconds: 30
```

### nginx

```nginx
upstream django {
    server app1:8000;
    server app2:8000;
    server app3:8000;
}

server {
    location /health {
        proxy_pass http://django/health;
        proxy_connect_timeout 5s;
        proxy_read_timeout 5s;
    }

    # Don't expose internal endpoints externally
    location /_matt/ {
        deny all;
        return 403;
    }
}
```

### HAProxy

```
backend django_backend
    option httpchk GET /health
    http-check expect status 200
    server app1 app1:8000 check inter 5000
    server app2 app2:8000 check inter 5000
```

## Docker Compose Health Checks

```yaml
# docker-compose.yml
services:
  app:
    build: .
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## Monitoring Alerts

### Prometheus Alert Rules

```yaml
# alerts.yml
groups:
  - name: django-app
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(myapp_http_errors_total[5m]))
          / sum(rate(myapp_http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is above 5%"

      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            rate(myapp_http_request_duration_seconds_bucket[5m])
          ) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "95th percentile latency is above 1 second"

      - alert: ServiceUnhealthy
        expr: up{job="django-app"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service is down"
          description: "Django app is not responding to health checks"
```
