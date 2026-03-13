# DevPlatform

API management SaaS built with django-matt. Like a mini Stripe Dashboard or PostHog.

## Stack
- Python 3.12+ / Django 5.2+ / django-matt / PostgreSQL / Redis
- Async-first, Pydantic schemas, JWT auth
- Stripe for billing, Celery for background tasks, Channels for WebSockets

## Key Features
- **API Keys** — Generate, rotate, and manage API keys per project
- **Projects** — Multi-tenant project management within organizations
- **Request Logging** — Capture and inspect API requests/responses
- **Usage Analytics** — Track API usage, latency, error rates
- **Webhooks** — Configurable webhook endpoints with retry logic
- **Usage-Based Billing** — Stripe integration with metered billing

## Run
```bash
make docker-up    # Start Postgres + Redis
make migrate      # Run migrations
make seed         # Seed sample data
make run          # Start dev server -> http://localhost:8000/api/docs
```

## Test
```bash
make test         # pytest with coverage
make lint         # ruff check
```

## Structure
- `apps/users/` — Custom user model, auth endpoints (register, login, me)
- `apps/organizations/` — Orgs, teams, memberships (multi-tenancy)
- `apps/projects/` — Projects within organizations
- `apps/keys/` — API key management
- `apps/gateway/` — API gateway and request routing
- `apps/analytics/` — Usage analytics and metrics
- `apps/webhooks/` — Webhook configuration and delivery
- `apps/billing/` — Stripe usage-based billing
- `apps/dashboard/` — Dashboard views and aggregations
- `config/` — Django settings, URLs, ASGI

## Key Endpoints
- POST /api/auth/register, /api/auth/login, GET /api/auth/me
- CRUD /api/organizations/, /api/organizations/{id}/members/
- CRUD /api/projects/, /api/projects/{id}/keys/
- GET /api/analytics/usage, /api/analytics/requests
- CRUD /api/webhooks/
- GET /api/billing/usage, POST /api/billing/subscribe
