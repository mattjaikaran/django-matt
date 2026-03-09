# Requirements: django-matt

**Defined:** 2026-03-07
**Core Value:** The fastest, most developer-friendly way to build Django APIs — if you can't ship faster with django-matt than with DRF or django-ninja, it hasn't shipped yet.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Core API Framework

- [x] **CORE-01**: Router supports async and sync view registration with automatic URL generation
- [x] **CORE-02**: Controller pattern provides class-based API endpoints with decorator-driven routing
- [x] **CORE-03**: Pydantic v2 schema validation on request bodies with structured error responses
- [x] **CORE-04**: CRUD ViewSet generates list/create/read/update/delete endpoints from model + schema
- [x] **CORE-05**: OpenAPI 3.1 schema auto-generated from routes, schemas, and type hints
- [x] **CORE-06**: Swagger UI and ReDoc served at configurable endpoints
- [x] **CORE-07**: Structured error handling with consistent JSON error format across all endpoints
- [x] **CORE-08**: `model_construct()` fast path for list serialization (skip re-validation on ORM reads)
- [x] **CORE-09**: Startup-time introspection caching — zero per-request `get_type_hints()` or `_meta.fields` calls
- [x] **CORE-10**: orjson used for all JSON serialization/deserialization (router, controller, views, responses)
- [x] **CORE-11**: Static-before-parameterized URL ordering prevents `/users/me` vs `/users/<id>` conflicts
- [x] **CORE-12**: API-mode middleware profile — stripped middleware stack for maximum throughput on API-only projects
- [x] **CORE-13**: Dependency injection container with ContextVar-based request scoping
- [x] **CORE-14**: Content negotiation supporting JSON, XML, CSV, YAML, MsgPack
- [x] **CORE-15**: API versioning strategies (URL, header, query param)
- [x] **CORE-16**: PATCH requests use NotSet sentinel to distinguish "not sent" from "sent as null"

### Authentication & Security

- [x] **AUTH-01**: JWT authentication with access and refresh token flow
- [x] **AUTH-02**: JWT token blacklist with bulk purge for revocation
- [x] **AUTH-03**: Session-based authentication for browser clients
- [x] **AUTH-04**: Permission classes: IsAuthenticated, IsAdmin, IsOwner, HasRole, HasPermission
- [x] **AUTH-05**: RBAC — role-based access control with role assignment and checking
- [x] **AUTH-06**: Password reset via email link flow
- [x] **AUTH-07**: Magic link passwordless login
- [x] **AUTH-08**: OAuth provider login (Google, GitHub, and extensible for others)
- [x] **AUTH-09**: SSO / SAML integration
- [x] **AUTH-10**: Passkey / WebAuthn authentication
- [x] **AUTH-11**: API key authentication with scoped permissions
- [x] **AUTH-12**: CSRF exemption correctly applied for JWT-authenticated API endpoints
- [x] **AUTH-13**: Permission decorators: `@jwt_required`, `@jwt_optional`, `@requires_role()`, `@requires_permission()`

### Developer Experience

- [x] **DX-01**: `startapi` CLI command scaffolds new project with template selection (basic, b2b, etc.)
- [x] **DX-02**: `generate_crud` CLI command generates controller, schema, service, admin, and tests from model
- [x] **DX-03**: `sync_types` generates TypeScript types from Django models and Pydantic schemas
- [x] **DX-04**: `sync_types` generates Swift types for iOS/macOS clients
- [x] **DX-05**: `sync_types` generates Zod schemas for frontend runtime validation
- [x] **DX-06**: `generate_ai_context` exports project structure, types, routes for LLM consumption
- [x] **DX-07**: Rich CLI with `matt info`, `doctor`, `routes`, `models`, `new` commands
- [x] **DX-08**: CLI migration tool rewrites django-ninja imports/patterns to django-matt with TODO markers
- [x] **DX-09**: Async test client with `force_authenticate()` using async token creation
- [x] **DX-10**: Test factories and assertion helpers for common API testing patterns
- [x] **DX-11**: Example apps demonstrating all major features (todo, ecommerce, saas-starter, realtime-chat)

### Performance & Data

- [ ] **PERF-01**: Pagination: page number, limit/offset, and cursor-based
- [ ] **PERF-02**: Filtering backend with Django filter integration, search, and ordering
- [ ] **PERF-03**: Rate limiting / throttling with configurable backends
- [x] **PERF-04**: Auto `optimize_queryset()` detects FK/M2M from schema for select_related/prefetch_related
- [x] **PERF-05**: Streaming response support for large datasets
- [x] **PERF-06**: Caching utilities with configurable backends
- [x] **PERF-07**: Benchmark suite comparing django-matt vs DRF, django-ninja, and FastAPI on equivalent endpoints
- [x] **PERF-08**: Query count assertion helper for tests (`assert_query_count()`)

### Multi-Tenancy

- [x] **TENANT-01**: Organization model with create/read/update/delete
- [x] **TENANT-02**: Team model with membership management
- [x] **TENANT-03**: Membership model with role-based team permissions
- [x] **TENANT-04**: Tenant-aware middleware scoping queries to current organization
- [x] **TENANT-05**: Tenant-aware controllers with automatic organization filtering

### Billing

- [x] **BILL-01**: Stripe integration — subscriptions, one-time payments, webhooks
- [x] **BILL-02**: PayPal integration — payments and webhooks
- [x] **BILL-03**: Polar integration — open-source-friendly billing
- [x] **BILL-04**: Billing controllers with subscription lifecycle management
- [x] **BILL-05**: Webhook handlers with signature verification

### Feature Flags

- [x] **FLAG-01**: Feature flag model with boolean/percentage/user-segment targeting
- [x] **FLAG-02**: Database backend for feature flags
- [x] **FLAG-03**: Redis backend for high-performance flag evaluation
- [x] **FLAG-04**: LaunchDarkly backend integration
- [x] **FLAG-05**: Unleash backend integration
- [x] **FLAG-06**: Feature flag decorators for views and controllers
- [x] **FLAG-07**: Feature flag middleware for request-scoped flag evaluation

### Analytics & Experiments

- [x] **ANLYT-01**: Event tracking with pluggable backends
- [x] **ANLYT-02**: Session tracking and user journey recording
- [x] **ANLYT-03**: Funnel analysis with conversion tracking
- [x] **ANLYT-04**: Analytics aggregation queries (daily/weekly/monthly)
- [x] **EXP-01**: A/B test experiment model with variant assignment
- [x] **EXP-02**: Multi-armed bandit assignment strategy
- [x] **EXP-03**: Statistical significance analysis for experiment results
- [x] **EXP-04**: Experiment decorators for controller endpoints

### Real-Time & Messaging

- [x] **RT-01**: WebSocket consumer base class with authentication middleware
- [x] **RT-02**: Presence tracking (who's online in a channel)
- [x] **RT-03**: WebSocket routing integrated with django-matt router
- [x] **MSG-01**: Conversation model with participants and messages
- [x] **MSG-02**: Message attachments (file references)
- [x] **MSG-03**: WebSocket transport for real-time message delivery

### Notifications & Email

- [ ] **NOTIF-01**: In-app notification system with read/unread tracking
- [ ] **NOTIF-02**: Email notifications with template rendering
- [ ] **NOTIF-03**: Push notifications via FCM and APNs
- [ ] **NOTIF-04**: SMS notifications
- [ ] **NOTIF-05**: Webhook notifications to external endpoints
- [ ] **EMAIL-01**: SendGrid email backend
- [ ] **EMAIL-02**: Mailgun email backend
- [ ] **EMAIL-03**: AWS SES email backend
- [ ] **EMAIL-04**: SMTP fallback backend
- [ ] **EMAIL-05**: Email templates with variable substitution

### AI & ML

- [ ] **AI-01**: LLM integration helpers (prompt management, response parsing)
- [ ] **AI-02**: Embedding generation and storage
- [ ] **AI-03**: RAG (retrieval-augmented generation) pipeline utilities
- [ ] **AI-04**: IDE context generation for AI coding tools
- [ ] **ML-01**: Vector storage with pgvector integration
- [ ] **ML-02**: Structured output parsing from LLM responses

### File Management

- [ ] **FILE-01**: File upload handling with validation (size, type)
- [ ] **FILE-02**: S3 storage backend
- [ ] **FILE-03**: Cloudflare R2 storage backend
- [ ] **FILE-04**: MinIO storage backend
- [ ] **FILE-05**: Signed URL generation for private files

### Background Tasks

- [ ] **TASK-01**: Celery task integration with django-matt
- [ ] **TASK-02**: Dramatiq task integration
- [ ] **TASK-03**: Django-Q task integration
- [ ] **TASK-04**: Task status tracking and result retrieval

### Audit & Compliance

- [ ] **AUDIT-01**: Audit log capturing create/update/delete with user, timestamp, and diff
- [ ] **AUDIT-02**: Soft delete support with restore capability
- [ ] **AUDIT-03**: Audit log query API for admin dashboards

### Frontend Integration

- [ ] **HTMX-01**: HTMX response helpers (triggers, swaps, redirects)
- [ ] **HTMX-02**: Livewire-style reactive component helpers
- [ ] **COMP-01**: Backend-served component system for server-rendered UIs

### GraphQL

- [ ] **GQL-01**: Strawberry-based schema auto-generation from Django models
- [ ] **GQL-02**: DataLoader integration for N+1 prevention
- [ ] **GQL-03**: GraphQL endpoint served alongside REST from same app

### Admin

- [ ] **ADMIN-01**: Django Unfold integration for modern admin UI
- [ ] **ADMIN-02**: Admin dashboard widgets
- [ ] **ADMIN-03**: Admin inline configuration from django-matt models

### Deployment & Observability

- [ ] **DEPLOY-01**: Docker deployment template with ASGI (Granian/uvicorn)
- [ ] **DEPLOY-02**: Fly.io deployment configuration
- [ ] **DEPLOY-03**: Railway deployment configuration
- [ ] **DEPLOY-04**: Render deployment configuration
- [ ] **DEPLOY-05**: AWS deployment configuration
- [ ] **DEPLOY-06**: `CONN_MAX_AGE=0` enforced in all ASGI deployment templates
- [x] **OBS-01**: Structured logging with configurable formatters
- [x] **OBS-02**: Metrics collection (Prometheus-compatible)
- [x] **OBS-03**: Distributed tracing (OpenTelemetry)
- [x] **OBS-04**: Request/response inspector for development

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### matt-stack 2.0 Integration

- **STACK-01**: `matt-stack` CLI scaffolds django-matt backend + React frontend projects
- **STACK-02**: Shared type definitions between backend and frontend via `sync_types`
- **STACK-03**: Development server coordination (backend + frontend)

### Advanced AI

- **AI-05**: MCP server integration for AI agent tooling
- **AI-06**: AI-powered code review suggestions for django-matt projects

### Frontend Framework

- **FE-01**: Custom React meta-framework (matt-stack v3)
- **FE-02**: Custom JS frontend framework

## Out of Scope

| Feature | Reason |
|---------|--------|
| Python < 3.12 support | Modern Python only — leverage latest features |
| Django < 5.2 support | No legacy compatibility burden |
| Mobile SDKs | Web-first; Swift type gen covers iOS models |
| GraphQL-first architecture | REST-first; GraphQL is an optional module |
| Custom ORM | Django ORM is battle-tested; improve usage, don't replace |
| Real-time video/audio | Too specialized; use dedicated services |
| msgspec replacement for orjson | Requires Struct types incompatible with Pydantic; revisit post-v1 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 3 | Complete |
| CORE-02 | Phase 3 | Complete |
| CORE-03 | Phase 1 | Complete |
| CORE-04 | Phase 3 | Complete |
| CORE-05 | Phase 3 | Complete |
| CORE-06 | Phase 3 | Complete |
| CORE-07 | Phase 1 | Complete |
| CORE-08 | Phase 2 | Complete |
| CORE-09 | Phase 2 | Complete |
| CORE-10 | Phase 2 | Complete |
| CORE-11 | Phase 3 | Complete |
| CORE-12 | Phase 2 | Complete |
| CORE-13 | Phase 3 | Complete |
| CORE-14 | Phase 3 | Complete |
| CORE-15 | Phase 3 | Complete |
| CORE-16 | Phase 1 | Complete |
| AUTH-01 | Phase 4 | Complete |
| AUTH-02 | Phase 4 | Complete |
| AUTH-03 | Phase 4 | Complete |
| AUTH-04 | Phase 4 | Complete |
| AUTH-05 | Phase 4 | Complete |
| AUTH-06 | Phase 4 | Complete |
| AUTH-07 | Phase 4 | Complete |
| AUTH-08 | Phase 4 | Complete |
| AUTH-09 | Phase 4 | Complete |
| AUTH-10 | Phase 4 | Complete |
| AUTH-11 | Phase 4 | Complete |
| AUTH-12 | Phase 4 | Complete |
| AUTH-13 | Phase 4 | Complete |
| DX-01 | Phase 3 | Complete |
| DX-02 | Phase 3 | Complete |
| DX-03 | Phase 3 | Complete |
| DX-04 | Phase 3 | Complete |
| DX-05 | Phase 3 | Complete |
| DX-06 | Phase 3 | Complete |
| DX-07 | Phase 3 | Complete |
| DX-08 | Phase 3 | Complete |
| DX-09 | Phase 3 | Complete |
| DX-10 | Phase 3 | Complete |
| DX-11 | Phase 3 | Complete |
| PERF-01 | Phase 7 | Pending |
| PERF-02 | Phase 7 | Pending |
| PERF-03 | Phase 7 | Pending |
| PERF-04 | Phase 2 | Complete |
| PERF-05 | Phase 2 | Complete |
| PERF-06 | Phase 2 | Complete |
| PERF-07 | Phase 2 | Complete |
| PERF-08 | Phase 2 | Complete |
| TENANT-01 | Phase 4 | Complete |
| TENANT-02 | Phase 4 | Complete |
| TENANT-03 | Phase 4 | Complete |
| TENANT-04 | Phase 4 | Complete |
| TENANT-05 | Phase 4 | Complete |
| BILL-01 | Phase 5 | Complete |
| BILL-02 | Phase 5 | Complete |
| BILL-03 | Phase 5 | Complete |
| BILL-04 | Phase 5 | Complete |
| BILL-05 | Phase 5 | Complete |
| FLAG-01 | Phase 5 | Complete |
| FLAG-02 | Phase 5 | Complete |
| FLAG-03 | Phase 5 | Complete |
| FLAG-04 | Phase 5 | Complete |
| FLAG-05 | Phase 5 | Complete |
| FLAG-06 | Phase 5 | Complete |
| FLAG-07 | Phase 5 | Complete |
| ANLYT-01 | Phase 5 | Complete |
| ANLYT-02 | Phase 5 | Complete |
| ANLYT-03 | Phase 5 | Complete |
| ANLYT-04 | Phase 5 | Complete |
| EXP-01 | Phase 5 | Complete |
| EXP-02 | Phase 5 | Complete |
| EXP-03 | Phase 5 | Complete |
| EXP-04 | Phase 5 | Complete |
| RT-01 | Phase 6 | Complete |
| RT-02 | Phase 6 | Complete |
| RT-03 | Phase 6 | Complete |
| MSG-01 | Phase 6 | Complete |
| MSG-02 | Phase 6 | Complete |
| MSG-03 | Phase 6 | Complete |
| NOTIF-01 | Phase 6 | Pending |
| NOTIF-02 | Phase 6 | Pending |
| NOTIF-03 | Phase 6 | Pending |
| NOTIF-04 | Phase 6 | Pending |
| NOTIF-05 | Phase 6 | Pending |
| EMAIL-01 | Phase 6 | Pending |
| EMAIL-02 | Phase 6 | Pending |
| EMAIL-03 | Phase 6 | Pending |
| EMAIL-04 | Phase 6 | Pending |
| EMAIL-05 | Phase 6 | Pending |
| AI-01 | Phase 7 | Pending |
| AI-02 | Phase 7 | Pending |
| AI-03 | Phase 7 | Pending |
| AI-04 | Phase 7 | Pending |
| ML-01 | Phase 7 | Pending |
| ML-02 | Phase 7 | Pending |
| FILE-01 | Phase 7 | Pending |
| FILE-02 | Phase 7 | Pending |
| FILE-03 | Phase 7 | Pending |
| FILE-04 | Phase 7 | Pending |
| FILE-05 | Phase 7 | Pending |
| TASK-01 | Phase 7 | Pending |
| TASK-02 | Phase 7 | Pending |
| TASK-03 | Phase 7 | Pending |
| TASK-04 | Phase 7 | Pending |
| AUDIT-01 | Phase 7 | Pending |
| AUDIT-02 | Phase 7 | Pending |
| AUDIT-03 | Phase 7 | Pending |
| HTMX-01 | Phase 7 | Pending |
| HTMX-02 | Phase 7 | Pending |
| COMP-01 | Phase 7 | Pending |
| GQL-01 | Phase 7 | Pending |
| GQL-02 | Phase 7 | Pending |
| GQL-03 | Phase 7 | Pending |
| ADMIN-01 | Phase 7 | Pending |
| ADMIN-02 | Phase 7 | Pending |
| ADMIN-03 | Phase 7 | Pending |
| DEPLOY-01 | Phase 7 | Pending |
| DEPLOY-02 | Phase 7 | Pending |
| DEPLOY-03 | Phase 7 | Pending |
| DEPLOY-04 | Phase 7 | Pending |
| DEPLOY-05 | Phase 7 | Pending |
| DEPLOY-06 | Phase 7 | Pending |
| OBS-01 | Phase 7 | Complete |
| OBS-02 | Phase 7 | Complete |
| OBS-03 | Phase 7 | Complete |
| OBS-04 | Phase 7 | Complete |

**Coverage:**
- v1 requirements: 101 total
- Mapped to phases: 101
- Unmapped: 0

---
*Requirements defined: 2026-03-07*
*Last updated: 2026-03-07 after roadmap creation — all 101 requirements mapped*
