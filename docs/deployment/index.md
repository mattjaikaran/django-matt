# Deployment Overview

django-matt provides comprehensive deployment support for popular cloud platforms and self-hosted options, with built-in configuration generators and platform-specific optimizations.

## Supported Platforms

| Platform | Type | Best For | Cost |
|----------|------|----------|------|
| [Fly.io](./fly-io.md) | PaaS | Global edge deployment | $$$ |
| [Railway](./railway.md) | PaaS | Rapid prototyping | $$ |
| [Render](./render.md) | PaaS | Simple deployments | $$ |
| [AWS](./aws.md) | Cloud | Enterprise scale | $$$$ |
| [Hetzner](./hetzner.md) | VPS | Cost-effective self-hosted | $ |
| [Docker](./docker.md) | Container | Any infrastructure | Varies |
| [Kubernetes](./kubernetes.md) | Orchestration | Large scale deployments | $$$$ |

## Platform Comparison

```
+----------------+--------+--------+-----------+------------+----------+
| Feature        | Fly.io | Railway| Render    | AWS        | Hetzner  |
+----------------+--------+--------+-----------+------------+----------+
| Auto SSL       | Yes    | Yes    | Yes       | Yes (ALB)  | Caddy    |
| Auto Scaling   | Yes    | Yes    | Yes       | Yes        | Manual   |
| Global CDN     | Yes    | No     | Limited   | CloudFront | No       |
| PostgreSQL     | Managed| Managed| Managed   | RDS        | Self     |
| Redis          | Upstash| Managed| Managed   | ElastiCache| Self     |
| WebSockets     | Yes    | Yes    | Yes       | Yes        | Yes      |
| SSH Access     | Yes    | No     | No        | Yes        | Yes      |
| Free Tier      | Yes    | Yes    | Yes       | Yes        | No       |
| Pricing        | Usage  | Usage  | Usage     | Complex    | Fixed    |
+----------------+--------+--------+-----------+------------+----------+
```

## Quick Start

### Using the Deploy Module

```python
from django_matt.deploy import (
    DeploymentConfig,
    get_provider,
    list_providers,
)

# List available providers
print(list_providers())  # ['fly', 'railway', 'render', 'aws', 'hetzner', 'digitalocean']

# Configure deployment
config = DeploymentConfig(
    app_name="myapp",
    django_settings_module="config.settings",
    python_version="3.13",
    port=8000,
    workers=4,
    create_database=True,
    create_redis=True,
)

# Get provider and generate config
provider = get_provider("fly", config)
files = provider.generate_config()

# Write configuration files
for filename, content in files.items():
    print(f"Generated: {filename}")
```

### Command Line Deployment

```bash
# Generate configuration for a platform
python manage.py deploy init --platform fly --app myapp

# Deploy to platform
python manage.py deploy --platform fly

# Deploy to specific environment
python manage.py deploy --platform fly --env production
```

## Deployment Architecture

```
                    +------------------+
                    |   Load Balancer  |
                    |   (SSL/TLS)      |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
        +-----v-----+  +-----v-----+  +-----v-----+
        | Instance 1|  | Instance 2|  | Instance 3|
        | (Gunicorn)|  | (Gunicorn)|  | (Gunicorn)|
        +-----+-----+  +-----+-----+  +-----+-----+
              |              |              |
              +--------------+--------------+
                             |
              +--------------+--------------+
              |                             |
        +-----v-----+               +-------v-------+
        | PostgreSQL|               |     Redis     |
        |  Primary  |               |    Cluster    |
        +-----+-----+               +---------------+
              |
        +-----v-----+
        |  Replica  |
        +-----------+
```

## Configuration Files Generated

Each deployment provider generates platform-specific configuration files:

| Provider | Files Generated |
|----------|-----------------|
| Fly.io | `fly.toml`, `Dockerfile`, `.dockerignore`, `release.sh` |
| Railway | `railway.json`, `Procfile`, `nixpacks.toml` |
| Render | `render.yaml`, `build.sh` |
| AWS | `Dockerfile`, `apprunner.yaml` or `ecs-task-definition.json`, `buildspec.yml` |
| Hetzner | `docker-compose.yml`, `Dockerfile`, `Caddyfile`, `cloud-init.yml`, `deploy.sh` |
| Docker | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `Caddyfile` |

## Health Checks

All deployments include health check endpoints:

```python
from django_matt.deploy import get_health_urls

# Add to urls.py
urlpatterns = [
    ...
    *get_health_urls(),
]
```

This provides:

- **`/health/`** - Full health check (database, cache, custom checks)
- **`/ready/`** - Kubernetes readiness probe
- **`/live/`** - Kubernetes liveness probe

### Custom Health Checks

```python
from django_matt.deploy import health_check, CheckResult, HealthStatus

@health_check("my_service")
def check_my_service():
    # Check service health
    is_healthy = check_external_service()
    return CheckResult(
        name="my_service",
        status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
        message="External service check",
    )
```

## Environment Management

django-matt provides environment-specific configuration:

```python
from django_matt.deploy import EnvironmentConfig, EnvironmentManager

manager = EnvironmentManager()

# Add standard environments
manager.add(EnvironmentConfig.development())
manager.add(EnvironmentConfig.staging(domain="staging.myapp.com"))
manager.add(EnvironmentConfig.production(domain="myapp.com"))

# Generate .env files for all environments
manager.generate_env_files()

# Validate configuration
errors = manager.validate("production")
```

See [Environment Variables](./environment-variables.md) for complete reference.

## Secret Management

```python
from django_matt.deploy import SecretManager

secrets = SecretManager()

# Load from .env file
secrets.load_from_dotenv(".env.production")

# Generate a secure secret key
secret_key = secrets.generate_secret_key()

# Export for deployment
secrets.export_to_file(".env.deploy", keys=["SECRET_KEY", "DATABASE_URL"])
```

!!! warning "Security Best Practices"
    - Never commit secrets to version control
    - Use platform-specific secret management (Fly secrets, Railway variables, AWS Secrets Manager)
    - Rotate secrets regularly
    - Use different secrets for each environment

## Production Checklist

Before deploying to production, ensure you have completed the [Production Checklist](./production-checklist.md):

- [ ] Security settings configured
- [ ] Database connection pooling enabled
- [ ] Static files served via CDN
- [ ] Error monitoring configured (Sentry)
- [ ] Logging configured
- [ ] Health checks implemented
- [ ] Backup strategy in place
- [ ] SSL/TLS enabled
- [ ] Rate limiting configured
- [ ] CORS settings verified

## Related Documentation

- [Docker Deployment](./docker.md) - Container-based deployment
- [Fly.io Deployment](./fly-io.md) - Global edge deployment
- [Railway Deployment](./railway.md) - Rapid deployment platform
- [Render Deployment](./render.md) - Simple cloud deployment
- [AWS Deployment](./aws.md) - Enterprise cloud deployment
- [Hetzner Deployment](./hetzner.md) - Cost-effective VPS deployment
- [Kubernetes Deployment](./kubernetes.md) - Container orchestration
- [Production Checklist](./production-checklist.md) - Security and performance
- [Environment Variables](./environment-variables.md) - Configuration reference
