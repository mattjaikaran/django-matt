# Django Matt Enhancement Research

> Consolidated findings from django-ninja, django-ninja-extra, django-bolt, django-shinobi, and django-ninja-crud.
> Research date: 2026-02-22

---

## Executive Summary

Researched 200+ open issues and PRs across 5 Django API framework projects. Findings organized into **3 tiers** by impact and effort. django-matt is already ahead of all these projects in most areas (permissions, multitenancy, lifecycle hooks, async-first, filtering, service layer). The gaps below represent real opportunities to pull further ahead.

---

## Tier 1: High Impact, Should Implement

### 1. Bulk CRUD Operations
**Source:** django-ninja-crud gap, django-bolt gap, common DRF feature request
**Status:** Neither library supports bulk create/update/delete
**Proposal:** Add `BulkCreateView`, `BulkUpdateView`, `BulkDeleteView` to `views/`
```python
class ProductViewSet(APIViewSet):
    bulk_create = BulkCreateView(max_items=100)
    bulk_update = BulkUpdateView(max_items=100)
    bulk_delete = BulkDeleteView(max_items=100)
```
**Why:** Extremely common REST API need. No Django API framework does this well.

### 2. Permissions in OpenAPI Schema
**Source:** django-ninja-extra #324 (actively worked)
**Status:** OpenAPI shows auth but not permission/role requirements
**Proposal:** Add `x-permissions` and `x-roles` extension fields to OpenAPI operation schemas. Extract from `permission_classes` and decorators like `@requires_role("admin")`.
```json
{
  "x-permissions": ["can_edit_products"],
  "x-roles": ["admin", "editor"],
  "x-auth-required": true
}
```
**Why:** Huge DX win for frontend devs and API consumers. No framework does this today.

### 3. Django Choices/TextChoices as OpenAPI Enums
**Source:** django-shinobi (implemented), django-ninja gap
**Status:** ModelSchema doesn't auto-detect Django choices fields
**Proposal:** Schema generation should detect `choices`, `TextChoices`, `IntegerChoices` on model fields and emit OpenAPI enums. Directly improves `typegen/` TypeScript/Swift output.
**Why:** Generated client code gets proper enum types instead of bare strings/ints.

### 4. Lifecycle Hooks on MattAPI (Startup/Shutdown)
**Source:** django-bolt #96, django-ninja #1601
**Proposal:** `on_startup` and `on_shutdown` hooks on the `MattAPI` instance.
```python
api = MattAPI()

@api.on_startup
async def init_pools():
    await setup_connection_pool()

@api.on_shutdown
async def cleanup():
    await close_connection_pool()
```
**Why:** Essential for connection pools, cache warming, background scheduler init, metrics setup.

### 5. Request/Response Schema Mode Separation
**Source:** django-ninja PR #1139 (13 upvotes), django-ninja-extra #267
**Proposal:** Generate separate request vs response JSON schemas using Pydantic's `JsonSchemaMode`. Response schemas mark defaulted fields as required. `JSONField` uses `dict[str, Any]` for read, `Any` for write.
**Why:** Critical for accurate TypeScript codegen in `typegen/`. Currently defaulted fields show as optional in responses.

### 6. Configurable Lookup Field on ViewSets
**Source:** django-ninja-extra #178/PR #336
**Proposal:** Support `lookup_field` config on ViewSets for UUID, slug, or other unique fields.
```python
class ProductViewSet(APIViewSet):
    model = Product
    lookup_field = "slug"  # default: "pk"
```
**Why:** Standard REST pattern. DRF has it. Essential for clean URL design.

### 7. Skip Re-validation of Already-Validated Schema Instances
**Source:** django-ninja #1239 (12 upvotes), django-shinobi #52
**Status:** Partially addressed via `from_orm_fast()` / `model_construct()`
**Proposal:** Ensure ALL response serialization paths detect pre-validated Schema instances and skip re-validation. Audit beyond just list views.
**Why:** Up to 2x performance improvement on response serialization.

---

## Tier 2: Medium Impact, Worth Adding

### 8. Auto camelCase/snake_case Mapping
**Source:** django-bolt #105, django-ninja #961
**Proposal:** Global or per-schema opt-in for camelCase API responses with snake_case Python code.
```python
# Global config
MATT_API = {"CASE_STYLE": "camelCase"}

# Or per-schema
class UserSchema(Schema):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
```
**Why:** Nearly universal need for JavaScript/TypeScript frontends.

### 9. Standardized Error Envelope
**Source:** django-bolt PR #143 (Litestar-style)
**Proposal:** Standardize on `{status_code, detail, extra}` with per-field validation errors in `extra`. Pre-allocate static error bodies for common codes. `extra` is null in production for 500s.
```json
{
  "status_code": 400,
  "detail": "Validation failed",
  "extra": [
    {"message": "Field required", "key": "email", "source": "body"}
  ]
}
```
**Why:** Frontend-friendly, consistent, secure. Consolidates `core/errors.py` and `utils/errors.py`.

### 10. Ordering Enhancements
**Source:** django-ninja-extra #101, #223, #284
**Proposal:**
- Support relation traversal in ordering (`field__related_field`)
- Preserve model `Meta.ordering` as default (only override when client passes `?ordering=`)
- Emit ordering fields as OpenAPI enums for TypeScript codegen
**Why:** Three related fixes that make ordering production-ready.

### 11. Custom Field Registration
**Source:** django-bolt #122
**Proposal:** A field registry for custom Django model fields to declare their serialization type.
```python
register_field_type(MoneyField, Decimal, {"type": "number", "format": "decimal"})
```
**Why:** No Django API framework handles custom fields well. First-class support is a differentiator.

### 12. Opt-in `full_clean()` in CRUD Views
**Source:** django-shinobi #35, django-ninja #443 (14 upvotes)
**Proposal:** Add `validate_model=True` option that calls `full_clean()` (via `sync_to_async` in async context) before save. Bridges Pydantic schema validation and Django model validation.
**Why:** Well-known Django footgun that no API framework addresses.

### 13. PK Nullability Audit
**Source:** django-shinobi (fixed upstream bug), django-ninja #1160 (10 upvotes)
**Proposal:** Audit schema generation to ensure PKs are never marked `Optional` in response schemas. Use `null` (not `blank`) as source of truth for nullability.
**Why:** Subtle bug that corrupts TypeScript types (`string | null` instead of `string`).

### 14. Scenario-Based CRUD Testing
**Source:** django-ninja-crud's companion `django-rest-testing`
**Proposal:** Add declarative test scenarios to `testing/`.
```python
class UserCRUDTest(CRUDTestCase):
    viewset = UserViewSet
    model_factory = UserFactory
    list_scenarios = [
        Scenario(expected_status=200, expected_count=3),
        Scenario(query_params={"is_active": False}, expected_count=0),
    ]
```
**Why:** Massive reduction in test boilerplate for CRUD-heavy APIs.

### 15. Retry-After Header on Throttle
**Source:** django-ninja #1666
**Proposal:** Auto-set `Retry-After` header when returning 429. Make IP resolution configurable. Support per-route throttle scopes.
**Why:** HTTP standard compliance. Easy fix, high correctness value.

### 16. Django 5.2 LoginRequiredMiddleware Compatibility
**Source:** django-ninja #1461
**Proposal:** Ensure MattAPI views work with Django's `LoginRequiredMiddleware`. Auto-apply `login_not_required` to API views or provide middleware adapter.
**Why:** Django 5.2 is current. Users will hit this.

### 17. Sync/Async Auto-Detecting Auth
**Source:** django-ninja-extra #252
**Proposal:** Single `MattJWTAuth` class that auto-detects sync vs async context. No separate `JWTAuth` / `AsyncJWTAuth`.
**Why:** Having two auth classes is a usability failure.

### 18. Multi-Response Schema Support
**Source:** django-ninja-crud #490
**Proposal:** Support `responses` parameter for views that return different status codes with different schemas.
```python
create_user = CreateView(
    responses={201: UserSchema, 400: ErrorSchema, 409: ConflictSchema}
)
```
**Why:** Enriches OpenAPI docs with accurate per-status response types.

---

## Tier 3: Lower Priority, Nice to Have

### 19. Dynamic Field Selection
**Source:** django-ninja #333 (11 comments), django-ninja-crud #462
**Proposal:** `?fields=id,name,email` query parameter that integrates with `.values()` for DB optimization.

### 20. Idempotent Router Registration
**Source:** django-ninja PR #437 (10 upvotes, 3 years open)
**Proposal:** `add_router()` / controller registration should be idempotent (dedup on re-registration).

### 21. Qualified OpenAPI Schema Naming
**Source:** django-shinobi #51
**Proposal:** Use fully qualified names (module + class) to prevent `UserSchema` / `UserSchema2` collisions.

### 22. Conditional Pagination
**Source:** django-ninja-extra #195
**Proposal:** `?no_page=1` or `pagination=false` header to skip pagination (for exports).

### 23. Configurable Nullable Representation
**Source:** django-shinobi #70
**Proposal:** Let users control `T | None` vs `Optional[T]` vs sentinel for OpenAPI/codegen.

### 24. FK `_id` Field Support in ModelSchema
**Source:** django-ninja #517 (5+ upvotes, 3 years open)
**Proposal:** `model_fk_use_pks = True` config that maps FK fields to `_id` counterparts.

### 25. Pydantic `model_dump(mode="json")` in Response Pipeline
**Source:** django-ninja #1624
**Proposal:** Use `model_dump(mode="json")` instead of `model_dump()` + custom encoder. Handles sets, UUIDs, etc. natively. Pairs with orjson.

### 26. Python 3.14 CI Testing
**Source:** django-shinobi #65, django-ninja-crud #532
**Proposal:** Add to CI matrix for PEP 649/749 annotation changes.

### 27. Pydantic Upper Bound Pin
**Source:** django-shinobi practice
**Proposal:** Pin `pydantic>=2.0,<2.13` to prevent untested version breakage.

### 28. CreateView Default Status Code 201
**Source:** django-ninja-crud observation
**Proposal:** `CreateView` should return 201 Created, not 200 OK. Make status_code configurable per view.

---

## What django-matt Already Does Better Than All of Them

| Feature | django-matt | Others |
|---------|-------------|--------|
| Service layer | Clean CRUD via services | Logic in views/controllers |
| Permissions system | Full RBAC, IsOwner, decorators | None (ninja-extra partial) |
| Multitenancy | Organization, Team, Membership | Nobody has this |
| Lifecycle hooks on views | before/after each CRUD op | Nobody has this |
| Queryset optimization | Auto select_related/prefetch_related | Nobody has this |
| Filtering/search/ordering | Full module with pluggable backends | Delegates to ninja or missing |
| Async-first | Native throughout | Partial or bolt-on |
| TypeScript/Swift codegen | Built-in typegen module | Nobody has this |
| AI/ML integration | Built-in modules | Nobody has this |
| Feature flags, analytics, experiments | Built-in modules | Nobody has this |
| Billing (Stripe/PayPal/Polar) | Built-in module | Nobody has this |

---

## Architectural Lessons Learned

1. **Never store registration metadata on the class itself** — use per-API-instance registry (django-ninja-extra #287)
2. **Never mutate inherited function objects** — copy/clone per controller subclass (django-ninja-extra #319)
3. **Use `contextvars.ContextVar` for request-scoped state** — not thread-locals (django-ninja-extra #75)
4. **Auth must run before permissions, always** — was a shipped bug in ninja-extra (#212)
5. **Decorator chains must propagate through all router tiers** — security vulnerability in django-ninja (#1597)
6. **Decorators should apply in declaration order** (outside-in), matching Django middleware (#1598)
7. **Route registration must prioritize static over dynamic paths** (django-ninja-extra #340)
8. **Preserve `__fields_set__` through serialization** for `exclude_unset` support (django-ninja #1542)

---

---

## NestJS Patterns (High-Value Additions)

### Interceptors (HIGH priority)
Composable request/response wrappers at controller/method level. Fills the gap between global Django middleware and inline code. Enables caching, logging, timeout, response transformation without touching middleware. `_setup_methods()` in controller.py is the perfect hook point.

### Event Bus (HIGH priority)
Async Pub/Sub with Topic/Subscription. Far better than Django signals for async apps. Enables decoupled module communication. Backends: in-memory (dev), Redis Streams, Celery, SQS.

### Config Validation (HIGH priority)
Pydantic-validated config namespaces catch misconfigurations at startup. Natural fit — Pydantic validates env vars with rich types and constraints.

### Serialization Groups (MEDIUM priority)
Role-based field visibility — admin sees all fields, user sees limited. `groups=["admin", "public"]` on schema fields.

### Layered Exception Filters (MEDIUM priority)
Typed, composable exception handlers at method/controller/global scope. More flexible than current single-level error handling.

### Method-level Guards (MEDIUM priority)
`@guard(IsAdmin)` on individual controller methods, not just controller-level `permission_classes`.

### Already covered by django-matt:
- DI container (singleton, scoped, transient) — matches NestJS
- Versioning — exceeds NestJS (5 strategies vs 4)
- Task scheduling — exceeds NestJS (multi-backend)
- Health checks — on par with NestJS Terminus
- Queue system — multi-backend (Celery, Dramatiq, Django-Q)

---

## Encore Patterns

### Pub/Sub Events (HIGH priority)
Declarative Topic/Subscription pattern. django-matt's task system is RPC-style ("do X later"), not event-driven ("X happened, react"). Add `django_matt.events` module.

### Secrets Management (HIGH priority)
Declarative `secret("STRIPE_KEY")` references. Backends: env vars, .env, Vault, AWS SM. Include `matt secrets` CLI and `matt doctor` validation.

### Infrastructure Introspection (MEDIUM priority)
`matt infra` CLI analyzes code imports and generates infrastructure manifests (Docker Compose, Terraform).

### Auto-Instrumentation (MEDIUM priority)
Zero-config tracing for all controller methods, DB queries, cache ops. Current observability is opt-in decorator-based.

### Already covered: Cron jobs, auth, database migrations, environment management.

---

## Hono Patterns

### SSE/Streaming Helpers (HIGH priority)
`sse_response()` and `stream_response()` for AI streaming, live dashboards, real-time updates. Simpler than WebSockets for many use cases.

### Route-Scoped Middleware (MEDIUM priority)
Per-controller and per-route middleware application. Currently Django middleware is globally applied.

### RPC-Style Typed Client (MEDIUM priority)
Enhance typegen client with Hono-style path autocomplete and request/response type inference.

### Already covered: Request validation (Pydantic = Zod), OpenAPI from schemas, testing helpers.

---

## django-ninja-boilerplate Patterns (to preserve)

### Controller Patterns
- Consistent decorator stack: `@paginate → @http_get → @handle_exceptions → @log_api_call`
- `auth=JWTAuth()` at controller level
- Response types as status-code dicts: `response={200: Schema, 400: dict}`
- Tuple returns: `return 200, data`

### Service Layer
- Generic `CRUDService[ModelT]` with transaction safety, audit tracking, soft delete, bulk ops
- `full_clean()` before save
- Tuple return convention `(success, message, data)` for composability
- Singleton instances at module level

### Schema Organization
- Separate Create/Update/Response schemas per entity
- Base schemas for pagination, errors, bulk actions
- UUID/datetime auto-conversion validators

### Already improved in django-matt:
- Async-first (boilerplate is sync-only)
- DI container (boilerplate uses module-level singletons)
- Filtering (boilerplate uses inline `if field: qs.filter()`)
- Pagination (boilerplate delegates to ninja_extra's basic `@paginate`)

---

## Sources

- [django-ninja issues](https://github.com/vitalik/django-ninja/issues) — 138 open
- [django-ninja-extra issues](https://github.com/eadwinCode/django-ninja-extra/issues) — 20 open
- [django-bolt issues](https://github.com/dj-bolt/django-bolt/issues) — 12 open
- [django-shinobi issues](https://github.com/pmdevita/django-shinobi/issues) — 10 open
- [django-ninja-crud issues](https://github.com/hbakri/django-ninja-crud/issues) — 8 open
- [NestJS docs](https://docs.nestjs.com) — guards, interceptors, modules, CQRS, config, events
- [Encore docs](https://encore.dev/docs) — infrastructure-from-code, Pub/Sub, secrets
- [Hono docs](https://hono.dev/docs) — middleware composition, RPC mode, SSE/streaming
- [django-ninja-boilerplate](https://github.com/mattjaikaran/django-ninja-boilerplate) — controller/service patterns
