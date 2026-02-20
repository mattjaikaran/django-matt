# Fly.io Deployment

Deploy django-matt applications to Fly.io with automatic configuration generation, global edge deployment, and managed services.

## Overview

Fly.io is a platform for running applications close to users worldwide. It provides:

- **Global Edge Network** - Deploy to 30+ regions
- **Automatic SSL** - Free TLS certificates
- **Managed Postgres** - Highly available PostgreSQL
- **Upstash Redis** - Serverless Redis
- **Auto-scaling** - Scale to zero or scale up

## Prerequisites

1. **Fly.io Account** - Sign up at [fly.io](https://fly.io)
2. **flyctl CLI** - Install the Fly.io command-line tool

### Install flyctl

=== "macOS (Homebrew)"
    ```bash
    brew install flyctl
    ```

=== "Linux"
    ```bash
    curl -L https://fly.io/install.sh | sh
    ```

=== "Windows"
    ```powershell
    powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
    ```

### Authenticate

```bash
flyctl auth login
```

## Quick Start

### Using django-matt Deploy Module

```python
from django_matt.deploy import DeploymentConfig, FlyioProvider

# Configure deployment
config = DeploymentConfig(
    app_name="myapp",
    django_settings_module="config.settings",
    python_version="3.13",
    port=8000,
    workers=4,
    create_database=True,
    create_redis=True,
    health_check_path="/health/",
)

# Initialize provider
provider = FlyioProvider(config)

# Validate configuration
errors = provider.validate()
if errors:
    print("Validation errors:", errors)

# Generate configuration files
files = provider.generate_config()
for filename, content in files.items():
    with open(filename, "w") as f:
        f.write(content)
    print(f"Generated: {filename}")

# Deploy (async)
import asyncio
result = asyncio.run(provider.deploy())
print(f"Status: {result.status}")
print(f"URL: {result.url}")
```

## Generated Configuration Files

### fly.toml

The main Fly.io configuration file:

```toml
app = "myapp"
primary_region = "iad"

[build]

[env]
PORT = "8000"
DJANGO_SETTINGS_MODULE = "config.settings"
DJANGO_ENV = "production"

[http_service]
internal_port = 8000
force_https = true
auto_stop_machines = true
auto_start_machines = true
min_machines_running = 1
processes = ["app"]

[http_service.concurrency]
type = "connections"
hard_limit = 100
soft_limit = 80

[checks.health]
type = "http"
path = "/health/"
interval = "30s"
timeout = "5s"
grace_period = "10s"

[deploy]
release_command = "sh release.sh"

[[mounts]]
source = "media_data"
destination = "/app/media"
```

### Dockerfile

```dockerfile
# Dockerfile for Fly.io deployment
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Run gunicorn
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --worker-class uvicorn.workers.UvicornWorker"]
```

### release.sh

Executed before each deployment:

```bash
#!/bin/sh
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Release complete!"
```

## Step-by-Step Deployment

### 1. Create the Application

```bash
# Create a new Fly app
flyctl apps create myapp

# Or let Fly choose a unique name
flyctl apps create
```

### 2. Provision PostgreSQL Database

```bash
# Create a PostgreSQL cluster
flyctl postgres create --name myapp-db \
    --region iad \
    --vm-size shared-cpu-1x \
    --volume-size 1

# Attach to your app (sets DATABASE_URL automatically)
flyctl postgres attach myapp-db --app myapp
```

!!! tip "Database Regions"
    Create the database in the same region as your app for lowest latency.

### 3. Provision Redis (Optional)

```bash
# Create Upstash Redis
flyctl redis create --name myapp-redis --region iad

# Or use Fly's built-in Redis
flyctl redis create
```

### 4. Set Secrets

```bash
# Set required secrets
flyctl secrets set \
    SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" \
    ALLOWED_HOSTS="myapp.fly.dev" \
    --app myapp

# Set additional secrets if needed
flyctl secrets set \
    SENTRY_DSN="https://xxx@sentry.io/xxx" \
    AWS_ACCESS_KEY_ID="xxx" \
    AWS_SECRET_ACCESS_KEY="xxx" \
    --app myapp
```

### 5. Create Persistent Volume (for Media Files)

```bash
# Create volume for media files (if not using S3)
flyctl volumes create media_data --size 1 --region iad --app myapp
```

### 6. Deploy

```bash
# Deploy the application
flyctl deploy

# Or deploy with specific image
flyctl deploy --image myregistry/myapp:latest
```

## Configuration Options

### Multiple Regions

Deploy to multiple regions for global availability:

```toml
# fly.toml
primary_region = "iad"

# Specify additional regions
[http_service]
processes = ["app"]
regions = ["iad", "lhr", "sin", "syd"]
```

```bash
# Scale to multiple regions
flyctl scale count 2 --region iad
flyctl scale count 2 --region lhr
flyctl scale count 1 --region sin
```

### Auto-Scaling

Configure auto-scaling based on connections:

```toml
[http_service]
auto_stop_machines = true
auto_start_machines = true
min_machines_running = 1

[http_service.concurrency]
type = "connections"
hard_limit = 100
soft_limit = 80
```

### Machine Sizing

```bash
# View available machine sizes
flyctl platform vm-sizes

# Scale machine size
flyctl scale vm shared-cpu-2x --app myapp

# Scale memory
flyctl scale memory 512 --app myapp
```

### Celery Workers

Run Celery workers as separate processes:

```toml
# fly.toml
[processes]
app = "gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4"
worker = "celery -A config worker -l info"
beat = "celery -A config beat -l info"
```

```bash
# Scale processes independently
flyctl scale count app=2 worker=4 beat=1
```

## Operations

### View Logs

```bash
# Stream logs
flyctl logs

# View recent logs
flyctl logs --app myapp

# Filter by instance
flyctl logs --instance abc123
```

### SSH into Instance

```bash
# SSH into running instance
flyctl ssh console

# Run a command
flyctl ssh console -C "python manage.py shell"

# Run migrations manually
flyctl ssh console -C "python manage.py migrate"
```

### Database Operations

```bash
# Connect to PostgreSQL
flyctl postgres connect -a myapp-db

# Proxy database locally
flyctl proxy 5432 -a myapp-db

# Then connect locally
psql postgres://postgres:password@localhost:5432/myapp
```

### Scaling

```bash
# Scale instances
flyctl scale count 3 --app myapp

# Scale to zero (saves money)
flyctl scale count 0 --app myapp

# View current scale
flyctl scale show --app myapp
```

### Rollback

```python
from django_matt.deploy import DeploymentConfig, FlyioProvider
import asyncio

config = DeploymentConfig(app_name="myapp", django_settings_module="config.settings")
provider = FlyioProvider(config)

# Get previous deployment
result = asyncio.run(provider.rollback("deployment-id"))
print(f"Rolled back: {result.status}")
```

Or via CLI:

```bash
# List releases
flyctl releases --app myapp

# Rollback to previous
flyctl deploy --image <previous-image-ref>
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Auto (via attach) |
| `REDIS_URL` | Redis connection string | No |
| `ALLOWED_HOSTS` | Comma-separated hosts | Yes |
| `DJANGO_SETTINGS_MODULE` | Settings module path | Yes |
| `DJANGO_ENV` | Environment name | Yes |
| `DEBUG` | Debug mode (false for production) | Yes |
| `SENTRY_DSN` | Sentry error tracking | No |

## Monitoring

### Fly.io Dashboard

Access metrics and logs at [fly.io/dashboard](https://fly.io/dashboard).

### Prometheus Metrics

```bash
# Enable metrics
flyctl metrics
```

### Health Checks

```toml
# fly.toml
[checks.health]
type = "http"
path = "/health/"
interval = "30s"
timeout = "5s"
grace_period = "10s"
```

## Cost Optimization

### Scale to Zero

```toml
[http_service]
auto_stop_machines = true
auto_start_machines = true
min_machines_running = 0
```

!!! note "Cold Starts"
    With `min_machines_running = 0`, expect ~2-3 second cold starts.

### Use Shared CPUs

```bash
# Use shared CPU for development/staging
flyctl scale vm shared-cpu-1x

# Use dedicated CPU for production
flyctl scale vm dedicated-cpu-1x
```

### Choose Appropriate Regions

Deploy only to regions where you have users:

```bash
# Check latency from different regions
flyctl ping
```

## Troubleshooting

### Deployment Fails

```bash
# Check build logs
flyctl logs --app myapp

# Check deployment status
flyctl status --app myapp

# SSH and check manually
flyctl ssh console
```

### Database Connection Issues

```bash
# Verify DATABASE_URL is set
flyctl secrets list --app myapp

# Check database status
flyctl status --app myapp-db

# Test connection
flyctl ssh console -C "python manage.py dbshell"
```

### Out of Memory

```bash
# Increase memory
flyctl scale memory 1024 --app myapp

# Or use a larger VM
flyctl scale vm shared-cpu-2x --app myapp
```

### Health Check Failures

```bash
# Check health endpoint
curl https://myapp.fly.dev/health/

# View health check logs
flyctl logs --app myapp | grep health
```

## Complete Example

```python
# deploy_fly.py
import asyncio
from django_matt.deploy import DeploymentConfig, FlyioProvider

async def deploy():
    config = DeploymentConfig(
        app_name="myapp",
        django_settings_module="config.settings",
        python_version="3.13",
        port=8000,
        workers=4,
        worker_class="uvicorn.workers.UvicornWorker",
        create_database=True,
        create_redis=True,
        environment="production",
        debug=False,
        allowed_hosts=["myapp.fly.dev"],
        health_check_path="/health/",
        health_check_interval=30,
        min_instances=1,
        max_instances=5,
        auto_scale=True,
    )

    provider = FlyioProvider(config)

    # Validate
    errors = provider.validate()
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        return

    # Generate and deploy
    result = await provider.deploy()

    print(f"Status: {result.status}")
    print(f"URL: {result.url}")

    for log in result.logs:
        print(f"  {log}")

    if result.errors:
        print("Errors:")
        for error in result.errors:
            print(f"  - {error}")

if __name__ == "__main__":
    asyncio.run(deploy())
```

## Related Documentation

- [Docker Deployment](./docker.md)
- [Production Checklist](./production-checklist.md)
- [Environment Variables](./environment-variables.md)
- [Fly.io Documentation](https://fly.io/docs/)
