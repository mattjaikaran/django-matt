# Technology Stack

**Project:** django-matt
**Researched:** 2026-03-07
**Research mode:** Ecosystem — Django meta-framework stack for 2025/2026

---

## Recommended Stack

### Core Runtime

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12+ | Runtime | 3.12 has 60% faster startup, 25% runtime speedup vs 3.10; 3.13 adds no-GIL PEP 703 (experimental). 3.12 is the floor per project constraint. |
| Django | 5.2 LTS / 6.0 | Web framework | 5.2 is the LTS (April 2025, supported until April 2028). 6.0 (Dec 2025) adds AsyncPaginator, GeneratedField auto-refresh, native background tasks, CSP middleware. Target 5.2+ for LTS stability; advertise 6.0 compatibility. |
| ASGI/asgiref | >=3.8 | Async bridge | Django's built-in async bridge. sync_to_async / async_to_sync for crossing the boundary. Shipped with Django — no separate pin needed. |

**Confidence: HIGH** — All versions verified against PyPI and official Django release notes.

---

### JSON Serialization

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| orjson | 3.11.7+ | Default JSON serializer | 10x faster than stdlib json on serialization, 2x faster on deserialization. Native support for dataclasses, datetime, UUID, numpy. Returns bytes (zero-copy). Only non-Django hard dependency — already in pyproject.toml. Latest release: 3.11.7 (2026-02-02). |
| msgpack | 1.0.8+ (optional) | Binary serialization | Compact binary format for cache storage and inter-service messaging. Already in performance optional group. Use alongside orjson, not instead of it. |

**On msgspec:** msgspec's JSON decode benchmarks are 4-10x faster than orjson for schema-bound structs. However, msgspec uses its own `Struct` type, not Pydantic models or Django ORM instances. Adopting msgspec would require a full schema layer rewrite. **Do not adopt msgspec** — orjson + Pydantic v2 achieves the design goal (FastAPI-level speed) without replacing the validation layer. Revisit if benchmark data shows orjson is the bottleneck in a hot path.

**Confidence: HIGH** — orjson version from PyPI (2026-02-02). msgspec benchmark data from official msgspec docs.

---

### Schema Validation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Pydantic | 2.11+ | Request/response validation and serialization | Pydantic v2 is 5-17x faster than v1 (Rust core). v2.11 (2025) adds 2x schema build-time speedup, 48% memory reduction for large model sets, 67% FastAPI startup improvement from generic caching. `model_construct()` for list serialization skips re-validation — already used in the codebase. |

**model_validate_json() vs model_construct():** Use `model_validate_json()` for untrusted input (validates + parses in one Rust call). Use `model_construct()` only for trusted ORM output on list endpoints. This distinction is already in the codebase; keep it.

**Pydantic v2.11+ specific:** Reuses `SchemaValidator`/`SchemaSerializer` across instances. Cache these at class definition time, not per-request. Already documented in MEMORY.md.

**Confidence: HIGH** — Verified against Pydantic release announcement and PyPI.

---

### ASGI Servers (Production)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Granian | 2.6.0+ | Primary production ASGI server | Rust HTTP server (Tokio + Hyper). Benchmarks: 11,270 req/sec avg vs uvicorn's ~9,000. 15MB base memory vs uvicorn's 20MB. HTTP/1, HTTP/2, WebSocket. Zero-copy via PyBackedBytes. More consistent latency (2.8x p99 spread vs uvicorn's 6.8x). |
| uvicorn[standard] | 0.32.0+ | Alternative / development server | Mature, widely supported, excellent Django docs. Use as fallback and in dev where granian may not be installed. Already in pyproject.toml under `server` extras. |
| gunicorn + uvicorn workers | 23.0.0+ | Multi-process production deployment | `gunicorn config.asgi:application --worker-class uvicorn.workers.UvicornWorker` — already documented in MEMORY.md. Granian has native multi-worker support; prefer granian directly in containers. |

**Recommendation:** Add `granian>=2.6.0` to the `server` optional group alongside uvicorn. Document granian as the recommended production server. Do not drop uvicorn — it's the ecosystem default and many CI/CD templates depend on it.

**Confidence: MEDIUM** — Granian benchmarks from GitHub (Dec 2025 run, v2.6.0). Production readiness confirmed by multiple deployment guides but granian is newer than uvicorn.

---

### Database

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 15+ (17 recommended) | Primary database | PG17 pipeline mode slashes round-trips by 70%. JSON operators, full-text search, pgvector all built-in. |
| psycopg | 3.2.0+ (binary + pool) | PostgreSQL driver | Async-native driver. AsyncConnectionPool provides 3.4x QPS improvement over psycopg2 (152k QPS vs 45k). Binary protocol. Django 5.1+ native pool support via `OPTIONS: {"pool": {...}}`. Already in pyproject.toml. |

**Async ORM critical rule:** Every ORM call in an async view must use the async variant: `.aget()`, `.asave()`, `.afilter()`, `.adelete()`. Never `.get()` in an `async def` view. Sync ORM calls in async context require `sync_to_async()` wrapper and create a thread per call.

**psycopg pool config for Django 5.1+:**
```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "OPTIONS": {
            "pool": {
                "min_size": 2,
                "max_size": 10,
                "timeout": 30,
            }
        },
        "CONN_MAX_AGE": 0,  # Required when using pool
    }
}
```

**Confidence: HIGH** — psycopg3 async docs, Django 5.1 pooling docs, benchmark from tigerdata.com.

---

### Development Toolchain

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| uv | 0.10+ | Package manager and virtual environments | 10-100x faster than pip. Workspace support. Lockfile. Replace `pip install` everywhere with `uv add` / `uv sync`. Already the project standard. |
| ruff | 0.9+ | Linting + formatting | Replaces flake8, black, isort, pyupgrade in a single Rust binary. v0.9 (Jan 2025) stabilized additional rules. Already the project standard. |
| pyright | 1.1.390+ | Type checking (primary) | Faster than mypy, native VSCode support, better generics inference for Django. Already in dev deps. |
| mypy | 1.11+ | Type checking (CI gate) | More conservative than pyright; run both in CI for maximum coverage. django-stubs integration. Already in dev deps. |
| pytest | 8.0+ | Test runner | asyncio_mode = "auto" already set. 4143 tests. Already the project standard. |
| pytest-asyncio | 0.24+ | Async test support | Required for async def test functions. Already in dev deps. |
| httpx | 0.27+ | HTTP test client | Async-native, supports ASGI transport for in-process testing without a server. Already in dev deps. |

**Confidence: HIGH** — All versions verified against PyPI.

---

### Optional / Ecosystem Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| celery | 5.4+ | Background tasks | Long-running tasks, scheduled work. Django 6.0 adds a lightweight built-in task system — use that for simple cases, Celery for distributed queues. |
| dramatiq[redis] | 1.17+ | Alternative task queue | Lower overhead than Celery, simpler Redis backend. Good for teams that find Celery complex. |
| redis | 5.0+ | Cache + Pub/Sub | Session storage, rate limiting, pub/sub for WebSocket presence. Use django-redis for cache backend. |
| boto3 | 1.34+ | S3/R2/MinIO file storage | File upload backend. |
| stripe | 10.0+ | Billing | Already in billing optional group. |
| cryptography | 42.0+ | RSA/EC JWT signing | For ES256 (Apple), RS256 keys. Optional; HMAC JWT works without it. |
| authlib | 1.3+ | OAuth flows | Already in oauth optional group. |
| webauthn | 2.1+ | Passkey/WebAuthn | Already in passkeys optional group. |
| mkdocs-material | 9.5+ | Documentation | Already in docs optional group. |
| strawberry-graphql | latest | GraphQL | Optional module; not a core dep. |

---

## What DRF Does Well (and Must Be Matched)

| DRF Strength | django-matt Approach |
|---|---|
| Browsable API (HTML fallback) | OpenAPI + Swagger/ReDoc covers this. Browsable HTML is low priority — JSON-first. |
| ViewSets with router auto-wiring | APIViewSet + APIController achieve this. Already built. |
| Serializer field-level validation | Pydantic model validators. Already built. |
| Pagination classes | PageNumber, LimitOffset, Cursor already in pagination module. |
| Permission system | IsAuthenticated, IsAdmin, IsOwner, HasRole already built. |
| Throttling | Already in throttling module. |
| Filtering + search + ordering | Already in filtering module. |
| Versioning | Already in versioning module. |
| Content negotiation | Already in negotiation module. |

---

## What django-ninja Does Well (and Must Be Matched or Exceeded)

| django-ninja Strength | django-matt Approach |
|---|---|
| Type-first endpoint definitions | `@api.get("/")` with Pydantic schema return types. Already built. |
| Automatic OpenAPI from type hints | Already built in openapi module. |
| Pydantic v2 integration | Already built. Pydantic 2.11 target for startup perf. |
| `NinjaAPI` router | `MattAPI` / `api.controller()` pattern. Already built. |
| Schema from ORM model | Schema auto-generation. Already built. |
| Async-native | All views default to `async def`. Already built. |
| `Form[T]`, `Query[T]`, `Header[T]` params | Already supported via controller parameter inspection. |

**What django-matt should exceed django-ninja on:**
- Class-based controllers (ninja-extra patterns built-in, not a plugin)
- TypeScript/Swift type generation (already built in typegen)
- Multi-tenancy (built-in, not bolt-on)
- AI/LLM context generation (built-in)
- CLI code generation (built-in)
- Websockets (built-in)
- Billing, analytics, experiments, feature flags (all built-in)

---

## What FastAPI Does Well (and Must Be Matched)

| FastAPI Strength | django-matt Approach |
|---|---|
| ASGI-native with Starlette | Django 5.2+ ASGI is full-stack async. Use Granian for equivalent server performance. |
| Dependency injection | DI container already built in `di/` module. |
| Automatic docs from types | OpenAPI module already built. |
| Sub-application routing | Router prefix + controller tags. Already built. |
| Background tasks (FastAPI's simple version) | Django 6.0 native tasks for simple cases, Celery for complex. |
| Response model validation | Pydantic return type annotations on endpoints. Already built. |
| Lifespan events | Use ASGI lifespan protocol or `AppConfig.ready()`. |

**The core FastAPI performance gap:** FastAPI runs on Starlette which is pure ASGI with minimal middleware. Django's default middleware stack (session, CSRF, auth, messages) adds 2-2.5x overhead if all are loaded. **Recommendation:** document a "high-performance middleware stack" in config that strips to bare minimum for API-only deployments. This is the biggest lever for matching FastAPI throughput inside Django.

---

## Alternatives Considered and Rejected

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| JSON serialization | orjson | msgspec | msgspec requires own Struct types; breaks Pydantic integration. Marginal gain not worth the rewrite. |
| JSON serialization | orjson | ujson | orjson is faster and supports more types natively. ujson is not maintained as actively. |
| Schema validation | Pydantic v2 | attrs + cattrs | Pydantic is the ecosystem standard; django-ninja, FastAPI all use it. No reason to diverge. |
| ASGI server | Granian / uvicorn | Daphne | Daphne is maintained by Django but slower than uvicorn. No HTTP/2. Only viable for WebSocket-heavy Django Channels apps. |
| ASGI server | Granian / uvicorn | Hypercorn | Hypercorn is slower (35k req/s vs granian 50k in hello-world). Hypercorn supports HTTP/3 but that's not a current requirement. |
| Package manager | uv | pip, poetry | pip is 100x slower; poetry is 10x slower and doesn't support PEP 621 fully. uv is the 2025/2026 standard. |
| Linter | ruff | flake8 + black + isort | ruff replaces all three in a single 100x faster binary. No reason to use legacy tools. |
| Type checker | pyright + mypy | pytype (Google) | pytype has no Windows support and slower iteration. pyright is faster for editor integration; mypy for CI strictness. |
| Background tasks (simple) | Django 6.0 native tasks | Huey | Huey is lightweight but adds a dependency. Django 6.0 native tasks cover the simple case with zero external deps. |
| Database driver | psycopg3 | asyncpg | asyncpg is slightly faster in raw benchmarks but doesn't integrate with Django's ORM. psycopg3 is the official Django-supported async driver. |

---

## Performance Target: Matching FastAPI

Based on benchmarks:

- **Raw Django + DRF:** ~3,000-5,000 req/s (synchronous, full middleware stack)
- **Raw Django + django-ninja:** ~8,000-12,000 req/s (async, Pydantic v2)
- **FastAPI + uvicorn:** ~15,000-20,000 req/s (TechEmpower Round 23, JSON endpoint)
- **FastAPI + Starlette:** ~20,000-25,000 req/s (minimal middleware)

**django-matt target on equivalent hardware:**
- Stripped middleware (no session/CSRF/messages for API-only): 10,000-15,000 req/s
- With Granian (vs uvicorn): additional ~20-25% throughput
- orjson serialization (vs stdlib json): 5-10x improvement on serialization-bound endpoints
- Pydantic v2.11 model_construct() on list responses: removes validation overhead for ORM output

**The gap:** Django will remain ~30-50% behind FastAPI's fastest benchmarks because Starlette is a thinner ASGI app than Django. The gap shrinks significantly with stripped middleware + async ORM + Granian + orjson. django-matt should target being the fastest Django-based API framework, not the fastest Python framework overall.

---

## Installation (Recommended Dev Setup)

```bash
# Core install
uv sync

# With all optional deps for full development
uv sync --all-extras

# Production server
uv add granian --optional server

# Run with Granian (production)
granian --interface asgi config.asgi:application --workers 4

# Run with uvicorn (development/fallback)
uvicorn config.asgi:application --reload
```

---

## Sources

- orjson 3.11.7 — https://pypi.org/project/orjson/ (fetched 2026-03-07, HIGH confidence)
- msgspec benchmarks — https://jcristharif.com/msgspec/benchmarks.html (HIGH confidence)
- Pydantic v2.11 release — https://pydantic.dev/articles/pydantic-v2-11-release (HIGH confidence)
- Django 6.0 release notes — https://docs.djangoproject.com/en/6.0/releases/6.0/ (HIGH confidence)
- Granian benchmarks — https://github.com/emmett-framework/granian/blob/master/benchmarks/vs.md (MEDIUM confidence — synthetic benchmark)
- psycopg3 async performance — https://www.tigerdata.com/blog/psycopg2-vs-psycopg3-performance-benchmark (MEDIUM confidence)
- Django native pooling — https://saurabh-kumar.com/articles/2025/06/cut-django-database-latency-by-50-70ms-with-native-connection-pooling/ (MEDIUM confidence)
- FastAPI vs django-ninja benchmarks — https://github.com/tanrax/python-api-frameworks-benchmark (MEDIUM confidence — community benchmark)
- TechEmpower Round 23 (2025-02-24) — https://www.techempower.com/benchmarks/ (HIGH confidence)
- Django async middleware overhead — https://forum.djangoproject.com/t/huge-performance-difference-when-using-asgi-and-wsgi/30344 (MEDIUM confidence)
- uv 0.10.9 — https://pypi.org/project/uv/ (HIGH confidence)
- ruff 0.9.0 — https://astral.sh/blog/ruff-v0.9.0 (HIGH confidence)
- django-ninja v1.5.x — https://django-ninja.dev/whatsnew_v1/ (HIGH confidence)
