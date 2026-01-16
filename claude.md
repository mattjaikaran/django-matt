# Django Matt - Claude Code Context

> Internal Django meta-framework consolidating Django Ninja ecosystem into one cohesive library.

## Project Overview

**django-matt** is a modern Django API framework that replaces multiple packages (Django Ninja, Django Ninja Extra, Django Ninja JWT, ninja-schema, django-ninja-crud) with a single, cohesive library. Built for Python 3.12+ with async-first design.

### Tech Stack
- **Python**: 3.12+ (3.13 recommended) with `uv` package manager
- **Django**: 5.2+
- **Validation**: Pydantic 2.0+
- **Frontend tooling**: bun
- **Containers**: Docker + Docker Compose

## Project Structure

```
django_matt/
├── api.py                  # MattAPI - main entry point
├── core/                   # Router, Controller, Schema, Errors
├── auth/                   # JWT, magic links, RBAC
├── views/                  # Composable CRUD views (ListView, CreateView, etc.)
├── permissions/            # Permission classes & decorators
├── openapi/                # OpenAPI/Swagger/ReDoc generation
├── config/                 # Modular configuration system
├── db/                     # Database utilities (PostgreSQL, pgvector)
├── multitenancy/           # B2B support (Organization, Team, Membership)
├── typegen/                # TypeScript/Swift code generation
├── testing/                # Test client, factories, fixtures, assertions
├── utils/                  # Performance, hot reload, errors
└── management/commands/    # CLI: startapi, config, sync_types, runserver_hot
```

## Key Modules

### Core (`django_matt.core`)
- **router.py**: `@get`, `@post`, `@put`, `@patch`, `@delete` decorators
- **controller.py**: `APIController`, `CRUDController` with DI support
- **schema.py**: `ModelSchema`, `create_schema_from_model()`
- **errors.py**: `APIError`, `NotFoundAPIError`, `ValidationAPIError`

### Authentication (`django_matt.auth`)
- **jwt.py**: Access/refresh tokens, `@jwt_required`, `@jwt_optional`
- **magic_link.py**: Passwordless email authentication
- **rbac/**: Role-based access control with hierarchy
- **controllers.py**: `/auth/login`, `/register`, `/refresh`, `/logout`, `/me`

### Views (`django_matt.views`)
- `ListView`, `CreateView`, `ReadView`, `UpdateView`, `DeleteView`
- `APIViewSet` for composing views
- Automatic pagination, filtering, schema inference

### Permissions (`django_matt.permissions`)
- Classes: `IsAuthenticated`, `IsAdmin`, `IsOwner`, `AllowAny`, `HasRole`
- Decorators: `@authenticated`, `@requires_permission()`, `@requires_role()`

### Multi-tenancy (`django_matt.multitenancy`)
- Models: `Organization`, `Team`, `Membership`, `Invitation`
- Full REST controllers for B2B applications
- Tenant context middleware

### Type Generation (`django_matt.typegen`)
- **typescript.py**: Pydantic → TypeScript interfaces, Zod schemas
- **swift.py**: Pydantic → Swift Codable structs
- **api_client.py**: Typed API client generation

### Performance (`django_matt.utils.performance`)
- `FastJSONRenderer` (orjson/ujson), `MessagePackRenderer`
- `StreamingJsonResponse` for large datasets
- `@cache_response()`, `@cache_result()` decorators
- `APIBenchmark`, `BenchmarkMiddleware`
- `DistributedCacheManager` - Redis cluster support with stampede prevention
- `QueryAnalyzer` - N+1 detection and optimization suggestions
- `PerformanceSuggester` - Runtime analysis and recommendations

### Passkeys/WebAuthn (`django_matt.auth.passkeys`)
- `PasskeyController` - Full registration and authentication endpoints
- `generate_registration_options()`, `verify_registration_response()`
- `generate_authentication_options()`, `verify_authentication_response()`
- `PasskeyCredential` model for storing credentials

### Testing (`django_matt.testing`)
- `APITestClient`, `AsyncAPITestClient`
- Factories: `UserFactory`, `OrganizationFactory`, `TeamFactory`
- Assertions: `assert_status()`, `assert_json_equal()`, `assert_created()`

## CLI Commands

```bash
# Initialize new project
python manage.py startapi myproject --template b2b --auth jwt --docker

# Configuration management
python manage.py config init
python manage.py config generate --env production

# Type synchronization
python manage.py sync_types --target typescript --output frontend/types
python manage.py sync_types --target swift --watch

# Hot reload development server
python manage.py runserver_hot
```

## Development Progress

### Completed (Stages 1-2, Phase 4A)

| Feature | Status | Location |
|---------|--------|----------|
| Core routing & decorators | Done | `core/router.py` |
| Class-based controllers | Done | `core/controller.py` |
| Pydantic ModelSchema | Done | `core/schema.py` |
| Error handling | Done | `core/errors.py` |
| OpenAPI/Swagger/ReDoc | Done | `openapi/` |
| JWT authentication | Done | `auth/jwt.py` |
| Magic link auth | Done | `auth/magic_link.py` |
| RBAC with hierarchy | Done | `auth/rbac/` |
| Auth controllers | Done | `auth/controllers.py` |
| Composable CRUD views | Done | `views/` |
| Permission system | Done | `permissions/` |
| Multi-tenancy (B2B) | Done | `multitenancy/` |
| TypeScript generator | Done | `typegen/typescript.py` |
| Swift generator | Done | `typegen/swift.py` |
| sync_types CLI | Done | `management/commands/sync_types.py` |
| startapi command | Done | `management/commands/startapi.py` |
| Hot reloading | Done | `utils/hot_reload.py` |
| Fast JSON (orjson/ujson) | Done | `utils/performance.py` |
| MessagePack serialization | Done | `utils/performance.py` |
| Streaming responses | Done | `utils/performance.py` |
| Response caching | Done | `utils/performance.py` |
| Benchmarking | Done | `utils/performance.py` |
| Distributed caching | Done | `utils/performance.py` |
| Query optimization | Done | `utils/performance.py` |
| Performance suggestions | Done | `utils/performance.py` |
| Passkeys/WebAuthn | Done | `auth/passkeys/` |
| Config system | Done | `config/` |
| PostgreSQL + pgvector | Done | `db/` |
| Testing utilities | Done | `testing/` |

### In Progress / Next Up

| Feature | Priority | Notes |
|---------|----------|-------|
| OAuth providers (Google, GitHub, Apple) | High | Add to `auth/oauth/` |
| Content negotiation | Medium | Multiple response formats |
| CRUD generator CLI | Medium | Generate from models |
| Subscriptions/billing (B2C) | Medium | Stripe integration |
| Real-time WebSockets | Low | Beyond hot-reload |
| HTMX integration | Low | View helpers |

### Template Repositories (Separate Repos - Not Started)

- `django-api-starter` - Minimal API template
- `react-vite-starter` - React frontend
- `django-api-b2b` - B2B with orgs/teams
- `fullstack-b2b` - Monorepo template
- `swift-ios-starter` - iOS app template

## Quick Reference

### Creating an API

```python
from django_matt import MattAPI
from django_matt.core import APIController
from django_matt.permissions import IsAuthenticated

api = MattAPI()

@api.controller("/users", tags=["Users"])
class UserController(APIController):
    permission_classes = [IsAuthenticated]

    @api.get("/")
    async def list_users(self):
        return await User.objects.all()

    @api.post("/")
    async def create_user(self, data: UserCreateSchema) -> UserSchema:
        user = await User.objects.create(**data.model_dump())
        return user
```

### Using CRUD Views

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

class ProductViewSet(APIViewSet):
    api = api
    model = Product
    default_response_schema = ProductSchema

    list = ListView()
    create = CreateView()
    read = ReadView()
    update = UpdateView()
    delete = DeleteView()
```

### Authentication

```python
from django_matt.auth import jwt_required, jwt_optional

@api.get("/protected")
@jwt_required
async def protected_route(request):
    return {"user": request.user.email}

@api.get("/optional")
@jwt_optional
async def optional_auth(request):
    if request.user.is_authenticated:
        return {"user": request.user.email}
    return {"user": "anonymous"}
```

### Passkeys/WebAuthn

```python
from django_matt.auth.passkeys import PasskeyController

# Add to your API (provides /passkeys/* endpoints)
api.register_controller(PasskeyController, prefix="/auth")

# Or use functions directly
from django_matt.auth.passkeys import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
)

# Registration flow
options = generate_registration_options(user)
# ... client creates credential ...
credential = verify_registration_response(user, credential_id, client_data, attestation, challenge_id)

# Authentication flow
options = generate_authentication_options(email="user@example.com")
# ... client authenticates ...
user, credential = verify_authentication_response(credential_id, client_data, auth_data, sig, challenge_id)
```

### Query Optimization

```python
from django_matt.utils import optimize_queryset, query_analyzer

# Auto-optimize a queryset
users = optimize_queryset(User.objects.all())  # Adds select_related/prefetch_related

# Analyze for suggestions
analysis = query_analyzer.analyze_queryset(User.objects.all())
print(analysis["suggestions"])  # Shows what's missing

# Enable query logging middleware for N+1 detection
# Add 'django_matt.utils.QueryLoggingMiddleware' to MIDDLEWARE
```

### Distributed Caching

```python
from django_matt.utils import distributed_cache

# Get or compute with stampede prevention
value = distributed_cache.get_or_set(
    "expensive_query",
    lambda: expensive_computation(),
    timeout=300,
)

# Bulk operations
values = distributed_cache.get_many(["key1", "key2", "key3"])
distributed_cache.set_many({"key1": "val1", "key2": "val2"})

# Atomic counters
distributed_cache.incr("page_views")
```

## Testing

```bash
# Run tests
pytest tests/

# With coverage
pytest tests/ --cov=django_matt

# Specific test file
pytest tests/test_auth.py -v
```

## Common Tasks

### Adding a new feature
1. Create module in appropriate package
2. Add tests in `tests/`
3. Update `__init__.py` exports
4. Add documentation in `docs/`

### Working on authentication
- JWT logic: `auth/jwt.py`
- Magic links: `auth/magic_link.py`
- RBAC: `auth/rbac/`
- Controllers: `auth/controllers.py`
- Schemas: `auth/schemas.py`

### Working on multi-tenancy
- Models: `multitenancy/models.py`
- Controllers: `multitenancy/controllers.py`
- Middleware: `multitenancy/middleware.py`
- Schemas: `multitenancy/schemas.py`

### Performance work
- All in `utils/performance.py`
- Caching, serialization, benchmarking

## Important Files

- `ROADMAP.md` - Development phases and checklist
- `todos.md` - Detailed development plan
- `docs/` - Feature documentation
- `examples/` - Working example apps
- `pyproject.toml` - Dependencies and project config

## Code Style

- Async-first design (use `async def` for handlers)
- Pydantic for all request/response schemas
- Type hints everywhere
- Keep external dependencies minimal
- Document as you go
