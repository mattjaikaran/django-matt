"""
RBAC utility functions for checking user roles and permissions.
"""

from django_matt.auth.rbac.config import rbac_config


def get_user_roles(user) -> list[str]:
    """
    Get all roles for a user.

    Checks:
    1. Django groups (if USE_DJANGO_GROUPS is True)
    2. Custom role field on user model
    3. Custom roles relation on user model
    """
    if user is None or not user.is_authenticated:
        return []

    roles = []

    # Check Django groups
    if rbac_config.use_django_groups and hasattr(user, "groups"):
        group_names = user.groups.values_list("name", flat=True)
        roles.extend(group_names)

    # Check custom role field
    if hasattr(user, "role"):
        user_role = user.role
        if isinstance(user_role, str) and user_role:
            roles.append(user_role)
        elif hasattr(user_role, "name"):
            roles.append(user_role.name)

    # Check custom roles relation
    if hasattr(user, "roles"):
        try:
            role_names = user.roles.values_list("name", flat=True)
            roles.extend(role_names)
        except Exception:
            pass

    # Add superadmin for superusers
    if hasattr(user, "is_superuser") and user.is_superuser:
        roles.append("superadmin")

    return list(set(roles))


def get_user_permissions(user) -> set[str]:
    """Get all permissions for a user based on their roles."""
    roles = get_user_roles(user)
    permissions = set()

    for role in roles:
        permissions |= rbac_config.get_role_permissions(role)

    return permissions


def user_has_permission(
    user,
    permission: str,
    resource: str | None = None,
) -> bool:
    """
    Check if a user has a specific permission.

    Args:
        user: Django user instance
        permission: Permission to check
        resource: Optional resource scope

    Returns:
        True if user has the permission through any of their roles
    """
    if user is None or not user.is_authenticated:
        return False

    # Superusers have all permissions
    if hasattr(user, "is_superuser") and user.is_superuser:
        return True

    roles = get_user_roles(user)

    for role in roles:
        if rbac_config.has_permission(role, permission, resource):
            return True

    return False


def user_has_role(user, role: str) -> bool:
    """Check if user has a specific role."""
    return role in get_user_roles(user)


def user_has_any_role(user, roles: list[str]) -> bool:
    """Check if user has any of the specified roles."""
    user_roles = set(get_user_roles(user))
    return bool(user_roles & set(roles))


def user_has_all_roles(user, roles: list[str]) -> bool:
    """Check if user has all of the specified roles."""
    user_roles = set(get_user_roles(user))
    return set(roles).issubset(user_roles)


def get_user_highest_role(user) -> str | None:
    """Get the user's highest priority role."""
    roles = get_user_roles(user)
    return rbac_config.get_highest_role(roles)
