"""
Feature flag backends.

Provides different storage backends for feature flags:
- DatabaseBackend: Uses Django ORM (default)
- RedisBackend: Uses Redis for high-performance lookups
- LaunchDarklyBackend: Integration with LaunchDarkly
- UnleashBackend: Integration with Unleash

Usage:
    from django_matt.flags.backends import get_backend

    backend = get_backend()  # Gets default backend from settings
    enabled = backend.is_enabled("new_feature", user=request.user)
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.cache import cache

import orjson

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

logger = logging.getLogger("django_matt.flags")


class FlagBackend(ABC):
    """Base class for feature flag backends."""

    @abstractmethod
    def is_enabled(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: bool = False,
    ) -> bool:
        """
        Check if a feature flag is enabled.

        Args:
            key: Flag key
            user: User to check for
            organization: Organization/tenant context
            attributes: Additional attributes for targeting
            default: Default value if flag not found

        Returns:
            Whether the flag is enabled
        """

    @abstractmethod
    def get_variant(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: str | None = None,
    ) -> str | None:
        """
        Get variant assignment for a feature flag.

        Args:
            key: Flag key
            user: User to get variant for
            organization: Organization/tenant context
            attributes: Additional attributes for targeting
            default: Default variant if not assigned

        Returns:
            Variant key or default
        """

    @abstractmethod
    def get_all_flags(
        self,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """
        Get all feature flags with their enabled status.

        Args:
            user: User context
            organization: Organization/tenant context
            attributes: Additional attributes

        Returns:
            Dict of flag key -> enabled status
        """

    @abstractmethod
    def invalidate(self, key: str) -> None:
        """
        Invalidate cache for a specific flag.

        Args:
            key: Flag key to invalidate
        """

    @abstractmethod
    def invalidate_all(self) -> None:
        """Invalidate all cached flags."""

    def close(self):
        """Clean up resources."""


class DatabaseBackend(FlagBackend):
    """
    Database-backed feature flag backend.

    Uses Django ORM for flag storage with optional caching.
    """

    def __init__(
        self,
        cache_timeout: int = 60,
        cache_prefix: str = "flags:",
        use_cache: bool = True,
    ):
        self.cache_timeout = cache_timeout
        self.cache_prefix = cache_prefix
        self.use_cache = use_cache

    def _get_cache_key(self, key: str) -> str:
        """Get cache key for a flag."""
        return f"{self.cache_prefix}{key}"

    def _get_flag(self, key: str):
        """Get a flag from database with caching."""
        from django_matt.flags.models import FeatureFlag

        if self.use_cache:
            cache_key = self._get_cache_key(key)
            flag = cache.get(cache_key)
            if flag is not None:
                if flag == "__NOT_FOUND__":
                    return None
                return flag

        try:
            flag = FeatureFlag.objects.prefetch_related("overrides").get(key=key)
            if self.use_cache:
                cache.set(cache_key, flag, self.cache_timeout)
            return flag
        except FeatureFlag.DoesNotExist:
            if self.use_cache:
                cache.set(cache_key, "__NOT_FOUND__", self.cache_timeout)
            return None

    def is_enabled(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: bool = False,
    ) -> bool:
        flag = self._get_flag(key)
        if not flag:
            return default

        return flag.is_enabled_for_user(
            user=user,
            organization=organization,
            attributes=attributes,
        )

    def get_variant(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: str | None = None,
    ) -> str | None:
        flag = self._get_flag(key)
        if not flag:
            return default

        variant = flag.get_variant(
            user=user,
            organization=organization,
            attributes=attributes,
        )
        return variant if variant else default

    def get_all_flags(
        self,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        from django_matt.flags.models import FeatureFlag, FlagStatus

        flags = FeatureFlag.objects.filter(status=FlagStatus.ACTIVE.value)
        result = {}

        for flag in flags:
            result[flag.key] = flag.is_enabled_for_user(
                user=user,
                organization=organization,
                attributes=attributes,
            )

        return result

    def invalidate(self, key: str) -> None:
        """Invalidate cache for a specific flag."""
        cache.delete(self._get_cache_key(key))

    def invalidate_all(self) -> None:
        """Invalidate all flag caches.

        Note: Django's default cache does not support pattern-based deletion.
        Use a cache backend that supports key scanning (e.g., Redis-backed Django
        cache) for full invalidation, or invalidate flags individually.
        """
        # No-op for generic cache backends; Redis-backed Django cache can use
        # cache.delete_pattern() from django-redis if available.

    def invalidate_cache(self, key: str | None = None):
        """Invalidate cache for a specific flag or all flags.

        Deprecated: use invalidate(key) or invalidate_all() instead.
        """
        if key:
            self.invalidate(key)
        else:
            self.invalidate_all()


class RedisBackend(FlagBackend):
    """
    Redis-backed feature flag backend.

    Optimized for high-performance lookups with Redis.
    Flag definitions are still stored in the database but cached in Redis.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        cache_timeout: int = 300,
        key_prefix: str = "feature_flags:",
    ):
        self.redis_url = redis_url or getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        self.cache_timeout = cache_timeout
        self.key_prefix = key_prefix
        self._client = None

    @property
    def client(self):
        """Lazy Redis client initialization."""
        if self._client is None:
            try:
                import redis

                self._client = redis.from_url(self.redis_url)
            except ImportError:
                raise ImportError(
                    "redis package is required for RedisBackend. Install with: uv add redis"
                )
        return self._client

    def _get_key(self, key: str) -> str:
        """Get Redis key for a flag."""
        return f"{self.key_prefix}{key}"

    def _serialize_flag(self, flag) -> str:
        """Serialize flag to JSON."""

        overrides = list(
            flag.overrides.values(
                "override_type", "target_id", "target_value", "enabled", "variant", "expires_at"
            )
        )

        # Convert datetime to string
        for override in overrides:
            if override.get("expires_at"):
                override["expires_at"] = override["expires_at"].isoformat()

        data = {
            "key": flag.key,
            "flag_type": flag.flag_type,
            "status": flag.status,
            "enabled_by_default": flag.enabled_by_default,
            "rollout_percentage": flag.rollout_percentage,
            "variants": flag.variants,
            "targeting_rules": flag.targeting_rules,
            "scheduled_enable_at": flag.scheduled_enable_at.isoformat()
            if flag.scheduled_enable_at
            else None,
            "scheduled_disable_at": flag.scheduled_disable_at.isoformat()
            if flag.scheduled_disable_at
            else None,
            "overrides": overrides,
        }
        return orjson.dumps(data).decode()

    def _deserialize_flag(self, data: str) -> dict:
        """Deserialize flag from JSON."""
        return orjson.loads(data)

    def _get_flag_data(self, key: str) -> dict | None:
        """Get flag data from Redis with database fallback."""
        redis_key = self._get_key(key)

        # Try Redis first
        data = self.client.get(redis_key)
        if data:
            return self._deserialize_flag(data)

        # Fallback to database and cache
        from django_matt.flags.models import FeatureFlag

        try:
            flag = FeatureFlag.objects.prefetch_related("overrides").get(key=key)
            serialized = self._serialize_flag(flag)
            self.client.setex(redis_key, self.cache_timeout, serialized)
            return self._deserialize_flag(serialized)
        except FeatureFlag.DoesNotExist:
            return None

    def is_enabled(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: bool = False,
    ) -> bool:
        flag_data = self._get_flag_data(key)
        if not flag_data:
            return default

        return self._evaluate_flag(flag_data, user, organization, attributes)

    def _evaluate_flag(
        self,
        flag_data: dict,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> bool:
        """Evaluate flag based on cached data."""
        from datetime import datetime

        from django_matt.flags.models import FlagStatus, FlagType, OverrideType

        if flag_data["status"] != FlagStatus.ACTIVE.value:
            return False

        # Check scheduled times
        now = datetime.now().isoformat()
        if flag_data.get("scheduled_enable_at") and now < flag_data["scheduled_enable_at"]:
            return False
        if flag_data.get("scheduled_disable_at") and now >= flag_data["scheduled_disable_at"]:
            return False

        # Check overrides
        for override in flag_data.get("overrides", []):
            # Check expiry
            if override.get("expires_at") and now >= override["expires_at"]:
                continue

            if override["override_type"] == OverrideType.USER.value and user:
                if override["target_id"] == str(user.pk):
                    return override["enabled"]

            if (
                override["override_type"] == OverrideType.EMAIL.value
                and user
                and hasattr(user, "email")
            ):
                if override["target_value"] == user.email:
                    return override["enabled"]

            if override["override_type"] == OverrideType.ORGANIZATION.value and organization:
                org_id = str(organization.pk if hasattr(organization, "pk") else organization)
                if override["target_id"] == org_id:
                    return override["enabled"]

        # Handle flag type
        flag_type = flag_data["flag_type"]

        if flag_type == FlagType.PERCENTAGE.value and user:
            percentage = flag_data.get("rollout_percentage", 0)
            if percentage <= 0:
                return False
            if percentage >= 100:
                return True

            hash_input = f"{flag_data['key']}:{user.pk}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            bucket = hash_value % 100
            return bucket < percentage

        return flag_data.get("enabled_by_default", False)

    def get_variant(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: str | None = None,
    ) -> str | None:
        flag_data = self._get_flag_data(key)
        if not flag_data:
            return default

        from django_matt.flags.models import FlagType

        if flag_data["flag_type"] != FlagType.VARIANT.value:
            return default

        variants = flag_data.get("variants", {}).get("variants", [])
        if not variants:
            return default

        # Check user override
        if user:
            for override in flag_data.get("overrides", []):
                if override["target_id"] == str(user.pk) and override.get("variant"):
                    return override["variant"]

        # Calculate consistent variant
        if user:
            hash_input = f"{key}:{user.pk}"
        else:
            import secrets

            hash_input = f"{key}:{secrets.token_hex(8)}"

        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        total_weight = sum(v.get("weight", 1) for v in variants)

        if total_weight == 0:
            return default

        bucket = hash_value % total_weight
        cumulative = 0

        for variant in variants:
            cumulative += variant.get("weight", 1)
            if bucket < cumulative:
                return variant.get("key")

        return default

    def get_all_flags(
        self,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        from django_matt.flags.models import FeatureFlag, FlagStatus

        # Get all active flag keys from database
        flag_keys = list(
            FeatureFlag.objects.filter(status=FlagStatus.ACTIVE.value).values_list("key", flat=True)
        )

        result = {}
        for key in flag_keys:
            result[key] = self.is_enabled(key, user, organization, attributes)

        return result

    def invalidate(self, key: str):
        """Invalidate cache for a specific flag."""
        self.client.delete(self._get_key(key))

    def invalidate_all(self):
        """Invalidate all flag caches."""
        pattern = f"{self.key_prefix}*"
        keys = self.client.keys(pattern)
        if keys:
            self.client.delete(*keys)

    def sync_from_database(self):
        """Sync all flags from database to Redis."""
        from django_matt.flags.models import FeatureFlag, FlagStatus

        flags = FeatureFlag.objects.filter(status=FlagStatus.ACTIVE.value).prefetch_related(
            "overrides"
        )

        pipeline = self.client.pipeline()
        for flag in flags:
            redis_key = self._get_key(flag.key)
            serialized = self._serialize_flag(flag)
            pipeline.setex(redis_key, self.cache_timeout, serialized)

        pipeline.execute()
        logger.info(f"Synced {len(flags)} flags to Redis")

    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None


class LaunchDarklyBackend(FlagBackend):
    """
    LaunchDarkly feature flag backend.

    Provides integration with LaunchDarkly's feature flag service.
    Requires: uv add launchdarkly-server-sdk
    """

    def __init__(
        self,
        sdk_key: str | None = None,
        config: dict | None = None,
    ):
        self.sdk_key = sdk_key or getattr(settings, "LAUNCHDARKLY_SDK_KEY", None)
        if not self.sdk_key:
            raise ValueError("LaunchDarkly SDK key is required")

        self._config = config or {}
        self._client = None

    @property
    def client(self):
        """Lazy LaunchDarkly client initialization."""
        if self._client is None:
            try:
                import ldclient
                from ldclient.config import Config

                config = Config(self.sdk_key, **self._config)
                ldclient.set_config(config)
                self._client = ldclient.get()

                if not self._client.is_initialized():
                    logger.warning("LaunchDarkly client failed to initialize")
            except ImportError:
                raise ImportError(
                    "launchdarkly-server-sdk is required. Install with: uv add launchdarkly-server-sdk"
                )
        return self._client

    def _build_context(
        self,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ):
        """Build LaunchDarkly context from user/org/attributes."""
        try:
            from ldclient import Context

            if user:
                builder = Context.builder(str(user.pk))
                builder.kind("user")

                if hasattr(user, "email") and user.email:
                    builder.set("email", user.email)
                if hasattr(user, "username") and user.username:
                    builder.set("username", user.username)
                if hasattr(user, "first_name"):
                    builder.set("firstName", user.first_name or "")
                if hasattr(user, "last_name"):
                    builder.set("lastName", user.last_name or "")
                if hasattr(user, "is_staff"):
                    builder.set("isStaff", user.is_staff)

                if attributes:
                    for key, value in attributes.items():
                        builder.set(key, value)

                return builder.build()
            # Anonymous context
            return Context.builder("anonymous").kind("user").anonymous(True).build()

        except ImportError:
            raise ImportError("launchdarkly-server-sdk is required")

    def is_enabled(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: bool = False,
    ) -> bool:
        context = self._build_context(user, organization, attributes)
        return self.client.variation(key, context, default)

    def get_variant(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: str | None = None,
    ) -> str | None:
        context = self._build_context(user, organization, attributes)
        return self.client.variation(key, context, default)

    def get_all_flags(
        self,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        context = self._build_context(user, organization, attributes)
        state = self.client.all_flags_state(context)
        return state.to_values_map()

    def invalidate(self, key: str) -> None:
        """LaunchDarkly manages its own cache; this is a no-op."""

    def invalidate_all(self) -> None:
        """LaunchDarkly manages its own cache; this is a no-op."""

    def close(self):
        """Close LaunchDarkly client."""
        if self._client:
            self._client.close()
            self._client = None


class UnleashBackend(FlagBackend):
    """
    Unleash feature flag backend.

    Provides integration with Unleash (or GitLab Feature Flags).
    Requires: uv add UnleashClient
    """

    def __init__(
        self,
        url: str | None = None,
        app_name: str | None = None,
        instance_id: str | None = None,
        custom_headers: dict | None = None,
    ):
        self.url = url or getattr(settings, "UNLEASH_URL", None)
        self.app_name = app_name or getattr(settings, "UNLEASH_APP_NAME", "django-matt")
        self.instance_id = instance_id or getattr(settings, "UNLEASH_INSTANCE_ID", None)
        self.custom_headers = custom_headers or getattr(settings, "UNLEASH_HEADERS", {})

        if not self.url:
            raise ValueError("Unleash URL is required")

        self._client = None

    @property
    def client(self):
        """Lazy Unleash client initialization."""
        if self._client is None:
            try:
                from UnleashClient import UnleashClient

                self._client = UnleashClient(
                    url=self.url,
                    app_name=self.app_name,
                    instance_id=self.instance_id,
                    custom_headers=self.custom_headers,
                )
                self._client.initialize_client()
            except ImportError:
                raise ImportError(
                    "UnleashClient is required. Install with: uv add UnleashClient"
                )
        return self._client

    def _build_context(
        self,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> dict:
        """Build Unleash context from user/org/attributes."""
        context = {}

        if user:
            context["userId"] = str(user.pk)
            if hasattr(user, "email") and user.email:
                context["email"] = user.email
            if hasattr(user, "username"):
                context["username"] = user.username

        if organization:
            context["organizationId"] = str(
                organization.pk if hasattr(organization, "pk") else organization
            )

        if attributes:
            context["properties"] = attributes

        return context

    def is_enabled(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: bool = False,
    ) -> bool:
        context = self._build_context(user, organization, attributes)
        return self.client.is_enabled(key, context, default)

    def get_variant(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: str | None = None,
    ) -> str | None:
        context = self._build_context(user, organization, attributes)
        variant = self.client.get_variant(key, context)

        if variant and variant.get("enabled"):
            return variant.get("name")
        return default

    def get_all_flags(
        self,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        # Unleash doesn't have a built-in all_flags method
        # We'd need to maintain a list of known flags
        logger.warning("get_all_flags is not fully supported with Unleash backend")
        return {}

    def invalidate(self, key: str) -> None:
        """Unleash manages its own polling cache; this is a no-op."""

    def invalidate_all(self) -> None:
        """Unleash manages its own polling cache; this is a no-op."""

    def close(self):
        """Close Unleash client."""
        if self._client:
            self._client.destroy()
            self._client = None


class MemoryBackend(FlagBackend):
    """
    In-memory feature flag backend.

    Useful for testing and development.
    """

    def __init__(self):
        self._flags: dict[str, dict] = {}

    def set_flag(
        self,
        key: str,
        enabled: bool = True,
        flag_type: str = "boolean",
        variants: list | None = None,
        rollout_percentage: int = 100,
    ):
        """Set a flag in memory."""
        self._flags[key] = {
            "enabled": enabled,
            "flag_type": flag_type,
            "variants": variants or [],
            "rollout_percentage": rollout_percentage,
            "overrides": {},
        }

    def set_override(
        self,
        key: str,
        user_id: str | None = None,
        enabled: bool = True,
        variant: str | None = None,
    ):
        """Set an override for a flag."""
        if key not in self._flags:
            self.set_flag(key)

        if user_id:
            self._flags[key]["overrides"][user_id] = {
                "enabled": enabled,
                "variant": variant,
            }

    def clear(self):
        """Clear all flags."""
        self._flags.clear()

    def is_enabled(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: bool = False,
    ) -> bool:
        if key not in self._flags:
            return default

        flag = self._flags[key]

        # Check user override
        if user:
            user_id = str(user.pk)
            if user_id in flag.get("overrides", {}):
                return flag["overrides"][user_id]["enabled"]

        # Check percentage rollout
        if flag["flag_type"] == "percentage" and user:
            percentage = flag.get("rollout_percentage", 100)
            hash_input = f"{key}:{user.pk}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            bucket = hash_value % 100
            return bucket < percentage

        return flag.get("enabled", default)

    def get_variant(
        self,
        key: str,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
        default: str | None = None,
    ) -> str | None:
        if key not in self._flags:
            return default

        flag = self._flags[key]

        # Check user override
        if user:
            user_id = str(user.pk)
            if user_id in flag.get("overrides", {}):
                override = flag["overrides"][user_id]
                if override.get("variant"):
                    return override["variant"]

        variants = flag.get("variants", [])
        if not variants:
            return default

        # Calculate consistent variant
        if user:
            hash_input = f"{key}:{user.pk}"
        else:
            import secrets

            hash_input = f"{key}:{secrets.token_hex(8)}"

        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        return variants[hash_value % len(variants)]

    def get_all_flags(
        self,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        return {key: self.is_enabled(key, user, organization, attributes) for key in self._flags}

    def invalidate(self, key: str) -> None:
        """Remove a flag from memory."""
        self._flags.pop(key, None)

    def invalidate_all(self) -> None:
        """Clear all flags from memory."""
        self._flags.clear()


# Backend registry
_backends: dict[str, type[FlagBackend]] = {
    "database": DatabaseBackend,
    "redis": RedisBackend,
    "launchdarkly": LaunchDarklyBackend,
    "unleash": UnleashBackend,
    "memory": MemoryBackend,
}

_default_backend: FlagBackend | None = None


def register_backend(name: str, backend_class: type[FlagBackend]):
    """Register a custom backend."""
    _backends[name] = backend_class


def get_backend(name: str | None = None, **kwargs) -> FlagBackend:
    """
    Get a feature flag backend.

    Args:
        name: Backend name (database, redis, launchdarkly, unleash, memory)
        **kwargs: Backend-specific configuration

    Returns:
        FlagBackend instance
    """
    global _default_backend

    if name is None:
        # Return cached default backend
        if _default_backend is not None:
            return _default_backend

        # Get from settings
        name = getattr(settings, "FEATURE_FLAG_BACKEND", "database")

    if name not in _backends:
        raise ValueError(f"Unknown backend: {name}. Available: {list(_backends.keys())}")

    backend_class = _backends[name]

    # Get backend-specific settings
    backend_settings = getattr(settings, "FEATURE_FLAG_BACKEND_SETTINGS", {})
    config = {**backend_settings.get(name, {}), **kwargs}

    backend = backend_class(**config)

    # Cache as default if using default name
    if name == getattr(settings, "FEATURE_FLAG_BACKEND", "database"):
        _default_backend = backend

    return backend


def reset_default_backend():
    """Reset the cached default backend."""
    global _default_backend
    if _default_backend:
        _default_backend.close()
        _default_backend = None


__all__ = [
    "FlagBackend",
    "DatabaseBackend",
    "RedisBackend",
    "LaunchDarklyBackend",
    "UnleashBackend",
    "MemoryBackend",
    "get_backend",
    "register_backend",
    "reset_default_backend",
]
