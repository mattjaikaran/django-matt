# Architecture

Django Matt is a Django meta-framework for building production-ready, large-scale APIs. It prioritizes **performance**, **modularity**, and **developer experience** using the fastest tools available.

## Core Principles

### 1. Small Files, Modular by Default

**No file should exceed 500 lines.** This is enforced by convention and scaffolding:

- **One model per file.** `models/post.py`, never a monolithic `models.py`.
- **One controller per file.** `controllers/post_controller.py`.
- **One schema set per file.** `schemas/post_schema.py`.
- **One admin config per file.** `admin/post_admin.py`.
- **One service per file.** `services/post_service.py`.
- **One test module per model.** `tests/test_post.py`.

The `startapp` and `generate_crud` commands create this structure automatically. There is no path to a 3000-line `views.py` — the package structure makes it structurally impossible.

**Why this matters:**
- Git diffs stay clean — changes to one model don't touch other models
- New developers navigate the codebase immediately
- Code review is faster — reviewers see exactly what changed
- Merge conflicts are rare — files don't overlap

### 2. Async-First

Every controller, service, and ORM call is async by default:

```python
# Controllers are async
@get("")
async def list_posts(self, request): ...

# Services use async ORM
async def get_by_id(post_id):
    return await Post.objects.aget(id=post_id)

# Never block the event loop
# Bad:  Post.objects.get(id=post_id)
# Good: await Post.objects.aget(id=post_id)
```

Sync fallbacks must use `sync_to_async()`.

### 3. Rust-Powered Toolchain

Django Matt uses Rust-based tools at every level for maximum speed:

| Tool | Replaces | Speedup |
|------|----------|---------|
| **uv** | pip, poetry | 10-100x faster installs |
| **ruff** | flake8, black, isort | 100x faster linting |
| **orjson** | stdlib json | 3-10x faster serialization |
| **Pydantic v2** | manual validation | Rust core via pydantic-core |
| **uvicorn** | gunicorn (WSGI) | Async with uvloop |

These aren't optional — they're the defaults. Generated code imports `orjson` directly. The linter is ruff. Package management is uv.

### 4. Convention Over Configuration

Django Matt provides strong defaults:

- UUID primary keys on all models
- Timestamps (`created_at`, `updated_at`) on all models
- Service layer for business logic (controllers stay thin)
- Pydantic schemas for all request/response validation
- Factory Boy for test data
- pytest for testing

You can override any of these, but the defaults get you to production fast.

## App Structure

Every Django Matt app follows the same package layout:

```
myapp/
├── __init__.py
├── apps.py
├── urls.py                    # APIRouter with registered controllers
├── models/
│   ├── __init__.py            # Re-exports all models
│   └── {model}.py             # One model per file
├── schemas/
│   ├── __init__.py            # Re-exports all schemas
│   └── {model}_schema.py      # Schema, CreateSchema, UpdateSchema
├── controllers/
│   ├── __init__.py            # Re-exports all controllers
│   └── {model}_controller.py  # Async CRUD endpoints
├── admin/
│   ├── __init__.py            # Re-exports all admin classes
│   └── {model}_admin.py       # Django admin config
├── services/
│   ├── __init__.py            # Re-exports all services
│   └── {model}_service.py     # Business logic
├── tests/
│   ├── __init__.py
│   ├── test_{model}.py        # Model + API tests
│   └── factories/
│       ├── __init__.py
│       └── {model}_factory.py # Factory Boy factories
├── utils/
│   └── __init__.py
└── management/
    └── commands/
        └── __init__.py
```

Create this structure with one command:

```bash
python manage.py startapp myapp --models Product Category
```

## Project Architecture Patterns

Django Matt supports multiple project architectures:

### API-Only (Most Common)

Django backend serving JSON. Frontend is a separate app (React, Next.js, Swift, etc.).

```
myproject/
├── config/              # Django settings, ASGI config
├── apps/
│   ├── users/           # User management
│   ├── products/        # Product domain
│   └── orders/          # Order domain
├── frontend/            # Separate React/Next.js app
└── manage.py
```

### Monorepo

Multiple services and frontends in one repo:

```
myproject/
├── server/              # Django API
│   ├── config/
│   └── apps/
├── web/                 # Next.js frontend
├── mobile/              # React Native / Swift
├── docs/                # API documentation
└── shared/              # Shared types, configs
```

### Django + HTMX

Server-rendered with progressive enhancement:

```
myproject/
├── config/
├── apps/
│   └── pages/           # HTMX-powered views
├── templates/           # Django templates with HTMX
├── static/
│   └── css/             # Tailwind CSS
└── manage.py
```

### B2B SaaS

Multi-tenant with organizations, teams, and billing:

```bash
python manage.py startapi myproject --template b2b --auth jwt --docker
```

## Request Flow

```
Request → ASGI (uvicorn)
       → Middleware (JWT decode, tenant resolution, benchmarking)
       → Router (URL → Controller method)
       → Controller (thin: validation + delegation)
       → Service (business logic, ORM calls)
       → Response (Pydantic schema → orjson serialization)
```

### Layer Responsibilities

| Layer | Responsibility | File |
|-------|---------------|------|
| **Router** | URL mapping, OpenAPI schema | `urls.py` |
| **Controller** | Request parsing, response formatting, permissions | `controllers/{model}_controller.py` |
| **Service** | Business logic, ORM queries, side effects | `services/{model}_service.py` |
| **Schema** | Input validation, output serialization | `schemas/{model}_schema.py` |
| **Model** | Database structure, constraints | `models/{model}.py` |

## Performance Architecture

Django Matt is optimized for high-throughput production workloads:

- **orjson** for JSON serialization (3-10x faster than stdlib)
- **Pydantic v2** with Rust core for schema validation
- **Connection pooling** via psycopg3 pool (enabled by default in production)
- **Cached type hints** — `get_type_hints()` cached at registration time, never per-request
- **Cached field introspection** — `_meta.fields` cached in `__init__` as frozenset
- **Single-pass JWT** — token decoded once in middleware, payload passed through
- **`model_construct()`** for list serialization — skips re-validation on ORM objects

## ASGI Production Stack

```
nginx → gunicorn → uvicorn workers → Django (ASGI)
```

```bash
gunicorn config.asgi:application \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000
```

## See Also

- [Scaffolding Workflow](scaffolding.md) — How to create and fill app structures
- [startapp](startapp.md) — App scaffolding command
- [generate_crud](crud-generator.md) — CRUD code generator
- [Quick Start](getting-started/quickstart.md) — Get running in 5 minutes
