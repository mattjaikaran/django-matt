# Architecture

Django Matt is a Django meta-framework for building production-ready, large-scale APIs. It prioritizes **performance**, **modularity**, and **developer experience** using the fastest tools available.

## Philosophy: Why This Exists

Django is the most productive web framework in any language. Its ORM, migrations, admin, auth system, and middleware ecosystem represent 20 years of battle-tested solutions to real problems. No other framework comes close to the breadth of what Django ships out of the box.

But Django was designed before async Python, before Pydantic, before type hints were universal, and before Rust-powered tooling made Python 10-100x faster at the edges. Django Matt doesn't replace Django — it builds on top of it, adding the modern patterns and performance characteristics that production APIs demand in 2026.

### The Approach: Rust at the Edges, Python Where It Matters

The fastest Python framework is still slower than the slowest Rust HTTP server. But the bottleneck in real applications is never the framework — it's database queries, network I/O, and business logic. Rewriting Django in Rust would trade the framework's greatest strength (ecosystem, ORM, admin, 20 years of packages) for speed gains on code that doesn't move the needle.

Instead, django-matt uses Rust where it actually helps:

- **Server layer** — Robyn and Granian handle HTTP parsing, connection management, and worker orchestration in compiled Rust, removing Python from the TCP-to-handler hot path
- **Serialization** — orjson (Rust) replaces stdlib json for 3-10x faster response encoding
- **Validation** — Pydantic v2's Rust core handles schema validation at compiled speed
- **Hot paths** — PyO3 native extensions accelerate router dispatch, JWT decoding, and query parsing (1.9x measured E2E speedup)
- **Tooling** — uv (package management), ruff (linting) are Rust-native, making the development loop faster

The result: the full request pipeline from TCP accept to response write is predominantly Rust, while business logic, ORM queries, and the Django ecosystem remain in Python where they're most productive.

### Why Not a Full Rust Rewrite

This was considered and rejected. The analysis:

- **Django's value IS the ecosystem.** ORM, admin, migrations, auth, middleware — all pure Python. Rewriting these in Rust gives speed on things that aren't the bottleneck.
- **Massive scope.** Django is ~250k lines of battle-tested code. Even 20% is person-years of work.
- **Adoption problem.** A "faster Django-like thing" without Django compatibility has to rebuild the entire plugin/package ecosystem from scratch.
- **Diminishing returns.** With Rust extensions on hot paths + Rust-native server, you capture 90%+ of possible performance gains. The remaining wins are in code that runs once per request where Python is fast enough.
- **Prior art.** Robyn (Rust-core Python framework) exists and has traction but hasn't displaced anything — speed isn't what holds Python frameworks back.

The right model is Pydantic v2: keep the Python API that developers love, rewrite the internals in Rust where it measurably matters.

### What Makes This Different

| Framework | Approach | Tradeoff |
|-----------|----------|----------|
| Django | Pure Python, batteries included | Slower on hot paths |
| FastAPI | Modern Python, Pydantic | No ORM, no admin, no migrations, assembly required |
| Django Ninja | Django + Pydantic | Thinner than django-matt, no service layer, no codegen |
| Robyn | Rust server + Python handlers | No Django ecosystem, build everything yourself |
| Axum/Actix | Pure Rust | Different language, different audience |
| **Django Matt** | Django + Pydantic + Rust hot paths + Rust server | Full Django ecosystem with compiled-speed critical paths |

Django Matt's position: **you shouldn't have to choose between Django's productivity and modern performance.** Use Django's ORM, admin, and ecosystem. Get Rust-level speed on the parts that actually matter for latency.

### AI-Native Development

Django Matt is designed to be consumed by AI agents and IDE copilots as much as by human developers:

- **Auto-generated context files** — `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md` are generated from the live project structure, not hand-written
- **Machine-readable introspection** — every route, schema, permission, and model relationship is queryable at runtime
- **Structured error messages** — errors include enough context for an LLM to diagnose and fix without additional exploration
- **Convention over configuration** — strong defaults mean AI tools can predict project structure without scanning every file

A framework that generates its own perfect documentation is a framework that works with AI, not against it.

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

## Service Layer Pattern

Django Matt apps separate concerns into three layers, following the boilerplate pattern proven in production:

### Layer Responsibilities

| Layer | Directory | Responsibility | Pattern |
|-------|-----------|---------------|---------|
| **Presentation** | `controllers/` | HTTP concerns: request parsing, response formatting, permission checks | Thin adapter — delegates all logic |
| **Business** | `services/` | Domain logic, ORM queries, validation, side effects | Extends `CRUDService`, one service per model |
| **Data** | `models/` | Database schema, constraints, model managers | One model per file, UUID PKs, timestamps |

### Controllers → Services → Models

```python
# controllers/post_controller.py — thin HTTP adapter
@api.controller("/posts", tags=["Blog"])
class PostController(APIController):
    def __init__(self):
        self.service = PostService()

    @api.get("/")
    async def list_posts(self, request, page: int = 1):
        items, total = await self.service.list_published(page=page)
        return {"items": items, "total": total}

    @api.post("/")
    async def create_post(self, request, data: PostCreateSchema):
        return await self.service.create(data.model_dump(), user=request.user)

    @api.post("/{id}/publish")
    async def publish_post(self, request, id: int):
        return await self.service.publish(id, user=request.user)
```

```python
# services/post_service.py — all business logic lives here
class PostService(CRUDService["Post"]):
    model = Post

    def get_queryset(self):
        return super().get_queryset().select_related("created_by")

    async def list_published(self, *, page: int = 1, page_size: int = 20):
        return await self.list(
            page=page, page_size=page_size,
            status=Post.Status.PUBLISHED,
            ordering="-published_at",
        )

    async def publish(self, pk: int, user) -> Post:
        post = await self.get(pk)
        if post.status == Post.Status.PUBLISHED:
            raise ConflictError(f"Post {pk} is already published")
        return await self.update(pk, {
            "status": Post.Status.PUBLISHED,
            "published_at": timezone.now(),
        }, user=user)
```

### Why Services?

- **Testable** — test business logic without HTTP infrastructure
- **Reusable** — same service works in controllers, management commands, background tasks, and WebSocket consumers
- **Single responsibility** — controllers handle HTTP, services handle logic
- **Swappable** — inject a mock service in tests or swap implementations without touching controllers

## Naming Conventions

Every Django Matt project follows these conventions for consistency:

### Files

| Type | Convention | Example |
|------|-----------|---------|
| Model files | `{model}.py` | `post.py`, `comment.py` |
| Schema files | `{model}_schema.py` | `post_schema.py` |
| Controller files | `{model}_controller.py` | `post_controller.py` |
| Service files | `{model}_service.py` | `post_service.py` |
| Test files | `test_{model}.py` | `test_post.py` |
| Factory files | `{model}_factory.py` | `post_factory.py` |
| Admin files | `{model}_admin.py` | `post_admin.py` |

### Classes

| Type | Convention | Example |
|------|-----------|---------|
| Models | `PascalCase` | `Post`, `Comment` |
| Schemas | `PascalCase` + `Schema` suffix | `PostSchema`, `CreatePostSchema`, `UpdatePostSchema` |
| Controllers | `PascalCase` + `Controller` suffix | `PostController` |
| Services | `PascalCase` + `Service` suffix | `PostService` |
| Factories | `PascalCase` + `Factory` suffix | `PostFactory` |

### URLs

| Type | Convention | Example |
|------|-----------|---------|
| Collection endpoints | Plural noun | `/posts`, `/users` |
| Single resource | `/{resource_id}` | `/posts/{post_id}` |
| Sub-resource actions | Verb or noun | `/posts/{id}/publish`, `/posts/featured` |
| Nested resources | `/{parent}/{parent_id}/{child}` | `/users/{user_id}/posts` |

### Module Exports

Always export public classes in `__init__.py` so imports stay clean:

```python
# models/__init__.py
from .post import Post
from .comment import Comment

__all__ = ["Post", "Comment"]
```

```python
# controllers/__init__.py
from .post_controller import PostController

__all__ = ["PostController"]
```

This means consuming code imports from the package, not the file:

```python
# Good — import from package
from blog.models import Post
from blog.controllers import PostController
from blog.services import PostService

# Bad — import from file (brittle, bypasses __init__)
from blog.models.post import Post
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

## Request Pipeline

The request pipeline is a layered architecture where each layer can intercept, transform, or short-circuit the request/response cycle:

```
Request → ASGI (uvicorn)
       → Global Middleware (JWT decode, tenant resolution, benchmarking)
       → Route-Scoped Middleware (per-route middleware stacks)
       → Interceptors (pre/post processing, logging, transforms)
       → Router (URL → Controller method)
       → Controller (thin: validation + delegation)
       → Service (business logic, ORM calls)
       → Exception Filters (structured error handling)
       → Response (Pydantic schema → orjson serialization)
```

### Interceptors (`django_matt/interceptors/`)

Interceptors wrap controller execution with pre- and post-processing hooks. Unlike middleware, interceptors have access to the resolved route and controller context:

- **Before interceptors** — run before the handler, can modify the request or short-circuit with an early response
- **After interceptors** — run after the handler, can transform the response
- **Error interceptors** — catch exceptions during handler execution

Interceptors are composable and can be applied globally, per-controller, or per-route.

### Route-Scoped Middleware (`django_matt/middleware/scoped.py`)

Standard Django middleware runs on every request. Route-scoped middleware runs only on matched routes:

- Attach middleware stacks to specific URL patterns or controllers
- Reduce overhead on routes that don't need certain processing (e.g., skip rate limiting on health checks)
- Configure via decorator or router configuration

### Exception Filters (`django_matt/exceptions/`)

Exception filters provide structured error handling with content negotiation:

- Map exception types to HTTP status codes and response formats
- Support custom error renderers per exception class
- Chain multiple filters — first match wins
- Built-in filters for validation errors, permission denied, not found, and throttled

### Layer Responsibilities

| Layer | Responsibility | File |
|-------|---------------|------|
| **Global Middleware** | Cross-cutting concerns (auth, CORS, tenant) | `middleware/*.py` |
| **Route-Scoped Middleware** | Per-route middleware stacks | `middleware/scoped.py` |
| **Interceptor** | Pre/post handler transforms, logging | `interceptors/*.py` |
| **Router** | URL mapping, OpenAPI schema | `urls.py` |
| **Controller** | Request parsing, response formatting, permissions | `controllers/{model}_controller.py` |
| **Service** | Business logic, ORM queries, side effects | `services/{model}_service.py` |
| **Schema** | Input validation, output serialization | `schemas/{model}_schema.py` |
| **Model** | Database structure, constraints | `models/{model}.py` |
| **Exception Filter** | Structured error responses | `exceptions/*.py` |

## Event-Driven Architecture

Django Matt includes a typed event bus and CQRS support for decoupled, event-driven designs.

### Event Bus (`django_matt/events/`)

The event bus provides publish/subscribe semantics with typed events:

- **Typed events** — define events as Pydantic models for validation and serialization
- **Sync and async subscribers** — handlers can be sync or async
- **Ordering** — subscribers execute in priority order
- **Transactional outbox** — optionally defer event dispatch until after transaction commit
- **Multiple backends** — in-process, Redis Pub/Sub, or custom transports

### CQRS (`django_matt/cqrs/`)

Command Query Responsibility Segregation separates read and write models:

- **Command bus** — dispatches write operations through typed command handlers
- **Query bus** — dispatches read operations through typed query handlers
- **Domain events** — commands emit domain events after successful execution
- **Event sourcing ready** — events can be persisted for replay and audit

```python
# Command → Handler → Domain Events → Event Bus → Subscribers
class CreateOrderCommand(Command):
    user_id: UUID
    items: list[OrderItem]

class CreateOrderHandler(CommandHandler[CreateOrderCommand]):
    async def handle(self, command: CreateOrderCommand) -> Order:
        order = await Order.objects.acreate(...)
        await self.emit(OrderCreatedEvent(order_id=order.id))
        return order
```

## Module System

### Plugin Architecture (`django_matt/modules/`)

The module system provides a plugin architecture with dependency resolution and lifecycle hooks:

- **Module declaration** — each module declares its dependencies, exports, and configuration schema
- **Dependency resolution** — modules are loaded in topological order based on declared dependencies
- **Lifecycle hooks** — `on_init`, `on_ready`, `on_shutdown` for setup and teardown
- **Auto-discovery** — modules are discovered from `INSTALLED_APPS` or explicit registration

### Slim Mode (`django_matt/slim.py`, `django_matt/loader.py`)

Slim mode controls which modules are loaded at startup, reducing memory footprint and import time:

- **Full mode** — all modules loaded (default, development)
- **Slim mode** — only modules referenced by the application are loaded
- **Minimal mode** — bare minimum (core, router, auth) for microservices and serverless

```python
# settings.py
MATT_MODE = "slim"  # "full", "slim", or "minimal"
```

The loader reads `MATT_MODE` at startup and only imports/initializes the required module set. Unused modules have zero import cost.

## Streaming and SSE (`django_matt/streaming/`)

Server-Sent Events and streaming response support for real-time data:

- **SSE endpoints** — decorator-based SSE with automatic keepalive and reconnection
- **Streaming responses** — async generator-based streaming for large payloads
- **Event formatting** — automatic SSE wire format (id, event, data, retry fields)
- **Client disconnection** — graceful handling when the client drops the connection

## Observability

### Auto-Instrumentation (`django_matt/observability/auto.py`)

Automatic tracing and metrics collection with zero configuration:

- **Span management** — automatic span creation for requests, DB queries, cache operations, and external HTTP calls
- **Collectors** — pluggable metric collectors for request latency, error rates, and throughput
- **Exporters** — send traces and metrics to OpenTelemetry, Datadog, Sentry, or custom backends
- **Context propagation** — trace context flows through async boundaries and background tasks

Auto-instrumentation activates on startup and requires no code changes in controllers or services.

## Security

### Secrets Management (`django_matt/secrets/`)

Pluggable secrets backend for managing sensitive configuration:

- **Pluggable backends** — environment variables, AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager
- **Lazy loading** — secrets are fetched on first access and cached
- **Rotation support** — automatic refresh when secrets approach expiration
- **Audit trail** — log which secrets were accessed and by which component

### Infrastructure Introspection (`django_matt/introspection/`)

Runtime introspection of the application's infrastructure and configuration:

- **Health checks** — database, cache, storage, and external service connectivity
- **Route listing** — enumerate all registered routes with their handlers and middleware
- **Configuration dump** — export resolved configuration (with secrets redacted)
- **Dependency graph** — visualize module dependencies

## Serialization Groups (`django_matt/serialization/`)

Context-aware field selection for schema serialization:

- **Groups** — define field groups (`"list"`, `"detail"`, `"admin"`) on schemas
- **Automatic selection** — views auto-select the appropriate group based on the operation
- **Custom groups** — define arbitrary groups for specialized use cases

## RPC Typed Client (`django_matt/rpc/`)

Type-safe inter-service communication:

- **Typed client generation** — generate Python clients from OpenAPI schemas
- **Async HTTP transport** — built on `httpx` with connection pooling and retries
- **Service discovery** — resolve service URLs from configuration or service registry

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

Django Matt supports multiple production server backends, from the traditional gunicorn+uvicorn stack to Rust-native servers:

### Server Backends

| Backend | Language | Protocol | Best For |
|---------|----------|----------|----------|
| **gunicorn + uvicorn** | Python | ASGI | Mature, well-understood, widest hosting support |
| **Granian** | Rust | ASGI/RSGI | HTTP/2, low latency, drop-in replacement |
| **Robyn** | Rust | ASGI | Lowest overhead, zero-copy responses |

### Default: gunicorn + uvicorn

```
nginx → gunicorn → uvicorn workers → Django (ASGI)
```

```bash
gunicorn config.asgi:application \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000
```

### Granian (Rust-native)

```bash
granian config.asgi:application \
    --interface asgi \
    --workers 4 \
    --host 0.0.0.0 \
    --port 8000
```

### Robyn (Rust-native)

```bash
# Via django-matt CLI (planned)
python manage.py serve --server robyn --workers 4
```

The `matt serve` command (planned) auto-detects the best available server and provides a unified interface regardless of backend.

## See Also

- [Scaffolding Workflow](scaffolding.md) — How to create and fill app structures
- [startapp](startapp.md) — App scaffolding command
- [generate_crud](crud-generator.md) — CRUD code generator
- [Quick Start](getting-started/quickstart.md) — Get running in 5 minutes
- [Visual Diagrams](diagrams.md) — Mermaid diagrams for all architectural layers
