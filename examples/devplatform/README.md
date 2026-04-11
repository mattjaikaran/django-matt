# DevPlatform

API management SaaS built with django-matt. Like a mini Stripe Dashboard or PostHog — manage API keys, track usage analytics, configure webhooks, and handle usage-based billing.

## Tech Stack

- **Python**: 3.12+ with [uv](https://docs.astral.sh/uv/) package manager
- **Django**: 5.2+
- **API Framework**: django-matt (async-first, Pydantic schemas, JWT auth)
- **Database**: PostgreSQL 16
- **Cache/Broker**: Redis 7
- **Payments**: Stripe (usage-based/metered billing)
- **Background Tasks**: Celery
- **WebSockets**: Django Channels

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose (for PostgreSQL + Redis)

## Quick Start

```bash
make install      # Install dependencies
make docker-up    # Start Postgres + Redis
make migrate      # Run migrations
make seed         # Seed sample data
make run          # Start dev server -> http://localhost:8000/api/docs
```

## Testing

```bash
make test         # pytest with coverage
make lint         # ruff check
make format       # ruff format
```

## Project Structure

```
apps/
├── users/           # Custom user model, auth endpoints (register, login, me)
├── organizations/   # Orgs, teams, memberships (multi-tenancy)
├── projects/        # Projects within organizations
├── keys/            # API key generation, rotation, management
├── gateway/         # API gateway and request routing/logging
├── analytics/       # Usage analytics, metrics, request tracking
├── webhooks/        # Webhook configuration and delivery with retries
├── billing/         # Stripe usage-based billing and subscriptions
└── dashboard/       # Dashboard views and aggregations
config/              # Django settings, URLs, ASGI
```

## API Endpoints

| Category | Endpoints |
|----------|-----------|
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| Organizations | `CRUD /api/organizations/`, `/api/organizations/{id}/members/` |
| Projects | `CRUD /api/projects/`, `/api/projects/{id}/keys/` |
| Analytics | `GET /api/analytics/usage`, `GET /api/analytics/requests` |
| Webhooks | `CRUD /api/webhooks/` |
| Billing | `GET /api/billing/usage`, `POST /api/billing/subscribe` |

## Features Demonstrated

- Multi-tenancy with organizations, teams, and memberships
- JWT authentication with custom user model
- API key generation with secure prefix + hash pattern
- API gateway with request/response logging
- Real-time usage analytics and metrics tracking
- Webhook endpoints with delivery tracking and retry logic
- Usage-based billing via Stripe metered subscriptions
- Dashboard aggregations with real-time updates via WebSockets
