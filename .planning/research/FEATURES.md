# Feature Landscape: Django Meta-Framework

**Domain:** Python/Django API Framework (meta-framework replacing DRF, django-ninja, FastAPI)
**Researched:** 2026-03-07
**Brownfield:** Substantial codebase exists with 4143 tests

---

## Research Context

This research covers what it takes for django-matt to be the default choice over:

- **DRF** (Django REST Framework) — mature, batteries-included, slow, bloated serialization
- **django-ninja** — type-safe, FastAPI-inspired, thin, missing class-based views and CRUD bundling
- **django-ninja-extra** — adds controller pattern to ninja, but still incomplete
- **FastAPI** — modern, fast, async-first, but no Django ORM, no admin, re-implements everything

The bar: "if you can't ship faster with django-matt than DRF or django-ninja, it hasn't shipped yet."

---

## Table Stakes

Features users expect from any serious API framework. Missing any one of these means developers will not adopt or will abandon.

### Routing and Request Handling

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Decorator-based routing (`@api.get`, `@api.post`) | FastAPI normalized this pattern; DRF's class-based routing feels archaic by comparison | Low | Exists | Core django_matt pattern |
| Path parameters with type coercion | Standard in FastAPI/Ninja | Low | Exists | `{id: int}` auto-coerces |
| Query parameter parsing | Standard | Low | Exists | |
| Request body parsing (JSON) | Standard | Low | Exists | orjson for performance |
| Response serialization with Pydantic | FastAPI made Pydantic the standard; DRF's serializers are the primary complaint | Medium | Exists | Pydantic v2, `from_orm_fast()` |
| Auto-generated OpenAPI/Swagger docs | Developers expect `/docs` and `/redoc` out of the box | Medium | Exists | openapi module |
| Async endpoint support | Django 4.1+ ASGI; FastAPI set the standard | Medium | Exists | Async-first design |
| HTTP method handling (GET/POST/PUT/PATCH/DELETE) | Fundamental | Low | Exists | |

**Confidence:** HIGH — verified against django-ninja docs, DRF docs, FastAPI docs, community comparisons.

### Authentication

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| JWT authentication | Industry standard for API auth | Medium | Exists | `auth/jwt.py` |
| Middleware-based auth | Rails/Django pattern; must not require per-route config | Low | Exists | `auth/middleware.py` |
| Permission system (IsAuthenticated, IsAdmin) | DRF normalized permission classes | Low | Exists | `permissions/` |
| Auth decorators (`@jwt_required`, `@requires_role`) | DX shortcut expected after ninja/DRF | Low | Exists | `auth/decorators/` |
| Token refresh | JWT standard | Low | Exists | refresh endpoint |
| Auth error responses (401/403 with detail) | Standard, but ninja's error handling is a known pain point | Low | Exists | via ErrorHandler |

**Confidence:** HIGH — django-ninja known pain: "doesn't handle more things regarding authentication ... for API key, HTTP Bearer or HTTP Basic auth, it gives you a base class you can subclass." Our implementation goes further.

### Schema and Validation

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Pydantic v2 schemas | FastAPI + django-ninja normalized Pydantic; DRF serializers are the #1 complaint | Medium | Exists | `core/schema.py` |
| ModelSchema (Django ORM → Pydantic) | Direct DRF equivalent; without this, devs write boilerplate | High | Exists | `core/schema.py` ModelSchema |
| Automatic request validation with clear errors | FastAPI's "killer feature" — validation errors auto-documented | Medium | Exists | ValidationAPIError |
| PATCH handling (partial updates, nullable vs absent) | django-ninja's `PatchDict` has a known critical bug (sets nullable=False fields to None) | High | Exists | Patched in our impl |
| Nested schema support | Required for real-world APIs | Medium | Exists | Pydantic v2 handles this |

**Confidence:** HIGH — django-ninja PatchDict bug is documented in jujens.eu 2025 post as a production-blocking issue. Our implementation must handle this correctly.

### Error Handling

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Structured error responses (RFC 7807 style) | APIs need consistent error contracts; DRF and ninja both have custom patterns | Medium | Exists | `core/errors.py` APIError hierarchy |
| HTTP status code mapping | Standard | Low | Exists | |
| 404 Not Found errors | Ninja: "developers don't like having to use get_object_or_404 all over the place" | Low | Exists | NotFoundAPIError |
| Validation error format | FastAPI's format is now the de facto standard | Low | Exists | ValidationAPIError |
| Custom exception handlers | DRF allows this; ninja requires more custom code | Medium | Exists | ErrorHandler class |

**Confidence:** HIGH — pain points sourced from multiple community discussions, verified against existing codebase.

### CRUD Operations

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Composable CRUD views (List, Create, Read, Update, Delete) | DRF's ModelViewSet is the standard; ninja requires 30+ lines for what ViewSet does in 4 | High | Exists | `views/` (list, create, read, update, delete) |
| Automatic URL routing for CRUD | DRF's router pattern; ninja forces manual URL registration | Medium | Exists | ViewSet wires routes |
| Pagination (Page, LimitOffset, Cursor) | Required for list endpoints in production | Medium | Exists | `pagination/` |
| Filtering and search | Required for list endpoints; DRF has django-filter integration | Medium | Exists | `filtering/` |
| Ordering | Standard | Low | Exists | `filtering/` |
| Queryset optimization (select_related/prefetch_related) | DRF's #1 performance pitfall: "doesn't automatically optimize query sets" | Medium | Exists | `views/base.py` auto-detects FK/M2M from schema |

**Confidence:** HIGH — DRF N+1 problem is documented by TestDriven.io. Our `optimize_queryset()` auto-detection from schema is a concrete improvement.

### Testing Support

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Test client with auth helpers | DRF has `APIClient.force_authenticate()` — developers expect this | Medium | Exists | `testing/client.py` |
| Schema factories (test data generation) | Reduces test boilerplate | High | Exists | `testing/factories.py`, `model_factory.py` |
| Response assertion helpers | DRF pattern; reduces test verbosity | Medium | Exists | `testing/assertions.py` |
| pytest integration | 63% of django devs use pytest (2025 survey) | Low | Exists | `testing/fixtures.py` |

**Confidence:** HIGH.

---

## Differentiators

Features that are not table stakes but drive adoption decisions. These are what make developers choose django-matt over established alternatives.

### DX: The "Ship Faster" Promise

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Class-based Controller pattern with permission_classes | django-ninja's biggest complaint is lack of CBVs; ninja-extra adds them but incompletely | High | `core/controller.py` — the #1 ninja-extra improvement |
| Single-pass method wrapping (DI + error handling in one closure) | Eliminates per-request overhead; ninja calls multiple decorators per request | High | Cached at registration time |
| Zero-boilerplate CRUD with ViewSet | 4-line CRUD vs DRF's 15 lines vs ninja's 30+ lines | High | `views/viewset.py` |
| Automatic queryset optimization from schema introspection | No other framework does this; eliminates N+1 by default | High | Detect FK/M2M at init, not per-request |
| Generate CRUD command (`generate_crud MyApp.Model --full`) | Rails-style scaffolding for controller + schema + service + admin + tests | High | `management/commands/generate_crud.py` |

**Confidence:** MEDIUM — competition verified, implementation exists, real-world DX value is hypothesis until validated.

### Performance

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| orjson everywhere (not optional) | 3-10x faster JSON than stdlib; FastAPI uses this; DRF uses stdlib | Low | Base dependency, already integrated |
| `model_construct()` for list serialization | Skips re-validation on already-validated ORM data; faster list endpoints | Medium | `core/schema.py` `from_orm_fast()` |
| Cached introspection at registration time | Type hints, field introspection, DI resolution done once at startup, never per-request | High | `_valid_filter_fields` frozenset, `get_type_hints()` cache |
| Singleton anonymous user | Eliminates object creation per-request for unauthenticated paths | Low | `_ANONYMOUS_USER` |
| JWT decode once, pass payload | Token decoded in middleware, passed as `_payload=` to avoid double-decode | Medium | |
| ASGI-first (Uvicorn/Gunicorn workers) | FastAPI-equivalent throughput for I/O-bound workloads | Low | Deployment module |

**Confidence:** HIGH — performance patterns are implemented and documented in MEMORY.md from verified profiling work.

### Type Generation (Cross-Language)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| TypeScript interfaces from Pydantic schemas | Eliminates frontend/backend type drift; Django Survey: 63% use type hints | High | `typegen/typescript.py` |
| Zod schema generation | Zod is the dominant runtime validation library in TypeScript ecosystems | High | `typegen/zod.py` |
| TypeScript API client generation | Auto-generated client matching server schemas; React Query compatible | High | `typegen/api_client.py` |
| Swift Codable struct generation | iOS/macOS native app development with correct types from day one | High | `typegen/swift.py` |
| `sync_types` CLI command | One command syncs types to frontend repo | Low | `management/commands/sync_types.py` |

**Confidence:** MEDIUM — implemented, but no third-party framework does all five in one integrated tool. Differentiation value is HIGH if the generated code is correct and ergonomic.

### AI-Native DX

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Context generation for LLMs (`generate_ai_context`) | Agentic coding is 2025's dominant DX trend; AI tools are #3 learning resource per Django survey | High | `ai/context/` |
| Framework self-documentation for code generation | LLMs generate correct django-matt code from examples instead of hallucinating DRF patterns | High | Example-driven documentation + context export |
| Structured example apps (todo, ecommerce, saas-starter, realtime-chat) | Concrete patterns for LLMs to reference when generating new endpoints | Medium | `examples/` |
| MCP-compatible tooling hooks | Model Context Protocol became the dominant agent tooling standard in 2025 | High | Future: API inspection via MCP |
| Agent-friendly API introspection | Agents can query running API for available endpoints, schemas, auth requirements | High | `inspector/` |

**Confidence:** MEDIUM (concept) / LOW (MCP specific) — AI coding trend confirmed by Django Survey 2025. MCP dominance confirmed by multiple sources. Implementation value unvalidated.

### Integrated Batteries (Unique Selling Point)

No other framework provides ALL of these in a single install:

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multi-tenancy (Organization/Team/Membership) | B2B SaaS table stakes; requires heavy custom code everywhere else | High | `multitenancy/` |
| Feature flags (DB, Redis, LaunchDarkly, Unleash) | A/B testing, gradual rollouts; every production app needs this | High | `flags/` |
| Stripe/PayPal/Polar billing | Billing is the first third-party integration every SaaS builds | High | `billing/` |
| WebSockets with auth middleware and presence | Real-time is increasingly table stakes for apps | High | `websockets/` |
| Analytics (event tracking, sessions, funnels) | Product analytics without Segment dependency | High | `analytics/` |
| Background tasks (Celery, Dramatiq, Django-Q) | Every production app uses task queues | Medium | `tasks/` |
| Audit logging with soft delete | Compliance and data recovery | Medium | `audit/` |
| File uploads with S3/R2/MinIO | Every app handles files | Medium | `files/` |
| Email (SendGrid, Mailgun, SES, SMTP) | Every app sends emails | Medium | `email/` |
| Push notifications (FCM, APNs, SMS) | Mobile-integrated apps | High | `notifications/` |
| In-app messaging with WebSocket transport | Chat/messaging without third-party service | High | `messaging/` |

**Confidence:** MEDIUM — the value is the integration; any individual module is replicable, but the sum is the differentiator.

### Migration Path from django-ninja

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Convention bridge (similar patterns, intentionally better where django-matt improves) | Reduces adoption friction from ninja projects | Medium | Design principle |
| CLI-guided migration (`migrate --from ninja`) | Automated conversion + TODO markers for manual review | High | `cli/commands/` planned |
| Compatibility notes in docs | Accelerates adoption decisions | Low | Documentation task |

**Confidence:** MEDIUM — convention bridge confirmed as design principle in PROJECT.md. CLI migration is partially implemented.

### Developer Ergonomics

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Rich CLI (`matt info`, `matt doctor`, `matt routes`, `matt models`, `matt new`) | Rails-style developer tooling; no other Django framework has this | High | `cli/` |
| Django Unfold admin integration | Modern admin UI out of the box; Django admin's biggest pain point is the UI | Medium | `admin/` |
| Content negotiation (JSON, XML, CSV, YAML, MsgPack) | Enterprise requirement; no boilerplate needed | Medium | `negotiation/` |
| Rate limiting / throttling built in | DRF has throttling but it's verbose; ninja has none | Medium | `throttling/` |
| API versioning strategies built in | Every mature API needs versioning; both DRF and ninja require third-party or custom | Medium | `versioning/` |
| Dependency injection container | Type-safe service injection without global state | High | `di/` |
| GraphQL via Strawberry (optional module) | Some teams need GraphQL; most need REST first | High | `graphql/` |
| HTMX helpers | Django Survey: HTMX grew from 5% to 24% (2021–2025) | Medium | `htmx/` |
| Observability (logging, metrics, tracing) | Production requirement; usually requires Sentry/Datadog setup | Medium | `observability/` |

**Confidence:** MEDIUM — features implemented; DX value validated by framework comparison research.

---

## Anti-Features

Features to deliberately NOT build or include in core. These represent scope creep risks or things that belong elsewhere.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Django ORM replacement | Django's ORM is the reason people use Django; replacing it destroys compatibility | Use Django ORM, enhance it with service layer patterns |
| React/Next.js frontend framework | Out of scope per PROJECT.md; would fragment focus | Ship TypeScript type gen + API client instead; React framework is "matt-stack v3" |
| Supporting Python < 3.12 | Legacy compatibility creates debt, blocks modern Python features (PEP 695, etc.) | State requirement clearly; 3.12+ is 2+ years old |
| Drop-in DRF compatibility layer | Creating a DRF compatibility shim would constrain the design forever | Convention bridge is enough; migration CLI is better than compat |
| Optional external dependencies in core | Every optional dep adds surface area for breakage; dependency philosophy: Django + orjson only | Flag integrations (Redis, Celery, Stripe) as optional extras, not core |
| GraphQL-first design | REST-first is the right call for 95%+ of APIs; GraphQL as optional module | Keep GraphQL in `graphql/` module, not in core routing |
| Admin UI replacement | Building a new admin UI is a multi-year project; Unfold solves this | Integrate Django Unfold, don't replace Django admin |
| Built-in CMS features | CMS is a different product category entirely | Not in scope |
| Mobile SDK generation (beyond Swift) | Increases scope without proportional return; Swift is justified (Matt's stack) | TypeScript (frontend) + Swift (iOS) are enough; Kotlin/Dart are separate projects |
| Custom ORM or query builder | Redundant with Django ORM; would break Django ecosystem compatibility | Service layer (`CRUDService`) is the right abstraction level |
| Framework-internal async task queue | Celery/Dramatiq exist and are proven; wrapping them is sufficient | `tasks/` should be adapters over existing queues |

---

## Feature Dependencies

```
Routing (core/router.py)
  └── Controller pattern (core/controller.py)
       ├── Permission system (permissions/)
       ├── DI container (di/)
       └── Error handling (core/errors.py)

Schema (core/schema.py)
  └── CRUD views (views/)
       ├── Pagination (pagination/)
       ├── Filtering (filtering/)
       └── Queryset optimization (views/base.py)

Auth (auth/)
  ├── JWT (auth/jwt.py)
  ├── RBAC (auth/rbac/)
  ├── Magic links (auth/magic_link.py)
  ├── OAuth (auth/oauth/)
  ├── SSO (auth/sso/)
  └── Passkeys (auth/passkeys/)

Service layer (services/)
  └── CRUD views delegate to services
  └── Billing, multitenancy, notifications use services

Type generation (typegen/)
  └── Depends on schema (core/schema.py)
  └── Produces TypeScript, Zod, Swift, API client

CLI (cli/)
  └── generate_crud → controller + schema + service + admin + tests
  └── sync_types → typegen output
  └── generate_ai_context → ai/context/

Multi-tenancy (multitenancy/)
  └── Depends on auth (user/org relationship)
  └── Billing depends on multitenancy (org-scoped subscriptions)

AI native (ai/)
  └── Depends on schema (context export)
  └── Depends on examples/ (training material)
```

---

## MVP Recommendation (for adoption validation)

**Highest priority — these drive the initial "ships faster than DRF/ninja" proof point:**

1. **Controller + CRUD views** — The core DX promise; validates the "4 lines of CRUD" claim vs ninja's 30 lines
2. **JWT auth with permission classes** — Required before any real project can use django-matt
3. **Pydantic ModelSchema + type generation** — The TypeScript/Zod output is a concrete, demonstrable differentiator
4. **Error handling** — ninja's biggest pain point; if errors "just work" like DRF, that alone drives switches
5. **CLI `generate_crud`** — Rails-style scaffolding is the fastest way to show "ships faster" in a demo

**Second priority — differentiators that win competitive comparisons:**

6. orjson performance + cached introspection benchmarks (proves FastAPI-level speed)
7. Multi-tenancy as built-in (no other API framework includes this)
8. Migration CLI from django-ninja (lowers adoption barrier for existing projects)
9. AI context generation (future-proof DX for agentic coding workflows)

**Defer until validated:**

- MCP tooling hooks (MCP is dominant but framework-specific integration is unproven value)
- GraphQL module (REST-first is right; GraphQL for teams that specifically need it)
- Full analytics/experiments suite (valuable but not adoption-driving)
- HTMX components (growing trend but not the API framework use case)

---

## Pain Point Mapping

This table maps known competitor pain points to django-matt features that address them.

| Competitor | Pain Point | django-matt Solution |
|------------|-----------|---------------------|
| django-ninja | No class-based views or ViewSets; 30+ lines for CRUD | `APIController` + `APIViewSet` with composable CRUD views |
| django-ninja | No bundled CRUD — write endpoint for every operation | `ViewSet` with `ListView`, `CreateView`, `ReadView`, `UpdateView`, `DeleteView` |
| django-ninja | PatchDict allows None on non-nullable fields (production bug) | Fixed PATCH handling in our schema layer |
| django-ninja | Error handling requires custom code; "doesn't just work" | `ErrorHandler` class, structured APIError hierarchy |
| django-ninja | No permission system; must repeat logic per endpoint | `permission_classes` on controller; `@requires_role`, `@requires_permission` |
| django-ninja | Maintenance concerns; issues open since 2020 | Internal ownership; no waiting on external maintainers |
| DRF | Serializer does too much (serialization + validation + model creation) | Schema handles schema; Service layer handles business logic; Views handle HTTP |
| DRF | N+1 queries not automatically prevented | `optimize_queryset()` auto-detects FK/M2M from schema at init time |
| DRF | Slow serialization (documented by DRF author himself) | orjson + `model_construct()` for list paths; 3-10x faster |
| DRF | No async support | Async-first design; sync_to_async fallbacks only |
| DRF | Steep learning curve; too many abstraction layers | Flatter controller pattern; single entry point |
| FastAPI | No Django ORM integration | Django ORM is core; no workarounds needed |
| FastAPI | No admin panel | Django admin + Unfold included |
| FastAPI | No built-in auth, billing, etc. | Full battery set: auth, billing, multitenancy, websockets |
| FastAPI | Single maintainer risk | Internal ownership |
| All | No TypeScript type generation | `sync_types` command generates TS interfaces, Zod schemas, API client |
| All | No AI context generation | `generate_ai_context` for LLM-readable project context |
| All | No CRUD scaffolding CLI | `generate_crud` for full scaffold in one command |

---

## Sources

- [Django Developers Survey 2025 Results](https://lp.jetbrains.com/django-developer-survey-2025/) — HIGH confidence, official data
- [Jujens: My opinion on Django Ninja (2025)](https://www.jujens.eu/posts/en/2025/Jul/06/django-ninja/) — HIGH confidence for ninja pain points
- [Loopwerk: DRF vs Django Ninja (2024)](https://www.loopwerk.io/articles/2024/drf-vs-ninja/) — HIGH confidence for DRF vs ninja comparison
- [TestDriven.io: DRF Pros and Cons](https://testdriven.io/blog/drf-pros-cons/) — HIGH confidence for DRF limitations
- [HackerNews: FastAPI production pain points](https://news.ycombinator.com/item?id=29471609) — MEDIUM confidence (community discussion)
- [django-ninja GitHub issues](https://github.com/vitalik/django-ninja) — MEDIUM confidence for open issues
- [django-ninja-extra docs](https://eadwincode.github.io/django-ninja-extra/) — HIGH confidence for controller pattern reference
- [FastAPI adoption statistics 2025](https://byteiota.com/fastapi-in-2025-why-38-of-python-developers-are-switching/) — MEDIUM confidence (third-party analysis)
- [CodeArtisanLab: Framework comparison 2025](https://codeartisanlab.com/drf-vs-fastapi-vs-django-ninja-vs-flask-best-python-web-frameworks-compared-in-2025/) — MEDIUM confidence
- Internal codebase analysis (`django_matt/` directory structure, ROADMAP.md, CLAUDE.md) — HIGH confidence
