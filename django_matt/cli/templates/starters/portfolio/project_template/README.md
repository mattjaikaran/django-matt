# {{ project_name }} Portfolio API

Portfolio API built with [django-matt](https://github.com/mattjaikaran/django-matt).

## Features

- **Projects** — showcase your work with descriptions, tech stack, links
- **Skills** — categorized skill list with proficiency levels
- **Experience** — work history with dates, descriptions, tech used
- **Contact** — public contact form, admin-only message viewing
- **Auth** — JWT for admin write operations (public endpoints are read-only)

## Quick Start

```bash
# Install dependencies
uv sync

# Run migrations
uv run python manage.py migrate

# Create a superuser (for admin endpoints)
uv run python manage.py createsuperuser

# Start the dev server
uv run python manage.py runserver
```

Visit http://localhost:8000/api/docs for interactive Swagger UI.

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/projects/` | Public | List published projects |
| GET | `/api/projects/{slug}` | Public | Get project detail |
| POST | `/api/projects/` | Staff | Create project |
| PATCH | `/api/projects/{slug}` | Staff | Update project |
| DELETE | `/api/projects/{slug}` | Staff | Delete project |
| GET | `/api/skills/` | Public | List skills |
| POST | `/api/skills/` | Staff | Create skill |
| PATCH | `/api/skills/{id}` | Staff | Update skill |
| DELETE | `/api/skills/{id}` | Staff | Delete skill |
| GET | `/api/experience/` | Public | List experience |
| POST | `/api/experience/` | Staff | Create entry |
| PATCH | `/api/experience/{id}` | Staff | Update entry |
| DELETE | `/api/experience/{id}` | Staff | Delete entry |
| POST | `/api/contact/` | Public | Submit contact form |
| GET | `/api/contact/` | Staff | View messages |

## Project Structure

```
{{ project_name }}/
├── config/           # Django settings, URL config, ASGI
├── app/              # Main application
│   ├── core/         # Base model
│   ├── projects/     # Project models, controllers, schemas
│   ├── skills/       # Skill models, controllers, schemas
│   ├── experience/   # Experience models, controllers, schemas
│   └── contact/      # Contact models, controllers, schemas
├── tests/            # pytest tests
├── manage.py
└── pyproject.toml
```

## Testing

```bash
uv run pytest -v
```
