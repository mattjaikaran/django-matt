# Railway Deployment

Deploy django-matt applications to Railway with automatic builds, managed databases, and preview environments.

## Overview

Railway is a modern deployment platform that provides:

- **Automatic Builds** - Detects Python/Django projects automatically
- **Managed PostgreSQL** - One-click database provisioning
- **Managed Redis** - Built-in caching support
- **Preview Environments** - Automatic PR deployments
- **Easy Scaling** - Horizontal and vertical scaling

## Prerequisites

1. **Railway Account** - Sign up at [railway.app](https://railway.app)
2. **Railway CLI** - Install the command-line tool

### Install Railway CLI

=== "macOS (Homebrew)"
    ```bash
    brew install railway
    ```

=== "npm"
    ```bash
    npm install -g @railway/cli
    ```

=== "Shell"
    ```bash
    bash <(curl -fsSL cli.new)
    ```

### Authenticate

```bash
railway login
```

## Quick Start

### Using django-matt Deploy Module

```python
from django_matt.deploy import DeploymentConfig, RailwayProvider

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
provider = RailwayProvider(config)

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

### railway.json

The main Railway configuration file:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt && python manage.py collectstatic --noinput"
  },
  "deploy": {
    "startCommand": "gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4",
    "healthcheckPath": "/health/",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Procfile

Standard Procfile for Railway:

```procfile
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --worker-class uvicorn.workers.UvicornWorker
release: python manage.py migrate --noinput
```

### nixpacks.toml

Custom Nixpacks build configuration:

```toml
[phases.setup]
nixPkgs = ["python313", "postgresql"]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[phases.build]
cmds = ["python manage.py collectstatic --noinput"]

[start]
cmd = "gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4"
```

## Step-by-Step Deployment

### 1. Initialize Railway Project

```bash
# Initialize new project
railway init

# Or link to existing project
railway link
```

### 2. Add PostgreSQL Database

```bash
# Add PostgreSQL plugin
railway add --database postgres

# The DATABASE_URL is automatically set
```

Alternatively, via the dashboard:

1. Go to your project in Railway dashboard
2. Click "New" > "Database" > "PostgreSQL"
3. Railway automatically sets `DATABASE_URL`

### 3. Add Redis (Optional)

```bash
# Add Redis plugin
railway add --database redis

# REDIS_URL is automatically set
```

### 4. Set Environment Variables

```bash
# Set required variables
railway variables --set SECRET_KEY="your-secret-key"
railway variables --set DJANGO_SETTINGS_MODULE="config.settings"
railway variables --set DJANGO_ENV="production"
railway variables --set DEBUG="false"
railway variables --set ALLOWED_HOSTS=".railway.app"

# View all variables
railway variables
```

### 5. Deploy

```bash
# Deploy current directory
railway up

# Deploy with detached output
railway up --detach

# Deploy specific branch
railway up --branch main
```

### 6. Generate Domain

```bash
# Generate a railway.app domain
railway domain

# Or add custom domain via dashboard
```

## Configuration Options

### Custom Build Commands

```json
{
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt && pip install gunicorn && python manage.py collectstatic --noinput"
  }
}
```

### Custom Start Command

```json
{
  "deploy": {
    "startCommand": "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2"
  }
}
```

### Health Checks

```json
{
  "deploy": {
    "healthcheckPath": "/health/",
    "healthcheckTimeout": 30
  }
}
```

### Restart Policy

```json
{
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

## Celery Workers

Railway supports running multiple services. Create separate services for Celery:

### Service: Web

```bash
# Procfile for web
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4
release: python manage.py migrate --noinput
```

### Service: Worker

Create a new service in Railway and set:

```bash
# Start command for worker service
celery -A config worker -l info
```

### Service: Beat

Create another service for Celery Beat:

```bash
# Start command for beat service
celery -A config beat -l info
```

!!! tip "Shared Database"
    All services can share the same PostgreSQL and Redis instances by setting the same `DATABASE_URL` and `REDIS_URL` variables.

## Operations

### View Logs

```bash
# Stream logs
railway logs

# View recent logs
railway logs -n 100
```

### Run Commands

```bash
# Open a shell
railway run bash

# Run migrations
railway run python manage.py migrate

# Create superuser
railway run python manage.py createsuperuser

# Open Django shell
railway run python manage.py shell
```

### Environment Variables

```bash
# List all variables
railway variables

# Set a variable
railway variables --set KEY=value

# Delete a variable
railway variables --delete KEY
```

### Scaling

Railway handles scaling automatically based on usage. For manual scaling:

1. Go to Railway dashboard
2. Select your service
3. Go to Settings > Scaling
4. Configure replicas and resources

!!! note "Scaling Limits"
    Railway's free tier has resource limits. Upgrade to a paid plan for production workloads.

## Preview Environments

Railway automatically creates preview environments for pull requests:

1. Enable GitHub integration in Railway dashboard
2. Create a pull request
3. Railway deploys a preview environment automatically
4. Each PR gets its own database copy

### Configure Preview Environments

```json
{
  "environments": {
    "preview": {
      "deploy": {
        "startCommand": "gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2"
      }
    }
  }
}
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Auto (via plugin) |
| `REDIS_URL` | Redis connection string | Auto (via plugin) |
| `ALLOWED_HOSTS` | Comma-separated hosts | Yes |
| `DJANGO_SETTINGS_MODULE` | Settings module path | Yes |
| `DJANGO_ENV` | Environment name | Yes |
| `DEBUG` | Debug mode (false for production) | Yes |
| `PORT` | Server port | Auto (Railway sets this) |

## Monitoring

### Railway Dashboard

Access metrics, logs, and deployments at [railway.app/dashboard](https://railway.app/dashboard).

### Deployment History

```bash
# View deployment history
railway deployments
```

### Resource Usage

View resource usage in the Railway dashboard under "Metrics".

## Cost Optimization

### Starter Plan

- $5/month minimum
- Pay for what you use
- Good for small projects

### Pro Plan

- $20/month per seat
- Better for teams
- More resources included

### Optimize Costs

1. **Use appropriate worker count** - Don't over-provision
2. **Enable sleep** - For development environments
3. **Share databases** - Multiple services can share one database
4. **Monitor usage** - Check metrics regularly

## Troubleshooting

### Build Failures

```bash
# Check build logs
railway logs

# Verify nixpacks configuration
cat nixpacks.toml

# Test build locally
nixpacks build . --name myapp
```

### Database Connection Issues

```bash
# Verify DATABASE_URL is set
railway variables | grep DATABASE

# Test connection
railway run python manage.py dbshell

# Check database status
railway status
```

### Deployment Not Working

```bash
# Check deployment status
railway status

# View deployment logs
railway logs

# Redeploy
railway up --force
```

### Domain Issues

```bash
# Check domain configuration
railway domain

# Generate new domain
railway domain --generate
```

## Complete Example

```python
# deploy_railway.py
import asyncio
from django_matt.deploy import DeploymentConfig, RailwayProvider

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
        health_check_path="/health/",
    )

    provider = RailwayProvider(config)

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

## GitHub Actions Integration

```yaml
# .github/workflows/deploy.yml
name: Deploy to Railway

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Railway CLI
        run: npm install -g @railway/cli

      - name: Deploy
        run: railway up
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
```

## Related Documentation

- [Docker Deployment](./docker.md)
- [Production Checklist](./production-checklist.md)
- [Environment Variables](./environment-variables.md)
- [Railway Documentation](https://docs.railway.app/)
