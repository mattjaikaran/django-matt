"""
Common permission classes for Django Matt.

Provides ready-to-use permission classes for common use cases.
"""

from typing import Any, ClassVar

from django.http import HttpRequest

from django_matt.permissions.base import BasePermission


class AllowAny(BasePermission):
    """
    Permission class that allows any request.
    
    Use this to explicitly mark endpoints as public.
    
    Example:
        class PublicController(APIController):
            permission_classes = [AllowAny]
    """
    
    message: ClassVar[str] = "Access granted."
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """Allow all requests."""
        return True


class IsAuthenticated(BasePermission):
    """
    Permission class that requires authenticated users.
    
    Denies access to unauthenticated requests.
    
    Example:
        class ProtectedController(APIController):
            permission_classes = [IsAuthenticated]
    """
    
    message: ClassVar[str] = "Authentication required."
    status_code: ClassVar[int] = 401
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """Check if user is authenticated."""
        user = getattr(request, "user", None)
        if user is None:
            return False
        return user.is_authenticated


class IsAdmin(BasePermission):
    """
    Permission class that requires admin users.
    
    User must be authenticated and either staff or superuser.
    
    Example:
        class AdminController(APIController):
            permission_classes = [IsAdmin]
    """
    
    message: ClassVar[str] = "Admin access required."
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """Check if user is admin (staff or superuser)."""
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser


class IsStaff(BasePermission):
    """
    Permission class that requires staff users.
    
    Example:
        class StaffController(APIController):
            permission_classes = [IsStaff]
    """
    
    message: ClassVar[str] = "Staff access required."
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """Check if user is staff."""
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return user.is_staff


class IsSuperUser(BasePermission):
    """
    Permission class that requires superusers.
    
    Example:
        class SuperUserController(APIController):
            permission_classes = [IsSuperUser]
    """
    
    message: ClassVar[str] = "Superuser access required."
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """Check if user is superuser."""
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return user.is_superuser


class IsOwner(BasePermission):
    """
    Object-level permission that requires the user to be the owner.
    
    Checks if the object has a `user`, `owner`, or `created_by` field
    that matches the current user.
    
    Example:
        class TaskController(APIController):
            permission_classes = [IsAuthenticated, IsOwner]
    """
    
    message: ClassVar[str] = "You do not own this resource."
    
    # Field names to check for ownership
    owner_fields: ClassVar[list[str]] = ["user", "owner", "created_by", "author"]
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """IsOwner is checked at object level only."""
        return True
    
    def has_object_permission(
        self, request: HttpRequest, view: Any, obj: Any
    ) -> bool:
        """Check if user owns the object."""
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        
        # Check each possible owner field
        for field in self.owner_fields:
            owner = getattr(obj, field, None)
            if owner is not None:
                # Handle ForeignKey (compare user objects or IDs)
                if hasattr(owner, "pk"):
                    return owner.pk == user.pk
                return owner == user
        
        return False


class HasRole(BasePermission):
    """
    Permission class that requires specific role(s).
    
    Checks if the user has any of the specified roles.
    Works with Django groups or custom role implementations.
    
    Example:
        manager_only = HasRole(roles=["manager", "admin"])
        
        class ManagerController(APIController):
            permission_classes = [manager_only]
    """
    
    message: ClassVar[str] = "Required role not found."
    
    def __init__(self, roles: list[str] | str | None = None):
        """
        Initialize with required roles.
        
        Args:
            roles: Single role or list of roles (user needs any one)
        """
        if roles is None:
            self.roles = []
        elif isinstance(roles, str):
            self.roles = [roles]
        else:
            self.roles = list(roles)
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """Check if user has any of the required roles."""
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        
        if not self.roles:
            return True  # No roles required
        
        # Check Django groups
        if hasattr(user, "groups"):
            user_groups = set(user.groups.values_list("name", flat=True))
            if user_groups & set(self.roles):
                return True
        
        # Check custom role field
        if hasattr(user, "role"):
            user_role = user.role
            if isinstance(user_role, str):
                return user_role in self.roles
            elif hasattr(user_role, "name"):
                return user_role.name in self.roles
        
        # Check roles many-to-many
        if hasattr(user, "roles"):
            user_roles = set(user.roles.values_list("name", flat=True))
            if user_roles & set(self.roles):
                return True
        
        return False


class HasPermission(BasePermission):
    """
    Permission class that requires specific Django permission(s).
    
    Uses Django's built-in permission system.
    
    Example:
        can_edit = HasPermission(permissions=["myapp.change_model"])
        
        @patch("{id}")
        @requires(can_edit)
        async def update(self, request, id):
            ...
    """
    
    message: ClassVar[str] = "Required permission not found."
    
    def __init__(
        self,
        permissions: list[str] | str | None = None,
        require_all: bool = False,
    ):
        """
        Initialize with required permissions.
        
        Args:
            permissions: Single permission or list of permissions
            require_all: If True, user must have all permissions.
                        If False (default), user needs any one.
        """
        if permissions is None:
            self.permissions = []
        elif isinstance(permissions, str):
            self.permissions = [permissions]
        else:
            self.permissions = list(permissions)
        
        self.require_all = require_all
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """Check if user has required permissions."""
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        
        if not self.permissions:
            return True  # No permissions required
        
        if self.require_all:
            return user.has_perms(self.permissions)
        else:
            return any(user.has_perm(p) for p in self.permissions)


# Commonly used permission combinations
class IsAuthenticatedOrReadOnly(BasePermission):
    """
    Permission that allows read-only access to unauthenticated users.
    
    Authenticated users get full access.
    """
    
    message: ClassVar[str] = "Authentication required for this action."
    
    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """Allow read-only for unauthenticated, full access for authenticated."""
        if request.method in self.SAFE_METHODS:
            return True
        
        user = getattr(request, "user", None)
        if user is None:
            return False
        return user.is_authenticated


class IsAdminOrReadOnly(BasePermission):
    """
    Permission that allows read-only access to non-admin users.
    
    Admin users get full access.
    """
    
    message: ClassVar[str] = "Admin access required for this action."
    
    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """Allow read-only for non-admin, full access for admin."""
        if request.method in self.SAFE_METHODS:
            return True
        
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser
