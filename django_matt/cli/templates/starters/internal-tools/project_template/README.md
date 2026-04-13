# {{ project_name }}

Internal tools and dashboard built with [django-matt](https://github.com/mattjaikaran/django-matt).

## Features

- Django Unfold admin dashboard
- SSO/SAML authentication (configurable)
- Audit logging for all write operations
- Feature flags with gradual rollout
- Analytics tracking

## Quick Start

```bash
uv sync
docker compose up db redis -d
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

## Admin Dashboard

Visit `http://localhost:8000/admin/` after creating a superuser.

## Testing

```bash
uv run pytest tests/ -x -q
```
