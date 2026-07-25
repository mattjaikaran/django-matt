# file-length-max: 450
"""
Base admin classes for Django Unfold integration.

Provides enhanced ModelAdmin classes that work with both standard Django admin
and Django Unfold's enhanced admin theme.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.db import models

if TYPE_CHECKING:
    from django.http import HttpRequest

# Check if Unfold is installed
try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    from unfold.admin import StackedInline as UnfoldStackedInline
    from unfold.admin import TabularInline as UnfoldTabularInline

    HAS_UNFOLD = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin  # type: ignore[misc,assignment]
    UnfoldStackedInline = admin.StackedInline  # type: ignore[misc,assignment]
    UnfoldTabularInline = admin.TabularInline  # type: ignore[misc,assignment]
    HAS_UNFOLD = False


def register_admin(
    model: type[models.Model],
    site: admin.AdminSite | None = None,
):
    """
    Decorator to register a model admin class.

    Usage:
        @register_admin(User)
        class UserAdmin(MattModelAdmin):
            list_display = ["email", "username"]

        # Or with a custom admin site
        @register_admin(User, site=my_admin_site)
        class UserAdmin(MattModelAdmin):
            pass
    """

    def decorator(admin_class: type[admin.ModelAdmin]):
        target_site = site or admin.site
        target_site.register(model, admin_class)
        return admin_class

    return decorator


class MattModelAdmin(UnfoldModelAdmin):
    """
    Enhanced ModelAdmin base class compatible with Django Unfold.

    Features:
    - Automatic list_display from model fields
    - Automatic search_fields for text fields
    - Automatic list_filter for choice/boolean/date fields
    - Automatic date_hierarchy for date fields
    - Fieldset auto-generation
    - Works with or without Unfold installed
    """

    # Auto-configuration options
    auto_list_display: bool = True
    auto_search_fields: bool = True
    auto_list_filter: bool = True
    auto_date_hierarchy: bool = True
    auto_readonly_fields: bool = True

    # Fields to always exclude from auto-generation
    exclude_from_auto: list[str] = ["password"]

    # Fields to always include as readonly
    always_readonly: list[str] = ["id", "created_at", "updated_at", "pk"]

    # Unfold-specific settings
    compressed_fields: bool = True
    warn_unsaved_form: bool = True

    def __init__(self, model: type[models.Model], admin_site: admin.AdminSite):
        # Auto-configure before calling super().__init__
        self._auto_configure(model)
        super().__init__(model, admin_site)

    def _auto_configure(self, model: type[models.Model]):
        """Auto-configure admin options based on model fields."""
        opts = model._meta

        # Auto list_display
        if self.auto_list_display and not self.list_display:
            self.list_display = self._generate_list_display(opts)

        # Auto search_fields
        if self.auto_search_fields and not self.search_fields:
            self.search_fields = self._generate_search_fields(opts)

        # Auto list_filter
        if self.auto_list_filter and not self.list_filter:
            self.list_filter = self._generate_list_filter(opts)

        # Auto date_hierarchy
        if self.auto_date_hierarchy and not self.date_hierarchy:
            self.date_hierarchy = self._generate_date_hierarchy(opts)

        # Auto readonly_fields
        if self.auto_readonly_fields and not self.readonly_fields:
            self.readonly_fields = self._generate_readonly_fields(opts)

    def _generate_list_display(self, opts) -> list[str]:
        """Generate list_display from model fields."""
        display = []

        # Common patterns for "name" fields
        name_fields = ["name", "title", "email", "username", "__str__"]

        for field_name in name_fields:
            if field_name == "__str__":
                display.append("__str__")
                break
            try:
                opts.get_field(field_name)
                display.append(field_name)
                break
            except Exception:
                continue

        # Add other useful fields
        for field in opts.get_fields():
            if not hasattr(field, "name"):
                continue

            name = field.name
            if name in display or name in self.exclude_from_auto:
                continue

            # Skip relations for list_display
            if field.is_relation and not field.many_to_one:
                continue

            # Add boolean fields (show as icons)
            if isinstance(field, models.BooleanField):
                display.append(name)
                continue

            # Add date fields
            if isinstance(field, (models.DateField, models.DateTimeField)):
                display.append(name)
                continue

            # Add status/choice fields
            if hasattr(field, "choices") and field.choices:
                display.append(name)
                continue

        # Limit to reasonable number
        return display[:8]

    def _generate_search_fields(self, opts) -> list[str]:
        """Generate search_fields for text-based fields."""
        search = []

        for field in opts.get_fields():
            if not hasattr(field, "name"):
                continue

            name = field.name
            if name in self.exclude_from_auto:
                continue

            # Add text fields
            if isinstance(field, (models.CharField, models.TextField)):
                search.append(name)

            # Add email fields
            if isinstance(field, models.EmailField):
                search.append(name)

        return search[:5]  # Limit for performance

    def _generate_list_filter(self, opts) -> list[str]:
        """Generate list_filter for filterable fields."""
        filters = []

        for field in opts.get_fields():
            if not hasattr(field, "name"):
                continue

            name = field.name
            if name in self.exclude_from_auto:
                continue

            # Boolean fields
            if isinstance(field, models.BooleanField):
                filters.append(name)

            # Choice fields
            if hasattr(field, "choices") and field.choices:
                filters.append(name)

            # Date fields
            if isinstance(field, (models.DateField, models.DateTimeField)):
                filters.append(name)

            # ForeignKey with limited choices
            if isinstance(field, models.ForeignKey):
                # Only add if related model is small
                filters.append(name)

        return filters[:6]

    def _generate_date_hierarchy(self, opts) -> str | None:
        """Find a suitable date field for hierarchy."""
        candidates = ["created_at", "created", "date", "timestamp", "updated_at"]

        for candidate in candidates:
            try:
                field = opts.get_field(candidate)
                if isinstance(field, (models.DateField, models.DateTimeField)):
                    return candidate
            except Exception:
                continue

        return None

    def _generate_readonly_fields(self, opts) -> tuple[str, ...]:
        """Generate readonly_fields for auto-managed fields."""
        readonly = []

        for field_name in self.always_readonly:
            try:
                opts.get_field(field_name)
                readonly.append(field_name)
            except Exception:
                continue

        return tuple(readonly)

    def get_queryset(self, request: HttpRequest):
        """Override to support custom querysets."""
        qs = super().get_queryset(request)

        # Add select_related for ForeignKey fields in list_display
        select_related = []
        for field_name in self.list_display:
            if "__" in str(field_name):
                select_related.append(field_name.split("__")[0])
            else:
                try:
                    field = self.model._meta.get_field(field_name)
                    if isinstance(field, models.ForeignKey):
                        select_related.append(field_name)
                except Exception:
                    pass

        if select_related:
            qs = qs.select_related(*select_related)

        return qs


class MattStackedInline(UnfoldStackedInline):
    """Enhanced StackedInline compatible with Unfold."""

    extra = 0
    show_change_link = True

    # Auto-configuration
    auto_readonly_fields: bool = True
    always_readonly: list[str] = ["id", "created_at", "updated_at"]

    def __init__(self, parent_model: type[models.Model], admin_site: admin.AdminSite):
        if self.auto_readonly_fields and not self.readonly_fields:
            self.readonly_fields = self._generate_readonly_fields()
        super().__init__(parent_model, admin_site)

    def _generate_readonly_fields(self) -> tuple[str, ...]:
        """Generate readonly_fields for auto-managed fields."""
        if not self.model:
            return ()

        readonly = []
        opts = self.model._meta

        for field_name in self.always_readonly:
            try:
                opts.get_field(field_name)
                readonly.append(field_name)
            except Exception:
                continue

        return tuple(readonly)


class MattTabularInline(UnfoldTabularInline):
    """Enhanced TabularInline compatible with Unfold."""

    extra = 0
    show_change_link = True

    # Auto-configuration
    auto_readonly_fields: bool = True
    always_readonly: list[str] = ["id", "created_at", "updated_at"]

    def __init__(self, parent_model: type[models.Model], admin_site: admin.AdminSite):
        if self.auto_readonly_fields and not self.readonly_fields:
            self.readonly_fields = self._generate_readonly_fields()
        super().__init__(parent_model, admin_site)

    def _generate_readonly_fields(self) -> tuple[str, ...]:
        """Generate readonly_fields for auto-managed fields."""
        if not self.model:
            return ()

        readonly = []
        opts = self.model._meta

        for field_name in self.always_readonly:
            try:
                opts.get_field(field_name)
                readonly.append(field_name)
            except Exception:
                continue

        return tuple(readonly)


class TenantModelAdmin(MattModelAdmin):
    """
    ModelAdmin for multi-tenant models.

    Automatically filters queryset by current organization/tenant.

    Usage:
        @register_admin(Project)
        class ProjectAdmin(TenantModelAdmin):
            tenant_field = "organization"
    """

    # Field name that references the tenant (organization)
    tenant_field: str = "organization"

    # Whether to hide the tenant field in forms
    hide_tenant_field: bool = True

    # Whether to auto-set tenant on save
    auto_set_tenant: bool = True

    def get_queryset(self, request: HttpRequest):
        """Filter queryset by tenant if user has one."""
        qs = super().get_queryset(request)

        # Check if user has organization attribute
        if hasattr(request.user, "organization") and request.user.organization:
            qs = qs.filter(**{self.tenant_field: request.user.organization})
        elif hasattr(request.user, "current_organization"):
            org = request.user.current_organization
            if org:
                qs = qs.filter(**{self.tenant_field: org})

        return qs

    def get_exclude(self, request: HttpRequest, obj=None):
        """Exclude tenant field from forms if configured."""
        exclude = list(super().get_exclude(request, obj) or [])

        if self.hide_tenant_field and self.tenant_field not in exclude:
            exclude.append(self.tenant_field)

        return exclude

    def save_model(self, request: HttpRequest, obj, form, change):
        """Auto-set tenant on save if not set."""
        if self.auto_set_tenant and not change:
            if not getattr(obj, self.tenant_field, None):
                tenant = None
                if hasattr(request.user, "organization"):
                    tenant = request.user.organization
                elif hasattr(request.user, "current_organization"):
                    tenant = request.user.current_organization

                if tenant:
                    setattr(obj, self.tenant_field, tenant)

        super().save_model(request, obj, form, change)


__all__ = [
    "MattModelAdmin",
    "MattStackedInline",
    "MattTabularInline",
    "TenantModelAdmin",
    "register_admin",
    "HAS_UNFOLD",
]
