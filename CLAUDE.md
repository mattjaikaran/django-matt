# Django Matt

> Internal Django meta-framework replacing Django Ninja + extras with one cohesive library.

## Stack

- Python 3.12+ / Django 5.2+ / Pydantic 2.0+ / `uv` / `bun`
- Async-first, type hints everywhere, ruff for lint/format

## Structure

```
django_matt/
├── api.py              # MattAPI entry point
├── core/               # Router, Controller, Schema, Errors
├── auth/               # JWT, magic links, RBAC, OAuth, SSO, Passkeys, API keys
├── views/              # Composable CRUD views (List, Create, Read, Update, Delete)
├── permissions/        # IsAuthenticated, IsAdmin, IsOwner, HasRole, decorators
├── openapi/            # Swagger/ReDoc generation
├── config/             # Modular configuration
├── db/                 # PostgreSQL, pgvector
├── multitenancy/       # Organization, Team, Membership (B2B)
├── typegen/            # TypeScript/Swift code generation
├── testing/            # Test client, factories, assertions
├── utils/              # Performance (orjson, caching, streaming, benchmarks)
├── admin/              # Django Unfold integration, dashboards, widgets
├── billing/            # Stripe, PayPal, Polar
├── negotiation/        # Content negotiation (JSON, XML, CSV, YAML, MsgPack)
├── websockets/         # Consumers, auth middleware, presence, routing
├── flags/              # Feature flags (DB, Redis, LaunchDarkly, Unleash)
├── analytics/          # Event tracking, sessions, funnels, multiple backends
├── experiments/        # A/B testing, multi-armed bandits, statistical analysis
├── graphql/            # Strawberry-based schema generation, dataloaders
├── inspector/          # Request/response capture for dev
├── messaging/          # Conversations, attachments, WebSocket transport
├── notifications/      # In-app, email, push (FCM/APNs), SMS, webhooks
├── email/              # SendGrid, Mailgun, SES, SMTP with templates
├── ai/                 # LLM integration, embeddings, RAG, IDE context gen
├── ml/                 # Vector storage, structured output
├── files/              # Upload, S3/R2/MinIO storage backends
├── tasks/              # Background tasks (Celery, Dramatiq, Django-Q)
├── tasks_native/       # Native task engine (Django 6.0+, Unfold dashboard) [Stage 17A]
├── audits/             # AI-assisted codebase audits (security, perf, bundle) [Stage 17B]
├── audit/              # Audit logging, soft delete
├── htmx/               # HTMX helpers, Livewire-style reactivity
├── components/         # Backend-served component system
├── cli/                # Rich CLI (matt info, doctor, routes, models, new)
├── deployment/         # Docker, Fly.io, Railway, Render, AWS, Hetzner
├── observability/      # Logging, metrics, tracing
├── throttling/         # Rate limiting
├── versioning/         # API versioning strategies
├── pagination/         # PageNumber, LimitOffset, Cursor
├── filtering/          # Django filter backend, search, ordering
├── di/                 # Dependency injection container
├── interceptors/       # Route-scoped middleware (before/after hooks, @intercept)
├── streaming/          # SSE responses, NDJSON streaming, heartbeat helpers
├── events/             # Async event bus (pub/sub, @on decorator, InMemory/Redis)
├── exceptions/         # Exception filters (ExceptionFilter, @catch, global registry)
├── serialization/      # Group-based field visibility (Grouped, Secret, @serialize_for)
├── secrets/            # Multi-backend secrets (env, Vault, AWS SM, GCP SM, dotenv)
├── introspection/      # Health checks, infra reporting, readiness/liveness probes
├── rpc/                # Typed HTTP client generation (Python + TypeScript)
├── modules/            # Plugin system with dependency resolution and lifecycle hooks
├── cqrs/               # Command/Query buses, domain events, bus middleware
├── migration_tools/    # SQL baselines, parallel execution, profiling, squashing
├── slim.py             # Slim mode config (full/slim/minimal/auto module loading)
├── loader.py           # Lazy/deferred module loading (LazyModuleProxy, DeferredLoader)
└── management/commands/ # startapi, config, sync_types, generate_crud, deploy
```

## Key Patterns

```python
# Controller
class UserController(APIController):
    prefix = "/users"
    tags = ["Users"]
    permission_classes = [IsAuthenticated]

    @api.get("/")
    async def list_users(self): ...

    @api.post("/")
    async def create_user(self, data: UserCreateSchema) -> UserSchema: ...

# Register controller
api.register_controller(UserController)

# CRUD ViewSet
class ProductViewSet(APIViewSet):
    api = api
    model = Product
    list = ListView()
    create = CreateView()
    read = ReadView()
    update = UpdateView()
    delete = DeleteView()

# Auth decorators
@jwt_required
@jwt_optional
@requires_role("admin")
@requires_permission("can_edit")
```

## CLI Commands

```bash
python manage.py startapi myproject --template b2b --auth jwt --docker
python manage.py generate_crud myapp.Model --full  # controller, schema, service, admin, tests
python manage.py sync_types --target typescript --output frontend/types
python manage.py generate_ai_context --format all
python manage.py config init
python manage.py deploy --platform fly

# Migration acceleration (for large codebases)
python manage.py matt_baseline create v1.0.0      # create SQL baseline
python manage.py matt_baseline load v1.0.0        # load on fresh DB
python manage.py matt_migrate --stats             # project statistics
python manage.py matt_migrate --profile           # profile pending migrations
python manage.py matt_migrate --parallel          # run in parallel waves
python manage.py matt_squash myapp 0001 0042      # squash migrations

# Native task engine (Stage 17A)
python manage.py matt_tasks list                  # list registered tasks
python manage.py matt_tasks run send_email '{}'   # run task manually
python manage.py matt_tasks status                # queue status
python manage.py matt_tasks purge --older-than 30d

# AI-assisted audits (Stage 17B)
python manage.py matt_audit                       # run all audits
python manage.py matt_audit security --level strict
python manage.py matt_audit bundle                # bundle size analysis
python manage.py matt_audit context --for claude  # generate LLM context
```

## Testing

```bash
pytest tests/                          # all tests
pytest tests/ --cov=django_matt        # with coverage
pytest tests/test_auth.py -v           # specific file
```

## Common Task Paths

| Task | Key Files |
|------|-----------|
| Auth | `auth/jwt.py`, `auth/controllers.py`, `auth/schemas.py`, `auth/rbac/`, `auth/oauth/`, `auth/sso/`, `auth/passkeys/` |
| Multi-tenancy | `multitenancy/models.py`, `multitenancy/controllers.py`, `multitenancy/middleware.py` |
| Performance | `utils/performance.py` (caching, serialization, benchmarks, query optimization) |
| Billing | `billing/providers.py`, `billing/controllers.py`, `billing/models.py` |
| Feature flags | `flags/models.py`, `flags/backends.py`, `flags/decorators.py` |
| Analytics | `analytics/tracker.py`, `analytics/backends.py`, `analytics/aggregations.py` |
| Experiments | `experiments/models.py`, `experiments/assignment.py`, `experiments/analysis.py` |
| Interceptors | `interceptors/base.py`, `interceptors/builtins.py`, `interceptors/decorators.py`, `interceptors/chain.py` |
| Streaming/SSE | `streaming/sse.py`, `streaming/response.py`, `streaming/decorators.py`, `streaming/helpers.py` |
| Events | `events/bus.py`, `events/decorators.py`, `events/middleware.py`, `events/backends.py` |
| Exceptions | `exceptions/filters.py`, `exceptions/decorators.py`, `exceptions/builtins.py`, `exceptions/registry.py` |
| Serialization | `serialization/groups.py`, `serialization/fields.py`, `serialization/decorators.py` |
| Secrets | `secrets/manager.py`, `secrets/backends.py`, `secrets/fields.py`, `secrets/rotation.py` |
| Introspection | `introspection/checks.py`, `introspection/endpoints.py`, `introspection/registry.py` |
| RPC | `rpc/client.py`, `rpc/proxy.py`, `rpc/auth.py`, `rpc/generator.py` |
| CQRS | `cqrs/commands.py`, `cqrs/queries.py`, `cqrs/events.py`, `cqrs/middleware.py` |
| Modules | `modules/base.py`, `modules/registry.py`, `modules/loader.py`, `modules/hooks.py` |
| Migrations | `migration_tools/baseline.py`, `migration_tools/parallel.py`, `migration_tools/stats.py`, `migration_tools/squash.py` |
| Native Tasks | `tasks_native/core.py`, `tasks_native/scheduling.py`, `tasks_native/retry.py`, `tasks_native/admin/` |
| Audits | `audits/framework.py`, `audits/bundle.py`, `audits/prompts/`, `audits/agents/` |
| Slim mode | `slim.py`, `loader.py` |

## Known Issues

No known issues. Phase 1 Correctness Audit (Plans 01-01 through 01-03) resolved all previously tracked issues:
- DJANGO_ALLOW_ASYNC_UNSAFE=true was removed; all sync ORM calls in async handlers converted (Plan 01-01)
- utils/errors.py duplication eliminated; canonical import is django_matt.core.errors (Plan 01-02)
- AsyncAPITestClient.force_authenticate() uses acreate_access_token() (Plan 01-01)

## Important Files

- `ROADMAP.md` — 17-stage development plan (Stage 17: Native Tasks & AI Audits in progress)
- `tasks/todo.md` — Active tasks and priorities
- `pyproject.toml` — deps, build config, tool settings
- `Makefile` — comprehensive dev commands
- `docs/` — feature documentation
- `examples/` — demo apps (todo, ecommerce, saas-starter, realtime-chat)
