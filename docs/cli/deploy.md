# Deployment Commands

Commands for deploying your Django Matt application to cloud platforms and managing Docker containers.

## Overview

Django Matt supports deployment to multiple platforms:

| Platform | Command | Features |
|----------|---------|----------|
| Fly.io | `matt deploy fly` | Global edge deployment |
| Railway | `matt deploy railway` | Simple PaaS |
| Render | `matt deploy render` | Static + dynamic hosting |
| Docker | `matt deploy docker` | Self-hosted / any cloud |

---

## matt deploy fly

Deploy to Fly.io.

```bash
matt deploy fly [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--app`, `-a` | Auto-detect | Fly app name |
| `--dry-run` | `false` | Generate config without deploying |

### Examples

```bash
# Deploy to Fly.io
matt deploy fly

# Specify app name
matt deploy fly --app my-django-app

# Generate config only
matt deploy fly --dry-run
```

### Generated fly.toml

```toml
app = "my-django-app"
primary_region = "iad"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "8000"
  DJANGO_SETTINGS_MODULE = "config.settings.production"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true

[[services]]
  internal_port = 8000
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]
```

### Prerequisites

1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Login: `fly auth login`
3. Create app: `fly apps create my-django-app`

---

## matt deploy railway

Deploy to Railway.

```bash
matt deploy railway [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--dry-run` | `false` | Generate config without deploying |

### Examples

```bash
# Deploy to Railway
matt deploy railway

# Generate config only
matt deploy railway --dry-run
```

### Generated railway.json

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn config.wsgi:application --bind 0.0.0.0:$PORT",
    "healthcheckPath": "/health/",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

---

## matt deploy render

Deploy to Render.

```bash
matt deploy render [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--dry-run` | `false` | Generate config without deploying |

### Examples

```bash
# Deploy to Render
matt deploy render

# Generate config only
matt deploy render --dry-run
```

### Generated render.yaml

```yaml
services:
  - type: web
    name: my-django-app
    env: python
    buildCommand: uv pip install -r requirements.txt && python manage.py collectstatic --noinput
    startCommand: gunicorn config.wsgi:application
    healthCheckPath: /health/
    envVars:
      - key: DJANGO_SETTINGS_MODULE
        value: config.settings.production
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: postgres
          property: connectionString

databases:
  - name: postgres
    plan: starter
```

---

## matt deploy config

Generate deployment configuration files without deploying.

```bash
matt deploy config PLATFORM [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `PLATFORM` | Platform: `fly`, `railway`, `render`, `docker` |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output`, `-o` | Current directory | Output directory |

### Examples

```bash
# Generate Fly.io config
matt deploy config fly

# Generate Docker config to specific directory
matt deploy config docker --output deploy/
```

---

## matt deploy docker

Generate Docker configuration files.

```bash
matt deploy docker [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--mode`, `-m` | `production` | Mode: `production`, `development` |
| `--db/--no-db` | `true` | Include PostgreSQL |
| `--redis` | `false` | Include Redis |
| `--celery` | `false` | Include Celery workers |
| `--proxy` | `caddy` | Proxy: `caddy`, `nginx`, `none` |
| `--domain` | None | Domain for SSL configuration |
| `--output`, `-o` | Current directory | Output directory |

### Examples

```bash
# Basic Docker setup
matt deploy docker

# Development mode
matt deploy docker --mode development

# Production with all services
matt deploy docker \
  --mode production \
  --redis \
  --celery \
  --proxy caddy \
  --domain myapp.com

# Without database (external DB)
matt deploy docker --no-db
```

### Generated Files

```
project/
  Dockerfile
  docker-compose.yml
  docker-compose.dev.yml  (if --mode development)
  .dockerignore
  .env.example
  Caddyfile              (if --proxy caddy)
  nginx.conf             (if --proxy nginx)
```

### Generated Dockerfile

```dockerfile
# Python base image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./
COPY requirements.txt ./

# Install dependencies
RUN uv pip install --system -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run the application
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

### Generated docker-compose.yml

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=False
      - DATABASE_URL=postgres://app:app@db:5432/app
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - static:/app/staticfiles
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
  caddy_data:
  static:
```

---

## matt deploy build

Build the Docker image.

```bash
matt deploy build [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--tag`, `-t` | `latest` | Image tag |
| `--no-cache` | `false` | Build without cache |
| `--platform` | Auto-detect | Target platform (e.g., `linux/amd64`) |

### Examples

```bash
# Build with default tag
matt deploy build

# Build with custom tag
matt deploy build --tag v1.2.3

# Build without cache
matt deploy build --no-cache

# Build for specific platform
matt deploy build --platform linux/amd64
```

---

## matt deploy up

Start Docker containers.

```bash
matt deploy up [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--detach/-d`, `--no-detach` | `true` | Run in background |
| `--build`, `-b` | `false` | Build images before starting |
| `--dev` | `false` | Use development compose file |

### Examples

```bash
# Start containers in background
matt deploy up

# Start with logs visible
matt deploy up --no-detach

# Build and start
matt deploy up --build

# Development mode
matt deploy up --dev
```

---

## matt deploy down

Stop Docker containers.

```bash
matt deploy down [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--volumes`, `-v` | `false` | Remove volumes (deletes data!) |
| `--remove-orphans` | `false` | Remove orphan containers |

### Examples

```bash
# Stop containers
matt deploy down

# Stop and remove volumes (caution!)
matt deploy down --volumes
```

---

## matt deploy logs

View container logs.

```bash
matt deploy logs [SERVICE] [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `SERVICE` | Service name (optional, shows all if omitted) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--follow`, `-f` | `false` | Follow log output |
| `--tail`, `-n` | `100` | Number of lines to show |

### Examples

```bash
# View all logs
matt deploy logs

# Follow logs
matt deploy logs --follow

# View specific service
matt deploy logs api

# Last 50 lines
matt deploy logs --tail 50
```

---

## matt deploy env

Manage environment configurations.

```bash
matt deploy env ACTION [OPTIONS]
```

### Actions

| Action | Description |
|--------|-------------|
| `init` | Initialize environment files |
| `list` | List environment files |
| `validate` | Validate environment configuration |
| `generate` | Generate environment file |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--domain` | None | Production domain |
| `--output`, `-o` | Current directory | Output directory |

### Examples

```bash
# Initialize environment files
matt deploy env init

# Initialize with domain
matt deploy env init --domain myapp.com

# Validate environment
matt deploy env validate

# List environment files
matt deploy env list
```

### Generated .env.example

```bash
# Django
DEBUG=False
SECRET_KEY=change-me-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,myapp.com

# Database
DATABASE_URL=postgres://user:password@host:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=change-me-in-production

# Email (optional)
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
```

---

## matt deploy health

Show health check endpoint information.

```bash
matt deploy health
```

### Expected Output

```
Health Check Endpoints

+- Available Endpoints -+
| /health/  - Full health check (database, cache, custom)
| /ready/   - Kubernetes readiness probe
| /live/    - Kubernetes liveness probe
+-----------------------+

Add to urls.py:

  from django_matt.deploy.health import get_health_urls
  urlpatterns = [..., *get_health_urls()]
```

---

## Deployment Workflows

### Fly.io Deployment

```bash
# 1. Install Fly CLI
curl -L https://fly.io/install.sh | sh

# 2. Login
fly auth login

# 3. Create app
fly apps create my-app

# 4. Set secrets
fly secrets set SECRET_KEY=$(openssl rand -hex 32)
fly secrets set DATABASE_URL=postgres://...

# 5. Deploy
matt deploy fly
```

### Docker Deployment

```bash
# 1. Generate config
matt deploy docker --redis --celery

# 2. Configure environment
cp .env.example .env
# Edit .env with your settings

# 3. Build and start
matt deploy up --build

# 4. Run migrations
docker compose exec api python manage.py migrate

# 5. Create superuser
docker compose exec api python manage.py createsuperuser
```

### Railway Deployment

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Initialize project
railway init

# 4. Deploy
matt deploy railway
```

---

## Best Practices

!!! tip "Environment Variables"
    Never commit secrets to version control. Use:
    - `.env` files (gitignored)
    - Platform secret management (Fly secrets, Railway variables)
    - External secret managers (AWS Secrets Manager, HashiCorp Vault)

!!! tip "Health Checks"
    Always configure health check endpoints for:
    - Load balancer health checks
    - Kubernetes probes
    - Monitoring systems

!!! warning "Database Migrations"
    Run migrations separately from deployment:
    ```bash
    # Fly.io
    fly ssh console -C "python manage.py migrate"

    # Docker
    docker compose exec api python manage.py migrate
    ```

!!! warning "Static Files"
    For production, use a CDN or object storage:
    - AWS S3 + CloudFront
    - Google Cloud Storage
    - Cloudflare R2

## See Also

- [Deployment Overview](../deployment/index.md)
- [Docker Configuration](../deployment/docker.md)
- [Fly.io Guide](../deployment/fly-io.md)
