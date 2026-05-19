# Tutorials

Learn Django Matt through hands-on tutorials, from basic REST APIs to production SaaS applications.

## Beginner

### [Build a REST API in 10 Minutes](build-a-rest-api.md)

Create a complete blog API with CRUD, authentication, pagination, and filtering.
Covers `MattAPI`, `APIController`, `ModelSchema`, `APIViewSet`, JWT auth, and the
built-in Swagger UI.

**Time:** ~15 minutes | **Prerequisites:** Python 3.12+, Django basics

### [Testing Your Django Matt App](testing-guide.md)

Set up pytest, use `AsyncAPITestClient` (primary) and `APITestClient` (sync
fallback), write controller tests, factory patterns, auth flow tests, and
webhook verification.

**Time:** ~20 minutes | **Prerequisites:** Build a REST API tutorial

## Intermediate

### [Build a Multi-Tenant SaaS API](build-a-saas-app.md)

Build a B2B SaaS backend with organizations, teams, role-based access,
Stripe billing, and per-tenant feature flags.

**Time:** ~30 minutes | **Prerequisites:** Build a REST API tutorial

### [Add Real-Time Features](realtime-features.md)

Add WebSocket consumers, Server-Sent Events (SSE), an async event bus,
push notifications, and presence indicators to an existing API.

**Time:** ~25 minutes | **Prerequisites:** Build a REST API tutorial

## Advanced

### [Build an AI/LLM Streaming API](ai-streaming-api.md)

Build a streaming AI endpoint with SSE, CQRS command/query separation,
interceptors for timing and logging, and rate limiting.

**Time:** ~25 minutes | **Prerequisites:** Real-Time Features tutorial

## Tutorial Conventions

- All code is copy-pasteable and verified against Stage 17 (current release).
- Imports always use the public API (`from django_matt import ...`).
- Async is the default. Sync alternatives are noted where they exist.
- Each tutorial ends with a complete, runnable code listing.
- Background tasks use `tasks_native` (`@task` decorator with Pydantic payloads).
  Celery remains supported but is no longer the default recommendation.
- TypeScript generation via `python manage.py sync_types` produces clean output
  with no `any` for optional fields.
- `AsyncAPITestClient` is the standard test client. All integration tests hit
  a real database — no DB mocking.
