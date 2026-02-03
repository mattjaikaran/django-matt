# Permissions

Django-matt provides a flexible permission system with class-based permissions and decorators for controlling access to API endpoints.

## Overview

Permissions are checked in order:

1. **View-level permissions**: `has_permission()` - Before any view logic
2. **Object-level permissions**: `has_object_permission()` - When accessing specific objects

## Quick Start

```python
from django_matt.permissions import IsAuthenticated, IsAdmin, IsOwner
from django_matt.views import APIViewSet

class ProductViewSet(APIViewSet):
    model = Product
    permission_classes = [IsAuthenticated]  # All endpoints require login

    list_products = ListView()
    create_product = CreateView()
    # ...
```

---

## Built-in Permission Classes

### AllowAny

Allows unrestricted access:

```python
from django_matt.permissions import AllowAny

class PublicViewSet(APIViewSet):
    permission_classes = [AllowAny]

    list_products = ListView()  # No authentication required
```

### IsAuthenticated

Requires authenticated users:

```python
from django_matt.permissions import IsAuthenticated

class ProtectedViewSet(APIViewSet):
    permission_classes = [IsAuthenticated]
```

**Response on denial:**
```json
{"detail": "Authentication required.", "code": "authentication_required"}
```
Status: 401 Unauthorized

### IsAdmin

Requires staff or superuser:

```python
from django_matt.permissions import IsAdmin

class AdminViewSet(APIViewSet):
    permission_classes = [IsAdmin]
```

### IsStaff

Requires `is_staff=True`:

```python
from django_matt.permissions import IsStaff

class StaffViewSet(APIViewSet):
    permission_classes = [IsStaff]
```

### IsSuperUser

Requires `is_superuser=True`:

```python
from django_matt.permissions import IsSuperUser

class SuperUserViewSet(APIViewSet):
    permission_classes = [IsSuperUser]
```

### IsOwner

Object-level permission checking ownership:

```python
from django_matt.permissions import IsAuthenticated, IsOwner

class TaskViewSet(APIViewSet):
    model = Task
    permission_classes = [IsAuthenticated, IsOwner]

    # Users can only access their own tasks
    list_tasks = ListView()
    read_task = ReadView()
    update_task = UpdateView()
    delete_task = DeleteView()
```

Checks these fields for ownership (in order):
- `user`
- `owner`
- `created_by`
- `author`

### IsAuthenticatedOrReadOnly

Read-only for anonymous, full access for authenticated:

```python
from django_matt.permissions import IsAuthenticatedOrReadOnly

class BlogViewSet(APIViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]

    list_posts = ListView()      # Anyone can read
    create_post = CreateView()   # Must be logged in
```

### IsAdminOrReadOnly

Read-only for non-admin, full access for admin:

```python
from django_matt.permissions import IsAdminOrReadOnly

class SettingsViewSet(APIViewSet):
    permission_classes = [IsAdminOrReadOnly]
```

---

## Role-Based Permissions

### HasRole

Check user roles/groups:

```python
from django_matt.permissions import HasRole

# Single role
manager_only = HasRole(roles=["manager"])

# Multiple roles (OR - any role matches)
editor_or_admin = HasRole(roles=["editor", "admin"])

class ContentViewSet(APIViewSet):
    permission_classes = [editor_or_admin]
```

Checks:
1. Django groups (`user.groups`)
2. Custom `role` field
3. Custom `roles` many-to-many

### HasPermission

Check Django permissions:

```python
from django_matt.permissions import HasPermission

# Single permission
can_publish = HasPermission(permissions=["blog.publish_post"])

# Multiple permissions (OR by default)
can_edit = HasPermission(permissions=["blog.change_post", "blog.add_post"])

# Require ALL permissions
full_access = HasPermission(
    permissions=["blog.change_post", "blog.delete_post"],
    require_all=True,
)
```

---

## Permission Decorators

### `@authenticated`

Require authentication for a single endpoint:

```python
from django_matt.permissions import authenticated

@api.get("/protected")
@authenticated
async def protected_view(request):
    return {"user": request.user.email}
```

### `@allow_any`

Mark endpoint as public when ViewSet has default permissions:

```python
from django_matt.permissions import allow_any, IsAuthenticated

class UserViewSet(APIViewSet):
    permission_classes = [IsAuthenticated]

    @api.get("/public")
    @allow_any
    async def public_info(request):
        return {"status": "ok"}
```

### `@requires_permission`

Check specific Django permissions:

```python
from django_matt.permissions import requires_permission

class TaskViewSet(APIViewSet):
    @api.delete("/{id}")
    @requires_permission("tasks.delete_task")
    async def delete_task(self, request, id: str):
        # Only users with tasks.delete_task can access
        pass

    @api.post("/")
    @requires_permission("tasks.add_task", "tasks.change_task")
    async def create_task(self, request):
        # User needs either permission
        pass
```

### `@requires_permissions`

Check multiple permissions with AND/OR logic:

```python
from django_matt.permissions import requires_permissions

# Require ALL permissions
@requires_permissions("blog.change_post", "blog.publish_post", require_all=True)
async def publish_post(request, id: str):
    pass

# Require ANY permission (default)
@requires_permissions("blog.change_post", "blog.delete_post", require_all=False)
async def manage_post(request, id: str):
    pass
```

### `@requires_role`

Check user roles:

```python
from django_matt.permissions import requires_role

@requires_role("manager", "admin")
async def approve_request(request):
    # Only managers and admins can access
    pass
```

### `@with_permissions`

Apply permission classes to a view:

```python
from django_matt.permissions import with_permissions, IsAuthenticated, IsOwner

@with_permissions(IsAuthenticated, IsOwner)
async def my_tasks(request):
    return Task.objects.filter(user=request.user)
```

---

## Custom Permission Classes

### Basic Custom Permission

```python
from django_matt.permissions import BasePermission

class IsProjectMember(BasePermission):
    """Check if user is a member of the project."""

    message = "You must be a member of this project."

    def has_permission(self, request, view=None):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return obj.project.members.filter(id=request.user.id).exists()
```

### Operation-Based Permission

```python
from django_matt.permissions import OperationPermission

class TaskPermissions(OperationPermission):
    """Different permissions for different operations."""

    read_permission = "tasks.view_task"
    create_permission = "tasks.add_task"
    update_permission = "tasks.change_task"
    delete_permission = "tasks.delete_task"
    list_permission = "tasks.view_task"
```

### Combining Conditions

```python
class IsOrganizationAdmin(BasePermission):
    """User must be admin of the resource's organization."""

    message = "Organization admin access required."

    def has_permission(self, request, view=None):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        org = getattr(obj, 'organization', None)
        if not org:
            return False

        return org.admins.filter(id=request.user.id).exists()
```

### Time-Based Permission

```python
import datetime

class BusinessHoursOnly(BasePermission):
    """Only allow access during business hours."""

    message = "This action is only available during business hours (9-17)."

    def has_permission(self, request, view=None):
        hour = datetime.datetime.now().hour
        return 9 <= hour < 17
```

---

## Combining Permissions

### AND Logic (All Must Pass)

```python
class SensitiveViewSet(APIViewSet):
    permission_classes = [IsAuthenticated, IsAdmin, IsOrganizationMember]
    # User must be: authenticated AND admin AND org member
```

### Custom OR Logic

```python
class IsOwnerOrAdmin(BasePermission):
    """Allow access if user is owner OR admin."""

    def has_object_permission(self, request, view, obj):
        # Check admin first
        if request.user.is_staff:
            return True

        # Then check ownership
        for field in ['user', 'owner', 'created_by']:
            owner = getattr(obj, field, None)
            if owner and owner.pk == request.user.pk:
                return True

        return False
```

---

## ViewSet Integration

### Default Permissions

```python
class ProductViewSet(APIViewSet):
    model = Product
    permission_classes = [IsAuthenticated]

    # All views inherit IsAuthenticated
    list_products = ListView()
    create_product = CreateView()
```

### Per-View Permissions

Override for specific views:

```python
from django_matt.views import ListView, CreateView, DeleteView
from django_matt.permissions import IsAuthenticated, IsAdmin, allow_any

class ProductViewSet(APIViewSet):
    model = Product
    permission_classes = [IsAuthenticated]

    # Public list
    @allow_any
    list_products = ListView()

    # Authenticated create
    create_product = CreateView()

    # Admin only delete
    @requires_role("admin")
    delete_product = DeleteView()
```

---

## Error Handling

### PermissionDenied Exception

```python
from django_matt.permissions import PermissionDenied

async def my_view(request):
    if not can_access(request.user):
        raise PermissionDenied(
            message="You don't have access to this resource",
            status_code=403,
            permission="resource.view",
        )
```

### Custom Error Response

```python
class CustomPermission(BasePermission):
    message = "Custom error message"
    status_code = 403  # Default

    def get_message(self):
        return self.message

    def get_status_code(self):
        return self.status_code
```

---

## Complete Example

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView
from django_matt.permissions import (
    BasePermission,
    IsAuthenticated,
    IsAdmin,
    IsOwner,
    HasRole,
    requires_permission,
    requires_role,
    allow_any,
)


# Custom permission
class IsOrganizationMember(BasePermission):
    """User must belong to the product's organization."""

    message = "You must be a member of this organization."

    def has_object_permission(self, request, view, obj):
        if not hasattr(obj, 'organization'):
            return True
        return obj.organization.members.filter(id=request.user.id).exists()


class ProductViewSet(APIViewSet):
    model = Product
    prefix = "products"

    # Default: authenticated users only
    permission_classes = [IsAuthenticated]

    # Public: anyone can list
    list_products = ListView()

    # Authenticated: can create
    create_product = CreateView()

    # Owner or org member: can read
    read_product = ReadView()

    # Owner only: can update
    update_product = UpdateView()

    # Admin only: can delete
    delete_product = DeleteView()

    def get_permissions(self, view_name: str):
        """Dynamic permission based on view."""
        if view_name == 'list_products':
            return []  # Public
        if view_name == 'delete_product':
            return [IsAuthenticated(), IsAdmin()]
        if view_name in ['read_product', 'update_product']:
            return [IsAuthenticated(), IsOrganizationMember()]
        return [IsAuthenticated()]

    # Custom endpoint with decorator
    @requires_role("manager", "admin")
    async def approve_product(self, request, id: str):
        product = await Product.objects.aget(id=id)
        product.is_approved = True
        await product.asave()
        return {"approved": True}

    @requires_permission("products.export")
    async def export_products(self, request):
        products = await self.get_queryset(request).aall()
        return {"products": [p.to_dict() for p in products]}
```

## Best Practices

1. **Use permission classes for ViewSets**: Apply consistent permissions across views
2. **Use decorators for exceptions**: Mark public endpoints or specific permission needs
3. **Combine permissions carefully**: AND logic by default, create custom classes for OR
4. **Check object permissions**: For update/delete operations on specific resources
5. **Custom messages**: Provide helpful error messages for debugging
6. **Test permissions**: Write tests for each permission scenario
