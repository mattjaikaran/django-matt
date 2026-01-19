# Role-Based Access Control (RBAC)

Django Matt provides a flexible RBAC system with role hierarchies and permission inheritance.

## Overview

```mermaid
flowchart TB
    subgraph "Role Hierarchy"
        SUPER[Super Admin]
        ADMIN[Admin]
        MANAGER[Manager]
        MEMBER[Member]
        GUEST[Guest]
    end

    subgraph "Permissions"
        P1[users:read]
        P2[users:write]
        P3[users:delete]
        P4[admin:access]
        P5[billing:manage]
    end

    SUPER --> ADMIN
    ADMIN --> MANAGER
    MANAGER --> MEMBER
    MEMBER --> GUEST

    SUPER -.-> P1 & P2 & P3 & P4 & P5
    ADMIN -.-> P1 & P2 & P3 & P4
    MANAGER -.-> P1 & P2
    MEMBER -.-> P1
```

## Quick Start

### Configuration

```python
# settings.py
from django_matt.auth.rbac import Role, RBACConfig

DJANGO_MATT_RBAC = RBACConfig(
    roles=[
        Role(
            name="super_admin",
            level=100,
            permissions=["*"],  # All permissions
        ),
        Role(
            name="admin",
            level=80,
            permissions=[
                "users:*",
                "posts:*",
                "admin:access",
            ],
        ),
        Role(
            name="manager",
            level=60,
            permissions=[
                "users:read",
                "users:write",
                "posts:*",
            ],
        ),
        Role(
            name="member",
            level=40,
            permissions=[
                "users:read",
                "posts:read",
                "posts:write",
            ],
        ),
        Role(
            name="guest",
            level=20,
            permissions=[
                "posts:read",
            ],
        ),
    ],
    # Map Django groups to RBAC roles
    group_mapping={
        "Administrators": "admin",
        "Staff": "manager",
        "Users": "member",
    },
    # Default role for new users
    default_role="member",
)
```

### Using in Views

```python
from django_matt.auth.rbac import requires_role_hierarchy, requires_rbac_permission

# Require minimum role level
@api.get("/admin/users")
@requires_role_hierarchy("manager")  # manager or higher
async def list_users(request):
    return User.objects.all()

# Require specific permission
@api.delete("/users/{id}")
@requires_rbac_permission("users:delete")
async def delete_user(request, id: int):
    User.objects.filter(id=id).delete()
    return {"deleted": True}
```

## Role Hierarchy

Roles are organized by level, where higher levels inherit permissions from lower levels:

```python
from django_matt.auth.rbac import Role

roles = [
    # Highest level - full access
    Role(name="super_admin", level=100, permissions=["*"]),

    # Admin - most permissions
    Role(name="admin", level=80, permissions=[
        "users:*",
        "settings:*",
        "admin:access",
    ]),

    # Manager - team management
    Role(name="manager", level=60, permissions=[
        "users:read",
        "users:invite",
        "team:*",
    ]),

    # Member - standard access
    Role(name="member", level=40, permissions=[
        "users:read",
        "projects:*",
    ]),

    # Guest - limited access
    Role(name="guest", level=20, permissions=[
        "projects:read",
    ]),
]
```

### Permission Inheritance

When using `requires_role_hierarchy`, users with higher-level roles automatically pass the check:

```python
@requires_role_hierarchy("manager")
async def team_view(request):
    # Accessible by: manager, admin, super_admin
    # NOT accessible by: member, guest
    pass
```

## Permission Syntax

### Wildcards

```python
permissions = [
    "*",              # All permissions
    "users:*",        # All user permissions
    "posts:read",     # Specific permission
]
```

### Scoped Permissions

```python
permissions = [
    "users:read",
    "users:write",
    "users:delete",
    "posts:read",
    "posts:write",
    "posts:publish",
    "admin:access",
    "billing:manage",
]
```

## Utility Functions

### Check User Roles

```python
from django_matt.auth.rbac import (
    get_user_roles,
    user_has_role,
    user_has_any_role,
    user_has_all_roles,
    get_user_highest_role,
)

# Get all roles for a user
roles = get_user_roles(user)  # ["member", "manager"]

# Check specific role
if user_has_role(user, "admin"):
    print("User is admin")

# Check any of multiple roles
if user_has_any_role(user, ["admin", "manager"]):
    print("User can manage")

# Check all roles
if user_has_all_roles(user, ["member", "verified"]):
    print("User is verified member")

# Get highest role
highest = get_user_highest_role(user)  # Role object with highest level
```

### Check Permissions

```python
from django_matt.auth.rbac import (
    get_user_permissions,
    user_has_permission,
)

# Get all permissions (including from role hierarchy)
permissions = get_user_permissions(user)
# {"users:read", "posts:read", "posts:write", ...}

# Check specific permission
if user_has_permission(user, "users:delete"):
    # User can delete users
    pass

# Wildcard matching
# If user has "users:*", then user_has_permission(user, "users:read") is True
```

## Decorators

### requires_role_hierarchy

Requires the user to have a role at or above the specified level:

```python
from django_matt.auth.rbac import requires_role_hierarchy

@api.get("/admin/dashboard")
@requires_role_hierarchy("admin")
async def admin_dashboard(request):
    # Only admin and super_admin can access
    return {"stats": get_admin_stats()}

@api.get("/team/members")
@requires_role_hierarchy("manager")
async def team_members(request):
    # manager, admin, super_admin can access
    return Team.objects.get_members(request.user)
```

### requires_rbac_permission

Requires a specific permission (checks wildcards):

```python
from django_matt.auth.rbac import requires_rbac_permission

@api.post("/posts")
@requires_rbac_permission("posts:write")
async def create_post(request, data: PostCreate):
    return Post.objects.create(**data.dict())

@api.delete("/posts/{id}")
@requires_rbac_permission("posts:delete")
async def delete_post(request, id: int):
    Post.objects.filter(id=id).delete()
    return {"deleted": True}
```

## Integration with Django Groups

Map Django groups to RBAC roles for compatibility with existing systems:

```python
# settings.py
DJANGO_MATT_RBAC = RBACConfig(
    roles=[...],
    group_mapping={
        "Django Admins": "super_admin",
        "Staff": "admin",
        "Moderators": "manager",
        "Registered Users": "member",
    },
)
```

When a user belongs to a Django group, they automatically receive the mapped RBAC role.

## Multi-Tenant RBAC

For B2B applications with organization-scoped roles:

```python
from django_matt.auth.rbac import get_user_roles

# Get roles within an organization
org_roles = get_user_roles(user, organization=org)

# Check permission within organization
if user_has_permission(user, "billing:manage", organization=org):
    # User can manage billing for this org
    pass
```

### Organization Role Assignment

```python
from django_matt.multitenancy import Membership

# Assign role within organization
membership = Membership.objects.create(
    user=user,
    organization=org,
    role="admin",  # RBAC role name
)

# User now has admin permissions within this org
```

## Custom Permission Checks

For complex permission logic, create custom checks:

```python
from django_matt.auth.rbac import user_has_permission

def can_edit_post(user, post):
    """Check if user can edit a post."""
    # Owner can always edit
    if post.author == user:
        return True

    # Check RBAC permission
    if user_has_permission(user, "posts:edit_any"):
        return True

    # Check organization permission
    if post.organization:
        return user_has_permission(
            user,
            "posts:edit",
            organization=post.organization
        )

    return False
```

## Permission Middleware

Add middleware for automatic permission context:

```python
# settings.py
MIDDLEWARE = [
    ...
    'django_matt.auth.rbac.RBACMiddleware',
]
```

This adds `request.rbac` with helper methods:

```python
async def my_view(request):
    # Check permission
    if request.rbac.has_permission("posts:delete"):
        # Can delete
        pass

    # Get user's role
    role = request.rbac.highest_role

    # Get all permissions
    permissions = request.rbac.permissions
```

## Testing

```python
import pytest
from django_matt.auth.rbac import rbac_config

@pytest.fixture
def admin_user(user_factory):
    """Create a user with admin role."""
    user = user_factory()
    user.groups.add(Group.objects.get(name="Staff"))
    return user

def test_admin_access(client, admin_user):
    client.force_login(admin_user)
    response = client.get("/admin/dashboard")
    assert response.status_code == 200

def test_member_denied(client, member_user):
    client.force_login(member_user)
    response = client.get("/admin/dashboard")
    assert response.status_code == 403
```

## Best Practices

1. **Use role hierarchy for levels** - Don't duplicate permissions across roles
2. **Use wildcards sparingly** - Be explicit about permissions
3. **Scope permissions to resources** - Use `resource:action` format
4. **Map Django groups** - Integrate with existing auth systems
5. **Test permission boundaries** - Ensure users can't access unauthorized resources
6. **Document permissions** - Maintain a list of all permissions and their meanings
