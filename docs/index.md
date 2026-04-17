# django-matt

<div class="grid cards" markdown>

-   :zap: **Async-First**

    ---

    Built for Python 3.12+ with full async/await support throughout the stack. Optional Rust extensions for hot paths.

-   :lock: **Secure by Default**

    ---

    JWT, OAuth, Passkeys, SSO - every auth method you need, built-in.

-   :rocket: **Developer Experience**

    ---

    Hot reload, type generation, interactive playground, and more.

-   :package: **All-in-One**

    ---

    54+ modules replace 5+ packages with one cohesive, production-ready framework.

</div>

## Why django-matt?

**django-matt** consolidates the fragmented Django Ninja ecosystem into a single, cohesive framework. No more juggling `django-ninja`, `django-ninja-extra`, `django-ninja-jwt`, `ninja-schema`, and `django-ninja-crud`.

```python
from django_matt import MattAPI, APIController, IsAuthenticated
from django_matt.auth import jwt_required

api = MattAPI(title="My API", version="1.0.0")

@api.controller("/users", tags=["Users"])
class UserController(APIController):
    permission_classes = [IsAuthenticated]

    @api.get("/")
    async def list_users(self):
        users = [u async for u in User.objects.all()]
        return [UserSchema.from_orm(u) for u in users]

    @api.get("/{user_id}")
    async def get_user(self, user_id: int):
        user = await User.objects.aget(id=user_id)
        return UserSchema.from_orm(user)
```

## Feature Comparison

| Feature | django-matt | DRF | Django Ninja |
|---------|-------------|-----|--------------|
| Async-first | Yes | Partial | Yes |
| Pydantic v2 | Yes | No | Yes |
| Class-based controllers | Yes | Yes | Via extra |
| JWT built-in | Yes | Via package | Via package |
| OAuth providers | Yes | No | No |
| Passkeys/WebAuthn | Yes | No | No |
| Enterprise SSO | Yes | No | No |
| Multi-tenancy | Yes | No | No |
| Billing integration | Yes | No | No |
| Type generation | Yes | Via package | No |
| SSE streaming | Yes | No | No |
| Event bus | Yes | No | No |
| CQRS | Yes | No | No |
| Interceptors | Yes | No | No |
| Rust extensions | Yes | No | No |
| Secrets management | Yes | No | No |
| Interactive playground | Yes | Browsable API | No |
| Hot reload | Yes | No | No |

## What You Replace

| Package | Feature | django-matt Module |
|---------|---------|-------------------|
| `django-ninja` | Core routing, OpenAPI | `django_matt.core` |
| `django-ninja-extra` | Class controllers, DI | `django_matt.core.controller` |
| `django-ninja-jwt` | JWT authentication | `django_matt.auth` |
| `ninja-schema` | ModelSchema for ORM | `django_matt.core.schema` |
| `django-ninja-crud` | CRUD views | `django_matt.views` |

## Quick Start

```bash
# Install with uv (recommended)
uv add django-matt

# Create a new project with everything configured
python manage.py startapi myproject --template b2b --auth jwt
```

```python
# myproject/api.py
from django_matt import MattAPI

api = MattAPI(title="My API", version="1.0.0")

@api.get("/hello")
async def hello(request):
    return {"message": "Hello, World!"}
```

```python
# myproject/urls.py
from django.urls import path
from .api import api

urlpatterns = [
    path("api/", api.urls),
]
```

Visit `http://localhost:8000/api/docs` for interactive Swagger documentation.

## What's New in 0.8

The 0.8 release is the largest yet, adding 13 new modules and optional Rust acceleration:

- **13 new modules** -- interceptors, SSE streaming, async event bus, CQRS, secrets management, introspection, RPC client generation, module system, serialization groups, exception filters, config validation, route-scoped middleware, slim mode
- **Rust extensions** -- optional PyO3 native extensions deliver up to 1.9x overall speedup on hot paths (router, JWT, serialization, rate limiting, permissions, query building, middleware)
- **54+ total modules** -- from auth to billing to observability, all designed to work together
- **6,300+ tests** -- comprehensive coverage across sync, async, and Rust paths
- **Code review agent** -- `generate_ai_context` produces CLAUDE.md and .cursorrules for AI-assisted development
- **Vite integration** -- first-class Vite dev server support with HMR proxy
- **Inertia.js adapter** -- server-driven SPA with Django templates and React/Vue/Svelte frontends
- **Predicate-based permissions** -- compose permission checks with `&`, `|`, `~` operators
- **Hybrid properties** -- `@hybrid_property` for computed fields that work in Python and SQL
- **Modern forms** -- Pydantic-powered form handling with validation
- **File storage redesign** -- unified API across S3, R2, MinIO, and local backends

## Rust Acceleration

Django Matt includes optional Rust extensions (via PyO3) that accelerate CPU-bound hot paths while keeping the framework pure-Python by default:

```bash
# Install with Rust support
uv add "django-matt[rust]"
```

| Component | What it accelerates |
|-----------|-------------------|
| Router | Radix tree route matching |
| JWT | Token encode/decode/verify |
| Serialization | JSON serialization with camelCase mapping |
| Rate limiting | Token bucket and sliding window counters |
| Permissions | Permission tree evaluation |
| Query building | Query string and filter parsing |
| Middleware | Header parsing and request routing |

Extensions are **completely optional** -- the framework auto-detects availability and falls back to pure Python:

```python
from django_matt._accel import HAS_RUST  # True if extensions are installed
```

## Key Features

### Authentication

Built-in support for every authentication method:

- **JWT** - Access and refresh tokens with rotation
- **Session** - Traditional Django sessions with CSRF
- **API Keys** - For service-to-service auth
- **OAuth** - Google, GitHub, Apple, Microsoft
- **Passkeys** - WebAuthn for passwordless auth
- **SSO** - SAML 2.0 and OIDC for enterprise

[Learn more about authentication](auth/overview.md)

### CRUD Views

Compose CRUD operations with declarative views:

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

class ProductViewSet(APIViewSet):
    model = Product
    default_response_schema = ProductSchema

    list = ListView()
    create = CreateView(permission_classes=[IsAuthenticated])
    read = ReadView()
    update = UpdateView(permission_classes=[IsOwner])
    delete = DeleteView(permission_classes=[IsOwner])
```

[Learn more about CRUD views](features/views.md)

### Multi-Tenancy

Full B2B support with organizations, teams, and memberships:

```python
from django_matt.multitenancy import OrganizationController, TeamController

api.register_controller(OrganizationController)
api.register_controller(TeamController)
```

[Learn more about multi-tenancy](multitenancy/overview.md)

### Type Generation

Generate TypeScript or Swift types from your Pydantic schemas:

```bash
# Generate TypeScript types
python manage.py sync_types --target typescript --output frontend/types

# Generate Swift types
python manage.py sync_types --target swift --output ios/Sources/Models

# Watch mode for development
python manage.py sync_types --target typescript --watch
```

[Learn more about type generation](typegen/typescript.md)

### Billing Integration

Integrated billing with Stripe, PayPal, and Polar:

```python
from django_matt.billing import BillingController, WebhookController

api.register_controller(BillingController)
api.register_controller(WebhookController)
```

[Learn more about billing](billing/overview.md)

### Performance

Built-in performance optimizations:

- **Fast JSON** - orjson serialization (base dependency)
- **Rust extensions** - optional PyO3 native modules for router, JWT, serialization, and more
- **Streaming** - SSE, NDJSON, and large dataset streaming
- **Caching** - Response and query caching with Redis support
- **Query optimization** - automatic N+1 detection with `select_related`/`prefetch_related`

[Learn more about performance](performance/optimization.md)

## Documentation

<div class="grid cards" markdown>

-   :material-clock-fast: **Getting Started**

    ---

    Install django-matt and create your first API in 5 minutes.

    [:octicons-arrow-right-24: Quick Start](getting-started/quickstart.md)

-   :material-book-open-variant: **Core Concepts**

    ---

    Learn about routing, controllers, schemas, and error handling.

    [:octicons-arrow-right-24: Core Concepts](core/routing.md)

-   :material-shield-account: **Authentication**

    ---

    Configure JWT, OAuth, Passkeys, and enterprise SSO.

    [:octicons-arrow-right-24: Authentication](auth/overview.md)

-   :material-code-braces: **API Reference**

    ---

    Complete reference for all modules and classes.

    [:octicons-arrow-right-24: API Reference](api/core.md)

-   :material-book-multiple: **Cookbook**

    ---

    Common patterns, recipes, and best practices.

    [:octicons-arrow-right-24: Cookbook](cookbook/common-patterns.md)

-   :material-swap-horizontal: **Migration Guides**

    ---

    Migrate from DRF or Django Ninja to django-matt.

    [:octicons-arrow-right-24: Migration](migration/from-drf.md)

</div>

## Version Compatibility

| django-matt | Python | Django | Status |
|-------------|--------|--------|--------|
| 0.8.x | 3.12+ | 5.2+ | **Current** |
| 1.0 (planned) | 3.13+ | 6.0+ | Upcoming |

## Community

- [GitHub Repository](https://github.com/mattjaikaran/django-matt)
- [Issue Tracker](https://github.com/mattjaikaran/django-matt/issues)
- [Discussions](https://github.com/mattjaikaran/django-matt/discussions)

## License

Apache License 2.0. See [LICENSE](https://github.com/mattjaikaran/django-matt/blob/main/LICENSE) for details.
