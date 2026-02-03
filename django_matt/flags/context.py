"""
Feature flag context management.

Provides FlagContext for evaluating feature flags with user/org context.

Usage:
    from django_matt.flags.context import FlagContext

    # Create context from request
    ctx = FlagContext.from_request(request)

    # Check flags
    if ctx.is_enabled("new_feature"):
        ...

    # Get variant
    variant = ctx.get_variant("experiment")
"""

import contextvars
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.contrib.auth.models import AbstractUser

# Context variable for current flag context
_current_context: contextvars.ContextVar["FlagContext | None"] = contextvars.ContextVar(
    "flag_context", default=None
)


@dataclass
class FlagContext:
    """
    Context for evaluating feature flags.

    Holds user, organization, and custom attributes for flag evaluation.
    Can be created from a request or manually for testing.
    """

    user: "AbstractUser | None" = None
    organization: Any | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    _backend: Any = None  # Lazy backend reference

    @classmethod
    def from_request(cls, request: "HttpRequest") -> "FlagContext":
        """
        Create a FlagContext from an HTTP request.

        Extracts user and organization from the request.
        """
        user = None
        organization = None
        attributes = {}

        # Get user if authenticated
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user

            # Try to get organization from various sources
            if hasattr(request, "organization"):
                organization = request.organization
            elif hasattr(user, "organization"):
                organization = user.organization
            elif hasattr(user, "current_organization"):
                organization = user.current_organization

            # Add user attributes
            if hasattr(user, "email"):
                attributes["email"] = user.email
            if hasattr(user, "is_staff"):
                attributes["is_staff"] = user.is_staff
            if hasattr(user, "is_superuser"):
                attributes["is_superuser"] = user.is_superuser
            if hasattr(user, "date_joined"):
                attributes["days_since_signup"] = (
                    (user.date_joined.now() - user.date_joined).days
                    if user.date_joined
                    else 0
                )

        # Add request attributes
        attributes["path"] = request.path
        attributes["method"] = request.method

        # Add header-based attributes
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        attributes["user_agent"] = user_agent
        attributes["is_mobile"] = any(
            x in user_agent.lower() for x in ["mobile", "android", "iphone", "ipad"]
        )

        return cls(user=user, organization=organization, attributes=attributes)

    @classmethod
    def current(cls) -> "FlagContext | None":
        """Get the current flag context from context var."""
        return _current_context.get()

    @classmethod
    def set_current(cls, context: "FlagContext | None"):
        """Set the current flag context."""
        _current_context.set(context)

    @property
    def backend(self):
        """Get the feature flag backend."""
        if self._backend is None:
            from django_matt.flags.backends import get_backend

            self._backend = get_backend()
        return self._backend

    def is_enabled(self, key: str, default: bool = False) -> bool:
        """
        Check if a feature flag is enabled.

        Args:
            key: Flag key
            default: Default value if flag not found

        Returns:
            Whether the flag is enabled
        """
        return self.backend.is_enabled(
            key=key,
            user=self.user,
            organization=self.organization,
            attributes=self.attributes,
            default=default,
        )

    def get_variant(self, key: str, default: str | None = None) -> str | None:
        """
        Get variant assignment for a feature flag.

        Args:
            key: Flag key
            default: Default variant if not assigned

        Returns:
            Variant key or default
        """
        return self.backend.get_variant(
            key=key,
            user=self.user,
            organization=self.organization,
            attributes=self.attributes,
            default=default,
        )

    def get_all_flags(self) -> dict[str, bool]:
        """
        Get all feature flags with their enabled status.

        Returns:
            Dict of flag key -> enabled status
        """
        return self.backend.get_all_flags(
            user=self.user,
            organization=self.organization,
            attributes=self.attributes,
        )

    def with_attributes(self, **attributes) -> "FlagContext":
        """
        Create a new context with additional attributes.

        Args:
            **attributes: Additional attributes to add

        Returns:
            New FlagContext with merged attributes
        """
        merged = {**self.attributes, **attributes}
        return FlagContext(
            user=self.user,
            organization=self.organization,
            attributes=merged,
            _backend=self._backend,
        )

    def with_user(self, user: "AbstractUser") -> "FlagContext":
        """
        Create a new context with a different user.

        Args:
            user: User to use

        Returns:
            New FlagContext with the user
        """
        return FlagContext(
            user=user,
            organization=self.organization,
            attributes=self.attributes,
            _backend=self._backend,
        )

    def with_organization(self, organization: Any) -> "FlagContext":
        """
        Create a new context with a different organization.

        Args:
            organization: Organization to use

        Returns:
            New FlagContext with the organization
        """
        return FlagContext(
            user=self.user,
            organization=organization,
            attributes=self.attributes,
            _backend=self._backend,
        )

    def __enter__(self):
        """Enter context manager - set as current context."""
        self._token = _current_context.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - restore previous context."""
        _current_context.reset(self._token)
        return False


def get_current_context() -> FlagContext | None:
    """Get the current flag context."""
    return _current_context.get()


def set_current_context(context: FlagContext | None):
    """Set the current flag context."""
    _current_context.set(context)


__all__ = [
    "FlagContext",
    "get_current_context",
    "set_current_context",
]
