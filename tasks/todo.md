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

- [x] 2.1 **Django choices → OpenAPI enums** — Literal types from choices now propagate to OpenAPI (enum constraints), TypeScript (`"a" | "b"`), Zod (`z.enum([...])`), and Swift (`String`/`Int`)
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

## Phase 7: Rust Native Extensions (Performance)

> **Goal:** Compile hot paths to Rust via PyO3 + maturin, achieving 10-50x speedups on
> per-request framework overhead while maintaining pure-Python fallbacks for all platforms.
>
> **Why Rust:** pydantic-core, orjson, ruff, uv, polars, cryptography, tiktoken, jiter all
> chose Rust+PyO3. Same perf ceiling as C, compile-time memory safety, maturin handles
> cross-platform wheel builds. The precedent is overwhelming — no other option comes close
> for new Python extension work in 2026.
>
> **Architecture:** Ship as optional `django-matt[rust]` extra. Pure Python fallback for every
> Rust-accelerated path. Pattern: `try: from django_matt._rust import X; except ImportError: ...`
>
> **Multi-session plan** — each sub-phase is independently shippable.

### Phase 7.0: Scaffold & Build Pipeline

Set up the Rust extension module, maturin build system, CI wheel building, and the
Python fallback pattern. No performance code yet — just infrastructure.

- [x] 7.0.1 **Rust crate scaffold** — `rust/` with `Cargo.toml`, `src/lib.rs`, `.cargo/config.toml`
- [x] 7.0.2 **maturin integration** — `rust/pyproject.toml`, `maturin develop --release` builds into venv
- [x] 7.0.3 **Fallback pattern** — `django_matt/_accel.py` with `HAS_RUST` flag, graceful ImportError
- [ ] 7.0.4 **CI wheel building** — GitHub Actions workflow (deferred until publish)
- [x] 7.0.5 **Dev workflow** — `make rust-dev/build/test/bench/clean` in Makefile
- [x] 7.0.6 **Benchmark harness** — `benchmarks/rust_vs_python.py` with router, JWT, query string

### Phase 7.1: Radix Tree URL Router

Replace Django's regex-based URL resolver with a Rust radix tree for route matching.
This is the single hottest path — called on every request.

- [x] 7.1.1 **Rust radix tree** — custom impl with static/param/wildcard, 12 Rust unit tests
- [x] 7.1.2 **Route registration API** — `router.add_route(method, pattern, endpoint_id)`
- [x] 7.1.3 **Route matching API** — `router.match_route(method, path) -> (endpoint_id, params)`
- [x] 7.1.4 **Python fallback** — via `_accel.py` import guard
- [x] 7.1.5 **Integration** — wired into `core/router.py` with `radix_dispatch()`, auto-builds on `get_urls()`
- [x] 7.1.6 **Benchmarks** — **4.0x overall, 12.7x on misses** (20 routes, 8 test cases)

**Measured gains:** 4.0x overall (1.7-12.7x per case)

### Phase 7.2: JWT Encode/Decode/Verify

Move the entire JWT pipeline to Rust. Every authenticated request hits this path.

- [x] 7.2.1 **HMAC signing** — HS256/HS384/HS512 via `hmac`+`sha2` crates, `subtle` for constant-time compare
- [ ] 7.2.2 **RSA/EC signing** — RS256/RS384/RS512, ES256/ES384/ES512 (deferred — `cryptography` pkg already Rust-based)
- [x] 7.2.3 **JWT encode** — `jwt_encode(payload_bytes, secret, algorithm) -> str`
- [x] 7.2.4 **JWT decode + verify** — `jwt_decode(token, secret, algorithm, verify_exp, leeway) -> dict`
- [x] 7.2.5 **Python fallback** — `jwt_builtin.py` auto-delegates to Rust for HMAC, falls back for RSA/EC
- [x] 7.2.6 **Integration** — wired into `auth/jwt_builtin.py`, transparent to 229 auth tests
- [x] 7.2.7 **Benchmarks** — **1.5x faster** (Python hmac is already C-accelerated). Main win: GIL release

**Measured gains:** 1.5x encode, 1.5x decode+verify. GIL release enables better concurrency.

### Phase 7.3: Fast Schema Serialization

JSON serialization with camelCase aliasing in a single pass.

- [x] 7.3.1 **Dict-to-JSON serializer** — `serialize_dicts_to_json(dicts, alias_map?)` handles str, int, float, bool, None, list, nested dict. Returns bytes.
- [x] 7.3.2 **CamelCase alias builder** — `build_camel_case_map(field_names)` generates snake→camel map at startup
- [x] 7.3.3 **Single dict serializer** — `serialize_dict_to_json(dict, alias_map?)`
- [x] 7.3.4 **Integration** — wired into `views/base.py` (Rust serializer used for camelCase list responses, orjson remains primary for non-camelCase)
- [x] 7.3.5 **Python fallback** — via `_accel.py` import guard
- [x] 7.3.6 **Benchmarks** — 1.7-1.9x vs json.dumps, orjson still faster for plain serialization. Rust value: camelCase rename in one pass.

**Measured gains:** 1.7-1.9x vs json.dumps. orjson faster for plain JSON (deeper CPython integration). Rust serializer wins for combined serialize+rename.

### Phase 7.4: Query String Parser

Parse filter/sort/fields/pagination params in Rust. Called on every list endpoint.

- [x] 7.4.1 **Parser implementation** — `parse_query_string(qs)` returns fields, filters, sort, pagination, extras
- [x] 7.4.2 **ParsedQuery struct** — dict with typed sub-dicts, url percent-decoding included
- [ ] 7.4.3 **Integration** — wire into filtering/ordering/pagination middleware
- [x] 7.4.4 **Python fallback** — via `_accel.py` import guard
- [x] 7.4.5 **Benchmarks** — **2.7-4.6x faster** (scales with query complexity)

**Measured gains:** 2.7x simple, 3.8x filters, 4.0x full, 4.6x complex

### Phase 7.5: Middleware & Header Parsing

Header parsing in Rust. Middleware chain compiler descoped (Django middleware is already lightweight).

- [x] 7.5.3 **Header parsing** — `parse_headers(meta)` extracts Authorization, Accept (q values), Content-Type, X-Request-ID, X-API-Key
- [x] 7.5.5 **Python fallback** — via `_accel.py` import guard
- [ ] 7.5.1 **Chain compiler** — descoped: Django middleware overhead is minimal, not worth Rust FFI boundary cost
- [x] 7.5.4 **Integration** — wired into `auth/jwt.py` and `auth/api_keys/utils.py` for fast header extraction

### Phase 7.6: Production Hardening

- [x] 7.6.1 **Fuzz testing** — 5 `cargo fuzz` targets (router, JWT, query parser, serializer, headers), `make rust-fuzz`
- [x] 7.6.2 **Memory profiling** — `benchmarks/bench_memory.py`, 11 tests, all PASS (0-0.5MB growth over 1M calls), `make rust-mem`
- [x] 7.6.3 **Thread safety audit** — all Rust types are Send + Sync by construction (no interior mutability)
- [x] 7.6.4 **Error propagation** — JWT errors map to ValueError with descriptive messages (expired, signature, format)
- [x] 7.6.5 **Documentation** — `docs/performance/rust-extensions.md` (architecture, benchmarks, dev workflow, fuzz testing)
- [x] 7.6.6 **End-to-end benchmark** — `benchmarks/bench_e2e_lifecycle.py` — **1.9x total speedup** (58K → 113K req/s framework overhead)

### Phase 7 — Measured Results

| Component | Python | Rust | Speedup |
|-----------|--------|------|---------|
| Route matching (20 routes) | ~6.6μs | ~1.7μs | **4.0x** (up to 13.1x) |
| JWT encode | ~2.9μs | ~1.9μs | **1.5x** |
| JWT decode+verify | ~2.9μs | ~2.0μs | **1.5x** + GIL release |
| Query string (full) | ~3.4μs | ~0.8μs | **4.1x** |
| JSON serialize (10 dicts) | ~9.6μs | ~4.9μs | **1.9x** (camelCase: 1.7x) |
| Header parsing | ~1.0μs | ~0.8μs | **1.2x** |
| **Total per-request (E2E)** | **~17μs** | **~9μs** | **~1.9x** |
| **Throughput (overhead only)** | **58K req/s** | **113K req/s** | **+54K req/s** |

The biggest wins are on route matching (especially misses/late matches) and query string parsing.
JWT speedup is modest because Python's `hmac` is already C-accelerated.
For camelCase APIs, the Rust serializer avoids a separate rename pass.
E2E lifecycle benchmark: `benchmarks/bench_e2e_lifecycle.py`

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
