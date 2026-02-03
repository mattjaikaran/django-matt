"""
Experiment storage backends.

Provides different storage backends for experiment data:
- DatabaseBackend: Uses Django ORM (default)
- RedisBackend: Uses Redis for high-performance assignment lookups
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.cache import cache

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from django_matt.experiments.models import (
        Experiment,
        ExperimentAssignment,
        Variant,
    )

logger = logging.getLogger("django_matt.experiments")


class ExperimentBackend(ABC):
    """Base class for experiment backends."""

    @abstractmethod
    def get_experiment(self, key: str) -> "Experiment | None":
        """Get an experiment by key."""
        pass

    @abstractmethod
    def get_assignment(
        self,
        experiment_key: str,
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
    ) -> "ExperimentAssignment | None":
        """Get an existing assignment."""
        pass

    @abstractmethod
    def create_assignment(
        self,
        experiment: "Experiment",
        variant: "Variant | None",
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
        is_holdout: bool = False,
        context: dict[str, Any] | None = None,
    ) -> "ExperimentAssignment":
        """Create a new assignment."""
        pass

    @abstractmethod
    def get_all_experiments(
        self,
        status: str | None = None,
    ) -> list["Experiment"]:
        """Get all experiments, optionally filtered by status."""
        pass

    def close(self):
        """Clean up resources."""
        pass


class DatabaseBackend(ExperimentBackend):
    """
    Database-backed experiment backend.

    Uses Django ORM for experiment storage with optional caching.
    """

    def __init__(
        self,
        cache_timeout: int = 60,
        cache_prefix: str = "experiments:",
        use_cache: bool = True,
    ):
        self.cache_timeout = cache_timeout
        self.cache_prefix = cache_prefix
        self.use_cache = use_cache

    def _get_cache_key(self, key: str) -> str:
        """Get cache key for an experiment."""
        return f"{self.cache_prefix}{key}"

    def _get_assignment_cache_key(
        self,
        experiment_key: str,
        user_id: str | None,
        anonymous_id: str | None,
    ) -> str:
        """Get cache key for an assignment."""
        identifier = user_id or anonymous_id or "unknown"
        return f"{self.cache_prefix}assignment:{experiment_key}:{identifier}"

    def get_experiment(self, key: str) -> "Experiment | None":
        """Get experiment from database with caching."""
        from django_matt.experiments.models import Experiment

        if self.use_cache:
            cache_key = self._get_cache_key(key)
            experiment = cache.get(cache_key)
            if experiment is not None:
                if experiment == "__NOT_FOUND__":
                    return None
                return experiment

        try:
            experiment = Experiment.objects.prefetch_related("variants").get(key=key)
            if self.use_cache:
                cache.set(cache_key, experiment, self.cache_timeout)
            return experiment
        except Experiment.DoesNotExist:
            if self.use_cache:
                cache.set(cache_key, "__NOT_FOUND__", self.cache_timeout)
            return None

    def get_assignment(
        self,
        experiment_key: str,
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
    ) -> "ExperimentAssignment | None":
        """Get existing assignment."""
        from django_matt.experiments.models import ExperimentAssignment

        # Check cache
        if self.use_cache:
            user_id = str(user.pk) if user else None
            cache_key = self._get_assignment_cache_key(
                experiment_key, user_id, anonymous_id
            )
            assignment = cache.get(cache_key)
            if assignment is not None:
                if assignment == "__NOT_FOUND__":
                    return None
                return assignment

        # Query database
        try:
            if user:
                assignment = ExperimentAssignment.objects.select_related(
                    "experiment", "variant"
                ).get(
                    experiment__key=experiment_key,
                    user=user,
                )
            elif anonymous_id:
                assignment = ExperimentAssignment.objects.select_related(
                    "experiment", "variant"
                ).get(
                    experiment__key=experiment_key,
                    anonymous_id=anonymous_id,
                )
            else:
                return None

            # Cache result
            if self.use_cache:
                cache.set(cache_key, assignment, self.cache_timeout)

            return assignment

        except ExperimentAssignment.DoesNotExist:
            if self.use_cache:
                cache.set(cache_key, "__NOT_FOUND__", self.cache_timeout)
            return None

    def create_assignment(
        self,
        experiment: "Experiment",
        variant: "Variant | None",
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
        is_holdout: bool = False,
        context: dict[str, Any] | None = None,
    ) -> "ExperimentAssignment":
        """Create a new assignment."""
        from django_matt.experiments.models import ExperimentAssignment

        assignment = ExperimentAssignment.objects.create(
            experiment=experiment,
            variant=variant,
            user=user,
            anonymous_id=anonymous_id or "",
            is_holdout=is_holdout,
            context=context or {},
        )

        # Update cache
        if self.use_cache:
            user_id = str(user.pk) if user else None
            cache_key = self._get_assignment_cache_key(
                experiment.key, user_id, anonymous_id
            )
            cache.set(cache_key, assignment, self.cache_timeout)

        return assignment

    def get_all_experiments(
        self,
        status: str | None = None,
    ) -> list["Experiment"]:
        """Get all experiments."""
        from django_matt.experiments.models import Experiment

        qs = Experiment.objects.prefetch_related("variants")

        if status:
            qs = qs.filter(status=status)

        return list(qs)

    def invalidate_cache(self, experiment_key: str | None = None):
        """Invalidate cache for a specific experiment or all experiments."""
        if experiment_key:
            cache.delete(self._get_cache_key(experiment_key))
        # For full cache clear, would need pattern deletion support


class RedisBackend(ExperimentBackend):
    """
    Redis-backed experiment backend.

    Optimized for high-performance assignment lookups.
    Experiment definitions are cached in Redis with database fallback.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        cache_timeout: int = 300,
        key_prefix: str = "experiments:",
    ):
        self.redis_url = redis_url or getattr(
            settings, "REDIS_URL", "redis://localhost:6379/0"
        )
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
                    "redis package is required for RedisBackend. Install with: pip install redis"
                )
        return self._client

    def _get_key(self, key: str) -> str:
        """Get Redis key."""
        return f"{self.key_prefix}{key}"

    def _get_assignment_key(
        self,
        experiment_key: str,
        user_id: str | None,
        anonymous_id: str | None,
    ) -> str:
        """Get Redis key for assignment."""
        identifier = user_id or anonymous_id or "unknown"
        return f"{self.key_prefix}assignment:{experiment_key}:{identifier}"

    def _serialize_experiment(self, experiment: "Experiment") -> str:
        """Serialize experiment to JSON."""
        variants_data = []
        for v in experiment.variants.all():
            variants_data.append({
                "id": str(v.id),
                "key": v.key,
                "name": v.name,
                "is_control": v.is_control,
                "weight": v.weight,
                "payload": v.payload,
            })

        data = {
            "id": str(experiment.id),
            "key": experiment.key,
            "name": experiment.name,
            "status": experiment.status,
            "strategy": experiment.strategy,
            "epsilon": experiment.epsilon,
            "exploration_weight": experiment.exploration_weight,
            "holdout_percentage": experiment.holdout_percentage,
            "targeting_rules": experiment.targeting_rules,
            "exclusion_group": experiment.exclusion_group,
            "min_sample_size": experiment.min_sample_size,
            "target_confidence": experiment.target_confidence,
            "primary_metric": experiment.primary_metric,
            "variants": variants_data,
        }
        return json.dumps(data)

    def _serialize_assignment(self, assignment: "ExperimentAssignment") -> str:
        """Serialize assignment to JSON."""
        data = {
            "id": str(assignment.id),
            "experiment_key": assignment.experiment.key,
            "variant_id": str(assignment.variant.id) if assignment.variant else None,
            "variant_key": assignment.variant.key if assignment.variant else None,
            "user_id": str(assignment.user_id) if assignment.user_id else None,
            "anonymous_id": assignment.anonymous_id,
            "is_holdout": assignment.is_holdout,
            "assigned_at": assignment.assigned_at.isoformat(),
        }
        return json.dumps(data)

    def get_experiment(self, key: str) -> "Experiment | None":
        """Get experiment from Redis with database fallback."""
        from django_matt.experiments.models import Experiment

        redis_key = self._get_key(key)

        # Try Redis first
        data = self.client.get(redis_key)
        if data:
            # Return the actual database object (we use Redis just for caching check)
            try:
                return Experiment.objects.prefetch_related("variants").get(key=key)
            except Experiment.DoesNotExist:
                return None

        # Fallback to database and cache
        try:
            experiment = Experiment.objects.prefetch_related("variants").get(key=key)
            serialized = self._serialize_experiment(experiment)
            self.client.setex(redis_key, self.cache_timeout, serialized)
            return experiment
        except Experiment.DoesNotExist:
            return None

    def get_assignment(
        self,
        experiment_key: str,
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
    ) -> "ExperimentAssignment | None":
        """Get assignment from Redis with database fallback."""
        from django_matt.experiments.models import ExperimentAssignment

        user_id = str(user.pk) if user else None
        redis_key = self._get_assignment_key(experiment_key, user_id, anonymous_id)

        # Try Redis first
        data = self.client.get(redis_key)
        if data:
            # Return actual database object
            try:
                if user:
                    return ExperimentAssignment.objects.select_related(
                        "experiment", "variant"
                    ).get(experiment__key=experiment_key, user=user)
                elif anonymous_id:
                    return ExperimentAssignment.objects.select_related(
                        "experiment", "variant"
                    ).get(experiment__key=experiment_key, anonymous_id=anonymous_id)
            except ExperimentAssignment.DoesNotExist:
                return None

        # Fallback to database
        try:
            if user:
                assignment = ExperimentAssignment.objects.select_related(
                    "experiment", "variant"
                ).get(experiment__key=experiment_key, user=user)
            elif anonymous_id:
                assignment = ExperimentAssignment.objects.select_related(
                    "experiment", "variant"
                ).get(experiment__key=experiment_key, anonymous_id=anonymous_id)
            else:
                return None

            # Cache in Redis
            serialized = self._serialize_assignment(assignment)
            self.client.setex(redis_key, self.cache_timeout, serialized)
            return assignment

        except ExperimentAssignment.DoesNotExist:
            return None

    def create_assignment(
        self,
        experiment: "Experiment",
        variant: "Variant | None",
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
        is_holdout: bool = False,
        context: dict[str, Any] | None = None,
    ) -> "ExperimentAssignment":
        """Create assignment and cache in Redis."""
        from django_matt.experiments.models import ExperimentAssignment

        assignment = ExperimentAssignment.objects.create(
            experiment=experiment,
            variant=variant,
            user=user,
            anonymous_id=anonymous_id or "",
            is_holdout=is_holdout,
            context=context or {},
        )

        # Cache in Redis
        user_id = str(user.pk) if user else None
        redis_key = self._get_assignment_key(experiment.key, user_id, anonymous_id)
        serialized = self._serialize_assignment(assignment)
        self.client.setex(redis_key, self.cache_timeout, serialized)

        return assignment

    def get_all_experiments(
        self,
        status: str | None = None,
    ) -> list["Experiment"]:
        """Get all experiments from database."""
        from django_matt.experiments.models import Experiment

        qs = Experiment.objects.prefetch_related("variants")

        if status:
            qs = qs.filter(status=status)

        return list(qs)

    def invalidate(self, experiment_key: str):
        """Invalidate cache for a specific experiment."""
        self.client.delete(self._get_key(experiment_key))

    def invalidate_assignment(
        self,
        experiment_key: str,
        user_id: str | None = None,
        anonymous_id: str | None = None,
    ):
        """Invalidate assignment cache."""
        redis_key = self._get_assignment_key(experiment_key, user_id, anonymous_id)
        self.client.delete(redis_key)

    def invalidate_all(self):
        """Invalidate all experiment caches."""
        pattern = f"{self.key_prefix}*"
        keys = self.client.keys(pattern)
        if keys:
            self.client.delete(*keys)

    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None


class MemoryBackend(ExperimentBackend):
    """
    In-memory experiment backend.

    Useful for testing and development.
    """

    def __init__(self):
        self._experiments: dict[str, "Experiment"] = {}
        self._assignments: dict[str, "ExperimentAssignment"] = {}

    def add_experiment(self, experiment: "Experiment"):
        """Add an experiment to memory."""
        self._experiments[experiment.key] = experiment

    def get_experiment(self, key: str) -> "Experiment | None":
        """Get experiment from memory."""
        return self._experiments.get(key)

    def get_assignment(
        self,
        experiment_key: str,
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
    ) -> "ExperimentAssignment | None":
        """Get assignment from memory."""
        if user:
            key = f"{experiment_key}:user:{user.pk}"
        elif anonymous_id:
            key = f"{experiment_key}:anon:{anonymous_id}"
        else:
            return None

        return self._assignments.get(key)

    def create_assignment(
        self,
        experiment: "Experiment",
        variant: "Variant | None",
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
        is_holdout: bool = False,
        context: dict[str, Any] | None = None,
    ) -> "ExperimentAssignment":
        """Create assignment in memory."""
        from django_matt.experiments.models import ExperimentAssignment

        assignment = ExperimentAssignment(
            experiment=experiment,
            variant=variant,
            user=user,
            anonymous_id=anonymous_id or "",
            is_holdout=is_holdout,
            context=context or {},
        )

        if user:
            key = f"{experiment.key}:user:{user.pk}"
        elif anonymous_id:
            key = f"{experiment.key}:anon:{anonymous_id}"
        else:
            key = f"{experiment.key}:unknown"

        self._assignments[key] = assignment
        return assignment

    def get_all_experiments(
        self,
        status: str | None = None,
    ) -> list["Experiment"]:
        """Get all experiments from memory."""
        if status:
            return [e for e in self._experiments.values() if e.status == status]
        return list(self._experiments.values())

    def clear(self):
        """Clear all data."""
        self._experiments.clear()
        self._assignments.clear()


# Backend registry
_backends: dict[str, type[ExperimentBackend]] = {
    "database": DatabaseBackend,
    "redis": RedisBackend,
    "memory": MemoryBackend,
}

_default_backend: ExperimentBackend | None = None


def register_backend(name: str, backend_class: type[ExperimentBackend]):
    """Register a custom backend."""
    _backends[name] = backend_class


def get_backend(name: str | None = None, **kwargs) -> ExperimentBackend:
    """
    Get an experiment backend.

    Args:
        name: Backend name (database, redis, memory)
        **kwargs: Backend-specific configuration

    Returns:
        ExperimentBackend instance
    """
    global _default_backend

    if name is None:
        # Return cached default backend
        if _default_backend is not None:
            return _default_backend

        # Get from settings
        name = getattr(settings, "EXPERIMENT_BACKEND", "database")

    if name not in _backends:
        raise ValueError(f"Unknown backend: {name}. Available: {list(_backends.keys())}")

    backend_class = _backends[name]

    # Get backend-specific settings
    backend_settings = getattr(settings, "EXPERIMENT_BACKEND_SETTINGS", {})
    config = {**backend_settings.get(name, {}), **kwargs}

    backend = backend_class(**config)

    # Cache as default if using default name
    if name == getattr(settings, "EXPERIMENT_BACKEND", "database"):
        _default_backend = backend

    return backend


def reset_default_backend():
    """Reset the cached default backend."""
    global _default_backend
    if _default_backend:
        _default_backend.close()
        _default_backend = None


__all__ = [
    "ExperimentBackend",
    "DatabaseBackend",
    "RedisBackend",
    "MemoryBackend",
    "get_backend",
    "register_backend",
    "reset_default_backend",
]
