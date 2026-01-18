# Permissions

Control access to API endpoints with permission classes and decorators.

## Permission Classes

### Built-in Classes

```python
from django_matt.permissions import (
    AllowAny,              # No restrictions
    IsAuthenticated,       # Must be logged in
    IsAdmin,               # Must be staff
    IsStaff,               # Must be staff
    IsSuperUser,           # Must be superuser
    IsOwner,               # Must own the resource
    HasRole,               # Must have specific role
    HasPermission,         # Must have Django permission
    IsAuthenticatedOrReadOnly,  # Auth for writes
    IsAdminOrReadOnly,     # Admin for writes
)
```

### Usage on Controllers

```python
from django_matt import APIController
from django_matt.permissions import IsAuthenticated, IsAdmin

@api.controller("/users")
class UserController(APIController):
    permission_classes = [IsAuthenticated]

    @get("/")
    async def list_users(self, request):
        # Requires authentication
        ...

    @delete("/{id}")
    async def delete_user(self, request, id: int):
        # Also requires authentication (inherited)
        ...
```

### Usage on ViewSets

```python
from django_matt.views import APIViewSet
from django_matt.permissions import IsAuthenticated, IsAdmin

class ProductViewSet(APIViewSet):
    permission_classes = [IsAuthenticated]

    list = ListView()  # Inherits IsAuthenticated
    create = CreateView(permission_classes=[IsAuthenticated, IsAdmin])
    delete = DeleteView(permission_classes=[IsAuthenticated, IsAdmin])
```

## Permission Decorators

### @requires_permission

```python
from django_matt.permissions import requires_permission

@api.delete("/posts/{id}")
@requires_permission("posts.delete_post")
async def delete_post(request, id: int):
    # Requires Django permission "posts.delete_post"
    ...
```

### @requires_permissions

```python
from django_matt.permissions import requires_permissions

@api.post("/admin/bulk-delete")
@requires_permissions("posts.delete_post", "posts.view_post")
async def bulk_delete(request, data: BulkDeleteRequest):
    # Requires both permissions
    ...
```

### @requires_role

```python
from django_matt.permissions import requires_role

@api.post("/admin/settings")
@requires_role("admin")
async def update_settings(request, data: SettingsUpdate):
    # Requires "admin" role (via RBAC)
    ...
```

### @authenticated

```python
from django_matt.permissions import authenticated

@api.get("/me")
@authenticated
async def get_me(request):
    return {"email": request.user.email}
```

### @allow_any

Override controller-level permissions:

```python
@api.controller("/api")
class MyController(APIController):
    permission_classes = [IsAuthenticated]

    @get("/public")
    @allow_any
    async def public_endpoint(self, request):
        # This endpoint is public despite controller-level auth
        ...
```

## Custom Permission Classes

```python
from django_matt.permissions import BasePermission

class IsVerifiedEmail(BasePermission):
    """Require verified email."""

    message = "Email verification required."

    def has_permission(self, request, view) -> bool:
        return (
            request.user.is_authenticated
            and request.user.email_verified
        )

class IsPremiumUser(BasePermission):
    """Require premium subscription."""

    message = "Premium subscription required."

    def has_permission(self, request, view) -> bool:
        if not request.user.is_authenticated:
            return False
        return request.user.subscription_tier in ("premium", "enterprise")

class IsResourceOwner(BasePermission):
    """Check object ownership."""

    def has_object_permission(self, request, view, obj) -> bool:
        return obj.user_id == request.user.id
```

## Combining Permissions

Permissions are evaluated with AND logic:

```python
# User must be authenticated AND admin AND have permission
permission_classes = [IsAuthenticated, IsAdmin, HasPermission("admin.access")]
```

For OR logic, create a custom class:

```python
class IsAdminOrOwner(BasePermission):
    """Allow admins or resource owners."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        return obj.user_id == request.user.id
```

## Object-Level Permissions

```python
class IsOwner(BasePermission):
    """Only allow owners to access the object."""

    owner_field = "user"  # Field name on the model

    def has_object_permission(self, request, view, obj) -> bool:
        owner = getattr(obj, self.owner_field, None)
        if hasattr(owner, "id"):
            return owner.id == request.user.id
        return owner == request.user.id
```

Usage:

```python
class PostViewSet(APIViewSet):
    permission_classes = [IsAuthenticated, IsOwner]

    read = ReadView()   # Checks IsOwner.has_object_permission
    update = UpdateView()  # Checks IsOwner.has_object_permission
    delete = DeleteView()  # Checks IsOwner.has_object_permission
```

## Permission Denied Handling

```python
from django_matt.permissions import PermissionDenied

# Automatic JSON response
{
    "error": {
        "message": "Permission denied",
        "code": "PERMISSION_DENIED"
    }
}
```

Custom message:

```python
class IsPremiumUser(BasePermission):
    message = "Upgrade to premium to access this feature."

# Returns:
{
    "error": {
        "message": "Upgrade to premium to access this feature.",
        "code": "PERMISSION_DENIED"
    }
}
```
