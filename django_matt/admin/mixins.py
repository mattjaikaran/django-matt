# file-length-max: 450
"""
Admin mixins for common patterns.

Provides reusable mixins for audit logging, soft delete, export, etc.
"""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone

import orjson

if TYPE_CHECKING:
    from django.http import HttpRequest


class AuditAdminMixin:
    """
    Mixin for models with audit fields (created_at, updated_at, created_by, updated_by).

    Automatically:
    - Shows audit fields as readonly
    - Sets created_by/updated_by on save
    - Adds audit info to list_display
    """

    # Field names (override if your model uses different names)
    created_at_field: str = "created_at"
    updated_at_field: str = "updated_at"
    created_by_field: str = "created_by"
    updated_by_field: str = "updated_by"

    # Whether to show audit fields in list_display
    show_audit_in_list: bool = True

    def get_readonly_fields(self, request: HttpRequest, obj=None):
        """Add audit fields to readonly."""
        readonly = list(super().get_readonly_fields(request, obj) or [])

        audit_fields = [
            self.created_at_field,
            self.updated_at_field,
            self.created_by_field,
            self.updated_by_field,
        ]

        for field in audit_fields:
            if field not in readonly:
                try:
                    self.model._meta.get_field(field)
                    readonly.append(field)
                except Exception:
                    pass

        return readonly

    def get_list_display(self, request: HttpRequest):
        """Add audit fields to list_display if configured."""
        display = list(super().get_list_display(request) or [])

        if self.show_audit_in_list:
            if self.created_at_field not in display:
                try:
                    self.model._meta.get_field(self.created_at_field)
                    display.append(self.created_at_field)
                except Exception:
                    pass

        return display

    def save_model(self, request: HttpRequest, obj, form, change):
        """Set created_by/updated_by on save."""
        # Set updated_by
        if hasattr(obj, self.updated_by_field):
            setattr(obj, self.updated_by_field, request.user)

        # Set created_by only on create
        if not change and hasattr(obj, self.created_by_field):
            if not getattr(obj, self.created_by_field, None):
                setattr(obj, self.created_by_field, request.user)

        super().save_model(request, obj, form, change)


class SoftDeleteAdminMixin:
    """
    Mixin for models with soft delete (deleted_at field).

    Provides:
    - Filter to show/hide deleted items
    - Restore action
    - Hard delete action
    """

    # Field name for soft delete timestamp
    deleted_at_field: str = "deleted_at"
    deleted_by_field: str = "deleted_by"

    # Default queryset behavior
    show_deleted_by_default: bool = False

    # Actions
    include_restore_action: bool = True
    include_hard_delete_action: bool = True

    def get_queryset(self, request: HttpRequest):
        """Optionally include deleted items."""
        qs = super().get_queryset(request)

        # Check for filter parameter
        show_deleted = request.GET.get("show_deleted", "")

        if not show_deleted and not self.show_deleted_by_default:
            # Exclude deleted by default
            qs = qs.filter(**{f"{self.deleted_at_field}__isnull": True})

        return qs

    def get_list_filter(self, request: HttpRequest):
        """Add deleted filter."""
        filters = list(super().get_list_filter(request) or [])

        # Capture deleted_at_field for use in the filter class
        deleted_field = self.deleted_at_field

        # Add custom deleted filter
        class DeletedFilter(admin.SimpleListFilter):
            title = "deleted status"
            parameter_name = "show_deleted"

            def lookups(self, request, model_admin):
                return [
                    ("", "Active only"),
                    ("1", "Include deleted"),
                    ("2", "Deleted only"),
                ]

            def queryset(self, request, queryset):
                if self.value() == "1":
                    return queryset
                if self.value() == "2":
                    return queryset.exclude(**{f"{deleted_field}__isnull": True})
                return queryset.filter(**{f"{deleted_field}__isnull": True})

        filters.append(DeletedFilter)
        return filters

    def get_actions(self, request: HttpRequest):
        """Add soft delete actions."""
        actions = super().get_actions(request)

        if self.include_restore_action:
            actions["restore_selected"] = (
                self._restore_selected,
                "restore_selected",
                "Restore selected items",
            )

        if self.include_hard_delete_action:
            actions["hard_delete_selected"] = (
                self._hard_delete_selected,
                "hard_delete_selected",
                "Permanently delete selected items",
            )

        return actions

    def _restore_selected(self, request: HttpRequest, queryset):
        """Restore soft-deleted items."""
        updated = queryset.update(**{self.deleted_at_field: None})
        messages.success(request, f"Restored {updated} item(s).")

    _restore_selected.short_description = "Restore selected items"

    def _hard_delete_selected(self, request: HttpRequest, queryset):
        """Permanently delete items."""
        count = queryset.count()
        queryset.delete()
        messages.success(request, f"Permanently deleted {count} item(s).")

    _hard_delete_selected.short_description = "Permanently delete selected items"

    def delete_model(self, request: HttpRequest, obj):
        """Soft delete instead of hard delete."""
        setattr(obj, self.deleted_at_field, timezone.now())

        if hasattr(obj, self.deleted_by_field):
            setattr(obj, self.deleted_by_field, request.user)

        obj.save()

    def delete_queryset(self, request: HttpRequest, queryset):
        """Soft delete queryset."""
        update_fields = {self.deleted_at_field: timezone.now()}

        if self.deleted_by_field:
            # Note: This won't work for deleted_by since it needs user
            # For bulk soft delete, we just set the timestamp
            pass

        queryset.update(**update_fields)


class ReadOnlyAdminMixin:
    """
    Mixin to make an admin read-only.

    Useful for audit logs, history tables, etc.
    """

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False


class ExportAdminMixin:
    """
    Mixin to add export actions (CSV, JSON).
    """

    # Fields to include in export (None = all)
    export_fields: list[str] | None = None

    # Fields to exclude from export
    export_exclude: list[str] = ["password"]

    def get_actions(self, request: HttpRequest):
        """Add export actions."""
        actions = super().get_actions(request)

        actions["export_csv"] = (
            self._export_as_csv,
            "export_csv",
            "Export selected as CSV",
        )

        actions["export_json"] = (
            self._export_as_json,
            "export_json",
            "Export selected as JSON",
        )

        return actions

    def _get_export_fields(self) -> list[str]:
        """Get fields to export."""
        if self.export_fields:
            return self.export_fields

        fields = []
        for field in self.model._meta.get_fields():
            if not hasattr(field, "name"):
                continue
            if field.name in self.export_exclude:
                continue
            if field.is_relation and not field.many_to_one:
                continue
            fields.append(field.name)

        return fields

    def _export_as_csv(self, request: HttpRequest, queryset):
        """Export queryset as CSV."""
        fields = self._get_export_fields()

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="{self.model._meta.model_name}_export.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(fields)

        for obj in queryset:
            row = []
            for field in fields:
                value = getattr(obj, field, "")
                if callable(value):
                    value = value()
                row.append(str(value) if value is not None else "")
            writer.writerow(row)

        return response

    _export_as_csv.short_description = "Export selected as CSV"

    def _export_as_json(self, request: HttpRequest, queryset):
        """Export queryset as JSON."""
        fields = self._get_export_fields()

        data = []
        for obj in queryset:
            item = {}
            for field in fields:
                value = getattr(obj, field, None)
                if callable(value):
                    value = value()
                # Handle non-serializable types
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                elif hasattr(value, "pk"):
                    value = value.pk
                item[field] = value
            data.append(item)

        response = HttpResponse(
            orjson.dumps(data, default=str, option=orjson.OPT_INDENT_2).decode(),
            content_type="application/json",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{self.model._meta.model_name}_export.json"'
        )

        return response

    _export_as_json.short_description = "Export selected as JSON"


class MultiTenantAdminMixin:
    """
    Mixin for multi-tenant admin filtering.

    Automatically filters queryset based on user's organization.
    """

    # Field name that references the tenant
    tenant_field: str = "organization"

    # Whether to hide tenant field in forms
    hide_tenant_in_form: bool = True

    # Whether to auto-set tenant on create
    auto_set_tenant: bool = True

    def get_queryset(self, request: HttpRequest):
        """Filter by tenant."""
        qs = super().get_queryset(request)

        tenant = self._get_current_tenant(request)
        if tenant:
            qs = qs.filter(**{self.tenant_field: tenant})

        return qs

    def _get_current_tenant(self, request: HttpRequest):
        """Get current tenant from request/user."""
        user = request.user

        # Try various common patterns
        if hasattr(user, "organization"):
            return user.organization
        if hasattr(user, "current_organization"):
            return user.current_organization
        if hasattr(request, "organization"):
            return request.organization
        if hasattr(request, "tenant"):
            return request.tenant

        return None

    def get_exclude(self, request: HttpRequest, obj=None):
        """Exclude tenant field from form."""
        exclude = list(super().get_exclude(request, obj) or [])

        if self.hide_tenant_in_form and self.tenant_field not in exclude:
            exclude.append(self.tenant_field)

        return exclude

    def save_model(self, request: HttpRequest, obj, form, change):
        """Auto-set tenant on create."""
        if self.auto_set_tenant and not change:
            if not getattr(obj, self.tenant_field, None):
                tenant = self._get_current_tenant(request)
                if tenant:
                    setattr(obj, self.tenant_field, tenant)

        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        """Filter foreign key choices by tenant."""
        if db_field.name == self.tenant_field:
            tenant = self._get_current_tenant(request)
            if tenant:
                kwargs["queryset"] = db_field.related_model.objects.filter(pk=tenant.pk)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


__all__ = [
    "AuditAdminMixin",
    "SoftDeleteAdminMixin",
    "ReadOnlyAdminMixin",
    "ExportAdminMixin",
    "MultiTenantAdminMixin",
]
