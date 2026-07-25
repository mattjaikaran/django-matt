"""Access pattern learner — track which relations are accessed after initial queries.

Observes query patterns across requests and builds a model of which related
objects are typically accessed together. Uses these patterns to suggest or
automatically apply select_related/prefetch_related optimizations.

Usage::

    learner = AccessPatternLearner()

    # Record observations
    learner.observe("myapp.User", ["organization", "profile"])
    learner.observe("myapp.User", ["organization"])
    learner.observe("myapp.User", ["organization", "profile", "teams"])

    # Get suggestions
    suggestions = learner.suggest_prefetches("myapp.User")
    # [("organization", 1.0), ("profile", 0.67), ("teams", 0.33)]

    # Auto-optimize a queryset
    qs = learner.auto_optimize(User.objects.all())
    # Adds select_related("organization") and prefetch_related("profile")
"""

from __future__ import annotations

import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class PatternStats:
    """Statistics for a model's access patterns."""

    model_key: str
    total_observations: int
    relation_counts: dict[str, int]
    suggestions: list[tuple[str, float]]


class AccessPatternLearner:
    """Track and learn from relation access patterns.

    Thread-safe. Maintains per-model counters of which relations are
    accessed, and uses frequency thresholds to suggest optimizations.

    Args:
        threshold: Minimum access frequency (0.0-1.0) to suggest a prefetch.
                   Default 0.3 means a relation must be accessed in ≥30% of
                   observations to be suggested.
        max_prefetches: Maximum number of relations to auto-apply.
    """

    def __init__(
        self,
        threshold: float = 0.3,
        max_prefetches: int = 5,
    ) -> None:
        self.threshold = threshold
        self.max_prefetches = max_prefetches
        self._observations: dict[str, int] = defaultdict(int)
        self._relations: dict[str, Counter[str]] = defaultdict(Counter)
        self._lock = threading.RLock()

    def observe(self, model_key: str, accessed_relations: list[str]) -> None:
        """Record which relations were accessed for a model.

        Args:
            model_key: Dotted model identifier (e.g. "myapp.User").
            accessed_relations: List of relation names accessed in this request.
        """
        with self._lock:
            self._observations[model_key] += 1
            for rel in accessed_relations:
                self._relations[model_key][rel] += 1

    def suggest_prefetches(
        self, model_key: str
    ) -> list[tuple[str, float]]:
        """Suggest relations to prefetch based on observed access patterns.

        Returns list of (relation_name, frequency) tuples sorted by
        frequency descending, filtered by threshold.
        """
        with self._lock:
            total = self._observations.get(model_key, 0)
            if total == 0:
                return []

            counts = self._relations.get(model_key, Counter())
            suggestions = []
            for rel, count in counts.most_common():
                freq = count / total
                if freq >= self.threshold:
                    suggestions.append((rel, round(freq, 3)))

            return suggestions[: self.max_prefetches]

    def auto_optimize(self, queryset: Any, model_key: str | None = None) -> Any:
        """Apply learned prefetch patterns to a queryset.

        Automatically determines whether to use select_related (FK/OneToOne)
        or prefetch_related (M2M/reverse FK) based on the model's meta.
        """
        if model_key is None:
            model = queryset.model
            model_key = f"{model._meta.app_label}.{model._meta.model_name}"

        suggestions = self.suggest_prefetches(model_key)
        if not suggestions:
            return queryset

        model = queryset.model
        select_rels = []
        prefetch_rels = []

        for rel_name, _ in suggestions:
            try:
                field_obj = model._meta.get_field(rel_name)
                if field_obj.many_to_many or field_obj.one_to_many:
                    prefetch_rels.append(rel_name)
                else:
                    select_rels.append(rel_name)
            except Exception:
                # Unknown field — try as prefetch
                prefetch_rels.append(rel_name)

        if select_rels:
            queryset = queryset.select_related(*select_rels)
        if prefetch_rels:
            queryset = queryset.prefetch_related(*prefetch_rels)

        return queryset

    def get_stats(self, model_key: str) -> PatternStats:
        """Return detailed statistics for a model's patterns."""
        with self._lock:
            total = self._observations.get(model_key, 0)
            counts = dict(self._relations.get(model_key, Counter()))
            suggestions = self.suggest_prefetches(model_key)

        return PatternStats(
            model_key=model_key,
            total_observations=total,
            relation_counts=counts,
            suggestions=suggestions,
        )

    def get_all_stats(self) -> dict[str, PatternStats]:
        """Return stats for all observed models."""
        with self._lock:
            keys = list(self._observations.keys())
        return {k: self.get_stats(k) for k in keys}

    def reset(self) -> None:
        """Clear all learned patterns."""
        with self._lock:
            self._observations.clear()
            self._relations.clear()
