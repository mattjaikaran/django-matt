# Multi-Tenancy Overview

Build B2B applications with organizations, teams, and role-based access.

## Features

- **Organizations** - Top-level tenant isolation
- **Teams** - Sub-groups within organizations
- **Memberships** - User-organization relationships with roles
- **Invitations** - Invite users to organizations
- **Middleware** - Automatic tenant context

## Quick Start

```python
from django_matt.multitenancy import (
    OrganizationController,
    TeamController,
    MembershipController,
)

api.register_controller(OrganizationController)
api.register_controller(TeamController)
api.register_controller(MembershipController)
```

## Models

```python
from django_matt.multitenancy import Organization, Team, Membership, Invitation

# Organization
org = await Organization.objects.acreate(
    name="Acme Inc",
    slug="acme",
)

# Team
team = await Team.objects.acreate(
    organization=org,
    name="Engineering",
)

# Membership
membership = await Membership.objects.acreate(
    user=user,
    organization=org,
    role="admin",
)
```

## Middleware

```python
# settings.py
MIDDLEWARE = [
    "django_matt.multitenancy.TenantMiddleware",
]
```

Access in views:

```python
@api.get("/data")
async def get_data(request):
    org = request.org  # Current organization
    return await Data.objects.filter(organization=org)
```

## See Also

- [Organizations](organizations.md)
- [Teams](teams.md)
