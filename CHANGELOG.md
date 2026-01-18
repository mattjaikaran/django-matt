# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

**Stage 6: Additional Features**
- Session authentication with CSRF protection (`django_matt.auth.session`)
- Audit logging system with model change tracking (`django_matt.audit`)
- Background tasks with Celery, Dramatiq, and Django-Q2 backends (`django_matt.tasks`)
- File handling with S3, R2, MinIO, and local storage (`django_matt.files`)
- API Key authentication with rate limiting (`django_matt.auth.api_keys`)
- Soft delete mixin for models (`django_matt.db.soft_delete`)

**Stage 5: Django-Ninja-Extra Features**
- Dependency injection container (`django_matt.di`)
- Pagination and filtering backends (`django_matt.pagination`, `django_matt.filtering`)
- API versioning schemes (`django_matt.versioning`)
- Rate limiting and throttling (`django_matt.throttling`)

**Stage 4: Advanced Features**
- Content negotiation (JSON, XML, CSV, YAML) (`django_matt.negotiation`)
- WebSocket support with Django Channels (`django_matt.websockets`)
- Billing integration - Stripe, PayPal, Polar (`django_matt.billing`)
- OAuth providers - Google, GitHub, Apple, Microsoft (`django_matt.auth.oauth`)
- Enterprise SSO - SAML 2.0, OIDC (`django_matt.auth.sso`)
- Passkeys/WebAuthn support (`django_matt.auth.passkeys`)

**Stage 7: Future Compatibility**
- GitHub Actions CI/CD workflows
- Django 6.0 compatibility (Python 3.12+ required)
- Ruff linter/formatter configuration
- Pyright/MyPy type checking configuration
- MkDocs documentation setup

### Changed
- Updated to Python 3.11+ minimum (Python 3.12+ for Django 6.0)
- Updated to Django 5.2+ minimum
- Replaced black/isort with Ruff for linting and formatting

## [0.1.0] - TBD

Initial release.

### Added
- Core routing and decorators (`django_matt.core`)
- Class-based controllers (`django_matt.core.controller`)
- Pydantic ModelSchema (`django_matt.core.schema`)
- OpenAPI/Swagger/ReDoc documentation (`django_matt.openapi`)
- JWT authentication (`django_matt.auth.jwt`)
- Magic link authentication (`django_matt.auth.magic_link`)
- Permission system (`django_matt.permissions`)
- RBAC with hierarchy (`django_matt.auth.rbac`)
- Multi-tenancy - organizations, teams (`django_matt.multitenancy`)
- Type generation - TypeScript, Swift (`django_matt.typegen`)
- CRUD generator CLI (`manage.py generate_crud`)
- Testing utilities (`django_matt.testing`)
