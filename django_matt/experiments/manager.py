# file-length-max: 900
"""
Experiment manager for assignment logic and bandit algorithms.

Provides ExperimentManager for user assignment, multi-armed bandit algorithms,
and experiment lifecycle management.
"""

import hashlib
import logging
import math
import random
import secrets
from typing import TYPE_CHECKING, Any

from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from django_matt.experiments.models import (
        Experiment,
        ExperimentAssignment,
        Variant,
    )

logger = logging.getLogger("django_matt.experiments")


class ExperimentManager:
    """
    Manager for experiment assignment and bandit algorithms.

    Handles:
    - User assignment to variants
    - Multi-armed bandit algorithms (epsilon-greedy, UCB, Thompson sampling)
    - Exclusion group management
    - Holdout group assignment
    - Integration with feature flags
    """

    def __init__(self, backend: Any = None):
        """
        Initialize the manager.

        Args:
            backend: Optional experiment backend (defaults to database)
        """
        self._backend = backend

    @property
    def backend(self):
        """Get the experiment backend."""
        if self._backend is None:
            from django_matt.experiments.backends import get_backend

            self._backend = get_backend()
        return self._backend

    def get_assignment(
        self,
        experiment_key: str,
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
        create: bool = True,
        context: dict[str, Any] | None = None,
    ) -> "ExperimentAssignment | None":
        """
        Get or create an assignment for a user in an experiment.

        Args:
            experiment_key: Experiment key
            user: Authenticated user (optional)
            anonymous_id: Anonymous identifier (optional)
            create: Whether to create assignment if not exists
            context: Additional context for assignment

        Returns:
            ExperimentAssignment or None if not eligible
        """
        from django_matt.experiments.models import (
            Experiment,
            ExperimentAssignment,
        )

        # Get experiment
        try:
            experiment = Experiment.objects.get(key=experiment_key)
        except Experiment.DoesNotExist:
            logger.warning(f"Experiment not found: {experiment_key}")
            return None

        # Check if experiment is running
        if not experiment.is_running:
            logger.debug(f"Experiment not running: {experiment_key}")
            return None

        # Check for existing assignment
        if user:
            try:
                return ExperimentAssignment.objects.get(
                    experiment=experiment,
                    user=user,
                )
            except ExperimentAssignment.DoesNotExist:
                pass
        elif anonymous_id:
            try:
                return ExperimentAssignment.objects.get(
                    experiment=experiment,
                    anonymous_id=anonymous_id,
                )
            except ExperimentAssignment.DoesNotExist:
                pass
        else:
            # No identifier provided
            return None

        if not create:
            return None

        # Check eligibility
        if not self._is_eligible(experiment, user, context):
            logger.debug(f"User not eligible for experiment: {experiment_key}")
            return None

        # Check exclusion groups
        if not self._check_exclusion_group(experiment, user, anonymous_id):
            logger.debug(f"User in conflicting exclusion group: {experiment_key}")
            return None

        # Create assignment
        assignment = self._create_assignment(
            experiment=experiment,
            user=user,
            anonymous_id=anonymous_id,
            context=context or {},
        )

        # Emit analytics event when a user is assigned to an experiment variant
        from django_matt.analytics import track_event

        track_event(
            name="experiment_assigned",
            properties={
                "experiment_key": experiment_key,
                "variant_key": assignment.variant.key if assignment.variant else None,
                "is_holdout": assignment.is_holdout,
            },
            user=user,
            anonymous_id=anonymous_id or "",
            category="experiment",
        )

        return assignment

    def get_variant(
        self,
        experiment_key: str,
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
        create: bool = True,
        context: dict[str, Any] | None = None,
    ) -> "Variant | None":
        """
        Get the assigned variant for a user in an experiment.

        Args:
            experiment_key: Experiment key
            user: Authenticated user (optional)
            anonymous_id: Anonymous identifier (optional)
            create: Whether to create assignment if not exists
            context: Additional context

        Returns:
            Variant or None
        """
        assignment = self.get_assignment(
            experiment_key=experiment_key,
            user=user,
            anonymous_id=anonymous_id,
            create=create,
            context=context,
        )

        if assignment and not assignment.is_holdout:
            return assignment.variant

        return None

    def get_variant_key(
        self,
        experiment_key: str,
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
        create: bool = True,
        context: dict[str, Any] | None = None,
        default: str | None = None,
    ) -> str | None:
        """
        Get the variant key for a user in an experiment.

        Args:
            experiment_key: Experiment key
            user: Authenticated user
            anonymous_id: Anonymous identifier
            create: Whether to create assignment
            context: Additional context
            default: Default value if not assigned

        Returns:
            Variant key or default
        """
        variant = self.get_variant(
            experiment_key=experiment_key,
            user=user,
            anonymous_id=anonymous_id,
            create=create,
            context=context,
        )

        if variant:
            return variant.key
        return default

    def track_conversion(
        self,
        experiment_key: str,
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
        metric_name: str = "conversion",
        value: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Track a conversion event for an experiment.

        Args:
            experiment_key: Experiment key
            user: Authenticated user
            anonymous_id: Anonymous identifier
            metric_name: Name of the metric
            value: Metric value (1.0 for binary conversion)
            metadata: Additional event data

        Returns:
            True if event was tracked
        """
        from decimal import Decimal

        from django_matt.experiments.models import (
            ExperimentResult,
            MetricType,
        )

        # Get assignment (don't create if doesn't exist)
        assignment = self.get_assignment(
            experiment_key=experiment_key,
            user=user,
            anonymous_id=anonymous_id,
            create=False,
        )

        if not assignment:
            logger.debug(f"No assignment found for conversion tracking: {experiment_key}")
            return False

        # Create result
        ExperimentResult.objects.create(
            assignment=assignment,
            variant=assignment.variant,
            metric_name=metric_name,
            metric_type=MetricType.CONVERSION.value,
            value=Decimal(str(value)),
            metadata=metadata or {},
        )

        return True

    def track_revenue(
        self,
        experiment_key: str,
        amount: float,
        user: "AbstractUser | None" = None,
        anonymous_id: str | None = None,
        metric_name: str = "revenue",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Track a revenue event for an experiment.

        Args:
            experiment_key: Experiment key
            amount: Revenue amount
            user: Authenticated user
            anonymous_id: Anonymous identifier
            metric_name: Name of the metric
            metadata: Additional event data

        Returns:
            True if event was tracked
        """
        from decimal import Decimal

        from django_matt.experiments.models import (
            ExperimentResult,
            MetricType,
        )

        assignment = self.get_assignment(
            experiment_key=experiment_key,
            user=user,
            anonymous_id=anonymous_id,
            create=False,
        )

        if not assignment:
            return False

        ExperimentResult.objects.create(
            assignment=assignment,
            variant=assignment.variant,
            metric_name=metric_name,
            metric_type=MetricType.REVENUE.value,
            value=Decimal(str(amount)),
            metadata=metadata or {},
        )

        return True

    def _is_eligible(
        self,
        experiment: "Experiment",
        user: "AbstractUser | None",
        context: dict[str, Any] | None,
    ) -> bool:
        """Check if user is eligible for the experiment."""
        if not experiment.targeting_rules:
            return True

        context = context or {}

        # Add user attributes to context
        if user:
            context["user_id"] = str(user.pk)
            if hasattr(user, "email"):
                context["email"] = user.email
            if hasattr(user, "is_staff"):
                context["is_staff"] = user.is_staff
            if hasattr(user, "date_joined"):
                context["days_since_signup"] = (timezone.now() - user.date_joined).days

        # Evaluate targeting rules
        for rule in experiment.targeting_rules:
            if not self._evaluate_rule(rule, context):
                return False

        return True

    def _evaluate_rule(self, rule: dict, context: dict[str, Any]) -> bool:
        """Evaluate a single targeting rule."""
        attribute = rule.get("attribute")
        operator = rule.get("operator", "eq")
        value = rule.get("value")

        if not attribute or attribute not in context:
            return True  # Skip if attribute not present

        attr_value = context[attribute]

        if operator == "eq":
            return attr_value == value
        if operator == "neq":
            return attr_value != value
        if operator == "gt":
            return attr_value > value
        if operator == "gte":
            return attr_value >= value
        if operator == "lt":
            return attr_value < value
        if operator == "lte":
            return attr_value <= value
        if operator == "in":
            return attr_value in value
        if operator == "not_in":
            return attr_value not in value
        if operator == "contains":
            return value in str(attr_value)

        return True

    def _check_exclusion_group(
        self,
        experiment: "Experiment",
        user: "AbstractUser | None",
        anonymous_id: str | None,
    ) -> bool:
        """
        Check if user can join this experiment based on exclusion groups.

        A user can only be in one experiment per exclusion group.
        """
        if not experiment.exclusion_group:
            return True

        from django_matt.experiments.models import (
            Experiment,
            ExperimentAssignment,
            ExperimentStatus,
        )

        # Get other experiments in the same exclusion group
        other_experiments = Experiment.objects.filter(
            exclusion_group=experiment.exclusion_group,
            status=ExperimentStatus.RUNNING.value,
        ).exclude(id=experiment.id)

        # Check if user is already in any of them
        for other in other_experiments:
            exists = False
            if user:
                exists = ExperimentAssignment.objects.filter(
                    experiment=other,
                    user=user,
                ).exists()
            elif anonymous_id:
                exists = ExperimentAssignment.objects.filter(
                    experiment=other,
                    anonymous_id=anonymous_id,
                ).exists()

            if exists:
                return False

        return True

    def _create_assignment(
        self,
        experiment: "Experiment",
        user: "AbstractUser | None",
        anonymous_id: str | None,
        context: dict[str, Any],
    ) -> "ExperimentAssignment":
        """Create a new assignment for a user."""
        from django_matt.experiments.models import (
            ExperimentAssignment,
        )

        # Check for holdout
        if self._is_in_holdout(experiment, user, anonymous_id):
            assignment = ExperimentAssignment.objects.create(
                experiment=experiment,
                user=user,
                anonymous_id=anonymous_id or "",
                variant=None,
                is_holdout=True,
                context=context,
            )
            return assignment

        # Select variant based on strategy
        variant = self._select_variant(experiment, user, anonymous_id)

        assignment = ExperimentAssignment.objects.create(
            experiment=experiment,
            user=user,
            anonymous_id=anonymous_id or "",
            variant=variant,
            is_holdout=False,
            context=context,
        )

        return assignment

    def _is_in_holdout(
        self,
        experiment: "Experiment",
        user: "AbstractUser | None",
        anonymous_id: str | None,
    ) -> bool:
        """Determine if user should be in holdout group."""
        if experiment.holdout_percentage <= 0:
            return False

        # Get identifier for consistent bucketing
        if user:
            identifier = f"{experiment.key}:holdout:{user.pk}"
        elif anonymous_id:
            identifier = f"{experiment.key}:holdout:{anonymous_id}"
        else:
            return False

        # Hash and bucket
        hash_value = int(hashlib.md5(identifier.encode()).hexdigest(), 16)
        bucket = (hash_value % 10000) / 10000  # 0.0 to 0.9999

        return bucket < experiment.holdout_percentage

    def _select_variant(
        self,
        experiment: "Experiment",
        user: "AbstractUser | None",
        anonymous_id: str | None,
    ) -> "Variant":
        """Select a variant for assignment based on strategy."""
        from django_matt.experiments.models import AssignmentStrategy

        variants = list(experiment.variants.all())
        if not variants:
            raise ValueError(f"Experiment has no variants: {experiment.key}")

        strategy = experiment.strategy

        if strategy == AssignmentStrategy.RANDOM.value:
            return self._random_assignment(variants, experiment, user, anonymous_id)
        if strategy == AssignmentStrategy.EPSILON_GREEDY.value:
            return self._epsilon_greedy_assignment(variants, experiment)
        if strategy == AssignmentStrategy.UCB.value:
            return self._ucb_assignment(variants, experiment)
        if strategy == AssignmentStrategy.THOMPSON.value:
            return self._thompson_assignment(variants, experiment)
        return self._random_assignment(variants, experiment, user, anonymous_id)

    def _random_assignment(
        self,
        variants: list["Variant"],
        experiment: "Experiment",
        user: "AbstractUser | None",
        anonymous_id: str | None,
    ) -> "Variant":
        """Random assignment based on weights."""
        # Get identifier for consistent assignment
        if user:
            identifier = f"{experiment.key}:{user.pk}"
        elif anonymous_id:
            identifier = f"{experiment.key}:{anonymous_id}"
        else:
            identifier = f"{experiment.key}:{secrets.token_hex(8)}"

        # Hash for consistent bucketing
        hash_value = int(hashlib.md5(identifier.encode()).hexdigest(), 16)

        # Calculate total weight
        total_weight = sum(v.weight for v in variants)
        if total_weight == 0:
            return variants[0]

        # Select based on weight
        bucket = hash_value % total_weight
        cumulative = 0

        for variant in variants:
            cumulative += variant.weight
            if bucket < cumulative:
                return variant

        return variants[-1]

    def _epsilon_greedy_assignment(
        self,
        variants: list["Variant"],
        experiment: "Experiment",
    ) -> "Variant":
        """Epsilon-greedy assignment."""
        # With probability epsilon, explore randomly
        if random.random() < experiment.epsilon:
            return random.choice(variants)

        # Otherwise, exploit best performing variant
        best_variant = None
        best_rate = -1.0

        for variant in variants:
            rate = variant.conversion_rate
            if rate > best_rate:
                best_rate = rate
                best_variant = variant

        return best_variant or variants[0]

    def _ucb_assignment(
        self,
        variants: list["Variant"],
        experiment: "Experiment",
    ) -> "Variant":
        """Upper Confidence Bound assignment."""
        total_assignments = sum(v.assignment_count for v in variants)
        if total_assignments == 0:
            return random.choice(variants)

        best_variant = None
        best_ucb = -1.0

        for variant in variants:
            n = variant.assignment_count
            if n == 0:
                return variant  # Explore unvisited variants first

            # UCB formula: mean + exploration_weight * sqrt(ln(total) / n)
            mean = variant.conversion_rate
            exploration = experiment.exploration_weight * math.sqrt(math.log(total_assignments) / n)
            ucb = mean + exploration

            if ucb > best_ucb:
                best_ucb = ucb
                best_variant = variant

        return best_variant or variants[0]

    def _thompson_assignment(
        self,
        variants: list["Variant"],
        experiment: "Experiment",
    ) -> "Variant":
        """Thompson Sampling assignment using Beta distribution."""
        best_variant = None
        best_sample = -1.0

        for variant in variants:
            # Beta distribution parameters
            # alpha = successes + 1, beta = failures + 1
            successes = variant.conversion_count
            failures = variant.assignment_count - successes

            # Sample from Beta distribution
            alpha = successes + 1
            beta = failures + 1
            sample = self._sample_beta(alpha, beta)

            if sample > best_sample:
                best_sample = sample
                best_variant = variant

        return best_variant or variants[0]

    def _sample_beta(self, alpha: float, beta: float) -> float:
        """
        Sample from Beta distribution using gamma random variates.

        Beta(a, b) = Gamma(a, 1) / (Gamma(a, 1) + Gamma(b, 1))
        """
        x = random.gammavariate(alpha, 1)
        y = random.gammavariate(beta, 1)
        return x / (x + y) if (x + y) > 0 else 0.5

    def get_bandit_weights(
        self,
        experiment: "Experiment",
    ) -> dict[str, float]:
        """
        Get current weights for bandit algorithms.

        Returns weights normalized to sum to 1.0.
        """
        from django_matt.experiments.models import AssignmentStrategy

        variants = list(experiment.variants.all())
        if not variants:
            return {}

        strategy = experiment.strategy

        if strategy == AssignmentStrategy.RANDOM.value:
            total = sum(v.weight for v in variants)
            if total == 0:
                return {str(v.id): 1.0 / len(variants) for v in variants}
            return {str(v.id): v.weight / total for v in variants}

        if strategy == AssignmentStrategy.EPSILON_GREEDY.value:
            # During exploration phase, weights are equal
            # During exploitation, best variant gets (1 - epsilon) + epsilon/n
            n = len(variants)
            explore_weight = experiment.epsilon / n

            best_variant = max(variants, key=lambda v: v.conversion_rate)
            weights = {}

            for v in variants:
                if v.id == best_variant.id:
                    weights[str(v.id)] = (1 - experiment.epsilon) + explore_weight
                else:
                    weights[str(v.id)] = explore_weight

            return weights

        if strategy == AssignmentStrategy.UCB.value:
            total_assignments = sum(v.assignment_count for v in variants)
            if total_assignments == 0:
                return {str(v.id): 1.0 / len(variants) for v in variants}

            ucb_values = {}
            for v in variants:
                n = v.assignment_count
                if n == 0:
                    ucb_values[str(v.id)] = float("inf")
                else:
                    mean = v.conversion_rate
                    exploration = experiment.exploration_weight * math.sqrt(
                        math.log(total_assignments) / n
                    )
                    ucb_values[str(v.id)] = mean + exploration

            # Normalize (handle infinity)
            max_ucb = max(ucb_values.values())
            if max_ucb == float("inf"):
                return {
                    str(v.id): (1.0 if ucb_values[str(v.id)] == float("inf") else 0.0)
                    / sum(1 for u in ucb_values.values() if u == float("inf"))
                    for v in variants
                }

            total = sum(ucb_values.values())
            if total == 0:
                return {str(v.id): 1.0 / len(variants) for v in variants}

            return {k: v / total for k, v in ucb_values.items()}

        if strategy == AssignmentStrategy.THOMPSON.value:
            # For Thompson, weights are based on expected probability of being best
            # Approximate with samples
            n_samples = 1000
            wins = {str(v.id): 0 for v in variants}

            for _ in range(n_samples):
                best_sample = -1.0
                best_id = None

                for v in variants:
                    alpha = v.conversion_count + 1
                    beta = v.assignment_count - v.conversion_count + 1
                    sample = self._sample_beta(alpha, beta)

                    if sample > best_sample:
                        best_sample = sample
                        best_id = str(v.id)

                if best_id:
                    wins[best_id] += 1

            return {k: v / n_samples for k, v in wins.items()}

        return {str(v.id): 1.0 / len(variants) for v in variants}


# Singleton manager instance
_manager: ExperimentManager | None = None


def get_manager() -> ExperimentManager:
    """Get the experiment manager singleton."""
    global _manager
    if _manager is None:
        _manager = ExperimentManager()
    return _manager


def get_assignment(
    experiment_key: str,
    user: "AbstractUser | None" = None,
    anonymous_id: str | None = None,
    create: bool = True,
    context: dict[str, Any] | None = None,
) -> "ExperimentAssignment | None":
    """Convenience function to get experiment assignment."""
    return get_manager().get_assignment(
        experiment_key=experiment_key,
        user=user,
        anonymous_id=anonymous_id,
        create=create,
        context=context,
    )


def get_variant(
    experiment_key: str,
    user: "AbstractUser | None" = None,
    anonymous_id: str | None = None,
    create: bool = True,
    context: dict[str, Any] | None = None,
) -> "Variant | None":
    """Convenience function to get experiment variant."""
    return get_manager().get_variant(
        experiment_key=experiment_key,
        user=user,
        anonymous_id=anonymous_id,
        create=create,
        context=context,
    )


def get_variant_key(
    experiment_key: str,
    user: "AbstractUser | None" = None,
    anonymous_id: str | None = None,
    create: bool = True,
    context: dict[str, Any] | None = None,
    default: str | None = None,
) -> str | None:
    """Convenience function to get variant key."""
    return get_manager().get_variant_key(
        experiment_key=experiment_key,
        user=user,
        anonymous_id=anonymous_id,
        create=create,
        context=context,
        default=default,
    )


def track_conversion(
    experiment_key: str,
    user: "AbstractUser | None" = None,
    anonymous_id: str | None = None,
    metric_name: str = "conversion",
    value: float = 1.0,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Convenience function to track conversion."""
    return get_manager().track_conversion(
        experiment_key=experiment_key,
        user=user,
        anonymous_id=anonymous_id,
        metric_name=metric_name,
        value=value,
        metadata=metadata,
    )


def track_revenue(
    experiment_key: str,
    amount: float,
    user: "AbstractUser | None" = None,
    anonymous_id: str | None = None,
    metric_name: str = "revenue",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Convenience function to track revenue."""
    return get_manager().track_revenue(
        experiment_key=experiment_key,
        amount=amount,
        user=user,
        anonymous_id=anonymous_id,
        metric_name=metric_name,
        metadata=metadata,
    )


__all__ = [
    "ExperimentManager",
    "get_manager",
    "get_assignment",
    "get_variant",
    "get_variant_key",
    "track_conversion",
    "track_revenue",
]
