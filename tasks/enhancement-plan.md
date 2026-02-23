# Django Matt Enhancement Plan

> Comprehensive plan derived from research across django-ninja, django-ninja-extra, django-bolt,
> django-shinobi, django-ninja-crud, NestJS, Encore, Hono, and the django-ninja-boilerplate.
> Date: 2026-02-22

---

## Research Sources

| Source | Key Takeaways |
|--------|---------------|
| **django-ninja** (138 open issues) | Double validation perf, async resolvers, request/response schema modes, permissions gap, throttle Retry-After, lifecycle hooks |
| **django-ninja-extra** (20 open issues) | Controller reuse across APIs, subclassable controllers, permissions in OpenAPI, configurable lookup_field, request-based queryset filtering, async permissions |
| **django-bolt** (12 open issues) | Error envelope standardization, custom field registration, camelCase mapping, lifecycle hooks, lazy init patterns |
| **django-shinobi** (10 open issues) | 15x serialization speedup (no DjangoGetter), choices→enums, PK nullability fix, full_clean() support, skip re-validation |
| **django-ninja-crud** (8 open issues) | Bulk operations gap, scenario-based testing, multi-response schemas, path parameter typing |
| **NestJS** | Interceptors, module system, event bus, config validation, serialization groups, layered exception filters, method-level guards |
| **Encore** | Pub/Sub event system, secrets-as-code, infrastructure introspection, auto-instrumentation |
| **Hono** | SSE/streaming helpers, route-scoped middleware, RPC-style typed client generation |
| **django-ninja-boilerplate** | Controller+service layer patterns, decorator stacks, schema organization, CRUDService[ModelT] |

---

## What django-matt Already Leads In

These are confirmed strengths — no work needed:

- Async-first architecture (native async ORM, async DI, async permissions)
- Service layer abstraction (CRUDController with clean separation)
- Lifecycle hooks on views (11 hook types, global + viewset-specific, priority ordering)
- Queryset optimization (auto select_related/prefetch_related from schema)
- Permissions system (RBAC, IsOwner, decorators, class-based + decorator-based)
- Filtering/search/ordering (pluggable backends, FilterSet)
- API versioning (URI, header, accept, query, hostname — exceeds NestJS)
- Task scheduling (Celery, Dramatiq, Django-Q + cron decorators — exceeds NestJS)
- Health checks (DB, cache, migration checks, readiness/liveness)
- TypeScript/Swift codegen (typegen module)
- DI container (singleton, scoped, transient lifetimes)
- Multitenancy, billing, feature flags, analytics, experiments, AI/ML

---

## Enhancement Phases

### Phase 1: Core DX & Correctness (Foundations)

Quick wins that fix bugs, improve correctness, and consolidate existing code.

| # | Enhancement | Effort | Impact | Files |
|---|------------|--------|--------|-------|
| 1.1 | **Unify error handling** — consolidate `utils/errors.py` into `core/errors.py`, standardize error envelope `{status_code, detail, extra}` | S | High | `core/errors.py`, `utils/errors.py`, imports across codebase |
| 1.2 | **PK nullability audit** — ensure PKs never marked Optional in response schemas | S | High | `core/schema.py` |
| 1.3 | **CreateView 201 status** — explicit 201 on CreateView, configurable `status_code` per view | S | Med | `views/create.py`, `views/base.py` |
| 1.4 | **Retry-After header on throttle** — auto-set when returning 429 | S | Med | `throttling/` |
| 1.5 | **Django choices → OpenAPI enums** — auto-detect TextChoices/IntegerChoices in schema generation | M | High | `core/schema.py`, `openapi/` |
| 1.6 | **Skip re-validation audit** — ensure `model_construct()` covers ALL response paths, not just lists | M | High | `core/controller.py`, `views/base.py`, `core/router.py` |
| 1.7 | **Ordering fixes** — relation traversal, preserve Meta.ordering, emit as OpenAPI enums | M | Med | `filtering/`, `openapi/` |

### Phase 2: Controller & View Enhancements

New capabilities on the CRUD system.

| # | Enhancement | Effort | Impact | Files |
|---|------------|--------|--------|-------|
| 2.1 | **Bulk CRUD views** — `BulkCreateView`, `BulkUpdateView`, `BulkDeleteView` with max_items, hooks, validation | M | High | `views/bulk.py` (new), `views/__init__.py` |
| 2.2 | **Configurable lookup_field on ViewSets** — UUID, slug, composite | S | High | `views/viewset.py`, `views/read.py`, `views/update.py`, `views/delete.py` |
| 2.3 | **Opt-in full_clean()** — `validate_model=True` with async wrapping | S | Med | `views/base.py`, `core/controller.py` |
| 2.4 | **Multi-response schemas** — `responses={201: Schema, 400: Error}` on views | M | Med | `views/base.py`, `openapi/` |
| 2.5 | **Permissions in OpenAPI** — `x-permissions`, `x-roles` extension fields | M | High | `openapi/`, `permissions/` |
| 2.6 | **Method-level guards** — `@guard(IsAdmin)` on individual controller methods | S | Med | `core/controller.py`, `permissions/` |

### Phase 3: Controller & View Enhancements

New CRUD capabilities, better ViewSet DX.

| # | Enhancement | Effort | Impact | Files |
|---|------------|--------|--------|-------|
| 3.1 | **Bulk CRUD views** — `BulkCreateView`, `BulkUpdateView`, `BulkDeleteView` with max_items, hooks, transactions | M | High | `views/bulk.py` (new), `views/__init__.py` |
| 3.2 | **Configurable lookup_field on ViewSets** — UUID, slug, composite | S | High | `views/viewset.py`, `views/read.py`, `views/update.py`, `views/delete.py` |
| 3.3 | **Opt-in full_clean()** — `validate_model=True` with `sync_to_async` wrapping | S | Med | `views/base.py`, `core/controller.py` |
| 3.4 | **Method-level permission overrides** — `@guard(IsAdmin)` on individual methods | S | Med | `core/controller.py`, `permissions/` |
| 3.5 | **SoftDeleteMixin for ViewSets** — reusable soft_delete/restore endpoints | S | Med | `views/mixins.py` (new) |

### Phase 4: DX & Compatibility

| # | Enhancement | Effort | Impact | Files |
|---|------------|--------|--------|-------|
| 4.1 | **camelCase/snake_case mapping** — global or per-schema opt-in | M | Med | `core/schema.py`, middleware |
| 4.2 | **Sync/async auto-detecting JWT** — single `MattJWTAuth` class | M | Med | `auth/jwt.py` |
| 4.3 | **Django 5.2 LoginRequiredMiddleware compat** | S | Med | middleware adapter |
| 4.4 | **Lifecycle hooks on MattAPI** — `@api.on_startup`, `@api.on_shutdown` | S | Med | `api.py` |
| 4.5 | **Dynamic field selection** — `?fields=id,name` with `.values()` optimization | M | Med | `filtering/`, `views/list.py` |
| 4.6 | **Conditional pagination** — `?no_page=1` for exports | S | Low | `pagination/` |

### Phase 5: Testing & Verification

| # | Enhancement | Effort | Impact | Files |
|---|------------|--------|--------|-------|
| 5.1 | **Scenario-based CRUD testing** — `CRUDTestCase` with declarative scenarios | M | High | `testing/scenarios.py` (new) |
| 5.2 | **TestClient cookie forwarding** — verify cookies pass through | S | Med | `testing/client.py` |
| 5.3 | **TestClient `auser()` mock support** | S | Med | `testing/client.py` |
| 5.4 | **Python 3.14 CI** — PEP 649/749 annotation changes | S | Low | CI config |
| 5.5 | **Pydantic version pinning** — upper bound | S | Low | `pyproject.toml` |

### Phase 6: Architectural Verification

Verify correctness — these were shipped bugs in other frameworks.

| # | Check | Effort | Risk | Source |
|---|-------|--------|------|--------|
| 6.1 | Controller registration metadata is per-API-instance, not on class | S | High | ninja-extra #287 |
| 6.2 | `_setup_methods()` clones inherited functions per subclass | S | High | ninja-extra #319 |
| 6.3 | Decorator chains propagate through all router tiers | S | Critical | ninja #1597 |
| 6.4 | Decorators apply in declaration order (outside-in) | S | Med | ninja #1598 |
| 6.5 | Static routes matched before parameterized paths | S | Med | ninja-extra #340 |
| 6.6 | Auth runs before permissions in middleware chain | S | High | ninja-extra #212 |
| 6.7 | `contextvars.ContextVar` used (not thread-locals) for request state | S | High | ninja-extra #75 |

---

## Tentative — Node.js-Inspired Ideas

> These patterns from NestJS, Encore, and Hono are good ideas but need architecture
> discussion before committing. They represent larger design decisions.

| Idea | Source | Notes |
|------|--------|-------|
| Interceptors (composable req/res wrappers) | NestJS | Fills gap between global middleware and inline code |
| Event bus / Pub/Sub (Topic/Subscription) | NestJS + Encore | Async event-driven communication between modules |
| Config validation namespaces | NestJS | Pydantic-validated config, fail-fast at startup |
| Layered exception filters | NestJS | Typed handlers at method/controller/global scope |
| Serialization groups | NestJS | Role-based field visibility |
| Secrets-as-code | Encore | Declarative `secret()` with backend abstraction |
| SSE/Streaming helpers | Hono | `sse_response()` for AI streaming, live dashboards |
| Infrastructure introspection | Encore | `matt infra` CLI generates Docker/Terraform from code |
| Auto-instrumentation | Encore | Zero-config tracing for controllers/DB/cache |
| Route-scoped middleware | Hono | Per-controller and per-route middleware |
| RPC-style typed client | Hono | Path autocomplete in typegen |
| Module system | NestJS | Formalized dependency graph between subpackages |
| CQRS | NestJS | Command/Query separation — only for event-sourced systems |

---

## Architectural Principles (from research)

These should be verified/enforced across the codebase:

1. **Never store registration metadata on the class** — use per-API-instance registry
2. **Never mutate inherited function objects** — clone per controller subclass
3. **Use `contextvars.ContextVar` for request-scoped state** — not thread-locals
4. **Auth runs before permissions, always** — enforce in middleware chain
5. **Decorator chains propagate through all router tiers** — no silent skips
6. **Decorators apply in declaration order** (outside-in)
7. **Static routes before dynamic** in registration
8. **Preserve `__fields_set__`** through serialization for `exclude_unset`
9. **`null` not `blank`** as source of truth for schema nullability
10. **Service layer for all business logic** — controllers stay thin

---

## Effort Key

- **S** = Small (< 1 day, single file or focused change)
- **M** = Medium (1-3 days, multiple files, some design)
- **L** = Large (3-5 days, new module, significant design)
- **XL** = Extra Large (1+ week, major architectural addition)
