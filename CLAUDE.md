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
└── management/commands/ # startapi, config, sync_types, generate_crud, deploy
```

## Key Patterns

```python
# Controller
@api.controller("/users", tags=["Users"])
class UserController(APIController):
    permission_classes = [IsAuthenticated]

    @api.get("/")
    async def list_users(self): ...

    @api.post("/")
    async def create_user(self, data: UserCreateSchema) -> UserSchema: ...

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

## Known Issues

- `conftest.py` sets `DJANGO_ALLOW_ASYNC_UNSAFE=true` globally, masking async/sync ORM bugs in tests
- `testing/client.py` `AsyncAPITestClient.force_authenticate()` calls sync `create_access_token()` — should use `acreate_access_token()`

## Important Files

- `ROADMAP.md` — 16-stage development plan (95%+ complete)
- `pyproject.toml` — deps, build config, tool settings
- `Makefile` — comprehensive dev commands
- `docs/` — feature documentation
- `examples/` — demo apps (todo, ecommerce, saas-starter, realtime-chat)
