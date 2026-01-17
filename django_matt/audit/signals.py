"""
Audit signals.

Django signals for audit logging events.
"""

from typing import Any, Optional, TYPE_CHECKING

from django.dispatch import Signal

if TYPE_CHECKING:
    from django.db import models
    from .models import AuditLog
    from .enums import AuditAction


# Signal sent before an audit log is created
pre_audit = Signal()
# Arguments: action, user, obj, changes

# Signal sent after an audit log is created
post_audit = Signal()
# Arguments: audit_log, action, user, obj, changes

# Internal flag for signal connection state
_signals_connected = False


def connect_audit_signals() -> None:
    """
    Connect Django model signals for automatic audit logging.

    This enables audit logging for ALL models, not just those with AuditableMixin.
    Use with caution as it can create many audit log entries.

    Usage:
        # In your app's ready() method
        from django_matt.audit import connect_audit_signals
        connect_audit_signals()
    """
    global _signals_connected

    if _signals_connected:
        return

    from django.db.models.signals import post_save, post_delete, pre_save
    from django.contrib.contenttypes.models import ContentType

    # Connect signals
    pre_save.connect(_pre_save_handler)
    post_save.connect(_post_save_handler)
    post_delete.connect(_post_delete_handler)

    _signals_connected = True


def disconnect_audit_signals() -> None:
    """Disconnect audit signals."""
    global _signals_connected

    if not _signals_connected:
        return

    from django.db.models.signals import post_save, post_delete, pre_save

    pre_save.disconnect(_pre_save_handler)
    post_save.disconnect(_post_save_handler)
    post_delete.disconnect(_post_delete_handler)

    _signals_connected = False


# Track original values before save
_pre_save_values = {}


def _should_audit_model(model: type) -> bool:
    """Check if a model should be audited via signals."""
    from .models import AuditLog

    # Never audit the AuditLog model itself
    if model is AuditLog:
        return False

    # Skip Django internal models by default
    skip_apps = {"contenttypes", "sessions", "admin", "auth"}
    if model._meta.app_label in skip_apps:
        return False

    # Skip migrations
    if model._meta.app_label == "django" and model.__name__ == "Migration":
        return False

    return True


def _pre_save_handler(sender, instance, **kwargs):
    """Store original values before save."""
    if not _should_audit_model(sender):
        return

    # Skip if instance has audit mixin (it handles its own logging)
    from .mixins import AuditableMixin
    if isinstance(instance, AuditableMixin):
        return

    if instance.pk:
        try:
            # Get original from database
            original = sender.objects.get(pk=instance.pk)
            _pre_save_values[id(instance)] = _get_model_values(original)
        except sender.DoesNotExist:
            pass


def _post_save_handler(sender, instance, created, **kwargs):
    """Log model creation/update."""
    if not _should_audit_model(sender):
        return

    # Skip if instance has audit mixin
    from .mixins import AuditableMixin
    if isinstance(instance, AuditableMixin):
        return

    from .models import AuditLog
    from .enums import AuditAction
    from .context import get_current_user

    user = get_current_user()

    if created:
        # Send pre_audit signal
        pre_audit.send(
            sender=sender,
            action=AuditAction.CREATE,
            user=user,
            obj=instance,
            changes=None,
        )

        audit_log = AuditLog.log(
            action=AuditAction.CREATE,
            user=user,
            obj=instance,
            description=f"Created {sender.__name__}",
            new_values=_get_model_values(instance),
        )

        # Send post_audit signal
        post_audit.send(
            sender=sender,
            audit_log=audit_log,
            action=AuditAction.CREATE,
            user=user,
            obj=instance,
            changes=None,
        )
    else:
        # Get original values
        original_values = _pre_save_values.pop(id(instance), {})
        current_values = _get_model_values(instance)

        # Calculate changes
        changes = _calculate_changes(original_values, current_values)

        if changes:
            pre_audit.send(
                sender=sender,
                action=AuditAction.UPDATE,
                user=user,
                obj=instance,
                changes=changes,
            )

            audit_log = AuditLog.log(
                action=AuditAction.UPDATE,
                user=user,
                obj=instance,
                description=f"Updated {sender.__name__}",
                changes=changes,
                old_values=original_values,
                new_values=current_values,
            )

            post_audit.send(
                sender=sender,
                audit_log=audit_log,
                action=AuditAction.UPDATE,
                user=user,
                obj=instance,
                changes=changes,
            )


def _post_delete_handler(sender, instance, **kwargs):
    """Log model deletion."""
    if not _should_audit_model(sender):
        return

    # Skip if instance has audit mixin
    from .mixins import AuditableMixin
    if isinstance(instance, AuditableMixin):
        return

    from .models import AuditLog
    from .enums import AuditAction
    from .context import get_current_user

    user = get_current_user()
    old_values = _get_model_values(instance)

    pre_audit.send(
        sender=sender,
        action=AuditAction.DELETE,
        user=user,
        obj=instance,
        changes=None,
    )

    audit_log = AuditLog.log(
        action=AuditAction.DELETE,
        user=user,
        description=f"Deleted {sender.__name__} (pk={instance.pk})",
        old_values=old_values,
        metadata={"pk": str(instance.pk), "model": sender.__name__},
    )

    post_audit.send(
        sender=sender,
        audit_log=audit_log,
        action=AuditAction.DELETE,
        user=user,
        obj=instance,
        changes=None,
    )


def _get_model_values(instance) -> dict:
    """Extract field values from a model instance."""
    values = {}

    for field in instance._meta.get_fields():
        if not field.concrete or field.many_to_many:
            continue

        try:
            value = getattr(instance, field.name)
            values[field.name] = _serialize_value(value)
        except AttributeError:
            pass

    return values


def _calculate_changes(old_values: dict, new_values: dict) -> dict:
    """Calculate changes between two value dicts."""
    changes = {}

    all_fields = set(old_values.keys()) | set(new_values.keys())

    for field in all_fields:
        old = old_values.get(field)
        new = new_values.get(field)

        if old != new:
            changes[field] = {"old": old, "new": new}

    return changes


def _serialize_value(value: Any) -> Any:
    """Convert a value to a JSON-serializable format."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "pk"):  # Model instance
        return str(value.pk) if value.pk else None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
