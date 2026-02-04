"""
Feature flag models.

Provides FeatureFlag and FlagOverride models for feature flag management.
"""

import hashlib
import secrets
import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class FlagType(str, Enum):
    """Type of feature flag."""

    BOOLEAN = "boolean"  # Simple on/off
    PERCENTAGE = "percentage"  # Gradual rollout
    VARIANT = "variant"  # A/B testing with variants

    @classmethod
    def choices(cls):
        return [(t.value, t.name.title()) for t in cls]


class FlagStatus(str, Enum):
    """Status of a feature flag."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"

    @classmethod
    def choices(cls):
        return [(s.value, s.name.title()) for s in cls]


class OverrideType(str, Enum):
    """Type of flag override."""

    USER = "user"
    ORGANIZATION = "organization"
    EMAIL = "email"
    ATTRIBUTE = "attribute"

    @classmethod
    def choices(cls):
        return [(t.value, t.name.title()) for t in cls]


class FeatureFlagManager(models.Manager):
    """Custom manager for FeatureFlag with common queries."""

    def active(self) -> models.QuerySet:
        """Get active feature flags."""
        return self.filter(status=FlagStatus.ACTIVE.value)

    def by_key(self, key: str) -> "FeatureFlag | None":
        """Get a flag by its key."""
        try:
            return self.get(key=key)
        except self.model.DoesNotExist:
            return None

    def enabled_for_user(self, user: "AbstractUser") -> models.QuerySet:
        """Get flags enabled for a specific user."""
        # This returns flags where:
        # 1. Status is active AND enabled_by_default is True
        # 2. OR there's a user override with enabled=True
        from django.db.models import Q

        return self.filter(
            Q(status=FlagStatus.ACTIVE.value, enabled_by_default=True)
            | Q(
                overrides__override_type=OverrideType.USER.value,
                overrides__target_id=str(user.pk),
                overrides__enabled=True,
            )
        ).distinct()


class FeatureFlag(models.Model):
    """
    Feature flag model.

    Supports boolean flags, percentage rollouts, and A/B test variants.

    Attributes:
        key: Unique identifier for the flag
        name: Human-readable name
        description: Optional description
        flag_type: Type of flag (boolean, percentage, variant)
        status: Current status (active, inactive, archived)
        enabled_by_default: Default state when no overrides apply
        rollout_percentage: Percentage of users to enable (for percentage flags)
        variants: JSON field with variant configurations
        targeting_rules: JSON field with targeting rules
        scheduled_enable_at: When to automatically enable
        scheduled_disable_at: When to automatically disable
        metadata: Additional metadata
        created_at: Creation timestamp
        updated_at: Last update timestamp
        created_by: User who created the flag
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique identifier for the flag (e.g., 'new_checkout')",
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for the flag",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Description of what this flag controls",
    )
    flag_type = models.CharField(
        max_length=20,
        choices=FlagType.choices(),
        default=FlagType.BOOLEAN.value,
        help_text="Type of feature flag",
    )
    status = models.CharField(
        max_length=20,
        choices=FlagStatus.choices(),
        default=FlagStatus.INACTIVE.value,
        db_index=True,
        help_text="Current status of the flag",
    )
    enabled_by_default = models.BooleanField(
        default=False,
        help_text="Default state when no overrides or targeting rules apply",
    )
    rollout_percentage = models.IntegerField(
        default=0,
        help_text="Percentage of users to enable (0-100) for percentage flags",
    )
    variants = models.JSONField(
        default=dict,
        blank=True,
        help_text="Variant configurations for A/B testing",
    )
    targeting_rules = models.JSONField(
        default=list,
        blank=True,
        help_text="Targeting rules for conditional enabling",
    )
    scheduled_enable_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Automatically enable at this time",
    )
    scheduled_disable_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Automatically disable at this time",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_flags",
    )

    objects = FeatureFlagManager()

    class Meta:
        app_label = "django_matt"
        ordering = ["key"]
        verbose_name = "Feature Flag"
        verbose_name_plural = "Feature Flags"
        indexes = [
            models.Index(fields=["key"]),
            models.Index(fields=["status"]),
            models.Index(fields=["flag_type"]),
            models.Index(fields=["scheduled_enable_at"]),
            models.Index(fields=["scheduled_disable_at"]),
        ]

    def __str__(self):
        return f"{self.key} ({self.flag_type})"

    @property
    def is_active(self) -> bool:
        """Check if the flag is active."""
        if self.status != FlagStatus.ACTIVE.value:
            return False

        now = timezone.now()

        # Check scheduled enable
        if self.scheduled_enable_at and now < self.scheduled_enable_at:
            return False

        # Check scheduled disable
        if self.scheduled_disable_at and now >= self.scheduled_disable_at:
            return False

        return True

    @property
    def type_enum(self) -> FlagType:
        """Get flag type as enum."""
        return FlagType(self.flag_type)

    @property
    def status_enum(self) -> FlagStatus:
        """Get status as enum."""
        return FlagStatus(self.status)

    def is_enabled_for_user(
        self,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> bool:
        """
        Check if the flag is enabled for a specific user/context.

        Args:
            user: The user to check
            organization: The organization/tenant to check
            attributes: Additional attributes for targeting

        Returns:
            Whether the flag is enabled
        """
        if not self.is_active:
            return False

        # Check user override
        if user:
            override = self.overrides.filter(
                override_type=OverrideType.USER.value,
                target_id=str(user.pk),
            ).first()
            if override:
                return override.enabled

            # Check email override
            if hasattr(user, "email") and user.email:
                override = self.overrides.filter(
                    override_type=OverrideType.EMAIL.value,
                    target_value=user.email,
                ).first()
                if override:
                    return override.enabled

        # Check organization override
        if organization:
            override = self.overrides.filter(
                override_type=OverrideType.ORGANIZATION.value,
                target_id=str(organization.pk if hasattr(organization, "pk") else organization),
            ).first()
            if override:
                return override.enabled

        # Check targeting rules
        if self.targeting_rules and attributes:
            if self._evaluate_targeting_rules(attributes):
                return True

        # Handle based on flag type
        if self.flag_type == FlagType.BOOLEAN.value:
            return self.enabled_by_default

        if self.flag_type == FlagType.PERCENTAGE.value:
            if user:
                return self._is_in_percentage_rollout(user)
            return False

        if self.flag_type == FlagType.VARIANT.value:
            # For variant flags, being enabled means having a variant assigned
            return self.enabled_by_default

        return self.enabled_by_default

    def get_variant(
        self,
        user: "AbstractUser | None" = None,
        organization: Any | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Get the variant assignment for a user.

        Args:
            user: The user to get variant for
            organization: The organization/tenant
            attributes: Additional attributes

        Returns:
            Variant key or None if not applicable
        """
        if not self.is_active or self.flag_type != FlagType.VARIANT.value:
            return None

        if not self.variants:
            return None

        # Check user override for specific variant
        if user:
            override = self.overrides.filter(
                override_type=OverrideType.USER.value,
                target_id=str(user.pk),
            ).first()
            if override and override.variant:
                return override.variant

        # Calculate consistent variant assignment
        variants = self.variants.get("variants", [])
        if not variants:
            return None

        # Use user ID or random for consistent assignment
        if user:
            hash_input = f"{self.key}:{user.pk}"
        else:
            hash_input = f"{self.key}:{secrets.token_hex(8)}"

        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        total_weight = sum(v.get("weight", 1) for v in variants)

        if total_weight == 0:
            return None

        bucket = hash_value % total_weight
        cumulative = 0

        for variant in variants:
            cumulative += variant.get("weight", 1)
            if bucket < cumulative:
                return variant.get("key")

        return variants[-1].get("key") if variants else None

    def _is_in_percentage_rollout(self, user: "AbstractUser") -> bool:
        """Check if user is in percentage rollout."""
        if self.rollout_percentage <= 0:
            return False
        if self.rollout_percentage >= 100:
            return True

        # Consistent bucketing based on user ID and flag key
        hash_input = f"{self.key}:{user.pk}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100

        return bucket < self.rollout_percentage

    def _evaluate_targeting_rules(self, attributes: dict[str, Any]) -> bool:
        """Evaluate targeting rules against attributes."""
        if not self.targeting_rules:
            return False

        for rule in self.targeting_rules:
            if self._evaluate_rule(rule, attributes):
                return True

        return False

    def _evaluate_rule(self, rule: dict, attributes: dict[str, Any]) -> bool:
        """Evaluate a single targeting rule."""
        attribute = rule.get("attribute")
        operator = rule.get("operator", "eq")
        value = rule.get("value")

        if not attribute or attribute not in attributes:
            return False

        attr_value = attributes[attribute]

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
        if operator == "starts_with":
            return str(attr_value).startswith(value)
        if operator == "ends_with":
            return str(attr_value).endswith(value)
        if operator == "regex":
            import re

            return bool(re.match(value, str(attr_value)))

        return False

    def add_override(
        self,
        override_type: OverrideType | str,
        target_id: str | None = None,
        target_value: str | None = None,
        enabled: bool = True,
        variant: str | None = None,
        expires_at: datetime | None = None,
    ) -> "FlagOverride":
        """Add an override for this flag."""
        if isinstance(override_type, OverrideType):
            override_type = override_type.value

        override, created = FlagOverride.objects.update_or_create(
            flag=self,
            override_type=override_type,
            target_id=target_id or "",
            target_value=target_value or "",
            defaults={
                "enabled": enabled,
                "variant": variant,
                "expires_at": expires_at,
            },
        )
        return override


class FlagOverride(models.Model):
    """
    Override for a feature flag.

    Allows targeting specific users, organizations, or attribute values.

    Attributes:
        flag: The feature flag this override applies to
        override_type: Type of override (user, organization, email, attribute)
        target_id: ID of the target (user ID, org ID, etc.)
        target_value: Value for attribute-based overrides
        enabled: Whether to enable or disable the flag
        variant: Specific variant to assign (for variant flags)
        expires_at: When this override expires
        created_at: Creation timestamp
        created_by: User who created the override
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    flag = models.ForeignKey(
        FeatureFlag,
        on_delete=models.CASCADE,
        related_name="overrides",
    )
    override_type = models.CharField(
        max_length=20,
        choices=OverrideType.choices(),
        db_index=True,
    )
    target_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="ID of the target (user ID, organization ID, etc.)",
    )
    target_value = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Value for attribute-based targeting (email address, etc.)",
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether to enable or disable the flag for this target",
    )
    variant = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Specific variant to assign (for variant flags)",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this override expires",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_flag_overrides",
    )

    class Meta:
        app_label = "django_matt"
        ordering = ["-created_at"]
        verbose_name = "Flag Override"
        verbose_name_plural = "Flag Overrides"
        unique_together = [["flag", "override_type", "target_id", "target_value"]]
        indexes = [
            models.Index(fields=["flag", "override_type"]),
            models.Index(fields=["override_type", "target_id"]),
            models.Index(fields=["override_type", "target_value"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        target = self.target_id or self.target_value
        return f"{self.flag.key} - {self.override_type}: {target}"

    @property
    def is_expired(self) -> bool:
        """Check if the override has expired."""
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at

    @property
    def is_active(self) -> bool:
        """Check if the override is active (not expired)."""
        return not self.is_expired


class FlagAuditLog(models.Model):
    """
    Audit log for feature flag changes.

    Records all changes to flags and overrides for compliance and debugging.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    flag = models.ForeignKey(
        FeatureFlag,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_logs",
    )
    flag_key = models.CharField(
        max_length=255,
        help_text="Flag key (preserved if flag is deleted)",
    )
    action = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Action performed (create, update, delete, enable, disable, etc.)",
    )
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Details of changes made",
    )
    old_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Previous values",
    )
    new_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="New values",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flag_audit_logs",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )
    user_agent = models.TextField(
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "django_matt"
        ordering = ["-created_at"]
        verbose_name = "Flag Audit Log"
        verbose_name_plural = "Flag Audit Logs"
        indexes = [
            models.Index(fields=["flag_key", "action"]),
            models.Index(fields=["user", "action"]),
        ]

    def __str__(self):
        return f"{self.flag_key} - {self.action} at {self.created_at}"

    @classmethod
    def log(
        cls,
        flag: FeatureFlag,
        action: str,
        changes: dict | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        user: "AbstractUser | None" = None,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> "FlagAuditLog":
        """Create an audit log entry."""
        return cls.objects.create(
            flag=flag,
            flag_key=flag.key,
            action=action,
            changes=changes or {},
            old_values=old_values or {},
            new_values=new_values or {},
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )


__all__ = [
    "FlagType",
    "FlagStatus",
    "OverrideType",
    "FeatureFlag",
    "FlagOverride",
    "FlagAuditLog",
]
