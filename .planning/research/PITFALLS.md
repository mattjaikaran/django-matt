# Domain Pitfalls: Django Meta-Framework

**Domain:** Django API/meta-framework (rivaling DRF, django-ninja, FastAPI)
**Researched:** 2026-03-07
**Confidence:** HIGH — multiple verified sources per pitfall

---

## Critical Pitfalls

Mistakes that cause rewrites, security incidents, or framework abandonment.

---

### Pitfall 1: Async/Sync ORM Boundary Violations

**What goes wrong:** Calling synchronous Django ORM methods (`.get()`, `.save()`, `.filter()`) directly inside `async def` views or coroutines causes `SynchronousOnlyOperation` exceptions in ASGI mode, or worse, silently blocks the event loop in environments where `DJANGO_ALLOW_ASYNC_UNSAFE=true` is set.

**Why it happens:** Django's ORM is still fundamentally synchronous. Every async-compatible method has an `a`-prefixed variant (`aget()`, `asave()`, `afilter()`), but the sync variants look identical in code review. The framework itself currently sets `DJANGO_ALLOW_ASYNC_UNSAFE=true` in `conftest.py`, which masks this entire class of bugs in tests.

**Consequences:**
- Async views that call sync ORM silently block the uvicorn event loop, destroying the concurrency benefit of ASGI
- Under load, one slow sync ORM call can starve all concurrent requests
- `DJANGO_ALLOW_ASYNC_UNSAFE=true` in tests means the CI suite never catches sync ORM calls inside async views

**Prevention:**
- Establish a lint rule or CI check that flags `DJANGO_ALLOW_ASYNC_UNSAFE=true` in non-development contexts
- Document in framework code that all ORM interactions inside `async def` handlers must use `a`-prefixed methods or `sync_to_async()`
- The framework's own internal code must be the reference implementation — if `views/base.py` or controllers use sync ORM calls, users will copy the pattern

**Detection:** Warning signs are: response latency that correlates with DB query count (not network concurrency), `BlockingIOError` or event loop blocked warnings in uvicorn logs.

**Phase:** Audit phase — verify zero sync ORM calls in all async handler paths in django_matt internal code.

**Sources:** [Django async docs](https://docs.djangoproject.com/en/5.2/topics/async/), [Loopwerk async Django](https://www.loopwerk.io/articles/2025/async-django-why/), known issue in `tests/conftest.py` (DJANGO_ALLOW_ASYNC_UNSAFE=true)

---

### Pitfall 2: CONN_MAX_AGE / Persistent Connections Break Under ASGI

**What goes wrong:** Setting `CONN_MAX_AGE` to any non-zero value in ASGI deployments causes connection leaks and `OperationalError: couldn't get a connection` errors under load. Django's persistent connection mechanism uses thread IDs for connection reuse — these are meaningless in async contexts where every coroutine runs on the same thread.

**Why it happens:** Django's connection persistence model was designed for WSGI (one thread = one request). In ASGI, every request creates a new connection that never reuses the pool, and old connections are not properly closed because the `request_finished` signal does not fire reliably.

**Consequences:**
- Connection pool exhaustion under moderate load
- Database `max_connections` exceeded
- `OperationalError` crashes in production

**Prevention:**
- Set `CONN_MAX_AGE = 0` in ASGI deployments, or use psycopg3's native connection pool (`CONN_MAX_AGE = None` in Django 4.2+ triggers the new pool pathway)
- django-matt's default config templates for ASGI deployments must not include non-zero `CONN_MAX_AGE`
- Document this in CLI scaffolding (`startapi` command) and in deployment guides

**Detection:** Connection count growing monotonically in Postgres `pg_stat_activity` during load tests.

**Phase:** Deployment/infrastructure phases. CLI scaffolding templates must be correct from day one.

**Sources:** [Django ticket #33497](https://code.djangoproject.com/ticket/33497), [Django async docs](https://docs.djangoproject.com/en/5.2/topics/async/)

---

### Pitfall 3: model_construct() Bypasses Validation on Untrusted Data

**What goes wrong:** Using `model_construct()` (Pydantic v2) or its equivalent for performance optimization on request-derived data skips all validators, coercions, and field constraints. A malicious or malformed payload passes through to the database layer unvalidated.

**Why it happens:** The pattern `from_orm_fast()` using `model_construct()` is appropriate for read paths (ORM -> response), where data comes from the trusted database. The bug occurs when the same pattern is accidentally applied to write paths (request body -> model), where data comes from untrusted network input.

**Consequences:**
- Type mismatches cause unexpected crashes deep in business logic
- Constraint violations reach the database directly
- Security: custom validators meant to enforce business rules (e.g., "email must be from company domain") are silently skipped

**Prevention:**
- Reserve `model_construct()` exclusively for ORM-to-schema serialization (read path)
- All request body deserialization must go through `model_validate()` (full validation)
- Add inline docstrings in `from_orm_fast()` stating: "NEVER use for request body data. Read path only."
- Write tests that confirm validation errors are raised for invalid request bodies — not just that valid data passes

**Detection:** Unit tests where invalid input (wrong types, missing required fields, constraint violations) passes through without `ValidationError`.

**Phase:** Core framework phase. This is a correctness invariant that must be established before other features build on top of it.

**Sources:** [Pydantic model_construct docs](https://docs.pydantic.dev/latest/concepts/models/), [GitHub issue #8084](https://github.com/pydantic/pydantic/issues/8084)

---

### Pitfall 4: PATCH Semantics — Distinguishing "Not Sent" from "Explicitly Null"

**What goes wrong:** PATCH endpoints that use a single optional schema cannot distinguish between a field being absent from the request (do not update it) versus a field being explicitly set to `null` (clear it). This is a known, unfixed issue in django-ninja that causes data corruption.

**Why it happens:** Pydantic's `Optional[T]` defaults to `None` for missing fields, making it impossible to tell if the client sent `{"field": null}` or simply omitted `"field"` entirely. Django-ninja's `PatchDict` helper has this bug — fields not in the payload get set to `None`, which then persists to the database.

**Consequences:**
- Silent data loss: existing field values get overwritten with `None` on partial updates
- Hard to detect — the HTTP 200 response looks normal
- Particularly dangerous for nullable foreign keys and optional fields

**Prevention:**
- Implement a `NotSet` sentinel type (or use Python's `dataclasses.MISSING` pattern) for PATCH schemas
- The framework should provide a first-class `PatchSchema` or `PartialSchema` that uses a sentinel, not `None`, to mark unset fields
- In update logic, only write fields that are not the sentinel value
- Document this pattern prominently in PATCH/partial update examples

**Detection:** A test that sends `PATCH /resource/1` with an empty body `{}` and confirms no existing fields are modified.

**Phase:** Core framework (CRUD views). This must be correct before shipping update views.

**Sources:** [django-ninja issue #1045](https://github.com/vitalik/django-ninja/issues/1045), [jujens.eu django-ninja review](https://www.jujens.eu/posts/en/2025/Jul/06/django-ninja/)

---

### Pitfall 5: Framework Abandonment — Third-Party Maintainer Risk

**What goes wrong:** API frameworks built as third-party libraries (Tastypie, django-piston, early DRF) stall when the primary maintainer's priorities shift. The project accumulates issues, falls behind Django releases, and users are forced to migrate.

**Why it happens:** Maintaining an API framework requires sustained effort across Django's annual major releases. A single maintainer cannot sustain this indefinitely. When encode (DRF's organization) pivoted to Starlette/httpx, DRF's async support stalled for years.

**Consequences:**
- Users migrate away, fragmeting the ecosystem
- Security patches delayed
- Incompatibility with new Django versions

**Prevention for django-matt:**
- Keep Django as the only hard dependency — never create dependency on a third-party package that itself needs maintenance
- Build against Django 5.2 LTS and 6.x simultaneously in CI — catch breakage before users do
- Document the "dependency philosophy" in the framework README as a first-class feature
- Version the public API explicitly — use deprecation warnings before removing anything

**Detection:** Django release notes that contain breaking changes the framework hasn't addressed.

**Phase:** Ongoing. CI must test against at minimum the current LTS and latest Django. Pin no upper bound on Django version.

**Sources:** [HN: Django's REST Problem](https://news.ycombinator.com/item?id=43510495), [Loopwerk DRF vs Ninja](https://www.loopwerk.io/articles/2024/drf-vs-ninja/)

---

## Moderate Pitfalls

---

### Pitfall 6: N+1 Queries in Serialization (The DRF Trap)

**What goes wrong:** Serializing a list of objects with nested relations issues one query per object for each related field. DRF's `ModelSerializer` was benchmarked as 377x slower than raw Python dictionaries, largely due to this pattern.

**Why it happens:** The serializer layer doesn't know what fields the caller will access, so it defers relation loading. Each access to a related field triggers a new DB query. Nested serializers in list endpoints are the most common trigger.

**Consequences:**
- A `/users/?limit=100` endpoint that serializes user + profile + org issues 300+ DB queries
- Performance appears acceptable in tests (small fixture data) but collapses in production

**Prevention:**
- The framework's list view must auto-detect ForeignKey and ManyToMany fields declared in the response schema and inject `select_related`/`prefetch_related` automatically (the `optimize_queryset()` pattern already in `views/base.py`)
- Provide a query count assertion helper in the testing module: `assert_query_count(n)` for endpoint tests
- Benchmark serialization in CI — a regression alert if list endpoint query count increases

**Detection:** Django Debug Toolbar showing query counts >10 for a single list endpoint request with a fixture of 20+ objects.

**Phase:** Performance/benchmark phase. Validate with real query count assertions.

**Sources:** [Haki Benita: DRF Slow](https://hakibenita.com/django-rest-framework-slow), [DRF GitHub discussion #9499](https://github.com/encode/django-rest-framework/discussions/9499)

---

### Pitfall 7: Per-Request Introspection — The Hidden Performance Killer

**What goes wrong:** Calling `get_type_hints()`, `inspect.signature()`, or accessing `Model._meta.fields` inside request handlers. These are expensive operations. DRF's `ModelSerializer` builds fields during `__init__` rather than at class definition time, contributing to its 3-6x overhead vs plain `Serializer`.

**Why it happens:** It's convenient to inspect types at use time. The performance cost is invisible until load tests reveal it.

**Consequences:**
- Overhead compounds under load — 100 RPS means 100 introspections per second on every endpoint
- GIL contention in CPython makes this worse under concurrent load

**Prevention:**
- Cache ALL introspection at class definition time or module import:
  - `get_type_hints()` → cache keyed by function `id()` or class reference
  - `_meta.fields` → store as `frozenset` on the class at `__init_subclass__` time
  - DI parameter analysis → computed once at route registration
- Never call `inspect.*` or `get_type_hints()` inside a function that runs per-request
- The caching patterns in `router.py` (`_hints_cache`) and `controller.py` (`_error_config`) are the right model — enforce this pattern everywhere

**Detection:** Profiling with `cProfile` on a tight benchmark loop — `get_type_hints` or `inspect` calls appearing in the hot path.

**Phase:** Performance audit. Run profiler against core router/controller code before declaring performance parity with FastAPI.

**Sources:** [Haki Benita: DRF Slow](https://hakibenita.com/django-rest-framework-slow), memory file (performance patterns)

---

### Pitfall 8: Middleware Async/Sync Mode Switching Under ASGI

**What goes wrong:** Inserting any synchronous middleware between the ASGI server and an async view causes Django to switch into a thread pool for that middleware, then back to async for the view. This adds one thread-per-request overhead, entirely negating the concurrency benefit of async views.

**Why it happens:** Django supports both sync and async middleware transparently — it silently wraps sync middleware in `sync_to_async`. The performance impact is invisible in development with one user.

**Consequences:**
- Mode switching adds 0.5-2ms latency per request
- Under high concurrency, thread pool exhaustion causes timeouts
- Nullifies FastAPI-level performance claims

**Prevention:**
- All middleware provided by django-matt must be `async def` natively, not sync
- The framework documentation must warn about third-party sync middleware in ASGI contexts
- Provide an async middleware base class and lint/check for sync middleware in the middleware stack when ASGI is detected

**Detection:** Uvicorn logs showing thread pool usage with async views. Benchmark latency spike proportional to middleware count.

**Phase:** Middleware/observability phases. Any new middleware added to the framework must be verified async.

**Sources:** [Django async docs](https://docs.djangoproject.com/en/5.2/topics/async/)

---

### Pitfall 9: orjson Datetime Timezone Gotchas

**What goes wrong:** orjson serializes `datetime` to RFC 3339 format (`1970-01-01T00:00:00+00:00`). Django's `DjangoJSONEncoder` historically produced slightly different output. Naive datetimes (no `tzinfo`) without `OPT_NAIVE_UTC` raise `TypeError`. `datetime.time` objects must not have timezone info — violating this causes a runtime `TypeError`.

**Why it happens:** orjson's datetime handling is stricter and faster than stdlib `json`. The incompatibilities are subtle and only surface at runtime with real data.

**Consequences:**
- API clients that expected Django's default datetime format break silently (format is similar but subtly different)
- Code that stores naive datetimes in the database and serializes them causes `TypeError` in production

**Prevention:**
- Globally audit all `datetime` objects produced by the ORM — ensure `USE_TZ=True` and all datetimes are timezone-aware
- Add `OPT_NAIVE_UTC` to the orjson options only as a conscious decision with documentation
- Test serialization of datetime, date, and time fields explicitly in the schema test suite
- Document the datetime format difference from Django's default JSON encoder in the migration guide

**Detection:** A test that serializes a Django model with a `DateTimeField` and asserts the exact output format.

**Phase:** Core schema/serialization. Test this before releasing schema generation.

**Sources:** [orjson GitHub repo](https://github.com/ijl/orjson), [orjson issue #418](https://github.com/ijl/orjson/issues/418)

---

### Pitfall 10: Pydantic v2 Nested ORM Model Validation

**What goes wrong:** In Pydantic v2, validation of nested ORM relationships is handled by Rust-based pydantic-core rather than Python. Custom hooks in nested models (validators, `__get_pydantic_core_schema__`) may not fire if the outermost model is validated via Rust. The old `orm_mode = True` config is removed; `from_attributes = True` replaces it.

**Why it happens:** Pydantic v2 rewrote validation in Rust for performance. The boundary between Python and Rust validation is at the outermost `model_validate()` call. Nested model hooks need explicit schema registration to be included in the Rust path.

**Consequences:**
- Custom validators on nested schemas silently don't run
- Data that should fail validation passes through

**Prevention:**
- Ensure all `ModelSchema` subclasses use `model_config = ConfigDict(from_attributes=True)` not the old `orm_mode`
- Test each schema's validators explicitly, including nested schemas, not just the top-level model
- When adding cross-model validators, verify they trigger during actual ORM validation paths

**Detection:** A test that validates a nested object with an invalid nested field and asserts `ValidationError` is raised.

**Phase:** Core schema phase. Establish schema validation test suite before building features on top.

**Sources:** [Pydantic migration guide](https://docs.pydantic.dev/latest/migration/), [GitHub discussion #7669](https://github.com/pydantic/pydantic/discussions/7669)

---

### Pitfall 11: Global Mutable State Polluting Tests

**What goes wrong:** Module-level caches (`_di_config`, `_error_config`, `_hints_cache`) are populated during one test and persist into later tests. When Django settings change between tests (common in multi-settings test suites), the cache serves stale values.

**Why it happens:** Module-level caches initialized to `None` and populated on first call are the correct production pattern. But without explicit reset hooks, they cause test pollution.

**Consequences:**
- Tests pass or fail depending on execution order
- CI is green but local runs differ (execution order differs)
- Hard to debug — the root cause is invisible in the failing test

**Prevention:**
- Every module-level cache in the framework must have a corresponding `_reset_*` function (the pattern in `controller.py` is correct — `_reset_di_config()` exists)
- Expose a `reset_all_caches()` function in a testing utilities module
- In the test suite, call cache resets in `autouse` fixtures for tests that modify settings

**Detection:** Running the test suite in both normal and randomized order (`pytest --randomly-seed=last`) and comparing results.

**Phase:** Testing infrastructure. Already partially addressed — enforce as a pattern for all future caches.

**Sources:** [pytest-antilru](https://pypi.org/project/pytest-antilru/), known issue in `django_matt/core/controller.py` (dual `_di_config` definitions)

---

### Pitfall 12: JWT Token Revocation is Stateful — Implement Correctly

**What goes wrong:** Stateless JWTs cannot be revoked without a blacklist. Common mistakes:
1. Not implementing a token blacklist, so logged-out tokens remain valid until expiry
2. Implementing a blacklist but not purging it — the table grows unboundedly
3. Using the same secret for Centrifugo connection tokens and Django API tokens

**Why it happens:** JWTs are marketed as stateless, leading developers to skip revocation. The nuance — short-lived access tokens + longer-lived refresh tokens + blacklist for logout — is non-obvious.

**Consequences:**
- Security: Stolen tokens remain valid after logout/password-change events
- DoS risk: Unbounded token blacklist table causes query performance degradation
- Token confusion: Using Django's JWT secret for Centrifugo signs attacker-controllable tokens with the wrong secret

**Prevention:**
- The `auth/blacklist/` module exists — ensure it: (a) is used on logout, (b) has a management command for periodic purge, (c) is tested for the stolen-token-after-logout scenario
- Access token TTL should be short (15 minutes), refresh token longer (7 days)
- Centrifugo tokens must use Centrifugo's HMAC secret, not Django's JWT secret (documented in `lessons.md`)

**Detection:** A security test: log in, get token, log out, attempt to use the token — assert 401.

**Phase:** Auth phase. Security test coverage is highest priority (from `lessons.md`).

**Sources:** [Modern JWT auth mistakes](https://dev.to/alvinseyidov/modern-web-authentication-security-jwt-cookies-csrf-and-common-developer-mistakes-fpj)

---

## Minor Pitfalls

---

### Pitfall 13: Metaclass Conflicts in Framework Base Classes

**What goes wrong:** Defining custom metaclasses for controller or schema base classes (e.g., to handle route registration at class creation time) causes `TypeError: metaclass conflict` when users inherit from both the framework base and another class that has its own metaclass (e.g., Django's `Model`, ABC classes).

**Why it happens:** Python only allows one metaclass per class. If two parent classes have different metaclasses, Python cannot automatically merge them.

**Prevention:**
- Prefer `__init_subclass__` hooks over custom metaclasses for registration patterns (PEP 487)
- `ModelSchemaMetaclass` in `core/schema.py` inherits from `type(BaseModel)` — test that user subclasses of `ModelSchema` that also inherit from other Pydantic-based classes don't conflict
- Document: do not add custom metaclasses to classes that inherit from framework base classes

**Detection:** `TypeError: metaclass conflict` when a user class inherits from two framework base classes simultaneously.

**Phase:** Core framework. Validate before adding more base classes.

**Sources:** [Python metaclass docs](https://jfine-python-classes.readthedocs.io/en/latest/decorators-versus-metaclass.html)

---

### Pitfall 14: Error Classes Duplicated Across Modules

**What goes wrong:** `utils/errors.py` duplicates error classes from `core/errors.py` (noted in CLAUDE.md). Users who import from the wrong module get subtly different error classes — `isinstance()` checks fail, error handlers miss exceptions.

**Why it happens:** Organically grown codebases accumulate duplicate utilities when contributors add to the nearest file rather than the canonical one.

**Consequences:**
- `except APIError` in a handler doesn't catch an `APIError` imported from the other module
- OpenAPI error response generation misses error types

**Prevention:**
- Consolidate into `core/errors.py` and have `utils/errors.py` re-export for backwards compatibility with deprecation warnings
- Add a lint rule or test that imports the same symbol from both modules and asserts `is` identity

**Detection:** `from django_matt.core.errors import APIError; from django_matt.utils.errors import APIError as APIError2; assert APIError is APIError2` — this test should pass.

**Phase:** Codebase audit phase. This is a correctness and DX issue.

**Sources:** Known issue in `CLAUDE.md` (Known Issues section)

---

### Pitfall 15: CSRF Conflicts with Custom Authentication in Mixed Auth Stacks

**What goes wrong:** Django's CSRF middleware fires for all non-safe HTTP methods (POST, PUT, PATCH, DELETE) regardless of authentication scheme. When a request uses token-based auth (JWT/API keys) without a session cookie, CSRF validation fails — even though CSRF is irrelevant for non-cookie-based auth.

**Why it happens:** Django-ninja users have reported this exact issue (CSRF errors on unauthenticated curl requests). The fix requires ordering auth providers correctly or exempting token-authenticated endpoints from CSRF.

**Prevention:**
- Ensure the framework's auth middleware uses `@csrf_exempt` on API endpoints when non-cookie auth is the primary method
- Document: Centrifugo proxy views must be `@csrf_exempt` (already in `lessons.md`)
- Test: confirm that JWT-authenticated POST requests from curl (no CSRF cookie) succeed

**Detection:** `403 Forbidden - CSRF verification failed` on valid API requests from non-browser clients.

**Phase:** Auth phase. Validate JWT endpoints work without CSRF cookies.

**Sources:** [jujens.eu django-ninja review](https://www.jujens.eu/posts/en/2025/Jul/06/django-ninja/), known issue in `lessons.md` (Centrifugo)

---

### Pitfall 16: Shared Mutable Class Attributes Across Subclasses

**What goes wrong:** Defining `tags: list[str] = []` as a class attribute on a base controller creates a single list shared across ALL subclasses. Appending to `tags` on one controller mutates every controller's tags.

**Why it happens:** Python class attribute mutation is a classic gotcha. The list is created once at class definition time and shared by reference.

**Prevention:**
- Use `__init_subclass__` to create a fresh list for each subclass (the note in `controller.py` line 78-79 documents this pattern correctly)
- Write a test: create two subclasses of `Controller`, append to one's `tags`, assert the other's `tags` is unchanged

**Detection:** Tags from one controller appearing in another controller's OpenAPI spec.

**Phase:** Core framework. Already known and addressed in the codebase — enforce via tests.

**Sources:** Known pattern in `django_matt/core/controller.py` comments

---

### Pitfall 17: OpenAPI Schema Drift (Documentation != Code)

**What goes wrong:** Auto-generated OpenAPI schemas that don't reflect actual API behavior — particularly around error responses, partial update schemas, authentication requirements, and pagination shapes.

**Why it happens:** Schema generation infers from type hints. When error shapes are defined in catch blocks rather than return type annotations, they don't appear in the schema. Non-obvious Pydantic validation (e.g., `PatchDict`) generates misleading schemas.

**Consequences:**
- Frontend developers code against wrong types
- Generated TypeScript client types are incorrect
- API clients fail silently with wrong field names

**Prevention:**
- Error response schemas must be declared in return type annotations (e.g., `-> UserSchema | ErrorSchema`) not just in error handlers
- Run schema generation in CI and diff against a committed reference — fail on unexpected changes
- Test the generated schema directly: assert specific paths, methods, and response shapes

**Detection:** Generate the OpenAPI spec and manually compare against what the endpoint actually returns for a known error case.

**Phase:** OpenAPI/typegen phases. Critical for the TypeScript code generation feature.

**Sources:** [drf-spectacular](https://github.com/tfranzel/drf-spectacular)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Core router/views | Per-request introspection (#7) | Audit hot path for `inspect.*` / `get_type_hints` calls |
| CRUD views (update) | PATCH null vs absent (#4) | Implement `NotSet` sentinel before shipping update views |
| Serialization | `model_construct()` on request data (#3) | Docstring + test guarding write paths |
| ASGI deployment | `CONN_MAX_AGE` leaks (#2) | Scaffold templates must have `CONN_MAX_AGE=0` |
| Async views | Sync ORM calls (#1) | Remove `DJANGO_ALLOW_ASYNC_UNSAFE=true`, run async audit |
| Auth/JWT | Token revocation (#12) | Security test: use token after logout → expect 401 |
| Middleware | Sync middleware in ASGI (#8) | Verify all framework middleware is `async def` |
| Schema generation | Pydantic v2 nested validation (#10) | Test nested schema validators explicitly |
| Testing | Module-level cache pollution (#11) | Add cache reset fixtures to test suite |
| OpenAPI/codegen | Schema drift (#17) | Commit reference schema; diff in CI |
| Error handling | Duplicate error classes (#14) | Consolidate `utils/errors.py` → `core/errors.py` |
| CSRF + auth | CSRF conflicts (#15) | Test JWT endpoints without CSRF cookie |
| orjson | Datetime timezone (#9) | Test datetime serialization with naive and aware datetimes |

---

## Sources

- [Django async documentation](https://docs.djangoproject.com/en/5.2/topics/async/) — HIGH confidence
- [Django ticket #33497: CONN_MAX_AGE broken under ASGI](https://code.djangoproject.com/ticket/33497) — HIGH confidence
- [Haki Benita: DRF Serializer Performance](https://hakibenita.com/django-rest-framework-slow) — HIGH confidence, benchmarked
- [Loopwerk: Async Django — a solution in search of a problem?](https://www.loopwerk.io/articles/2025/async-django-why/) — MEDIUM confidence, opinion piece but data-backed
- [jujens.eu: Django-Ninja review (2025)](https://www.jujens.eu/posts/en/2025/Jul/06/django-ninja/) — MEDIUM confidence, real-world usage report
- [django-ninja issue #1045: PATCH with Optional fields](https://github.com/vitalik/django-ninja/issues/1045) — HIGH confidence, documented bug
- [Pydantic v2 migration guide](https://docs.pydantic.dev/latest/migration/) — HIGH confidence, official docs
- [Pydantic discussion #7669: ORM mode broken in v2](https://github.com/pydantic/pydantic/discussions/7669) — HIGH confidence
- [orjson GitHub: datetime handling](https://github.com/ijl/orjson) — HIGH confidence, official source
- [HN: Django's REST Framework Problem](https://news.ycombinator.com/item?id=43510495) — MEDIUM confidence, community discussion
- [DRF GitHub discussion #9499: ModelSerializer performance](https://github.com/encode/django-rest-framework/discussions/9499) — HIGH confidence
- [Modern JWT auth mistakes](https://dev.to/alvinseyidov/modern-web-authentication-security-jwt-cookies-csrf-and-common-developer-mistakes-fpj) — MEDIUM confidence, dev.to post
- Project `CLAUDE.md` Known Issues section — HIGH confidence, first-party
- Project `tasks/lessons.md` — HIGH confidence, first-party
