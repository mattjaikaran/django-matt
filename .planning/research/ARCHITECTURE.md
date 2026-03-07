# Architecture Patterns

**Domain:** Django meta-framework (async-first REST API, type-driven, single-dependency)
**Researched:** 2026-03-07
**Confidence:** HIGH (based on existing codebase + verified patterns from FastAPI/django-ninja ecosystem)

---

## Recommended Architecture

django-matt is already built on sound architectural foundations. This document maps the existing
architecture as-is, names the patterns correctly, identifies gaps, and provides build-order guidance
for any remaining or future phases.

---

## Layer Diagram

```
  ┌──────────────────────────────────────────────────────────┐
  │                    Django ASGI/WSGI                       │
  └──────────────────────────────────────────────────────────┘
           │  Django middleware stack (SecurityHeaders, CORS,
           │  RequestID, JWT auth, ContentNegotiation, etc.)
           ▼
  ┌──────────────────────────────────────────────────────────┐
  │               MattAPI / APIRouter                         │
  │  (route registry, OpenAPI schema cache, URL compilation)  │
  └──────────────────────────────────────────────────────────┘
           │  URL dispatch (Django path() compiled at startup)
           ▼
  ┌──────────────────────────────────────────────────────────┐
  │          View Function / Controller Method                 │
  │  (generated async closure — closes over DI params,        │
  │   type hints, error handler at registration time)         │
  └──────────────────────────────────────────────────────────┘
           │  orjson parse → Pydantic validate
           ▼
  ┌────────────────┐   ┌────────────────┐   ┌─────────────────┐
  │  Permission    │   │  DI Resolution  │   │  Hook Chain      │
  │  Classes       │   │  (ContextVar    │   │  (before/after   │
  │  (BoundView)   │   │   scoped)       │   │   hooks in Views) │
  └────────────────┘   └────────────────┘   └─────────────────┘
           │
           ▼
  ┌──────────────────────────────────────────────────────────┐
  │               Service Layer (optional)                    │
  │  BaseService / CRUDService / BaseThirdPartyService        │
  └──────────────────────────────────────────────────────────┘
           │  async ORM methods (aget, acreate, asave, adelete)
           ▼
  ┌──────────────────────────────────────────────────────────┐
  │               Django ORM + Database                       │
  │  (select_related / prefetch_related auto-applied)         │
  └──────────────────────────────────────────────────────────┘
           │
           ▼
  ┌──────────────────────────────────────────────────────────┐
  │    Response Serialization                                 │
  │  model_construct() fast path (lists) or full from_orm()   │
  │  orjson → JsonResponse                                    │
  └──────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `MattAPI` | Entry point. Owns route registry, URL compilation, OpenAPI schema cache, module registry (slim mode) | `APIRouter`, `OpenAPISchema`, `ModuleRegistry` |
| `APIRouter` | Route registration (`@api.get`, `@api.post`), static-before-parameterized URL ordering, controller discovery | `MattAPI`, `APIController`, Django `path()` |
| `APIController` / `CRUDController` | Class-based endpoint grouping. Single-pass `_setup_methods()` wraps DI + error handling at `__init__` time, not per-request | `APIRouter`, `ErrorHandler`, `DI Container` |
| `ViewSet` + `APIView` | Composable CRUD — each view (`ListView`, `CreateView`, etc.) is a descriptor attached to a `ViewSet`. `BoundView.__call__` dispatches, enforces method, checks permissions, runs hooks | `ViewSet`, `HookChain`, `PermissionClasses`, `ModelSchema` |
| `ModelSchema` | Pydantic schema generated from Django model at class definition time via metaclass. `from_orm_fast()` uses `model_construct()` for list serialization | `CRUDController`, `APIView`, `OpenAPISchema` |
| `DI Container` | Singleton/Scoped/Transient lifetime management. `ContextVar` for per-request scope (no thread locals). Circular dependency detection | `APIController`, `APIRouter` view closure |
| `ModuleRegistry` (slim mode) | Tracks which modules are active. Controls which middleware is registered and which URL patterns are served. Freeze-on-first-use | `MattAPI`, `DjangoMattMiddleware` |
| `DjangoMattMiddleware` | Auto-chains internal middleware stack (security, CORS, request ID, logging, timing) in correct order at startup — not per-request | Django middleware stack |
| `ErrorHandler` | Captures exceptions, attaches source snippet in debug mode. Converts `APIError`, `ValidationError`, `DoesNotExist` to JSON responses | `APIController._error_handler` (class-level singleton) |
| `PermissionClasses` | `has_permission(request, view)` protocol. Checked in `BoundView.__call__` before endpoint dispatch | `APIController`, `ViewSet`, `BoundView` |
| `ServiceLayer` | Business logic isolated from HTTP concerns. `CRUDService` wraps async ORM. `BaseThirdPartyService` wraps httpx for external APIs | `APIController`, direct use |
| `OpenAPISchema` | Generates OpenAPI 3.x JSON from registered routes and controllers at schema-request time (cached) | `MattAPI`, `ModelSchema` |

---

## Data Flow

### Request Path (Happy Path)

```
HTTP Request
  → Django ASGI server (uvicorn)
  → Django middleware stack (auth middleware sets request.user)
  → URL router: compiled path() patterns match → dispatch to view_func
  → view_func async closure (created once at startup via _create_view_func):
      1. Method check (frozenset O(1) lookup)
      2. orjson.loads(request.body)  — single parse, no second stdlib parse
      3. Pydantic validate (body_schema cached by id(endpoint))
      4. DI resolution (ContextVar scope, _di_params analyzed at registration)
      5. Endpoint coroutine: await endpoint(request, **kwargs)
  → Service layer (optional): async ORM → database
  → Return value:
      - BaseModel → model_dump()
      - list[BaseModel] → [item.model_dump() for item in result]
      - dict → pass through
  → JsonResponse(result, status=status_code, safe=False)
  → Response through middleware stack (timing, logging add headers)
  → HTTP Response
```

### Controller Path (Class-Based)

```
HTTP Request → URL dispatch → BoundView.__call__:
  1. HTTP method enforcement
  2. Permission check (per-op override → viewset-level)
  3. Hook chain: before_* hooks
  4. view.handle(request, **kwargs)
  5. Hook chain: after_* hooks
  6. Serialize result → JsonResponse
  Exception path → error hooks → APIError/ValidationError → JsonResponse
```

### Schema Generation (Startup/First Request)

```
MattAPI._generate_openapi_schema() [lazy, cached]
  → OpenAPISchema.add_routes(self.routes)
  → OpenAPISchema.add_controller(controller_class)
  → ModelSchema fields introspected at metaclass time
  → schema.build() → dict (JSON-serializable)
  → Cached as self._openapi_schema
```

---

## Patterns to Follow

### Pattern 1: Startup-Time Introspection, Zero Per-Request Overhead

**What:** All Python reflection (get_type_hints, inspect.signature, _meta.fields) happens at route registration or Controller.__init__. Never per-request.

**Why it matters:** DRF ModelSerializer builds fields on every init — 3-6x slower. django-matt caches everything.

**Implementation in codebase:**
```python
# core/router.py — cached at registration
_hints_cache: dict[int, dict] = {}

def get_body_schema(endpoint):
    key = id(endpoint)
    if key not in _hints_cache:
        _hints_cache[key] = get_type_hints(endpoint)
    ...

# core/controller.py — cached at __init__
def __init__(self):
    self._valid_filter_fields = frozenset(f.name for f in self.model._meta.fields)
    self._fk_fields = self._get_foreign_key_fields()  # cached once
    self._m2m_fields = self._get_many_to_many_fields()  # cached once
```

**Rule:** If it uses `get_type_hints`, `inspect.signature`, `_meta.*`, or `get_type_hints` — it must be called at init/registration time only.

### Pattern 2: Async-First, Sync via sync_to_async

**What:** All endpoint handlers and ORM calls are async. Sync fallbacks must use `sync_to_async()`.

**Why:** Django ASGI with uvicorn lets the event loop serve other requests while one waits for I/O. Blocking the event loop with sync ORM negates the benefit.

**Implementation:**
```python
# Good — async ORM (Django 4.1+)
instance = await queryset.aget(id=id)
await instance.asave()
items = [item async for item in queryset]

# Bad — blocks event loop
instance = queryset.get(id=id)  # Blocks. Never do this in async context.
```

### Pattern 3: orjson Everywhere for JSON

**What:** Use `orjson.loads()` for parsing request bodies. Never `json.loads()` or `request.POST`.

**Why:** orjson is 3-10x faster than stdlib json. It is a base dependency — no conditional import.

**Implementation:**
```python
# core/controller.py, core/router.py, views/base.py
import orjson
body_data = orjson.loads(request.body)
```

**Rule:** `import json` anywhere in django_matt/ is a bug.

### Pattern 4: Single-Pass Wrapper via Closure

**What:** `_setup_methods()` wraps each route method exactly once in `__init__`. The wrapper closes over pre-computed `_method`, `_pydantic_params`, `_di_params`, `_error_handler` as default arguments (avoids closure capture bugs).

**Why:** Wrapping once at init avoids repeated introspection on every request. Default-argument binding (`_method=method`) solves Python's loop closure capture problem.

**Implementation:**
```python
# core/controller.py
async def wrapper(request, *args,
                  _method=method,
                  _is_coro=is_coro,
                  _pydantic_params=pydantic_params,
                  _error_handler=error_handler,
                  _di_params=di_params,
                  **kwargs):
    ...
```

### Pattern 5: ContextVar for Per-Request DI Scope

**What:** Scoped DI instances use `ContextVar` (not threading.local). Each request coroutine gets its own scope dictionary.

**Why:** Thread locals don't work with async. ContextVar is propagated correctly through coroutine chains and properly reset after each request.

**Implementation:**
```python
# di/container.py
_scoped_instances: ContextVar[dict[type, Any]] = ContextVar("scoped_instances", default=None)

# In view wrapper
scope_token = _scoped_instances.set({})
try:
    result = await endpoint(...)
finally:
    _scoped_instances.reset(scope_token)
```

### Pattern 6: model_construct() for List Serialization

**What:** Bulk/list responses use `ModelSchema.from_orm_fast()` which calls `model_construct()` — skips Pydantic re-validation.

**Why:** Data comes from the database (already validated at write time). Re-validating 100 rows wastes CPU. `model_construct()` is 3-5x faster.

**Rule:** Single-object responses (create, retrieve) use full `from_orm()`. List responses use `from_orm_fast()`.

### Pattern 7: Static URLs Before Parameterized

**What:** `APIRouter.get_urls()` separates static patterns (`/users/me`) from parameterized (`/users/<id>`) and places static first.

**Why:** Django's URL resolver short-circuits on first match. Without this, `/users/<id>` would swallow `/users/me`.

**Implementation:**
```python
# core/router.py
if self._is_parameterized_path(pattern):
    param_patterns.append(pattern)
else:
    static_patterns.append(pattern)
return static_patterns + param_patterns
```

### Pattern 8: Module Registry (Slim Mode)

**What:** `ModuleRegistry` tracks which modules are active. In `"minimal"` mode, only core + explicitly activated modules load. In `"full"` mode, everything loads. In `"auto"` mode, it reads DJANGO_MATT settings to detect usage.

**Why:** Large projects only pay for features they use. Middleware chain, URL patterns, and heavy optional modules only load when active.

**Implementation:**
```python
# slim.py
api = MattAPI(mode="minimal").activate("auth", "cors", "observability")
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Per-Request get_type_hints()

**What:** Calling `get_type_hints(endpoint)` inside the view handler function, not at registration time.

**Why bad:** `get_type_hints()` is slow (reads `__annotations__`, resolves forward references). At 1000 req/s this is 1000 unnecessary calls/second.

**Instead:** Cache in `_hints_cache` keyed by `id(endpoint)` at registration. See Pattern 1.

### Anti-Pattern 2: Sync ORM in Async Views

**What:** `Model.objects.get()`, `instance.save()`, `queryset.filter()` in `async def` without `sync_to_async()`.

**Why bad:** Django raises `SynchronousOnlyOperation` in ASGI context. Even when `DJANGO_ALLOW_ASYNC_UNSAFE=true` is set (as in conftest.py), it masks bugs and causes thread blocking in production.

**Instead:** Use `aget()`, `acreate()`, `asave()`, `adelete()`, `aexists()`, `acount()`. For truly sync-only code, wrap with `sync_to_async()`.

### Anti-Pattern 3: DRF-Style Dynamic Field Construction

**What:** Building schema/serializer fields on every serializer instantiation (DRF ModelSerializer pattern).

**Why bad:** ModelSerializer is 3-6x slower than regular Serializer. The field construction on every `__init__()` is the bottleneck.

**Instead:** `ModelSchemaMetaclass` generates Pydantic fields at class definition time. All introspection is done once when the `class` statement executes.

### Anti-Pattern 4: Thread Locals for Request State

**What:** Storing per-request data in `threading.local()`.

**Why bad:** Thread locals don't propagate through async coroutines. A request started on thread A can resume on thread B in async mode.

**Instead:** `ContextVar` for all per-request mutable state (DI scopes, request ID propagation, etc.).

### Anti-Pattern 5: Importing Heavyweight Modules at Top Level

**What:** `from django_matt.billing import ...` at module top level, even when billing is not configured.

**Why bad:** Bloats startup time and memory for projects that don't use billing.

**Instead:** Lazy imports inside functions/methods, guarded by module registry check. The slim mode system exists precisely for this.

### Anti-Pattern 6: Direct JsonResponse with stdlib json

**What:** `JsonResponse({"key": datetime.now()})` — Django's JsonResponse uses stdlib json internally.

**Why bad:** stdlib json can't handle datetime, UUID, Decimal natively. It's also slower than orjson.

**Instead:** Use `orjson.dumps()` and return `HttpResponse(content, content_type="application/json")`, or ensure the dict is fully JSON-serializable before passing to JsonResponse.

---

## How FastAPI, DRF, and django-ninja Compare

### DRF Architecture Weaknesses (What django-matt Avoids)

| DRF Problem | django-matt Solution |
|-------------|---------------------|
| ModelSerializer builds fields per-init | ModelSchemaMetaclass builds at class time |
| Per-request content negotiation overhead | ContentNegotiationMiddleware runs once |
| Sync-first, async bolted on | Async-first, sync via sync_to_async |
| No DI system | Full Container with Singleton/Scoped/Transient |
| Mixins inheritance pyramid | Composable view descriptors (ListView, etc.) |
| ViewSet routing magic | Explicit `as_urls()` with clear URL names |

### FastAPI Architecture Strengths (What django-matt Adopts)

| FastAPI Pattern | django-matt Equivalent |
|-----------------|----------------------|
| Type-driven validation with Pydantic | Same — Pydantic v2 + ModelSchema |
| Dependency injection with Depends() | `DependencyMarker` + `Container` |
| OpenAPI schema auto-generation | `OpenAPISchema` from route/controller introspection |
| orjson for response serialization | orjson as base dependency |
| ASGI-native async | Django ASGI + uvicorn |
| Middleware pipeline (Starlette) | DjangoMattMiddleware + auto-chaining |

### django-ninja Architecture Strengths (What django-matt Extends)

| django-ninja Pattern | django-matt Extension |
|---------------------|----------------------|
| Clean `@api.get()` decorator | Same, plus controller class pattern |
| Router splitting | `include_router()` |
| Pydantic schemas | Adds `ModelSchema` with metaclass generation |
| request.user for auth (not DI) | Both — request.user AND DI-injectable auth |

### Key Performance Delta vs FastAPI

FastAPI runs on Starlette (ASGI framework). django-matt runs on Django's ASGI. The gap:
- Starlette route matching is slightly faster (trie-based)
- Django URL resolver uses compiled regex, adequate but not trie
- Both use Pydantic v2 (Rust core) for validation
- orjson closes the JSON serialization gap
- Async ORM (psycopg3 with connection pooling) closes the DB gap
- `model_construct()` closes the serialization gap for lists

**Remaining gap:** Django's middleware chain is heavier than Starlette's. Every Django MIDDLEWARE entry adds overhead. Use slim mode to minimize this.

---

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---------|--------------|--------------|-------------|
| JSON serialization | orjson adequate | orjson adequate | Consider msgspec if benchmarks show it |
| Database connections | Default pool, 5-10 conn | psycopg3 pool (CONN_MAX_AGE=600) | PgBouncer in front of PostgreSQL |
| ORM queries | select_related auto-detect | Explicit select_related on hot paths | Read replicas for reporting queries |
| Caching | Per-view cache | Redis shared cache | Redis cluster |
| Async workers | 1 uvicorn worker per core | 1 uvicorn worker per core | Multiple servers behind load balancer |
| Schema generation | Lazy + cached | Lazy + cached | Pre-warm at startup |
| Rate limiting | In-memory throttle | Redis throttle | Redis cluster throttle |
| WebSockets | Django Channels | Django Channels + Redis layer | Horizontal scale with sticky sessions |

---

## Build Order for Remaining Phases

The existing core (router, controller, schema, DI, middleware, views, auth, services) is complete.
Future phases build on top without touching the core.

### Dependency Graph

```
core (router, controller, schema, errors)    [DONE — do not break]
  └── auth (JWT, RBAC, OAuth, SSO, passkeys) [DONE]
  └── views (ViewSet, composable CRUD)        [DONE]
  └── services (BaseService, CRUDService)     [DONE]
  └── permissions                             [DONE]
  └── DI container                            [DONE]
  └── middleware stack                        [DONE]
  └── openapi                                 [DONE]

Phase boundary: anything above here is "stable core"

Next layer (can be built in any order, no inter-dependencies):
  ├── audit (depends on: services, models)
  ├── multitenancy (depends on: auth, permissions)
  ├── billing (depends on: auth, third-party service base)
  ├── analytics (depends on: middleware for session tracking)
  ├── experiments (depends on: analytics, flags)
  ├── notifications (depends on: email, websockets)
  ├── graphql (depends on: core schema, models)
  └── AI/ML (depends on: services, files)

Infrastructure layer (can be added independently):
  ├── observability (logging, metrics, tracing)
  ├── deployment (Docker, Fly.io, Railway configs)
  └── CLI enhancements (generate_crud, sync_types, ai_context)
```

### Suggested Build Order for Audit/Performance Phase

1. **Core correctness audit first** — before adding features, verify all existing modules have no async/sync bugs, no per-request introspection leaks, no import-time side effects
2. **Benchmark baseline** — establish req/s for core CRUD endpoints vs DRF vs django-ninja
3. **Hot path optimization** — profile and fix the 20% of code responsible for 80% of overhead
4. **Integration tests** — each module in isolation + together (import side effects are common)
5. **Documentation** — architecture decision records for each pattern above

---

## Component Interaction: Request Lifecycle Detail

```
Request enters ASGI server (uvicorn)
  │
  ├─ Django MIDDLEWARE chain (each calls get_response()):
  │   SecurityHeadersMiddleware → RequestIDMiddleware → CORSMiddleware
  │   → JWTAuthenticationMiddleware (sets request.user)
  │   → ContentNegotiationMiddleware → RequestLoggingMiddleware
  │   → TimingMiddleware
  │
  ├─ Django URL resolver:
  │   urlpatterns = api.get_urls()  → compiled once at startup
  │   path("users/", view_func)     → static patterns first
  │   path("users/<str:id>", ...)   → parameterized patterns after
  │
  ├─ view_func (generated async closure):
  │   │  [All below computed at registration, not per-request]
  │   ├─ allowed_methods = frozenset({"GET", "POST"})  → O(1) check
  │   ├─ body_schema = get_body_schema(endpoint)        → cached
  │   ├─ di_params = _analyze_di_params(endpoint)       → cached
  │   │
  │   ├─ 1. Method enforcement
  │   ├─ 2. orjson.loads(request.body)
  │   ├─ 3. body_schema(**body_data) → Pydantic ValidationError → 422
  │   ├─ 4. DI scope: _scoped_instances.set({}) → resolve deps → reset
  │   ├─ 5. await endpoint(request, *args, **kwargs)
  │   └─ 6. Serialize result → JsonResponse
  │
  └─ Response exits through middleware chain (reverse order)
      TimingMiddleware adds X-Response-Time header
      RequestLoggingMiddleware logs status + duration
      SecurityHeadersMiddleware adds security headers
```

---

## Sources

- Existing codebase: `django_matt/core/router.py`, `controller.py`, `schema.py`, `di/container.py`, `views/base.py`, `slim.py`, `middleware/chaining.py` (HIGH confidence — direct inspection)
- [FastAPI request lifecycle (Medium, 2025)](https://medium.com/@rameshkannanyt0078/%EF%B8%8F-understanding-the-lifecycle-of-a-fastapi-application-in-2025-d5595bf16b4e) (MEDIUM confidence)
- [FastAPI middleware documentation](https://fastapi.tiangolo.com/tutorial/middleware/) (HIGH confidence — official docs)
- [DRF serializer performance analysis](https://hakibenita.com/django-rest-framework-slow) (HIGH confidence — empirical benchmarks)
- [DRF ModelSerializer performance GitHub discussion](https://github.com/encode/django-rest-framework/discussions/9499) (MEDIUM confidence)
- [django-ninja motivation and architecture](https://django-ninja.dev/motivation/) (HIGH confidence — official docs)
- [Pydantic model_construct performance](https://github.com/pydantic/pydantic/discussions/6388) (MEDIUM confidence — community discussion)
- [orjson + FastAPI integration](https://oandersonbm.medium.com/orjson-fastapi-a4477de3c3fc) (MEDIUM confidence)
- [Pydantic at service boundaries only](https://leehanchung.github.io/blogs/2025/07/03/pydantic-is-all-you-need-for-performance-spaghetti/) (MEDIUM confidence — engineering blog)
