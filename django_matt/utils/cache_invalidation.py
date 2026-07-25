# file-length-max: 600
"""
Cache invalidation utilities for Django Matt.

Provides automatic cache invalidation when model instances are saved or deleted,
using Django's signal system.

Usage:
    # Option 1: Mixin for automatic cache invalidation
    from django_matt.utils.cache_invalidation import CacheInvalidationMixin

    class Product(CacheInvalidationMixin, models.Model):
        name = models.CharField(max_length=100)
        price = models.DecimalField(...)

        class CacheMeta:
            cache_key_prefix = "product"
            invalidate_related = ["category"]  # Also invalidate related objects


    # Option 2: Manual registration
    from django_matt.utils.cache_invalidation import register_cache_invalidation

    register_cache_invalidation(Product, cache_key_prefix="product")


    # Option 3: Decorator for view caching with auto-invalidation
    from django_matt.utils.cache_invalidation import cached_view

    @cached_view(timeout=300, model=Product)
    async def get_products(request):
        return Product.objects.all()
"""

from __future__ import annotations

import functools
import hashlib
import logging
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from django.core.cache import cache as default_cache
from django.core.cache import caches
from django.db.models import Model
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete

if TYPE_CHECKING:
    from django.core.cache.backends.base import BaseCache
    from django.http import HttpRequest

logger = logging.getLogger("django_matt.cache")

F = TypeVar("F", bound=Callable[..., Any])


class CacheInvalidator:
    """
    Manages cache invalidation for models.

    This class handles the registration and execution of cache invalidation
    when model instances are created, updated, or deleted.
    """

    def __init__(self, cache_alias: str = "default"):
        """
        Initialize the cache invalidator.

        Args:
            cache_alias: The cache alias to use (default: "default")
        """
        self._cache_alias = cache_alias
        self._registered_models: dict[type[Model], dict[str, Any]] = {}
        self._invalidation_callbacks: dict[type[Model], list[Callable]] = {}

    @property
    def cache(self) -> BaseCache:
        """Get the cache backend."""
        return caches[self._cache_alias]

    def register(
        self,
        model: type[Model],
        cache_key_prefix: str | None = None,
        invalidate_related: list[str] | None = None,
        invalidate_on_save: bool = True,
        invalidate_on_delete: bool = True,
        custom_key_generator: Callable[[Model], list[str]] | None = None,
    ) -> None:
        """
        Register a model for automatic cache invalidation.

        Args:
            model: The Django model class to register
            cache_key_prefix: Prefix for cache keys (defaults to model name)
            invalidate_related: List of related field names to also invalidate
            invalidate_on_save: Invalidate cache on save (default: True)
            invalidate_on_delete: Invalidate cache on delete (default: True)
            custom_key_generator: Optional function to generate custom cache keys
        """
        if model in self._registered_models:
            logger.warning(f"Model {model.__name__} is already registered for cache invalidation")
            return

        prefix = cache_key_prefix or model.__name__.lower()

        self._registered_models[model] = {
            "prefix": prefix,
            "invalidate_related": invalidate_related or [],
            "custom_key_generator": custom_key_generator,
        }

        # Connect signals
        if invalidate_on_save:
            post_save.connect(
                self._handle_save,
                sender=model,
                dispatch_uid=f"cache_invalidation_save_{model.__name__}",
            )

        if invalidate_on_delete:
            post_delete.connect(
                self._handle_delete,
                sender=model,
                dispatch_uid=f"cache_invalidation_delete_{model.__name__}",
            )
            pre_delete.connect(
                self._handle_pre_delete,
                sender=model,
                dispatch_uid=f"cache_invalidation_pre_delete_{model.__name__}",
            )

        # Connect M2M signals if there are M2M fields
        for field in model._meta.get_fields():
            if field.many_to_many and hasattr(field, "through"):
                m2m_changed.connect(
                    self._handle_m2m_changed,
                    sender=field.remote_field.through,
                    dispatch_uid=f"cache_invalidation_m2m_{model.__name__}_{field.name}",
                )

        logger.debug(f"Registered {model.__name__} for cache invalidation with prefix '{prefix}'")

    def unregister(self, model: type[Model]) -> None:
        """
        Unregister a model from cache invalidation.

        Args:
            model: The Django model class to unregister
        """
        if model not in self._registered_models:
            return

        # Disconnect signals
        post_save.disconnect(
            self._handle_save,
            sender=model,
            dispatch_uid=f"cache_invalidation_save_{model.__name__}",
        )
        post_delete.disconnect(
            self._handle_delete,
            sender=model,
            dispatch_uid=f"cache_invalidation_delete_{model.__name__}",
        )
        pre_delete.disconnect(
            self._handle_pre_delete,
            sender=model,
            dispatch_uid=f"cache_invalidation_pre_delete_{model.__name__}",
        )

        del self._registered_models[model]
        logger.debug(f"Unregistered {model.__name__} from cache invalidation")

    def add_callback(self, model: type[Model], callback: Callable[[Model, str], None]) -> None:
        """
        Add a callback to be called when cache is invalidated for a model.

        Args:
            model: The model class
            callback: Function(instance, action) where action is 'save' or 'delete'
        """
        if model not in self._invalidation_callbacks:
            self._invalidation_callbacks[model] = []
        self._invalidation_callbacks[model].append(callback)

    def get_cache_keys(self, instance: Model) -> list[str]:
        """
        Get all cache keys that should be invalidated for a model instance.

        Args:
            instance: The model instance

        Returns:
            List of cache keys to invalidate
        """
        model = instance.__class__
        if model not in self._registered_models:
            return []

        config = self._registered_models[model]
        prefix = config["prefix"]
        keys = []

        # Custom key generator
        if config["custom_key_generator"]:
            keys.extend(config["custom_key_generator"](instance))
        else:
            # Standard keys
            pk = instance.pk
            keys.extend(
                [
                    f"{prefix}:list",  # List cache
                    f"{prefix}:{pk}",  # Single object cache
                    f"{prefix}:detail:{pk}",  # Detail view cache
                    f"{prefix}:count",  # Count cache
                ]
            )

        # Related object keys
        for related_field in config["invalidate_related"]:
            related_obj = getattr(instance, related_field, None)
            if related_obj is not None:
                if hasattr(related_obj, "pk"):
                    # Single related object
                    related_prefix = related_obj.__class__.__name__.lower()
                    keys.append(f"{related_prefix}:{related_obj.pk}")
                    keys.append(f"{related_prefix}:list")
                elif hasattr(related_obj, "all"):
                    # Related manager (reverse relation)
                    for obj in related_obj.all():
                        related_prefix = obj.__class__.__name__.lower()
                        keys.append(f"{related_prefix}:{obj.pk}")

        return keys

    def invalidate(self, instance: Model, action: str = "update") -> int:
        """
        Invalidate cache for a model instance.

        Args:
            instance: The model instance
            action: The action that triggered invalidation ('save', 'delete', 'update')

        Returns:
            Number of keys invalidated
        """
        keys = self.get_cache_keys(instance)
        if not keys:
            return 0

        # Delete all keys
        self.cache.delete_many(keys)

        # Call callbacks
        model = instance.__class__
        if model in self._invalidation_callbacks:
            for callback in self._invalidation_callbacks[model]:
                try:
                    callback(instance, action)
                except Exception as e:
                    logger.error(f"Cache invalidation callback error: {e}")

        logger.debug(f"Invalidated {len(keys)} cache keys for {model.__name__}:{instance.pk}")
        return len(keys)

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache keys matching a pattern.

        Note: This only works with cache backends that support pattern deletion
        (e.g., Redis with django-redis).

        Args:
            pattern: Pattern to match (e.g., "product:*")

        Returns:
            Number of keys deleted, or -1 if not supported
        """
        # Try to use delete_pattern if available (django-redis)
        if hasattr(self.cache, "delete_pattern"):
            return self.cache.delete_pattern(pattern)

        # For other backends, we can't do pattern matching
        logger.warning(f"Cache backend does not support pattern deletion: {pattern}")
        return -1

    def _handle_save(
        self, sender: type[Model], instance: Model, created: bool, **kwargs: Any
    ) -> None:
        """Handle post_save signal."""
        action = "create" if created else "update"
        self.invalidate(instance, action)

    def _handle_delete(self, sender: type[Model], instance: Model, **kwargs: Any) -> None:
        """Handle post_delete signal."""
        self.invalidate(instance, "delete")

    def _handle_pre_delete(self, sender: type[Model], instance: Model, **kwargs: Any) -> None:
        """
        Handle pre_delete signal.

        This is needed to capture related objects before they're deleted.
        """
        # Store related object keys for invalidation after delete
        model = instance.__class__
        if model not in self._registered_models:
            return

        config = self._registered_models[model]
        for related_field in config["invalidate_related"]:
            related_obj = getattr(instance, related_field, None)
            if related_obj is not None and hasattr(related_obj, "all"):
                # Cache the related objects to invalidate after delete
                instance._cache_invalidation_related = list(related_obj.all())

    def _handle_m2m_changed(
        self,
        sender: type[Model],
        instance: Model,
        action: str,
        **kwargs: Any,
    ) -> None:
        """Handle m2m_changed signal."""
        if action in ("post_add", "post_remove", "post_clear"):
            self.invalidate(instance, "m2m_change")


# Global cache invalidator instance
cache_invalidator = CacheInvalidator()


def register_cache_invalidation(
    model: type[Model],
    cache_key_prefix: str | None = None,
    invalidate_related: list[str] | None = None,
    invalidate_on_save: bool = True,
    invalidate_on_delete: bool = True,
    custom_key_generator: Callable[[Model], list[str]] | None = None,
) -> None:
    """
    Register a model for automatic cache invalidation.

    This is a convenience function that uses the global cache invalidator.

    Args:
        model: The Django model class to register
        cache_key_prefix: Prefix for cache keys (defaults to model name)
        invalidate_related: List of related field names to also invalidate
        invalidate_on_save: Invalidate cache on save (default: True)
        invalidate_on_delete: Invalidate cache on delete (default: True)
        custom_key_generator: Optional function to generate custom cache keys

    Example:
        from django_matt.utils.cache_invalidation import register_cache_invalidation

        register_cache_invalidation(
            Product,
            cache_key_prefix="product",
            invalidate_related=["category", "tags"],
        )
    """
    cache_invalidator.register(
        model=model,
        cache_key_prefix=cache_key_prefix,
        invalidate_related=invalidate_related,
        invalidate_on_save=invalidate_on_save,
        invalidate_on_delete=invalidate_on_delete,
        custom_key_generator=custom_key_generator,
    )


class CacheInvalidationMixin:
    """
    Mixin for Django models to enable automatic cache invalidation.

    Add this mixin to your model to automatically invalidate cache
    when instances are saved or deleted.

    Example:
        from django_matt.utils.cache_invalidation import CacheInvalidationMixin

        class Product(CacheInvalidationMixin, models.Model):
            name = models.CharField(max_length=100)

            class CacheMeta:
                cache_key_prefix = "product"
                invalidate_related = ["category"]
    """

    class CacheMeta:
        """Cache configuration for the model."""

        cache_key_prefix: str | None = None
        invalidate_related: list[str] = []
        invalidate_on_save: bool = True
        invalidate_on_delete: bool = True

    @classmethod
    def _register_cache_invalidation(cls) -> None:
        """Register this model for cache invalidation."""
        meta = getattr(cls, "CacheMeta", CacheInvalidationMixin.CacheMeta)
        register_cache_invalidation(
            model=cls,
            cache_key_prefix=getattr(meta, "cache_key_prefix", None),
            invalidate_related=getattr(meta, "invalidate_related", []),
            invalidate_on_save=getattr(meta, "invalidate_on_save", True),
            invalidate_on_delete=getattr(meta, "invalidate_on_delete", True),
        )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register the model when a subclass is created."""
        super().__init_subclass__(**kwargs)
        # Only register if this is a concrete model (has _meta)
        if hasattr(cls, "_meta") and not cls._meta.abstract:
            cls._register_cache_invalidation()


def cached_view(
    timeout: int = 300,
    key_prefix: str = "view",
    model: type[Model] | None = None,
    vary_on: list[str] | None = None,
    cache_alias: str = "default",
) -> Callable[[F], F]:
    """
    Decorator for view caching with automatic invalidation.

    Caches the view response and automatically invalidates when the
    associated model is modified.

    Args:
        timeout: Cache timeout in seconds (default: 300)
        key_prefix: Prefix for cache keys
        model: Model class to associate with this view for invalidation
        vary_on: List of request attributes to vary cache on (e.g., ["user.id"])
        cache_alias: Cache alias to use

    Example:
        @cached_view(timeout=300, model=Product, vary_on=["user.id"])
        async def get_products(request):
            return {"products": list(Product.objects.all())}
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            cache_key = _generate_view_cache_key(func, key_prefix, request, vary_on, args, kwargs)

            # Try to get from cache
            cached = caches[cache_alias].get(cache_key)
            if cached is not None:
                return cached

            # Call the view
            result = await func(request, *args, **kwargs)

            # Cache the result
            caches[cache_alias].set(cache_key, result, timeout)

            return result

        @functools.wraps(func)
        def sync_wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            cache_key = _generate_view_cache_key(func, key_prefix, request, vary_on, args, kwargs)

            # Try to get from cache
            cached = caches[cache_alias].get(cache_key)
            if cached is not None:
                return cached

            # Call the view
            result = func(request, *args, **kwargs)

            # Cache the result
            caches[cache_alias].set(cache_key, result, timeout)

            return result

        # If model is specified, register for invalidation
        if model is not None:

            def invalidate_callback(instance: Model, action: str) -> None:
                # Invalidate all cached views for this model
                caches[cache_alias].delete_many([f"{key_prefix}:{func.__name__}:*"])

            cache_invalidator.add_callback(model, invalidate_callback)

        # Return appropriate wrapper based on async
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def _generate_view_cache_key(
    func: Callable,
    prefix: str,
    request: HttpRequest,
    vary_on: list[str] | None,
    args: tuple,
    kwargs: dict,
) -> str:
    """Generate a cache key for a view."""
    parts = [prefix, func.__name__]

    # Add vary_on attributes
    if vary_on:
        for attr in vary_on:
            value = request
            for part in attr.split("."):
                value = getattr(value, part, None)
            parts.append(f"{attr}={value}")

    # Add args and kwargs
    if args:
        parts.append(f"args={args}")
    if kwargs:
        parts.append(f"kwargs={sorted(kwargs.items())}")

    # Generate hash
    key_string = ":".join(str(p) for p in parts)
    return f"{prefix}:{func.__name__}:{hashlib.md5(key_string.encode()).hexdigest()}"


def invalidate_cache_for_model(model: type[Model], instance: Model | None = None) -> int:
    """
    Manually invalidate cache for a model.

    Args:
        model: The model class
        instance: Specific instance to invalidate (if None, invalidates list cache)

    Returns:
        Number of keys invalidated
    """
    if instance is not None:
        return cache_invalidator.invalidate(instance, "manual")

    # Invalidate list cache
    prefix = model.__name__.lower()
    keys = [f"{prefix}:list", f"{prefix}:count"]
    default_cache.delete_many(keys)
    return len(keys)


__all__ = [
    "CacheInvalidator",
    "CacheInvalidationMixin",
    "cache_invalidator",
    "register_cache_invalidation",
    "cached_view",
    "invalidate_cache_for_model",
]
