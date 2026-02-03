"""
Feature Flags for Django Matt.

A complete feature flag system with support for:
- Boolean, percentage rollout, and variant (A/B testing) flags
- User, organization, and attribute-based targeting
- Scheduled activation/deactivation
- Multiple backends (Database, Redis, LaunchDarkly, Unleash)
- REST API for flag management
- Django admin integration
- Audit logging

Usage:
    # Simple flag check
    from django_matt.flags import feature_enabled

    if feature_enabled("new_checkout", user=request.user):
        return new_checkout_flow()

    # Using decorator
    from django_matt.flags import feature_flag, requires_flag

    @feature_flag("beta_feature", default=False)
    async def beta_endpoint(request):
        ...

    @requires_flag("admin_tools")
    async def admin_only(request):
        ...

    # Get variant for A/B testing
    from django_matt.flags import get_variant

    variant = get_variant("checkout_experiment", user=request.user)
    if variant == "control":
        ...
    elif variant == "treatment_a":
        ...

    # Using context
    from django_matt.flags import FlagContext

    ctx = FlagContext.from_request(request)
    if ctx.is_enabled("feature"):
        ...

    # Register controllers
    from django_matt.flags import FlagController
    api.register_controller(FlagController)

Configuration (settings.py):
    # Backend selection
    FEATURE_FLAG_BACKEND = "database"  # or "redis", "launchdarkly", "unleash"

    # Backend-specific settings
    FEATURE_FLAG_BACKEND_SETTINGS = {
        "database": {
            "cache_timeout": 60,
            "use_cache": True,
        },
        "redis": {
            "redis_url": "redis://localhost:6379/0",
            "cache_timeout": 300,
        },
        "launchdarkly": {
            "sdk_key": "sdk-xxx",
        },
        "unleash": {
            "url": "https://unleash.example.com/api",
            "app_name": "my-app",
        },
    }

    # Middleware configuration
    FEATURE_FLAG_MIDDLEWARE = {
        "header_overrides": True,    # Allow X-Feature-Flag-* headers
        "cookie_overrides": False,   # Allow ff_* cookies
        "query_overrides": False,    # Allow ?ff_* query params
        "expose_flags_header": True, # Add X-Feature-Flags response header
    }

    # Add middleware (after auth middleware)
    MIDDLEWARE = [
        ...
        'django_matt.flags.FlagMiddleware',
        ...
    ]
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


# Lazy imports to avoid circular dependencies
def __getattr__(name: str):
    """Lazy import handler."""
    if name == "FeatureFlag":
        from django_matt.flags.models import FeatureFlag

        return FeatureFlag
    elif name == "FlagOverride":
        from django_matt.flags.models import FlagOverride

        return FlagOverride
    elif name == "FlagAuditLog":
        from django_matt.flags.models import FlagAuditLog

        return FlagAuditLog
    elif name == "FlagType":
        from django_matt.flags.models import FlagType

        return FlagType
    elif name == "FlagStatus":
        from django_matt.flags.models import FlagStatus

        return FlagStatus
    elif name == "OverrideType":
        from django_matt.flags.models import OverrideType

        return OverrideType
    elif name == "FlagContext":
        from django_matt.flags.context import FlagContext

        return FlagContext
    elif name == "get_current_context":
        from django_matt.flags.context import get_current_context

        return get_current_context
    elif name == "feature_flag":
        from django_matt.flags.decorators import feature_flag

        return feature_flag
    elif name == "requires_flag":
        from django_matt.flags.decorators import requires_flag

        return requires_flag
    elif name == "variant_flag":
        from django_matt.flags.decorators import variant_flag

        return variant_flag
    elif name == "with_flag_context":
        from django_matt.flags.decorators import with_flag_context

        return with_flag_context
    elif name == "FlagEnabledMixin":
        from django_matt.flags.decorators import FlagEnabledMixin

        return FlagEnabledMixin
    elif name == "FlagMiddleware":
        from django_matt.flags.middleware import FlagMiddleware

        return FlagMiddleware
    elif name == "AsyncFlagMiddleware":
        from django_matt.flags.middleware import AsyncFlagMiddleware

        return AsyncFlagMiddleware
    elif name == "FlagBackend":
        from django_matt.flags.backends import FlagBackend

        return FlagBackend
    elif name == "DatabaseBackend":
        from django_matt.flags.backends import DatabaseBackend

        return DatabaseBackend
    elif name == "RedisBackend":
        from django_matt.flags.backends import RedisBackend

        return RedisBackend
    elif name == "LaunchDarklyBackend":
        from django_matt.flags.backends import LaunchDarklyBackend

        return LaunchDarklyBackend
    elif name == "UnleashBackend":
        from django_matt.flags.backends import UnleashBackend

        return UnleashBackend
    elif name == "MemoryBackend":
        from django_matt.flags.backends import MemoryBackend

        return MemoryBackend
    elif name == "get_backend":
        from django_matt.flags.backends import get_backend

        return get_backend
    elif name == "FlagController":
        from django_matt.flags.controllers import FlagController

        return FlagController
    elif name == "FlagEvaluationController":
        from django_matt.flags.controllers import FlagEvaluationController

        return FlagEvaluationController
    elif name == "FeatureFlagAdmin":
        from django_matt.flags.admin import FeatureFlagAdmin

        return FeatureFlagAdmin
    elif name == "FlagOverrideAdmin":
        from django_matt.flags.admin import FlagOverrideAdmin

        return FlagOverrideAdmin
    elif name == "FlagAuditLogAdmin":
        from django_matt.flags.admin import FlagAuditLogAdmin

        return FlagAuditLogAdmin

    raise AttributeError(f"module 'django_matt.flags' has no attribute {name!r}")


# Convenience functions that use the default backend


def feature_enabled(
    key: str,
    user: "AbstractUser | None" = None,
    organization: Any | None = None,
    attributes: dict[str, Any] | None = None,
    default: bool = False,
) -> bool:
    """
    Check if a feature flag is enabled.

    This is a convenience function that uses the default backend.

    Args:
        key: Feature flag key
        user: User to check for (optional)
        organization: Organization/tenant context (optional)
        attributes: Additional attributes for targeting (optional)
        default: Default value if flag not found

    Returns:
        Whether the flag is enabled

    Example:
        if feature_enabled("new_feature", user=request.user):
            # Feature is enabled
            ...
    """
    from django_matt.flags.backends import get_backend

    backend = get_backend()
    return backend.is_enabled(
        key=key,
        user=user,
        organization=organization,
        attributes=attributes,
        default=default,
    )


def get_variant(
    key: str,
    user: "AbstractUser | None" = None,
    organization: Any | None = None,
    attributes: dict[str, Any] | None = None,
    default: str | None = None,
) -> str | None:
    """
    Get variant assignment for a feature flag.

    This is a convenience function that uses the default backend.

    Args:
        key: Feature flag key
        user: User to get variant for (optional)
        organization: Organization/tenant context (optional)
        attributes: Additional attributes for targeting (optional)
        default: Default variant if not assigned

    Returns:
        Variant key or default

    Example:
        variant = get_variant("checkout_experiment", user=request.user)
        if variant == "control":
            return control_checkout()
        elif variant == "treatment_a":
            return new_checkout()
    """
    from django_matt.flags.backends import get_backend

    backend = get_backend()
    return backend.get_variant(
        key=key,
        user=user,
        organization=organization,
        attributes=attributes,
        default=default,
    )


def get_all_flags(
    user: "AbstractUser | None" = None,
    organization: Any | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, bool]:
    """
    Get all feature flags with their enabled status.

    This is a convenience function that uses the default backend.

    Args:
        user: User context (optional)
        organization: Organization/tenant context (optional)
        attributes: Additional attributes (optional)

    Returns:
        Dict of flag key -> enabled status
    """
    from django_matt.flags.backends import get_backend

    backend = get_backend()
    return backend.get_all_flags(
        user=user,
        organization=organization,
        attributes=attributes,
    )


__all__ = [
    # Convenience functions
    "feature_enabled",
    "get_variant",
    "get_all_flags",
    # Models
    "FeatureFlag",
    "FlagOverride",
    "FlagAuditLog",
    "FlagType",
    "FlagStatus",
    "OverrideType",
    # Context
    "FlagContext",
    "get_current_context",
    # Decorators
    "feature_flag",
    "requires_flag",
    "variant_flag",
    "with_flag_context",
    "FlagEnabledMixin",
    # Middleware
    "FlagMiddleware",
    "AsyncFlagMiddleware",
    # Backends
    "FlagBackend",
    "DatabaseBackend",
    "RedisBackend",
    "LaunchDarklyBackend",
    "UnleashBackend",
    "MemoryBackend",
    "get_backend",
    # Controllers
    "FlagController",
    "FlagEvaluationController",
    # Admin
    "FeatureFlagAdmin",
    "FlagOverrideAdmin",
    "FlagAuditLogAdmin",
]
