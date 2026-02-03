# Changelog

All notable changes to django-matt are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Core Framework
- `MattAPI` - Main API class with OpenAPI generation
- `APIRouter` - Modular routing with tags and prefixes
- `APIController` - Class-based controllers with dependency injection
- `CRUDController` - Pre-built CRUD operations
- `ModelSchema` - Automatic Pydantic schemas from Django models
- HTTP method decorators: `@get`, `@post`, `@put`, `@patch`, `@delete`

#### Authentication
- **JWT Authentication**
  - Access and refresh token support
  - Token rotation and blacklisting
  - `@jwt_required` and `@jwt_optional` decorators
  - `JWTAuthenticationMiddleware` for automatic token parsing
  - `AuthController` with login, register, refresh, logout endpoints

- **Session Authentication**
  - `@session_required` decorator
  - CSRF protection support
  - Session-based login/logout

- **API Key Authentication**
  - `APIKey` model for managing keys
  - `@api_key_required` decorator
  - Rate limiting per API key
  - Key rotation support

- **OAuth Providers**
  - `GoogleOAuthProvider` - Google OAuth 2.0
  - `GitHubOAuthProvider` - GitHub OAuth
  - `AppleOAuthProvider` - Sign in with Apple
  - `MicrosoftOAuthProvider` - Microsoft/Azure AD
  - `OAuthController` for OAuth flow management
  - `OAuthConnection` model for user-provider links

- **Passkeys/WebAuthn**
  - `PasskeyController` - Full registration and authentication
  - `PasskeyCredential` model for storing credentials
  - Platform authenticator support
  - Cross-platform authenticator support

- **Enterprise SSO**
  - `SAMLProvider` - SAML 2.0 support
  - `OIDCProvider` - OpenID Connect with PKCE
  - `SSOController` for SSO flow management
  - `SSOConnection` model for org-level configuration
  - Support for Okta, Azure AD, Google Workspace, Auth0, OneLogin

- **RBAC (Role-Based Access Control)**
  - `Role` and `Permission` models
  - Role hierarchy support
  - `HasRole` and `HasPermission` permission classes
  - `@requires_role()` and `@requires_permission()` decorators

#### Views & Permissions
- **CRUD Views**
  - `ListView` - List with pagination and filtering
  - `CreateView` - Create with validation
  - `ReadView` - Single item retrieval
  - `UpdateView` - Full update
  - `PatchView` - Partial update
  - `DeleteView` - Soft or hard delete
  - `APIViewSet` - Compose views into viewsets

- **Permission Classes**
  - `AllowAny` - No authentication required
  - `IsAuthenticated` - Require authenticated user
  - `IsAdmin` - Require admin user
  - `IsStaff` - Require staff user
  - `IsSuperUser` - Require superuser
  - `IsOwner` - Require object ownership
  - `HasRole` - Require specific role
  - `HasPermission` - Require specific permission

#### Multi-Tenancy
- `Organization` model with billing support
- `Team` model for sub-organization grouping
- `Membership` model with role-based access
- `Invitation` model for user invitations
- `TenantMiddleware` for automatic tenant context
- `OrganizationController` and `TeamController`
- `@requires_org_membership` decorator

#### Billing Integration
- **Stripe Provider**
  - Checkout sessions
  - Subscription management
  - Customer portal
  - Webhook handling
  - Invoice retrieval

- **PayPal Provider**
  - Subscription plans
  - Payment processing
  - Webhook handling

- **Polar Provider**
  - Modern billing API support
  - Subscription management

- **Models**
  - `BillingCustomer` - Customer records
  - `Subscription` - Active subscriptions
  - `Invoice` - Invoice history
  - `BillingProduct` - Product catalog
  - `BillingPrice` - Pricing tiers

#### Content Negotiation
- `ContentNegotiationMiddleware` for automatic format detection
- **Renderers**
  - `JSONRenderer` - JSON output
  - `XMLRenderer` - XML output
  - `CSVRenderer` - CSV export
  - `YAMLRenderer` - YAML output
  - `MessagePackRenderer` - Binary MessagePack
  - `HTMLRenderer` - HTML templates

- **Parsers**
  - `JSONParser` - JSON input
  - `XMLParser` - XML input
  - `YAMLParser` - YAML input
  - `MessagePackParser` - MessagePack input

- **Decorators**
  - `@renders()` - Limit supported formats
  - `@render_as()` - Force specific format
  - `@content_negotiated` - Full negotiation

#### WebSockets
- **Consumers**
  - `BaseConsumer` - Base WebSocket consumer
  - `JsonConsumer` - JSON message handling
  - `AuthenticatedConsumer` - With JWT/session auth
  - `RoomConsumer` - Room-based messaging

- **Authentication**
  - `JWTAuthMiddleware` - JWT token auth for WebSockets
  - `SessionAuthMiddleware` - Session auth for WebSockets
  - `AuthMiddlewareStack` - Combined auth stack

- **Utilities**
  - `broadcast()` - Send to channel groups
  - `send_to_user()` - Send to specific user
  - `PresenceManager` - Track online users
  - `WebSocketRouter` - URL routing for consumers

#### Type Generation
- **TypeScript**
  - Pydantic to TypeScript interfaces
  - Zod schema generation
  - API client generation
  - Enum generation

- **Swift**
  - Pydantic to Swift Codable structs
  - API client generation
  - Enum generation

- **CLI Command**
  - `python manage.py sync_types`
  - Watch mode for development
  - Multiple output formats

#### Performance
- **Fast Serialization**
  - `FastJSONRenderer` with orjson/ujson
  - `MessagePackRenderer` for binary
  - `StreamingJsonResponse` for large data

- **Caching**
  - `@cache_response()` decorator
  - `@cache_result()` for function results
  - `DistributedCacheManager` for Redis clusters
  - Cache stampede prevention

- **Query Optimization**
  - `QueryAnalyzer` for N+1 detection
  - `optimize_queryset()` helper
  - `PerformanceSuggester` for recommendations
  - `QueryLoggingMiddleware`

- **Benchmarking**
  - `APIBenchmark` class
  - `BenchmarkMiddleware`
  - Request timing and metrics

#### Pagination & Filtering
- **Pagination**
  - `PageNumberPagination`
  - `LimitOffsetPagination`
  - `CursorPagination`

- **Filtering**
  - `FilterSet` for declarative filters
  - `CharFilter`, `IntegerFilter`, `BooleanFilter`
  - `DateFilter`, `DateTimeFilter`
  - `InFilter` for list filtering
  - `SearchBackend` for text search
  - `PostgresSearchBackend` for full-text search
  - `OrderingBackend` for sorting

#### Dependency Injection
- `Container` for service registration
- `Singleton`, `Scoped`, `Transient` lifetimes
- `Depends()` for dependency declaration
- `@inject` decorator
- Built-in dependencies: `CurrentUser`, `CurrentRequest`, `CurrentOrg`
- `DependencyInjectionMiddleware`

#### Admin Integration
- `MattModelAdmin` - Auto-configured admin
- `MattStackedInline`, `MattTabularInline`
- `@register_admin()` decorator
- **Mixins**
  - `AuditAdminMixin`
  - `SoftDeleteAdminMixin`
  - `MultiTenantAdminMixin`
  - `ExportAdminMixin`

- **Dashboard**
  - `Dashboard` builder class
  - `StatWidget`, `ChartWidget`, `TableWidget`
  - `model_stat_widget()` helper
  - `auto_dashboard()` generator

- **Custom Pages**
  - `AdminPage` for custom pages
  - `AdminPageGroup` for grouping
  - `@pages.register()` decorator

#### Background Tasks
- `@task` decorator
- **Backends**
  - Celery integration
  - Dramatiq integration
  - Django-Q2 integration
  - Sync backend for testing

- **Scheduling**
  - Periodic task support
  - Cron-style scheduling

#### File Handling
- **Storage Backends**
  - Local filesystem
  - Amazon S3
  - Cloudflare R2
  - MinIO

- **Utilities**
  - `UploadedFile` type
  - `@file_upload` decorator
  - Image processing helpers

#### CLI Commands
- `python manage.py startapi` - Generate new API projects
- `python manage.py generate_crud` - Generate CRUD from models
- `python manage.py sync_types` - Generate TypeScript/Swift types
- `python manage.py config` - Configuration management

#### Hot Reload
- `HotReloadMiddleware` for development
- API-only reload (no full server restart)
- File watcher for Python files

#### Testing Utilities
- `APITestClient` - Sync test client
- `AsyncAPITestClient` - Async test client
- **Factories**
  - `UserFactory`
  - `OrganizationFactory`
  - `TeamFactory`
  - `MembershipFactory`

- **Assertions**
  - `assert_status()`
  - `assert_json_equal()`
  - `assert_created()`
  - `assert_not_found()`

#### Error Handling
- `APIError` base exception
- `NotFoundError` (404)
- `ValidationError` (400)
- `UnauthorizedError` (401)
- `ForbiddenError` (403)
- `ConflictError` (409)
- `RateLimitError` (429)
- Custom exception handlers

#### OpenAPI Documentation
- Automatic schema generation
- Swagger UI at `/docs`
- ReDoc at `/redoc`
- OpenAPI JSON at `/openapi.json`
- Tag-based organization
- Security scheme documentation

#### Interactive Documentation
- API playground at `/_matt/docs/playground/`
- Code snippet generation (curl, Python, JS, HTTPie)
- Request history
- Dark/light mode toggle
- Search functionality

### Changed
- Minimum Python version: 3.12+
- Minimum Django version: 5.2+
- Pydantic 2.0+ required
- Configured Ruff for linting and formatting

### Deprecated
- None

### Removed
- None

### Fixed
- None

### Security
- JWT tokens use HS256 by default with configurable algorithms
- CSRF protection for session authentication
- API key hashing for secure storage
- Rate limiting to prevent abuse

---

## [0.1.0] - TBD

Initial release.

### Added
- Core routing and decorators
- Class-based controllers
- Pydantic ModelSchema
- OpenAPI documentation
- JWT authentication
- Permission system
- RBAC with hierarchy

---

## Migration Notes

### Migrating from Django Ninja

See [Migration Guide: Django Ninja](migration/from-django-ninja.md)

Key changes:
- Replace `NinjaAPI` with `MattAPI`
- Replace `ninja_extra` decorators with `@api.get`, etc.
- Update schema `Config` classes to `Meta` classes
- Replace `ninja_jwt` with built-in `AuthController`

### Migrating from Django REST Framework

See [Migration Guide: DRF](migration/from-drf.md)

Key changes:
- Replace serializers with Pydantic schemas
- Replace `APIView` with `APIController`
- Replace `ModelViewSet` with `APIViewSet`
- Update authentication configuration
