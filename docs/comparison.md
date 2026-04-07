# Framework Comparison

A practical comparison of django-matt against Django REST Framework, Django Ninja, and FastAPI. This is not marketing -- we note honest trade-offs.

## Feature Matrix

| Feature | django-matt | DRF | Django Ninja | FastAPI |
|---------|:-----------:|:---:|:------------:|:-------:|
| **Core** | | | | |
| Pydantic v2 schemas | Yes | No (serializers) | Yes | Yes |
| Async-first | Yes | Partial | No | Yes |
| Type hints everywhere | Yes | Partial | Partial | Yes |
| OpenAPI generation | Built-in | Via drf-spectacular | Built-in | Built-in |
| Class-based controllers | Yes | Yes (ViewSets) | Via ninja-extra | No |
| Declarative CRUD ViewSets | Yes | Yes | Via ninja-crud | No |
| Dependency injection | Built-in | No | Via ninja-extra | Built-in |
| orjson serialization | Built-in (base dep) | No | Optional | Optional |
| Rust-accelerated router | Yes (optional) | No | No | No |
| **Authentication** | | | | |
| JWT | Built-in | Via simplejwt | Via ninja-jwt | Roll your own |
| OAuth (Google, GitHub, etc.) | Built-in | Via dj-rest-auth | Roll your own | Roll your own |
| SSO (SAML, OIDC) | Built-in | Roll your own | Roll your own | Roll your own |
| Passkeys / WebAuthn | Built-in | No | No | No |
| Magic links | Built-in | No | No | No |
| API keys (with rate limits) | Built-in | No | No | No |
| RBAC with hierarchy | Built-in | No | No | No |
| Token blacklisting | Built-in | Via simplejwt | No | No |
| **Data** | | | | |
| ORM | Django | Django | Django | SQLAlchemy |
| Auto migrations | Yes | Yes | Yes | Alembic (manual) |
| Admin panel | Django + Unfold | Django | Django | None |
| Soft delete | Built-in | No | No | No |
| Audit logging | Built-in | No | No | No |
| Multi-tenancy | Built-in | No | No | No |
| **Real-time** | | | | |
| WebSockets | Built-in consumers | Via channels | Via channels | Built-in |
| SSE streaming | Built-in | No | No | Built-in |
| Presence tracking | Built-in | No | No | No |
| **Developer Experience** | | | | |
| TypeScript codegen | Built-in | Via drf-spectacular | No | Via openapi-ts |
| Swift codegen | Built-in | No | No | No |
| CLI scaffolding | Built-in | No | No | No |
| Lifecycle hooks | Built-in | Signals | No | No |
| Content negotiation | Built-in | Built-in | No | No |
| **Infrastructure** | | | | |
| Background tasks | Built-in abstraction | Via celery | Via celery | BackgroundTasks |
| Feature flags | Built-in | No | No | No |
| A/B testing | Built-in | No | No | No |
| Billing (Stripe, etc.) | Built-in | No | No | No |
| Observability (tracing, metrics) | Built-in | No | No | No |
| Rate limiting / throttling | Built-in | Built-in | No | Via slowapi |
| Deployment helpers | Built-in | No | No | No |
| **Testing** | | | | |
| Async test client | Built-in | No | No | httpx |
| Model factories | Built-in | Via factory-boy | Via factory-boy | No |
| CRUD test scenarios | Built-in | No | No | No |
| Assertion helpers | Built-in | Built-in | No | No |

## Performance

Based on internal benchmarks (see `django_matt/utils/benchmarks.py`):

| Metric | django-matt | DRF | Django Ninja | FastAPI |
|--------|:-----------:|:---:|:------------:|:-------:|
| JSON serialization (orjson) | ~3x faster than stdlib | stdlib json | stdlib json | Optional orjson |
| Route matching (Rust radix) | O(path length) | Django URLconf | Django URLconf | Starlette trie |
| Schema validation | Pydantic v2 | DRF serializers (slower) | Pydantic v2 | Pydantic v2 |
| Query optimization | Auto select/prefetch | Manual | Manual | Manual |
| List serialization | `from_orm_fast()` (no re-validation) | Full re-serialization | Full re-serialization | Full re-serialization |
| JWT decode | Rust-accelerated (optional) | Python | Python | Python |

django-matt is not the fastest Python framework in raw request/response throughput -- that title goes to FastAPI on uvicorn. But the gap narrows significantly with orjson and the Rust router, and django-matt compensates with automatic query optimization that reduces total request time for real database-backed endpoints.

## When to Choose Each

### Choose django-matt when:
- You want batteries-included: auth, billing, multi-tenancy, codegen in one package
- You are building a SaaS product and need org/team/membership models
- You want Django's admin panel, ORM, and ecosystem
- You need TypeScript/Swift type generation from your API
- You want async-first with Pydantic v2 on Django
- Your team knows Django or is coming from DRF/Django Ninja

### Choose DRF when:
- You have a large existing DRF codebase and migration cost is too high
- You need a very mature, battle-tested framework with extensive third-party packages
- Your team knows DRF deeply and productivity matters more than async performance
- You do not need async (most CRUD apps do not)

### Choose Django Ninja when:
- You want a lightweight layer on Django with Pydantic
- You do not need auth, billing, real-time, or other batteries
- You prefer a minimal API surface and fewer abstractions

### Choose FastAPI when:
- You are not using Django and do not need its ORM/admin/ecosystem
- You are building a microservice that does not need a database (or uses a non-relational store)
- Raw ASGI throughput is your primary concern
- You want maximum control over every layer and are willing to assemble your own stack
- You are already deeply invested in SQLAlchemy

## Honest Trade-offs

### django-matt drawbacks
- **Large surface area** -- many modules means more to learn (mitigated by slim mode: load only what you use)
- **Django dependency** -- you are locked into the Django ecosystem
- **Newer** -- less battle-tested than DRF (which has 10+ years of production use)
- **Performance ceiling** -- Django's middleware stack adds overhead vs raw ASGI

### DRF drawbacks
- **Async story is weak** -- async views work but serializers, permissions, and filters are sync
- **Serializer boilerplate** -- verbose compared to Pydantic models
- **No built-in async test client**
- **Large dependency tree** -- needs simplejwt, django-filter, drf-spectacular, etc. for a complete setup

### Django Ninja drawbacks
- **Ecosystem fragmentation** -- need ninja-extra, ninja-jwt, ninja-crud, ninja-schema as separate packages
- **No class-based controllers** without ninja-extra
- **Limited auth** -- need to wire JWT yourself or use ninja-jwt
- **Sync by default** -- async support exists but is not the default path

### FastAPI drawbacks
- **No built-in ORM** -- must choose and configure SQLAlchemy + Alembic
- **No admin panel** -- must build or use third-party (SQLAdmin, etc.)
- **Auth is DIY** -- every project re-implements JWT, OAuth, etc.
- **No Django ecosystem** -- miss out on thousands of Django packages
- **Session management** -- manual database session lifecycle with `Depends(get_db)`

## Migration Guides

- [Migrating from DRF](migration/from-drf.md)
- [Migrating from Django Ninja](migration/from-django-ninja.md)
- [Migrating from FastAPI](migration/from-fastapi.md)
