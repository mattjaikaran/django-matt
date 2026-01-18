"""
RBAC configuration and role definitions.
"""

from dataclasses import dataclass, field
from typing import ClassVar

from django.conf import settings


@dataclass
class Role:
    """
    Defines a role with permissions and optional parent roles.

    Example:
        viewer = Role(
            name="viewer",
            permissions=["read"],
        )

        editor = Role(
            name="editor",
            permissions=["create", "update"],
            inherits=["viewer"],  # Also gets "read" permission
        )

        admin = Role(
            name="admin",
            permissions=["delete", "manage_users"],
            inherits=["editor"],  # Gets all editor + viewer permissions
        )
    """

    name: str
    permissions: list[str] = field(default_factory=list)
    inherits: list[str] = field(default_factory=list)
    description: str = ""
    priority: int = 0  # Higher = more authority


class RBACConfig:
    """
    RBAC configuration manager.

    Configure in Django settings:
        DJANGO_MATT_RBAC = {
            "ROLES": {
                "viewer": {
                    "permissions": ["read"],
                    "priority": 1,
                },
                "editor": {
                    "permissions": ["create", "update"],
                    "inherits": ["viewer"],
                    "priority": 2,
                },
                "admin": {
                    "permissions": ["delete", "manage_users"],
                    "inherits": ["editor"],
                    "priority": 3,
                },
                "superadmin": {
                    "permissions": ["*"],  # Wildcard = all permissions
                    "priority": 100,
                },
            },
            "DEFAULT_ROLE": "viewer",
            "USE_DJANGO_GROUPS": True,
            "PERMISSION_DELIMITER": ".",
        }
    """

    _instance: ClassVar["RBACConfig | None"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._roles: dict[str, Role] = {}
        self._permission_cache: dict[str, set[str]] = {}
        self._load_config()

    def _load_config(self):
        """Load RBAC configuration from Django settings."""
        config = getattr(settings, "DJANGO_MATT_RBAC", {})

        self.default_role = config.get("DEFAULT_ROLE", "viewer")
        self.use_django_groups = config.get("USE_DJANGO_GROUPS", True)
        self.permission_delimiter = config.get("PERMISSION_DELIMITER", ".")

        roles_config = config.get("ROLES", self._default_roles())

        for name, role_config in roles_config.items():
            if isinstance(role_config, dict):
                self._roles[name] = Role(
                    name=name,
                    permissions=role_config.get("permissions", []),
                    inherits=role_config.get("inherits", []),
                    description=role_config.get("description", ""),
                    priority=role_config.get("priority", 0),
                )
            elif isinstance(role_config, Role):
                self._roles[name] = role_config

    def _default_roles(self) -> dict[str, dict]:
        """Default role hierarchy."""
        return {
            "viewer": {
                "permissions": ["read", "list"],
                "priority": 1,
                "description": "Can view resources",
            },
            "editor": {
                "permissions": ["create", "update"],
                "inherits": ["viewer"],
                "priority": 2,
                "description": "Can create and edit resources",
            },
            "manager": {
                "permissions": ["delete", "publish", "assign"],
                "inherits": ["editor"],
                "priority": 3,
                "description": "Can manage resources and team",
            },
            "admin": {
                "permissions": ["manage_users", "manage_roles", "manage_settings"],
                "inherits": ["manager"],
                "priority": 4,
                "description": "Full administrative access",
            },
            "superadmin": {
                "permissions": ["*"],
                "priority": 100,
                "description": "Unrestricted access",
            },
        }

    def get_role(self, name: str) -> Role | None:
        """Get a role by name."""
        return self._roles.get(name)

    def get_all_roles(self) -> list[Role]:
        """Get all defined roles."""
        return list(self._roles.values())

    def get_role_permissions(self, role_name: str) -> set[str]:
        """Get all permissions for a role, including inherited ones."""
        if role_name in self._permission_cache:
            return self._permission_cache[role_name]

        permissions = self._collect_permissions(role_name, set())
        self._permission_cache[role_name] = permissions
        return permissions

    def _collect_permissions(self, role_name: str, visited: set[str]) -> set[str]:
        """Recursively collect permissions including inherited ones."""
        if role_name in visited:
            return set()

        visited.add(role_name)

        role = self._roles.get(role_name)
        if role is None:
            return set()

        permissions = set(role.permissions)

        for parent_role in role.inherits:
            permissions |= self._collect_permissions(parent_role, visited)

        return permissions

    def has_permission(
        self,
        role_name: str,
        permission: str,
        resource: str | None = None,
    ) -> bool:
        """Check if a role has a specific permission."""
        role_permissions = self.get_role_permissions(role_name)

        if "*" in role_permissions:
            return True

        if permission in role_permissions:
            return True

        if resource:
            scoped_permission = f"{resource}{self.permission_delimiter}{permission}"
            if scoped_permission in role_permissions:
                return True

        if resource and f"{resource}{self.permission_delimiter}*" in role_permissions:
            return True

        return False

    def get_role_priority(self, role_name: str) -> int:
        """Get the priority of a role."""
        role = self._roles.get(role_name)
        return role.priority if role else 0

    def is_role_higher(self, role1: str, role2: str) -> bool:
        """Check if role1 has higher priority than role2."""
        return self.get_role_priority(role1) > self.get_role_priority(role2)

    def get_highest_role(self, roles: list[str]) -> str | None:
        """Get the highest priority role from a list."""
        if not roles:
            return None
        return max(roles, key=self.get_role_priority)

    def register_role(self, role: Role):
        """Register a new role or update existing one."""
        self._roles[role.name] = role
        self._permission_cache.pop(role.name, None)

    def clear_cache(self):
        """Clear the permission cache."""
        self._permission_cache.clear()


# Global RBAC config instance
rbac_config = RBACConfig()
