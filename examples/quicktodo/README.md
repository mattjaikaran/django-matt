# QuickTodo

Multi-tenant todo API built with django-matt — the "build an API in 10 minutes" demo.

## Tech Stack

- **Python**: 3.12+ with [uv](https://docs.astral.sh/uv/) package manager
- **Django**: 5.2+
- **API Framework**: django-matt (async-first, Pydantic schemas, JWT auth)
- **Database**: PostgreSQL 16

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose (for PostgreSQL)

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
├── core/            # Shared base models and utilities
├── users/           # Custom user model, auth endpoints
├── organizations/   # Organizations, teams, memberships
└── todos/           # Todo lists and todo items
config/              # Django settings, URLs, ASGI
```

## API Endpoints

| Category | Endpoints |
|----------|-----------|
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| Organizations | `CRUD /api/organizations/`, teams, members |
| Todo Lists | `CRUD /api/organizations/{org_id}/lists/` |
| Todos | `CRUD /api/organizations/{org_id}/lists/{list_id}/todos/` |

### Filtering & Pagination

```
GET /api/.../todos/?status=pending&priority=high&search=keyword
GET /api/.../todos/?limit=20&offset=0
```

## Features Demonstrated

- JWT authentication with custom user model
- Multi-tenancy with organization-scoped data
- Permission scoping (users only access their org's data)
- Filtering by status, priority, and search keyword
- Limit/offset pagination
- Minimal dependency footprint — no Celery, Channels, or Stripe
