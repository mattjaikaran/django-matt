# Code Examples

Practical examples for common use cases with django-matt.

| Example | Description |
|---------|-------------|
| [Basic CRUD API](crud.md) | Simple REST API with CRUD operations using `APIController` and `ModelSchema` |
| [Authentication](auth.md) | JWT auth flow, OAuth social login, and Passkey/WebAuthn |
| [Features](features.md) | File uploads, background tasks, WebSockets, multi-tenancy, billing |
| [Task Management API](task-management.md) | Complete example combining multiple features |

## Example Applications

The `examples/` directory contains full runnable apps:

| App | Stack | Description |
|-----|-------|-------------|
| `quicktodo` | Django API + PostgreSQL | Minimal multi-tenant todo API — the "build an API in 10 minutes" demo |
| `todo_app` | Django API (in-process) | Importable CRUD example, minimal footprint |
| `blog-app/api` | Django API + PostgreSQL | Full blog backend — JWT auth, full-text search, RSS, SEO endpoints, threaded comments, TypeScript codegen |
| `blog-app/frontend` | React + Vite | Blog frontend consuming generated TypeScript types from `sync_types` |
| `portfolio-api` | Django API + PostgreSQL | Personal portfolio backend — projects, skills, experience, contact form |
| `portfolio-frontend` | React + Vite + Tailwind | Portfolio UI paired with portfolio-api |
| `ecommerce-api` | Django API + PostgreSQL + Redis + Stripe + Celery | E-commerce with product variants, cart, Stripe payments, reviews, wishlists |
| `ecommerce-v2` | Django API + PostgreSQL + Redis + Stripe + Celery | Multi-vendor marketplace |
| `ai-chat` | Django API (ASGI) + OpenAI | SSE token streaming, CQRS buses, async event bus |
| `multitenant-saas` | Django API (ASGI) | Interceptor chains, feature flags, domain events |
| `realtime-chat` | Django API + Django Channels + Redis | WebSocket chat with presence, threading, JWT auth over WS |
| `saas-starter` | Django API + PostgreSQL + Redis + Stripe + Celery + Channels | Full SaaS template — multi-tenancy, billing, real-time notifications, background tasks |
| `devplatform` | Django API + PostgreSQL + Redis + Stripe + Celery | API management SaaS — API keys, usage analytics, webhooks, metered billing |
| `plugins/` | Installable packages | Clerk auth, Resend email, and Stripe webhook integrations |

See [`examples/README.md`](../../examples/README.md) for setup instructions, run commands, and a "choose your starting point" guide.
