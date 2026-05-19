# Django Matt Examples

Full-stack and API-only example applications demonstrating the features and capabilities of the Django Matt framework.

## Quick Reference

| Example | Stack | What it demonstrates | Run command |
|---------|-------|----------------------|-------------|
| **quicktodo** | Django API + PostgreSQL | "Build an API in 10 minutes" — JWT auth, multi-tenant todos, org/team model, minimal footprint | `cd quicktodo && make docker-up && make migrate && make run` |
| **todo_app** | Django API (in-process) | Minimal CRUD controller, Pydantic schemas, basic error handling — importable into an existing project | Use as an installed Django app (see its README) |
| **blog-app/api** | Django API + PostgreSQL | JWT auth, full-text search, draft/publish workflow, threaded comments, RSS, SEO endpoints, Django Unfold admin, TypeScript codegen via `sync_types` | `cd blog-app/api && make docker-up && make migrate && make run` |
| **blog-app/frontend** | React + Vite + TanStack | Post listing, search, tag/category pages, author dashboard, JWT auth, generated TypeScript types | `cd blog-app/frontend && bun install && bun dev` |
| **portfolio-api** | Django API + PostgreSQL | Projects, skills, work experience, contact form, slug routing, OpenAPI docs | `cd portfolio-api && make install && make migrate && make run` |
| **portfolio-frontend** | React + Vite + Tailwind | Portfolio UI wired to portfolio-api, TanStack Router, shadcn/ui | `cd portfolio-frontend && bun install && bun dev` |
| **ecommerce-api** | Django API + PostgreSQL + Redis + Stripe + Celery | Product catalog with variants, cart, checkout, Stripe payments and webhooks, reviews, wishlists, full-text search, Django Unfold admin | `cd ecommerce-api && make docker-up && make migrate && make run` |
| **ecommerce-v2** | Django API + PostgreSQL + Redis + Stripe + Celery | Multi-vendor marketplace — multiple stores, catalog, cart, orders, Stripe, reviews, search | `cd ecommerce-v2 && make docker-up && make migrate && make run` |
| **ai-chat** | Django API (ASGI) + OpenAI | SSE token streaming via `sse_response()`, CQRS command/query buses, async event bus, OpenAI integration | `cd ai-chat && export OPENAI_API_KEY=sk-... && uv run uvicorn ai_chat_project.asgi:application --reload` |
| **multitenant-saas** | Django API (ASGI) | Org-scoped resources, interceptor chains (tenant resolution + plan gating), feature flags, domain events | `cd multitenant-saas && uv run python manage.py migrate && uv run uvicorn mt_project.asgi:application --reload` |
| **realtime-chat** | Django API + Django Channels + Redis + HTML/JS | WebSockets, presence tracking, typing indicators, read receipts, message threading, JWT auth over WS | `cd realtime-chat && make docker-up && make migrate && make run` |
| **saas-starter** | Django API + PostgreSQL + Redis + Stripe + Celery + Channels | Full SaaS template — multi-tenancy, Stripe billing, real-time notifications, background tasks | `cd saas-starter && make docker-up && make migrate && make run` |
| **devplatform** | Django API + PostgreSQL + Redis + Stripe + Celery | API management SaaS — API keys, usage analytics, webhooks, metered Stripe billing, gateway routing | `cd devplatform && make docker-up && make migrate && make run` |
| **plugins/** | Python packages | Third-party integrations: Clerk auth, Resend email, Stripe webhook handlers | See each plugin's README |

---

## Choose Your Starting Point

### API-only vs Full-Stack

**API-only (backend only):**
- `quicktodo` — smallest possible footprint
- `ai-chat` — streaming + CQRS
- `multitenant-saas` — interceptors + feature flags
- `ecommerce-v2` — marketplace backend
- `portfolio-api` — content/portfolio backend
- `devplatform` — API gateway/management

**Full-stack (API + React frontend):**
- `blog-app` — blog API paired with a React/Vite frontend; includes generated TypeScript types
- `portfolio-api` + `portfolio-frontend` — portfolio backend paired with a React/Vite/Tailwind frontend

**Real-time (WebSockets):**
- `realtime-chat` — Slack-like chat with presence, threading, and JWT auth over WebSockets
- `saas-starter` — includes real-time notifications via Django Channels

### Simple vs Complex

| Complexity | Recommendation |
|------------|----------------|
| Learning the basics | `quicktodo` or `todo_app` |
| Building a blog or content site | `blog-app` |
| Building a portfolio site | `portfolio-api` + `portfolio-frontend` |
| SaaS with billing | `saas-starter` (all-in-one) or `multitenant-saas` (interceptors focus) |
| Marketplace / e-commerce | `ecommerce-v2` |
| AI / streaming responses | `ai-chat` |
| Real-time chat | `realtime-chat` |
| Developer tools / API gateway | `devplatform` |

---

## Example App Summaries

### quicktodo

Multi-tenant todo API — the "build an API in 10 minutes" demo. Covers JWT auth, organization/team models, nested resource routing, filtering, pagination, and seeded test data. The smallest complete example in the repo.

Django Matt features: `APIController`, `ModelSchema`, `jwt_required`, `IsAuthenticated`, `multitenancy`, `pagination`, `filtering`.

### todo_app

Minimal in-process example meant to be installed into an existing Django project. Demonstrates a CRUD controller with Pydantic schemas and basic error handling. Good for copy-paste when adding a new resource to an existing API.

Django Matt features: `APIController`, `ModelSchema`, `MattAPI`.

### blog-app

Two-part full-stack example: `blog-app/api` (Django backend) + `blog-app/frontend` (React/Vite).

**API** demonstrates: JWT auth with refresh tokens, full-text PostgreSQL search, draft/publish workflow, threaded comments (auth optional), RSS/Atom feeds, per-post SEO metadata endpoint, view tracking, Django Unfold admin, TypeScript type generation via `sync_types`.

**Frontend** demonstrates: TanStack Router (file-based), TanStack Query, Zustand auth state, Axios with JWT interceptor, shadcn/ui + Tailwind, dark mode, and consuming generated TypeScript types from `sync_types`.

Generated TypeScript types live in `blog-app/frontend/src/types/generated.ts`. Regenerate them with:

```bash
cd examples/blog-app/api
python manage.py sync_types --target typescript --output ../frontend/src/types/generated.ts
```

Django Matt features: `APIController`, `ModelSchema`, `jwt_required`, `sync_types`, `CRUDService`, full-text search, RSS feed helpers, Django Unfold admin integration.

### portfolio-api + portfolio-frontend

Personal portfolio backend (projects, skills, work experience, contact form, slug routing) paired with a React/Vite/Tailwind frontend.

**API** demonstrates: slug-based routing, public and authenticated endpoints, seeded sample data, OpenAPI docs.

**Frontend** demonstrates: TanStack Router, shadcn/ui, Tailwind CSS, consuming the portfolio API with typed responses.

Django Matt features: `APIController`, `ModelSchema`, `jwt_required`, `IsAuthenticated`.

### ecommerce-api

Production-quality e-commerce backend with a hierarchical category tree, product variants, inventory tracking, session-based cart, coupon support, Stripe payments and webhook handling, product reviews with moderation, user wishlists, full-text PostgreSQL search, Celery background tasks for async processing, Redis caching, and Django Unfold admin.

Django Matt features: `APIController`, `ModelSchema`, `jwt_required`, `billing` (Stripe), `tasks` (Celery), `admin` (Unfold), `filtering`, `pagination`.

### ecommerce-v2

Multi-vendor marketplace. Supports multiple vendor stores, per-store product catalogs, shopping cart, order placement and fulfillment, Stripe checkout and refunds, product reviews and ratings, and product search and filtering. Includes a Celery worker for background jobs.

Django Matt features: `APIController`, `ModelSchema`, `jwt_required`, `billing` (Stripe), `tasks` (Celery), `filtering`, `pagination`.

### ai-chat

AI-powered chat demonstrating SSE token streaming, CQRS, and the async event bus. Conversations and messages are managed through typed command/query buses. Responses stream token-by-token from OpenAI via `sse_response()`.

Architecture: `POST /conversations/{id}/stream` → `SendMessageCommand` → CommandBus → OpenAI → SSE stream.

Django Matt features: `APIController`, `sse_response()`, `cqrs` (CommandBus, QueryBus), `events` (EventBus, `@on`), `streaming`.

### multitenant-saas

Focused demonstration of django-matt's interceptor chain, multi-tenancy, feature flags, and domain events. Tenant resolution happens in a `TenantInterceptor` before the controller runs. Plan-based feature gating (archive is Pro+ only) is handled by a `FeatureGateInterceptor`. Domain events (`tenant.created`, `project.created`, `member.invited`) are emitted via the async event bus.

Django Matt features: `APIController`, `interceptors` (`@intercept`, `InterceptorChain`), `multitenancy`, `flags` (plan-based gating), `events` (EventBus).

### realtime-chat

Slack-like real-time chat: workspaces, public/private channels, direct messages, presence (online/away/offline), typing indicators, read receipts, message threading, emoji reactions, @mentions, file attachments, and full-text message search. Includes a minimal HTML/JS demo client.

Django Matt features: `APIController`, `websockets` (Django Channels consumers, `AuthenticatedConsumer`, `broadcast`), `messaging`, `jwt_required`.

### saas-starter

All-in-one SaaS template combining multi-tenancy, Stripe billing (subscriptions), Django Channels real-time notifications, and Celery background tasks. Good starting point for a new B2B SaaS product.

Django Matt features: `APIController`, `multitenancy`, `billing` (Stripe), `websockets`, `tasks` (Celery), `jwt_required`.

### devplatform

API management SaaS (mini Stripe Dashboard / PostHog). Manages API keys (generation, rotation), logs and aggregates API gateway usage, configures and delivers webhooks (with retries), and handles usage-based metered billing via Stripe. Includes an analytics dashboard.

Django Matt features: `APIController`, `throttling`, `analytics`, `billing` (Stripe metered), `tasks` (Celery), `jwt_required`, `multitenancy`.

### plugins/

Three installable packages that extend django-matt with third-party service integrations:

| Plugin | Purpose |
|--------|---------|
| `django-matt-clerk-auth` | Verifies Clerk session JWTs, syncs Clerk users to Django, handles Clerk webhook events, emits `clerk.*` events on the event bus |
| `django-matt-resend` | Drop-in Django email backend that sends transactional email via Resend API; supports templates and batch sending |
| `django-matt-stripe-webhooks` | Auto-registers a Stripe webhook endpoint, verifies signatures, dispatches to typed handlers via `@on_stripe_event`, emits `stripe.*` events on the event bus |

---

## Prerequisites

All examples require:

```bash
# Python package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install django-matt from the repo root (editable)
cd /path/to/django-matt
uv add -e .
```

Examples with a database need PostgreSQL and/or Redis (via Docker):

```bash
# Inside any example directory that has a docker-compose.yml
make docker-up
```

Frontend examples (`blog-app/frontend`, `portfolio-frontend`) use `bun`:

```bash
brew install oven-sh/bun/bun  # macOS
# or: curl -fsSL https://bun.sh/install | bash
```

---

## Common Setup Steps

Most directory-based examples follow this pattern:

```bash
cd examples/<name>
make install       # uv sync + install deps
make docker-up     # start Postgres + Redis (if needed)
make migrate       # uv run python manage.py migrate
make seed          # load sample data
make run           # start dev server at http://localhost:8000
# Docs: http://localhost:8000/api/docs
```

For ASGI-only examples (ai-chat, multitenant-saas) that have no Makefile:

```bash
cd examples/<name>
uv run python manage.py migrate
uv run uvicorn <project>.asgi:application --reload
```

---

## Service Layer Pattern

All examples follow the thin controller + service pattern: controllers parse requests and return responses; services own the business logic and ORM operations.

```python
class PostService(CRUDService["Post"]):
    model = Post

    def get_queryset(self):
        return super().get_queryset().select_related("author", "category").prefetch_related("tags")


class PostController(APIController):
    prefix = "/posts"
    tags = ["Posts"]

    def __init__(self):
        self.service = PostService()
        super().__init__()

    @api.get("/")
    async def list_posts(self, request):
        items, total = await self.service.list(status="published")
        return {"items": items, "total": total}

    @api.post("/")
    async def create_post(self, request, data: PostCreateSchema):
        return await self.service.create(data.model_dump(), author=request.user)
```

---

## TypeScript Codegen

The `blog-app` example includes committed `sync_types` output. Generated TypeScript types live in `blog-app/frontend/src/types/generated.ts`. To regenerate:

```bash
cd examples/blog-app/api
python manage.py sync_types --target typescript --output ../frontend/src/types/generated.ts
```

The typegen handles `X | None` unions, `EmailStr`, nested schemas, paginated list wrappers, and Zod validation schema generation.

---

## Additional Resources

- [Django Matt README](../README.md) — framework overview and quick start
- [docs/recipes/](../docs/recipes/) — 9 cookbook recipes (auth, uploads, tasks, pagination, tenancy, webhooks, rate-limiting, testing, frontend)
- [docs/migrations/](../docs/migrations/) — migration guides from DRF, FastAPI, and Django Ninja
- [docs/examples/](../docs/examples/) — inline code examples for CRUD, auth, features, and task management
