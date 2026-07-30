"""
Audit action enums.

Defines the types of actions that can be logged in the audit system.
"""

from enum import Enum


class AuditAction(str, Enum):
    """
    Types of auditable actions.

    Used to categorize audit log entries for filtering and reporting.
    """

    # Model operations
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"  # For soft-deleted models

    # Authentication actions
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    TOKEN_REFRESH = "token_refresh"

    # Authorization actions
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"

    # Data access
    VIEW = "view"
    EXPORT = "export"
    IMPORT = "import"
    SEARCH = "search"

    # API actions
    API_CALL = "api_call"
    RATE_LIMITED = "rate_limited"

    # Admin actions
    BULK_UPDATE = "bulk_update"
    BULK_DELETE = "bulk_delete"
    CONFIGURATION_CHANGE = "configuration_change"

    # Custom action (for user-defined actions)
    CUSTOM = "custom"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def model_actions(cls) -> list["AuditAction"]:
        """Get actions related to model operations."""
        return [cls.CREATE, cls.UPDATE, cls.DELETE, cls.RESTORE]

    @classmethod
    def auth_actions(cls) -> list["AuditAction"]:
        """Get actions related to authentication."""
        return [
            cls.LOGIN,
            cls.LOGOUT,
            cls.LOGIN_FAILED,
            cls.PASSWORD_CHANGE,
            cls.PASSWORD_RESET,
            cls.TOKEN_REFRESH,
        ]

    @classmethod
    def security_actions(cls) -> list["AuditAction"]:
        """Get security-sensitive actions."""
        return [
            cls.LOGIN,
            cls.LOGIN_FAILED,
            cls.PASSWORD_CHANGE,
            cls.PASSWORD_RESET,
            cls.PERMISSION_GRANTED,
            cls.PERMISSION_DENIED,
            cls.ROLE_ASSIGNED,
            cls.ROLE_REMOVED,
            cls.CONFIGURATION_CHANGE,
        ]


class AuditSeverity(str, Enum):
    """
    Severity levels for audit events.

    Used for filtering and alerting on important events.
    """

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    def __str__(self) -> str:
        return self.value

    @property
    def level(self) -> int:
        """Get numeric level for comparison."""
        levels = {
            "debug": 10,
            "info": 20,
            "warning": 30,
            "error": 40,
            "critical": 50,
        }
        return levels.get(self.value, 20)


# ─── Disambiguation aliases ─────────────────────────────────────
# These prevent collision with django_matt.audits.AuditSeverity
# (which is for code-quality findings, not operational logging).
# Prefer these names in new code:
#   from django_matt.audit import LogSeverity, LogAction

LogSeverity = AuditSeverity
LogAction = AuditAction
