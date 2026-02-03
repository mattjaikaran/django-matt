# django-matt

<div class="grid cards" markdown>

-   :zap: **Async-First**

    ---

    Built for Python 3.12+ with full async/await support throughout the stack.

-   :lock: **Secure by Default**

    ---

    JWT, OAuth, Passkeys, SSO - every auth method you need, built-in.

-   :rocket: **Developer Experience**

    ---

    Hot reload, type generation, interactive playground, and more.

-   :package: **All-in-One**

    ---

    Replaces 5+ packages with one cohesive, well-designed framework.

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
        users = await User.objects.all()
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

# Or with pip
pip install django-matt

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

api.register_controller(OrganizationController, prefix="/orgs")
api.register_controller(TeamController, prefix="/teams")
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

api.register_controller(BillingController, prefix="/billing")
api.register_controller(WebhookController, prefix="/billing/webhooks")
```

[Learn more about billing](billing/overview.md)

### Performance

Built-in performance optimizations:

- **Fast JSON** - orjson/ujson serialization
- **Streaming** - Large dataset streaming
- **Caching** - Response and query caching
- **Query optimization** - N+1 detection

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

| django-matt | Python | Django |
|-------------|--------|--------|
| 0.1.x | 3.12+ | 5.2+ |
| 0.2.x (planned) | 3.13+ | 6.0+ |

## Community

- [GitHub Repository](https://github.com/mattjaikaran/django-matt)
- [Issue Tracker](https://github.com/mattjaikaran/django-matt/issues)
- [Discussions](https://github.com/mattjaikaran/django-matt/discussions)

## Status

This is an internal/private framework. It is not published to PyPI.
