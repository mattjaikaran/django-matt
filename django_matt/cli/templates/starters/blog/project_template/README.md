# {{ project_name }} Blog API

Full-featured blog API built with [django-matt](https://github.com/mattjaikaran/django-matt).

## Features

- **Posts** — CRUD with draft/publish workflow, tagging, search, pagination
- **Comments** — public commenting with admin approval
- **Auth** — JWT registration, login, token refresh
- **Tags** — tagging system with CRUD

## Quick Start

```bash
# Install dependencies
uv sync

# Run migrations
uv run python manage.py migrate

# Create a superuser
uv run python manage.py createsuperuser

# Start the dev server
uv run python manage.py runserver
```

Visit http://localhost:8000/api/docs for interactive Swagger UI.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login and get JWT tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Get current user (auth required) |
| GET | `/api/posts/` | List published posts |
| GET | `/api/posts/{slug}` | Get single post |
| GET | `/api/posts/search?q=` | Search posts |
| GET | `/api/posts/my` | User's own posts (auth required) |
| POST | `/api/posts/` | Create post (auth required) |
| PATCH | `/api/posts/{slug}` | Update post (auth required) |
| POST | `/api/posts/{slug}/publish` | Publish post (auth required) |
| DELETE | `/api/posts/{slug}` | Delete post (auth required) |
| GET | `/api/tags/` | List tags |
| POST | `/api/tags/` | Create tag (staff only) |
| GET | `/api/comments/?post={id}` | List comments for post |
| POST | `/api/comments/?post={id}` | Create comment |

## Project Structure

```
{{ project_name }}/
├── config/           # Django settings, URL config, ASGI
├── app/              # Main application
│   ├── posts/        # Post models, controllers, schemas
│   ├── comments/     # Comment models, controllers, schemas
│   └── users/        # User model, auth controller, schemas
├── tests/            # pytest tests
├── manage.py
└── pyproject.toml
```

## Testing

```bash
uv run pytest -v
```
