#!/bin/bash
# Post-create setup script for DevContainer
# This runs once when the container is first created

set -e

echo "=========================================="
echo "Django-Matt DevContainer Setup"
echo "=========================================="

# Navigate to workspace
cd /workspace

# Configure git (if not already configured)
if [ -z "$(git config --global user.email)" ]; then
    echo "Note: Git user.email not configured. Set it with:"
    echo "  git config --global user.email 'your@email.com'"
    echo "  git config --global user.name 'Your Name'"
fi

# Create virtual environment with uv
echo ""
echo "Creating Python virtual environment..."
uv venv .venv --python 3.13

# Activate venv
source .venv/bin/activate

# Install dependencies
echo ""
echo "Installing project dependencies..."
uv pip install -e ".[dev,all]"

# Install pre-commit hooks if .pre-commit-config.yaml exists
if [ -f ".pre-commit-config.yaml" ]; then
    echo ""
    echo "Installing pre-commit hooks..."
    uv pip install pre-commit
    pre-commit install
fi

# Wait for database to be ready
echo ""
echo "Waiting for database..."
until pg_isready -h db -U django_matt -d django_matt; do
    echo "  Database not ready, waiting..."
    sleep 2
done
echo "Database is ready!"

# Wait for Redis to be ready
echo ""
echo "Waiting for Redis..."
until redis-cli -h redis ping | grep -q PONG; do
    echo "  Redis not ready, waiting..."
    sleep 2
done
echo "Redis is ready!"

# Run Django migrations (if manage.py exists in a test project)
if [ -f "tests/manage.py" ]; then
    echo ""
    echo "Running migrations..."
    python tests/manage.py migrate --noinput || true
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo ""
    echo "Creating .env file from template..."
    cat > .env << 'EOF'
# Django-Matt Development Environment
DEBUG=true
SECRET_KEY=dev-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database
DATABASE_URL=postgres://django_matt:django_matt@db:5432/django_matt

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1

# Email (Mailhog)
EMAIL_HOST=mailhog
EMAIL_PORT=1025
EMAIL_USE_TLS=false

# JWT (generate a real secret for production)
JWT_SECRET_KEY=dev-jwt-secret-change-in-production
JWT_ACCESS_TOKEN_LIFETIME=3600
JWT_REFRESH_TOKEN_LIFETIME=604800
EOF
    echo ".env file created"
fi

# Setup mkcert for local SSL (optional)
echo ""
echo "Setting up mkcert for local SSL..."
mkcert -install 2>/dev/null || true
if [ ! -d ".certs" ]; then
    mkdir -p .certs
    cd .certs
    mkcert localhost 127.0.0.1 ::1 2>/dev/null || true
    cd /workspace
fi

# Print success message
echo ""
echo "=========================================="
echo "DevContainer setup complete!"
echo "=========================================="
echo ""
echo "Quick Start:"
echo "  1. Activate venv:  source .venv/bin/activate"
echo "  2. Run tests:      pytest"
echo "  3. Start server:   python manage.py runserver 0.0.0.0:8000"
echo ""
echo "Services:"
echo "  - PostgreSQL:  localhost:5432 (user: django_matt, pass: django_matt)"
echo "  - Redis:       localhost:6379"
echo "  - Mailhog UI:  http://localhost:8025"
echo ""
echo "Happy coding!"
