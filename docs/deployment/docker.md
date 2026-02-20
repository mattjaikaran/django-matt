# Docker Deployment

django-matt provides production-ready Docker configuration generators for containerized deployments.

## Overview

The Docker deployment module generates:

- **Dockerfile** - Optimized multi-stage builds for production
- **docker-compose.yml** - Development and production configurations
- **Caddyfile** or **nginx.conf** - Reverse proxy with automatic SSL
- **.dockerignore** - Optimized build context

## Quick Start

### Using the Generator

```python
from django_matt.deploy import DockerfileGenerator, ComposeGenerator, DockerfileConfig

# Generate Dockerfile
dockerfile_gen = DockerfileGenerator(
    config=DockerfileConfig(
        python_version="3.13",
        port=8000,
        workers=4,
        use_asgi=False,
        wsgi_module="config.wsgi:application",
    )
)

# Write production Dockerfile
dockerfile_gen.write("Dockerfile", mode="production")

# Write development Dockerfile
dockerfile_gen.write("Dockerfile.dev", mode="development")
```

### Generate Docker Compose

```python
compose_gen = ComposeGenerator(
    app_name="myapp",
    port=8000,
    django_settings_module="config.settings",
    include_db=True,
    include_redis=True,
    include_celery=True,
    include_proxy=True,
    proxy_type="caddy",
    domain="myapp.com",
)

# Generate production compose file
compose_gen.write("docker-compose.yml", mode="production")

# Generate development compose file
compose_gen.write("docker-compose.dev.yml", mode="development")

# Generate Caddyfile
caddyfile = compose_gen.generate_caddyfile()
with open("Caddyfile", "w") as f:
    f.write(caddyfile)
```

## Dockerfile Modes

### Production Mode

Optimized for production with:

- Non-root user for security
- Static file collection
- Health checks
- Gunicorn/Uvicorn server

```dockerfile
# Production Dockerfile
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

# Create directories
RUN mkdir -p staticfiles media

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:$PORT/health/ || exit 1

# Run the application
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --worker-class uvicorn.workers.UvicornWorker"]
```

### Multi-Stage Mode

Smaller images with separate build and runtime stages:

```dockerfile
# Multi-stage production Dockerfile
# Stage 1: Build
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt

# Copy project and collect static files
COPY . .
RUN python manage.py collectstatic --noinput

# Stage 2: Runtime
FROM python:3.13-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy application
COPY --from=builder /app .

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:$PORT/health/ || exit 1

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4"]
```

### Development Mode

Hot reloading for development:

```dockerfile
# Development Dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

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

# Install development tools
RUN uv pip install --no-cache-dir watchdog[watchmedo]

EXPOSE 8000

# Run development server with hot reload
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

## Docker Compose Configuration

### Development Configuration

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings
      - DJANGO_ENV=development
      - DEBUG=true
      - DATABASE_URL=postgres://django:django@db:5432/django
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - .:/app
      - /app/.venv  # Exclude venv
    depends_on:
      - db
      - redis

  db:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=django
      - POSTGRES_USER=django
      - POSTGRES_PASSWORD=django
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

### Production Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    restart: always
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings
      - DJANGO_ENV=production
      - DEBUG=false
      - DATABASE_URL=postgres://django:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
    env_file:
      - .env
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    networks:
      - app_network
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  caddy:
    image: caddy:2-alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
      - static_volume:/srv/static:ro
      - media_volume:/srv/media:ro
    depends_on:
      - web
    networks:
      - app_network

  db:
    image: postgres:16-alpine
    restart: always
    environment:
      - POSTGRES_DB=${POSTGRES_DB:-myapp}
      - POSTGRES_USER=django
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - app_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U django -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redis_data:/data
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  celery_worker:
    build: .
    restart: always
    command: celery -A config worker -l info
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings
      - DJANGO_ENV=production
      - DATABASE_URL=postgres://django:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
    env_file:
      - .env
    depends_on:
      - db
      - redis
    networks:
      - app_network

  celery_beat:
    build: .
    restart: always
    command: celery -A config beat -l info
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings
      - DJANGO_ENV=production
      - DATABASE_URL=postgres://django:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
    env_file:
      - .env
    depends_on:
      - db
      - redis
    networks:
      - app_network

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:
  caddy_data:
  caddy_config:

networks:
  app_network:
    driver: bridge
```

## Reverse Proxy Configuration

### Caddyfile (Automatic SSL)

```caddyfile
myapp.com {
    # Enable compression
    encode gzip

    # Serve static files
    handle /static/* {
        root * /srv
        file_server
    }

    # Serve media files
    handle /media/* {
        root * /srv
        file_server
    }

    # Proxy to Django
    handle {
        reverse_proxy web:8000
    }

    # Security headers
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
        X-XSS-Protection "1; mode=block"
        -Server
    }
}
```

### Nginx Configuration

```nginx
events {
    worker_connections 1024;
}

http {
    upstream django {
        server web:8000;
    }

    server {
        listen 80;
        server_name myapp.com;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name myapp.com;

        ssl_certificate /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;

        # Security headers
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # Static files
        location /static/ {
            alias /var/www/static/;
            expires 30d;
            add_header Cache-Control "public, immutable";
        }

        # Media files
        location /media/ {
            alias /var/www/media/;
            expires 7d;
        }

        # Django app
        location / {
            proxy_pass http://django;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

## .dockerignore

Optimize build context by excluding unnecessary files:

```dockerignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
ENV/
env/
*.egg-info/
.eggs/

# Django
*.log
local_settings.py
db.sqlite3
media/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Git
.git/
.gitignore

# Docker
Dockerfile*
docker-compose*
.docker/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Misc
*.env
.env.*
!.env.example
.DS_Store
node_modules/
```

## Running Docker Compose

### Development

```bash
# Start all services
docker-compose -f docker-compose.dev.yml up

# Start in background
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f web

# Run migrations
docker-compose -f docker-compose.dev.yml exec web python manage.py migrate

# Create superuser
docker-compose -f docker-compose.dev.yml exec web python manage.py createsuperuser

# Stop services
docker-compose -f docker-compose.dev.yml down
```

### Production

```bash
# Build and start
docker-compose up -d --build

# Run migrations
docker-compose exec web python manage.py migrate --noinput

# Create superuser
docker-compose exec web python manage.py createsuperuser

# View logs
docker-compose logs -f web

# Scale workers
docker-compose up -d --scale celery_worker=3

# Update and restart
docker-compose pull
docker-compose up -d --build

# Full restart
docker-compose down && docker-compose up -d
```

## Environment Variables

Create a `.env` file for production secrets:

```bash
# .env
SECRET_KEY=your-very-long-and-secure-secret-key
POSTGRES_PASSWORD=your-secure-database-password
POSTGRES_DB=myapp

# Optional
SENTRY_DSN=https://xxx@sentry.io/xxx
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
```

!!! warning "Never Commit .env Files"
    Add `.env` to your `.gitignore` and use `.env.example` as a template.

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs web

# Check container status
docker-compose ps

# Rebuild without cache
docker-compose build --no-cache
```

### Database connection issues

```bash
# Check if database is ready
docker-compose exec db pg_isready -U django

# Connect to database
docker-compose exec db psql -U django -d myapp
```

### Permission issues

```bash
# Fix volume permissions
sudo chown -R 1000:1000 ./media ./staticfiles
```

### Slow builds

```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker-compose build
```

## Related Documentation

- [Production Checklist](./production-checklist.md)
- [Environment Variables](./environment-variables.md)
- [Kubernetes Deployment](./kubernetes.md)
