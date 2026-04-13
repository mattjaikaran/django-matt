# {{ project_name }}

Pure API backend built with [django-matt](https://github.com/mattjaikaran/django-matt).

## Quick Start

```bash
# Install dependencies
uv sync

# Run migrations
uv run python manage.py migrate

# Start dev server
uv run python manage.py runserver
```

## With Docker

```bash
docker compose up -d
docker compose exec api python manage.py migrate
```

## Testing

```bash
uv run pytest tests/ -x -q
```

## API Endpoints

- `GET /api/health/` — Health check
- `GET /api/items/` — List items (auth required)
- `POST /api/items/create/` — Create item (auth required)
- `GET /api/items/<id>/` — Get item (auth required)
- `PATCH /api/items/<id>/update/` — Update item (auth required)
- `DELETE /api/items/<id>/delete/` — Delete item (auth required)
