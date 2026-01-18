# Deployment Overview

django-matt provides built-in deployment support for popular cloud platforms and self-hosted options.

## Supported Platforms

```mermaid
flowchart TB
    subgraph "PaaS Platforms"
        FLY[Fly.io]
        RAILWAY[Railway]
        RENDER[Render]
        DO[DigitalOcean<br/>App Platform]
    end

    subgraph "Cloud Providers"
        AWS[AWS<br/>ECS/App Runner]
        HETZNER[Hetzner Cloud]
    end

    subgraph "Self-Hosted"
        DOCKER[Docker Compose]
        K8S[Kubernetes]
    end

    DEPLOY[Deploy Command] --> FLY
    DEPLOY --> RAILWAY
    DEPLOY --> RENDER
    DEPLOY --> DO
    DEPLOY --> AWS
    DEPLOY --> HETZNER
    DEPLOY --> DOCKER
```

## Quick Start

```bash
# Initialize deployment configuration
python manage.py deploy init --platform fly

# Deploy to platform
python manage.py deploy --platform fly

# Deploy specific environment
python manage.py deploy --platform fly --env production
```

## Deployment Architecture

```mermaid
flowchart LR
    subgraph "Source"
        CODE[Application Code]
        ENV[Environment Vars]
    end

    subgraph "Build"
        DOCKER[Docker Build]
        STATIC[Collect Static]
        MIGRATE[Run Migrations]
    end

    subgraph "Deploy"
        PLATFORM[Cloud Platform]
        LB[Load Balancer]
        INSTANCES[App Instances]
    end

    subgraph "Services"
        DB[(PostgreSQL)]
        CACHE[(Redis)]
        STORAGE[Object Storage]
    end

    CODE --> DOCKER
    ENV --> DOCKER
    DOCKER --> STATIC
    STATIC --> MIGRATE
    MIGRATE --> PLATFORM

    PLATFORM --> LB
    LB --> INSTANCES
    INSTANCES --> DB
    INSTANCES --> CACHE
    INSTANCES --> STORAGE
```

## Configuration Files

```mermaid
flowchart TD
    INIT[deploy init] --> FILES{Generated Files}

    FILES --> DOCKERFILE[Dockerfile]
    FILES --> COMPOSE[docker-compose.yml]
    FILES --> PLATFORM[Platform Config]
    FILES --> ENVFILES[.env Files]

    PLATFORM --> FLY_TOML[fly.toml]
    PLATFORM --> RAILWAY_JSON[railway.json]
    PLATFORM --> RENDER_YAML[render.yaml]
    PLATFORM --> APP_YAML[.do/app.yaml]
```

## Environment Configuration

```python
# Generated environments
environments/
├── .env.development
├── .env.staging
└── .env.production
```

Each environment includes:
- Database connection
- Redis/cache settings
- Security settings (SECRET_KEY, ALLOWED_HOSTS)
- Email configuration
- Storage settings

## Health Checks

```mermaid
flowchart LR
    LB[Load Balancer] --> HEALTH[/health/]
    K8S[Kubernetes] --> READY[/ready/]
    K8S --> LIVE[/live/]

    HEALTH --> DB_CHECK[Database Check]
    HEALTH --> CACHE_CHECK[Cache Check]
    HEALTH --> CUSTOM[Custom Checks]
```

Built-in endpoints:
- `/health/` - Full health check (all services)
- `/ready/` - Kubernetes readiness probe
- `/live/` - Kubernetes liveness probe

## Related Documentation

- [Fly.io](./fly.md)
- [Railway](./railway.md)
- [Render](./render.md)
- [AWS](./aws.md)
- [Docker](./docker.md)
- [Environment Setup](./environments.md)
