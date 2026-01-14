# Django Matt - Development Roadmap

> A complete standalone meta-framework replacing Django Ninja and its ecosystem.

## Overview

django-matt consolidates features from multiple packages into one cohesive library:

| Package | Feature | django-matt Module |
|---------|---------|-------------------|
| django-ninja | Core routing, OpenAPI | `django_matt.core` |
| django-ninja-extra | Class controllers, permissions, DI | `django_matt.core.controller` |
| django-ninja-jwt | JWT authentication | `django_matt.auth` |
| ninja-schema | ModelSchema for Django ORM | `django_matt.core.schema` |
| django-ninja-crud | Composable CRUD views | `django_matt.views` |

## Tooling Standards

- **Python**: 3.13 with uv package manager
- **Frontend**: bun package manager
- **Containers**: Docker + Docker Compose

---

## Stage 1: Core Framework (Replace Django Ninja)

### Phase 0: Core Enhancements

- [x] **0A** - OpenAPI schema generation + Swagger/ReDoc docs
  - Create `django_matt/openapi/` package
  - Add schema builder, docs views
  - Integrate with router

- [x] **0B** - Enhanced ModelSchema with model_validator
  - Add `model_validator` decorator (from ninja-schema)
  - Add `from_orm()` method
  - Add `apply_to_model()` method
  - Support `include`, `exclude`, `optional`, `depth` config

- [x] **0C** - Composable CRUD views
  - Create `django_matt/views/` package
  - Add `ListView`, `CreateView`, `ReadView`, `UpdateView`, `DeleteView`
  - Add `APIViewSet` for grouping views
  - Support default request/response body inference

- [x] **0D** - Permission classes and RBAC decorators
  - Create `django_matt/permissions/` package
  - Add `IsAuthenticated`, `IsAdmin`, `AllowAny`
  - Add custom permission base class
  - Integrate with controllers

### Phase 1: Authentication System

- [x] **1A** - JWT authentication backend
  - Create `django_matt/auth/` package
  - Implement access/refresh token generation
  - Add token validation and refresh flow
  - Settings-based configuration

- [x] **1B** - Auth decorators and middleware
  - Add `@jwt_required`, `@jwt_optional` decorators
  - Add `@with_roles`, `@with_permission` decorators
  - Create JWT auth middleware
  - Integrate with controllers

- [x] **1B+** - RBAC with hierarchy support
  - Role definitions with permission inheritance
  - Priority-based role hierarchy
  - `@requires_role_hierarchy` decorator
  - Settings-based RBAC configuration

- [x] **1C** - Magic link passwordless authentication
  - Add magic link token generation
  - Email-based verification flow
  - Token expiration handling

- [x] **1D** - Auth controllers
  - Build `/auth/login` endpoint
  - Build `/auth/register` endpoint
  - Build `/auth/refresh` endpoint
  - Build `/auth/logout` endpoint
  - Build `/auth/me` endpoint

- [x] **1E** - Multi-tenant support (B2B)
  - Add Organization model
  - Add Team model
  - Add Membership model with roles
  - Add Invitation model
  - Add tenant context middleware

---

## Stage 2: Developer Experience

### Phase 2: Type Synchronization

- [x] **2A** - TypeScript generator
  - Create `django_matt/typegen/` package
  - Pydantic schema to TypeScript interface
  - Django model to TypeScript interface
  - Generate Zod validation schemas
  - Generate typed API client

- [x] **2B** - Swift generator
  - Pydantic schema to Swift Codable struct
  - Generate URLSession-based API client

- [x] **2C** - sync_types CLI command
  - Create `sync_types` management command
  - Support `--target typescript` and `--target swift`
  - Support `--output` directory
  - Support `--watch` mode for development

### Phase 3: CLI Tools

- [x] **3A** - Enhanced startapi command
  - Add `--template` option (starter, b2b, b2c)
  - Add `--auth` option (jwt, magic-link, oauth)
  - Add `--frontend` option (none, react-vite, swift)
  - Add `--docker` option
  - Generate Makefile

### Phase 4: Testing Infrastructure

- [ ] **4A** - Test utilities
  - Create `django_matt/testing/` package
  - Add `APITestClient` with auth helpers
  - Add base factory classes
  - Add pytest fixtures
  - Add custom assertions

---

## Stage 3: Template Repositories (Separate Repos)

- [ ] **django-api-starter** - Minimal API with JWT, uv, Docker
- [ ] **react-vite-starter** - Minimal React Vite with bun
- [ ] **django-api-b2b** - Organizations, teams, roles
- [ ] **react-vite-b2b** - Org switcher, team management UI
- [ ] **fullstack-b2b** - Monorepo with Docker orchestration
- [ ] **swift-ios-starter** - SwiftUI + generated API client

---

## Stage 4: Advanced Features

- [ ] OAuth providers (Google, GitHub, Apple)
- [ ] Passkeys/WebAuthn support
- [ ] Subscriptions/billing (B2C)
- [ ] Real-time WebSocket support

---

## Dependencies

```toml
[project]
requires-python = ">=3.13"
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
all = ["django-matt[full,auth,oauth,passkeys,typegen,testing]"]
```

---

## Reference Projects

- [django-ninja-extra](https://github.com/eadwinCode/django-ninja-extra) - Class controllers, permissions
- [django-ninja-jwt](https://github.com/eadwinCode/django-ninja-jwt) - JWT auth
- [ninja-schema](https://github.com/eadwinCode/ninja-schema) - ModelSchema
- [django-ninja-crud](https://github.com/hbakri/django-ninja-crud) - Composable CRUD views
- [django-shinobi](https://github.com/pmdevita/django-shinobi) - Community fork with fixes
