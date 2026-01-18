"""
Hetzner Cloud deployment provider.

Provides deployment to Hetzner Cloud servers with Docker.
"""

from typing import Any, Dict, List, Optional
import json

from django_matt.deploy.base import (
    DeploymentProvider,
    DeploymentConfig,
    DeploymentResult,
    DeploymentStatus,
    register_provider,
)


@register_provider("hetzner")
class HetznerProvider(DeploymentProvider):
    """
    Hetzner Cloud deployment provider.

    Supports:
    - Server provisioning with cloud-init
    - Docker and Docker Compose deployment
    - Automatic SSL with Caddy/Traefik
    - PostgreSQL and Redis setup
    - Firewall configuration
    - Snapshots and backups
    """

    name = "hetzner"
    display_name = "Hetzner"

    def __init__(self, config: DeploymentConfig, server_type: str = "cx22"):
        super().__init__(config)
        self.server_type = server_type
        self.location = "nbg1"  # Nuremberg

    def validate(self) -> List[str]:
        """Validate configuration for Hetzner deployment."""
        errors = []

        # Check CLI is installed
        if not self.check_cli_installed("hcloud"):
            errors.append("hcloud CLI is not installed. Install from https://github.com/hetznercloud/cli")

        # Validate app name
        if not self.config.app_name:
            errors.append("app_name is required")

        # Check for Django settings
        if not self.config.django_settings_module:
            errors.append("django_settings_module is required")

        # Check for domain (required for SSL)
        if not self.config.allowed_hosts:
            errors.append("allowed_hosts is required (domain for SSL)")

        return errors

    def generate_config(self) -> Dict[str, str]:
        """Generate Hetzner deployment configuration files."""
        files = {}

        # Generate docker-compose.yml
        files["docker-compose.yml"] = self._generate_docker_compose()

        # Generate Dockerfile
        files["Dockerfile"] = self._generate_dockerfile()

        # Generate Caddyfile for reverse proxy
        files["Caddyfile"] = self._generate_caddyfile()

        # Generate cloud-init script
        files["cloud-init.yml"] = self._generate_cloud_init()

        # Generate deploy script
        files["deploy.sh"] = self._generate_deploy_script()

        # Generate .env.production template
        files[".env.production"] = self._generate_env_template()

        return files

    def _generate_docker_compose(self) -> str:
        """Generate docker-compose.yml for Hetzner deployment."""
        compose = f'''version: '3.8'

services:
  web:
    build: .
    restart: always
    environment:
      - DJANGO_SETTINGS_MODULE={self.config.django_settings_module}
      - DJANGO_ENV={self.config.environment}
      - DEBUG={str(self.config.debug).lower()}
      - DATABASE_URL=${{DATABASE_URL}}
      - SECRET_KEY=${{SECRET_KEY}}
      - ALLOWED_HOSTS=${{ALLOWED_HOSTS}}
'''

        if self.config.redis_url or self.config.create_redis:
            compose += '      - REDIS_URL=${REDIS_URL}\n'

        compose += f'''    depends_on:
'''

        if self.config.create_database:
            compose += '      - db\n'

        if self.config.create_redis:
            compose += '      - redis\n'

        compose += f'''    volumes:
      - static_volume:/app/{self.config.static_root}
      - media_volume:/app/{self.config.media_root}
    networks:
      - app_network

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
'''

        if self.config.create_database:
            compose += f'''
  db:
    image: postgres:16-alpine
    restart: always
    environment:
      - POSTGRES_DB={self.config.app_name.replace('-', '_')}
      - POSTGRES_USER=django
      - POSTGRES_PASSWORD=${{POSTGRES_PASSWORD}}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - app_network
'''

        if self.config.create_redis:
            compose += '''
  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redis_data:/data
    networks:
      - app_network
'''

        compose += '''
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
'''

        return compose

    def _generate_dockerfile(self) -> str:
        """Generate Dockerfile for Hetzner."""
        return f'''# Dockerfile for Hetzner deployment
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT={self.config.port}

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    libpq-dev \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create directories
RUN mkdir -p {self.config.static_root} {self.config.media_root}

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE {self.config.port}

# Run the application
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn {self.config.django_settings_module.rsplit('.', 1)[0]}.wsgi:application --bind 0.0.0.0:{self.config.port} --workers {self.config.workers}"]
'''

    def _generate_caddyfile(self) -> str:
        """Generate Caddyfile for automatic SSL."""
        domain = self.config.allowed_hosts[0] if self.config.allowed_hosts else "localhost"

        return f'''{domain} {{
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
        reverse_proxy web:{self.config.port}
    }}

    # Security headers
    header {{
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
        X-XSS-Protection "1; mode=block"
    }}

    # Logging
    log {{
        output file /var/log/caddy/access.log
    }}
}}
'''

    def _generate_cloud_init(self) -> str:
        """Generate cloud-init configuration for server setup."""
        return f'''#cloud-config
package_update: true
package_upgrade: true

packages:
  - docker.io
  - docker-compose
  - git
  - ufw

# Configure firewall
runcmd:
  - ufw default deny incoming
  - ufw default allow outgoing
  - ufw allow ssh
  - ufw allow http
  - ufw allow https
  - ufw --force enable
  - systemctl enable docker
  - systemctl start docker
  - usermod -aG docker root

# Create app directory
write_files:
  - path: /root/deploy.sh
    permissions: '0755'
    content: |
      #!/bin/bash
      cd /opt/{self.config.app_name}
      docker-compose pull
      docker-compose up -d --build
      docker-compose exec -T web python manage.py migrate --noinput

final_message: "Server setup complete. Ready for deployment."
'''

    def _generate_deploy_script(self) -> str:
        """Generate deployment script."""
        return f'''#!/bin/bash
set -e

# Configuration
SERVER_IP="${{SERVER_IP}}"
APP_NAME="{self.config.app_name}"
REMOTE_DIR="/opt/$APP_NAME"

echo "Deploying to Hetzner server..."

# Ensure remote directory exists
ssh root@$SERVER_IP "mkdir -p $REMOTE_DIR"

# Sync files
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \\
    --exclude='venv' --exclude='.venv' --exclude='node_modules' \\
    --exclude='.env' --exclude='db.sqlite3' \\
    ./ root@$SERVER_IP:$REMOTE_DIR/

# Copy environment file
scp .env.production root@$SERVER_IP:$REMOTE_DIR/.env

# Deploy
ssh root@$SERVER_IP "cd $REMOTE_DIR && docker-compose pull && docker-compose up -d --build"

# Run migrations
ssh root@$SERVER_IP "cd $REMOTE_DIR && docker-compose exec -T web python manage.py migrate --noinput"

echo "Deployment complete!"
echo "Visit https://{self.config.allowed_hosts[0] if self.config.allowed_hosts else 'your-domain.com'}"
'''

    def _generate_env_template(self) -> str:
        """Generate .env.production template."""
        template = f'''# Production environment variables
DJANGO_SETTINGS_MODULE={self.config.django_settings_module}
DJANGO_ENV=production
DEBUG=false
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS={','.join(self.config.allowed_hosts) if self.config.allowed_hosts else 'your-domain.com'}
'''

        if self.config.create_database:
            template += f'''
# Database (internal Docker network)
DATABASE_URL=postgres://django:your-db-password-here@db:5432/{self.config.app_name.replace('-', '_')}
POSTGRES_PASSWORD=your-db-password-here
'''
        elif self.config.database_url:
            template += f'''
DATABASE_URL={self.config.database_url}
'''

        if self.config.create_redis:
            template += '''
# Redis (internal Docker network)
REDIS_URL=redis://redis:6379/0
'''
        elif self.config.redis_url:
            template += f'''
REDIS_URL={self.config.redis_url}
'''

        return template

    async def deploy(self) -> DeploymentResult:
        """Deploy to Hetzner Cloud."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        # Validate first
        errors = self.validate()
        if errors:
            result.status = DeploymentStatus.FAILED
            result.errors = errors
            return result

        try:
            result.status = DeploymentStatus.BUILDING

            # Write configuration files
            configs = self.generate_config()
            for filename, content in configs.items():
                file_path = self.config.project_dir / filename
                with open(file_path, "w") as f:
                    f.write(content)
                result.add_log(f"Generated {filename}")

            # Make deploy script executable
            deploy_script = self.config.project_dir / "deploy.sh"
            deploy_script.chmod(0o755)

            # Check if server exists
            servers_result = self.run_command([
                "hcloud", "server", "list", "-o", "json"
            ])

            server_exists = False
            server_ip = None

            if servers_result.returncode == 0:
                servers = json.loads(servers_result.stdout)
                for server in servers:
                    if server.get("name") == self.config.app_name:
                        server_exists = True
                        server_ip = server.get("public_net", {}).get("ipv4", {}).get("ip")
                        break

            if not server_exists:
                # Create server
                result.add_log(f"Creating server: {self.config.app_name}")

                # First, get or create SSH key
                ssh_keys_result = self.run_command(["hcloud", "ssh-key", "list", "-o", "json"])
                ssh_key_name = None

                if ssh_keys_result.returncode == 0:
                    ssh_keys = json.loads(ssh_keys_result.stdout)
                    if ssh_keys:
                        ssh_key_name = ssh_keys[0].get("name")

                if not ssh_key_name:
                    result.add_log("No SSH key found. Please add one via: hcloud ssh-key create --name mykey --public-key-from-file ~/.ssh/id_rsa.pub")
                    result.status = DeploymentStatus.FAILED
                    result.add_error("SSH key required for server creation")
                    return result

                # Create server with cloud-init
                cloud_init_file = self.config.project_dir / "cloud-init.yml"

                create_result = self.run_command([
                    "hcloud", "server", "create",
                    "--name", self.config.app_name,
                    "--type", self.server_type,
                    "--image", "ubuntu-22.04",
                    "--location", self.location,
                    "--ssh-key", ssh_key_name,
                    "--user-data-from-file", str(cloud_init_file),
                ])

                if create_result.returncode != 0:
                    result.status = DeploymentStatus.FAILED
                    result.add_error(f"Failed to create server: {create_result.stderr}")
                    return result

                # Get server IP
                server_info = self.run_command([
                    "hcloud", "server", "describe", self.config.app_name, "-o", "json"
                ])

                if server_info.returncode == 0:
                    info = json.loads(server_info.stdout)
                    server_ip = info.get("public_net", {}).get("ipv4", {}).get("ip")

                result.add_log(f"Server created with IP: {server_ip}")
                result.add_log("Waiting for server initialization (this may take a few minutes)...")

            result.status = DeploymentStatus.DEPLOYING

            if server_ip:
                result.add_log("")
                result.add_log("Configuration files generated successfully!")
                result.add_log("")
                result.add_log("To complete deployment:")
                result.add_log(f"1. Edit .env.production with your secrets")
                result.add_log(f"2. Run: SERVER_IP={server_ip} ./deploy.sh")
                result.add_log("")
                result.add_log(f"Or manually deploy:")
                result.add_log(f"  rsync -avz ./ root@{server_ip}:/opt/{self.config.app_name}/")
                result.add_log(f"  ssh root@{server_ip} 'cd /opt/{self.config.app_name} && docker-compose up -d'")

                result.url = f"https://{self.config.allowed_hosts[0]}" if self.config.allowed_hosts else None
                result.metadata = {"server_ip": server_ip}

            result.status = DeploymentStatus.SUCCESS

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def get_status(self, deployment_id: str) -> DeploymentResult:
        """Get deployment status."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        try:
            status_result = self.run_command([
                "hcloud", "server", "describe", self.config.app_name, "-o", "json"
            ])

            if status_result.returncode == 0:
                data = json.loads(status_result.stdout)
                result.deployment_id = str(data.get("id", ""))
                result.metadata = data

                status = data.get("status", "")
                if status == "running":
                    result.status = DeploymentStatus.SUCCESS
                elif status == "initializing" or status == "starting":
                    result.status = DeploymentStatus.DEPLOYING
                elif status == "off":
                    result.status = DeploymentStatus.CANCELLED
                else:
                    result.status = DeploymentStatus.PENDING

                server_ip = data.get("public_net", {}).get("ipv4", {}).get("ip")
                if server_ip and self.config.allowed_hosts:
                    result.url = f"https://{self.config.allowed_hosts[0]}"
            else:
                result.status = DeploymentStatus.FAILED
                result.add_error(status_result.stderr)

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def rollback(self, deployment_id: str) -> DeploymentResult:
        """Rollback using server snapshot."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        result.add_log("To rollback on Hetzner:")
        result.add_log("1. Create snapshots before deployments: hcloud server create-image --type snapshot")
        result.add_log("2. Rebuild from snapshot: hcloud server rebuild --image <snapshot-id>")
        result.add_log("")
        result.add_log("Or use Docker to rollback:")
        result.add_log("  ssh root@SERVER_IP 'cd /opt/app && git checkout <previous-commit> && docker-compose up -d --build'")

        result.status = DeploymentStatus.SUCCESS
        return result

    async def scale(self, instances: int) -> DeploymentResult:
        """Scale the application (upgrade server or add load balancer)."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        if instances > 1:
            result.add_log("For multiple instances on Hetzner:")
            result.add_log("1. Create additional servers")
            result.add_log("2. Set up a Hetzner Load Balancer")
            result.add_log("3. Add servers to the load balancer")
            result.add_log("")
            result.add_log("Commands:")
            result.add_log("  hcloud load-balancer create --name lb --type lb11 --location nbg1")
            result.add_log("  hcloud load-balancer add-target --server <server-id>")
        else:
            result.add_log("For vertical scaling, resize the server:")
            result.add_log("  hcloud server change-type --server <server-name> --type <new-type>")
            result.add_log("")
            result.add_log("Available types: cx22, cx32, cx42, cx52 (shared) or cpx11, cpx21, etc (dedicated)")

        result.status = DeploymentStatus.SUCCESS
        return result

    async def get_logs(self, lines: int = 100) -> List[str]:
        """Get application logs."""
        # Get server IP
        server_info = self.run_command([
            "hcloud", "server", "describe", self.config.app_name, "-o", "json"
        ])

        if server_info.returncode != 0:
            return ["Failed to get server info"]

        info = json.loads(server_info.stdout)
        server_ip = info.get("public_net", {}).get("ipv4", {}).get("ip")

        if not server_ip:
            return ["Server IP not found"]

        # Get logs via SSH
        result = self.run_command([
            "ssh", f"root@{server_ip}",
            f"cd /opt/{self.config.app_name} && docker-compose logs --tail={lines}",
        ])

        if result.returncode == 0:
            return result.stdout.split("\n")
        return [f"Failed to get logs: {result.stderr}"]


__all__ = ["HetznerProvider"]
