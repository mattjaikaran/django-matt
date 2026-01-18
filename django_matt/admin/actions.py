"""
Common admin actions for bulk operations.

Provides reusable actions for export, soft delete, restore, etc.
"""

from __future__ import annotations

import csv
import json
from typing import TYPE_CHECKING

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest


@admin.action(description="Export selected as CSV")
def export_as_csv(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet,
):
    """
    Export selected objects as CSV.

    Usage:
        class MyAdmin(MattModelAdmin):
            actions = [export_as_csv]
    """
    opts = modeladmin.model._meta
    fields = _get_export_fields(modeladmin)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{opts.model_name}_export.csv"'

    writer = csv.writer(response)
    writer.writerow(fields)

    for obj in queryset:
        row = []
        for field in fields:
            value = _get_field_value(obj, field)
            row.append(str(value) if value is not None else "")
        writer.writerow(row)

    messages.success(request, f"Exported {queryset.count()} item(s) as CSV.")
    return response


@admin.action(description="Export selected as JSON")
def export_as_json(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet,
):
    """
    Export selected objects as JSON.

    Usage:
        class MyAdmin(MattModelAdmin):
            actions = [export_as_json]
    """
    opts = modeladmin.model._meta
    fields = _get_export_fields(modeladmin)

    data = []
    for obj in queryset:
        item = {}
        for field in fields:
            value = _get_field_value(obj, field)
            # Handle non-JSON-serializable types
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            elif hasattr(value, "pk"):
                value = value.pk
            item[field] = value
        data.append(item)

    response = HttpResponse(
        json.dumps(data, indent=2, default=str),
        content_type="application/json",
    )
    response["Content-Disposition"] = f'attachment; filename="{opts.model_name}_export.json"'

    messages.success(request, f"Exported {queryset.count()} item(s) as JSON.")
    return response


@admin.action(description="Soft delete selected")
def soft_delete_selected(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet,
):
    """
    Soft delete selected objects (set deleted_at timestamp).

    Usage:
        class MyAdmin(MattModelAdmin):
            actions = [soft_delete_selected]
    """
    deleted_at_field = getattr(modeladmin, "deleted_at_field", "deleted_at")

    # Check if model has deleted_at field
    try:
        modeladmin.model._meta.get_field(deleted_at_field)
    except Exception:
        messages.error(
            request,
            f"Model does not have a '{deleted_at_field}' field for soft delete.",
        )
        return

    count = queryset.update(**{deleted_at_field: timezone.now()})
    messages.success(request, f"Soft deleted {count} item(s).")


@admin.action(description="Restore selected (undo soft delete)")
def restore_selected(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet,
):
    """
    Restore soft-deleted objects (clear deleted_at timestamp).

    Usage:
        class MyAdmin(MattModelAdmin):
            actions = [restore_selected]
    """
    deleted_at_field = getattr(modeladmin, "deleted_at_field", "deleted_at")

    # Check if model has deleted_at field
    try:
        modeladmin.model._meta.get_field(deleted_at_field)
    except Exception:
        messages.error(
            request,
            f"Model does not have a '{deleted_at_field}' field for soft delete.",
        )
        return

    count = queryset.update(**{deleted_at_field: None})
    messages.success(request, f"Restored {count} item(s).")


@admin.action(description="Permanently delete selected")
def hard_delete_selected(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet,
):
    """
    Permanently delete selected objects (bypass soft delete).

    Usage:
        class MyAdmin(MattModelAdmin):
            actions = [hard_delete_selected]
    """
    count = queryset.count()
    queryset.delete()
    messages.success(request, f"Permanently deleted {count} item(s).")


@admin.action(description="Mark as active")
def mark_active(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet,
):
    """
    Mark selected objects as active.

    Usage:
        class MyAdmin(MattModelAdmin):
            actions = [mark_active]
    """
    active_field = getattr(modeladmin, "active_field", "is_active")

    try:
        modeladmin.model._meta.get_field(active_field)
    except Exception:
        messages.error(request, f"Model does not have a '{active_field}' field.")
        return

    count = queryset.update(**{active_field: True})
    messages.success(request, f"Marked {count} item(s) as active.")


@admin.action(description="Mark as inactive")
def mark_inactive(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet,
):
    """
    Mark selected objects as inactive.

    Usage:
        class MyAdmin(MattModelAdmin):
            actions = [mark_inactive]
    """
    active_field = getattr(modeladmin, "active_field", "is_active")

    try:
        modeladmin.model._meta.get_field(active_field)
    except Exception:
        messages.error(request, f"Model does not have a '{active_field}' field.")
        return

    count = queryset.update(**{active_field: False})
    messages.success(request, f"Marked {count} item(s) as inactive.")


@admin.action(description="Duplicate selected")
def duplicate_selected(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet,
):
    """
    Duplicate selected objects.

    Usage:
        class MyAdmin(MattModelAdmin):
            actions = [duplicate_selected]
    """
    count = 0
    for obj in queryset:
        # Clear primary key to create new object
        obj.pk = None
        obj.id = None

        # Clear unique fields if they exist
        opts = modeladmin.model._meta
        for field in opts.get_fields():
            if hasattr(field, "unique") and field.unique and field.name not in ("pk", "id"):
                # Append suffix to unique fields
                value = getattr(obj, field.name, None)
                if value and isinstance(value, str):
                    setattr(obj, field.name, f"{value} (copy)")

        obj.save()
        count += 1

    messages.success(request, f"Duplicated {count} item(s).")


def _get_export_fields(modeladmin: admin.ModelAdmin) -> list[str]:
    """Get fields to export for a model admin."""
    # Check for explicit export_fields
    if hasattr(modeladmin, "export_fields") and modeladmin.export_fields:
        return modeladmin.export_fields

    # Use list_display if available
    if modeladmin.list_display and modeladmin.list_display != ("__str__",):
        fields = []
        for field in modeladmin.list_display:
            if field != "__str__" and not callable(getattr(modeladmin, field, None)):
                fields.append(field)
        if fields:
            return fields

    # Fall back to model fields
    exclude = getattr(modeladmin, "export_exclude", ["password"])
    fields = []

    for field in modeladmin.model._meta.get_fields():
        if not hasattr(field, "name"):
            continue
        if field.name in exclude:
            continue
        if field.is_relation and not field.many_to_one:
            continue
        fields.append(field.name)

    return fields


def _get_field_value(obj, field_name: str):
    """Get a field value from an object, handling nested fields."""
    if "__" in field_name:
        parts = field_name.split("__")
        value = obj
        for part in parts:
            if value is None:
                return None
            value = getattr(value, part, None)
        return value

    value = getattr(obj, field_name, None)
    if callable(value):
        value = value()
    return value


__all__ = [
    "export_as_csv",
    "export_as_json",
    "soft_delete_selected",
    "restore_selected",
    "hard_delete_selected",
    "mark_active",
    "mark_inactive",
    "duplicate_selected",
]
