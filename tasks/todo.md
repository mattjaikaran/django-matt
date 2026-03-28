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

- [x] 1.1 **Unify error handling** — done (ROADMAP.md)
- [x] 1.2 **PK nullability audit** — done (ROADMAP.md)
- [x] 1.3 **choices → enums** — done (ROADMAP.md)
- [x] 1.4 **Retry-After header on 429** — all 429 paths include Retry-After (RFC 6585)
- [x] 1.5 **Skip re-validation** — `serialize_single()` uses `model_construct()` on all CRUD views

### Phase 2: Schema & OpenAPI Improvements

Better schema generation, better generated client code.

- [ ] 2.1 **Django choices → OpenAPI enums** — auto-detect TextChoices/IntegerChoices
  - Schema generation emits Pydantic enums for choice fields
  - OpenAPI output includes enum constraints
  - Directly improves `typegen/` TypeScript/Swift output
  - Source: django-shinobi (implemented)
- [x] 2.2 **Permissions in OpenAPI** — x-auth-required, x-roles, x-permissions extension fields
- [x] 2.3 **Request/response schema mode separation** — validation vs serialization modes in OpenAPI
- [x] 2.4 **Ordering enhancements** — relation traversal, Meta.ordering fallback, OpenAPI enums
- [x] 2.5 **Custom field registration** — register_field_type() for custom Django→Pydantic mappings
- [x] 2.6 **FK `_id` field support** — `model_fk_use_pks=True` maps FK to `_id` columns
- [x] 2.7 **Qualified OpenAPI schema naming** — auto-detect collisions, QUALIFIED_SCHEMA_NAMES setting
- [x] 2.8 **Multi-response schemas** — responses={404: ErrorSchema} on route decorators

### Phase 3: Controller & View Enhancements

New CRUD capabilities, better ViewSet DX.

- [x] 3.1 **Bulk CRUD views** — BulkCreateView, BulkUpdateView, BulkDeleteView with max_items + hooks
- [x] 3.2 **Configurable lookup_field** — ViewSet lookup_field/lookup_type propagate to detail views
- [x] 3.3 **Opt-in full_clean()** — validate_model=True on ViewSet or per-view, 422 on failure
- [x] 3.4 **Method-level permission overrides** — `@guard()` decorator overrides controller perms
- [x] 3.5 **SoftDeleteMixin** — restore + permanent delete endpoints, lifecycle hooks

### Phase 4: DX & Compatibility

Developer experience, framework compat, auth improvements.

- [x] 4.1 **camelCase/snake_case mapping** — global or per-schema opt-in (IN PROGRESS)
  - Setting: `DJANGO_MATT.CAMEL_CASE_API = True/False` (default: False)
  - ModelSchema: `alias_generator=to_camel` + `populate_by_name=True` when enabled
  - 5 serialization funnels updated with `by_alias=True`
  - OpenAPI: `model_json_schema(by_alias=True)` for matching docs
  - Source: django-bolt #105, django-ninja #961
- [x] 4.2 **Unified MattJWTAuth** — single class with authenticate() + aauthenticate()
- [x] 4.3 **Django 5.1+ LoginRequiredMiddleware compat** — auto `login_not_required` on all API views
- [x] 4.4 **Lifecycle hooks** — @api.on_startup, @api.on_shutdown with sync/async support
- [x] 4.5 **Dynamic field selection** — ?fields=id,name,email with .only() optimization
- [x] 4.6 **Conditional pagination** — ?no_page=1 or X-No-Pagination header, max_unpaginated safety cap

### Phase 5: Testing Enhancements

Better test tooling for users of django-matt.

- [x] 5.1 **Scenario-based CRUD testing** — CRUDTestCase + generate_crud_scenarios()
- [x] 5.2 **TestClient cookie forwarding** — cookie convenience methods + async client parity
- [x] 5.3 **TestClient auser() mock** — request.auser() in JWT middleware + test clients
- [ ] 5.4 **Python 3.14 CI** — add to matrix for PEP 649/749 annotation changes
- [x] 5.5 **Pydantic version pinning** — pydantic>=2.0.0,<3.0.0

### Phase 6: Architectural Verification

Verify these patterns are correctly implemented — bugs found in other frameworks.

- [x] 6.1 **Controller registration metadata** — verified: per-instance storage, no cross-contamination
- [x] 6.2 **Inherited method cloning** — verified: `setattr(self, ...)` wraps per-instance
- [x] 6.3 **Decorator chain propagation** — verified: explicit per-method, no silent skipping
- [x] 6.4 **Decorator ordering** — verified: native Python order, no reversal
- [x] 6.5 **Static vs dynamic route priority** — verified: `static_patterns + param_patterns`
- [x] 6.6 **Auth before permissions** — verified: middleware → BoundView. Fixed controller enforcement gap.
- [x] 6.7 **contextvars not thread-locals** — verified: zero `threading.local()`, all ContextVar

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
