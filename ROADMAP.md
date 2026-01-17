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

## Stage 5: Missing django-ninja-extra Features

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

### Phase 5C: Pagination & Filtering
- [ ] **5C.1** - Pagination classes
  - `PageNumberPagination`
  - `LimitOffsetPagination`
  - `CursorPagination`
- [ ] **5C.2** - Filtering
  - Query parameter filters
  - Django ORM filter integration
  - Custom filter backends
- [ ] **5C.3** - Ordering/Sorting
  - `?ordering=created_at,-name`
  - Allowed fields configuration
- [ ] **5C.4** - Search
  - Full-text search integration
  - Elasticsearch/Meilisearch support

### Phase 5D: Dependency Injection
- [ ] **5D.1** - DI container
  - Service registration
  - Scoped/singleton/transient lifetimes
  - Auto-injection in controllers
- [ ] **5D.2** - Built-in dependencies
  - Request context
  - Current user
  - Current organization (multi-tenant)

---

## Stage 6: Additional Features

### Phase 6A: File Handling
- [ ] **6A.1** - File uploads
  - Multipart form handling
  - Size/type validation
  - Async upload support
- [ ] **6A.2** - Storage backends
  - Local filesystem
  - AWS S3 / Cloudflare R2
  - Pre-signed URLs

### Phase 6B: Background Tasks
- [ ] **6B.1** - Task queue integration
  - Celery support
  - Dramatiq support
  - Django-Q2 support
- [ ] **6B.2** - Task decorators
  - `@background_task`
  - Retry policies
  - Task scheduling

### Phase 6C: Audit & Logging
- [ ] **6C.1** - Audit logging
  - Model change tracking
  - User action logging
  - IP/User-Agent tracking
- [ ] **6C.2** - Soft delete
  - `SoftDeleteMixin` for models
  - Automatic filtering of deleted records
  - Restore functionality

### Phase 6D: Additional Auth
- [ ] **6D.1** - API Key authentication
  - Key generation and rotation
  - Scoped permissions per key
  - Rate limiting per key
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

### Phase 8C: Replace Jinja2 for Type Generation
- [ ] **8C.1** - Built-in template engine for codegen
  - Simple string-based templating
  - Or use Django's template engine
  - TypeScript/Swift template rendering
- [ ] **8C.2** - Remove jinja2 dependency from typegen

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
| PyJWT | Built-in JWT | Medium | High |
| passlib | Django hashers | Low | High |
| argon2-cffi | Django hashers | Low | High |
| jinja2 | String templates | Low | Medium |
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

## Reference Projects

- [django-ninja-extra](https://github.com/eadwinCode/django-ninja-extra) - Class controllers, permissions, throttling
- [django-ninja-jwt](https://github.com/eadwinCode/django-ninja-jwt) - JWT auth
- [ninja-schema](https://github.com/eadwinCode/ninja-schema) - ModelSchema
- [django-ninja-crud](https://github.com/hbakri/django-ninja-crud) - Composable CRUD views
- [django-shinobi](https://github.com/pmdevita/django-shinobi) - Community fork with fixes
