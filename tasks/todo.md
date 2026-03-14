# Django Matt — Active Tasks

## In Progress

- [ ] Add test coverage for `auth/` module (JWT, OAuth, SSO, Passkeys, RBAC, API keys)
- [ ] Add test coverage for `billing/` module (Stripe, PayPal, Polar, webhooks)
- [ ] Add test coverage for `multitenancy/` module (Organization, Team, Membership, isolation)

## Up Next — Test Coverage

- [ ] Add test coverage for `views/` (CRUD views, APIViewSet)
- [ ] Add test coverage for `flags/` (feature flags, backends, rollout)
- [ ] Add test coverage for `analytics/` (tracker, backends, aggregations)
- [ ] Add test coverage for `experiments/` (A/B testing, bandits, analysis)
- [ ] Add test coverage for `graphql/` (schema gen, dataloaders, middleware)
- [ ] Add test coverage for `management/` commands

---

## Enhancement Plan

> Derived from 200+ issues across django-ninja, django-ninja-extra, django-bolt, django-shinobi, django-ninja-crud, and the django-ninja-boilerplate.
> Full research notes: `tasks/enhancement-research.md`
> Detailed plan: `tasks/enhancement-plan.md`

### Phase 1: Error Handling & Correctness

Consolidate duplicated code, fix known correctness issues, quick wins.

- [ ] 1.1 **Unify error handling** — consolidate `utils/errors.py` into `core/errors.py`
  - Standardize error envelope: `{status_code, detail, extra}`
  - Per-field validation errors in `extra`: `[{message, key, source}]`
  - Pre-allocate static error bodies for common codes (400, 401, 403, 404, 429)
  - `extra` is null in production for 500s (security)
  - Update all imports across codebase
  - Source: django-bolt PR #143, known issue in CLAUDE.md
- [ ] 1.2 **PK nullability audit** — ensure PKs never marked `Optional` in response schemas
  - Use `null` (not `blank`) as source of truth for nullability
  - Audit `core/schema.py` field mapping
  - Source: django-shinobi fix, django-ninja #1160 (10 upvotes)
- [ ] 1.3 **CreateView explicit 201** — add configurable `status_code` per view class
  - Router already defaults POST to 201, but make it explicit on the view
  - `BoundView.__call__` should respect `self.view.status_code`
  - Source: django-ninja-crud observation
- [ ] 1.4 **Retry-After header on 429** — auto-set when throttle triggers
  - Configurable IP resolution via callable in settings
  - Per-route throttle scopes
  - Source: django-ninja #1666, #1674, #1673
- [ ] 1.5 **Skip re-validation audit** — ensure `model_construct()` on ALL response paths
  - Currently only covers list serialization via `from_orm_fast()`
  - Audit single-object responses in create, read, update views
  - Detect pre-validated Schema instances and skip re-validation
  - Source: django-ninja #1239 (12 upvotes), django-shinobi #52

### Phase 2: Schema & OpenAPI Improvements

Better schema generation, better generated client code.

- [ ] 2.1 **Django choices → OpenAPI enums** — auto-detect TextChoices/IntegerChoices
  - Schema generation emits Pydantic enums for choice fields
  - OpenAPI output includes enum constraints
  - Directly improves `typegen/` TypeScript/Swift output
  - Source: django-shinobi (implemented)
- [ ] 2.2 **Permissions in OpenAPI** — `x-permissions`, `x-roles`, `x-auth-required` extension fields
  - Extract from `permission_classes` and decorators like `@requires_role("admin")`
  - Include in operation schema generation
  - Source: django-ninja-extra #324 (actively worked)
- [ ] 2.3 **Request/response schema mode separation**
  - Generate separate request vs response JSON schemas via Pydantic `JsonSchemaMode`
  - Response schemas: defaulted fields marked as required (not optional)
  - `JSONField`: `dict[str, Any]` for read, `Any` for write
  - Critical for accurate `typegen/` output
  - Source: django-ninja PR #1139 (13 upvotes), django-ninja-extra #267
- [ ] 2.4 **Ordering enhancements**
  - Support relation traversal (`field__related_field`)
  - Preserve model `Meta.ordering` as default (only override on explicit `?ordering=`)
  - Emit ordering fields as OpenAPI enums for TypeScript codegen
  - Source: django-ninja-extra #101, #223, #284
- [ ] 2.5 **Custom field registration** — `register_field_type(DjangoField, PydanticType, openapi_schema)`
  - No Django API framework handles custom fields well
  - Source: django-bolt #122
- [ ] 2.6 **FK `_id` field support** — `model_fk_use_pks=True` config on ModelSchema
  - Maps FK fields to their `_id` integer counterparts automatically
  - Source: django-ninja #517 (5+ upvotes, 3 years open)
- [ ] 2.7 **Qualified OpenAPI schema naming** — module+class to prevent collisions
  - Avoid `UserSchema` / `UserSchema2` in multi-app projects
  - Source: django-shinobi #51
- [ ] 2.8 **Multi-response schemas** — `responses={201: Schema, 400: Error, 409: Conflict}` on views
  - Enriches OpenAPI docs with accurate per-status response types
  - Source: django-ninja-crud #490

### Phase 3: Controller & View Enhancements

New CRUD capabilities, better ViewSet DX.

- [ ] 3.1 **Bulk CRUD views** — `BulkCreateView`, `BulkUpdateView`, `BulkDeleteView`
  - `max_items` config to prevent abuse
  - Hook support (before_bulk_create, after_bulk_create, etc.)
  - Transaction wrapping
  - Controller already has bulk_create/bulk_update — views don't expose them
  - Source: gap in all frameworks (django-ninja-crud, django-bolt, DRF feature request)
- [ ] 3.2 **Configurable lookup_field on ViewSets** — UUID, slug, composite
  - Controller already supports this (`controller.py:309`) — verify views do too
  - Ensure type annotations propagate to OpenAPI (UUID vs int vs str)
  - Source: django-ninja-extra #178/PR #336
- [ ] 3.3 **Opt-in full_clean()** — `validate_model=True` on ViewSet or per-view
  - Calls `full_clean()` before save, wraps in `sync_to_async` for async context
  - Bridges Pydantic validation and Django model validation
  - Source: django-shinobi #35, django-ninja #443 (14 upvotes)
- [ ] 3.4 **Method-level permission overrides** — `@guard(IsAdmin)` on individual methods
  - Currently only controller-level `permission_classes`
  - Source: NestJS guards pattern, django-ninja-extra #212
- [ ] 3.5 **SoftDeleteMixin for ViewSets** — reusable soft_delete/restore endpoints
  - Already in boilerplate pattern, standardize in django-matt
  - Source: django-ninja-boilerplate `SoftDeleteMixin`

### Phase 4: DX & Compatibility

Developer experience, framework compat, auth improvements.

- [ ] 4.1 **camelCase/snake_case mapping** — global or per-schema opt-in
  - Config: `MATT_API = {"CASE_STYLE": "camelCase"}`
  - Or per-schema via `ConfigDict(alias_generator=to_camel, populate_by_name=True)`
  - Request body: camelCase → snake_case; Response: snake_case → camelCase
  - Source: django-bolt #105, django-ninja #961
- [ ] 4.2 **Sync/async auto-detecting JWT** — single `MattJWTAuth` class
  - Auto-detect sync vs async context, use appropriate code path
  - No separate `JWTAuth` / `AsyncJWTAuth`
  - Source: django-ninja-extra #252
- [ ] 4.3 **Django 5.2 LoginRequiredMiddleware compat**
  - Auto-apply `login_not_required` to API views
  - Or provide middleware adapter
  - Source: django-ninja #1461
- [ ] 4.4 **Lifecycle hooks on MattAPI** — `@api.on_startup`, `@api.on_shutdown`
  - Connection pool init, cache warming, scheduler startup, metrics setup
  - Source: django-bolt #96, django-ninja #1601
- [ ] 4.5 **Dynamic field selection** — `?fields=id,name,email` query param
  - Integrate with `.values()` for DB optimization
  - Source: django-ninja #333, django-ninja-crud #462
- [ ] 4.6 **Conditional pagination** — `?no_page=1` or header to skip pagination for exports
  - Source: django-ninja-extra #195

### Phase 5: Testing Enhancements

Better test tooling for users of django-matt.

- [ ] 5.1 **Scenario-based CRUD testing** — `CRUDTestCase` with declarative scenarios
  - Each scenario: request params, expected status, expected body
  - Auto-generate happy/error path scenarios per ViewSet
  - Transaction savepoint isolation per scenario
  - Source: django-rest-testing (companion to django-ninja-crud)
- [ ] 5.2 **TestClient cookie forwarding** — verify cookies pass through in test requests
  - Source: django-shinobi #27
- [ ] 5.3 **TestClient `auser()` mock support** — for async endpoints using Django's async user access
  - Source: django-ninja PR #1339 (12 upvotes)
- [ ] 5.4 **Python 3.14 CI** — add to matrix for PEP 649/749 annotation changes
  - Source: django-shinobi #65, django-ninja-crud #532
- [ ] 5.5 **Pydantic version pinning** — upper bound `pydantic>=2.0,<2.13`
  - Prevent untested version breakage
  - Source: django-shinobi practice

### Phase 6: Architectural Verification

Verify these patterns are correctly implemented — bugs found in other frameworks.

- [ ] 6.1 **Controller registration metadata** — verify per-API-instance, not on class
  - Registering same controller across multiple API instances must work
  - Source: django-ninja-extra #287
- [ ] 6.2 **Inherited method cloning** — verify `_setup_methods()` clones per subclass
  - Never mutate inherited function objects in place
  - Source: django-ninja-extra #319
- [ ] 6.3 **Decorator chain propagation** — verify decorators propagate through all router tiers
  - Security vulnerability in django-ninja: intermediate router decorators silently skipped
  - Source: django-ninja #1597
- [ ] 6.4 **Decorator ordering** — verify outside-in (declaration order), not reversed
  - Source: django-ninja #1598
- [ ] 6.5 **Static vs dynamic route priority** — verify static paths matched before parameterized
  - Source: django-ninja-extra #340
- [ ] 6.6 **Auth before permissions execution order** — verify in middleware chain
  - Was a shipped bug in ninja-extra that hit production
  - Source: django-ninja-extra #212
- [ ] 6.7 **`contextvars.ContextVar` for request-scoped state** — verify no thread-locals
  - Breaks under ASGI multi-worker
  - Source: django-ninja-extra #75

---

## Tentative — Node.js-Inspired Ideas (Discuss Before Implementing)

> These came from NestJS, Encore, and Hono research. Good patterns but need
> architecture discussion before committing. See `tasks/enhancement-plan.md` for details.

- [ ] Interceptors — composable request/response wrappers (NestJS pattern)
- [ ] Event bus / Pub/Sub — async Topic/Subscription system (NestJS + Encore)
- [ ] Config validation namespaces — Pydantic-validated config at startup (NestJS)
- [ ] Layered exception filters — typed handlers at method/controller/global scope (NestJS)
- [ ] Serialization groups — role-based field visibility (NestJS)
- [ ] Secrets-as-code — declarative `secret()` references with backend abstraction (Encore)
- [ ] SSE/Streaming helpers — `sse_response()`, `stream_response()` (Hono)
- [ ] Infrastructure introspection — `matt infra` CLI generates Docker/Terraform from code (Encore)
- [ ] Auto-instrumentation — zero-config tracing for controllers/DB/cache (Encore)
- [ ] Route-scoped middleware — per-controller and per-route middleware (Hono)
- [ ] RPC-style typed client — Hono-style path autocomplete in typegen
- [ ] Module system — formalized dependency graph between subpackages (NestJS)
- [ ] CQRS — Command/Query separation with buses (NestJS)

---

## Remaining Roadmap Items

- [ ] PlanetScale support (Stage 9B.6)
- [ ] Kubernetes/Helm charts (Stage 9C.3)
- [ ] vLLM / llama.cpp / LocalAI integrations (Stage 10C)
- [ ] Vue renderer (Stage 12D.4)
- [ ] Svelte renderer (Stage 12D.5)

---

## Completed

- [x] Optimize CLAUDE.md (1,215 → 135 lines)
- [x] Fix CI — add pyright/twine deps, remove continue-on-error, fix Django constraint
- [x] Align pyproject.toml version targets to py312
- [x] Add .pre-commit-config.yaml
- [x] Rename claude.md → CLAUDE.md
- [x] Enhancement research — 9 frameworks analyzed, 200+ issues reviewed
- [x] Enhancement plan — 6-phase plan + tentative Node ideas written
- [x] **Centrifugo WebSocket backend** — `django_matt/websockets/centrifugo/` (config, tokens, client, proxy); Centrifugo is now the default backend; 25 tests
- [x] **Service layer** — `django_matt/services/` with `BaseService`, `CRUDService`, `BaseThirdPartyService`; `ServiceError` hierarchy; CLI template generator updated; 29 tests
- [x] **Service layer across examples** — todo, ecommerce, saas-starter, realtime-chat all migrated; 4 new `docs/services/` files; README/ROADMAP/architecture updated; 4234 tests passing
- [x] **Phase 6 architectural verification** — 2 bugs found+fixed (shared `tags` list in Controller, static routes not sorted before parameterized); 5 checks passed (method cloning, decorator order, auth→permissions order, ContextVar usage, decorator propagation)
- [x] **Dogfooding validation** — validated 3 example apps (quicktodo, ecommerce-v2, devplatform); fixed: ErrorMiddleware path (3 apps), `request.json` → `orjson.loads(request.body)` (19 controllers), `data:` → `body:` schema param (cart+order controllers), test assertion fixes
- [x] **Starter template upgrade** — startapi command: added `saas` template, `ErrorMiddleware` in settings, `body:` param fix, pyproject.toml/conftest/seed_data generation, Makefile with `uv run pytest`/lint/format/seed targets, CLAUDE.md+CI for all non-starter templates
- [x] **Phase 1.1 error unification** — `utils/errors.py` merged into `core/errors.py`; standardized `{status, detail, extra}` envelope; shim for backwards compat
- [x] **Phase 1.2 PK nullability** — PKs never Optional in response schemas; `field.null` not `field.blank` for optionality
- [x] **Phase 1.3 choices → enums** — Django `TextChoices`/`IntegerChoices` → `Literal[...]` for OpenAPI enum constraints
- [x] **Lint to zero** — migrated 35 UP046/UP047 Generic syntax to PEP 695; fixed F821, UP036; per-file-ignores for graphql/+views/base.py
