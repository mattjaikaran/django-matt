"""Models for {{ project_name }}."""

from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    """Audit log entry for tracking user actions."""

    class Action(models.TextChoices):
        CREATE = "create"
        UPDATE = "update"
        DELETE = "delete"
        LOGIN = "login"
        LOGOUT = "logout"
        EXPORT = "export"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_entries",
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100, blank=True, default="")
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "audit entries"

    def __str__(self) -> str:
        return f"{self.action} {self.resource_type} by {self.user}"


class FeatureFlag(models.Model):
    """Feature flag for gradual rollout."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    enabled = models.BooleanField(default=False)
    rollout_percent = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        status = "ON" if self.enabled else "OFF"
        return f"{self.name} ({status})"
