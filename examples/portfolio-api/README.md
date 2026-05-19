# Portfolio API

A personal portfolio backend API built with [django-matt](../../README.md) — an async-first Django meta-framework.

## Stack

- Python 3.12+ / Django 5.2+
- django-matt (async controllers, JWT auth, Pydantic v2 schemas)
- PostgreSQL
- `uv` for dependency management

## Features

- JWT authentication (register, login, profile)
- Portfolio projects CRUD (slug-based routing, featured filter)
- Technical skills with categories and proficiency levels
- Work experience with date ranges
- Contact form (public submission, admin read/mark-read)
- OpenAPI docs at `/api/docs`

## Setup

### Local dev

```bash
# 1. Install dependencies
make install

# 2. Copy env and configure
cp .env.example .env
# Edit .env with your DATABASE_URL

# 3. Run migrations
make migrate

# 4. Seed sample data
make seed
# Creates: admin@example.com / admin123 + sample projects/skills/experience

# 5. Start server
make run
# API: http://localhost:8000
# Docs: http://localhost:8000/api/docs
```

### Docker

```bash
docker-compose up --build
# API on http://localhost:8000
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Register |
| POST | `/api/auth/login` | — | Login → JWT tokens |
| GET | `/api/auth/me` | JWT | Current user |
| PATCH | `/api/auth/me` | JWT | Update profile |
| GET | `/api/projects` | — | List projects (`?featured=true`) |
| POST | `/api/projects` | JWT | Create project |
| GET | `/api/projects/:slug` | — | Get project |
| PATCH | `/api/projects/:slug` | JWT | Update project |
| DELETE | `/api/projects/:slug` | JWT | Delete project |
| GET | `/api/skills` | — | List skills (`?category=backend`) |
| POST | `/api/skills` | JWT | Create skill |
| GET | `/api/skills/:id` | — | Get skill |
| PATCH | `/api/skills/:id` | JWT | Update skill |
| DELETE | `/api/skills/:id` | JWT | Delete skill |
| GET | `/api/experience` | — | List experience |
| POST | `/api/experience` | JWT | Create entry |
| GET | `/api/experience/:id` | — | Get entry |
| PATCH | `/api/experience/:id` | JWT | Update entry |
| DELETE | `/api/experience/:id` | JWT | Delete entry |
| POST | `/api/contact` | — | Submit contact form |
| GET | `/api/contact` | JWT | List messages (admin) |
| PATCH | `/api/contact/:id/read` | JWT | Mark as read |
| GET | `/api/health` | — | Health check |

## Skill Categories

`frontend` | `backend` | `devops` | `database` | `mobile` | `other`

## Testing

```bash
make test
# or
uv run pytest tests/ -x -q
```

Tests use SQLite in-memory — no external services needed.
