# Production Readiness Checklist

A comprehensive checklist for deploying django-matt applications to production. Work through each section before your first production deploy.

---

## Security

- [ ] **Django SECRET_KEY** is unique, random, and loaded from a secrets backend -- never committed to source control
- [ ] **DEBUG = False** in production settings
- [ ] **ALLOWED_HOSTS** is set to your exact domain(s)
- [ ] **CORS configured** with explicit origins (never `True` / `"*"` in production)

```python
from django_matt.config import configure

configure(
    environment="production",
    cors=["https://app.example.com", "https://admin.example.com"],
    middleware="production",  # enables security headers, request ID, CORS, logging, timing
)
```

- [ ] **Secrets backend** configured -- use `EncryptedFileBackend`, `VaultBackend`, or a cloud provider instead of env vars for sensitive values

```python
from django_matt.secrets.backends import VaultBackend

secrets = VaultBackend(
    url="https://vault.internal:8200",
    token=os.environ["VAULT_TOKEN"],
    mount_point="secret",
    path_prefix="myapp/",
)
db_password = await secrets.get("DATABASE_PASSWORD")
```

- [ ] **Rate limiting** enabled on public endpoints

```python
from django_matt.throttling import throttle, AnonRateThrottle

@api.get("/public")
@throttle(AnonRateThrottle, rate="60/minute")
async def public_endpoint(request):
    ...
```

- [ ] **CSP headers** configured via the `SecurityHeadersMiddleware` (auto-enabled with `middleware="production"`)
- [ ] **HTTPS enforced** -- `SECURE_SSL_REDIRECT = True`, `SECURE_HSTS_SECONDS` set
- [ ] **CSRF protection** enabled for session-based auth (default in Django, verify not disabled)
- [ ] **Admin panel** behind VPN or IP allowlist

---

## Performance

- [ ] **Connection pooling** enabled for PostgreSQL

```python
configure(
    database="postgresql",  # auto-enables pool: min_size=2, max_size=10
)

# Or configure explicitly:
DJANGO_MATT = {
    "CONNECTION_POOL": {
        "ENABLED": True,
        "MIN_SIZE": 5,
        "MAX_SIZE": 20,
    },
}
```

- [ ] **Caching** configured with Redis

```python
configure(cache="redis")

# Use CacheManager for view-level caching
from django_matt.utils.performance import CacheManager

cache = CacheManager()
cache.set("user:123", user_data, timeout=300)
```

- [ ] **Slim mode** evaluated -- use `"slim"` or `"auto"` mode if you only need a subset of modules

```python
DJANGO_MATT = {
    "SLIM_MODE": {
        "mode": "auto",         # detect from settings which modules to load
        "lazy_imports": True,   # defer heavy imports until first use
    },
}
```

- [ ] **Rust extensions** installed for hot paths (if available)

```python
from django_matt._accel import HAS_RUST

# When HAS_RUST is True, the following are accelerated:
# - JWT encode/decode/verify
# - URL routing (RadixRouter)
# - JSON serialization (serialize_dicts_to_json)
# - Query string parsing
# - Header parsing
# - camelCase mapping
```

- [ ] **orjson** is used everywhere (it is a base dependency, always available)
- [ ] **Static files** served by a CDN or whitenoise, not Django in production

---

## Observability

- [ ] **Tracing** enabled with an exporter (Jaeger, OTLP, Datadog, etc.)

```python
DJANGO_MATT_TRACING = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTER": "otlp",
    "ENDPOINT": "http://otel-collector:4317",
    "SAMPLE_RATE": 0.1,  # sample 10% of requests in production
}
```

- [ ] **Metrics** enabled with Prometheus or compatible backend

```python
DJANGO_MATT_METRICS = {
    "ENABLED": True,
    "PREFIX": "myapp",
    "DEFAULT_BUCKETS": [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
}
```

- [ ] **Structured logging** in JSON format

```python
from django_matt.observability import get_logging_config

LOGGING = get_logging_config(format="json", level="INFO")
```

- [ ] **Health check endpoints** registered

```python
from django_matt.observability import observability_urlpatterns

urlpatterns = [
    path("", include(observability_urlpatterns)),
    # Exposes:
    #   /health/   -- liveness probe
    #   /ready/    -- readiness probe (checks DB, cache, etc.)
    #   /metrics/  -- Prometheus metrics
    #   /info/     -- app version and runtime info
]
```

- [ ] **Middleware stack** includes observability middleware

```python
MIDDLEWARE = [
    "django_matt.observability.ObservabilityMiddleware",  # combined tracing+metrics+logging
    # ...
]
```

- [ ] **Request correlation IDs** propagated via `RequestIDMiddleware` (auto-enabled with `middleware="production"`)

---

## Database

- [ ] **Migrations** run and verified on a staging environment first
- [ ] **Connection limits** match your pool size and worker count. Rule of thumb: `max_connections >= (pool_max_size * num_workers) + headroom`
- [ ] **Statement timeout** configured to prevent runaway queries

```sql
-- In PostgreSQL:
ALTER ROLE myapp_user SET statement_timeout = '30s';
```

- [ ] **Indexes** verified for common query patterns -- use `django_matt.observability.DatabaseQueryMiddleware` to find slow queries
- [ ] **Read replicas** configured if read-heavy workload warrants it
- [ ] **Backups** automated and tested with restore drills

---

## Authentication

- [ ] **JWT access token lifetime** is short (15 minutes default is good)

```python
from datetime import timedelta

DJANGO_MATT_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
}
```

- [ ] **Refresh token rotation** enabled (`ROTATE_REFRESH_TOKENS: True`)
- [ ] **Token blacklisting** enabled after rotation
- [ ] **API keys** scoped to specific permissions, not global access
- [ ] **Asymmetric JWT** considered for microservices (RS256/ES256 with `SIGNING_KEY` / `VERIFYING_KEY`)
- [ ] **Auth header** is `Authorization: Bearer <token>` (default)

---

## Error Handling

- [ ] **Exception filters** registered for known error types

```python
from django_matt.exceptions.filters import ExceptionFilter
from django_matt.exceptions.decorators import register_global_filter

class PaymentErrorFilter(ExceptionFilter):
    exception_types = (PaymentError,)
    order = 10

    async def catch(self, exc, request):
        return JsonResponse(
            {"error": "payment_failed", "detail": str(exc)},
            status=402,
        )

register_global_filter(PaymentErrorFilter())
```

- [ ] **No raw exception details** leak to clients in production -- the `ExceptionFilterChain` handles this
- [ ] **Error reporting** integrated (Sentry, Datadog, etc.) via interceptors or middleware
- [ ] **Structured error responses** -- all errors return consistent JSON shape

---

## Deployment

- [ ] **ASGI server** configured (uvicorn via gunicorn)

```bash
gunicorn config.asgi:application \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --graceful-timeout 30
```

- [ ] **Health probes** configured in orchestrator (Kubernetes, Fly.io, etc.)

```yaml
# Kubernetes example
livenessProbe:
  httpGet:
    path: /health/
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

- [ ] **Graceful shutdown** -- gunicorn `--graceful-timeout` allows in-flight requests to complete
- [ ] **Docker image** is minimal (multi-stage build, no dev dependencies)

```dockerfile
FROM python:3.13-slim AS base
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
CMD ["gunicorn", "config.asgi:application", "--worker-class", "uvicorn.workers.UvicornWorker"]
```

- [ ] **Environment variables** injected at runtime, not baked into the image
- [ ] **Log output** goes to stdout/stderr (not files) for container log collection
- [ ] **Resource limits** set (memory, CPU) to prevent noisy-neighbor issues
- [ ] **Rollback plan** documented -- know how to revert to the previous version

---

## Pre-Deploy Smoke Test

```bash
# Run full test suite
uv run pytest tests/ -x -q

# Check for lint issues
uv run ruff check django_matt/

# Verify config
python manage.py matt doctor

# Review routes
python manage.py matt routes

# Dry-run migrations
python manage.py migrate --check
```
