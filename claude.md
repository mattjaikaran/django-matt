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
├── auth/                   # JWT, magic links, RBAC, OAuth, SSO, Passkeys
├── views/                  # Composable CRUD views (ListView, CreateView, etc.)
├── permissions/            # Permission classes & decorators
├── openapi/                # OpenAPI/Swagger/ReDoc generation
├── config/                 # Modular configuration system
├── db/                     # Database utilities (PostgreSQL, pgvector)
├── multitenancy/           # B2B support (Organization, Team, Membership)
├── typegen/                # TypeScript/Swift code generation
├── testing/                # Test client, factories, fixtures, assertions
├── utils/                  # Performance, hot reload, errors
├── admin/                  # Django Unfold admin integration, dashboards, widgets
└── management/commands/    # CLI: startapi, config, sync_types, generate_crud
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

### OAuth Social Login (`django_matt.auth.oauth`)
- `OAuthController` - Full OAuth flow endpoints
- Providers: `GoogleOAuthProvider`, `GitHubOAuthProvider`, `AppleOAuthProvider`, `MicrosoftOAuthProvider`
- `OAuthConnection` model for storing user-provider links
- Support for both redirect and SPA flows

### Enterprise SSO (`django_matt.auth.sso`)
- `SSOController` - Full SSO flow endpoints
- `SAMLProvider` - SAML 2.0 authentication
- `OIDCProvider` - OpenID Connect with PKCE
- `SSOConnection` model for per-org configuration
- Supports: Okta, Azure AD, Google Workspace, Auth0, OneLogin

### Testing (`django_matt.testing`)
- `APITestClient`, `AsyncAPITestClient`
- Factories: `UserFactory`, `OrganizationFactory`, `TeamFactory`
- Assertions: `assert_status()`, `assert_json_equal()`, `assert_created()`

### Billing (`django_matt.billing`)
- `BillingController` - Full REST API for billing operations
- `WebhookController` - Handles webhooks from all providers
- Providers: `StripeProvider`, `PayPalProvider`, `PolarProvider`
- Models: `BillingCustomer`, `Subscription`, `Invoice`, `BillingProduct`, `BillingPrice`
- `get_provider()` - Factory function for provider instances

### Content Negotiation (`django_matt.negotiation`)
- `ContentNegotiationMiddleware` - Automatic format negotiation
- Renderers: `JSONRenderer`, `XMLRenderer`, `CSVRenderer`, `YAMLRenderer`, `MessagePackRenderer`, `HTMLRenderer`
- Parsers: `JSONParser`, `XMLParser`, `YAMLParser`, `MessagePackParser`
- Decorators: `@renders()`, `@render_as()`, `@content_negotiated`, `@with_template()`
- `negotiate()`, `render()`, `render_format()` - Direct negotiation functions

### WebSockets (`django_matt.websockets`)
- Consumers: `BaseConsumer`, `JsonConsumer`, `AuthenticatedConsumer`, `RoomConsumer`
- Auth: `JWTAuthMiddleware`, `SessionAuthMiddleware`, `AuthMiddlewareStack`
- Groups: `broadcast()`, `send_to_user()`, `PresenceManager`
- Routing: `WebSocketRouter`, `create_asgi_application()`
- Schemas: `ChatMessage`, `NotificationMessage`, `PresenceMessage`, etc.

### Feature Flags (`django_matt.flags`)
- Models: `FeatureFlag`, `FlagOverride`, `FlagAuditLog`
- Types: Boolean, percentage rollout, and variant (A/B testing) flags
- Backends: `DatabaseBackend`, `RedisBackend`, `LaunchDarklyBackend`, `UnleashBackend`
- Functions: `feature_enabled()`, `get_variant()`, `get_all_flags()`
- Decorators: `@feature_flag()`, `@requires_flag()`, `@variant_flag()`
- Context: `FlagContext` for evaluation with user/org context
- Middleware: `FlagMiddleware` for automatic context setup
- Controllers: `FlagController` - Full REST API for flag management
- Admin: Django admin integration for flag management

### GraphQL (`django_matt.graphql`)
- **schema.py**: `GraphQLSchema`, `generate_schema()` - Auto-generate schema from Django models
- **types.py**: `DjangoModelType`, `create_type_from_model()`, `ConnectionType`, `NodeInterface`
- **queries.py**: `QueryGenerator`, `generate_list_query()`, `generate_detail_query()`
- **mutations.py**: `MutationGenerator`, CRUD mutations generator
- **subscriptions.py**: `SubscriptionManager`, `SubscriptionGenerator` - WebSocket subscriptions
- **dataloaders.py**: `DataLoaderRegistry`, `ModelDataLoader`, `RelatedDataLoader` - N+1 prevention
- **middleware.py**: `AuthMiddleware`, `RateLimitMiddleware`, `ComplexityMiddleware`, `PersistedQueryMiddleware`
- **decorators.py**: `@graphql_type`, `@graphql_input`, `@resolver`, `@mutation`, `@subscription`
- **views.py**: `GraphQLView`, `AsyncGraphQLView`, `GraphQLAPI`
- **codegen.py**: `TypeScriptGenerator`, `generate_typescript_types()`, `generate_typescript_client()`
- Requires: `pip install strawberry-graphql[django]`

### Admin (`django_matt.admin`)
Django Unfold admin integration with dashboard builder and custom page support.

**Base Classes:**
- `MattModelAdmin` - Auto-configured admin with list_display, search_fields, filters
- `MattStackedInline`, `MattTabularInline` - Inline admin classes
- `register_admin(Model)` - Decorator for quick registration

**Mixins:**
- `AuditAdminMixin` - Created/updated tracking
- `SoftDeleteAdminMixin` - Soft delete support with restore action
- `MultiTenantAdminMixin` - Filter by organization/tenant
- `ExportAdminMixin` - CSV/JSON export actions

**Dashboard Widgets (`admin/widgets.py`):**
- `StatWidget` - Statistics card with value, change indicator, icon
- `ActivityWidget` - Recent activity feed
- `QuickActionsWidget` - Grid of action buttons
- `TableWidget` - Simple data tables
- `ProgressWidget` - Progress/goal indicators
- `model_stat_widget(Model)` - Auto-generate stats from Django model

**Chart Components (`admin/charts.py`):**
- `ChartWidget` - Chart.js charts (line, bar, doughnut, pie, area, radar)
- `SparklineWidget` - Compact inline sparklines
- `model_time_series_chart(Model)` - Auto-generate time series from model
- `model_distribution_chart(Model, field)` - Auto-generate pie/doughnut from field

**Dashboard Builder (`admin/dashboard.py`):**
- `Dashboard` - Build dashboards with stats, charts, sections
- `DashboardSection` - Collapsible grid sections
- `DashboardAdminSite` - Custom AdminSite with dashboard support
- `auto_dashboard()` - Auto-generate dashboard from registered admin models

**Page Builder (`admin/pages.py`):**
- `AdminPage` - Custom admin pages with permission support
- `AdminPageGroup` - Group pages under common parent
- `AdminPageRegistry` - `@pages.register()` decorator for page registration
- `PageBuilderMixin` - Add custom pages to any AdminSite

### AI IDE Context (`django_matt.ai.context`)
Enhanced AI IDE integration for generating context files.

**Generators:**
- `ClaudeMdGenerator` - CLAUDE.md for Claude Code
- `CursorRulesGenerator` - .cursorrules for Cursor IDE
- `CopilotInstructionsGenerator` - .copilot-instructions for GitHub Copilot
- `JsonIntrospectionGenerator` - Machine-readable JSON introspection
- `ContextGenerator` - Unified generator for all formats

**Introspection:**
- `EnhancedIntrospector` - Deep project introspection
- `EndpointInfo` - API endpoint with method, auth, schemas
- `AuthRequirement` - Auth type (jwt_required, jwt_optional, api_key, etc.)
- `PydanticSchemaInfo` - Schema with field types and constraints
- `TestPatternInfo` - Test framework and fixture detection

**Watch Mode:**
- `ContextWatcher` - File watcher with debounced auto-updates
- `DebouncedCallback` - Batches rapid file changes
- `FileChangeHandler` - Filters relevant file changes

**Pre-commit Integration:**
- `generate_precommit_hook()` - Shell script for pre-commit
- `generate_precommit_config()` - YAML configuration
- `install_precommit_hook()` - Auto-install hook

**HTTP Endpoint:**
- `/_matt/introspection` - JSON introspection endpoint
- `/_matt/introspection/endpoints` - List all API endpoints
- `/_matt/introspection/schemas` - List all Pydantic schemas
- `/_matt/introspection/models` - List all Django models

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

# Development server (hot reload enabled by default)
python manage.py runserver              # Hot reload enabled (default)
python manage.py runserver --no-hot     # Standard Django behavior
python manage.py runserver 8080         # Custom port with hot reload

# Generate CRUD from Django models (service layer included by default)
python manage.py generate_crud myapp.MyModel              # Includes service layer by default
python manage.py generate_crud myapp.MyModel --no-service # Skip service layer
python manage.py generate_crud myapp.MyModel --with-admin # Add Django Unfold admin
python manage.py generate_crud myapp.MyModel --full       # All: controller, schema, service, admin, tests
python manage.py generate_crud myapp.MyModel --permissions IsAuthenticated --soft-delete
python manage.py generate_crud myapp.MyModel --dry-run    # Preview without writing

# AI Context Generation (for IDE integration)
python manage.py generate_ai_context                     # Generate claude, cursor, copilot files
python manage.py generate_ai_context --format all        # All formats including JSON
python manage.py generate_ai_context --format claude     # Only CLAUDE.md
python manage.py generate_ai_context --format cursor     # Only .cursorrules
python manage.py generate_ai_context --format copilot    # Only .copilot-instructions
python manage.py generate_ai_context --watch             # Auto-update on file changes
python manage.py generate_ai_context --include-examples  # Include code examples
python manage.py generate_ai_context --output-json       # Output JSON to stdout
python manage.py generate_ai_context --install-hook      # Install pre-commit hook
python manage.py generate_ai_context --show-hook         # Show hook script
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
| OAuth (Google, GitHub, Apple, Microsoft) | Done | `auth/oauth/` |
| Enterprise SSO (SAML, OIDC) | Done | `auth/sso/` |
| Config system | Done | `config/` |
| PostgreSQL + pgvector | Done | `db/` |
| Testing utilities | Done | `testing/` |
| CRUD generator CLI | Done | `management/commands/generate_crud.py` |
| Billing (Stripe, PayPal, Polar) | Done | `billing/` |
| Content negotiation | Done | `negotiation/` |
| Feature flags | Done | `flags/` |
| GraphQL (Strawberry) | Done | `graphql/` |

### In Progress / Next Up

| Feature | Priority | Notes |
|---------|----------|-------|
| Real-time WebSockets | Medium | Beyond hot-reload |
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

### Content Negotiation

```python
from django_matt.negotiation import (
    renders, render_as, content_negotiated, render, render_format,
    ContentNegotiationMiddleware
)

# Add middleware for automatic negotiation
MIDDLEWARE = [
    ...
    'django_matt.negotiation.ContentNegotiationMiddleware',
]

# Limit view to specific formats
@api.get("/users")
@renders("json", "xml", "csv")
async def list_users(request):
    return users  # Automatically rendered based on Accept header

# Force specific format
@api.get("/export")
@render_as("csv")
async def export_data(request):
    return data  # Always returns CSV

# Manual negotiation
@api.get("/data")
async def get_data(request):
    data = {"users": users}
    return render(request, data)  # Negotiates based on Accept header

# Request formats via:
# - Accept header: Accept: application/xml
# - Query param: /users?format=xml
# - URL suffix: /users.xml
```

### Billing / Subscriptions

```python
from django_matt.billing import get_provider, BillingController, WebhookController

# Register controllers
api.register_controller(BillingController, prefix="/billing")
api.register_controller(WebhookController, prefix="/billing/webhooks")

# Or use providers directly
provider = get_provider("stripe")  # or "paypal" or "polar"

# Create checkout session
checkout = await provider.create_checkout_session(
    price_id="price_xxx",
    success_url="https://example.com/success",
    cancel_url="https://example.com/cancel",
    customer_email="user@example.com",
)

# Manage subscriptions
subscription = await provider.get_subscription("sub_xxx")
await provider.cancel_subscription("sub_xxx", cancel_at_period_end=True)

# Create billing portal for customer self-service (Stripe/Polar)
portal_url = await provider.create_billing_portal_session(
    customer_id="cus_xxx",
    return_url="https://example.com/account",
)
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

### Admin Dashboard

```python
from django_matt.admin import (
    MattModelAdmin, register_admin,
    Dashboard, auto_dashboard, DashboardAdminSite,
    StatWidget, model_stat_widget, model_time_series_chart,
)

# Quick model admin registration
@register_admin(Product)
class ProductAdmin(MattModelAdmin):
    list_display = ["name", "price", "created_at"]
    search_fields = ["name"]

# Auto-generate dashboard from registered models
admin_site = DashboardAdminSite(name="myadmin")
admin_site.dashboard = auto_dashboard(site=admin_site)

# Or build custom dashboard
dashboard = Dashboard(title="Sales Dashboard")
dashboard.add_stat(model_stat_widget(Order, icon="shopping", color="success"))
dashboard.add_stat(model_stat_widget(User, icon="users", color="primary"))
dashboard.add_chart(model_time_series_chart(Order, date_field="created_at", days=30))
```

### Custom Admin Pages

```python
from django_matt.admin import pages, AdminPage

# Register custom admin page with decorator
@pages.register("reports/sales/", title="Sales Report", icon="chart")
def sales_report(request):
    data = get_sales_data()
    return pages.render(request, "sales", {"data": data})

# Or create page manually
report_page = AdminPage(
    title="Analytics",
    url_name="analytics",
    url_path="analytics/",
    permission="app.view_analytics",
)

@report_page.view
def analytics_view(request):
    return report_page.render(request, {"charts": get_charts()})
```

### GraphQL

```python
from django_matt.graphql import (
    GraphQLAPI, generate_schema, graphql_type, graphql_input,
    GraphQLView, create_type_from_model,
)

# Auto-generate schema from Django models
schema = generate_schema(
    models=[User, Post, Comment],
    auto_mutations=True,  # Generate CRUD mutations
    auto_subscriptions=False,  # Generate subscriptions
)

# Add GraphQL to your API
api = MattAPI()
graphql = GraphQLAPI(schema=schema, graphiql=True)
# Include in urls: path("graphql/", include(graphql.urls))

# Or manual type definition
@graphql_type
class UserType:
    id: int
    email: str
    username: str

    @staticmethod
    def from_orm(user):
        return UserType(id=user.id, email=user.email, username=user.username)

# Create types from Django models
PostType = create_type_from_model(Post, fields=["id", "title", "content"])

# Input types
@graphql_input
class CreateUserInput:
    email: str
    username: str
    password: str

# Using DataLoaders for N+1 prevention
from django_matt.graphql import DataLoaderRegistry

registry = DataLoaderRegistry()
registry.register_model(User, UserType)
registry.register_model(Post, PostType)

# In resolver
async def resolve_users(info):
    loader = info.context["dataloaders"].get_loader(User)
    users = await loader.load_many([1, 2, 3])
    return users

# TypeScript client generation
from django_matt.graphql import generate_typescript_client

generate_typescript_client(schema, output_path="frontend/src/graphql/client.ts")
```

### AI IDE Context Generation

```python
from django_matt.ai.context import (
    ContextGenerator,
    EnhancedIntrospector,
    ContextWatcher,
)

# Generate all context files (CLAUDE.md, .cursorrules, .copilot-instructions)
generator = ContextGenerator(output_dir=".")
files = generator.generate_all()

# Generate specific formats
generator.generate_claude_md()
generator.generate_cursorrules()
generator.generate_copilot_instructions()
generator.generate_json()  # Machine-readable introspection

# Use enhanced introspector directly
introspector = EnhancedIntrospector(include_examples=True)
info = introspector.introspect()

# Access detailed information
for endpoint in info.endpoints:
    print(f"{endpoint.method} {endpoint.path} - {endpoint.auth_requirement}")

for schema in info.schemas:
    print(f"{schema.name}: {[f.name for f in schema.fields]}")

# Watch mode for auto-updates during development
watcher = ContextWatcher(
    project_root=".",
    formats=["claude", "cursor", "copilot"],
    debounce_delay=1.0,
)
watcher.start()
# ... do development work ...
watcher.stop()

# Or use as context manager
with ContextWatcher() as watcher:
    # Files auto-regenerate on Python file changes
    pass
```

Add introspection endpoint to urls.py:
```python
from django_matt.ai.context.views import urlpatterns as ai_context_urls

urlpatterns = [
    ...
    path("", include(ai_context_urls)),  # Adds /_matt/introspection
]
```

Generate pre-commit hook:
```python
from django_matt.ai.context import generate_precommit_hook, install_precommit_hook

# View the hook script
print(generate_precommit_hook())

# Install automatically
install_precommit_hook(".")
```

### Feature Flags

```python
from django_matt.flags import feature_enabled, feature_flag, get_variant

# Check flag
if feature_enabled("new_checkout", user=request.user):
    return new_checkout_flow()

# Decorator
@feature_flag("beta_feature", default=False)
async def beta_endpoint(request):
    ...

# Require flag (404 if disabled)
@requires_flag("admin_tools")
async def admin_endpoint(request):
    ...

# Variants for A/B testing
variant = get_variant("checkout_experiment", user=request.user)
if variant == "control":
    return control_flow()
elif variant == "treatment_a":
    return treatment_flow()

# Using context
from django_matt.flags import FlagContext

ctx = FlagContext.from_request(request)
if ctx.is_enabled("feature"):
    ...

# Register API controller
from django_matt.flags import FlagController
api.register_controller(FlagController)

# Configuration (settings.py)
FEATURE_FLAG_BACKEND = "database"  # or "redis", "launchdarkly", "unleash"

MIDDLEWARE = [
    ...
    'django_matt.flags.FlagMiddleware',
    ...
]
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
