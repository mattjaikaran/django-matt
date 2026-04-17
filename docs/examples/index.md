# Code Examples

Practical examples for common use cases with django-matt.

| Example | Description |
|---------|-------------|
| [Basic CRUD API](crud.md) | Simple REST API with CRUD operations |
| [Authentication](auth.md) | JWT, OAuth, and Passkeys |
| [Features](features.md) | File uploads, background tasks, WebSockets, multi-tenancy, billing |
| [Task Management API](task-management.md) | Complete example combining multiple features |

## Example Applications

The `examples/` directory in the repository contains full runnable apps:

| App | Description |
|-----|-------------|
| `todo` | Minimal todo API |
| `ecommerce-v2` | E-commerce with event bus |
| `saas-starter` | SaaS with interceptors + events |
| `devplatform` | SSE streaming + gateway |
| `realtime-chat` | WebSocket messaging |
| `ai-chat` | SSE streaming + CQRS |
| `multitenant-saas` | Events + feature flags |

All examples run with `uv run python manage.py runserver`.
