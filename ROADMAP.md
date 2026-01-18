# Django Matt - Development Roadmap

> A complete standalone meta-framework replacing Django Ninja and its ecosystem.

⚠️ **Internal Tool** - This is currently a private/internal framework for personal development. Not yet published to PyPI.

## Overview

django-matt consolidates features from multiple packages into one cohesive library:

| Package | Feature | django-matt Module |
|---------|---------|-------------------|
| django-ninja | Core routing, OpenAPI | `django_matt.core` |
| django-ninja-extra | Class controllers, permissions, DI, throttling | `django_matt.core.controller` |
| django-ninja-jwt | JWT authentication | `django_matt.auth` |
| ninja-schema | ModelSchema for Django ORM | `django_matt.core.schema` |
| django-ninja-crud | Composable CRUD views | `django_matt.views` |
| (built-in) | Rate limiting & throttling | `django_matt.throttling` |
| (built-in) | API versioning | `django_matt.versioning` |
| (built-in) | Frontend codegen (React, Svelte, Solid) | `django_matt.codegen` |

## Tooling Standards (2026)

### Python
- **Minimum**: Python 3.11
- **Default**: Python 3.13
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (fast, Rust-based)
- **Linter/Formatter**: [Ruff](https://github.com/astral-sh/ruff) (replaces flake8, black, isort)
- **Type Checking**: pyright or mypy

### Frontend
- **Package Manager**: [Bun](https://bun.sh) (default), with npm/yarn/pnpm support
- **Runtime**: Bun or Node.js 20+

### Infrastructure
- **Containers**: Docker + Docker Compose
- **CI/CD**: GitHub Actions
- **Testing**: pytest + pytest-django + pytest-asyncio

---

## Stage 1: Core Framework (Replace Django Ninja) ✅

### Phase 1A: Core Enhancements

- [x] **1A.1** - OpenAPI schema generation + Swagger/ReDoc docs
- [x] **1A.2** - Enhanced ModelSchema with model_validator
- [x] **1A.3** - Composable CRUD views
- [x] **1A.4** - Permission classes and RBAC decorators

### Phase 1B: Authentication System

- [x] **1B.1** - JWT authentication backend
- [x] **1B.2** - Auth decorators and middleware
- [x] **1B.3** - RBAC with hierarchy support
- [x] **1B.4** - Magic link passwordless authentication
- [x] **1B.5** - Auth controllers (login, register, refresh, logout, me)
- [x] **1B.6** - Multi-tenant support (B2B)

---

## Stage 2: Developer Experience ✅

### Phase 2A: Type Synchronization

- [x] **2A.1** - TypeScript generator (interfaces, Zod schemas, API client)
- [x] **2A.2** - Swift generator (Codable structs, URLSession client)
- [x] **2A.3** - sync_types CLI command

### Phase 2B: CLI Tools

- [x] **2B.1** - Enhanced startapi command (templates, auth options, frontend)
- [x] **2B.2** - CRUD generator CLI

### Phase 2C: Testing Infrastructure

- [x] **2C.1** - Test utilities (APITestClient, factories, fixtures)

---

## Stage 3: Template Repositories ✅

- [x] **django-api-starter** - Minimal API with JWT, uv, Docker
- [x] **react-vite-starter** - Minimal React Vite with bun, TanStack Router
- [x] **django-api-b2b** - Organizations, teams, roles
- [x] **react-vite-b2b** - Org switcher, team management UI, TanStack Router
- [x] **fullstack-b2b** - Monorepo with Docker orchestration
- [x] **swift-ios-starter** - SwiftUI + generated API client (iOS 26)

---

## Stage 4: Advanced Features ✅

### Phase 4A: Authentication Providers

- [x] **4A.1** - OAuth providers (Google, GitHub, Apple, Microsoft)
- [x] **4A.2** - Enterprise SSO (SAML 2.0 and OIDC)
- [x] **4A.3** - Passkeys/WebAuthn support

### Phase 4B: Business Features

- [x] **4B.1** - Subscriptions/billing (Stripe, PayPal, Polar)
- [x] **4B.2** - Content negotiation (JSON, XML, CSV, YAML, MessagePack)
- [x] **4B.3** - Real-time WebSocket support

### Phase 4C: Performance

- [x] **4C.1** - Distributed caching with Redis
- [x] **4C.2** - Query optimization utilities (N+1 detection)
- [x] **4C.3** - Performance suggestion system

---

## Stage 5: Missing django-ninja-extra Features ✅

### Phase 5A: Throttling & Rate Limiting ✅
- [x] **5A.1** - Throttle classes
  - `AnonRateThrottle` - Rate limit anonymous users
  - `UserRateThrottle` - Rate limit authenticated users
  - `ScopedRateThrottle` - Different limits per endpoint
  - `BurstRateThrottle` - Short-term burst + sustained limits
- [x] **5A.2** - Throttle backends
  - In-memory (development)
  - Redis (production)
  - Django cache backend
  - Custom backend support
- [x] **5A.3** - Decorators and middleware
  - `@throttle(rate="100/hour")`
  - `@throttle_anon()` / `@throttle_user()`
  - `ThrottleMiddleware` - Global throttling
  - `PathSpecificThrottleMiddleware` - Path-based rates
  - `ThrottlesMixin` - For class-based views

### Phase 5B: API Versioning ✅
- [x] **5B.1** - Versioning schemes
  - `URLPathVersioning` - `/api/v1/`, `/api/v2/`
  - `HeaderVersioning` - `X-API-Version: 2`
  - `AcceptHeaderVersioning` - `Accept: application/json; version=2`
  - `QueryParameterVersioning` - `?version=1`
  - `HostNameVersioning` - `v1.api.example.com`
  - `NamespaceVersioning` - URL namespace-based
- [x] **5B.2** - Version routing
  - `VersioningMiddleware` - Automatic version detection
  - `VersionedRouter` - Version-specific endpoint groups
  - `VersionedAPI` - Multi-version API management
- [x] **5B.3** - Version decorators
  - `@version("1", "2")` - Specify supported versions
  - `@deprecated()` - Mark endpoints as deprecated
  - `@min_version()` / `@max_version()` - Version constraints
  - `VersionedMixin` - For class-based views

### Phase 5C: Pagination & Filtering ✅
- [x] **5C.1** - Pagination classes
  - `PageNumberPagination` - Standard page/page_size pagination
  - `LimitOffsetPagination` - Offset-based pagination
  - `CursorPagination` - Efficient cursor-based pagination for large datasets
- [x] **5C.2** - Filtering
  - `FilterSet` - Declarative filter definitions
  - `DjangoFilterBackend` - Query parameter filters with ORM lookups
  - Filter classes: `CharFilter`, `IntegerFilter`, `BooleanFilter`, `DateFilter`, etc.
  - `InFilter`, `RangeFilter`, `MultipleChoiceFilter` for complex queries
- [x] **5C.3** - Ordering/Sorting
  - `OrderingBackend` - `?ordering=created_at,-name`
  - `ordering_fields` configuration for allowed fields
  - Default ordering support
- [x] **5C.4** - Search
  - `SearchBackend` - Basic search with field prefixes (`^`, `=`, `@`)
  - `PostgresSearchBackend` - Full-text search with SearchVector/SearchRank
  - `ElasticsearchEngine` - Elasticsearch integration
  - `MeilisearchEngine` - Meilisearch integration

### Phase 5D: Dependency Injection ✅
- [x] **5D.1** - DI container
  - `Container` class with service registration
  - `Singleton`, `Scoped`, `Transient` lifetimes
  - Auto-injection in controllers via type hints
  - `@injectable`, `@inject`, `@provides` decorators
  - `Depends()` marker for explicit dependencies
  - Circular dependency detection
  - Factory function support
- [x] **5D.2** - Built-in dependencies
  - `CurrentRequest` - HTTP request access
  - `CurrentUser` - Authenticated user (with optional flag)
  - `CurrentOrg` / `CurrentTenant` - Multi-tenant organization
  - `DBSession` - Database connection
  - `Settings` - Django settings access
  - `Cache` - Cache backend access
  - `Logger` - Logging instance
  - `Query`, `Header`, `Path` - Request parameter extraction
- [x] **5D.3** - Middleware
  - `DependencyInjectionMiddleware` - Request scope management
  - `RequestScopeMiddleware` - Lightweight scope-only middleware
  - Async variants for both middleware

---

## Stage 6: Additional Features

### Phase 6A: File Handling ✅
- [x] **6A.1** - File uploads
  - `UploadedFile` class with streaming support
  - `MultipartParser` for manual parsing
  - `FileValidator` with size, type, and extension validation
  - Pre-built validators: `images()`, `documents()`, `videos()`, `audio()`
  - Async upload support throughout
- [x] **6A.2** - Storage backends
  - `LocalStorage` - Local filesystem with signed URL simulation
  - `S3Storage` - AWS S3 with full async support
  - `R2Storage` - Cloudflare R2
  - `MinIOStorage` - Self-hosted MinIO
  - `DOSpacesStorage` - DigitalOcean Spaces
  - Pre-signed upload/download URLs for all backends
  - `get_storage()` factory with settings-based configuration

### Phase 6B: Background Tasks ✅
- [x] **6B.1** - Task queue integration
  - `CeleryBackend` - Full Celery support with groups, chains, chords
  - `DramatiqBackend` - Dramatiq with Redis/RabbitMQ brokers
  - `DjangoQBackend` - Django-Q2 for database-backed queues
  - `SyncBackend` - Synchronous execution for development/testing
  - `get_backend()` factory with Django settings configuration
- [x] **6B.2** - Task decorators
  - `@task` - Register functions as background tasks
  - `@shared_task` - Register without explicit app binding
  - `@periodic_task` - Schedule tasks with crontab/interval
  - `@schedule` - Decorator for scheduling configuration
- [x] **6B.3** - Retry policies
  - `RetryPolicy` base class
  - `ExponentialBackoff` - Exponential delay increase
  - `LinearBackoff` - Linear delay increase
  - `FixedDelay` - Constant retry delay
  - Configurable max retries, exceptions, jitter
- [x] **6B.4** - Task primitives
  - `Signature` - Callable task representation
  - `group()` - Execute tasks in parallel
  - `chain()` - Execute tasks sequentially (with result piping)
  - `chord()` - Group + callback pattern
  - `GroupResult` for aggregating results
- [x] **6B.5** - Scheduling
  - `crontab()` - Cron-style scheduling
  - `every()` - Interval-based scheduling (seconds, minutes, hours, days)
  - `Scheduler` class for managing periodic tasks

### Phase 6C: Audit & Logging
- [x] **6C.1** - Audit logging ✅
  - `AuditLog` model with generic foreign key for any object
  - `AuditableMixin` for automatic model change tracking (create, update, delete)
  - `AuditableWithUserMixin` with created_by/updated_by fields
  - `AuditMiddleware` for request context capture (IP, User-Agent)
  - `@log_action` and `@audit_action` decorators for view logging
  - `AuditLogContext` context manager for grouping operations
  - Signals: `pre_audit`, `post_audit` for custom hooks
  - Query utilities: `get_audit_history()`, `get_user_actions()`, `get_model_changes()`
  - Security: `get_security_events()`, `get_failed_logins_by_ip()`
  - Export: `export_audit_logs()` (JSON/CSV format)
  - Cleanup: `cleanup_old_logs()` for log rotation
- [x] **6C.2** - Soft delete ✅
  - `SoftDeleteMixin` for models with `deleted_at` field
  - `SoftDeleteWithUserMixin` for tracking who deleted records
  - `SoftDeleteManager` with auto-filtering (excludes deleted by default)
  - `SoftDeleteQuerySet` for chainable operations (`delete()`, `hard_delete()`, `restore()`)
  - `with_deleted()` and `deleted_only()` query methods
  - Cascade soft delete/restore utilities
  - Async support (`adelete`, `arestore`, `ahard_delete`)

### Phase 6D: Additional Auth
- [x] **6D.1** - API Key authentication ✅
  - `APIKey` model with live/test keys (like Stripe's `sk_live_` / `sk_test_`)
  - `APIKeyUsage` model for hourly usage tracking and analytics
  - Key generation, rotation, and secure hashing
  - Scoped permissions (`requires_scope("write:posts")`)
  - Plan-based rate limiting (free/starter/pro/enterprise tiers)
  - IP allowlisting per key
  - Decorators: `@api_key_required`, `@api_key_optional`, `@requires_scope`, `@requires_live_key`, `@requires_plan`
  - Middleware: `APIKeyAuthenticationMiddleware`, `APIKeyRateLimitMiddleware`, `APIKeyUsageTrackingMiddleware`
  - `APIKeyController` - Full CRUD, rotation, usage analytics, data export
- [x] **6D.2** - Session authentication ✅
  - `SessionConfig` with cookie and CSRF settings
  - `SessionStore` enhanced backend with user tracking, activity timestamps
  - `SessionAuthMiddleware` / `AsyncSessionAuthMiddleware` for authentication
  - `CSRFMiddleware` / `AsyncCSRFMiddleware` with token validation
  - CSRF utilities: `get_csrf_token()`, `verify_csrf_token()`, `rotate_csrf_token()`
  - Decorators: `@session_required`, `@login_required`, `@fresh_session_required`
  - `@csrf_exempt`, `@csrf_protect`, `@ensure_csrf_cookie`
  - Session utils: `login_session()`, `logout_session()`, `flash_message()`
  - `SessionController` - Full REST API for session management
  - Multi-session support: `get_user_sessions()`, `delete_other_sessions()`

---

## Stage 7: Future Compatibility ✅

### Phase 7A: Django 6.0 Support ✅
- [x] **7A.1** - Django 6.0 compatibility testing
  - Updated pyproject.toml for Django 5.2 and 6.0 support
  - Note: Django 6.0 requires Python 3.12+ (drops 3.10, 3.11)
  - Django 6.0 includes built-in background tasks framework
- [x] **7A.2** - Update deprecated APIs
  - Code compatible with both Django 5.2 and 6.0
- [x] **7A.3** - CI/CD matrix testing (Django 5.2, 6.0)
  - GitHub Actions tests Django 5.2 (Python 3.11-3.13)
  - GitHub Actions tests Django 6.0 (Python 3.12-3.13)

### Phase 7B: Python Version Support ✅
- [x] **7B.1** - Python 3.11 minimum support
  - `requires-python = ">=3.11"` for Django 5.2 compatibility
- [x] **7B.2** - Python 3.13 as default
  - CI/CD uses Python 3.13 for lint/typecheck/docs
- [x] **7B.3** - Python 3.14 readiness
  - Classifiers and CI matrix prepared for 3.14

### Phase 7C: Modern Tooling ✅
- [x] **7C.1** - uv package manager (all templates)
  - CI/CD uses uv for all operations
  - Documentation recommends uv
- [x] **7C.2** - Ruff linter/formatter
  - Comprehensive Ruff configuration in pyproject.toml
  - Replaces black, isort, flake8
  - Security rules (bandit), performance rules enabled
- [x] **7C.3** - Full type annotations (pyright strict)
  - Pyright configuration in pyproject.toml
  - MyPy configuration with django-stubs
  - Type checking in CI pipeline

### Phase 7D: Documentation (Internal) ✅
- [x] **7D.1** - MkDocs setup
  - mkdocs.yml with Material theme
  - Full navigation structure
  - mkdocstrings for API reference
- [x] **7D.2** - Core documentation
  - Installation, quickstart, configuration guides
  - Contributing guidelines
  - Changelog
- [ ] **7D.3** - API reference (in progress)
  - Structure defined, content to be generated

### Phase 7E: CI/CD ✅
- [x] **7E.1** - GitHub Actions pipelines
  - ci.yml: lint, typecheck, test (matrix), security, docs, build
  - release.yml: build, GitHub release, PyPI publish (ready)
- [x] **7E.2** - Template repository workflows
  - uv-based workflows for templates
- [x] **7E.3** - Security scanning
  - Ruff security rules (bandit integration)
  - Dependency vulnerability scanning (uv pip audit)

---

## Stage 8: Dependency Reduction ✅

> Goal: Minimize external dependencies to reduce version conflicts, security surface, and maintenance burden.

### Phase 8A: Replace PyJWT ✅
- [x] **8A.1** - Built-in JWT implementation
  - HMAC signing (HS256, HS384, HS512) using `hmac` stdlib
  - Base64url encoding/decoding
  - Claims validation (exp, nbf, iat, iss, aud)
  - Token parsing and verification
  - `jwt_builtin.py` - complete implementation
- [x] **8A.2** - RSA/EC support (optional `cryptography` dep)
  - RS256, RS384, RS512
  - ES256, ES384, ES512 (used by Apple Sign In)
  - Public key verification
  - Install with `pip install 'django-matt[jwt-asymmetric]'`

### Phase 8B: Replace passlib/argon2-cffi ✅
- [x] **8B.1** - Use Django's built-in password hashers
  - Django already supports Argon2, bcrypt, PBKDF2
  - Wrapper around `make_password()` / `check_password()`
  - Password strength validation and generation
  - `passwords.py` - complete implementation
- [x] **8B.2** - Remove passlib and argon2-cffi dependencies
  - `auth = []` - no external deps needed for basic auth
  - Django hashers handle all password operations

### Phase 8C: Universal Frontend Codegen Engine ✅

> Replace Jinja2 with a powerful multi-framework code generation system.
> Generate full components, not just types.

#### 8C.1 - Core Codegen Infrastructure ✅
- [x] **8C.1.1** - AST-based code generation primitives
  - `codegen/core.py` - Language-agnostic intermediate representation
  - Pretty printing with configurable formatting (indent levels)
  - Import management and deduplication in `CodeFile`
- [x] **8C.1.2** - Model introspection system
  - `codegen/introspection.py` - Extract fields, types, relationships from Django models
  - Map Django fields to TypeScript and Python types
  - Handle validators, choices, and constraints
- [x] **8C.1.3** - Template registry and plugin system
  - Register generators per framework via `CodeGenerator` base class
  - Framework-specific generators: React, Svelte, SolidJS
  - Customizable output through generator options

#### 8C.2 - React Generator (Primary) ✅
- [x] **8C.2.1** - TypeScript types and Zod schemas
  - `codegen/typescript.py` - Interfaces from Django models
  - Zod validation schemas with field constraints
  - Create/Update input types
- [x] **8C.2.2** - React Query / TanStack Query hooks
  - `codegen/react.py` - `useUsers()`, `useUser(id)`, `useCreateUser()`
  - Query invalidation on mutations
  - Proper error handling
- [x] **8C.2.3** - Form components (shadcn/ui default)
  - `<UserForm />` with react-hook-form + zod validation
  - Field components based on model field types
  - Full shadcn/ui integration
- [x] **8C.2.4** - List/Table components
  - `<UserList />` with search, pagination
  - DataTable integration with sorting
  - Delete confirmation flow
- [x] **8C.2.5** - Detail/Show components
  - `<UserDetail />` display component
  - Loading and error states

#### 8C.3 - Svelte Generator (Secondary) ✅
- [x] **8C.3.1** - TypeScript types
  - Same type generation as React
- [x] **8C.3.2** - Svelte stores and queries
  - `codegen/svelte.py` - Writable/derived stores for state
  - CRUD operations with error handling
- [x] **8C.3.3** - Svelte components
  - `UserForm.svelte` with two-way binding
  - `UserList.svelte` with search/pagination
  - `UserDetail.svelte` with loading states
- [x] **8C.3.4** - Svelte 5 runes support
  - `generate_svelte5_stores()` with `$state`, `$derived`
  - Modern Svelte patterns via `svelte_version` option

#### 8C.4 - SolidJS Generator (Tertiary) ✅
- [x] **8C.4.1** - TypeScript types
  - Same type generation
- [x] **8C.4.2** - Solid primitives
  - `codegen/solid.py` - `createSignal`, `createResource`
  - `createStore` with produce for immutable updates
- [x] **8C.4.3** - Solid components
  - `UserForm.tsx` (Solid JSX)
  - `UserList.tsx` with For/Show
  - `UserDetail.tsx`

#### 8C.5 - CLI and Integration (Basic)
- [x] **8C.5.1** - Generator classes ready for CLI
  - `ReactGenerator`, `SvelteGenerator`, `SolidGenerator`
  - `TypeScriptGenerator` for types-only output
  - All with `generate_all()` returning file dict
- [ ] **8C.5.2** - Watch mode for development (future)
  - Auto-regenerate on model changes
  - HMR-friendly output
- [ ] **8C.5.3** - Config file support (future)
  ```python
  # django_matt_codegen.py
  CODEGEN = {
      "framework": "react",
      "ui_library": "shadcn",  # or "tailwind", "headless", "none"
      "output_dir": "./frontend/src/generated",
      "models": ["users.User", "posts.Post"],
  }
  ```

#### Generated Output Example (React + shadcn)

```tsx
// generated/users/types.ts
export interface User {
  id: number
  email: string
  firstName: string
  lastName: string
  createdAt: string
}

export const userSchema = z.object({
  email: z.string().email(),
  firstName: z.string().min(1),
  lastName: z.string().min(1),
})

// generated/users/hooks.ts
export function useUsers(params?: UserListParams) {
  return useQuery({
    queryKey: ['users', params],
    queryFn: () => api.users.list(params),
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.users.create,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })
}

// generated/users/components/UserForm.tsx
export function UserForm({ onSuccess }: UserFormProps) {
  const form = useForm<UserInput>({ resolver: zodResolver(userSchema) })
  const createUser = useCreateUser()

  return (
    <Form {...form}>
      <FormField name="email" render={...} />
      <FormField name="firstName" render={...} />
      <FormField name="lastName" render={...} />
      <Button type="submit" disabled={createUser.isPending}>
        {createUser.isPending ? 'Creating...' : 'Create User'}
      </Button>
    </Form>
  )
}
```

### Phase 8D: Replace factory-boy ✅
- [x] **8D.1** - Built-in model factory system
  - `ModelFactory` base class in `testing/model_factory.py`
  - `Field`, `LazyAttribute`, `Sequence` definitions
  - `SubFactory` for related models
  - `PostGeneration` hooks
  - Field auto-generation based on Django model field types
- [x] **8D.2** - Built-in data generators (replace Faker)
  - `DataGenerator` class in `testing/generators.py`
  - Names, emails, usernames, passwords
  - Addresses, cities, states, countries
  - Phone numbers, credit cards (fake)
  - Dates, times, timestamps
  - Lorem ipsum text, sentences, paragraphs
  - UUIDs, colors, file names, MIME types
  - All with deterministic seeding support

### Phase 8E: Replace python-multipart ✅
- [x] **8E.1** - Built-in multipart form parser
  - Already implemented in `files/upload.py`
  - `MultipartParser` class with streaming support
  - File upload handling with validation
  - Memory-efficient large file support
  - Content-Type and boundary handling

### Dependency Analysis

| Dependency | Replacement | Status |
|------------|-------------|--------|
| PyJWT | `jwt_builtin.py` (HMAC + RSA/EC) | ✅ Done |
| passlib | `passwords.py` (Django hashers) | ✅ Done |
| argon2-cffi | `passwords.py` (Django hashers) | ✅ Done |
| jinja2 | `codegen/` (AST-based generators) | ✅ Done |
| factory-boy | `model_factory.py` | ✅ Done |
| faker | `generators.py` | ✅ Done |
| python-multipart | `files/upload.py` (already built) | ✅ Done |

### Dependencies to Keep (Too Complex/Specialized)

| Dependency | Reason |
|------------|--------|
| django | Foundation framework |
| pydantic | Schema validation - too complex to replicate |
| orjson | C-optimized JSON - performance critical |
| authlib | OAuth complexity - many provider specs |
| webauthn | Passkeys/FIDO2 spec is very complex |
| redis | Redis protocol client |
| boto3 | AWS SDK - massive surface area |
| celery | Task queue - mature ecosystem |
| pytest | Testing framework standard |

---

## Dependencies

### Current Dependencies (After Stage 8)
```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "django>=5.2",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
# Performance optimizations
performance = ["orjson>=3.10.0", "ujson>=5.10.0", "msgpack>=1.0.8", "redis>=5.0.0"]

# Authentication - built-in JWT, uses Django password hashers
# No external dependencies needed for basic auth!
auth = []

# JWT with RSA/EC algorithms (ES256 for Apple, RS256 for others)
jwt-asymmetric = ["cryptography>=42.0.0"]

# OAuth providers
oauth = ["authlib>=1.3.0"]

# Passkeys/WebAuthn
passkeys = ["webauthn>=2.1.0"]

# Type generation - built-in codegen engine, no external deps
typegen = []

# File handling (S3, etc.) - built-in multipart parser
files = ["boto3>=1.34.0"]

# Background tasks
tasks = ["celery>=5.4.0", "dramatiq[redis]>=1.17.0", "django-q2>=1.6.0"]

# Billing providers
billing = ["stripe>=10.0.0"]

# Testing utilities - built-in factories and data generators
testing = ["pytest>=8.0.0", "pytest-django>=4.8.0", "pytest-asyncio>=0.24.0", "httpx>=0.27.0"]
all = ["django-matt[full,auth,oauth,passkeys,typegen,testing,files,tasks]"]
```

### Target Dependencies (After Stage 8)
```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "django>=5.2",           # Foundation
    "pydantic>=2.0.0",       # Schema validation
]

[project.optional-dependencies]
# Performance - keep these (C extensions, can't replicate)
performance = ["orjson>=3.9.0", "uvicorn>=0.30.0"]

# Auth - no external deps needed! (built-in JWT + Django hashers)
# auth = []  # Built-in!

# OAuth - keep (complex multi-provider specs)
oauth = ["authlib>=1.3.0"]

# Passkeys - keep (FIDO2/WebAuthn spec is complex)
passkeys = ["webauthn>=2.1.0"]

# Type generation - no external deps needed!
# typegen = []  # Built-in!

# Testing - only pytest ecosystem
testing = ["pytest>=8.0.0", "pytest-django>=4.8.0", "pytest-asyncio>=0.24.0", "httpx>=0.27.0"]
# factory-boy and faker replaced with built-in!

# Cloud storage - keep (AWS SDK)
files = ["boto3>=1.34.0"]
# python-multipart replaced with built-in!

# Background tasks - keep (task queue ecosystem)
tasks = ["celery>=5.4.0", "redis>=5.0.0"]

# RSA/EC JWT signing (optional, only if needed)
jwt-asymmetric = ["cryptography>=42.0.0"]
```

### Dependency Reduction Summary

| Category | Before | After | Removed |
|----------|--------|-------|---------|
| Core | 3 | 2 | typing-extensions (use Python 3.11+) |
| Auth | 3 | 0 | PyJWT, passlib, argon2-cffi |
| Typegen | 1 | 0 | jinja2 |
| Testing | 5 | 4 | factory-boy, faker |
| Files | 2 | 1 | python-multipart |
| **Total Optional** | **14** | **5** | **9 deps removed** |

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "ASYNC"]

[tool.uv]
python = "3.13"
```

---

## Stage 9: Deployment & DevOps

> Goal: Easy deployment to popular cloud platforms with minimal configuration.

### Phase 9A: Deployment CLI
- [ ] **9A.1** - `deploy` management command
  - Platform detection and configuration
  - Environment variable management
  - Database migration handling
  - Static file collection
- [ ] **9A.2** - Dockerfile generation
  - Production-optimized Dockerfile
  - Multi-stage builds
  - Health check endpoints
- [ ] **9A.3** - Docker Compose templates
  - Development compose file
  - Production compose with Nginx/Traefik

### Phase 9B: Platform Providers
- [ ] **9B.1** - Fly.io support
  - `fly.toml` generation
  - `python manage.py deploy --platform fly`
  - Automatic secrets management
  - PostgreSQL provisioning
- [ ] **9B.2** - Railway support
  - `railway.json` generation
  - Environment sync
  - Database provisioning
- [ ] **9B.3** - Render support
  - `render.yaml` generation
  - Blueprint templates
  - Managed PostgreSQL setup
- [ ] **9B.4** - Digital Ocean App Platform
  - `.do/app.yaml` generation
  - Droplet deployment scripts
  - Managed database integration
- [ ] **9B.5** - AWS support
  - ECS Fargate deployment
  - Lambda + API Gateway (serverless)
  - RDS PostgreSQL setup
  - CloudFormation/CDK templates
- [ ] **9B.6** - PlanetScale support
  - Connection configuration
  - Branch-based workflows
  - Migration handling for serverless MySQL
- [ ] **9B.7** - Hetzner support
  - Hetzner Cloud server provisioning
  - `hcloud` CLI integration
  - Floating IP configuration
  - Hetzner managed PostgreSQL
  - Cost-effective EU hosting option

### Phase 9C: Self-Hosted Options
- [ ] **9C.1** - VPS deployment scripts
  - Ubuntu/Debian setup scripts
  - Nginx + Gunicorn/Uvicorn configuration
  - SSL via Let's Encrypt (certbot)
  - Systemd service files
- [ ] **9C.2** - Docker self-hosted
  - `docker-compose.prod.yml` with Traefik
  - Automatic SSL with Traefik
  - Redis + PostgreSQL containers
  - Backup scripts
- [ ] **9C.3** - Kubernetes self-hosted
  - Helm chart generation
  - K3s lightweight cluster support
  - Ingress configuration
  - Horizontal pod autoscaling

### Phase 9D: Multi-Environment Configuration
- [ ] **9D.1** - Environment structure
  - `config/environments/development.py`
  - `config/environments/production.py`
  - `config/environments/staging.py` (optional)
  - `config/environments/base.py` (shared settings)
- [ ] **9D.2** - Environment CLI
  - `python manage.py config init --environments dev,staging,prod`
  - `python manage.py config switch staging`
  - Auto-detect environment from `DJANGO_ENV` variable
- [ ] **9D.3** - Environment-specific features
  - Debug toolbar (dev only)
  - Sentry/error tracking (staging/prod)
  - Database connection pooling (prod)
  - Cache backends per environment
  - Logging levels per environment
- [ ] **9D.4** - Environment templates
  - `.env.development.example`
  - `.env.staging.example`
  - `.env.production.example`
  - Validation of required vars per environment

### Phase 9E: Production Utilities
- [ ] **9E.1** - Health check endpoints
  - `/health` - Basic liveness check
  - `/health/ready` - Readiness with DB/cache checks
  - `/health/live` - Kubernetes liveness probe
- [ ] **9E.2** - Environment management
  - Secrets loading from platform vaults
  - Environment validation on startup
  - Missing config warnings

---

## Stage 10: Machine Learning & AI

> Goal: First-class ML/AI support for modern Django applications.

### Phase 10A: ML Utilities ✅
- [x] **10A.1** - Embedding utilities
  - `EmbeddingProvider` base class with async support
  - `CachedEmbeddings` - caching layer for any provider
  - `BatchEmbeddings` - efficient bulk embedding with concurrency
  - Similarity functions: `cosine_similarity`, `euclidean_distance`, `dot_product`
- [x] **10A.2** - Vector storage integration
  - `VectorStore` unified interface
  - `InMemoryVectorStore` - development/testing
  - `PgVectorStore` - PostgreSQL with pgvector extension
  - `PineconeVectorStore` - Pinecone cloud integration
  - `QdrantVectorStore` - Qdrant vector DB integration
- [x] **10A.3** - Embedding providers
  - `OpenAIEmbeddings` - text-embedding-3-small/large, ada-002
  - `GeminiEmbeddings` - text-embedding-004
  - `OllamaEmbeddings` - nomic-embed-text, mxbai-embed-large

### Phase 10B: LLM Integration (Cloud Providers) ✅
- [x] **10B.1** - LLM client utilities
  - `LLMProvider` base class with unified interface
  - `OpenAIProvider` - GPT-4o, GPT-4, GPT-3.5-turbo
  - `AnthropicProvider` - Claude 3.5 Sonnet, Claude 3 Opus/Haiku
  - `GeminiProvider` - Gemini 1.5 Pro/Flash
  - `get_provider(name)` factory function
- [x] **10B.2** - RAG (Retrieval Augmented Generation)
  - Text splitters: `CharacterSplitter`, `RecursiveSplitter`, `SentenceSplitter`
  - `ConversationMemory` - window-based history
  - `SummaryMemory` - LLM-summarized history
  - `RAGChain` - standard RAG pipeline
  - `MultiQueryRAG` - query expansion for better retrieval
- [x] **10B.3** - Structured output
  - `StructuredOutputProvider` mixin
  - `complete_structured()` with Pydantic models
  - JSON mode helpers for all providers
  - Validation and retry logic

### Phase 10C: Self-Hosted LLMs ✅
- [x] **10C.1** - Ollama integration
  - `OllamaProvider` - full chat completion support
  - Model management: `list_models()`, `pull_model()`, `delete_model()`
  - Streaming responses with async iterators
  - `OllamaEmbeddings` for local embeddings
  - JSON mode for structured output
- [ ] **10C.2** - vLLM integration (future)
  - vLLM server client
  - OpenAI-compatible API support
- [ ] **10C.3** - llama.cpp integration (future)
  - Direct llama-cpp-python bindings
- [ ] **10C.4** - LocalAI integration (future)
  - LocalAI client wrapper

### Phase 10D: AI IDE Integration ✅
- [x] **10D.1** - Context file generation
  - `ClaudeMdGenerator` - auto-generates `CLAUDE.md`
  - `CursorRulesGenerator` - auto-generates `.cursorrules`
  - `ProjectIntrospector` - extracts models, views, URLs
  - Project structure tree generation
- [x] **10D.2** - Management command
  - `python manage.py generate_ai_context`
  - Options: `--output`, `--format`, `--dry-run`
  - Supports: claude, cursor, or all formats

---

## Stage 11: Frontend Integrations

> Goal: Seamless integration with modern frontend frameworks.

### Phase 11A: HTMX Integration ✅
- [x] **11A.1** - HTMX view helpers
  - `@htmx_view` decorator with automatic template switching
  - `@htmx_partial`, `@htmx_only` decorators
  - Out-of-band swaps via `oob_swap()`, `OobBuilder`
- [x] **11A.2** - HTMX response utilities
  - `HtmxResponse` with chainable `trigger()`, `push_url()`, `retarget()`
  - `HtmxTemplateResponse` for template rendering
  - `HtmxRedirectResponse`, `HtmxRefreshResponse`, `StopPolling`
- [x] **11A.3** - Component library
  - `InfiniteScrollConfig` + `render_infinite_scroll_page()`
  - `SearchConfig` + `render_search_results()` with debounce
  - `ModalConfig` + `open_modal()`, `close_modal()`
  - `ToastConfig` + `show_toast()`, `add_toast_oob()`
- [x] **11A.4** - Template tags and middleware
  - `{% htmx_script %}`, `{% htmx_attrs %}`, `{% htmx_csrf %}`
  - `HtmxMiddleware` adds `request.htmx` attribute
  - `htmx_context_processor` for templates

### Phase 11B: Django Matt Pages (Server-Driven SPA) ✅

> A modern alternative to Inertia.js with end-to-end type safety.
> See [full design document](docs/design/pages-system.md).

- [x] **11B.1** - Core page system
  - `PageResponse` class with script tag injection (not data attributes)
  - `@page` decorator for simple page views
  - `PageMiddleware` for request mode detection
  - Asset versioning with manifest support
- [x] **11B.2** - Hybrid API/Page mode
  - Same endpoint serves JSON API or page response
  - Content negotiation integration
  - `X-Page` header for SPA navigation
  - Mobile apps can use same views as JSON API
- [x] **11B.3** - Type safety integration
  - Props schemas with Pydantic
  - Codegen generates TypeScript props interfaces
  - Zod schemas for client-side validation
  - Zero manual type maintenance
- [x] **11B.4** - Client adapters
  - `@django-matt/react` - React adapter with hooks
  - `@django-matt/svelte` - Svelte adapter with stores
  - `@django-matt/solid` - SolidJS adapter with resources
  - Link component, navigation, shared data
- [x] **11B.5** - Advanced features
  - Streaming SSR (React 19 `renderToReadableStream`) - architecture ready
  - Schema-driven form handling (PageForm with Pydantic)
  - WebSocket live updates integration - architecture ready
  - Progressive enhancement (no-JS fallback)
  - Error boundaries and error pages

**Key improvements over Inertia.js:**
| Feature | Inertia.js | django_matt.pages |
|---------|------------|-------------------|
| Props delivery | `data-page` attr (slow) | `<script>` tag (fast) |
| Type safety | Manual | Auto-generated |
| Hybrid API | No | Yes |
| Streaming SSR | No | Yes |
| Codegen integration | No | Yes |

### Phase 11C: Livewire-style Reactivity ✅
- [x] **11C.1** - Reactive components
  - `LiveComponent` base class with reactive state
  - `ValidatedComponent` for forms with validation
  - `@action`, `@computed`, `@watch` decorators
  - Lifecycle hooks: `@on_mount`, `@on_hydrate`, `@on_dehydrate`
  - Component registry for name-based lookup
- [x] **11C.2** - State management
  - `Snapshot` serialization with signed tokens
  - `State` class with dirty tracking and diffing
  - `StateManager` with memory/cache/database backends
- [x] **11C.3** - Real-time updates
  - `LivewireConsumer` for Django Channels WebSocket
  - Connection manager for component subscriptions
  - `broadcast_to()`, `broadcast_to_user()`, `broadcast_to_all()`
- [x] **11C.4** - Client-side JavaScript
  - `livewire.js` - handles wire: attribute bindings
  - `wire:click`, `wire:submit`, `wire:model` support
  - Debounced model updates, optimistic UI
  - WebSocket mode for real-time updates
- [x] **11C.5** - Template tags
  - `{% livewire "component-name" prop=value %}`
  - `{% livewire_scripts %}`, `{% livewire_styles %}`
  - `{% wire_click %}`, `{% wire_model %}`, `{% wire_submit %}`

---

## Stage 12: Backend-Served Component System ✅

> Goal: Serve UI components from the backend that render in any frontend framework, with built-in validation, theming, and customization. Inspired by FastUI, but framework-agnostic.

### Phase 12A: Component Definition System ✅
- [x] **12A.1** - Component schema DSL
  - Pydantic models for component definitions
  - Props, slots, events, validation rules
  - JSON-serializable component trees
  ```python
  from django_matt.components import Form, TextField, EmailField, SubmitButton

  login_form = Form(
      id="login",
      fields=[
          EmailField(name="email", label="Email", required=True),
          TextField(name="password", type="password", label="Password", required=True),
      ],
      submit=SubmitButton(label="Sign In"),
      action="/api/auth/login",
  )
  ```
- [x] **12A.2** - Component registry
  - Register custom components
  - Extend built-in components
  - Component versioning
- [x] **12A.3** - Validation integration
  - Pydantic validation rules → frontend validation
  - Server-side validation feedback
  - ValidationRule class for form fields

### Phase 12B: Pre-built Component Library ✅
- [x] **12B.1** - Authentication components
  - `LoginForm` - Email/password with OAuth, magic link, passkeys support
  - `RegisterForm` - Registration with password strength indicator
  - `OAuthButtons` - Social login buttons (Google, GitHub, Apple, etc.)
- [x] **12B.2** - CRUD components
  - `DataTable` - Sortable, filterable, paginated table with actions
  - `DetailView` - Model detail display with fields
  - `Form` - Generic form with auto-generated fields
  - `SearchInput` - Debounced search with suggestions
- [x] **12B.3** - Layout components
  - `Modal` / `Drawer` - Overlay dialogs
  - `Tabs` / `Accordion` - Content organization
  - `Card` / `Container` - Content containers
  - `Alert` / `Toast` - Notifications
  - `Pagination` - Page navigation
  - `Nav` / `NavItem` - Navigation menus
- [x] **12B.4** - Input components
  - `TextField`, `NumberField`, `EmailField`, `PasswordField`
  - `Select`, `MultiSelect`
  - `Checkbox`, `RadioGroup`, `Switch`
  - `DatePicker`
  - `FileUpload`
  - `Textarea`

### Phase 12C: Theming & Design System Integration ✅
- [x] **12C.1** - Theme configuration
  - CSS variables / design tokens (SemanticColors, DarkColors)
  - Color schemes (light/dark mode)
  - Typography (FontFamily, FontSize, LineHeight, FontWeight)
  - Spacing, BorderRadius, Shadow, Breakpoints, ZIndex
  - Animation configuration
  ```python
  theme = Theme(
      name="blue",
      colors=SemanticColors(
          primary="hsl(221.2 83.2% 53.3%)",
          secondary="hsl(210 40% 96.1%)",
      ),
  )
  ```
- [x] **12C.2** - Design system adapters
  - shadcn/ui compatible theme (default)
  - Theme presets: zinc, blue, green, violet
  - `to_css_variables()` for CSS output
  - `to_tailwind_config()` for Tailwind integration
- [x] **12C.3** - Custom styling
  - `class_name` overrides per component
  - `style` prop for inline styles
  - `with_class()` and `with_style()` builder methods

### Phase 12D: Framework Renderers ✅
- [x] **12D.1** - JSON renderer
  - Component tree → JSON for API responses
  - PrettyJSONRenderer and CompactJSONRenderer variants
- [x] **12D.2** - React renderer
  - `ReactRenderer` - JSON props for React consumption
  - `ReactHtmlRenderer` - HTML with embedded props for SSR
  - shadcn/ui component mapping
- [x] **12D.3** - HTML renderer
  - Pure HTML output for SSR, email, print
  - Tailwind CSS classes by default
  - Full component coverage (forms, layout, data)
- [ ] **12D.4** - Vue renderer (future)
  - Component tree → Vue SFCs
- [ ] **12D.5** - Svelte renderer (future)
  - Component tree → Svelte components

### Phase 12E: Component Serving & API ✅
- [x] **12E.1** - Response classes
  - `ComponentResponse` - Generic component response
  - `JsonComponentResponse` - JSON serialized components
  - `HtmlComponentResponse` - HTML rendered components
- [x] **12E.2** - View decorators
  - `@component_view()` - Render component return values
  - `@json_component_view` - Return components as JSON
  - `@html_component_view()` - Return components as HTML
- [x] **12E.3** - Class-based views
  - `ComponentView` - Base CBV for components
  - `JsonComponentView` - JSON component CBV
  - `HtmlComponentView` - HTML component CBV
- [x] **12E.4** - Page builder
  - `Page` class for multi-component pages
  - `add()` for components, `add_script()`, `add_style()`
  - `render()` and `to_dict()` methods
- [x] **12E.5** - Component factories
  - `create_component(type, **props)` - Create by type name
  - `create_from_dict(data)` - Create from dictionary
  - `create_from_json(json_str)` - Create from JSON string

### Phase 12F: Developer Experience ✅
- [x] **12F.1** - Component playground
  - `PlaygroundView` - Interactive web UI for testing
  - Live props editor with type-aware inputs
  - Theme switcher (light/dark, presets)
  - Code export tabs (JSON, HTML, React)
  - API endpoints for programmatic access
- [x] **12F.2** - CLI tools
  - `python manage.py components list` - List registered components
  - `python manage.py components show <name>` - Show component details
  - `python manage.py components preview <name>` - Preview output
  - `python manage.py components export --framework react` - Export wrappers
  - `python manage.py components docs` - Generate documentation
- [x] **12F.3** - Documentation generation
  - Markdown docs with props tables
  - JSON schema export
  - Per-component and index files

### Example Usage

```python
# views.py
from django_matt.components import serve_component, LoginForm, DataTable
from django_matt.components.themes import ShadcnTheme

@api.get("/components/login")
def get_login_component(request):
    return serve_component(
        LoginForm(
            action="/api/auth/login",
            oauth_providers=["google", "github"],
            show_magic_link=True,
            show_passkeys=True,
        ),
        theme=ShadcnTheme(mode="dark"),
        renderer="react",  # or "web-component", "vue", "svelte", "html"
    )

@api.get("/components/users-table")
def get_users_table(request):
    return serve_component(
        DataTable(
            model=User,
            columns=["email", "name", "created_at", "is_active"],
            sortable=True,
            filterable=True,
            actions=["edit", "delete"],
        ),
        theme=ShadcnTheme(),
    )
```

```html
<!-- In your frontend (any framework) -->
<script src="/api/components/matt-components.js"></script>
<matt-login-form
  api-url="/api/auth/login"
  theme="dark"
  show-oauth="google,github">
</matt-login-form>
```

```tsx
// Or in React
import { useComponent } from '@django-matt/react'

function LoginPage() {
  const LoginForm = useComponent('login')
  return <LoginForm onSuccess={() => navigate('/dashboard')} />
}
```

---

## Reference Projects

- [django-ninja-extra](https://github.com/eadwinCode/django-ninja-extra) - Class controllers, permissions, throttling
- [django-ninja-jwt](https://github.com/eadwinCode/django-ninja-jwt) - JWT auth
- [ninja-schema](https://github.com/eadwinCode/ninja-schema) - ModelSchema
- [django-ninja-crud](https://github.com/hbakri/django-ninja-crud) - Composable CRUD views
- [django-shinobi](https://github.com/pmdevita/django-shinobi) - Community fork with fixes
