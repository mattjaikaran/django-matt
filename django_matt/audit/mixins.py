"""
Auditable model mixins.

Provides mixins for automatic change tracking on Django models.
"""

from typing import TYPE_CHECKING, Any, Optional

from django.db import models

from .enums import AuditAction

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AuditableQuerySet(models.QuerySet):
    """QuerySet with audit logging support."""

    def update(self, **kwargs):
        """Override update to log bulk updates."""
        from .models import AuditLog

        # Get affected objects before update
        pks = list(self.values_list("pk", flat=True))

        # Perform the update
        result = super().update(**kwargs)

        # Log bulk update if any records were updated
        if result > 0 and pks:
            AuditLog.log(
                action=AuditAction.BULK_UPDATE,
                description=f"Bulk updated {result} {self.model.__name__} records",
                metadata={
                    "model": f"{self.model._meta.app_label}.{self.model.__name__}",
                    "count": result,
                    "pks": pks[:100],  # Limit logged PKs
                    "fields": list(kwargs.keys()),
                },
            )

        return result

    def delete(self):
        """Override delete to log bulk deletions."""
        from .models import AuditLog

        # Get affected objects before delete
        pks = list(self.values_list("pk", flat=True))
        count = len(pks)

        # Perform the delete
        result = super().delete()

        # Log bulk delete
        if count > 0:
            AuditLog.log(
                action=AuditAction.BULK_DELETE,
                description=f"Bulk deleted {count} {self.model.__name__} records",
                metadata={
                    "model": f"{self.model._meta.app_label}.{self.model.__name__}",
                    "count": count,
                    "pks": pks[:100],  # Limit logged PKs
                },
            )

        return result


class AuditableManager(models.Manager):
    """Manager that uses AuditableQuerySet."""

    def get_queryset(self):
        return AuditableQuerySet(self.model, using=self._db)


class AuditableMixin(models.Model):
    """
    Mixin for automatic audit logging on model changes.

    Tracks create, update, and delete operations automatically.

    Usage:
        class Article(AuditableMixin, models.Model):
            title = models.CharField(max_length=200)
            content = models.TextField()

            # Optional: customize which fields to track
            audit_fields = ['title', 'content']  # Only track these fields
            audit_exclude = ['updated_at']  # Exclude these fields

            # Optional: customize audit behavior
            audit_on_create = True
            audit_on_update = True
            audit_on_delete = True
    """

    # Configuration attributes (can be overridden in subclasses)
    audit_fields: set[str] | None = None  # Fields to track (None = all)
    audit_exclude: set[str] = set()  # Fields to exclude from tracking
    audit_on_create: bool = True
    audit_on_update: bool = True
    audit_on_delete: bool = True

    # Internal state
    _audit_original_values: dict = {}
    _audit_skip: bool = False

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._store_original_values()

    def _store_original_values(self) -> None:
        """Store current field values for change detection."""
        if self.pk:
            self._audit_original_values = self._get_auditable_values()
        else:
            self._audit_original_values = {}

    def _get_auditable_fields(self) -> set[str]:
        """Get the set of fields to track."""
        # Get all concrete field names
        all_fields = {f.name for f in self._meta.get_fields() if f.concrete and not f.many_to_many}

        # Filter to specified fields if set
        if self.audit_fields:
            all_fields = all_fields & set(self.audit_fields)

        # Exclude specified fields
        all_fields -= set(self.audit_exclude)

        # Always exclude internal fields
        all_fields -= {"_audit_original_values", "_audit_skip"}

        return all_fields

    def _get_auditable_values(self) -> dict:
        """Get current values of auditable fields."""
        values = {}
        for field_name in self._get_auditable_fields():
            try:
                value = getattr(self, field_name)
                # Convert to serializable format
                values[field_name] = self._serialize_value(value)
            except AttributeError:
                pass
        return values

    def _serialize_value(self, value: Any) -> Any:
        """Convert a value to a JSON-serializable format."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, models.Model):
            return str(value.pk) if value.pk else None
        if hasattr(value, "isoformat"):  # datetime, date, time
            return value.isoformat()
        if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
            return [self._serialize_value(v) for v in value]
        return str(value)

    def _get_changes(self) -> dict:
        """
        Detect changes between original and current values.

        Returns:
            Dict of changes: {field: {"old": old_value, "new": new_value}}
        """
        changes = {}
        current_values = self._get_auditable_values()

        for field_name in self._get_auditable_fields():
            old_value = self._audit_original_values.get(field_name)
            new_value = current_values.get(field_name)

            if old_value != new_value:
                changes[field_name] = {
                    "old": old_value,
                    "new": new_value,
                }

        return changes

    def save(self, *args, audit_user: Optional["AbstractUser"] = None, **kwargs):
        """
        Save the model with audit logging.

        Args:
            audit_user: Override the user for this audit entry
            *args, **kwargs: Standard save arguments
        """
        from .context import get_current_user
        from .models import AuditLog

        # Check if we should skip auditing
        if self._audit_skip:
            return super().save(*args, **kwargs)

        is_new = self.pk is None
        changes = {} if is_new else self._get_changes()

        # Perform the save
        result = super().save(*args, **kwargs)

        # Log the action
        user = audit_user or get_current_user()

        if is_new and self.audit_on_create:
            AuditLog.log(
                action=AuditAction.CREATE,
                user=user,
                obj=self,
                description=f"Created {self._meta.verbose_name}",
                new_values=self._get_auditable_values(),
            )
        elif not is_new and self.audit_on_update and changes:
            AuditLog.log(
                action=AuditAction.UPDATE,
                user=user,
                obj=self,
                description=f"Updated {self._meta.verbose_name}",
                changes=changes,
                old_values=self._audit_original_values,
                new_values=self._get_auditable_values(),
            )

        # Update stored values for next change detection
        self._store_original_values()

        return result

    def delete(self, *args, audit_user: Optional["AbstractUser"] = None, **kwargs):
        """
        Delete the model with audit logging.

        Args:
            audit_user: Override the user for this audit entry
        """
        from .context import get_current_user
        from .models import AuditLog

        if self._audit_skip or not self.audit_on_delete:
            return super().delete(*args, **kwargs)

        user = audit_user or get_current_user()

        # Store values before deletion
        old_values = self._get_auditable_values()
        pk = self.pk

        # Perform the delete
        result = super().delete(*args, **kwargs)

        # Log the deletion
        AuditLog.log(
            action=AuditAction.DELETE,
            user=user,
            description=f"Deleted {self._meta.verbose_name} (pk={pk})",
            old_values=old_values,
            metadata={"pk": str(pk)},
        )

        return result

    async def asave(self, *args, audit_user: Optional["AbstractUser"] = None, **kwargs):
        """Async version of save with audit logging."""
        from asgiref.sync import sync_to_async

        return await sync_to_async(self.save)(*args, audit_user=audit_user, **kwargs)

    async def adelete(self, *args, audit_user: Optional["AbstractUser"] = None, **kwargs):
        """Async version of delete with audit logging."""
        from asgiref.sync import sync_to_async

        return await sync_to_async(self.delete)(*args, audit_user=audit_user, **kwargs)

    def save_without_audit(self, *args, **kwargs):
        """Save without creating audit log."""
        self._audit_skip = True
        try:
            return super().save(*args, **kwargs)
        finally:
            self._audit_skip = False

    def delete_without_audit(self, *args, **kwargs):
        """Delete without creating audit log."""
        self._audit_skip = True
        try:
            return super().delete(*args, **kwargs)
        finally:
            self._audit_skip = False

    def refresh_from_db(self, *args, **kwargs):
        """Refresh and update stored original values."""
        result = super().refresh_from_db(*args, **kwargs)
        self._store_original_values()
        return result


class AuditableWithUserMixin(AuditableMixin):
    """
    Auditable mixin that also tracks created_by and updated_by.

    Adds automatic user tracking fields to the model.
    """

    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
    )
    updated_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
    )

    class Meta:
        abstract = True

    def save(self, *args, audit_user: Optional["AbstractUser"] = None, **kwargs):
        """Save with automatic user tracking."""
        from .context import get_current_user

        user = audit_user or get_current_user()

        if self.pk is None and user:
            self.created_by = user

        if user:
            self.updated_by = user

        return super().save(*args, audit_user=audit_user, **kwargs)
