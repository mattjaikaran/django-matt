"""
Integration between experiments and feature flags modules.

Provides utilities for using experiments as feature flags and vice versa.

Usage:
    from django_matt.experiments.flags_integration import (
        experiment_as_flag,
        flag_as_experiment,
        sync_experiment_to_flag,
    )

    # Use experiment variant as a feature flag
    if experiment_as_flag("checkout_experiment", user=request.user):
        # User is in treatment variant
        ...

    # Sync experiment winner to feature flag
    sync_experiment_to_flag("checkout_experiment", "new_checkout_flag")
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from django_matt.experiments.models import Experiment
    from django_matt.flags.models import FeatureFlag

logger = logging.getLogger("django_matt.experiments")


def experiment_as_flag(
    experiment_key: str,
    user: "AbstractUser | None" = None,
    anonymous_id: str | None = None,
    treatment_variants: list[str] | None = None,
    default: bool = False,
) -> bool:
    """
    Use an experiment assignment as a feature flag.

    Returns True if user is in a treatment variant, False if in control/holdout.

    Args:
        experiment_key: Experiment key
        user: Authenticated user
        anonymous_id: Anonymous identifier
        treatment_variants: List of variant keys considered "treatment" (default: all non-control)
        default: Default value if not in experiment

    Returns:
        True if user is in treatment, False otherwise

    Example:
        if experiment_as_flag("new_checkout"):
            return new_checkout()
        return old_checkout()
    """
    from django_matt.experiments.manager import get_manager

    manager = get_manager()
    assignment = manager.get_assignment(
        experiment_key=experiment_key,
        user=user,
        anonymous_id=anonymous_id,
        create=True,
    )

    if not assignment:
        return default

    if assignment.is_holdout:
        return False

    if not assignment.variant:
        return default

    # If treatment_variants specified, check if in those
    if treatment_variants:
        return assignment.variant.key in treatment_variants

    # Otherwise, return True for any non-control variant
    return not assignment.variant.is_control


def flag_as_experiment_targeting(
    experiment_key: str,
    flag_key: str,
    user: "AbstractUser | None" = None,
    organization: Any | None = None,
    attributes: dict[str, Any] | None = None,
) -> bool:
    """
    Use a feature flag to determine experiment eligibility.

    Only users with the flag enabled are eligible for the experiment.

    Args:
        experiment_key: Experiment key
        flag_key: Feature flag key for targeting
        user: Authenticated user
        organization: Organization context
        attributes: Additional attributes

    Returns:
        True if user should be in experiment
    """
    from django_matt.flags import feature_enabled

    return feature_enabled(
        key=flag_key,
        user=user,
        organization=organization,
        attributes=attributes,
        default=False,
    )


def sync_experiment_to_flag(
    experiment_key: str,
    flag_key: str | None = None,
    enable_flag: bool = True,
) -> "FeatureFlag | None":
    """
    Sync experiment winner to a feature flag.

    When an experiment completes with a winner, create or update a feature flag
    to permanently enable the winning variant behavior.

    Args:
        experiment_key: Experiment key
        flag_key: Target feature flag key (defaults to experiment's feature_flag_key)
        enable_flag: Whether to enable the flag

    Returns:
        FeatureFlag if synced, None otherwise

    Example:
        # After experiment completes
        flag = sync_experiment_to_flag("checkout_experiment")
        if flag:
            print(f"Created flag: {flag.key}")
    """
    from django_matt.experiments.models import Experiment, ExperimentStatus
    from django_matt.flags.models import FeatureFlag, FlagStatus, FlagType

    try:
        experiment = Experiment.objects.get(key=experiment_key)
    except Experiment.DoesNotExist:
        logger.warning(f"Experiment not found: {experiment_key}")
        return None

    if experiment.status != ExperimentStatus.COMPLETED.value:
        logger.warning(f"Experiment not completed: {experiment_key}")
        return None

    if not experiment.has_winner:
        logger.warning(f"Experiment has no winner: {experiment_key}")
        return None

    # Determine flag key
    target_flag_key = flag_key or experiment.feature_flag_key
    if not target_flag_key:
        target_flag_key = f"experiment_{experiment_key}_winner"

    # Get winning variant
    try:
        from django_matt.experiments.models import Variant
        winner = Variant.objects.get(id=experiment.winner_variant_id)
    except Variant.DoesNotExist:
        logger.warning(f"Winner variant not found: {experiment.winner_variant_id}")
        return None

    # Create or update flag
    flag, created = FeatureFlag.objects.update_or_create(
        key=target_flag_key,
        defaults={
            "name": f"{experiment.name} - Winner",
            "description": f"Auto-created from experiment '{experiment_key}'. "
                          f"Winner: {winner.key} (confidence: {experiment.winner_confidence:.2%})",
            "flag_type": FlagType.BOOLEAN.value,
            "status": FlagStatus.ACTIVE.value if enable_flag else FlagStatus.INACTIVE.value,
            "enabled_by_default": enable_flag and not winner.is_control,
            "metadata": {
                "source": "experiment",
                "experiment_key": experiment_key,
                "winner_variant_key": winner.key,
                "winner_confidence": experiment.winner_confidence,
                "synced_at": str(experiment.winner_detected_at),
            },
        },
    )

    action = "created" if created else "updated"
    logger.info(f"Feature flag {action}: {target_flag_key} from experiment {experiment_key}")

    return flag


def create_experiment_from_flag(
    flag_key: str,
    experiment_key: str | None = None,
    control_is_disabled: bool = True,
    sample_size: int = 1000,
    confidence: float = 0.95,
) -> "Experiment | None":
    """
    Create an experiment from an existing feature flag.

    Useful for A/B testing a flag before full rollout.

    Args:
        flag_key: Feature flag key
        experiment_key: Experiment key (defaults to flag_key)
        control_is_disabled: Whether control means flag disabled
        sample_size: Minimum sample size
        confidence: Target confidence level

    Returns:
        Experiment if created, None otherwise

    Example:
        # Test a flag before full rollout
        exp = create_experiment_from_flag("new_feature")
        exp.start()
    """
    from django_matt.experiments.models import AssignmentStrategy, Experiment, Variant
    from django_matt.flags.models import FeatureFlag, FlagType

    try:
        flag = FeatureFlag.objects.get(key=flag_key)
    except FeatureFlag.DoesNotExist:
        logger.warning(f"Feature flag not found: {flag_key}")
        return None

    target_key = experiment_key or flag_key

    # Check if experiment already exists
    if Experiment.objects.filter(key=target_key).exists():
        logger.warning(f"Experiment already exists: {target_key}")
        return None

    # Create experiment
    experiment = Experiment.objects.create(
        key=target_key,
        name=f"A/B Test: {flag.name}",
        description=f"Testing feature flag '{flag_key}' before full rollout.",
        strategy=AssignmentStrategy.RANDOM.value,
        min_sample_size=sample_size,
        target_confidence=confidence,
        feature_flag_key=flag_key,
        metadata={
            "source": "feature_flag",
            "flag_key": flag_key,
        },
    )

    # Create variants
    if flag.flag_type == FlagType.VARIANT.value and flag.variants:
        # Use flag's variants
        variants_config = flag.variants.get("variants", [])
        for v_config in variants_config:
            Variant.objects.create(
                experiment=experiment,
                key=v_config.get("key", "variant"),
                name=v_config.get("name", v_config.get("key", "Variant")),
                is_control=v_config.get("key") == variants_config[0].get("key"),
                weight=v_config.get("weight", 1),
                payload=v_config.get("payload", {}),
            )
    else:
        # Create control/treatment for boolean flag
        Variant.objects.create(
            experiment=experiment,
            key="control",
            name="Control (Flag Disabled)" if control_is_disabled else "Control (Flag Enabled)",
            is_control=True,
            weight=1,
        )
        Variant.objects.create(
            experiment=experiment,
            key="treatment",
            name="Treatment (Flag Enabled)" if control_is_disabled else "Treatment (Flag Disabled)",
            is_control=False,
            weight=1,
        )

    logger.info(f"Created experiment from flag: {target_key}")
    return experiment


def get_experiment_flag_status(
    experiment_key: str,
    user: "AbstractUser | None" = None,
    anonymous_id: str | None = None,
) -> dict[str, Any]:
    """
    Get combined experiment and flag status for a user.

    Useful for debugging and admin views.

    Args:
        experiment_key: Experiment key
        user: Authenticated user
        anonymous_id: Anonymous identifier

    Returns:
        Dict with experiment and flag status
    """
    from django_matt.experiments.manager import get_manager
    from django_matt.experiments.models import Experiment

    result = {
        "experiment_key": experiment_key,
        "experiment_status": None,
        "assignment": None,
        "variant": None,
        "is_holdout": False,
        "flag_key": None,
        "flag_enabled": None,
    }

    try:
        experiment = Experiment.objects.get(key=experiment_key)
        result["experiment_status"] = experiment.status
        result["flag_key"] = experiment.feature_flag_key or None

        # Get assignment
        manager = get_manager()
        assignment = manager.get_assignment(
            experiment_key=experiment_key,
            user=user,
            anonymous_id=anonymous_id,
            create=False,
        )

        if assignment:
            result["assignment"] = str(assignment.id)
            result["variant"] = assignment.variant.key if assignment.variant else None
            result["is_holdout"] = assignment.is_holdout

        # Get flag status if linked
        if experiment.feature_flag_key:
            from django_matt.flags import feature_enabled
            result["flag_enabled"] = feature_enabled(
                experiment.feature_flag_key,
                user=user,
            )

    except Experiment.DoesNotExist:
        pass

    return result


__all__ = [
    "experiment_as_flag",
    "flag_as_experiment_targeting",
    "sync_experiment_to_flag",
    "create_experiment_from_flag",
    "get_experiment_flag_status",
]
