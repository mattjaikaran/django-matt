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
- [ ] **6C.1** - Audit logging
  - Model change tracking
  - User action logging
  - IP/User-Agent tracking
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
- [ ] **6D.2** - Session authentication
  - Cookie-based sessions
  - CSRF protection
  - Session management endpoints

---

## Stage 7: Future Compatibility

### Phase 7A: Django 6.0 Support
- [ ] **7A.1** - Django 6.0 compatibility testing
- [ ] **7A.2** - Update deprecated APIs
- [ ] **7A.3** - CI/CD matrix testing (Django 5.2, 6.0)

### Phase 7B: Python Version Support
- [ ] **7B.1** - Python 3.11 minimum support
- [ ] **7B.2** - Python 3.13 as default
- [ ] **7B.3** - Python 3.14 readiness

### Phase 7C: Modern Tooling
- [ ] **7C.1** - uv package manager (all templates)
- [ ] **7C.2** - Ruff linter/formatter
- [ ] **7C.3** - Full type annotations (pyright strict)

### Phase 7D: Documentation (Internal)
- [ ] **7D.1** - MkDocs setup
- [ ] **7D.2** - Core documentation
- [ ] **7D.3** - API reference

### Phase 7E: CI/CD
- [ ] **7E.1** - GitHub Actions pipelines
- [ ] **7E.2** - Template repository workflows
- [ ] **7E.3** - Security scanning

---

## Stage 8: Dependency Reduction

> Goal: Minimize external dependencies to reduce version conflicts, security surface, and maintenance burden.

### Phase 8A: Replace PyJWT
- [ ] **8A.1** - Built-in JWT implementation
  - HMAC signing (HS256, HS384, HS512) using `hmac` stdlib
  - Base64url encoding/decoding
  - Claims validation (exp, nbf, iat, iss, aud)
  - Token parsing and verification
- [ ] **8A.2** - RSA/EC support (optional `cryptography` dep)
  - RS256, RS384, RS512
  - ES256, ES384, ES512
  - Public key verification

### Phase 8B: Replace passlib/argon2-cffi
- [ ] **8B.1** - Use Django's built-in password hashers
  - Django already supports Argon2, bcrypt, PBKDF2
  - Wrapper around `make_password()` / `check_password()`
  - Password strength validation
- [ ] **8B.2** - Remove passlib and argon2-cffi dependencies
  - Migrate existing code to Django hashers
  - Maintain backward compatibility with existing hashes

### Phase 8C: Universal Frontend Codegen Engine

> Replace Jinja2 with a powerful multi-framework code generation system.
> Generate full components, not just types.

#### 8C.1 - Core Codegen Infrastructure
- [ ] **8C.1.1** - AST-based code generation primitives
  - Language-agnostic intermediate representation
  - Pretty printing with configurable formatting
  - Import management and deduplication
- [ ] **8C.1.2** - Model introspection system
  - Extract fields, types, relationships from Django models
  - Map Django fields to frontend types
  - Handle validators and constraints
- [ ] **8C.1.3** - Template registry and plugin system
  - Register generators per framework
  - Customizable templates per project
  - Override defaults easily

#### 8C.2 - React Generator (Primary)
- [ ] **8C.2.1** - TypeScript types and Zod schemas
  - Interfaces from Django models
  - Zod validation schemas
  - API response types
- [ ] **8C.2.2** - React Query / TanStack Query hooks
  - `useUsers()`, `useUser(id)`, `useCreateUser()`
  - Optimistic updates
  - Infinite scroll queries
- [ ] **8C.2.3** - Form components (shadcn/ui default)
  - `<UserForm />` with validation
  - Field components based on model field types
  - react-hook-form integration
- [ ] **8C.2.4** - List/Table components
  - `<UserList />` with pagination
  - `<UserTable />` with sorting, filtering
  - shadcn/ui DataTable integration
- [ ] **8C.2.5** - Detail/Show components
  - `<UserDetail />` display component
  - Loading and error states

#### 8C.3 - Svelte Generator (Secondary)
- [ ] **8C.3.1** - TypeScript types
  - Same type generation as React
- [ ] **8C.3.2** - Svelte stores and queries
  - Writable stores for state
  - TanStack Query Svelte or custom fetch
- [ ] **8C.3.3** - Svelte components
  - `UserForm.svelte`
  - `UserList.svelte`
  - `UserDetail.svelte`
- [ ] **8C.3.4** - Svelte 5 runes support
  - `$state`, `$derived`, `$effect`
  - Modern Svelte patterns

#### 8C.4 - SolidJS Generator (Tertiary)
- [ ] **8C.4.1** - TypeScript types
  - Same type generation
- [ ] **8C.4.2** - Solid primitives
  - `createSignal`, `createResource`
  - `createStore` for complex state
- [ ] **8C.4.3** - Solid components
  - `UserForm.tsx` (Solid JSX)
  - `UserList.tsx`
  - `UserDetail.tsx`

#### 8C.5 - CLI and Integration
- [ ] **8C.5.1** - Enhanced `sync_types` command
  ```bash
  python manage.py sync_types --framework react --output ./src/generated
  python manage.py sync_types --framework svelte --output ./src/lib/generated
  python manage.py sync_types --framework solid --output ./src/generated
  ```
- [ ] **8C.5.2** - Watch mode for development
  - Auto-regenerate on model changes
  - HMR-friendly output
- [ ] **8C.5.3** - Config file support
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

### Phase 8D: Replace factory-boy
- [ ] **8D.1** - Built-in model factory system
  - `ModelFactory` base class
  - Field auto-generation based on model fields
  - Sequence support for unique values
  - Trait/variant support
  - Related object creation
- [ ] **8D.2** - Built-in data generators (replace Faker)
  - Names, emails, usernames
  - Addresses, phone numbers
  - Dates, times, timestamps
  - Lorem ipsum text
  - UUIDs, slugs
  - Common patterns (credit cards, SSN - fake only)

### Phase 8E: Replace python-multipart
- [ ] **8E.1** - Built-in multipart form parser
  - Streaming multipart parsing
  - File upload handling
  - Memory-efficient large file support
  - Content-Type validation

### Dependency Analysis

| Current Dep | Replacement | Complexity | Priority |
|------------|-------------|------------|----------|
| PyJWT | Built-in JWT (symmetric + asymmetric) | Medium | High |
| passlib | Django hashers | Low | High |
| argon2-cffi | Django hashers | Low | High |
| jinja2 | Universal Codegen Engine | High | High |
| factory-boy | Built-in factories | Medium | Medium |
| faker | Built-in generators | Medium | Low |
| python-multipart | Built-in parser | High | Low |

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

### Current Dependencies
```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "django>=5.2",
    "pydantic>=2.0.0",
    "typing-extensions>=4.0.0",
]

[project.optional-dependencies]
full = ["orjson>=3.9.0", "uvicorn>=0.30.0"]
auth = ["PyJWT>=2.9.0", "passlib[bcrypt]>=1.7.4", "argon2-cffi>=23.1.0"]
oauth = ["authlib>=1.3.0"]
passkeys = ["webauthn>=2.1.0"]
typegen = ["jinja2>=3.1.0"]
testing = ["factory-boy>=3.3.0", "faker>=24.0.0", "pytest>=8.0.0", "pytest-django>=4.8.0", "httpx>=0.27.0"]
files = ["boto3>=1.34.0", "python-multipart>=0.0.9"]
tasks = ["celery>=5.4.0", "redis>=5.0.0"]
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

### Phase 10A: ML Utilities
- [ ] **10A.1** - Model serving utilities
  - `MLModel` base class for inference
  - Async inference support
  - Batch prediction endpoints
- [ ] **10A.2** - Vector storage integration
  - pgvector utilities (already started in `db/`)
  - Pinecone integration
  - Weaviate integration
  - Qdrant integration
- [ ] **10A.3** - Embedding utilities
  - OpenAI embeddings helper
  - Sentence transformers integration
  - Caching for embeddings

### Phase 10B: LLM Integration (Cloud Providers)
- [ ] **10B.1** - LLM client utilities
  - OpenAI client wrapper
  - Anthropic client wrapper
  - Google Gemini client wrapper
  - Unified interface for multiple providers
- [ ] **10B.2** - RAG (Retrieval Augmented Generation)
  - Document chunking utilities
  - Vector search + LLM pipelines
  - Conversation memory
- [ ] **10B.3** - Structured output
  - Pydantic model extraction from LLM responses
  - JSON mode helpers
  - Validation and retry logic

### Phase 10C: Self-Hosted LLMs
- [ ] **10C.1** - Ollama integration
  - Ollama client wrapper
  - Model management (pull, list, delete)
  - Streaming responses
  - Embeddings via Ollama
- [ ] **10C.2** - vLLM integration
  - vLLM server client
  - OpenAI-compatible API support
  - Batch inference
- [ ] **10C.3** - llama.cpp integration
  - Direct llama-cpp-python bindings
  - GGUF model loading
  - Quantization options
- [ ] **10C.4** - LocalAI integration
  - LocalAI client wrapper
  - Drop-in OpenAI replacement
  - Multiple model backends
- [ ] **10C.5** - Self-hosted infrastructure
  - Docker Compose for local LLM stack
  - GPU passthrough configuration
  - Model download/caching utilities
  - Health checks for LLM services

### Phase 10D: AI IDE Integration
- [ ] **10D.1** - Context file generation
  - Auto-generate `.cursorrules` / `CLAUDE.md`
  - Project structure documentation
  - API endpoint documentation for AI assistants
- [ ] **10D.2** - Code generation prompts
  - Model-to-code prompts
  - Schema documentation for AI
  - Example generation

---

## Stage 11: Frontend Integrations

> Goal: Seamless integration with modern frontend frameworks.

### Phase 11A: HTMX Integration
- [ ] **11A.1** - HTMX view helpers
  - `@htmx_view` decorator
  - Partial template rendering
  - Out-of-band swaps support
- [ ] **11A.2** - HTMX response utilities
  - `HtmxResponse` with triggers
  - Push URL, redirect helpers
  - Retarget/reswap utilities
- [ ] **11A.3** - Component library
  - Infinite scroll
  - Search with debounce
  - Modal dialogs
  - Toast notifications

### Phase 11B: InertiaJS Integration
- [ ] **11B.1** - Inertia middleware
  - Asset version handling
  - Partial reload support
- [ ] **11B.2** - Inertia responses
  - `inertia()` response helper
  - Shared data (auth, flash messages)
  - Lazy loading props
- [ ] **11B.3** - SSR support
  - Node.js SSR server
  - Vite integration

### Phase 11C: Livewire-style Reactivity
- [ ] **11C.1** - Reactive components
  - Python component classes
  - State management
  - Action handling
- [ ] **11C.2** - Real-time updates
  - WebSocket integration
  - Optimistic UI updates

---

## Stage 12: Backend-Served Component System

> Goal: Serve UI components from the backend that render in any frontend framework, with built-in validation, theming, and customization. Inspired by FastUI, but framework-agnostic.

### Phase 12A: Component Definition System
- [ ] **12A.1** - Component schema DSL
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
- [ ] **12A.2** - Component registry
  - Register custom components
  - Extend built-in components
  - Component versioning
- [ ] **12A.3** - Validation integration
  - Pydantic validation rules → frontend validation
  - Server-side validation feedback
  - Real-time validation via WebSocket

### Phase 12B: Pre-built Component Library
- [ ] **12B.1** - Authentication components
  - `LoginForm` - Email/password with validation
  - `RegisterForm` - Registration with password strength
  - `ForgotPasswordForm` - Password reset flow
  - `MagicLinkForm` - Passwordless login
  - `OAuthButtons` - Social login buttons
  - `PasskeyPrompt` - WebAuthn registration/login
- [ ] **12B.2** - CRUD components
  - `DataTable` - Sortable, filterable, paginated table
  - `DetailView` - Model detail display
  - `CreateForm` / `EditForm` - Auto-generated from schema
  - `DeleteConfirm` - Confirmation dialog
  - `SearchInput` - Debounced search with suggestions
- [ ] **12B.3** - Layout components
  - `Modal` / `Dialog` / `Drawer`
  - `Tabs` / `Accordion`
  - `Card` / `Panel`
  - `Alert` / `Toast` / `Banner`
  - `Pagination` / `InfiniteScroll`
- [ ] **12B.4** - Input components
  - Text, Number, Email, Password, URL
  - Select, MultiSelect, Combobox
  - Checkbox, Radio, Switch
  - DatePicker, TimePicker, DateRangePicker
  - FileUpload, ImageUpload
  - RichTextEditor, MarkdownEditor

### Phase 12C: Theming & Design System Integration
- [ ] **12C.1** - Theme configuration
  - CSS variables / design tokens
  - Color schemes (light/dark mode)
  - Typography, spacing, borders
  ```python
  theme = Theme(
      primary="#3B82F6",
      secondary="#10B981",
      font_family="Inter, sans-serif",
      border_radius="0.5rem",
  )
  ```
- [ ] **12C.2** - Design system adapters
  - shadcn/ui adapter (default)
  - Tailwind CSS adapter
  - Material UI adapter
  - Chakra UI adapter
  - Headless (unstyled) adapter
- [ ] **12C.3** - Custom styling
  - Class name overrides per component
  - Style prop support
  - CSS-in-JS compatible output

### Phase 12D: Framework Renderers
- [ ] **12D.1** - Web Components renderer (universal)
  - Custom elements from component definitions
  - Shadow DOM encapsulation
  - Works with any framework or vanilla JS
  - `<matt-login-form theme="dark"></matt-login-form>`
- [ ] **12D.2** - React renderer
  - Component tree → React JSX
  - Hooks for state management
  - React Query integration for data fetching
- [ ] **12D.3** - Vue renderer
  - Component tree → Vue SFCs
  - Composition API support
- [ ] **12D.4** - Svelte renderer
  - Component tree → Svelte components
  - Svelte 5 runes support
- [ ] **12D.5** - Vanilla JS renderer
  - Pure DOM manipulation
  - No framework dependencies
  - Progressive enhancement friendly

### Phase 12E: Component Serving & API
- [ ] **12E.1** - Component endpoints
  - `GET /api/components/{name}` - Get component definition
  - `GET /api/components/{name}/render` - Get rendered HTML/JSON
  - `POST /api/components/{name}/validate` - Validate form data
  - `POST /api/components/{name}/submit` - Handle form submission
- [ ] **12E.2** - Component embedding
  - Django template tags: `{% matt_component "login_form" %}`
  - Script tag injection for SPAs
  - iframe embedding option
- [ ] **12E.3** - Component streaming
  - Server-sent events for updates
  - Partial component updates
  - Optimistic UI patterns

### Phase 12F: Developer Experience
- [ ] **12F.1** - Component playground
  - Live preview of components
  - Props editor
  - Theme switcher
  - Code export (React, Vue, Svelte, HTML)
- [ ] **12F.2** - CLI tools
  - `python manage.py components list` - List available components
  - `python manage.py components preview` - Launch playground
  - `python manage.py components export --framework react` - Export to framework
- [ ] **12F.3** - Documentation generation
  - Auto-generate component docs
  - Props table, examples, variants
  - Storybook-compatible export

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
