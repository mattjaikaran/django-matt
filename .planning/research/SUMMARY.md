# Project Research Summary

**Project:** django-matt
**Domain:** Django API meta-framework (async-first, type-driven, batteries-included)
**Researched:** 2026-03-07
**Confidence:** HIGH

## Executive Summary

django-matt is a brownfield meta-framework project targeting the gap between django-ninja (thin, type-safe, no CRUD bundling, no class-based views) and DRF (mature, batteries-included, synchronous, slow serialization). The research confirms a well-defined competitive landscape: DRF owns the "batteries-included" legacy market, django-ninja owns the "FastAPI-style Django" market, FastAPI owns the "greenfield async API" market. django-shinobi and django-bolt occupy similar fast-Django-API niches but lack the integrated auth/billing/multitenancy suite that is django-matt's differentiating value proposition. The fundamental thesis — one install to ship a production-grade Django API with auth, multitenancy, billing, WebSockets, and type generation — is not matched by any competitor.

The recommended approach is clear and substantiated: async-first ASGI with Granian or uvicorn, Pydantic v2.11+ with model_construct() on read paths, orjson as a hard dependency (not optional), psycopg3 with connection pooling, and startup-time introspection caching everywhere. The core architecture is already sound. The primary remaining work is correctness auditing (async/sync boundary violations masked by DJANGO_ALLOW_ASYNC_UNSAFE=true in tests), consolidating duplicate error classes, wiring the remaining integrated modules (analytics, experiments, notifications, billing, multitenancy), and producing the CLI scaffolding and type generation outputs that make the "ships faster" promise demonstrable.

The key risks are not architectural — they are quality and surface area risks. The CONN_MAX_AGE/ASGI connection leak is a deploy-day production blocker if the default config templates are wrong. The PATCH null-vs-absent semantics bug (which kills django-ninja in production) must be handled correctly before update views are considered done. Module-level cache pollution in tests creates flaky CI that degrades confidence over time. These are all addressable and are already partially mitigated — the research flags them to ensure they're not skipped during roadmap execution.

---

## Key Findings

### Recommended Stack

The stack is well-settled. Python 3.12+ (floor), Django 5.2 LTS targeting 6.0 compatibility, Pydantic v2.11+, orjson 3.11.7+, psycopg3 binary with connection pool, and Granian 2.6.0+ as the recommended production server (uvicorn as the fallback and dev standard). No changes to the toolchain are warranted: uv, ruff, pyright + mypy, pytest with asyncio_mode=auto are all correct choices.

The single highest-leverage infrastructure decision is the "stripped middleware stack" for API-only deployments. Django's default middleware (session, CSRF, messages, authentication) adds 2-2.5x overhead compared to Starlette. Documenting and shipping a minimal middleware profile closes the biggest remaining gap to FastAPI throughput. With Granian + stripped middleware + orjson + Pydantic v2 model_construct(), the realistic target is 10,000-15,000 req/s — the fastest achievable Django-based API throughput, not competitive with raw Starlette/ASGI but competitive with every Django-based alternative.

**Core technologies:**
- Python 3.12+: Runtime — 60% faster startup vs 3.10; 3.13 no-GIL experimental upside
- Django 5.2 LTS / 6.0: Framework — LTS stability + 6.0 native background tasks, AsyncPaginator
- Pydantic 2.11+: Validation/serialization — 5-17x faster than v1; generic caching 48% memory reduction
- orjson 3.11.7+: JSON — 10x faster than stdlib; base dependency, never optional
- psycopg3 binary + pool: DB driver — async-native, 3.4x QPS vs psycopg2; Django 5.1+ native pool
- Granian 2.6.0+: Production ASGI — 11,270 req/s avg vs uvicorn 9,000; lower p99 spread
- uv 0.10+: Package manager — 10-100x faster than pip; already project standard
- ruff 0.9+: Lint/format — replaces flake8 + black + isort in one binary

**Rejected alternatives (do not revisit without new benchmark data):**
- msgspec: faster than orjson for schema-bound structs but requires replacing Pydantic entirely
- asyncpg: slightly faster than psycopg3 in raw benchmarks but incompatible with Django ORM
- Daphne/Hypercorn: slower than Granian/uvicorn; Hypercorn only interesting when HTTP/3 is required

---

### Expected Features

The features table is fully mapped against the competitive landscape. Table stakes are entirely implemented. The primary competitive differentiators are the integrated batteries (multitenancy, billing, feature flags, analytics, experiments, WebSockets) and the cross-language type generation (TypeScript interfaces, Zod schemas, API client, Swift Codable structs). No other framework in the competitive set — DRF, django-ninja, django-shinobi, django-bolt, FastAPI — provides all of these in a single install.

**Must have (table stakes — all implemented):**
- Decorator-based routing (`@api.get`, `@api.post`) — industry standard since FastAPI
- Class-based controllers with `permission_classes` — django-ninja's #1 complaint is the absence of this
- Pydantic v2 ModelSchema with `from_orm_fast()` — DRF serializers are the primary adoption blocker
- Composable CRUD ViewSet (List/Create/Read/Update/Delete) — 4-line CRUD vs ninja's 30+ lines
- JWT auth with middleware and permission decorators — production auth without per-route config
- Pagination, filtering, ordering — required for any production list endpoint
- Auto-generated OpenAPI/Swagger — developers expect `/docs` and `/redoc` out of the box
- Structured error responses — RFC 7807-style; django-ninja's error handling is a documented pain point
- Test client with auth helpers and assertion utilities — matches DRF's `APIClient.force_authenticate()`

**Should have (competitive differentiators):**
- `generate_crud` CLI scaffolding — Rails-style; demonstrates the "ships faster" value in a 30-second demo
- TypeScript interfaces + Zod schemas + API client generation — eliminates frontend/backend type drift
- Swift Codable struct generation — iOS/macOS native apps with correct types from day one
- Multi-tenancy (Organization/Team/Membership) — B2B SaaS table stakes; no other API framework includes this
- Feature flags (DB, Redis, LaunchDarkly, Unleash) — required in production; usually third-party
- Stripe/PayPal/Polar billing — first third-party integration every SaaS builds
- WebSockets with auth middleware and presence — real-time increasingly expected
- `generate_ai_context` CLI — LLM-readable project context for agentic coding workflows
- Rich CLI (`matt info`, `matt doctor`, `matt routes`, `matt models`, `matt new`) — no other Django framework has this

**Defer to v2+:**
- MCP tooling hooks — MCP is dominant standard in 2025 but framework-specific integration value unvalidated
- GraphQL-first design — keep Strawberry in `graphql/` optional module, not core routing
- Full HTMX component system — growing trend but not the API framework primary use case
- Mobile SDK generation beyond Swift (Kotlin, Dart) — disproportionate scope increase
- Browser-first CMS features — different product category entirely

**Anti-features (deliberately excluded):**
- Django ORM replacement — destroys compatibility; service layer is the right abstraction level
- DRF drop-in compatibility shim — constrains the design; migration CLI is better than compat
- Optional external dependencies in core — only Django + orjson in core; everything else is an optional extra
- Custom async task queue — Celery/Dramatiq/Django-Q exist; `tasks/` should be adapters

---

### Architecture Approach

The architecture is already established and sound. The layered ASGI → Middleware → MattAPI Router → Controller/ViewSet → Service → ORM → Response pattern is correctly implemented. The key patterns to maintain are: startup-time introspection (zero per-request `get_type_hints`/`inspect` calls), async-first ORM (all handlers use `aget`/`asave`/`adelete`), orjson everywhere (no `import json` in `django_matt/`), single-pass closure wrapping with default-arg binding to avoid closure capture bugs, and ContextVar (not threading.local) for per-request DI scope. The slim mode module registry ensures projects only pay for what they activate.

The remaining architecture work is not new design — it is verifying that the existing patterns hold across all modules and connecting the independent batteries (analytics, experiments, notifications, billing, multitenancy, AI/ML) to the stable core without touching the core.

**Major components:**
1. `MattAPI / APIRouter` — route registry, URL compilation, OpenAPI schema cache; entry point
2. `APIController / CRUDController` — class-based endpoint grouping; single-pass `_setup_methods()` at `__init__`
3. `ViewSet + APIView` — composable CRUD descriptors; `BoundView.__call__` dispatches, checks permissions, runs hooks
4. `ModelSchema` — Pydantic schema from Django model at class definition time; `from_orm_fast()` for list paths
5. `DI Container` — Singleton/Scoped/Transient; ContextVar per-request scope; circular dependency detection
6. `ModuleRegistry` — tracks active modules in slim mode; controls middleware chain and URL patterns
7. `DjangoMattMiddleware` — auto-chains internal middleware stack at startup; all middleware must be async def
8. `ErrorHandler` — class-level singleton on APIController; converts APIError/ValidationError/DoesNotExist to JSON
9. `ServiceLayer` — BaseService/CRUDService/BaseThirdPartyService; business logic isolated from HTTP
10. `OpenAPISchema` — generates OpenAPI 3.x JSON from routes/controllers at schema-request time; cached

**Build order for remaining work:** The dependency graph is flat above the stable core. multitenancy, billing, analytics, experiments, notifications, graphql, AI/ML can be built in any order — they all depend on core but not on each other. Infrastructure additions (observability, deployment, CLI enhancements) are similarly independent.

---

### Critical Pitfalls

5 pitfalls are classified critical (cause rewrites, security incidents, or framework abandonment):

1. **Async/sync ORM boundary violations** — `DJANGO_ALLOW_ASYNC_UNSAFE=true` in `conftest.py` masks the entire bug class in CI. Remove this setting and audit all `async def` handlers for sync ORM calls (`.get()`, `.save()`, `.filter()` without `a`-prefix). This is the most important correctness audit before any performance claims.

2. **CONN_MAX_AGE under ASGI causes connection pool exhaustion** — Django's persistent connection mechanism uses thread IDs, which are meaningless in async. Set `CONN_MAX_AGE=0` in all ASGI deployment templates. CLI scaffolding (`startapi`) must emit the correct config from day one — this is a production blocker if misconfigured.

3. **model_construct() on untrusted request data skips validation** — `from_orm_fast()` with `model_construct()` is correct on read paths (ORM -> response). Applying it to write paths (request body -> model) bypasses all validators and field constraints, allowing malformed or malicious data to reach the database. This boundary must be enforced by docstring and test.

4. **PATCH null vs absent semantics** — django-ninja's `PatchDict` sets non-nullable fields to `None` when a key is absent from the PATCH payload, causing silent data loss. The `NotSet` sentinel pattern must be the framework's answer to partial updates, and must be tested with an empty-body PATCH that asserts no existing fields are modified.

5. **Framework maintainer risk / Django version coupling** — keep Django as the only hard dependency. Never pin an upper bound on Django version. Test against at minimum Django 5.2 LTS and 6.x simultaneously in CI. The history of Tastypie, django-piston, and DRF's async stall all trace back to dependency drift from Django's release cycle.

**Top moderate pitfalls:**
- N+1 queries in serialization — `optimize_queryset()` auto-detection exists; validate with query count assertions
- Per-request introspection — `get_type_hints`/`inspect` in hot path; audit router/controller for any missed caches
- Sync middleware in ASGI stack — one sync middleware causes Django to spawn a thread per request; all framework middleware must be `async def`
- JWT token revocation — blacklist module exists; enforce: (a) used on logout, (b) has purge command, (c) tested post-logout
- Module-level cache pollution in tests — `_reset_*` functions exist; expose `reset_all_caches()` and use in autouse fixtures
- Duplicate error classes (`utils/errors.py` vs `core/errors.py`) — consolidate; re-export from utils with deprecation warning

---

## Implications for Roadmap

### Phase 1: Correctness Audit and Async Hygiene
**Rationale:** The async/sync ORM boundary violations (Pitfall 1) are masked by `DJANGO_ALLOW_ASYNC_UNSAFE=true` in `conftest.py`. This must be resolved before any performance claims or further feature work — it is a correctness prerequisite, not a nice-to-have. The duplicate error classes (Pitfall 14) and PATCH semantics (Pitfall 4) also belong here.
**Delivers:** Zero sync ORM calls in async handler paths; `DJANGO_ALLOW_ASYNC_UNSAFE=true` removed; error classes consolidated in `core/errors.py`; PATCH sentinel pattern verified; all existing 4143 tests passing with correct async constraints
**Addresses:** Routing, schema validation, error handling (all table stakes already implemented — this phase verifies correctness)
**Avoids:** Pitfalls 1 (async/sync boundary), 4 (PATCH null/absent), 14 (duplicate errors)

### Phase 2: Performance Baseline and Optimization
**Rationale:** After correctness is established, benchmark against DRF and django-ninja to validate performance claims. The stripped middleware stack for API-only deployments is the single biggest lever for closing the FastAPI throughput gap. This phase also validates that no per-request introspection leaks exist (Pitfall 7).
**Delivers:** Documented req/s benchmarks for core CRUD endpoints vs DRF vs django-ninja; high-performance middleware profile documented and shipped; Granian added to optional server group; profiler run on hot path confirming zero `get_type_hints`/`inspect` calls per-request
**Uses:** Granian 2.6.0+, orjson, Pydantic v2 model_construct(), psycopg3 pool
**Avoids:** Pitfall 7 (per-request introspection), Pitfall 8 (sync middleware in ASGI)

### Phase 3: CLI Scaffolding and Type Generation
**Rationale:** The "ships faster than DRF/ninja" value proposition is best demonstrated in a 30-second CLI demo. `generate_crud MyApp.Model --full` generating a controller + schema + service + admin + test file is the strongest adoption driver. TypeScript type generation is the second most demonstrable differentiator.
**Delivers:** `generate_crud` producing working scaffold in one command; `sync_types` generating TypeScript interfaces, Zod schemas, and API client; `generate_ai_context` for LLM-readable project context; `matt doctor`/`matt routes`/`matt info` Rich CLI commands
**Addresses:** DX "Ship Faster" differentiators; AI-native DX features; cross-language type generation
**Avoids:** Pitfall 17 (OpenAPI schema drift — generated types must match actual API behavior)

### Phase 4: Integrated Batteries — Auth Hardening and Multi-Tenancy
**Rationale:** Multi-tenancy is the #1 feature no other API framework includes out of the box. Auth hardening (token revocation blacklist with purge, CSRF exemption for JWT endpoints, Passkeys/WebAuthn, OAuth/SSO) must be production-verified before multi-tenancy builds on top of it. Auth is the dependency layer for multi-tenancy (user/org relationship).
**Delivers:** JWT blacklist with purge command and post-logout security test; CSRF exemption verified on JWT endpoints; multi-tenancy models (Organization, Team, Membership) with permission integration; org-scoped API access patterns documented
**Addresses:** Auth table stakes + RBAC differentiators; multi-tenancy integrated batteries
**Avoids:** Pitfall 12 (JWT revocation), Pitfall 15 (CSRF conflicts with JWT), Pitfall 5 (hard dependency on non-Django auth libs)

### Phase 5: Billing, Feature Flags, and Analytics
**Rationale:** These three modules are independent of each other but all depend on the auth/multitenancy layer (org-scoped subscriptions, per-user flags, per-user event tracking). They constitute the second tier of "no other framework includes this" differentiators.
**Delivers:** Stripe/PayPal/Polar billing with subscription management; feature flags with DB/Redis/LaunchDarkly/Unleash backends; analytics event tracking with session and funnel aggregations; A/B experiments module with multi-armed bandit and statistical analysis
**Addresses:** Integrated batteries (billing, flags, analytics, experiments)
**Avoids:** Pitfall 5 (third-party dependency coupling — all integrations must be optional extras)

### Phase 6: Real-Time and Notifications
**Rationale:** WebSockets and notifications depend on the same auth/presence infrastructure. Grouping them reduces redundant work. Django Channels is the only viable Django WebSocket layer — the architecture is well-understood.
**Delivers:** WebSocket consumers with auth middleware and presence tracking; in-app messaging with WebSocket transport; push notifications (FCM/APNs), SMS, email notification dispatch; `notifications/` and `messaging/` modules complete
**Addresses:** WebSockets differentiator; notifications integrated battery
**Avoids:** Pitfall 8 (sync middleware — Channels consumers must be async)

### Phase 7: Deployment, Observability, and Documentation
**Rationale:** Final hardening before open promotion. CONN_MAX_AGE bug (Pitfall 2) must be fixed in all CLI-generated deployment config. Observability (logging, metrics, tracing) and deployment configs (Docker, Fly.io, Railway, Render, AWS, Hetzner) round out the batteries.
**Delivers:** All CLI deployment templates emit `CONN_MAX_AGE=0`; observability module (structured logging, Prometheus metrics, OTEL tracing) complete; Docker/Fly/Railway config generators in deployment module; architecture decision records written; migration guide from django-ninja published
**Addresses:** Deployment pitfall; observability battery; developer ergonomics (migration from ninja)
**Avoids:** Pitfall 2 (CONN_MAX_AGE under ASGI), Pitfall 5 (Django version coupling — CI must test 5.2 LTS + 6.0)

### Phase Ordering Rationale

- **Correctness before performance:** Benchmarks against DRF/ninja are meaningless if the async/sync boundary is broken. Phase 1 must precede Phase 2.
- **Core before batteries:** All integrated battery modules (auth, multitenancy, billing, analytics, websockets) depend on the core router/controller/schema being stable and correct. Phases 1-2 establish this.
- **Auth before multitenancy:** The org/team/membership model is built on top of Django's user model with the auth permission system. Phase 4 cannot start until auth hardening is verified.
- **CLI before batteries:** Demonstrating `generate_crud` and type generation (Phase 3) validates the DX premise before investing in the full battery set.
- **Independent battery phases:** Phases 5 and 6 can overlap — billing/flags/analytics have no dependency on WebSockets/notifications and vice versa.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (Multi-Tenancy):** Row-level security patterns, org-scoped queryset filtering, and invitation flows have multiple viable implementation strategies — research the Django multi-tenancy ecosystem (django-tenants, pgschemas) to confirm the chosen approach (shared schema, org FK filtering) is the right call for django-matt's target market (B2B SaaS, not data isolation at the DB level).
- **Phase 6 (WebSockets):** Django Channels v4 architecture (in-memory channel layer vs Redis channel layer) and presence tracking at scale need research before implementation begins.
- **Phase 5 (Billing):** Stripe API versions and webhook signature verification patterns change frequently — verify current best practices at implementation time.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Correctness Audit):** The bugs are already identified; the audit process is mechanical.
- **Phase 2 (Performance):** Benchmarking methodology is well-documented; Granian integration is straightforward.
- **Phase 3 (CLI + Type Gen):** The feature is already partially implemented; the TypeScript/Zod/Swift generation patterns are well-understood.
- **Phase 7 (Deployment + Observability):** Docker, Fly.io, Railway configs are templatable; OTEL/Prometheus patterns are well-documented.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI and official release notes. Granian benchmark is MEDIUM (synthetic, Dec 2025) but the directional finding is reliable. |
| Features | HIGH | Table stakes verified against DRF/ninja/FastAPI docs. Competitor pain points sourced from documented issues and real-world usage reports. Differentiator value for integrated batteries is MEDIUM — the sum is the claim, individual modules are replicable. |
| Architecture | HIGH | Based on direct codebase inspection plus FastAPI/DRF architecture comparisons from official sources. The patterns are established and working. |
| Pitfalls | HIGH | All critical pitfalls have multiple corroborating sources. The CONN_MAX_AGE Django ticket is first-party. The PATCH bug is a documented django-ninja issue. The async/sync masking is first-party (CLAUDE.md Known Issues). |

**Overall confidence:** HIGH

### Gaps to Address

- **MCP integration value:** MCP became the dominant agent tooling standard in 2025 (confirmed), but the value of a framework-specific MCP integration for django-matt is unvalidated. Defer to post-v1 and validate by gathering feedback from agentic coding users.
- **django-shinobi and django-bolt competitive positioning:** Both are named competitors in the space. The research did not include direct feature comparison with these projects. Recommend a quick feature audit of django-shinobi and django-bolt before finalizing Phase 3 (CLI/typegen) to confirm django-matt's differentiators hold against them specifically, not just against DRF/ninja/FastAPI.
- **Granian production readiness at scale:** Granian (Rust/Tokio) is newer than uvicorn. Benchmark data is from Dec 2025 synthetic runs. Recommend running granian under realistic load (concurrent connections, DB-bound endpoints) before documenting it as the default recommendation in deployment guides.
- **Pydantic 2.11 nested ORM validator behavior:** Pitfall 10 (nested validators silently not running) is identified but requires an explicit test suite to confirm current behavior. The gap closes when that test suite exists.

---

## Sources

### Primary (HIGH confidence)
- Django 5.2/6.0 release notes — https://docs.djangoproject.com/en/6.0/releases/6.0/
- Django async documentation — https://docs.djangoproject.com/en/5.2/topics/async/
- Django ticket #33497 (CONN_MAX_AGE ASGI bug) — https://code.djangoproject.com/ticket/33497
- Pydantic v2.11 release announcement — https://pydantic.dev/articles/pydantic-v2-11-release
- orjson 3.11.7 PyPI — https://pypi.org/project/orjson/
- uv 0.10.9 PyPI — https://pypi.org/project/uv/
- ruff 0.9.0 — https://astral.sh/blog/ruff-v0.9.0
- django-ninja v1.5.x — https://django-ninja.dev/whatsnew_v1/
- Haki Benita: DRF serializer performance benchmarks — https://hakibenita.com/django-rest-framework-slow
- DRF GitHub discussion #9499 (ModelSerializer performance) — https://github.com/encode/django-rest-framework/discussions/9499
- django-ninja issue #1045 (PATCH Optional fields bug) — https://github.com/vitalik/django-ninja/issues/1045
- Pydantic migration guide v1 → v2 — https://docs.pydantic.dev/latest/migration/
- TechEmpower Round 23 (2025-02-24) — https://www.techempower.com/benchmarks/
- Django Developers Survey 2025 — https://lp.jetbrains.com/django-developer-survey-2025/
- Internal codebase (`django_matt/`, ROADMAP.md, CLAUDE.md, tasks/lessons.md) — first-party

### Secondary (MEDIUM confidence)
- Granian benchmarks (Dec 2025, v2.6.0) — https://github.com/emmett-framework/granian/blob/master/benchmarks/vs.md
- psycopg3 async performance benchmark — https://www.tigerdata.com/blog/psycopg2-vs-psycopg3-performance-benchmark
- Django native connection pooling — https://saurabh-kumar.com/articles/2025/06/cut-django-database-latency-by-50-70ms-with-native-connection-pooling/
- FastAPI vs django-ninja community benchmark — https://github.com/tanrax/python-api-frameworks-benchmark
- jujens.eu: Django-Ninja review (2025) — https://www.jujens.eu/posts/en/2025/Jul/06/django-ninja/
- Loopwerk: DRF vs Django Ninja (2024) — https://www.loopwerk.io/articles/2024/drf-vs-ninja/
- TestDriven.io: DRF Pros and Cons — https://testdriven.io/blog/drf-pros-cons/
- HackerNews: Django REST Framework problem — https://news.ycombinator.com/item?id=43510495
- Pydantic model_construct discussion — https://github.com/pydantic/pydantic/discussions/6388
- Modern JWT auth mistakes — https://dev.to/alvinseyidov/modern-web-authentication-security-jwt-cookies-csrf-and-common-developer-mistakes-fpj

### Tertiary (LOW confidence / needs validation)
- FastAPI adoption statistics 2025 (38% of Python devs switching) — https://byteiota.com/fastapi-in-2025-why-38-of-python-developers-are-switching/ — third-party analysis, unverified methodology
- django-shinobi and django-bolt feature sets — not directly researched; competitive positioning relative to these two needs a dedicated audit before Phase 3

---
*Research completed: 2026-03-07*
*Ready for roadmap: yes*
