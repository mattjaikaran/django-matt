"""
DataLoader implementation for Django Matt GraphQL.

Provides batched data loading to prevent N+1 query problems.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Callable, Generic, TypeVar, overload

from django.db import models

try:
    import strawberry
    from strawberry.dataloader import DataLoader
    from strawberry.types import Info
    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False
    DataLoader = object
    Info = Any


K = TypeVar("K")
V = TypeVar("V")


def _require_strawberry():
    """Raise an error if strawberry is not installed."""
    if not STRAWBERRY_AVAILABLE:
        raise ImportError(
            "strawberry-graphql is required for DataLoaders. "
            "Install it with: pip install strawberry-graphql[django]"
        )


class ModelDataLoader(Generic[V]):
    """
    DataLoader for loading Django model instances by ID.

    Usage:
        loader = ModelDataLoader(User)
        user = await loader.load(1)
        users = await loader.load_many([1, 2, 3])
    """

    def __init__(
        self,
        model: type[models.Model],
        type_class: type | None = None,
        lookup_field: str = "pk",
        select_related: list[str] | None = None,
        prefetch_related: list[str] | None = None,
        cache: bool = True,
    ):
        """
        Initialize the model data loader.

        Args:
            model: Django model class
            type_class: Optional Strawberry type to convert results to
            lookup_field: Field to look up by (default: pk)
            select_related: Fields to select_related
            prefetch_related: Fields to prefetch_related
            cache: Whether to cache results
        """
        _require_strawberry()
        self.model = model
        self.type_class = type_class
        self.lookup_field = lookup_field
        self.select_related = select_related or []
        self.prefetch_related = prefetch_related or []

        # Create the underlying DataLoader
        self._loader = DataLoader(load_fn=self._batch_load)

        # Local cache for the current request
        self._cache: dict[Any, V] = {} if cache else None

    async def _batch_load(self, keys: list[Any]) -> list[V | None]:
        """Batch load function for DataLoader."""
        # Build queryset
        queryset = self.model.objects.filter(**{f"{self.lookup_field}__in": keys})

        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        if self.prefetch_related:
            queryset = queryset.prefetch_related(*self.prefetch_related)

        # Fetch all objects
        objects = {getattr(obj, self.lookup_field): obj for obj in queryset}

        # Build results in the same order as keys
        results = []
        for key in keys:
            obj = objects.get(key)
            if obj is not None and self.type_class:
                if hasattr(self.type_class, "from_orm"):
                    obj = self.type_class.from_orm(obj)
            results.append(obj)

        return results

    async def load(self, key: Any) -> V | None:
        """
        Load a single item by key.

        Args:
            key: The key (usually ID) to load

        Returns:
            The loaded object or None
        """
        # Check local cache first
        if self._cache is not None and key in self._cache:
            return self._cache[key]

        result = await self._loader.load(key)

        # Cache the result
        if self._cache is not None:
            self._cache[key] = result

        return result

    async def load_many(self, keys: list[Any]) -> list[V | None]:
        """
        Load multiple items by keys.

        Args:
            keys: List of keys to load

        Returns:
            List of loaded objects (None for missing)
        """
        # Check cache for already loaded items
        if self._cache is not None:
            cached_results = {}
            missing_keys = []
            for key in keys:
                if key in self._cache:
                    cached_results[key] = self._cache[key]
                else:
                    missing_keys.append(key)

            if not missing_keys:
                return [cached_results.get(key) for key in keys]

            # Load missing items
            loaded = await self._loader.load_many(missing_keys)
            for key, result in zip(missing_keys, loaded):
                self._cache[key] = result
                cached_results[key] = result

            return [cached_results.get(key) for key in keys]

        return await self._loader.load_many(keys)

    def prime(self, key: Any, value: V) -> None:
        """
        Prime the cache with a value.

        Args:
            key: The key
            value: The value to cache
        """
        if self._cache is not None:
            self._cache[key] = value

    def clear(self, key: Any | None = None) -> None:
        """
        Clear the cache.

        Args:
            key: Specific key to clear (None = clear all)
        """
        if self._cache is not None:
            if key is None:
                self._cache.clear()
            else:
                self._cache.pop(key, None)


class RelatedDataLoader(Generic[V]):
    """
    DataLoader for loading related objects (foreign key, many-to-many).

    Usage:
        # For ForeignKey (one-to-many from parent's perspective)
        posts_loader = RelatedDataLoader(Post, "author_id", PostType)
        posts = await posts_loader.load(user_id)

        # For ManyToMany
        tags_loader = RelatedDataLoader(Tag, "posts__id", TagType, many_to_many=True)
        tags = await tags_loader.load(post_id)
    """

    def __init__(
        self,
        model: type[models.Model],
        related_field: str,
        type_class: type | None = None,
        select_related: list[str] | None = None,
        prefetch_related: list[str] | None = None,
        order_by: list[str] | None = None,
        cache: bool = True,
    ):
        """
        Initialize the related data loader.

        Args:
            model: Django model class of related objects
            related_field: Field name linking to parent (e.g., "author_id")
            type_class: Optional Strawberry type
            select_related: Fields to select_related
            prefetch_related: Fields to prefetch_related
            order_by: Fields to order by
            cache: Whether to cache results
        """
        _require_strawberry()
        self.model = model
        self.related_field = related_field
        self.type_class = type_class
        self.select_related = select_related or []
        self.prefetch_related = prefetch_related or []
        self.order_by = order_by or []

        self._loader = DataLoader(load_fn=self._batch_load)
        self._cache: dict[Any, list[V]] = {} if cache else None

    async def _batch_load(self, keys: list[Any]) -> list[list[V]]:
        """Batch load related objects."""
        # Build queryset
        queryset = self.model.objects.filter(**{f"{self.related_field}__in": keys})

        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        if self.prefetch_related:
            queryset = queryset.prefetch_related(*self.prefetch_related)
        if self.order_by:
            queryset = queryset.order_by(*self.order_by)

        # Group objects by related key
        grouped: dict[Any, list] = defaultdict(list)
        for obj in queryset:
            # Get the related field value (handle both field and field_id)
            if self.related_field.endswith("_id"):
                key = getattr(obj, self.related_field)
            else:
                related_obj = getattr(obj, self.related_field.replace("__id", ""), None)
                if related_obj:
                    key = related_obj.pk if hasattr(related_obj, "pk") else related_obj
                else:
                    key = getattr(obj, f"{self.related_field}_id", None)

            # Convert to type if specified
            if self.type_class and hasattr(self.type_class, "from_orm"):
                obj = self.type_class.from_orm(obj)

            grouped[key].append(obj)

        # Return results in same order as keys
        return [grouped.get(key, []) for key in keys]

    async def load(self, key: Any) -> list[V]:
        """
        Load related objects for a key.

        Args:
            key: Parent object's ID

        Returns:
            List of related objects
        """
        if self._cache is not None and key in self._cache:
            return self._cache[key]

        result = await self._loader.load(key)

        if self._cache is not None:
            self._cache[key] = result

        return result

    async def load_many(self, keys: list[Any]) -> list[list[V]]:
        """
        Load related objects for multiple keys.

        Args:
            keys: List of parent IDs

        Returns:
            List of lists of related objects
        """
        return await self._loader.load_many(keys)


class DataLoaderRegistry:
    """
    Registry for managing DataLoaders per request.

    Each request should have its own registry to ensure proper caching.

    Usage:
        # In your middleware or context setup
        registry = DataLoaderRegistry()
        registry.register_model(User, UserType)
        registry.register_model(Post, PostType)

        # In your context
        context["dataloaders"] = registry

        # In your resolver
        loader = info.context["dataloaders"].get_loader(User)
        user = await loader.load(user_id)
    """

    def __init__(self):
        """Initialize the registry."""
        _require_strawberry()
        self._model_loaders: dict[type[models.Model], ModelDataLoader] = {}
        self._related_loaders: dict[tuple, RelatedDataLoader] = {}
        self._custom_loaders: dict[str, DataLoader] = {}

    def register_model(
        self,
        model: type[models.Model],
        type_class: type | None = None,
        lookup_field: str = "pk",
        select_related: list[str] | None = None,
        prefetch_related: list[str] | None = None,
    ) -> ModelDataLoader:
        """
        Register a model loader.

        Args:
            model: Django model class
            type_class: Strawberry type class
            lookup_field: Field to look up by
            select_related: Fields to select_related
            prefetch_related: Fields to prefetch_related

        Returns:
            The created ModelDataLoader
        """
        loader = ModelDataLoader(
            model=model,
            type_class=type_class,
            lookup_field=lookup_field,
            select_related=select_related,
            prefetch_related=prefetch_related,
        )
        self._model_loaders[model] = loader
        return loader

    def register_related(
        self,
        model: type[models.Model],
        related_field: str,
        type_class: type | None = None,
        select_related: list[str] | None = None,
        prefetch_related: list[str] | None = None,
        order_by: list[str] | None = None,
    ) -> RelatedDataLoader:
        """
        Register a related objects loader.

        Args:
            model: Django model class of related objects
            related_field: Field linking to parent
            type_class: Strawberry type class
            select_related: Fields to select_related
            prefetch_related: Fields to prefetch_related
            order_by: Fields to order by

        Returns:
            The created RelatedDataLoader
        """
        key = (model, related_field)
        loader = RelatedDataLoader(
            model=model,
            related_field=related_field,
            type_class=type_class,
            select_related=select_related,
            prefetch_related=prefetch_related,
            order_by=order_by,
        )
        self._related_loaders[key] = loader
        return loader

    def register_custom(
        self,
        name: str,
        load_fn: Callable[[list], list],
    ) -> DataLoader:
        """
        Register a custom loader.

        Args:
            name: Unique name for the loader
            load_fn: Batch loading function

        Returns:
            The created DataLoader
        """
        loader = DataLoader(load_fn=load_fn)
        self._custom_loaders[name] = loader
        return loader

    def get_loader(self, model: type[models.Model]) -> ModelDataLoader | None:
        """
        Get the loader for a model.

        Args:
            model: Django model class

        Returns:
            ModelDataLoader or None
        """
        return self._model_loaders.get(model)

    def get_related_loader(
        self,
        model: type[models.Model],
        related_field: str,
    ) -> RelatedDataLoader | None:
        """
        Get the related loader.

        Args:
            model: Django model class
            related_field: Related field name

        Returns:
            RelatedDataLoader or None
        """
        return self._related_loaders.get((model, related_field))

    def get_custom_loader(self, name: str) -> DataLoader | None:
        """
        Get a custom loader by name.

        Args:
            name: Loader name

        Returns:
            DataLoader or None
        """
        return self._custom_loaders.get(name)

    def clear_all(self) -> None:
        """Clear all loader caches."""
        for loader in self._model_loaders.values():
            loader.clear()
        for loader in self._related_loaders.values():
            loader.clear()


def get_loader(
    info: Info,
    model: type[models.Model],
) -> ModelDataLoader | None:
    """
    Get a DataLoader from the GraphQL context.

    Args:
        info: Strawberry Info object
        model: Django model class

    Returns:
        ModelDataLoader or None
    """
    _require_strawberry()
    registry = info.context.get("dataloaders")
    if registry:
        return registry.get_loader(model)
    return None


def create_dataloaders(
    models: list[type[models.Model]],
    type_map: dict[type[models.Model], type] | None = None,
) -> DataLoaderRegistry:
    """
    Create a DataLoaderRegistry with loaders for the given models.

    Args:
        models: List of Django model classes
        type_map: Optional mapping of models to Strawberry types

    Returns:
        Configured DataLoaderRegistry
    """
    _require_strawberry()
    registry = DataLoaderRegistry()
    type_map = type_map or {}

    for model in models:
        type_class = type_map.get(model)
        registry.register_model(model, type_class)

    return registry


__all__ = [
    "ModelDataLoader",
    "RelatedDataLoader",
    "DataLoaderRegistry",
    "get_loader",
    "create_dataloaders",
]
