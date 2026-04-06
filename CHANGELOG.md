# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-04-06

### Added

**13 New Modules — Node.js-Inspired Features (555 tests)**

- **Interceptors** (`django_matt.interceptors`) — composable request/response wrappers with before_request, after_response, on_error hooks. Built-ins: Logging, Timing, Caching, Transform, Retry, RateLimit. 32 tests.
- **SSE/Streaming** (`django_matt.streaming`) — `sse_response()`, `stream_json()`, `stream_text()`, `@sse_endpoint` decorator, heartbeat helpers. 30 tests.
- **Config Validation** (`django_matt.config.namespaces`) — Pydantic-validated settings namespaces (AuthConfig, CacheConfig, DatabaseConfig, SecurityConfig, APIConfig, BillingConfig, ObservabilityConfig). Catches typos via `extra="forbid"`. 45 tests.
- **Route-Scoped Middleware** (`django_matt.middleware.scoped`) — per-controller and per-route middleware via `middleware_classes` and `@use_middleware`/`@skip_middleware`. Built-ins: ScopedCors, ScopedRateLimit, ScopedCache, ScopedAuth. 34 tests.
- **Exception Filters** (`django_matt.exceptions`) — layered typed exception handlers at route/controller/global scope. Built-ins: Validation→422, NotFound→404, Permission→403, Database→409, Throttle→429. 28 tests.
- **Event Bus** (`django_matt.events`) — async pub/sub with typed Pydantic events, wildcard matching, concurrent handlers, error isolation. InMemory and Redis backends. 41 tests.
- **Serialization Groups** (`django_matt.serialization`) — role-based field visibility via `Grouped()` field annotations and `@serialize_for()` decorator. 34 tests.
- **Auto-Instrumentation** (`django_matt.observability.auto`) — zero-config tracing for controllers, services, DB, cache, HTTP. Span management with contextvars. Console/JSON/Prometheus/OTel exporters. 51 tests.
- **Secrets** (`django_matt.secrets`) — pluggable secret management with Env, Dotenv, EncryptedFile, AWS, Vault, GCP backends. Rotation policies, SecretField for Pydantic, CLI commands. 80 tests.
- **Introspection** (`django_matt.introspection`) — `/health`, `/health/detailed`, `/health/ready`, `/health/live`, `/_info` endpoints. Auto-registers DB, cache, Redis, Celery, storage checks. K8s probe compatible. 33 tests.
- **RPC Client** (`django_matt.rpc`) — typed client generation from controllers. Python and TypeScript output. Dynamic proxy (`proxy.users.list()`). Auth strategies. 60 tests.
- **Module System** (`django_matt.modules`) — plugin architecture with dependency resolution, entry point discovery, lifecycle hooks. `@module`, `@requires_module`, `@optional_module`. 51 tests.
- **CQRS** (`django_matt.cqrs`) — command/query buses with middleware (logging, validation, transaction, caching). Domain events. Test utilities. 36 tests.

**Slim Mode (77 tests)**

- `MattAPI(mode="minimal")` — core routing + auth only
- `MattAPI(mode="slim")` — user-specified module list
- `LazyModuleProxy` for deferred heavy module imports
- `StartupProfiler` for import time measurement

**Framework Benchmarks**

- `benchmarks/framework_comparison.py` with Rich tables
- Route resolution, schema serialization, request parsing, full lifecycle comparisons
- `make bench-compare` target

**Python 3.14 CI**

- Added Python 3.14 to CI matrix for Django 6.0 with `continue-on-error`

**640+ New Tests Across Existing Modules**

- Auth: passwords, middleware, session, RBAC
- Billing: Stripe Connect, webhooks, signals
- Multitenancy: org, team, membership, isolation
- Views, flags, analytics, experiments, GraphQL, management commands

## [0.1.0] - 2026-03-09

### v1.0 Milestone Complete

Full audit, hardening, and completion pass across all modules — 7 phases, 24 plans, 2100+ tests passing.

### Added

**Phase 7: Deployment, Observability, and Completion** (2026-03-09)
- CONN_MAX_AGE=0 enforced across all ASGI deployment configs — production connection leak blocker resolved
- TracingMiddleware fix: only 5xx responses marked as OTEL ERROR (was incorrectly marking 4xx)
- Admin inline generation (`AdminGenerator._generate_inlines()`) auto-creates TabularInline from reverse FK relations
- Soft-delete integration with audit trail — delete/restore operations produce audit log entries
- 100+ new tests across deployment, observability, audit, files, tasks, admin, GraphQL, HTMX, components, AI/ML, pagination, filtering, throttling

**Phase 6: Real-Time, Notifications, and Communications** (2026-03-08)
- `MessageService.asend_message()` and `amark_as_read()` async wrappers via `sync_to_async`
- `Conversation.ais_member()` async instance method
- `PresenceManager.get_user_groups()` reverse cache index for O(1) user-to-groups lookup
- `PushToken` model for per-device push notification targeting (FCM/APNs/web)
- `EmailDeliveryHandler` wired through `EmailService` (not `django.core.mail` directly)
- SMTP provider tests and EMAIL requirement-to-test mapping
- 49 new tests across messaging, notifications, and email

**Phase 5: Billing, Feature Flags, and Analytics** (2026-03-08)
- Stripe/PayPal/Polar billing webhook lifecycle with signature verification
- Billing signals (`subscription_created`, `subscription_updated`, `subscription_canceled`)
- Mock event factories for billing webhook testing (`django_matt.billing.testing`)
- Feature flag backends: DB, Redis, LaunchDarkly, Unleash with percentage rollout
- `@feature_flag` decorator and `FeatureFlagMiddleware`
- Analytics funnel analysis and session aggregation
- A/B experiment deterministic assignment with `@experiment` decorator
- Statistical significance computation for experiment results

**Phase 4: Auth Hardening and Multi-Tenancy** (2026-03-08)
- JWT token blacklist with cache-first backend and bulk revocation
- CSRF exemption for JWT-authenticated API endpoints
- OAuth provider integration (Google, GitHub, Apple, Microsoft)
- SSO support (SAML 2.0, OIDC)
- Passkeys/WebAuthn support
- Org-aware permission classes (`IsOrgMember`, `IsOrgAdmin`)
- `TenantMiddlewareAsync` for automatic org scoping
- Cross-org data isolation enforcement

**Phase 3: CLI and Type Generation** (2026-03-08)
- `generate_crud` command — full controller, schema, service, admin, tests from model
- `sync_types --target typescript` — TypeScript interfaces + Zod schemas from Pydantic
- `sync_types --target swift` — Swift Codable structs
- `generate_ai_context --format all` — CLAUDE.md, .cursorrules generation
- `matt routes` — Rich table of all registered API routes
- `matt doctor` — configuration diagnostics
- Migration tool from Django Ninja to django-matt

**Phase 2: Performance Baseline** (2026-03-08)
- Framework comparison benchmarks (`make benchmark`) — django-matt vs DRF vs Ninja vs FastAPI
- API-mode middleware stripping profile
- `assert_query_count()` test helper for N+1 detection
- `@cache_response` decorator with stampede prevention
- `model_construct()` on all ORM-read list serialization paths
- Hot-path verification: zero `get_type_hints()` or `inspect` per-request

**Phase 1: Correctness Audit** (2026-03-07)
- Removed `DJANGO_ALLOW_ASYNC_UNSAFE=true` — all sync ORM calls converted to async
- Consolidated error classes: `django_matt.core.errors` is single canonical import
- PATCH null semantics with `model_fields_set` sentinel
- `AsyncAPITestClient.force_authenticate()` uses `acreate_access_token()`

### Core Framework (pre-milestone)

- Core routing and decorators (`django_matt.core`)
- Class-based controllers (`django_matt.core.controller`)
- Pydantic ModelSchema (`django_matt.core.schema`)
- OpenAPI/Swagger/ReDoc documentation (`django_matt.openapi`)
- JWT authentication (`django_matt.auth.jwt`)
- Magic link authentication (`django_matt.auth.magic_link`)
- Permission system (`django_matt.permissions`)
- RBAC with hierarchy (`django_matt.auth.rbac`)
- Multi-tenancy — organizations, teams (`django_matt.multitenancy`)
- Type generation — TypeScript, Swift (`django_matt.typegen`)
- CRUD generator CLI (`manage.py generate_crud`)
- Testing utilities (`django_matt.testing`)
- Service layer — `CRUDService`, `BaseThirdPartyService` (`django_matt.services`)
- Content negotiation — JSON, XML, CSV, YAML (`django_matt.negotiation`)
- WebSocket support with Django Channels (`django_matt.websockets`)
- Billing integration — Stripe, PayPal, Polar (`django_matt.billing`)
- Dependency injection container (`django_matt.di`)
- Pagination and filtering backends (`django_matt.pagination`, `django_matt.filtering`)
- API versioning schemes (`django_matt.versioning`)
- Rate limiting and throttling (`django_matt.throttling`)
- Session authentication with CSRF protection (`django_matt.auth.session`)
- Audit logging system with model change tracking (`django_matt.audit`)
- Background tasks — Celery, Dramatiq, Django-Q2 (`django_matt.tasks`)
- File handling — S3, R2, MinIO, local storage (`django_matt.files`)
- API Key authentication with rate limiting (`django_matt.auth.api_keys`)
- Soft delete mixin for models (`django_matt.db.soft_delete`)
- Frontend codegen — React, Svelte, Solid (`django_matt.codegen`)
- GraphQL — Strawberry schema generation, DataLoaders (`django_matt.graphql`)
- HTMX helpers and reactive components (`django_matt.htmx`)
- Backend component system (`django_matt.components`)
- AI/ML integration — LLM helpers, embeddings, RAG, vector storage (`django_matt.ai`, `django_matt.ml`)
- Observability — OpenTelemetry, Prometheus, structured logging (`django_matt.observability`)
- Deployment configs — Docker, Fly.io, Railway, Render, AWS (`django_matt.deploy`)
- Email providers — SendGrid, Mailgun, SES, SMTP (`django_matt.email`)
- Notifications — in-app, push, SMS, webhooks (`django_matt.notifications`)
- Messaging — conversations, attachments, WebSocket transport (`django_matt.messaging`)
- Feature flags — DB, Redis, LaunchDarkly, Unleash (`django_matt.flags`)
- Analytics — event tracking, sessions, funnels (`django_matt.analytics`)
- Experiments — A/B testing, multi-armed bandits (`django_matt.experiments`)

### Changed
- Python 3.12+ minimum (3.13 recommended)
- Django 5.2+ minimum (6.0 compatible)
- Replaced black/isort with Ruff for linting and formatting
- All deprecated `datetime.utcnow()` replaced with `datetime.now(UTC)`
- All deprecated `asyncio.get_event_loop()` replaced with `asyncio.to_thread()`
- orjson used everywhere (controller, router, views) instead of stdlib json

### Fixed
- CONN_MAX_AGE production blocker — Django ticket #33497 persistent connection leak under ASGI
- TracingMiddleware incorrectly marking 4xx responses as OTEL ERROR status
- S3 storage backend using deprecated `asyncio.get_event_loop()`
- Background tasks using deprecated `datetime.utcnow()`
- AI base classes using deprecated `asyncio.get_event_loop()`
- PayPal webhook test missing required transmission headers
- `_get_push_tokens` app_label bug (was "notifications", fixed to "django_matt")
