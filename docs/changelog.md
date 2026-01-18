# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Session authentication with CSRF protection
- Audit logging system with model change tracking
- Background tasks with Celery, Dramatiq, and Django-Q2 backends
- File handling with S3, R2, MinIO, and local storage
- API Key authentication with rate limiting
- Soft delete mixin for models
- Dependency injection container
- Pagination and filtering backends
- API versioning schemes
- Rate limiting and throttling
- Content negotiation (JSON, XML, CSV, YAML)
- WebSocket support with Django Channels
- Billing integration (Stripe, PayPal, Polar)
- OAuth providers (Google, GitHub, Apple, Microsoft)
- Enterprise SSO (SAML 2.0, OIDC)
- Passkeys/WebAuthn support
- Type generation (TypeScript, Swift)
- CRUD generator CLI
- Multi-tenancy (organizations, teams)

### Changed
- Updated to Python 3.11+ minimum
- Updated to Django 5.2+ minimum
- Configured Ruff for linting/formatting

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
