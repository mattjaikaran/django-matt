# Why django-matt?

Django is one of the best frameworks ever built. But the moment you need a real production API in 2025 — JWT auth, billing, multi-tenancy, type-safe frontend contracts, background tasks, real-time — you are immediately assembling packages that were never designed to work together.

django-matt replaces that assembly with one cohesive library.

---

## The "Before" Stack

A typical Django API project with production features requires:

```
# Authentication
djangorestframework-simplejwt    # JWT
dj-rest-auth                     # login/logout endpoints
django-allauth                   # OAuth / social login
django-otp                       # 2FA
django-passkeys                  # WebAuthn (if you're lucky)

# API layer
djangorestframework              # DRF
drf-spectacular                  # OpenAPI docs
django-filter                    # query filtering
djangorestframework-camel-case   # JSON casing

# OR if using Ninja:
django-ninja
django-ninja-extra               # class-based controllers
django-ninja-jwt                 # JWT for Ninja
ninja-schema                     # schema extras
django-ninja-crud                # CRUD helpers

# Multi-tenancy
django-tenant-schemas            # or django-tenants
# (then rewrite half your queries for schema routing)

# Billing
dj-stripe                        # Stripe webhooks + models
# (wire up webhook views, signals, customer sync yourself)

# Background tasks
celery                           # task worker
redis                            # broker
django-celery-beat               # periodic tasks
django-celery-results            # result backend
flower                           # monitoring (separate process)

# Real-time
channels                         # WebSockets
channels-redis                   # channel layer
daphne                           # ASGI server

# Admin
django-unfold                    # modern admin theme
# (configure manually per model)

# Storage
django-storages                  # S3/R2/GCS
boto3                            # AWS SDK

# Testing
factory-boy                      # model factories
pytest-django                    # pytest integration
# async test client: write your own

# TypeScript types
# openapi-ts + manual glue script, or just... don't bother

# Total: 20-30 packages, each with its own config, signals,
# middleware, and gotchas. And you still haven't added feature
# flags, analytics, A/B testing, audit logging, or rate limiting.
```

## The "After" Stack

```python
# requirements.txt
django-matt

# settings.py
INSTALLED_APPS = ["django_matt", ...]

# api.py
from django_matt import MattAPI
api = MattAPI()
```

That's it. Auth, billing, multi-tenancy, tasks, real-time, type generation, testing helpers, admin — all configured and integrated.

---

## Feature Table

| Feature | django-matt | DRF | Django Ninja | FastAPI |
|---------|:-----------:|:---:|:------------:|:-------:|
| **API** | | | | |
| Pydantic v2 schemas | Yes | No (serializers) | Yes | Yes |
| Async-first | Yes | Partial | No | Yes |
| OpenAPI generation | Built-in | Via drf-spectacular | Built-in | Built-in |
| Class-based controllers | Yes | Yes (ViewSets) | Via ninja-extra | No |
| Declarative CRUD ViewSets | Yes | Yes | Via ninja-crud | No |
| Dependency injection | Built-in | No | Via ninja-extra | Built-in |
| orjson (base dep) | Yes | No | Optional | Optional |
| Rust-accelerated router | Yes | No | No | No |
| Content negotiation (JSON/XML/CSV/YAML/MsgPack) | Built-in | Built-in | No | No |
| Interceptors (before/after hooks) | Built-in | No | No | No |
| Exception filters | Built-in | Partial | No | No |
| **Auth** | | | | |
| JWT | Built-in | Via simplejwt | Via ninja-jwt | Roll your own |
| OAuth (Google, GitHub, Apple) | Built-in | Via allauth | Roll your own | Roll your own |
| SSO (SAML 2.0, OIDC) | Built-in | Roll your own | Roll your own | Roll your own |
| Passkeys / WebAuthn | Built-in | No | No | No |
| Magic links | Built-in | No | No | No |
| API keys with rate limits | Built-in | No | No | No |
| RBAC with role hierarchy | Built-in | No | No | No |
| Token blacklisting | Built-in | Via simplejwt | No | No |
| **Data** | | | | |
| Auto query optimization (select/prefetch) | Built-in | Manual | Manual | Manual |
| Fast list serialization (no re-validation) | Built-in | No | No | No |
| Soft delete | Built-in | No | No | No |
| Audit logging | Built-in | No | No | No |
| Multi-tenancy (org/team/membership) | Built-in | No | No | No |
| **Real-time** | | | | |
| WebSockets with auth middleware | Built-in | Via channels | Via channels | Built-in |
| SSE streaming | Built-in | No | No | Built-in |
| Presence tracking | Built-in | No | No | No |
| Event bus (in-memory + Redis) | Built-in | No | No | No |
| **Tasks** | | | | |
| Native task engine (no Celery required) | Built-in | No | No | No |
| Celery / Dramatiq / Django-Q abstraction | Built-in | Via celery | Via celery | BackgroundTasks |
| Scheduled / periodic tasks | Built-in | Via celery-beat | Via celery-beat | No |
| Task admin dashboard | Built-in | Via flower | Via flower | No |
| Dead letter queue | Built-in | Manual | Manual | No |
| **Developer Experience** | | | | |
| TypeScript codegen | Built-in | Via drf-spectacular | No | Via openapi-ts |
| Swift codegen | Built-in | No | No | No |
| CLI scaffolding (`generate_crud`, `startapi`) | Built-in | No | No | No |
| Async test client | Built-in | No | No | httpx |
| Model factories | Built-in | Via factory-boy | Via factory-boy | No |
| CRUD test scenarios | Built-in | No | No | No |
| Migration acceleration (baseline, parallel, squash) | Built-in | No | No | No |
| **Infrastructure** | | | | |
| Feature flags (DB, Redis, LaunchDarkly, Unleash) | Built-in | No | No | No |
| A/B testing with statistical analysis | Built-in | No | No | No |
| Billing (Stripe, PayPal, Polar) | Built-in | No | No | No |
| Observability (tracing, metrics, structured logs) | Built-in | No | No | No |
| Rate limiting / throttling | Built-in | Built-in | No | Via slowapi |
| Secrets management (env, Vault, AWS SM, GCP SM) | Built-in | No | No | No |
| AI-assisted codebase audits | Built-in | No | No | No |
| Slim / lazy module loading | Built-in | No | No | No |

---

## What You Get for Free

Things you would otherwise spend days building — or never build at all:

### Type Generation
```bash
python manage.py sync_types --target typescript --output frontend/types
```
Every route, schema, and error type in your Django API becomes a TypeScript interface. No manual sync. No drift.

### Multi-tenancy
```python
class Project(TenantModel):
    ...
```
Organization, Team, Membership models with middleware-level tenant isolation. Not a schema-routing hack — clean FK-based tenancy that works with Django's ORM as-is.

### Billing
```python
@api.post("/subscribe")
async def subscribe(self, plan: str, request: HttpRequest):
    customer = await billing.get_or_create_customer(request.user)
    return await billing.create_subscription(customer, plan)
```
Stripe webhooks handled automatically. Customer sync, subscription state, invoice history — models included.

### Audit Logging
Every model write is logged automatically once you add `AuditMixin`. IP address, user agent, before/after state, soft delete — zero boilerplate.

### Native Tasks (no Celery required)
```python
@task(retry=3, retry_backoff=True)
async def send_welcome_email(user_id: int):
    ...

# Call it anywhere:
await send_welcome_email.delay(user_id=user.id)
```
Runs on Django's native task backend (6.0+), falls back to Celery or Dramatiq if present. Dead letter queue, admin dashboard, scheduled tasks — all included.

### AI-Assisted Audits
```bash
python manage.py matt_audit security --level strict
python manage.py matt_audit --output sarif  # → GitHub Code Scanning
```
Static + dynamic analysis across your entire codebase. SARIF output integrates directly with GitHub's security tab.

### Rust Acceleration (optional)
```python
# zero config — detected automatically at startup
# Route matching: 4x faster (radix trie vs Django URLconf)
# JWT verify: 1.5x faster
# JSON serialize: 1.9x faster (orjson is a base dep)
# Query string parse: 4x faster
```

---

## Package Count Comparison

**Building a SaaS API with DRF:**
```
djangorestframework, simplejwt, dj-rest-auth, django-allauth,
drf-spectacular, django-filter, django-storages, boto3,
celery, redis, django-celery-beat, django-celery-results,
channels, channels-redis, dj-stripe, django-tenant-schemas,
factory-boy, pytest-django, django-unfold

= 19 packages minimum, more for feature flags / analytics / A/B
```

**Building the same SaaS API with django-matt:**
```
django-matt

= 1 package
```

---

## Line Count Comparison

Rough line counts for a production auth setup (JWT + OAuth + RBAC):

| Approach | Lines of glue code |
|----------|--------------------|
| DRF + simplejwt + allauth | ~400-600 lines |
| Django Ninja + ninja-jwt + ninja-extra | ~300-500 lines |
| django-matt | ~20 lines (controller + decorator) |

---

## Async: First-Class vs Bolted On

| | django-matt | DRF | Django Ninja | FastAPI |
|--|:-----------:|:---:|:------------:|:-------:|
| Async handlers | Yes | Yes (Django 4.1+) | Yes | Yes |
| Async auth middleware | Yes | No | No | Yes |
| Async permissions | Yes | No | No | Yes |
| Async test client | Yes | No | No | Yes |
| ORM calls auto-guarded | Yes (sync_to_async) | No | No | Yes (SQLAlchemy async) |
| Sync ORM in async handler | Warning + safe fallback | Silently blocks | Silently blocks | N/A |

DRF added `async def` views in Django 4.1 but its permissions, throttles, and serializers are still sync. You get async handlers that block on every auth check.

Django Ninja's async support is similar — the endpoint can be async, but the underlying machinery is not.

django-matt is async from the controller wrapper through auth, permissions, DI resolution, and the test client. The ORM stays sync (it's Django's ORM) and every sync call is wrapped in `sync_to_async` automatically.

---

## Honest Trade-offs

django-matt is the right choice when you need a full-stack Django API with production features and want to spend your time on product, not infrastructure.

It is **not** the right choice when:
- You have a large existing DRF codebase — migration cost is real
- You want the absolute fastest raw ASGI throughput — FastAPI on uvicorn wins that benchmark
- You prefer assembling your own stack and owning every dependency — django-matt's surface area is large by design
- You are building a one-off microservice that needs only one or two endpoints

See [comparison.md](./comparison.md) for the full framework comparison and honest trade-offs per framework.
