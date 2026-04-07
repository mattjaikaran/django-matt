# Core Concepts

These guides explain the design principles and architectural patterns underlying django-matt. Read them to understand how the pieces fit together before diving into specific module docs.

## Architecture

- [Request Lifecycle](request-lifecycle.md) — the full journey of a request through middleware, interceptors, permissions, controllers, and error handling
- [Module Architecture](module-architecture.md) — how django-matt modules are organized, loaded, and extended

## Patterns

- [Dependency Injection](dependency-injection.md) — the DI container, `@inject`, `Depends()`, service lifetimes, and testing
- [Async Patterns](async-patterns.md) — async-first design, `sync_to_async` for ORM fallbacks, concurrent operations, and common pitfalls
- [Error Handling](error-handling.md) — the layered error handling system: `APIError` hierarchy, `ErrorHandler`, exception filters, and `@catch` decorators

## Quick Reference

| Concept | Key Import | One-liner |
|---------|-----------|-----------|
| Controllers | `from django_matt.core.controller import APIController` | Class-based route handlers with DI |
| ViewSets | `from django_matt.views import APIViewSet, ListView, CreateView` | Declarative CRUD with lifecycle hooks |
| Schemas | `from django_matt.core.schema import ModelSchema` | Django model to Pydantic schema |
| Permissions | `from django_matt.permissions import IsAuthenticated` | Per-route authorization |
| DI | `from django_matt.di import Depends, inject, container` | Constructor and parameter injection |
| Interceptors | `from django_matt.interceptors import Interceptor, intercept` | Route-scoped before/after hooks |
| Exception Filters | `from django_matt.exceptions import ExceptionFilter, catch` | Scoped error handling |
| Modules | `from django_matt.modules import MattModule` | Plugin system with lifecycle hooks |
| Slim Mode | `DJANGO_MATT = {"SLIM_MODE": {"mode": "slim"}}` | Load only what you use |
