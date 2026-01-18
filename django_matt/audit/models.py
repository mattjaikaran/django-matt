"""
Audit log models.

Provides the AuditLog model for storing audit entries.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from .enums import AuditAction, AuditSeverity

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AuditLogManager(models.Manager):
    """Custom manager for AuditLog with common queries."""

    def for_object(self, obj: models.Model) -> models.QuerySet:
        """Get audit logs for a specific object."""
        content_type = ContentType.objects.get_for_model(obj)
        return self.filter(content_type=content_type, object_id=str(obj.pk))

    def for_model(self, model: type[models.Model]) -> models.QuerySet:
        """Get audit logs for a model class."""
        content_type = ContentType.objects.get_for_model(model)
        return self.filter(content_type=content_type)

    def for_user(self, user: "AbstractUser") -> models.QuerySet:
        """Get audit logs for a specific user."""
        return self.filter(user=user)

    def by_action(self, action: AuditAction) -> models.QuerySet:
        """Filter by action type."""
        return self.filter(action=action.value)

    def by_severity(self, severity: AuditSeverity, and_above: bool = False) -> models.QuerySet:
        """Filter by severity level."""
        if and_above:
            severities = [s.value for s in AuditSeverity if s.level >= severity.level]
            return self.filter(severity__in=severities)
        return self.filter(severity=severity.value)

    def recent(self, days: int = 7) -> models.QuerySet:
        """Get recent audit logs."""
        since = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=since)

    def security_events(self) -> models.QuerySet:
        """Get security-related audit logs."""
        security_actions = [a.value for a in AuditAction.security_actions()]
        return self.filter(action__in=security_actions)

    def failed_logins(self, since: datetime | None = None) -> models.QuerySet:
        """Get failed login attempts."""
        qs = self.filter(action=AuditAction.LOGIN_FAILED.value)
        if since:
            qs = qs.filter(created_at__gte=since)
        return qs

    def by_ip(self, ip_address: str) -> models.QuerySet:
        """Get audit logs from a specific IP."""
        return self.filter(ip_address=ip_address)


class AuditLog(models.Model):
    """
    Audit log entry.

    Stores information about actions performed in the system including:
    - Who performed the action (user)
    - What action was performed
    - What object was affected
    - When it happened
    - Request context (IP, User-Agent)
    - Before/after state for changes
    """

    # User who performed the action (nullable for anonymous/system actions)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    # Action type
    action = models.CharField(
        max_length=50,
        choices=[(a.value, a.value) for a in AuditAction],
        db_index=True,
    )

    # Severity level
    severity = models.CharField(
        max_length=20,
        choices=[(s.value, s.value) for s in AuditSeverity],
        default=AuditSeverity.INFO.value,
        db_index=True,
    )

    # Target object (generic foreign key)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    object_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")

    # Object representation (in case object is deleted)
    object_repr = models.CharField(max_length=500, blank=True, default="")

    # Description of the action
    description = models.TextField(blank=True, default="")

    # Changes (for update actions)
    changes = models.JSONField(default=dict, blank=True)

    # State before the action
    old_values = models.JSONField(default=dict, blank=True)

    # State after the action
    new_values = models.JSONField(default=dict, blank=True)

    # Request context
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.TextField(blank=True, default="")
    request_method = models.CharField(max_length=10, blank=True, default="")
    request_path = models.CharField(max_length=2000, blank=True, default="")

    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Custom manager
    objects = AuditLogManager()

    class Meta:
        app_label = "django_matt"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["user", "action"]),
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
        ]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self) -> str:
        user_str = str(self.user) if self.user else "Anonymous"
        return f"{user_str} - {self.action} - {self.object_repr or 'N/A'}"

    @property
    def action_enum(self) -> AuditAction:
        """Get action as enum."""
        try:
            return AuditAction(self.action)
        except ValueError:
            return AuditAction.CUSTOM

    @property
    def severity_enum(self) -> AuditSeverity:
        """Get severity as enum."""
        try:
            return AuditSeverity(self.severity)
        except ValueError:
            return AuditSeverity.INFO

    @property
    def changed_fields(self) -> list[str]:
        """Get list of fields that were changed."""
        return list(self.changes.keys())

    @classmethod
    def log(
        cls,
        action: AuditAction,
        user: Optional["AbstractUser"] = None,
        obj: models.Model | None = None,
        description: str = "",
        changes: dict | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        ip_address: str | None = None,
        user_agent: str = "",
        request_method: str = "",
        request_path: str = "",
        metadata: dict | None = None,
    ) -> "AuditLog":
        """
        Create an audit log entry.

        Args:
            action: The type of action being logged
            user: The user performing the action (or None for system/anonymous)
            obj: The object being acted upon
            description: Human-readable description
            changes: Dict of field changes {field: {"old": x, "new": y}}
            old_values: State before the action
            new_values: State after the action
            severity: Severity level of the event
            ip_address: Client IP address
            user_agent: Client User-Agent string
            request_method: HTTP method
            request_path: Request path
            metadata: Additional context

        Returns:
            The created AuditLog instance
        """
        # Get context from thread-local if not provided
        from .context import get_current_user, get_request_ip, get_user_agent

        if user is None:
            user = get_current_user()
        if ip_address is None:
            ip_address = get_request_ip()
        if not user_agent:
            user_agent = get_user_agent() or ""

        # Build content type info if object provided
        content_type = None
        object_id = None
        object_repr = ""

        if obj is not None:
            content_type = ContentType.objects.get_for_model(obj)
            object_id = str(obj.pk) if obj.pk else None
            object_repr = str(obj)[:500]

        return cls.objects.create(
            user=user,
            action=action.value if isinstance(action, AuditAction) else action,
            severity=severity.value if isinstance(severity, AuditSeverity) else severity,
            content_type=content_type,
            object_id=object_id,
            object_repr=object_repr,
            description=description,
            changes=changes or {},
            old_values=old_values or {},
            new_values=new_values or {},
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_path=request_path,
            metadata=metadata or {},
        )

    @classmethod
    async def alog(
        cls,
        action: AuditAction,
        user: Optional["AbstractUser"] = None,
        obj: models.Model | None = None,
        **kwargs,
    ) -> "AuditLog":
        """Async version of log()."""
        from asgiref.sync import sync_to_async

        return await sync_to_async(cls.log)(action, user, obj, **kwargs)
