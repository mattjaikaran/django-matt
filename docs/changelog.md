# Changelog

All notable changes to django-matt are documented in this file.

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

#### Stage 17A: Native Task Engine (`tasks_native`) — Complete

- `@task` decorator for registering background tasks with Pydantic-validated payloads
- `TaskConfig` — per-task configuration: queue, priority, timeout, max_retries
- `RetryPolicy` — configurable retry strategies: linear, exponential backoff, jitter, fixed delay
- `ScheduledTask` model — periodic task definitions with cron/interval expressions
- `TaskResult` model — persistent task result storage with status tracking
- `TaskBeat` scheduler — APScheduler-based periodic task runner (no Celery Beat dependency)
- Unfold admin dashboard — real-time task status via WebSocket, queue depth charts, retry controls
- Conditional loading and tree-shaking — only active when `"django_matt.tasks_native"` is in `INSTALLED_APPS`
- Backends: in-process threading (default), Celery, Dramatiq, Django-Q2, sync (testing)
- CLI commands:
  - `python manage.py matt_tasks list` — list all registered tasks
  - `python manage.py matt_tasks run <task_name> '<json>'` — run a task manually
  - `python manage.py matt_tasks status` — show queue depth and worker status
  - `python manage.py matt_tasks purge --older-than <duration>` — purge old results

#### Stage 17B: AI-Assisted Codebase Audits (`audits`)

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

#### Typegen Fixes (`typegen/`)

- Python 3.10+ `X | None` union syntax now correctly emits `string | null` (was broken for non-`Optional` unions)
- `EmailStr` fields now map to `string` in TypeScript output (was emitting `EmailStr` literally)
- Inherited field resolution uses `get_type_hints()` instead of `__annotations__` — fields from parent Pydantic models are now included in generated interfaces

#### Docs: Recipes Cookbook (`docs/recipes/`)

Nine new end-to-end cookbook files covering real-world patterns:
- `auth-flows.md` — JWT login, magic links, OAuth, SSO, passkey registration
- `file-uploads.md` — local/S3/R2 uploads, image processing, signed URLs
- `background-tasks.md` — `@task` decorator, retry policies, periodic scheduling
- `pagination-filtering.md` — PageNumber/LimitOffset/Cursor pagination, FilterSet
- `multi-tenancy.md` — org/team/membership setup, tenant middleware, scoped queries
- `webhooks.md` — incoming webhook verification, outgoing webhook delivery
- `rate-limiting.md` — per-user/per-key/per-IP throttling, Redis sliding window
- `testing-patterns.md` — `AsyncAPITestClient`, factories, assertion helpers
- `frontend-integration.md` — `sync_types` workflow, Zod schemas, React hooks

#### Docs: Migration Guides (`docs/migrations/`)

Three comprehensive migration guides:
- `from-drf.md` — serializer → Pydantic schema, ViewSet → APIViewSet, simplejwt → built-in auth
- `from-fastapi.md` — Starlette routing → MattAPI, Depends → built-in DI, SQLAlchemy → Django ORM
- `from-ninja.md` — NinjaAPI → MattAPI, ninja-extra → APIController, ninja-jwt → AuthController

#### Examples

- `examples/blog-app/` — full-stack blog: Django API + React/Vite frontend with TanStack Router, Zustand, shadcn/ui; committed `sync_types` output (`generated.ts` and `generated.schemas.ts`) as a codegen reference
- `examples/portfolio-api/` + `examples/portfolio-frontend/` — personal portfolio backend + React frontend with contact form
- `examples/ecommerce-v2/` — multi-store marketplace with React/TypeScript frontend (replaces `ecommerce-api`)

### Fixed

- `typegen`: `X | None` (PEP 604 unions) were not detected as optional — only `Optional[X]` was handled
- `typegen`: `EmailStr` was passed through as-is instead of resolving to `string`
- `typegen`: subclasses of Pydantic models with fields defined on a parent class generated empty interfaces
- Blog example app: comment thread rendering, Swagger docs prefix (`/api`), Docker Compose wiring for local dev
- Ecommerce v2: orders flow, payment mock, cart storeId, async middleware, CORS, and migrations

---

## [0.1.0] - 2026-03-09

v1.0 Milestone — 54 modules, 2100+ tests. Full audit, hardening, and completion pass (7 phases, 24 plans).

### Added

#### Core Framework

- `MattAPI` — main API class with OpenAPI generation
- `APIRouter` — modular routing with tags and prefixes
- `APIController` — class-based controllers with dependency injection
- `CRUDController` — pre-built CRUD operations
- `ModelSchema` — automatic Pydantic schemas from Django models
- HTTP method decorators: `@get`, `@post`, `@put`, `@patch`, `@delete`
- Single-pass `_setup_methods()` — DI + error handling wrapped in one closure per route
- `from_orm_fast()` — list serialization via `model_construct()` (no re-validation overhead)
- orjson as a base dependency — used in router, controller, and views

#### Authentication

- JWT: access/refresh tokens, blacklisting, `@jwt_required`/`@jwt_optional`, `AuthController`
- Session auth with CSRF protection; API keys with per-key rate limiting and rotation
- Magic links (time-limited signed login links)
- OAuth providers: Google, GitHub, Apple, Microsoft
- Passkeys/WebAuthn: `PasskeyController`, `PasskeyCredential` model
- Enterprise SSO: SAML 2.0, OIDC with PKCE; Okta, Azure AD, Google Workspace, Auth0, OneLogin

#### RBAC

- `Role` and `Permission` models with hierarchy support
- `HasRole`, `HasPermission` permission classes
- `@requires_role()`, `@requires_permission()` decorators

#### Multi-Tenancy

- `Organization`, `Team`, `Membership`, `Invitation` models
- `TenantMiddleware`, `OrganizationController`, `TeamController`
- `@requires_org_membership` decorator; cross-org data isolation enforcement

#### Views & Permissions

- `ListView`, `CreateView`, `ReadView`, `UpdateView`, `PatchView`, `DeleteView`, `APIViewSet`
- `AllowAny`, `IsAuthenticated`, `IsAdmin`, `IsStaff`, `IsSuperUser`, `IsOwner`, `HasRole`, `HasPermission`
- Auto `optimize_queryset()` — detects FK/M2M from schema, applies select_related/prefetch_related

#### Billing

- Stripe: checkout sessions, subscriptions, customer portal, webhooks, invoices
- PayPal: subscription plans, payment processing, webhooks
- Polar: modern billing API, subscription management
- Webhook signature verification; billing signals (`subscription_created`, `subscription_updated`, `subscription_canceled`)
- Mock event factories for billing webhook testing (`django_matt.billing.testing`)

#### Background Tasks (Abstraction Layer)

- `@task` decorator with Celery, Dramatiq, Django-Q2, and sync backends
- Periodic task support with cron-style scheduling

#### File Handling

- Storage backends: local filesystem, Amazon S3, Cloudflare R2, MinIO
- `UploadedFile` type, `@file_upload` decorator, image processing helpers

#### Type Generation

- TypeScript: Pydantic → interfaces, Zod schemas, API client, enums
- Swift: Pydantic → Codable structs, API client, enums
- `python manage.py sync_types` with watch mode

#### Performance

- `FastJSONRenderer` (orjson/ujson), `MessagePackRenderer`, `StreamingJsonResponse`
- `@cache_response()`, `@cache_result()`, `DistributedCacheManager` (Redis clusters, stampede prevention)
- `QueryAnalyzer` (N+1 detection), `optimize_queryset()`, `PerformanceSuggester`
- `APIBenchmark`, `BenchmarkMiddleware`

#### Pagination & Filtering

- `PageNumberPagination`, `LimitOffsetPagination`, `CursorPagination`
- `FilterSet` with Char, Integer, Boolean, Date, DateTime, and In filters
- `SearchBackend`, `PostgresSearchBackend`, `OrderingBackend`

#### Dependency Injection

- `Container` with Singleton, Scoped, Transient lifetimes
- `Depends()`, `@inject`, built-in providers: `CurrentUser`, `CurrentRequest`, `CurrentOrg`
- `DependencyInjectionMiddleware`

#### Admin Integration (Unfold)

- `MattModelAdmin`, `MattStackedInline`, `MattTabularInline`, `@register_admin()`
- Mixins: `AuditAdminMixin`, `SoftDeleteAdminMixin`, `MultiTenantAdminMixin`, `ExportAdminMixin`
- Dashboard: `StatWidget`, `ChartWidget`, `TableWidget`, `model_stat_widget()`, `auto_dashboard()`
- Custom admin pages: `AdminPage`, `AdminPageGroup`, `@pages.register()`

#### Advanced Modules (54 total)

- `streaming/` — SSE responses, NDJSON streaming, heartbeat helpers
- `events/` — async event bus (pub/sub, `@on` decorator, InMemory/Redis backends)
- `exceptions/` — `ExceptionFilter`, `@catch`, global exception registry
- `serialization/` — group-based field visibility (`Grouped`, `Secret`, `@serialize_for`)
- `secrets/` — env, Vault, AWS Secrets Manager, GCP Secret Manager, dotenv backends
- `introspection/` — health checks, readiness/liveness probes, infra reporting
- `rpc/` — typed HTTP client generation (Python + TypeScript)
- `modules/` — plugin system with dependency resolution and lifecycle hooks
- `cqrs/` — Command/Query buses, domain events, bus middleware
- `migration_tools/` — SQL baselines, parallel migration execution, profiling, squashing
- `flags/` — feature flags (DB, Redis, LaunchDarkly, Unleash)
- `analytics/` — event tracking, sessions, funnels, multiple backends
- `experiments/` — A/B testing, multi-armed bandits, statistical analysis
- `graphql/` — Strawberry-based schema generation, dataloaders
- `websockets/`, `htmx/`, `components/`, `ai/`, `ml/`, `messaging/`, `notifications/`, `email/`
- `interceptors/` — route-scoped middleware (before/after hooks, `@intercept`)
- `versioning/`, `throttling/`, `observability/`, `di/`, `audit/`, `openapi/`, `inspector/`
- `slim.py` — slim/minimal/auto module loading; `loader.py` — lazy/deferred module proxy

#### CLI Commands

- `python manage.py startapi` — scaffold new API projects
- `python manage.py generate_crud` — CRUD controller + schema + service + admin + tests from a model
- `python manage.py sync_types` — generate TypeScript/Swift types
- `python manage.py config` — configuration management
- `python manage.py deploy` — multi-platform deployment (Fly.io, Railway, Render, AWS, Hetzner)
- Migration tools: `matt_baseline`, `matt_migrate --profile/--parallel`, `matt_squash`

#### Testing Utilities

- `APITestClient`, `AsyncAPITestClient` with `force_authenticate()` via `acreate_access_token()`
- Factories: `UserFactory`, `OrganizationFactory`, `TeamFactory`, `MembershipFactory`
- Assertions: `assert_status()`, `assert_json_equal()`, `assert_created()`, `assert_not_found()`, `assert_query_count()`

#### Error Handling

- `APIError`, `NotFoundError`, `ValidationError`, `UnauthorizedError`, `ForbiddenError`, `ConflictError`, `RateLimitError`

#### OpenAPI / Interactive Docs

- Swagger UI at `/docs`, ReDoc at `/redoc`, OpenAPI JSON at `/openapi.json`
- API playground at `/_matt/docs/playground/` — code snippets (curl/Python/JS/HTTPie), request history, dark/light mode

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

---

## Migration Notes

### From Django Ninja

See [Migration Guide: Django Ninja](migrations/from-ninja.md).

Key changes: replace `NinjaAPI` with `MattAPI`; replace `ninja_extra` decorators with `@api.get` etc.; update schema `Config` classes to `Meta`; replace `ninja_jwt` with built-in `AuthController`.

### From Django REST Framework

See [Migration Guide: DRF](migrations/from-drf.md).

Key changes: replace serializers with Pydantic schemas; replace `APIView` with `APIController`; replace `ModelViewSet` with `APIViewSet`; update authentication configuration.

### From FastAPI

See [Migration Guide: FastAPI](migrations/from-fastapi.md).

Key changes: replace `FastAPI()` with `MattAPI()`; replace `Depends()` with built-in DI container; replace SQLAlchemy + Alembic with Django ORM + migrations; gain Django admin, ecosystem packages, and all batteries-included modules.
