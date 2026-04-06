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

### Slim Mode (`django_matt/slim.py`, `django_matt/loader.py`, `django_matt/startup.py`)

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
- [Visual Diagrams](diagrams.md) — Mermaid diagrams for all architectural layers
