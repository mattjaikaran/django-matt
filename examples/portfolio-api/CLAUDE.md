# Portfolio API

Personal portfolio backend built with django-matt.

## Stack
- **Backend**: Python 3.12+ / Django 5.2+ / django-matt / PostgreSQL
- Async-first, Pydantic v2 schemas, JWT auth
- `uv` for package management

## Run (Local)
```bash
make install      # uv sync
make migrate      # makemigrations + migrate
make seed         # seed sample data (admin@example.com / admin123)
make run          # Django API -> http://localhost:8000/api/docs
```

## Run (Docker)
```bash
docker-compose up --build    # API on :8000
```

## API Endpoints

### Auth
- `POST /api/auth/register` — register new user
- `POST /api/auth/login` — login, get JWT tokens
- `GET /api/auth/me` — get current user (JWT required)
- `PATCH /api/auth/me` — update profile (JWT required)

### Projects
- `GET /api/projects` — list published projects (filter: `?featured=true`)
- `POST /api/projects` — create project (JWT required)
- `GET /api/projects/:slug` — get project by slug
- `PATCH /api/projects/:slug` — update project (JWT required)
- `DELETE /api/projects/:slug` — delete project (JWT required)

### Skills
- `GET /api/skills` — list skills (filter: `?category=backend`)
- `POST /api/skills` — create skill (JWT required)
- `GET /api/skills/:id` — get skill
- `PATCH /api/skills/:id` — update skill (JWT required)
- `DELETE /api/skills/:id` — delete skill (JWT required)

### Experience
- `GET /api/experience` — list experience entries
- `POST /api/experience` — create entry (JWT required)
- `GET /api/experience/:id` — get entry
- `PATCH /api/experience/:id` — update entry (JWT required)
- `DELETE /api/experience/:id` — delete entry (JWT required)

### Contact
- `POST /api/contact` — submit contact message (no auth)
- `GET /api/contact` — list all messages (JWT required)
- `PATCH /api/contact/:id/read` — mark as read (JWT required)

### Misc
- `GET /api/health` — health check

## Backend Structure
- `apps/users/` — custom user model (email login, no username), JWT auth
- `apps/projects/` — portfolio project CRUD with slug-based lookup
- `apps/skills/` — technical skills with category + proficiency level
- `apps/experience/` — work experience with date ranges
- `apps/contact/` — contact form submissions
- `config/` — Django settings, URLs, ASGI

## Testing
```bash
make test         # pytest tests/ -x -q
```
Tests use SQLite in-memory DB (config/test_settings.py). No external services required.
