# SaaS Starter

A comprehensive SaaS example application showcasing django-matt features including multi-tenancy, billing, real-time notifications, and background tasks.

## Tech Stack

- **Python**: 3.13+ with [uv](https://docs.astral.sh/uv/) package manager
- **Django**: 5.2+
- **API Framework**: django-matt
- **Database**: PostgreSQL 16
- **Cache/Broker**: Redis 7
- **Background Tasks**: Celery
- **WebSockets**: Django Channels with Daphne
- **Billing**: Stripe

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- PostgreSQL 16+
- Redis 7+
- Docker & Docker Compose (optional, for containerized setup)

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv

# Or with Homebrew (macOS)
brew install uv
```

## Quick Start

### Local Development

```bash
# Clone and navigate to the project
cd examples/saas-starter

# Install dependencies
make install

# Or install with dev dependencies
make install-dev

# Copy environment file
cp .env.example .env

# Run database migrations
make migrate

# Seed with sample data
make seed

# Start development server
make dev
```

### Docker Development

```bash
# Build and start all services
make docker-up-build

# Or step by step
make docker-build
make docker-up

# Run migrations in Docker
make docker-migrate

# Seed database in Docker
make docker-seed

# View logs
make docker-logs

# Stop services
make docker-down
```

## Available Commands

Run `make help` to see all available commands.

### Setup & Dependencies

| Command | Description |
|---------|-------------|
| `make install` | Install dependencies with uv |
| `make install-dev` | Install all dependencies including dev |
| `make sync` | Sync dependencies from lockfile |
| `make update` | Update all dependencies |
| `make add pkg=name` | Add a dependency |
| `make add-dev pkg=name` | Add a dev dependency |

### Development

| Command | Description |
|---------|-------------|
| `make dev` | Start development server with hot reload |
| `make run` | Start production-like server with uvicorn |
| `make shell` | Open Django shell with IPython |
| `make migrate` | Run database migrations |
| `make migrations` | Create new migrations |

### Testing

| Command | Description |
|---------|-------------|
| `make test` | Run all tests |
| `make test-cov` | Run tests with coverage report |
| `make test-fast` | Run tests in parallel |
| `make lint` | Run linter (ruff) |
| `make format` | Format code with ruff |
| `make check` | Run all code quality checks |

### Background Tasks

| Command | Description |
|---------|-------------|
| `make celery` | Start Celery worker |
| `make celery-beat` | Start Celery beat scheduler |
| `make celery-flower` | Start Flower monitoring |

### Docker

| Command | Description |
|---------|-------------|
| `make docker-build` | Build Docker images |
| `make docker-up` | Start all services |
| `make docker-down` | Stop all services |
| `make docker-logs` | View logs from all services |
| `make docker-shell` | Open shell in app container |

## Project Structure

```
saas-starter/
├── api/                    # API endpoints
│   ├── main.py            # API router setup
│   ├── auth.py            # Authentication endpoints
│   ├── organizations.py   # Organization management
│   ├── teams.py           # Team management
│   ├── projects.py        # Project CRUD
│   ├── tasks.py           # Task management
│   ├── billing.py         # Billing/subscription endpoints
│   └── notifications.py   # Notification endpoints
├── core/                   # Core application
│   ├── models.py          # User and base models
│   ├── schemas.py         # Pydantic schemas
│   └── management/        # Management commands
├── projects/               # Projects app
│   ├── models.py          # Project, Task models
│   └── schemas.py         # Project schemas
├── billing/                # Billing app
│   ├── models.py          # Subscription models
│   └── tasks.py           # Billing background tasks
├── notifications/          # Notifications app
│   ├── models.py          # Notification models
│   ├── consumers.py       # WebSocket consumers
│   └── tasks.py           # Notification tasks
├── saas_project/           # Django project settings
│   ├── settings.py        # Django settings
│   ├── urls.py            # URL configuration
│   ├── celery.py          # Celery configuration
│   └── asgi.py            # ASGI configuration
├── scripts/               # Utility scripts
├── pyproject.toml         # Project dependencies (uv)
├── Makefile               # Development commands
├── Dockerfile             # Production Docker image
└── docker-compose.yml     # Docker Compose services
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Django
DEBUG=true
DJANGO_SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=saas_starter
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## API Documentation

Once the server is running, access:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI Schema**: http://localhost:8000/api/openapi.json

## Features

### Multi-tenancy
- Organization-based isolation
- Team management with roles
- Invitation system

### Authentication
- JWT-based authentication
- Magic link (passwordless) login
- Role-based access control (RBAC)

### Billing
- Stripe integration
- Subscription management
- Usage-based billing support

### Real-time
- WebSocket notifications
- Live updates via Django Channels

### Background Tasks
- Celery for async processing
- Scheduled tasks with Celery Beat
- Task monitoring with Flower

## License

MIT License
