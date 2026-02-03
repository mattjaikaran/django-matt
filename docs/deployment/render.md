# Render Deployment

Deploy django-matt applications to Render with Blueprint specification, managed databases, and automatic deployments from Git.

## Overview

Render is a unified cloud platform that provides:

- **Blueprint Specification** - Infrastructure as Code via `render.yaml`
- **Managed PostgreSQL** - Automatic backups and scaling
- **Managed Redis** - High-availability caching
- **Auto-Deploy** - Deploy on every Git push
- **Free SSL** - Automatic HTTPS for all services

## Prerequisites

1. **Render Account** - Sign up at [render.com](https://render.com)
2. **GitHub/GitLab Repository** - Render deploys from Git

### Optional: Render CLI

```bash
# Install via npm
npm install -g @render/cli

# Or via pip
pip install render-cli
```

## Quick Start

### Using django-matt Deploy Module

```python
from django_matt.deploy import DeploymentConfig, RenderProvider

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
    auto_scale=True,
    min_instances=1,
    max_instances=5,
)

# Initialize provider
provider = RenderProvider(config)

# Validate configuration
errors = provider.validate()
# Note: RENDER_API_KEY warning is optional for Blueprint deploy

# Generate configuration files
files = provider.generate_config()
for filename, content in files.items():
    with open(filename, "w") as f:
        f.write(content)
    print(f"Generated: {filename}")

# Deploy via Blueprint (push to Git, then use Render dashboard)
import asyncio
result = asyncio.run(provider.deploy())
print(f"Status: {result.status}")
print(f"Instructions: {result.logs}")
```

## Generated Configuration Files

### render.yaml (Blueprint)

The Blueprint specification defines your entire infrastructure:

```yaml
services:
  - type: web
    name: myapp
    runtime: python
    buildCommand: sh build.sh
    startCommand: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4
    healthCheckPath: /health/
    envVars:
      - key: DJANGO_SETTINGS_MODULE
        value: config.settings
      - key: DJANGO_ENV
        value: production
      - key: DEBUG
        value: "false"
      - key: STATIC_URL
        value: /static/
      - key: STATIC_ROOT
        value: staticfiles
      - key: DATABASE_URL
        fromDatabase:
          name: myapp-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: myapp-redis
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: ALLOWED_HOSTS
        value: ".onrender.com"
    autoDeploy: true
    scaling:
      minInstances: 1
      maxInstances: 5
      targetMemoryPercent: 80
      targetCPUPercent: 80

  - type: redis
    name: myapp-redis
    plan: starter
    maxmemoryPolicy: allkeys-lru

databases:
  - name: myapp-db
    databaseName: myapp
    user: django
    plan: starter
```

### build.sh

Build script executed during deployment:

```bash
#!/usr/bin/env bash
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate --noinput
```

!!! warning "Make build.sh Executable"
    ```bash
    chmod +x build.sh
    ```

## Step-by-Step Deployment

### 1. Generate Configuration

```python
from django_matt.deploy import DeploymentConfig, RenderProvider

config = DeploymentConfig(
    app_name="myapp",
    django_settings_module="config.settings",
    create_database=True,
    create_redis=True,
)

provider = RenderProvider(config)
files = provider.generate_config()

# Write files
for filename, content in files.items():
    with open(filename, "w") as f:
        f.write(content)
```

### 2. Push to Git

```bash
git add render.yaml build.sh
git commit -m "Add Render deployment configuration"
git push origin main
```

### 3. Deploy via Render Dashboard

1. Go to [dashboard.render.com/blueprints](https://dashboard.render.com/blueprints)
2. Click **"New Blueprint Instance"**
3. Connect your GitHub/GitLab repository
4. Render automatically detects `render.yaml`
5. Review the services and databases to be created
6. Click **"Apply"** to deploy

### 4. Verify Deployment

```bash
# Check your app
curl https://myapp.onrender.com/health/

# Or visit the URL in your browser
```

## Configuration Options

### Web Service Options

```yaml
services:
  - type: web
    name: myapp
    runtime: python

    # Build configuration
    buildCommand: sh build.sh

    # Start command
    startCommand: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4

    # Health check
    healthCheckPath: /health/

    # Auto-deploy on Git push
    autoDeploy: true

    # Instance type (starter, standard, pro)
    plan: starter

    # Region
    region: oregon

    # Environment variables
    envVars:
      - key: SECRET_KEY
        generateValue: true  # Render generates a random value
      - key: DATABASE_URL
        fromDatabase:
          name: myapp-db
          property: connectionString
```

### Database Options

```yaml
databases:
  - name: myapp-db
    databaseName: myapp
    user: django

    # Plan: free, starter, standard, pro
    plan: starter

    # Region (should match web service)
    region: oregon

    # PostgreSQL version
    postgresMajorVersion: 16

    # Enable high availability (paid plans only)
    # highAvailability: true
```

### Redis Options

```yaml
services:
  - type: redis
    name: myapp-redis

    # Plan: free, starter, standard, pro
    plan: starter

    # Memory eviction policy
    maxmemoryPolicy: allkeys-lru

    # Region
    region: oregon
```

### Auto-Scaling

```yaml
services:
  - type: web
    name: myapp
    scaling:
      minInstances: 1
      maxInstances: 10
      targetMemoryPercent: 80
      targetCPUPercent: 80
```

!!! note "Scaling Requirements"
    Auto-scaling requires a paid plan (Standard or higher).

### Cron Jobs

```yaml
services:
  - type: cron
    name: myapp-scheduler
    runtime: python
    schedule: "0 * * * *"  # Every hour
    buildCommand: pip install -r requirements.txt
    startCommand: python manage.py clearsessions
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: myapp-db
          property: connectionString
```

### Background Workers

```yaml
services:
  - type: worker
    name: myapp-worker
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A config worker -l info
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: myapp-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: myapp-redis
          property: connectionString
```

## Operations

### View Logs

Access logs from the Render dashboard:

1. Go to your service
2. Click "Logs" tab
3. Filter by time range or search

### Shell Access

Render provides a web-based shell:

1. Go to your service
2. Click "Shell" tab
3. Run commands directly

```bash
# In Render shell
python manage.py migrate
python manage.py createsuperuser
python manage.py shell
```

### Manual Deploy

Trigger a manual deployment:

1. Go to your service
2. Click "Manual Deploy" > "Deploy latest commit"

Or via API:

```bash
curl -X POST "https://api.render.com/v1/services/<service-id>/deploys" \
  -H "Authorization: Bearer $RENDER_API_KEY"
```

### Rollback

1. Go to your service
2. Click "Events" tab
3. Find a previous successful deploy
4. Click "Rollback to this deploy"

### Scaling

Via dashboard:

1. Go to your service
2. Click "Scaling" tab
3. Adjust instances and resources

Or update `render.yaml` and redeploy.

## Environment Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `SECRET_KEY` | Django secret key | `generateValue: true` |
| `DATABASE_URL` | PostgreSQL connection | `fromDatabase` |
| `REDIS_URL` | Redis connection | `fromService` |
| `ALLOWED_HOSTS` | Allowed hosts | Manual |
| `DJANGO_SETTINGS_MODULE` | Settings module | Manual |
| `DJANGO_ENV` | Environment name | Manual |
| `DEBUG` | Debug mode | Manual |
| `PORT` | Server port | Auto (Render sets) |

### Environment Variable Sources

```yaml
envVars:
  # Static value
  - key: DEBUG
    value: "false"

  # Generated random value
  - key: SECRET_KEY
    generateValue: true

  # From database
  - key: DATABASE_URL
    fromDatabase:
      name: myapp-db
      property: connectionString

  # From another service
  - key: REDIS_URL
    fromService:
      type: redis
      name: myapp-redis
      property: connectionString

  # Sync from environment group
  - fromGroup: production-secrets
```

### Environment Groups

Create reusable environment variable groups:

1. Go to "Environment Groups" in dashboard
2. Create a new group
3. Add variables
4. Reference in `render.yaml`:

```yaml
envVars:
  - fromGroup: production-secrets
```

## Custom Domains

### Add Custom Domain

1. Go to your service
2. Click "Settings" > "Custom Domains"
3. Add your domain
4. Configure DNS:

```
# CNAME record
myapp.com -> myapp.onrender.com
```

Or for apex domains:
```
# A record (Render's IP)
myapp.com -> 216.24.57.1
```

### SSL Certificates

Render automatically provisions and renews SSL certificates for all domains.

## Preview Environments

Enable preview environments for pull requests:

1. Go to your service settings
2. Enable "Pull Request Previews"
3. Each PR gets its own deployment

!!! note "Preview Database"
    Preview environments can share the production database (read-only recommended) or use a separate preview database.

## Monitoring

### Health Checks

```yaml
services:
  - type: web
    healthCheckPath: /health/
```

### Metrics

View metrics in the dashboard:

- CPU usage
- Memory usage
- Request count
- Response times
- Error rates

### Alerts

Set up alerts for:

- Service down
- High error rate
- Resource usage thresholds

## Cost Optimization

### Plans Comparison

| Plan | Cost | Use Case |
|------|------|----------|
| Free | $0 | Testing, prototypes |
| Starter | $7/mo | Small projects |
| Standard | $25/mo | Production |
| Pro | $85/mo | High traffic |

### Tips

1. **Start with Starter** - Upgrade as needed
2. **Use free tier for staging** - Save on non-production
3. **Share databases** - Multiple services can share one database
4. **Enable auto-sleep** - For development environments

## Troubleshooting

### Build Failures

```bash
# Check build logs in dashboard
# Common issues:
# - Missing dependencies in requirements.txt
# - build.sh not executable
# - Python version mismatch
```

### Database Connection Issues

```yaml
# Ensure DATABASE_URL is from the database
envVars:
  - key: DATABASE_URL
    fromDatabase:
      name: myapp-db
      property: connectionString
```

### Static Files Not Loading

```yaml
# Ensure collectstatic runs in build
buildCommand: pip install -r requirements.txt && python manage.py collectstatic --noinput
```

### Health Check Failures

```python
# Ensure health check endpoint returns 200
# In django_matt, add health URLs:

from django_matt.deploy import get_health_urls

urlpatterns = [
    ...
    *get_health_urls(),
]
```

## Complete Example

```python
# deploy_render.py
import asyncio
from django_matt.deploy import DeploymentConfig, RenderProvider

async def deploy():
    config = DeploymentConfig(
        app_name="myapp",
        django_settings_module="config.settings",
        python_version="3.13",
        port=8000,
        workers=4,
        create_database=True,
        create_redis=True,
        environment="production",
        debug=False,
        health_check_path="/health/",
        auto_scale=True,
        min_instances=1,
        max_instances=5,
    )

    provider = RenderProvider(config)

    # Generate configuration
    result = await provider.deploy()

    print(f"Status: {result.status}")
    print()
    for log in result.logs:
        print(log)

if __name__ == "__main__":
    asyncio.run(deploy())
```

## GitHub Actions Integration

```yaml
# .github/workflows/render.yml
name: Deploy to Render

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Render
        env:
          RENDER_API_KEY: ${{ secrets.RENDER_API_KEY }}
          RENDER_SERVICE_ID: ${{ secrets.RENDER_SERVICE_ID }}
        run: |
          curl -X POST "https://api.render.com/v1/services/$RENDER_SERVICE_ID/deploys" \
            -H "Authorization: Bearer $RENDER_API_KEY" \
            -H "Content-Type: application/json" \
            -d '{"clearCache": "do_not_clear"}'
```

## Related Documentation

- [Docker Deployment](./docker.md)
- [Production Checklist](./production-checklist.md)
- [Environment Variables](./environment-variables.md)
- [Render Documentation](https://render.com/docs)
