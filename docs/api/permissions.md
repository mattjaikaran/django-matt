# Permissions API Reference

Flexible permission system for controlling access to API endpoints.

## Base Classes

### BasePermission

Base class for all permission classes.

::: django_matt.permissions.base.BasePermission
    options:
      show_source: false
      heading_level: 4

### Permission

Alias for BasePermission.

::: django_matt.permissions.base.Permission
    options:
      show_source: false
      heading_level: 4

### OperationPermission

Permission class that checks based on the operation type (list, create, read, update, delete).

::: django_matt.permissions.base.OperationPermission
    options:
      show_source: false
      heading_level: 4

### PermissionDenied

Exception raised when permission is denied.

::: django_matt.permissions.base.PermissionDenied
    options:
      show_source: false
      heading_level: 4

---

## Common Permission Classes

### AllowAny

Allows unrestricted access to the endpoint.

::: django_matt.permissions.common.AllowAny
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.permissions import AllowAny

class PublicController(APIController):
    permission_classes = [AllowAny]
```

---

### IsAuthenticated

Only allows access to authenticated users.

::: django_matt.permissions.common.IsAuthenticated
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.permissions import IsAuthenticated

class UserController(APIController):
    permission_classes = [IsAuthenticated]
```

---

### IsAuthenticatedOrReadOnly

Allows read access to anyone, but requires authentication for write operations.

::: django_matt.permissions.common.IsAuthenticatedOrReadOnly
    options:
      show_source: false
      heading_level: 4

---

### IsAdmin

Only allows access to admin users (`is_staff=True`).

::: django_matt.permissions.common.IsAdmin
    options:
      show_source: false
      heading_level: 4

---

### IsAdminOrReadOnly

Allows read access to anyone, but requires admin status for write operations.

::: django_matt.permissions.common.IsAdminOrReadOnly
    options:
      show_source: false
      heading_level: 4

---

### IsStaff

Only allows access to staff users.

::: django_matt.permissions.common.IsStaff
    options:
      show_source: false
      heading_level: 4

---

### IsSuperUser

Only allows access to superusers.

::: django_matt.permissions.common.IsSuperUser
    options:
      show_source: false
      heading_level: 4

---

### IsOwner

Only allows access if the user owns the resource.

::: django_matt.permissions.common.IsOwner
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.permissions import IsOwner

class PostController(APIController):
    permission_classes = [IsAuthenticated, IsOwner]

    # IsOwner checks obj.user == request.user by default
    # Configure with owner_field for different field names
```

---

### HasRole

Checks if user has a specific role.

::: django_matt.permissions.common.HasRole
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.permissions import HasRole

class AdminController(APIController):
    permission_classes = [HasRole("admin")]
```

---

### HasPermission

Checks if user has a specific Django permission.

::: django_matt.permissions.common.HasPermission
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.permissions import HasPermission

class ProductController(APIController):
    permission_classes = [HasPermission("products.add_product")]
```

---

## Permission Decorators

### requires_permission

Decorator that requires a specific Django permission.

::: django_matt.permissions.decorators.requires_permission
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.permissions import requires_permission

class ProductController(APIController):
    @post("")
    @requires_permission("products.add_product")
    async def create_product(self, request, data: ProductCreate):
        ...
```

---

### requires_permissions

Decorator that requires multiple Django permissions.

::: django_matt.permissions.decorators.requires_permissions
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.permissions import requires_permissions

@requires_permissions("products.add_product", "products.change_product")
async def bulk_update(self, request, data: BulkUpdateData):
    ...
```

---

### requires_role

Decorator that requires a specific role.

::: django_matt.permissions.decorators.requires_role
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.permissions import requires_role

@requires_role("admin")
async def admin_action(self, request):
    ...
```

---

### authenticated

Decorator that requires authentication.

::: django_matt.permissions.decorators.authenticated
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.permissions import authenticated

@authenticated
async def get_profile(self, request):
    return {"user": request.user.email}
```

---

### allow_any

Decorator that allows any access (bypasses controller-level permissions).

::: django_matt.permissions.decorators.allow_any
    options:
      show_source: false
      heading_level: 4

**Example:**

```python
from django_matt.permissions import allow_any, IsAuthenticated

class MixedController(APIController):
    permission_classes = [IsAuthenticated]

    @get("/public")
    @allow_any  # This endpoint is public despite controller-level auth
    async def public_endpoint(self, request):
        ...
```

---

### with_permissions

Decorator that applies multiple permission classes.

::: django_matt.permissions.decorators.with_permissions
    options:
      show_source: false
      heading_level: 4

---

### check_permissions

Utility function to manually check permissions.

::: django_matt.permissions.decorators.check_permissions
    options:
      show_source: false
      heading_level: 4

---

## Custom Permission Classes

Create custom permissions by subclassing `BasePermission`:

```python
from django_matt.permissions import BasePermission

class IsVerifiedEmail(BasePermission):
    """Only allow users with verified email addresses."""

    message = "Email verification required."

    def has_permission(self, request, view) -> bool:
        return (
            request.user.is_authenticated
            and getattr(request.user, 'email_verified', False)
        )

class IsPremiumUser(BasePermission):
    """Only allow premium subscribers."""

    message = "Premium subscription required."

    def has_permission(self, request, view) -> bool:
        if not request.user.is_authenticated:
            return False
        return request.user.subscription_tier in ('premium', 'enterprise')

    def has_object_permission(self, request, view, obj) -> bool:
        # Additional object-level check
        return self.has_permission(request, view)

# Usage
class PremiumController(APIController):
    permission_classes = [IsAuthenticated, IsVerifiedEmail, IsPremiumUser]
```

---

## Combining Permissions

Permissions are evaluated in order and all must pass:

```python
from django_matt.permissions import IsAuthenticated, HasRole, HasPermission

class AdminController(APIController):
    # User must be: authenticated AND have admin role AND have specific permission
    permission_classes = [
        IsAuthenticated,
        HasRole("admin"),
        HasPermission("admin.access_dashboard"),
    ]
```

For OR logic, create a custom permission:

```python
class IsAdminOrOwner(BasePermission):
    """Allow admins or resource owners."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        return obj.user == request.user
```
