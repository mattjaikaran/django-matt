"""
Docker configuration generators.

Generates Dockerfile and docker-compose.yml for self-hosted deployments.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DockerfileConfig:
    """Configuration for Dockerfile generation."""

    python_version: str = "3.13"
    base_image: str = "python:{version}-slim"
    working_dir: str = "/app"
    port: int = 8000
    workers: int = 4
    worker_class: str = "uvicorn.workers.UvicornWorker"
    wsgi_module: str = "config.wsgi:application"
    asgi_module: str = "config.asgi:application"
    use_asgi: bool = False
    system_packages: list[str] = field(
        default_factory=lambda: [
            "build-essential",
            "libpq-dev",
            "curl",
        ]
    )
    requirements_file: str = "requirements.txt"
    static_root: str = "staticfiles"
    media_root: str = "media"
    health_check_path: str = "/health/"
    extra_commands: list[str] = field(default_factory=list)


class DockerfileGenerator:
    """
    Generates optimized Dockerfiles for Django applications.

    Supports:
    - Multi-stage builds
    - Production and development modes
    - ASGI and WSGI configurations
    - Health checks
    - Non-root user
    """

    def __init__(self, config: DockerfileConfig | None = None):
        self.config = config or DockerfileConfig()

    def generate(self, mode: str = "production") -> str:
        """Generate Dockerfile content."""
        if mode == "development":
            return self._generate_development()
        if mode == "multistage":
            return self._generate_multistage()
        return self._generate_production()

    def _generate_production(self) -> str:
        """Generate production Dockerfile."""
        base_image = self.config.base_image.format(version=self.config.python_version)
        server_cmd = self._get_server_command()

        dockerfile = f"""# Production Dockerfile
FROM {base_image}

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT={self.config.port}

# Set work directory
WORKDIR {self.config.working_dir}

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    {" ".join(self.config.system_packages)} \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY {self.config.requirements_file} .
RUN uv pip install --no-cache-dir -r {self.config.requirements_file}

# Copy project
COPY . .

# Create directories
RUN mkdir -p {self.config.static_root} {self.config.media_root}

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser {self.config.working_dir}
USER appuser

# Expose port
EXPOSE {self.config.port}

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
    CMD curl -f http://localhost:$PORT{self.config.health_check_path} || exit 1

# Run the application
CMD {server_cmd}
"""
        return dockerfile

    def _generate_multistage(self) -> str:
        """Generate multi-stage Dockerfile for smaller images."""
        base_image = self.config.base_image.format(version=self.config.python_version)
        server_cmd = self._get_server_command()

        dockerfile = f"""# Multi-stage production Dockerfile
# Stage 1: Build
FROM {base_image} AS builder

WORKDIR {self.config.working_dir}

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    libpq-dev

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY {self.config.requirements_file} .
RUN uv pip install --no-cache-dir -r {self.config.requirements_file}

# Copy project and collect static files
COPY . .
RUN python manage.py collectstatic --noinput

# Stage 2: Runtime
FROM {base_image} AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libpq5 \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR {self.config.working_dir}

# Copy application
COPY --from=builder {self.config.working_dir} .

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser {self.config.working_dir}
USER appuser

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT={self.config.port}

EXPOSE {self.config.port}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
    CMD curl -f http://localhost:$PORT{self.config.health_check_path} || exit 1

CMD {server_cmd}
"""
        return dockerfile

    def _generate_development(self) -> str:
        """Generate development Dockerfile with hot reloading."""
        base_image = self.config.base_image.format(version=self.config.python_version)

        dockerfile = f"""# Development Dockerfile
FROM {base_image}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT={self.config.port}

WORKDIR {self.config.working_dir}

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    {" ".join(self.config.system_packages)} \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY {self.config.requirements_file} .
RUN uv pip install --no-cache-dir -r {self.config.requirements_file}

# Install development tools
RUN uv pip install --no-cache-dir watchdog[watchmedo]

EXPOSE {self.config.port}

# Run development server with hot reload
CMD ["python", "manage.py", "runserver", "0.0.0.0:{self.config.port}"]
"""
        return dockerfile

    def _get_server_command(self) -> str:
        """Get the appropriate server command."""
        if self.config.use_asgi:
            return f'["sh", "-c", "python manage.py migrate --noinput && uvicorn {self.config.asgi_module} --host 0.0.0.0 --port $PORT --workers {self.config.workers}"]'
        return f'["sh", "-c", "python manage.py migrate --noinput && gunicorn {self.config.wsgi_module} --bind 0.0.0.0:$PORT --workers {self.config.workers} --worker-class {self.config.worker_class}"]'

    def write(self, path: Path, mode: str = "production"):
        """Write Dockerfile to path."""
        content = self.generate(mode)
        with open(path, "w") as f:
            f.write(content)


@dataclass
class ComposeService:
    """Configuration for a Docker Compose service."""

    name: str
    image: str | None = None
    build: str | None = "."
    ports: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    env_file: str | None = None
    volumes: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    command: str | None = None
    restart: str = "unless-stopped"
    healthcheck: dict[str, Any] | None = None
    networks: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class ComposeConfig:
    """Configuration for Docker Compose generation."""

    project_name: str
    services: list[ComposeService] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    networks: list[str] = field(default_factory=list)


class ComposeGenerator:
    """
    Generates docker-compose.yml files for Django applications.

    Supports:
    - Multiple environments (development, production)
    - PostgreSQL, Redis, Celery
    - Nginx/Caddy reverse proxy
    - SSL with Let's Encrypt
    """

    def __init__(
        self,
        app_name: str,
        port: int = 8000,
        django_settings_module: str = "config.settings",
        include_db: bool = True,
        include_redis: bool = False,
        include_celery: bool = False,
        include_proxy: bool = True,
        proxy_type: str = "caddy",  # "caddy" or "nginx"
        domain: str | None = None,
    ):
        self.app_name = app_name
        self.port = port
        self.django_settings_module = django_settings_module
        self.include_db = include_db
        self.include_redis = include_redis
        self.include_celery = include_celery
        self.include_proxy = include_proxy
        self.proxy_type = proxy_type
        self.domain = domain

    def generate(self, mode: str = "production") -> str:
        """Generate docker-compose.yml content."""
        if mode == "development":
            return self._generate_development()
        return self._generate_production()

    def _generate_production(self) -> str:
        """Generate production docker-compose.yml."""
        compose: dict[str, Any] = {
            "version": "3.8",
            "services": {},
            "volumes": {},
            "networks": {"app_network": {"driver": "bridge"}},
        }

        # Web service
        web_service: dict[str, Any] = {
            "build": ".",
            "restart": "always",
            "environment": {
                "DJANGO_SETTINGS_MODULE": self.django_settings_module,
                "DJANGO_ENV": "production",
                "DEBUG": "false",
            },
            "env_file": [".env"],
            "volumes": [
                "static_volume:/app/staticfiles",
                "media_volume:/app/media",
            ],
            "networks": ["app_network"],
            "depends_on": [],
        }

        if self.include_db:
            web_service["depends_on"].append("db")
            web_service["environment"]["DATABASE_URL"] = (
                "postgres://django:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"
            )

        if self.include_redis:
            web_service["depends_on"].append("redis")
            web_service["environment"]["REDIS_URL"] = "redis://redis:6379/0"

        compose["services"]["web"] = web_service
        compose["volumes"]["static_volume"] = {}
        compose["volumes"]["media_volume"] = {}

        # Database service
        if self.include_db:
            compose["services"]["db"] = {
                "image": "postgres:16-alpine",
                "restart": "always",
                "environment": {
                    "POSTGRES_DB": "${POSTGRES_DB:-" + self.app_name.replace("-", "_") + "}",
                    "POSTGRES_USER": "django",
                    "POSTGRES_PASSWORD": "${POSTGRES_PASSWORD}",
                },
                "volumes": ["postgres_data:/var/lib/postgresql/data"],
                "networks": ["app_network"],
                "healthcheck": {
                    "test": ["CMD-SHELL", "pg_isready -U django -d ${POSTGRES_DB}"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                },
            }
            compose["volumes"]["postgres_data"] = {}

        # Redis service
        if self.include_redis:
            compose["services"]["redis"] = {
                "image": "redis:7-alpine",
                "restart": "always",
                "volumes": ["redis_data:/data"],
                "networks": ["app_network"],
                "healthcheck": {
                    "test": ["CMD", "redis-cli", "ping"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                },
            }
            compose["volumes"]["redis_data"] = {}

        # Celery workers
        if self.include_celery:
            compose["services"]["celery_worker"] = {
                "build": ".",
                "restart": "always",
                "command": "celery -A config worker -l info",
                "environment": web_service["environment"].copy(),
                "env_file": [".env"],
                "depends_on": ["db", "redis"] if self.include_db else ["redis"],
                "networks": ["app_network"],
            }

            compose["services"]["celery_beat"] = {
                "build": ".",
                "restart": "always",
                "command": "celery -A config beat -l info",
                "environment": web_service["environment"].copy(),
                "env_file": [".env"],
                "depends_on": ["db", "redis"] if self.include_db else ["redis"],
                "networks": ["app_network"],
            }

        # Reverse proxy
        if self.include_proxy:
            if self.proxy_type == "caddy":
                compose["services"]["caddy"] = {
                    "image": "caddy:2-alpine",
                    "restart": "always",
                    "ports": ["80:80", "443:443"],
                    "volumes": [
                        "./Caddyfile:/etc/caddy/Caddyfile",
                        "caddy_data:/data",
                        "caddy_config:/config",
                        "static_volume:/srv/static:ro",
                        "media_volume:/srv/media:ro",
                    ],
                    "depends_on": ["web"],
                    "networks": ["app_network"],
                }
                compose["volumes"]["caddy_data"] = {}
                compose["volumes"]["caddy_config"] = {}
            else:
                compose["services"]["nginx"] = {
                    "image": "nginx:alpine",
                    "restart": "always",
                    "ports": ["80:80", "443:443"],
                    "volumes": [
                        "./nginx.conf:/etc/nginx/nginx.conf:ro",
                        "./certs:/etc/nginx/certs:ro",
                        "static_volume:/var/www/static:ro",
                        "media_volume:/var/www/media:ro",
                    ],
                    "depends_on": ["web"],
                    "networks": ["app_network"],
                }

        return yaml.dump(compose, default_flow_style=False, sort_keys=False)

    def _generate_development(self) -> str:
        """Generate development docker-compose.yml."""
        compose: dict[str, Any] = {
            "version": "3.8",
            "services": {},
            "volumes": {},
        }

        # Web service with hot reload
        compose["services"]["web"] = {
            "build": {
                "context": ".",
                "dockerfile": "Dockerfile.dev",
            },
            "ports": [f"{self.port}:{self.port}"],
            "environment": {
                "DJANGO_SETTINGS_MODULE": self.django_settings_module,
                "DJANGO_ENV": "development",
                "DEBUG": "true",
            },
            "volumes": [
                ".:/app",
                "/app/.venv",  # Exclude venv
            ],
            "depends_on": [],
        }

        if self.include_db:
            compose["services"]["web"]["depends_on"].append("db")
            compose["services"]["web"]["environment"]["DATABASE_URL"] = (
                "postgres://django:django@db:5432/django"
            )

            compose["services"]["db"] = {
                "image": "postgres:16-alpine",
                "ports": ["5432:5432"],
                "environment": {
                    "POSTGRES_DB": "django",
                    "POSTGRES_USER": "django",
                    "POSTGRES_PASSWORD": "django",
                },
                "volumes": ["postgres_data:/var/lib/postgresql/data"],
            }
            compose["volumes"]["postgres_data"] = {}

        if self.include_redis:
            compose["services"]["web"]["depends_on"].append("redis")
            compose["services"]["web"]["environment"]["REDIS_URL"] = "redis://redis:6379/0"

            compose["services"]["redis"] = {
                "image": "redis:7-alpine",
                "ports": ["6379:6379"],
            }

        return yaml.dump(compose, default_flow_style=False, sort_keys=False)

    def generate_caddyfile(self) -> str:
        """Generate Caddyfile for Caddy reverse proxy."""
        domain = self.domain or "localhost"

        return f"""{domain} {{
    # Enable compression
    encode gzip

    # Serve static files
    handle /static/* {{
        root * /srv
        file_server
    }}

    # Serve media files
    handle /media/* {{
        root * /srv
        file_server
    }}

    # Proxy to Django
    handle {{
        reverse_proxy web:{self.port}
    }}

    # Security headers
    header {{
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
        X-XSS-Protection "1; mode=block"
        -Server
    }}
}}
"""

    def generate_nginx_conf(self) -> str:
        """Generate nginx.conf for Nginx reverse proxy."""
        domain = self.domain or "localhost"

        return f"""events {{
    worker_connections 1024;
}}

http {{
    upstream django {{
        server web:{self.port};
    }}

    server {{
        listen 80;
        server_name {domain};
        return 301 https://$host$request_uri;
    }}

    server {{
        listen 443 ssl http2;
        server_name {domain};

        ssl_certificate /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;

        # Security headers
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # Static files
        location /static/ {{
            alias /var/www/static/;
            expires 30d;
            add_header Cache-Control "public, immutable";
        }}

        # Media files
        location /media/ {{
            alias /var/www/media/;
            expires 7d;
        }}

        # Django app
        location / {{
            proxy_pass http://django;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}
    }}
}}
"""

    def generate_dockerignore(self) -> str:
        """Generate .dockerignore file."""
        return """# Python
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
"""

    def write(self, path: Path, mode: str = "production"):
        """Write docker-compose.yml to path."""
        content = self.generate(mode)
        with open(path, "w") as f:
            f.write(content)


__all__ = [
    "ComposeConfig",
    "ComposeGenerator",
    "ComposeService",
    "DockerfileConfig",
    "DockerfileGenerator",
]
