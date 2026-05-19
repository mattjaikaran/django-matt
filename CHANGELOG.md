# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- LLM-optimized error responses: `code`, `hint`, `docs_url` fields in error envelope
- Starter templates: `--template ai-saas` and `--template marketplace`
- Benchmark CI job with PR commenting
- Docs version switcher (mike plugin)

### Fixed
- Deprecated `datetime.utcnow()` → `datetime.now(UTC)` across tasks, livewire, files
- Deprecated `asyncio.get_event_loop()` → `asyncio.get_running_loop()` / `async_to_sync()` in ml, files
- Public API docstring example corrected (`api.register_controller()` pattern)
- `matt_analyze` command handles missing `BASE_DIR` setting gracefully
- All broken documentation links resolved
- Ruff lint warnings fixed (quoted annotations, unused imports)

---

## [0.9.0] - 2026-05-19

### Added

**Stage 17A — Native Task Engine** (`django_matt/tasks_native/`) — complete

- `@task` decorator for registering background tasks with Pydantic-validated payloads
- `TaskConfig` — per-task configuration: queue, priority, timeout, max_retries
- `RetryPolicy` — linear, exponential backoff, jitter, and fixed-delay strategies
- `ScheduledTask` model — periodic task definitions with cron/interval expressions
- `TaskResult` model — persistent result storage with status tracking
- `TaskBeat` scheduler — APScheduler-based periodic runner (no Celery Beat dependency)
- Unfold admin dashboard — real-time task status via WebSocket, queue depth charts, retry controls
- Conditional loading and tree-shaking — only active when `"django_matt.tasks_native"` is in `INSTALLED_APPS`
- Backends: in-process threading (default), Celery, Dramatiq, Django-Q2, sync (testing)
- CLI commands:
  - `python manage.py matt_tasks list` — list all registered tasks
  - `python manage.py matt_tasks run <task_name> '<json>'` — run a task manually
  - `python manage.py matt_tasks status` — show queue depth and worker status
  - `python manage.py matt_tasks purge --older-than <duration>` — purge old results

**Stage 17B — AI-Assisted Codebase Audits** (`django_matt/audits/`)

- `AuditFramework` class with pluggable `AuditLens` protocol
- Security audit lens: OWASP top-10, SQL injection, exposed secrets, auth gaps
- Performance audit lens: N+1 queries, missing indexes, slow views, cache misses
- Bundle audit lens: frontend bundle analysis, dead code, large dependencies
- Pre-built LLM prompt templates (`audits/prompts/`)
- `AuditAgent` — MCP tool definitions for AI agent integration (`audits/agents/`)
- CLI commands:
  - `python manage.py matt_audit` — run all audit lenses
  - `python manage.py matt_audit security --level strict`
  - `python manage.py matt_audit bundle`
  - `python manage.py matt_audit context --for claude` — generate `CLAUDE.md` / `.cursorrules` from live codebase state

**TypeScript Codegen fixes** (`django_matt/typegen/`)

- Python 3.10+ `X | None` union syntax now correctly emits `string | null` (was broken for non-`Optional` unions)
- `EmailStr` fields now map to `string` in TypeScript output (was emitting `EmailStr` literally)
- Inherited field resolution uses `get_type_hints()` instead of `__annotations__` — fields from parent Pydantic models are now included in generated interfaces

**Docs: Recipes Cookbook** (`docs/recipes/`)

Nine end-to-end cookbook recipes covering real-world patterns:
- `auth-flows.md` — JWT login, magic links, OAuth, SSO, passkey registration
- `file-uploads.md` — local/S3/R2 uploads, image processing, signed URLs
- `background-tasks.md` — `@task` decorator, retry policies, periodic scheduling
- `pagination-filtering.md` — PageNumber/LimitOffset/Cursor pagination, FilterSet
- `multi-tenancy.md` — org/team/membership setup, tenant middleware, scoped queries
- `webhooks.md` — incoming webhook verification, outgoing webhook delivery
- `rate-limiting.md` — per-user/per-key/per-IP throttling, Redis sliding window
- `testing-patterns.md` — `AsyncAPITestClient`, factories, assertion helpers
- `frontend-integration.md` — `sync_types` workflow, Zod schemas, React hooks

**Docs: Migration Guides** (`docs/migrations/`)

Three comprehensive migration guides:
- `from-drf.md` — serializer → Pydantic schema, ViewSet → APIViewSet, simplejwt → built-in auth
- `from-fastapi.md` — Starlette routing → MattAPI, Depends → built-in DI, SQLAlchemy → Django ORM
- `from-ninja.md` — NinjaAPI → MattAPI, ninja-extra → APIController, ninja-jwt → AuthController

**Examples**

- `examples/blog-app/` — full-stack blog: Django API + React/Vite frontend with TanStack Router, Zustand, shadcn/ui; committed `sync_types` output (`generated.ts` and `generated.schemas.ts`) as codegen reference
- `examples/portfolio-api/` + `examples/portfolio-frontend/` — personal portfolio backend + React frontend with contact form
- `examples/ecommerce-v2/` — multi-store marketplace with React/TypeScript frontend (replaces `ecommerce-api`)

### Fixed

- `typegen`: `X | None` (PEP 604 unions) were not detected as optional — only `Optional[X]` was handled
- `typegen`: `EmailStr` was passed through as-is instead of resolving to `string`
- `typegen`: subclasses of Pydantic models with fields defined on a parent class generated empty interfaces
- Blog example app: comment thread rendering, Swagger docs prefix, Docker Compose wiring
- Ecommerce v2: orders flow, payment mock, cart storeId, async middleware, CORS, and migrations

---

## [0.1.0] - 2026-03-09

v1.0 Milestone — 54 modules, 2100+ tests. Full audit, hardening, and completion pass across all modules (7 phases, 24 plans).

### Added

- **Core framework**: `MattAPI`, `APIRouter`, `APIController`, `CRUDController`, `ModelSchema`, HTTP method decorators, single-pass `_setup_methods()`, `from_orm_fast()` list serialization, orjson as base dependency
- **Authentication**: JWT (access/refresh/blacklist, `@jwt_required`/`@jwt_optional`), session + CSRF, API keys with rate limiting, magic links, OAuth (Google/GitHub/Apple/Microsoft), Passkeys/WebAuthn, Enterprise SSO (SAML 2.0, OIDC)
- **RBAC**: `Role`/`Permission` models with hierarchy, `HasRole`/`HasPermission` permission classes, `@requires_role()`/`@requires_permission()` decorators
- **Multi-tenancy**: `Organization`, `Team`, `Membership`, `Invitation` models, `TenantMiddleware`, org-aware permission classes, cross-org data isolation
- **CRUD views**: `ListView`, `CreateView`, `ReadView`, `UpdateView`, `PatchView`, `DeleteView`, `APIViewSet`; auto `optimize_queryset()` with select_related/prefetch_related detection
- **Billing**: Stripe (checkout, subscriptions, customer portal, webhooks), PayPal, Polar; webhook signature verification; billing signals
- **Background tasks abstraction**: `@task` decorator with Celery, Dramatiq, Django-Q2, and sync backends; periodic cron scheduling
- **File handling**: local, S3, R2, MinIO storage backends; `@file_upload` decorator; image processing helpers
- **Type generation**: TypeScript interfaces + Zod schemas; Swift Codable structs; `sync_types` with watch mode
- **CLI**: `startapi`, `generate_crud`, `sync_types`, `config`, `deploy`; migration tools (`matt_baseline`, `matt_migrate --profile/--parallel`, `matt_squash`)
- **Testing utilities**: `APITestClient`, `AsyncAPITestClient` (with `force_authenticate()` via `acreate_access_token()`); `UserFactory`, `OrganizationFactory`; `assert_status()`, `assert_query_count()`
- **Advanced modules** (54 total): `streaming/` (SSE/NDJSON), `events/` (async pub/sub), `exceptions/` (typed filters), `serialization/` (group-based visibility), `secrets/` (multi-backend), `introspection/` (health/readiness probes), `rpc/` (typed client gen), `modules/` (plugin system), `cqrs/` (command/query buses), `migration_tools/`, `flags/`, `analytics/`, `experiments/`, `graphql/`, `websockets/`, `htmx/`, `components/`, `ai/`, `ml/`, `messaging/`, `notifications/`, `email/`, `interceptors/`, `versioning/`, `throttling/`, `observability/`, `di/`, `audit/`, `openapi/`, `inspector/`; slim/minimal module loading (`slim.py`, `loader.py`)
- **Admin integration** (Django Unfold): `MattModelAdmin`, dashboard widgets, custom admin pages
- **Pagination & filtering**: `PageNumberPagination`, `LimitOffsetPagination`, `CursorPagination`; `FilterSet`, search, ordering backends
- **Dependency injection**: `Container` with Singleton/Scoped/Transient lifetimes, `Depends()`, `@inject`
- **Content negotiation**: JSON, XML, CSV, YAML, MessagePack, HTML renderers and parsers
- **OpenAPI / Interactive docs**: Swagger UI at `/docs`, ReDoc at `/redoc`, API playground at `/_matt/docs/playground/`
- **Performance**: `FastJSONRenderer`, `@cache_response()` with stampede prevention, `QueryAnalyzer` (N+1 detection), `APIBenchmark`

### Changed

- Python 3.12+ minimum (3.13 recommended)
- Django 5.2+ minimum (6.0 compatible)
- Pydantic 2.0+ required
- Replaced black/isort with Ruff (line-length 88, py313 target)
- All deprecated `datetime.utcnow()` replaced with `datetime.now(UTC)`
- All deprecated `asyncio.get_event_loop()` replaced with `asyncio.to_thread()`
- orjson used everywhere instead of stdlib json

### Fixed

- `CONN_MAX_AGE=0` enforced across all ASGI deployment configs — production connection leak blocker (Django ticket #33497)
- `TracingMiddleware` was incorrectly marking 4xx responses as OTEL ERROR status
- Removed `DJANGO_ALLOW_ASYNC_UNSAFE=true` — all sync ORM calls converted to async equivalents
- Consolidated error classes: `django_matt.core.errors` is single canonical import (eliminated `utils/errors.py` duplication)
- `AsyncAPITestClient.force_authenticate()` now uses `acreate_access_token()`
- `PATCH` null semantics corrected using `model_fields_set` sentinel
- S3 storage backend using deprecated `asyncio.get_event_loop()`
- PayPal webhook test missing required transmission headers
- `_get_push_tokens` app_label bug (`"notifications"` → `"django_matt"`)
- Admin inline generation: `AdminGenerator._generate_inlines()` auto-creates `TabularInline` from reverse FK relations
- Soft-delete integration with audit trail — delete/restore operations produce audit log entries
