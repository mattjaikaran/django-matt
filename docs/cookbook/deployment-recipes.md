# Deployment Recipes

Docker, Kubernetes, Fly.io, health checks, connection pooling, and background tasks.

## Docker + docker-compose Setup

```dockerfile
# Dockerfile
FROM python:3.13-slim AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# Copy app
COPY . .
RUN uv run python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["uv", "run", "gunicorn", "config.asgi:application", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "4"]
```

```yaml
# docker-compose.yml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgres://app:secret@db:5432/app
      - REDIS_URL=redis://redis:6379/0
      - DJANGO_SETTINGS_MODULE=config.settings.production
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 10s
      timeout: 5s

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

## Fly.io Deploy with Secrets

```toml
# fly.toml
app = "myapp"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

  [http_service.concurrency]
    type = "requests"
    hard_limit = 250
    soft_limit = 200

[[services.http_checks]]
  interval = 10000
  grace_period = "10s"
  method = "GET"
  path = "/health"
  timeout = 2000

[checks]
  [checks.readiness]
    type = "http"
    port = 8000
    path = "/ready"
    interval = "15s"
    timeout = "5s"
    method = "GET"

[env]
  DJANGO_SETTINGS_MODULE = "config.settings.production"
```

```bash
# Set secrets (never commit these)
fly secrets set DATABASE_URL="postgres://..." SECRET_KEY="..." REDIS_URL="redis://..."

# Deploy
fly deploy

# Scale
fly scale count 3 --region iad,ord
```

## Health Checks for Kubernetes Probes

```python
# settings.py
MIDDLEWARE = [
    ...
    "django_matt.observability.ObservabilityMiddleware",
]

# urls.py
from django_matt.observability import observability_urlpatterns

urlpatterns = [
    path("", include(observability_urlpatterns)),
    # Provides:
    #   /health  — liveness probe (always returns 200 if process is alive)
    #   /ready   — readiness probe (checks DB, cache, custom checks)
]

# Register custom readiness checks
from django_matt.observability import readiness_checker

def check_migrations():
    from django.core.management import call_command
    from io import StringIO
    out = StringIO()
    call_command("showmigrations", "--plan", stdout=out)
    pending = [l for l in out.getvalue().splitlines() if l.strip().startswith("[ ]")]
    if pending:
        return (False, f"{len(pending)} pending migrations")
    return (True, "All migrations applied")

readiness_checker.register("migrations", check_migrations)
```

```yaml
# k8s deployment snippet
spec:
  containers:
    - name: web
      livenessProbe:
        httpGet:
          path: /health
          port: 8000
        initialDelaySeconds: 5
        periodSeconds: 10
      readinessProbe:
        httpGet:
          path: /ready
          port: 8000
        initialDelaySeconds: 10
        periodSeconds: 15
      startupProbe:
        httpGet:
          path: /health
          port: 8000
        failureThreshold: 30
        periodSeconds: 2
```

## Kubernetes Manifest Generation

```python
from django_matt.deployment import (
    KubernetesConfig,
    KubernetesManifestGenerator,
    ServiceType,
    IngressClass,
    generate_helm_chart,
)

# Generate full Kubernetes manifests
config = KubernetesConfig(
    app_name="myapp",
    namespace="production",
    image="ghcr.io/myorg/myapp",
    image_tag="v1.2.3",
    replicas=3,
    port=8000,
    health_check_path="/health",
    readiness_path="/ready",
    cpu_request="200m",
    cpu_limit="1000m",
    memory_request="256Mi",
    memory_limit="1Gi",
    hpa_enabled=True,
    hpa_min_replicas=3,
    hpa_max_replicas=20,
    ingress_enabled=True,
    ingress_class=IngressClass.NGINX,
    ingress_host="api.myapp.com",
    ingress_tls_enabled=True,
    env_vars={
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
    },
)

generator = KubernetesManifestGenerator(config)
manifests = generator.generate_all()

# Or generate a Helm chart
generate_helm_chart("myapp", output_dir="./charts")
```

## Environment-Specific Config with Namespaces

```python
# config/settings/base.py — shared settings
from django_matt.secrets import secret

SECRET_KEY = secret("SECRET_KEY")
DATABASE_URL = secret("DATABASE_URL")

DJANGO_MATT = {
    "SLIM_MODE": {"mode": "auto"},
}


# config/settings/development.py
from .base import *

DEBUG = True
DJANGO_MATT["SLIM_MODE"]["mode"] = "full"


# config/settings/staging.py
from .base import *

DEBUG = False
DJANGO_MATT_OBSERVABILITY = {
    "ENABLED": True,
    "EXPORTERS": [{"type": "json"}],
}


# config/settings/production.py
from .base import *

DEBUG = False
DJANGO_MATT_OBSERVABILITY = {
    "ENABLED": True,
    "SERVICE_NAME": "myapp",
    "EXPORTERS": [
        {"type": "opentelemetry", "service_name": "myapp"},
        {"type": "prometheus"},
    ],
}

# Select via DJANGO_SETTINGS_MODULE env var
# DJANGO_SETTINGS_MODULE=config.settings.production
```

## Connection Pooling for Production

```python
# settings.py — psycopg3 connection pooling (enabled by default in production)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myapp",
        "USER": "myapp",
        "PASSWORD": secret("DB_PASSWORD"),
        "HOST": "db.internal",
        "PORT": "5432",
        "OPTIONS": {
            "pool": {
                "min_size": 5,
                "max_size": 20,
                "timeout": 30,
            },
        },
        # Or use pgbouncer
        # "HOST": "pgbouncer.internal",
        # "PORT": "6432",
        # "OPTIONS": {
        #     "options": "-c search_path=public",
        # },
    },
}

# For ASGI with gunicorn + uvicorn workers:
# gunicorn config.asgi:application \
#   --worker-class uvicorn.workers.UvicornWorker \
#   --workers 4 \
#   --bind 0.0.0.0:8000
```

## Background Task Setup

```python
# Using Django-Q2 (recommended for simple setups)
# settings.py
Q_CLUSTER = {
    "name": "myapp",
    "workers": 4,
    "recycle": 500,
    "timeout": 60,
    "redis": {
        "host": "redis",
        "port": 6379,
        "db": 0,
    },
}

# tasks.py
from django_q.tasks import async_task, schedule


async def send_report(user_id: int):
    user = await User.objects.aget(pk=user_id)
    report = await generate_report(user)
    await email_service.send(to=user.email, template="report", context=report)


# Enqueue a one-off task
async_task("myapp.tasks.send_report", user_id=42)

# Schedule a recurring task
schedule(
    "myapp.tasks.send_report",
    user_id=42,
    schedule_type="C",  # cron
    cron="0 8 * * 1",   # every Monday at 8am
)
```

```bash
# Run the task worker alongside your web process
uv run python manage.py qcluster
```

## ASGI Production Config

```python
# config/asgi.py
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_asgi_application()

# Optional: set up observability at startup
from django_matt.observability import setup_observability
setup_observability(auto=True)
```

```bash
# Production command
gunicorn config.asgi:application \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile - \
  --timeout 120 \
  --graceful-timeout 30
```
