"""
Role-Based Access Control (RBAC) with hierarchy support for Django Matt.

Provides a flexible RBAC system with:
- Role hierarchies (e.g., admin > manager > user)
- Permission inheritance
- Custom role definitions
- Integration with Django groups
"""

from django_matt.auth.rbac.config import Role, RBACConfig, rbac_config
from django_matt.auth.rbac.utils import (
    get_user_roles,
    get_user_permissions,
    user_has_permission,
    user_has_role,
    user_has_any_role,
    user_has_all_roles,
    get_user_highest_role,
)
from django_matt.auth.rbac.decorators import (
    requires_role_hierarchy,
    requires_rbac_permission,
)

__all__ = [
    # Config
    "Role",
    "RBACConfig",
    "rbac_config",
    # Utils
    "get_user_roles",
    "get_user_permissions",
    "user_has_permission",
    "user_has_role",
    "user_has_any_role",
    "user_has_all_roles",
    "get_user_highest_role",
    # Decorators
    "requires_role_hierarchy",
    "requires_rbac_permission",
]
