# Roadmap: django-matt

## Overview

django-matt is a brownfield Django meta-framework with 4143 tests and substantial module coverage already in place. This milestone is not a greenfield build — it is an audit, fix, and completion pass to bring every module to v1 quality. The journey moves from correctness first (fix the async/sync violations masked by the test suite), through performance validation, DX tooling, auth hardening, integrated batteries (billing, flags, analytics), real-time and notifications, and finally deployment hardening and the remaining optional modules. Each phase delivers a verifiable capability on top of an already-existing codebase.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Correctness Audit** - Remove async/sync ORM violations, consolidate error classes, verify PATCH sentinel, confirm all 4143 tests pass under strict async constraints (completed 2026-03-07)
- [ ] **Phase 2: Performance Baseline** - Benchmark django-matt vs DRF/ninja/FastAPI, ship stripped middleware profile, audit all hot paths for per-request introspection
- [ ] **Phase 3: CLI and Type Generation** - Complete scaffolding commands, TypeScript/Swift/Zod type gen, AI context export, Rich CLI commands
- [ ] **Phase 4: Auth Hardening and Multi-Tenancy** - Harden JWT blacklist/revocation, complete OAuth/SSO/Passkeys, wire Organization/Team/Membership with permission integration
- [ ] **Phase 5: Billing, Feature Flags, and Analytics** - Complete Stripe/PayPal/Polar billing, flag backends (DB/Redis/LaunchDarkly/Unleash), analytics event tracking and A/B experiments
- [ ] **Phase 6: Real-Time, Notifications, and Communications** - Complete WebSocket consumers with auth/presence, messaging module, notification dispatch (in-app, push, SMS), email backends
- [ ] **Phase 7: Deployment, Observability, and Completion** - Deployment configs with CONN_MAX_AGE=0, observability (logging/metrics/tracing), plus audit/file/task/admin/GraphQL/HTMX/AI module completion

## Phase Details

### Phase 1: Correctness Audit
**Goal**: Every async handler in django-matt makes zero sync ORM calls; the test suite passes without DJANGO_ALLOW_ASYNC_UNSAFE=true; error handling is consolidated and consistent; PATCH semantics correctly distinguish null from absent
**Depends on**: Nothing (first phase)
**Requirements**: CORE-03, CORE-07, CORE-16
**Success Criteria** (what must be TRUE):
  1. `DJANGO_ALLOW_ASYNC_UNSAFE=true` is removed from conftest.py and all 4143 tests pass (no new failures)
  2. A developer calling any async handler with a sync ORM method receives an explicit error, not silent incorrect behavior
  3. `from django_matt.core.errors import` is the single canonical error import — `utils/errors.py` re-exports with deprecation, no duplicate class definitions
  4. A PATCH request with an empty body leaves all existing fields unchanged — verified by dedicated test
  5. All endpoint responses return the same structured error JSON format regardless of error type (validation, auth, not-found, server)
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Audit and fix async/sync ORM boundary violations across views, auth, multitenancy, and testing modules
- [ ] 01-02-PLAN.md — Consolidate error classes (delete utils/errors.py), fix PATCH null semantics with model_fields_set
- [ ] 01-03-PLAN.md — Remove DJANGO_ALLOW_ASYNC_UNSAFE, verify full test suite, finalize CLAUDE.md

### Phase 2: Performance Baseline
**Goal**: django-matt's throughput on equivalent CRUD endpoints is documented, matched against DRF/django-ninja/FastAPI, and the stripped middleware profile for API-only deployments ships and works
**Depends on**: Phase 1
**Requirements**: CORE-08, CORE-09, CORE-10, CORE-12, PERF-04, PERF-05, PERF-06, PERF-07, PERF-08
**Success Criteria** (what must be TRUE):
  1. A developer can run `make benchmark` and see req/s numbers for django-matt vs DRF vs django-ninja vs FastAPI on a list endpoint and a create endpoint
  2. The API-mode middleware profile is documented and reduces middleware overhead to near-Starlette levels (confirmed by profiler output, not just claim)
  3. No `get_type_hints()` or `inspect` call occurs per-request — confirmed by profiler showing zero calls in hot path after app startup
  4. `model_construct()` is used on all ORM-read list serialization paths — verified by code audit and query count test
  5. A test using `assert_query_count()` fails when N+1 is introduced into a queryset and passes when `optimize_queryset()` is correctly applied
**Plans**: 3 plans

Plans:
- [ ] 02-01-PLAN.md — Build FrameworkComparisonScenario, RichTableReporter, wire `make benchmark`, audit orjson coverage
- [ ] 02-02-PLAN.md — Ship MATT_API_MODE middleware stripping, cProfile hot-path verification test
- [ ] 02-03-PLAN.md — Add assert_query_count, @cache_response, verify model_construct/streaming/N+1 prevention

### Phase 3: CLI and Type Generation
**Goal**: A developer can scaffold a full CRUD module in one command, generate TypeScript/Swift/Zod types from the running app, export AI context for LLM coding tools, and use Rich CLI commands to inspect the project
**Depends on**: Phase 1
**Requirements**: DX-01, DX-02, DX-03, DX-04, DX-05, DX-06, DX-07, DX-08, DX-09, DX-10, DX-11, CORE-01, CORE-02, CORE-04, CORE-05, CORE-06, CORE-11, CORE-13, CORE-14, CORE-15
**Success Criteria** (what must be TRUE):
  1. `python manage.py generate_crud myapp.MyModel --full` produces a working controller, schema, service, admin registration, and test file — the generated code passes linting without modification
  2. `python manage.py sync_types --target typescript` produces TypeScript interfaces and Zod schemas that match the actual running API (no drift from OpenAPI spec)
  3. `python manage.py sync_types --target swift` produces Swift Codable structs for all models
  4. `python manage.py generate_ai_context --format all` produces a structured file an LLM can read to understand the project routes, types, and conventions
  5. `matt routes` lists all registered API routes with methods, paths, and handler names; `matt doctor` reports any configuration issues
**Plans**: TBD

Plans:
- [ ] 03-01: Complete generate_crud and startapi CLI scaffolding commands
- [ ] 03-02: Complete sync_types (TypeScript interfaces, Zod schemas, Swift structs) and generate_ai_context
- [ ] 03-03: Complete Rich CLI (matt info/doctor/routes/models/new), async test client fix, django-ninja migration tool

### Phase 4: Auth Hardening and Multi-Tenancy
**Goal**: Authentication is production-secure with verified token revocation, CSRF safety on JWT endpoints, and working OAuth/SSO/Passkeys; multi-tenancy delivers Organization/Team/Membership with org-scoped API access
**Depends on**: Phase 1
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07, AUTH-08, AUTH-09, AUTH-10, AUTH-11, AUTH-12, AUTH-13, TENANT-01, TENANT-02, TENANT-03, TENANT-04, TENANT-05
**Success Criteria** (what must be TRUE):
  1. After a user logs out, their previous JWT token is rejected — verified by test that issues a token, logs out, then reuses the token and asserts 401
  2. A JWT-authenticated endpoint with `@jwt_required` does not require or validate a CSRF token — verified by test sending no CSRF header
  3. A user can log in via OAuth (Google) and via magic link — both flows complete without error in integration test
  4. An org admin can create a team, add a member with a role, and that member's API requests are automatically scoped to their organization — verified end-to-end by test
  5. An API request without a valid org membership receives a 403, not a 500 or data from another org
**Plans**: TBD

Plans:
- [ ] 04-01: Audit and harden JWT blacklist, CSRF exemption, password reset, magic links, and API keys
- [ ] 04-02: Complete OAuth (Google/GitHub), SSO/SAML, and Passkeys/WebAuthn modules
- [ ] 04-03: Complete multitenancy (Organization, Team, Membership) with middleware and controller integration

### Phase 5: Billing, Feature Flags, and Analytics
**Goal**: Stripe/PayPal/Polar billing, feature flags with multiple backends, analytics event tracking, and A/B experiments are complete, documented, and covered by tests
**Depends on**: Phase 4
**Requirements**: BILL-01, BILL-02, BILL-03, BILL-04, BILL-05, FLAG-01, FLAG-02, FLAG-03, FLAG-04, FLAG-05, FLAG-06, FLAG-07, ANLYT-01, ANLYT-02, ANLYT-03, ANLYT-04, EXP-01, EXP-02, EXP-03, EXP-04
**Success Criteria** (what must be TRUE):
  1. A Stripe webhook event arrives, signature is verified, and the subscription lifecycle (created/updated/cancelled) updates the correct database record — verified by test with a mock Stripe event payload
  2. A feature flag check using the Redis backend returns the correct value for a user in a percentage-based rollout — verified by test
  3. `@feature_flag("my-flag")` on a controller endpoint returns 404 when the flag is disabled and the normal response when enabled
  4. An analytics event is tracked per user, session aggregations can be queried, and a funnel conversion rate is calculable from recorded events — verified by test
  5. An A/B experiment assigns users to variants deterministically, and the statistical significance of results can be computed — verified by test
**Plans**: TBD

Plans:
- [ ] 05-01: Complete billing (Stripe, PayPal, Polar) with webhook verification and subscription management
- [ ] 05-02: Complete feature flags (DB, Redis, LaunchDarkly, Unleash backends, decorators, middleware)
- [ ] 05-03: Complete analytics (event tracking, session recording, funnel analysis) and experiments (A/B, bandit, stats)

### Phase 6: Real-Time, Notifications, and Communications
**Goal**: WebSocket consumers with auth middleware and presence work end-to-end; messaging delivers conversation and message models with WebSocket transport; notification dispatch (in-app, push, SMS, webhook) and email backends are complete
**Depends on**: Phase 4
**Requirements**: RT-01, RT-02, RT-03, MSG-01, MSG-02, MSG-03, NOTIF-01, NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05, EMAIL-01, EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05
**Success Criteria** (what must be TRUE):
  1. A WebSocket client authenticates using a JWT token in the connection handshake and receives presence events (join/leave) for other users in the same channel
  2. A user sends a message in a conversation and another participant receives it via WebSocket within the same request cycle — verified by async test
  3. An in-app notification is created for a user, they retrieve it via the notifications API, and marking it read updates the read timestamp — verified by test
  4. An email with variable substitution renders correctly and dispatches through the configured backend (SendGrid, Mailgun, SES, or SMTP) — verified by test with mock backend
  5. A push notification can be enqueued for dispatch to FCM and APNs targets — verified by test with mock dispatch
**Plans**: TBD

Plans:
- [ ] 06-01: Complete WebSocket consumers (auth middleware, presence tracking, router integration)
- [ ] 06-02: Complete messaging module (conversation, message, attachment models with WebSocket transport)
- [ ] 06-03: Complete notifications (in-app, push FCM/APNs, SMS, webhook) and email backends (SendGrid, Mailgun, SES, SMTP, templates)

### Phase 7: Deployment, Observability, and Completion
**Goal**: All deployment configs emit correct ASGI settings, observability (logging/metrics/tracing) is wired, and the remaining optional modules (audit, file uploads, background tasks, admin, GraphQL, HTMX, AI/ML) reach v1 quality
**Depends on**: Phase 1
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05, DEPLOY-06, OBS-01, OBS-02, OBS-03, OBS-04, AUDIT-01, AUDIT-02, AUDIT-03, FILE-01, FILE-02, FILE-03, FILE-04, FILE-05, TASK-01, TASK-02, TASK-03, TASK-04, HTMX-01, HTMX-02, COMP-01, GQL-01, GQL-02, GQL-03, ADMIN-01, ADMIN-02, ADMIN-03, AI-01, AI-02, AI-03, AI-04, ML-01, ML-02, PERF-01, PERF-02, PERF-03
**Success Criteria** (what must be TRUE):
  1. Every CLI-generated deployment config (Docker, Fly.io, Railway, Render, AWS) sets `CONN_MAX_AGE=0` and `DATABASES["default"]["CONN_MAX_AGE"] = 0` — verified by inspecting generated template output
  2. A developer can run `matt routes` and see structured logs via the observability module; Prometheus-compatible metrics endpoint responds; OTEL tracing emits spans for request handling
  3. Create, update, and delete operations on an audited model produce audit log entries with user, timestamp, before/after diff — and soft-deleted records are restorable — verified by test
  4. A file uploaded through the framework is stored to the configured backend (S3/R2/MinIO) and a signed URL is generated for private access — verified by test with mock storage
  5. A Celery task registered via the tasks module executes and its result is retrievable via the task status API — verified by test
**Plans**: TBD

Plans:
- [ ] 07-01: Complete deployment configs (Docker, Fly, Railway, Render, AWS) with CONN_MAX_AGE=0 enforcement
- [ ] 07-02: Complete observability (structured logging, Prometheus metrics, OTEL tracing, request inspector)
- [ ] 07-03: Complete audit logging, soft delete, file uploads (S3/R2/MinIO/signed URLs), background tasks (Celery/Dramatiq/Django-Q)
- [ ] 07-04: Complete admin (Unfold integration, widgets, inlines), GraphQL (Strawberry, DataLoaders), HTMX helpers, backend components, AI/ML modules
- [ ] 07-05: Complete pagination/filtering/throttling, django-ninja migration guide, and final integration verification

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7
Note: Phases 3, 4, and 7 can start after Phase 1 completes. Phases 5 and 6 require Phase 4.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Correctness Audit | 3/3 | Complete   | 2026-03-07 |
| 2. Performance Baseline | 2/3 | In Progress|  |
| 3. CLI and Type Generation | 0/3 | Not started | - |
| 4. Auth Hardening and Multi-Tenancy | 0/3 | Not started | - |
| 5. Billing, Feature Flags, and Analytics | 0/3 | Not started | - |
| 6. Real-Time, Notifications, and Communications | 0/3 | Not started | - |
| 7. Deployment, Observability, and Completion | 0/5 | Not started | - |
