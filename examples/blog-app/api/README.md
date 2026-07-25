# blog-api

A production-quality blog backend built with [django-matt](https://github.com/mattjaikaran/django-matt).

Demonstrates: JWT auth, full-text search, RSS feed, SEO endpoints, threaded comments, view tracking, draft/publish workflow, and TypeScript codegen.

## Tech Stack

| Layer | Choice |
|---|---|
| Framework | django-matt (Django 5.2+, async-first) |
| Auth | JWT (access + refresh tokens) |
| Database | PostgreSQL 16 with full-text search |
| Server | uvicorn (ASGI) |
| Package manager | uv |
| Admin | Django Unfold |

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | — | Register new user |
| POST | `/api/auth/login` | — | Login, receive JWT tokens |
| POST | `/api/auth/refresh-token` | — | Refresh access token |
| GET | `/api/auth/me` | ✓ | Get current user |
| PUT | `/api/auth/update-profile` | ✓ | Update profile |
| GET | `/api/authors` | — | List authors |
| GET | `/api/authors/{username}` | — | Author detail |
| GET | `/api/posts` | — | List published posts (filter by category/tag/author/featured) |
| GET | `/api/posts/{slug}` | — | Post detail (auto-tracks views) |
| GET | `/api/posts/{slug}/seo` | — | SEO metadata for frontend `<head>` |
| GET | `/api/posts/search?q=...` | — | Full-text search |
| POST | `/api/posts` | ✓ | Create post |
| PUT | `/api/posts/{slug}` | ✓ | Update post |
| POST | `/api/posts/{slug}/publish` | ✓ | Publish draft |
| DELETE | `/api/posts/{slug}` | ✓ | Delete post |
| GET | `/api/posts/my-posts` | ✓ | Author's own posts (all statuses) |
| GET | `/api/tags` | — | List tags |
| GET | `/api/tags/{slug}` | — | Tag detail |
| POST | `/api/tags` | staff | Create tag |
| GET | `/api/categories` | — | List categories |
| GET | `/api/categories/{slug}` | — | Category detail |
| POST | `/api/categories` | staff | Create category |
| GET | `/api/posts/{slug}/comments` | — | List comments for a post |
| POST | `/api/posts/{slug}/comments` | optional | Add comment (auth optional) |
| PUT | `/api/posts/{slug}/comments/{id}` | ✓ | Edit own comment |
| DELETE | `/api/posts/{slug}/comments/{id}` | ✓ | Delete own comment |
| GET | `/feed/rss/` | — | RSS feed (latest 20 posts) |

Interactive docs: `http://localhost:8000/api/docs`

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16+ (or use Docker)

### Local setup

```bash
# 1. Clone and enter
cd examples/blog-api

# 2. Install dependencies
make install

# 3. Copy env
cp .env.example .env
# Edit DATABASE_URL and JWT_SECRET_KEY

# 4. Run migrations and seed
make migrate
make seed

# 5. Start server
make dev
```

### Docker setup (zero dependencies)

```bash
cp .env.example .env
make docker-up

# In another terminal:
docker-compose exec web uv run python manage.py migrate
docker-compose exec web uv run python manage.py seed_blog
```

Server: `http://localhost:8000`
Docs:   `http://localhost:8000/api/docs`
Admin:  `http://localhost:8000/admin/`
RSS:    `http://localhost:8000/feed/rss/`

Seed credentials: `author@example.com` / `password123`

## Generate TypeScript types

After starting the server, run from the django-matt repo:

```bash
python manage.py sync_types --target typescript --output ../blog-frontend/src/types
```

This generates:
- `types/blog.ts` — TypeScript interfaces for all schemas
- `types/blog.zod.ts` — Zod validation schemas
- `types/blog.hooks.ts` — React Query hooks

## Project Structure

```
blog-api/
├── blog/
│   ├── api.py              # DjangoMattAPI entry point + controller registration
│   ├── posts/
│   │   ├── models.py       # Post, Tag, Category, PostView
│   │   ├── schemas.py      # Pydantic request/response schemas
│   │   ├── controllers.py  # PostController, TagController, CategoryController
│   │   ├── services.py     # Business logic (search, view tracking, publish)
│   │   ├── feeds.py        # RSS + Atom feeds
│   │   └── admin.py
│   ├── users/
│   │   ├── models.py       # User (UUID pk), AuthorProfile
│   │   ├── schemas.py
│   │   ├── controllers.py  # AuthController, AuthorController
│   │   └── admin.py
│   └── comments/
│       ├── models.py       # Comment (threaded, auth optional)
│       ├── schemas.py
│       ├── controllers.py
│       └── admin.py
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── pyproject.toml
```

## Pairing with a Frontend

This API is designed to be paired with `examples/blog-frontend/` (React + Vite).

Key integration points:
- **CORS**: Set `CORS_ALLOWED_ORIGINS` in `.env` to your frontend origin
- **JWT**: Store `access` token in memory, `refresh` token in an httpOnly cookie or localStorage
- **Types**: Run `sync_types` to keep frontend types in sync with API schemas
- **SEO**: Use `/api/posts/{slug}/seo` to populate `<head>` meta tags on the frontend

## Testing

```bash
make test
make test-cov
```
