# Hetzner Deployment

Deploy django-matt applications to Hetzner Cloud with Docker, automatic SSL via Caddy, and cost-effective VPS hosting.

## Overview

Hetzner Cloud provides affordable and reliable VPS hosting:

- **Cost-Effective** - Starting from ~$4/month for VPS
- **European Data Centers** - GDPR-compliant hosting
- **Excellent Performance** - NVMe SSDs, dedicated resources
- **Full Control** - Root access to your server
- **Automatic SSL** - Via Caddy reverse proxy

## Prerequisites

1. **Hetzner Account** - Sign up at [hetzner.cloud](https://www.hetzner.com/cloud)
2. **hcloud CLI** - Install the Hetzner Cloud CLI
3. **SSH Key** - For server access
4. **Domain Name** - For SSL certificates

### Install hcloud CLI

=== "macOS (Homebrew)"
    ```bash
    brew install hcloud
    ```

=== "Linux"
    ```bash
    # Download latest release
    curl -o hcloud-linux-amd64.tar.gz \
        https://github.com/hetznercloud/cli/releases/latest/download/hcloud-linux-amd64.tar.gz
    tar xzf hcloud-linux-amd64.tar.gz
    sudo mv hcloud /usr/local/bin/
    ```

=== "Windows"
    ```powershell
    # Download from GitHub releases
    # https://github.com/hetznercloud/cli/releases
    ```

### Configure CLI

```bash
# Set API token
hcloud context create myproject

# Enter your API token from Hetzner Cloud Console
# Console > Projects > API Tokens > Generate API Token

# Verify
hcloud server list
```

### Add SSH Key

```bash
# Add your SSH key to Hetzner
hcloud ssh-key create --name mykey --public-key-from-file ~/.ssh/id_rsa.pub

# List keys
hcloud ssh-key list
```

## Quick Start

### Using django-matt Deploy Module

```python
from django_matt.deploy import DeploymentConfig, HetznerProvider

# Configure deployment
config = DeploymentConfig(
    app_name="myapp",
    django_settings_module="config.settings",
    python_version="3.13",
    port=8000,
    workers=4,
    create_database=True,
    create_redis=True,
    allowed_hosts=["myapp.example.com"],
    health_check_path="/health/",
)

# Initialize provider
provider = HetznerProvider(config, server_type="cx22")

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

# Deploy
import asyncio
result = asyncio.run(provider.deploy())
print(f"Status: {result.status}")
print(f"Server IP: {result.metadata.get('server_ip')}")
```

## Generated Configuration Files

### docker-compose.yml

Complete Docker Compose configuration with PostgreSQL, Redis, and Caddy:

```yaml
version: '3.8'

services:
  web:
    build: .
    restart: always
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings
      - DJANGO_ENV=production
      - DEBUG=false
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - db
      - redis
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
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

  db:
    image: postgres:16-alpine
    restart: always
    environment:
      - POSTGRES_DB=myapp
      - POSTGRES_USER=django
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - app_network

  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redis_data:/data
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

### Dockerfile

Production-ready Dockerfile:

```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p staticfiles media
RUN python manage.py collectstatic --noinput

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4"]
```

### Caddyfile

Automatic SSL with Caddy reverse proxy:

```caddyfile
myapp.example.com {
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
    }

    # Logging
    log {
        output file /var/log/caddy/access.log
    }
}
```

### cloud-init.yml

Server initialization script:

```yaml
#cloud-config
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
      cd /opt/myapp
      docker-compose pull
      docker-compose up -d --build
      docker-compose exec -T web python manage.py migrate --noinput

final_message: "Server setup complete. Ready for deployment."
```

### deploy.sh

Deployment script for your local machine:

```bash
#!/bin/bash
set -e

# Configuration
SERVER_IP="${SERVER_IP}"
APP_NAME="myapp"
REMOTE_DIR="/opt/$APP_NAME"

echo "Deploying to Hetzner server..."

# Ensure remote directory exists
ssh root@$SERVER_IP "mkdir -p $REMOTE_DIR"

# Sync files
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='venv' --exclude='.venv' --exclude='node_modules' \
    --exclude='.env' --exclude='db.sqlite3' \
    ./ root@$SERVER_IP:$REMOTE_DIR/

# Copy environment file
scp .env.production root@$SERVER_IP:$REMOTE_DIR/.env

# Deploy
ssh root@$SERVER_IP "cd $REMOTE_DIR && docker-compose pull && docker-compose up -d --build"

# Run migrations
ssh root@$SERVER_IP "cd $REMOTE_DIR && docker-compose exec -T web python manage.py migrate --noinput"

echo "Deployment complete!"
echo "Visit https://myapp.example.com"
```

### .env.production

Environment variables template:

```bash
# Production environment variables
DJANGO_SETTINGS_MODULE=config.settings
DJANGO_ENV=production
DEBUG=false
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=myapp.example.com

# Database (internal Docker network)
DATABASE_URL=postgres://django:your-db-password-here@db:5432/myapp
POSTGRES_PASSWORD=your-db-password-here

# Redis (internal Docker network)
REDIS_URL=redis://redis:6379/0
```

## Step-by-Step Deployment

### 1. Generate Configuration Files

```python
from django_matt.deploy import DeploymentConfig, HetznerProvider

config = DeploymentConfig(
    app_name="myapp",
    django_settings_module="config.settings",
    create_database=True,
    create_redis=True,
    allowed_hosts=["myapp.example.com"],
)

provider = HetznerProvider(config, server_type="cx22")
files = provider.generate_config()

for filename, content in files.items():
    with open(filename, "w") as f:
        f.write(content)
```

### 2. Create Server

```bash
# Create server with cloud-init
hcloud server create \
    --name myapp \
    --type cx22 \
    --image ubuntu-22.04 \
    --location nbg1 \
    --ssh-key mykey \
    --user-data-from-file cloud-init.yml

# Get server IP
hcloud server ip myapp
```

### 3. Configure DNS

Point your domain to the server IP:

```
A    myapp.example.com    <server-ip>
```

!!! tip "Wait for DNS Propagation"
    DNS changes can take up to 24 hours to propagate globally, though typically 5-30 minutes.

### 4. Edit Environment Variables

```bash
# Generate a secure secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Edit .env.production with actual values
vim .env.production
```

### 5. Deploy

```bash
# Make deploy script executable
chmod +x deploy.sh

# Deploy
SERVER_IP=$(hcloud server ip myapp) ./deploy.sh
```

### 6. Verify Deployment

```bash
# Check your site
curl https://myapp.example.com/health/

# SSH and check logs
ssh root@$(hcloud server ip myapp) "cd /opt/myapp && docker-compose logs -f"
```

## Server Types

| Type | vCPU | RAM | Storage | Price/mo |
|------|------|-----|---------|----------|
| cx22 | 2 | 4 GB | 40 GB | ~$4 |
| cx32 | 4 | 8 GB | 80 GB | ~$8 |
| cx42 | 8 | 16 GB | 160 GB | ~$16 |
| cx52 | 16 | 32 GB | 320 GB | ~$32 |
| cpx11 | 2 (dedicated) | 2 GB | 40 GB | ~$5 |
| cpx21 | 3 (dedicated) | 4 GB | 80 GB | ~$9 |
| cpx31 | 4 (dedicated) | 8 GB | 160 GB | ~$15 |

!!! tip "Choosing Server Type"
    - **cx22**: Good for small to medium Django apps
    - **cx32**: Recommended for production
    - **cpx series**: When you need dedicated CPU

## Operations

### View Logs

```bash
# SSH to server
ssh root@$(hcloud server ip myapp)

# View all logs
cd /opt/myapp && docker-compose logs -f

# View specific service
docker-compose logs -f web
docker-compose logs -f db
docker-compose logs -f caddy
```

### Run Management Commands

```bash
# SSH to server
ssh root@$(hcloud server ip myapp)

# Run Django commands
cd /opt/myapp
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python manage.py shell
```

### Database Access

```bash
# Connect to PostgreSQL
ssh root@$(hcloud server ip myapp) \
    "cd /opt/myapp && docker-compose exec db psql -U django -d myapp"

# Backup database
ssh root@$(hcloud server ip myapp) \
    "cd /opt/myapp && docker-compose exec -T db pg_dump -U django myapp" > backup.sql

# Restore database
cat backup.sql | ssh root@$(hcloud server ip myapp) \
    "cd /opt/myapp && docker-compose exec -T db psql -U django myapp"
```

### Update Deployment

```bash
# Pull latest changes and redeploy
SERVER_IP=$(hcloud server ip myapp) ./deploy.sh
```

### Scaling

#### Vertical Scaling (Bigger Server)

```bash
# Power off server
hcloud server poweroff myapp

# Resize server
hcloud server change-type myapp cx32

# Power on
hcloud server poweron myapp
```

#### Horizontal Scaling (Multiple Servers)

For high availability, use a load balancer:

```bash
# Create load balancer
hcloud load-balancer create --name myapp-lb --type lb11 --location nbg1

# Add servers to load balancer
hcloud load-balancer add-target myapp-lb --server myapp

# Create additional servers
hcloud server create --name myapp-2 --type cx22 --image ubuntu-22.04 ...
hcloud load-balancer add-target myapp-lb --server myapp-2
```

### Backups

```bash
# Create snapshot
hcloud server create-image --type snapshot --description "Before update" myapp

# List snapshots
hcloud image list --type snapshot

# Restore from snapshot
hcloud server rebuild --image <snapshot-id> myapp
```

### Rollback

```bash
# Option 1: Restore from snapshot
hcloud server rebuild --image <snapshot-id> myapp

# Option 2: Git-based rollback
ssh root@$(hcloud server ip myapp) \
    "cd /opt/myapp && git checkout <previous-commit> && docker-compose up -d --build"
```

## Firewall Configuration

### Using Hetzner Firewall

```bash
# Create firewall
hcloud firewall create --name myapp-fw

# Add rules
hcloud firewall add-rule myapp-fw --direction in --protocol tcp --port 22 --source-ips 0.0.0.0/0 --description "SSH"
hcloud firewall add-rule myapp-fw --direction in --protocol tcp --port 80 --source-ips 0.0.0.0/0 --description "HTTP"
hcloud firewall add-rule myapp-fw --direction in --protocol tcp --port 443 --source-ips 0.0.0.0/0 --description "HTTPS"

# Apply to server
hcloud firewall apply-to-resource myapp-fw --type server --server myapp
```

### Using UFW (Ubuntu Firewall)

```bash
# SSH to server
ssh root@$(hcloud server ip myapp)

# Configure UFW
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow http
ufw allow https
ufw enable
```

## Monitoring

### Server Metrics

View metrics in Hetzner Cloud Console or via CLI:

```bash
# Check server status
hcloud server describe myapp
```

### Application Monitoring

Add monitoring tools to docker-compose:

```yaml
services:
  # ... existing services ...

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    networks:
      - app_network

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    networks:
      - app_network

volumes:
  prometheus_data:
  grafana_data:
```

## Cost Optimization

### Estimated Monthly Costs

| Component | Cost |
|-----------|------|
| cx22 Server | ~$4 |
| Volume (100GB) | ~$4 |
| Snapshot Backups | ~$0.01/GB |
| Load Balancer | ~$6 |
| Floating IP | ~$3 |
| **Total (Basic)** | **~$4-15** |

### Tips

1. **Right-size your server** - Start small, scale up as needed
2. **Use snapshots instead of backups** - More cost-effective
3. **Delete unused resources** - Snapshots, volumes, IPs
4. **Use reserved instances** - For predictable workloads (contact Hetzner)

## Troubleshooting

### Server Won't Start

```bash
# Check server status
hcloud server describe myapp

# View console logs
hcloud server request-console myapp
```

### Docker Issues

```bash
# SSH to server
ssh root@$(hcloud server ip myapp)

# Check Docker status
systemctl status docker

# Check container status
docker-compose ps
docker-compose logs
```

### SSL Certificate Issues

```bash
# Check Caddy logs
docker-compose logs caddy

# Verify DNS
dig myapp.example.com

# Check if ports 80/443 are open
ufw status
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps db

# Check logs
docker-compose logs db

# Test connection
docker-compose exec db pg_isready -U django
```

## Complete Example

```python
# deploy_hetzner.py
import asyncio
from django_matt.deploy import DeploymentConfig, HetznerProvider

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
        allowed_hosts=["myapp.example.com"],
        health_check_path="/health/",
    )

    provider = HetznerProvider(config, server_type="cx22")

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

    for log in result.logs:
        print(log)

    if result.metadata.get("server_ip"):
        print(f"\nServer IP: {result.metadata['server_ip']}")
        print(f"URL: {result.url}")

if __name__ == "__main__":
    asyncio.run(deploy())
```

## Related Documentation

- [Docker Deployment](./docker.md)
- [Production Checklist](./production-checklist.md)
- [Environment Variables](./environment-variables.md)
- [Hetzner Cloud Documentation](https://docs.hetzner.cloud/)
