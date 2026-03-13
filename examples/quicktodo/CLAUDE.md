# QuickTodo

Multi-tenant todo API built with django-matt. The "build an API in 10 minutes" demo.

## Stack
- Python 3.12+ / Django 5.2+ / django-matt / PostgreSQL / Redis
- Async-first, Pydantic schemas, JWT auth

## Run
```bash
make docker-up    # Start Postgres + Redis
make migrate      # Run migrations
make seed         # Seed sample data
make run          # Start dev server → http://localhost:8000/api/docs
```

## Test
```bash
make test         # pytest with coverage
make lint         # ruff check
```

## Structure
- `apps/users/` — Custom user model, auth endpoints (register, login, me)
- `apps/organizations/` — Orgs, teams, memberships (multi-tenancy)
- `apps/todos/` — TodoList + Todo CRUD with filtering and pagination
- `config/` — Django settings, URLs, ASGI

## Key Endpoints
- POST /api/auth/register, /api/auth/login, GET /api/auth/me
- CRUD /api/organizations/, /api/organizations/{id}/members/
- CRUD /api/organizations/{org_id}/lists/, /api/organizations/{org_id}/todos/
- Filtering: ?status=pending&priority=high&search=keyword
- Pagination: ?limit=20&offset=0
