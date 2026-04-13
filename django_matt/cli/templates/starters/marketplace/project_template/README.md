# {{ project_name }}

Multi-vendor marketplace built with [django-matt](https://github.com/mattjaikaran/django-matt).

## Features

- Multi-vendor stores (multitenancy)
- Product listings with search
- Review and rating system
- Stripe Connect for vendor payouts
- File uploads for product images

## Quick Start

```bash
uv sync
docker compose up db redis -d
uv run python manage.py migrate
uv run python manage.py runserver
```

## Testing

```bash
uv run pytest tests/ -x -q
```
