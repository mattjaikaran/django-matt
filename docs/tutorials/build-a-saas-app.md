# Build a Multi-Tenant SaaS API

Build a B2B SaaS backend with organization-level tenant isolation,
team management, role-based access control, Stripe billing, and
per-tenant feature flags.

## Prerequisites

- Completed [Build a REST API](build-a-rest-api.md) tutorial
- PostgreSQL (multi-tenancy uses UUID PKs and JSON fields)
- A Stripe account (test mode) for the billing section

## 1. Scaffold the Project

```bash
python manage.py startapi saas_app --template b2b --auth jwt --docker
```

Or add the modules to an existing project:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "django_matt",
    "django_matt.multitenancy",
    "django_matt.billing",
    "django_matt.flags",
]

MIDDLEWARE = [
    # ...
    "django_matt.auth.middleware.JWTAuthenticationMiddlewareAsync",
    "django_matt.multitenancy.TenantMiddleware",
]
```

Run migrations to create the multi-tenancy tables:

```bash
python manage.py migrate
```

## 2. Multi-Tenancy Models

Django Matt provides four core models in `django_matt.multitenancy`:

### Organization

The top-level tenant boundary. All data isolation happens at this level.

```python
from django_matt.multitenancy import Organization
```

Key fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `UUIDField` (PK) | Auto-generated UUID |
| `name` | `CharField(255)` | Display name |
| `slug` | `SlugField(100)` | URL-safe identifier (unique) |
| `description` | `TextField` | Optional description |
| `logo_url` | `URLField` | Optional logo |
| `settings` | `JSONField` | Org-specific key-value config |
| `is_active` | `BooleanField` | Soft disable |
| `created_at` | `DateTimeField` | Auto-set |
| `updated_at` | `DateTimeField` | Auto-set |

### Membership

Links users to organizations with a role.

```python
from django_matt.multitenancy.models import Membership, MembershipRole

# MembershipRole is a str Enum:
#   OWNER  = "owner"   (priority 100)
#   ADMIN  = "admin"   (priority 75)
#   MEMBER = "member"  (priority 50)
#   VIEWER = "viewer"  (priority 25)
```

### Team

Groups users within an organization:

```python
from django_matt.multitenancy import Team
```

### Invitation

Invite new users with a role and optional team:

```python
from django_matt.multitenancy.models import Invitation, InvitationStatus

# InvitationStatus: PENDING, ACCEPTED, DECLINED, EXPIRED, REVOKED
```

## 3. Tenant Middleware

`TenantMiddleware` resolves the current organization from each request
and stores it in a `contextvars.ContextVar`.

Resolution order:

1. `X-Organization-ID` header
2. `X-Organization-Slug` header
3. `org_slug` URL parameter
4. Session default
5. User's first organization (fallback)

Access the current tenant anywhere:

```python
from django_matt.multitenancy.middleware import get_current_tenant

async def my_view(request):
    org = get_current_tenant()
    if org is None:
        return {"error": "No organization context"}
    return {"org": org.name}
```

## 4. Tenant-Scoped Models

Scope your own models to the current organization:

```python
# saas_app/models.py
import uuid
from django.db import models


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "django_matt_multitenancy.Organization",
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
```

### Auto-scope queries

Create a mixin that filters by the current tenant:

```python
# saas_app/mixins.py
from django_matt.multitenancy.middleware import get_current_tenant


class TenantScopedMixin:
    """Mixin for ViewSets that auto-filters by current organization."""

    async def before_list(self, request, queryset):
        org = get_current_tenant()
        if org:
            return queryset.filter(organization=org)
        return queryset.none()

    async def before_create(self, request, data):
        org = get_current_tenant()
        if org:
            data["organization_id"] = str(org.id)
        return data
```

## 5. Role-Based Access Control

### Controller-level RBAC

Use the multitenancy decorators to enforce roles:

```python
from django_matt import APIController
from django_matt.multitenancy.decorators import (
    requires_org_membership,
    requires_org_admin,
    requires_org_owner,
    requires_min_org_role,
)
from .api import api


@api.controller("/projects", tags=["Projects"])
class ProjectController(APIController):

    @api.get("/")
    @requires_org_membership
    async def list_projects(self, request):
        """Any org member can list projects."""
        org = get_current_tenant()
        projects = []
        async for p in Project.objects.filter(organization=org):
            projects.append({"id": str(p.id), "name": p.name})
        return {"items": projects}

    @api.post("/")
    @requires_min_org_role("admin")
    async def create_project(self, request, data: ProjectCreateSchema):
        """Only admins and above can create projects."""
        org = get_current_tenant()
        project = await Project.objects.acreate(
            organization=org,
            **data.model_dump(),
        )
        return {"id": str(project.id), "name": project.name}

    @api.delete("/{project_id}")
    @requires_org_owner
    async def delete_project(self, request, project_id: str):
        """Only owners can delete projects."""
        project = await Project.objects.aget(id=project_id)
        await project.adelete()
        return {"success": True}
```

### Built-in Controllers

Register the provided CRUD controllers for managing tenants:

```python
from django_matt.multitenancy import (
    OrganizationController,
    TeamController,
    MembershipController,
    InvitationController,
)

api.register_controller(OrganizationController, prefix="/orgs")
api.register_controller(TeamController, prefix="/orgs/{org_id}/teams")
api.register_controller(MembershipController, prefix="/orgs/{org_id}/members")
api.register_controller(InvitationController, prefix="/orgs/{org_id}/invitations")
```

## 6. Stripe Billing

### Configuration

```python
# settings.py
DJANGO_MATT_BILLING = {
    "ENABLED": True,
    "DEFAULT_PROVIDER": "stripe",
    "CURRENCY": "usd",
    "STRIPE": {
        "SECRET_KEY": "sk_test_...",
        "PUBLISHABLE_KEY": "pk_test_...",
        "WEBHOOK_SECRET": "whsec_...",
    },
}
```

### Register billing controllers

```python
from django_matt.billing import BillingController, WebhookController

api.register_controller(BillingController, prefix="/billing")
api.register_controller(WebhookController, prefix="/billing/webhooks")
```

This gives you:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/billing/checkout` | POST | Create a Stripe Checkout session |
| `/billing/portal` | POST | Create a customer portal session |
| `/billing/subscription` | GET | Get current subscription |
| `/billing/webhooks/stripe` | POST | Stripe webhook receiver |

### Use the provider directly

```python
from django_matt.billing import get_provider

provider = get_provider("stripe")

# Create a checkout session
checkout = await provider.create_checkout_session(
    price_id="price_1234",
    success_url="https://app.example.com/billing/success",
    cancel_url="https://app.example.com/billing/cancel",
    customer_email=request.user.email,
    metadata={"org_id": str(org.id)},
)

# Returns CheckoutSessionData with:
#   - checkout.id (Stripe session ID)
#   - checkout.url (redirect URL for the user)
```

### Webhook handling

The `WebhookController` verifies Stripe signatures and dispatches events.
Hook into billing events with the event bus:

```python
# saas_app/events.py
from django_matt.events import on, Event


@on("billing.subscription.created")
async def handle_subscription_created(event: Event):
    org_id = event.metadata.get("org_id")
    plan = event.metadata.get("plan")
    # Activate features for the org
    ...


@on("billing.subscription.canceled")
async def handle_subscription_canceled(event: Event):
    org_id = event.metadata.get("org_id")
    # Downgrade to free tier
    ...
```

## 7. Feature Flags Per Tenant

### Configuration

```python
# settings.py
FEATURE_FLAG_BACKEND = "database"
FEATURE_FLAG_BACKEND_SETTINGS = {
    "database": {
        "cache_timeout": 60,
        "use_cache": True,
    },
}
```

### Check flags

```python
from django_matt.flags import feature_enabled, get_variant, FlagContext

# Simple boolean check
if feature_enabled("advanced_analytics", user=request.user):
    return advanced_dashboard()

# With organization context
ctx = FlagContext.from_request(request)
if ctx.is_enabled("custom_branding"):
    return branded_response()

# A/B test variant
variant = get_variant("onboarding_flow", user=request.user)
if variant == "treatment_a":
    return new_onboarding()
```

### Decorator-based flags

```python
from django_matt.flags import feature_flag, requires_flag

@api.get("/analytics")
@requires_flag("advanced_analytics")
async def analytics_dashboard(request):
    """Only accessible when advanced_analytics flag is enabled."""
    ...

@api.get("/search")
@feature_flag("new_search", default=False)
async def search(request):
    """Falls back to old behavior if flag is disabled."""
    ...
```

### Flag management API

Register the controller for CRUD operations on flags:

```python
from django_matt.flags import FlagController

api.register_controller(FlagController, prefix="/flags")
```

Create a flag targeting a specific organization:

```bash
http POST http://localhost:8000/api/flags/ \
    name="advanced_analytics" \
    flag_type="boolean" \
    enabled:=true \
    targeting:='{"organizations": ["org-uuid-here"]}' \
    Authorization:"Bearer <admin-token>"
```

## 8. Background Tasks with tasks_native

Django Matt ships a native task engine (`tasks_native`) that does not
require Celery or an external broker for most use cases. Use it for
deferred work like sending welcome emails, syncing billing state, or
provisioning new tenants.

### Define a task

```python
# saas_app/tasks.py
from django_matt.tasks_native import task
from pydantic import BaseModel


class WelcomeEmailPayload(BaseModel):
    user_id: int
    org_id: str


@task(
    name="saas_app.send_welcome_email",
    retry_policy={"max_attempts": 3, "backoff": "exponential"},
)
async def send_welcome_email(payload: WelcomeEmailPayload) -> None:
    """Send a welcome email when a user joins an organization."""
    from django.contrib.auth import get_user_model
    from django_matt.email import send_email

    User = get_user_model()
    user = await User.objects.aget(pk=payload.user_id)
    await send_email(
        to=user.email,
        template="welcome",
        context={"user": user, "org_id": payload.org_id},
    )
```

### Enqueue from a controller

```python
# saas_app/controllers.py
from .tasks import send_welcome_email, WelcomeEmailPayload

@api.post("/")
@requires_min_org_role("admin")
async def create_project(self, request, data: dict):
    org = get_current_tenant()
    project = await Project.objects.acreate(
        organization=org,
        name=data["name"],
        description=data.get("description", ""),
    )
    # Enqueue non-blocking background task
    await send_welcome_email.enqueue(
        WelcomeEmailPayload(
            user_id=request.user.id,
            org_id=str(org.id),
        )
    )
    return {"id": str(project.id), "name": project.name}
```

### Manage tasks

```bash
python manage.py matt_tasks list            # list registered tasks
python manage.py matt_tasks run saas_app.send_welcome_email '{}'
python manage.py matt_tasks status          # queue status
```

Tasks are visible in the Django Unfold admin dashboard when
`django_matt.tasks_native` is in `INSTALLED_APPS`.

## 9. Putting It All Together

```python
# settings.py
from datetime import timedelta

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django_matt",
    "django_matt.multitenancy",
    "django_matt.billing",
    "django_matt.flags",
    "saas_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django_matt.auth.middleware.JWTAuthenticationMiddlewareAsync",
    "django_matt.multitenancy.TenantMiddleware",
]

DJANGO_MATT_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

DJANGO_MATT_BILLING = {
    "ENABLED": True,
    "DEFAULT_PROVIDER": "stripe",
    "CURRENCY": "usd",
    "STRIPE": {
        "SECRET_KEY": "sk_test_...",
        "PUBLISHABLE_KEY": "pk_test_...",
        "WEBHOOK_SECRET": "whsec_...",
    },
}

FEATURE_FLAG_BACKEND = "database"
```

```python
# api.py
from django_matt import DjangoMattAPI
from django_matt.auth import AuthController
from django_matt.multitenancy import (
    OrganizationController,
    MembershipController,
    InvitationController,
)
from django_matt.billing import BillingController, WebhookController
from django_matt.flags import FlagController

api = DjangoMattAPI(
    title="SaaS API",
    version="1.0.0",
    description="Multi-tenant SaaS backend",
)

# Auth
api.register_controller(AuthController, prefix="/auth")

# Multi-tenancy
api.register_controller(OrganizationController, prefix="/orgs")
api.register_controller(MembershipController, prefix="/orgs/{org_id}/members")
api.register_controller(InvitationController, prefix="/orgs/{org_id}/invitations")

# Billing
api.register_controller(BillingController, prefix="/billing")
api.register_controller(WebhookController, prefix="/billing/webhooks")

# Feature flags
api.register_controller(FlagController, prefix="/flags")
```

```python
# saas_app/models.py
import uuid
from django.db import models


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "django_matt_multitenancy.Organization",
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

```python
# saas_app/controllers.py
from django_matt import APIController
from django_matt.multitenancy.middleware import get_current_tenant
from django_matt.multitenancy.decorators import (
    requires_org_membership,
    requires_min_org_role,
    requires_org_owner,
)
from django_matt.flags import feature_enabled
from .api import api
from .models import Project


@api.controller("/projects", tags=["Projects"])
class ProjectController(APIController):

    @api.get("/")
    @requires_org_membership
    async def list_projects(self, request):
        org = get_current_tenant()
        projects = []
        async for p in Project.objects.filter(organization=org):
            projects.append({"id": str(p.id), "name": p.name})

        response = {"items": projects}

        if feature_enabled("advanced_analytics", user=request.user):
            response["analytics"] = {"total": len(projects)}

        return response

    @api.post("/")
    @requires_min_org_role("admin")
    async def create_project(self, request, data: dict):
        org = get_current_tenant()
        project = await Project.objects.acreate(
            organization=org,
            name=data["name"],
            description=data.get("description", ""),
        )
        return {"id": str(project.id), "name": project.name}

    @api.delete("/{project_id}")
    @requires_org_owner
    async def delete_project(self, request, project_id: str):
        project = await Project.objects.aget(id=project_id)
        await project.adelete()
        return {"success": True}
```

## 10. Deployment

Generate a production Dockerfile:

```bash
python manage.py deploy --platform fly
```

Or use the deployment module for other platforms:

```bash
python manage.py deploy --platform railway
python manage.py deploy --platform render
```

Key production settings:

```python
# Production ASGI
# gunicorn config.asgi:application --worker-class uvicorn.workers.UvicornWorker

# Connection pooling (enabled by default with psycopg3)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "OPTIONS": {
            "pool": True,
        },
    }
}
```

## Next Steps

- [Add Real-Time Features](realtime-features.md) -- WebSockets and push notifications
- [Build an AI/LLM Streaming API](ai-streaming-api.md) -- streaming endpoints with SSE
- [Testing Your Django Matt App](testing-guide.md) -- test multi-tenant flows
