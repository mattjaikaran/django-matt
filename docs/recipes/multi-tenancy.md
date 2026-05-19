# Multi-Tenancy

Organization/Team/Membership models, per-tenant query isolation, middleware, and decorators.

---

## Models

```
Organization  ──< Membership >── User
     │
     └──< Team ──< TeamMembership >── User
```

- A **User** belongs to one or more **Organizations** via **Membership**.
- An **Organization** contains one or more **Teams**.
- A **User** joins a **Team** via **TeamMembership** (requires parent `Membership`).

### Roles

`MembershipRole` (string enum): `owner` > `admin` > `member` > `viewer`

---

## Setup

### Migrations

```python
INSTALLED_APPS = [
    ...
    "django_matt.multitenancy",
]
```

```bash
python manage.py migrate
```

### Middleware

```python
MIDDLEWARE = [
    ...
    "django_matt.multitenancy.middleware.TenantMiddleware",     # sync
    # or
    "django_matt.multitenancy.middleware.TenantMiddlewareAsync", # async
]
```

The middleware resolves the tenant from (in order):

1. `X-Organization-ID` / `X-Organization-Slug` request headers
2. URL params
3. Session
4. First active membership of the authenticated user

Sets `request.organization` and `request.tenant`.

### Settings

```python
DJANGO_MATT_MULTITENANCY = {
    "TENANT_HEADER_ID": "X-Organization-ID",
    "TENANT_HEADER_SLUG": "X-Organization-Slug",
    "INVITATION_EXPIRY_DAYS": 7,
    "TENANT_REQUIRED_PATHS": [],    # paths that 404 without a tenant
    "TENANT_EXEMPT_PATHS": ["/auth/", "/admin/"],
}
```

---

## Working With Organizations

### Create

```python
from django_matt.multitenancy.utils import create_organization_with_owner

org = await acreate_organization_with_owner(
    name="Acme Corp",
    slug="acme",
    owner=request.user,
)
```

### Members

```python
# Add member
membership = org.add_member(user, role="member")

# Check membership
if org.is_member(user):
    role = org.get_member_role(user)  # "member"

# List members by role
admins = org.get_admins()    # QuerySet[Membership]
owners = org.get_owners()

# Remove
org.remove_member(user)
```

### Ownership transfer

```python
from django_matt.multitenancy.utils import transfer_ownership

ok = transfer_ownership(org, current_owner=user_a, new_owner=user_b)
```

---

## Working With Teams

```python
from django_matt.multitenancy.utils import create_team_with_members

team = create_team_with_members(
    organization=org,
    name="Engineering",
    slug="engineering",
    members=[(user_a, "admin"), (user_b, "member")],
)

# Standard membership operations
team.add_member(user_c, role="member")
team.remove_member(user_c)
if team.is_member(user_c):
    ...
```

---

## Per-Tenant Query Isolation

Always scope queries to the current organization. The simplest pattern:

```python
class ProjectController(APIController):
    prefix = "/projects"

    @get("/")
    @jwt_required
    async def list(self, request):
        org = request.organization
        if org is None:
            return self.error("Organization required", status=400)
        projects = Project.objects.filter(organization=org)
        ...
```

### Using context vars (outside request scope)

```python
from django_matt.multitenancy.middleware import get_current_tenant, set_current_tenant, clear_current_tenant

org = get_current_tenant()     # set by middleware on every request

# In background tasks or signal handlers where middleware isn't active:
set_current_tenant(org)
try:
    do_work()
finally:
    clear_current_tenant()
```

---

## Access Control Decorators

All decorators support both sync and async views.

```python
from django_matt.multitenancy.decorators import (
    requires_organization,     # 400 if no tenant set
    requires_org_membership,   # 403 if not a member
    requires_org_role,         # 403 if role doesn't match
    requires_org_admin,        # 403 if not owner/admin
    requires_org_owner,        # 403 if not owner
    requires_min_org_role,     # 403 if role below threshold
    requires_team_membership,  # 403 if not in team
)

@get("/{id}")
@jwt_required
@requires_org_membership
async def get_project(self, request, id: int):
    project = await Project.objects.aget(id=id, organization=request.organization)
    return ProjectSchema.from_orm(project)

@post("/settings")
@jwt_required
@requires_org_admin
async def update_settings(self, request):
    ...

@delete("/")
@jwt_required
@requires_org_owner
async def delete_org(self, request):
    ...

@post("/deploy")
@jwt_required
@requires_min_org_role("member")
async def deploy(self, request):
    ...
```

---

## Invitations

```python
from django_matt.multitenancy.models import Invitation

# Create invitation (token generated automatically)
invite = await Invitation.objects.acreate(
    organization=org,
    email="bob@example.com",
    role="member",
    invited_by=request.user,
)
token = invite.token  # 32-byte URL-safe string

# Build invite URL and send email
invite_url = f"https://app.example.com/invite/{token}"

# Accept
result = await invite.accept(user=bob)

# Decline / revoke / resend
await invite.decline()
await invite.revoke()
await invite.resend()
```

Invitations expire after `INVITATION_EXPIRY_DAYS` (default 7). `invite.is_expired` and `invite.can_accept` are sync properties.

---

## Utility Functions

```python
from django_matt.multitenancy.utils import (
    get_user_organizations,     # QuerySet[Organization]
    get_user_teams,             # QuerySet[Team], optional org filter
    get_organization_members,   # QuerySet[Membership], optional role filter
    user_is_org_admin,          # bool (owner OR admin)
    user_is_org_owner,          # bool
    user_has_org_permission,    # bool (role priority check)
    # async variants
    auser_is_org_admin,
    auser_is_org_owner,
    acreate_organization_with_owner,
)

orgs = get_user_organizations(user)
teams = get_user_teams(user, organization=org)
members = get_organization_members(org, role="admin")

if await auser_is_org_admin(user, org):
    ...
```

---

## Schemas

```python
from django_matt.multitenancy.schemas import (
    OrganizationCreate, OrganizationUpdate, OrganizationResponse,
    TeamCreate, TeamUpdate, TeamResponse,
    MembershipCreate, MembershipUpdate, MembershipResponse,
    InvitationCreate, InvitationResponse, InvitationAcceptRequest,
    TenantContext,   # has_organization, has_team
)
```

---

## Full Controller Example

```python
from django_matt.core.controller import APIController
from django_matt.core.router import get, post, delete
from django_matt.auth.decorators import jwt_required
from django_matt.multitenancy.decorators import requires_org_membership, requires_org_admin
from django_matt.multitenancy.schemas import OrganizationResponse

class OrgController(APIController):
    prefix = "/orgs"

    @get("/me")
    @jwt_required
    @requires_org_membership
    async def current(self, request) -> OrganizationResponse:
        return OrganizationResponse.from_orm(request.organization)

    @post("/{org_id}/members")
    @jwt_required
    @requires_org_admin
    async def invite(self, request, org_id: str):
        body = await request.json()
        # create invitation, send email ...
        return {"invited": body["email"]}

    @delete("/{org_id}")
    @jwt_required
    @requires_org_owner
    async def delete_org(self, request, org_id: str):
        await request.organization.adelete()
        return {"deleted": True}
```
