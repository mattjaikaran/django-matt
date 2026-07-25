# file-length-max: 550
"""
Admin class generator for auto-generating admin.py from Django models.

Usage:
    from django_matt.admin.generator import generate_admin_class, AdminGenerator

    # Generate a single admin class
    UserAdmin = generate_admin_class(User)
    admin.site.register(User, UserAdmin)

    # Generate admin module code
    code = generate_admin_module([User, Post, Comment])
    print(code)  # Python code for admin.py

    # Use generator for more control
    generator = AdminGenerator(
        include_audit=True,
        include_soft_delete=True,
        include_export=True,
    )
    UserAdmin = generator.generate(User)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.db import models

if TYPE_CHECKING:
    from collections.abc import Sequence

from django_matt.admin.base import MattModelAdmin


class AdminGenerator:
    """
    Generator for creating admin classes from Django models.

    Provides extensive customization options for the generated admin.
    """

    def __init__(
        self,
        # Base class options
        base_class: type[admin.ModelAdmin] | None = None,
        # Feature flags
        include_audit: bool = True,
        include_soft_delete: bool = False,
        include_export: bool = True,
        include_multi_tenant: bool = False,
        # Field options
        list_display_limit: int = 8,
        search_fields_limit: int = 5,
        list_filter_limit: int = 6,
        # Readonly fields
        always_readonly: list[str] | None = None,
        # Excluded fields
        exclude_fields: list[str] | None = None,
        # Tenant configuration
        tenant_field: str = "organization",
    ):
        self.base_class = base_class or MattModelAdmin
        self.include_audit = include_audit
        self.include_soft_delete = include_soft_delete
        self.include_export = include_export
        self.include_multi_tenant = include_multi_tenant
        self.list_display_limit = list_display_limit
        self.search_fields_limit = search_fields_limit
        self.list_filter_limit = list_filter_limit
        self.always_readonly = always_readonly or ["id", "created_at", "updated_at", "pk"]
        self.exclude_fields = exclude_fields or ["password"]
        self.tenant_field = tenant_field

    def generate(
        self,
        model: type[models.Model],
        **overrides,
    ) -> type[admin.ModelAdmin]:
        """
        Generate an admin class for the given model.

        Args:
            model: Django model class
            **overrides: Override any admin attribute

        Returns:
            Generated admin class
        """
        opts = model._meta

        # Build mixins list
        mixins = []
        if self.include_audit:
            from django_matt.admin.mixins import AuditAdminMixin

            mixins.append(AuditAdminMixin)

        if self.include_soft_delete and self._has_field(opts, "deleted_at"):
            from django_matt.admin.mixins import SoftDeleteAdminMixin

            mixins.append(SoftDeleteAdminMixin)

        if self.include_export:
            from django_matt.admin.mixins import ExportAdminMixin

            mixins.append(ExportAdminMixin)

        if self.include_multi_tenant and self._has_field(opts, self.tenant_field):
            from django_matt.admin.mixins import MultiTenantAdminMixin

            mixins.append(MultiTenantAdminMixin)

        # Generate class attributes
        attrs = {
            "list_display": self._generate_list_display(opts),
            "search_fields": self._generate_search_fields(opts),
            "list_filter": self._generate_list_filter(opts),
            "readonly_fields": self._generate_readonly_fields(opts),
            "ordering": self._generate_ordering(opts),
        }

        # Add date_hierarchy if available
        date_hierarchy = self._generate_date_hierarchy(opts)
        if date_hierarchy:
            attrs["date_hierarchy"] = date_hierarchy

        # Add fieldsets if model has many fields
        fieldsets = self._generate_fieldsets(opts)
        if fieldsets:
            attrs["fieldsets"] = fieldsets

        # Add inlines for related models
        inlines = self._generate_inlines(opts)
        if inlines:
            attrs["inlines"] = inlines

        # Apply overrides
        attrs.update(overrides)

        # Create class
        bases = tuple(mixins) + (self.base_class,)
        admin_class = type(f"{model.__name__}Admin", bases, attrs)

        return admin_class

    def _has_field(self, opts, field_name: str) -> bool:
        """Check if model has a field."""
        try:
            opts.get_field(field_name)
            return True
        except Exception:
            return False

    def _generate_list_display(self, opts) -> list[str]:
        """Generate list_display."""
        display = []

        # Priority fields
        priority = ["name", "title", "email", "username"]
        for field_name in priority:
            if self._has_field(opts, field_name):
                display.append(field_name)
                break

        if not display:
            display.append("__str__")

        # Add other useful fields
        for field in opts.get_fields():
            if not hasattr(field, "name"):
                continue

            name = field.name
            if name in display or name in self.exclude_fields:
                continue

            if len(display) >= self.list_display_limit:
                break

            # Skip complex relations
            if field.is_relation and not isinstance(field, models.ForeignKey):
                continue

            # Add booleans, dates, choices
            if (
                isinstance(field, models.BooleanField)
                or isinstance(field, (models.DateField, models.DateTimeField))
                or (hasattr(field, "choices") and field.choices)
                or isinstance(field, models.ForeignKey)
            ):
                display.append(name)

        return display

    def _generate_search_fields(self, opts) -> list[str]:
        """Generate search_fields."""
        search = []

        for field in opts.get_fields():
            if not hasattr(field, "name"):
                continue

            if len(search) >= self.search_fields_limit:
                break

            name = field.name
            if name in self.exclude_fields:
                continue

            if isinstance(field, (models.CharField, models.TextField, models.EmailField)):
                search.append(name)

        return search

    def _generate_list_filter(self, opts) -> list[str]:
        """Generate list_filter."""
        filters = []

        for field in opts.get_fields():
            if not hasattr(field, "name"):
                continue

            if len(filters) >= self.list_filter_limit:
                break

            name = field.name
            if name in self.exclude_fields:
                continue

            if (
                isinstance(field, models.BooleanField)
                or (hasattr(field, "choices") and field.choices)
                or isinstance(field, (models.DateField, models.DateTimeField))
                or isinstance(field, models.ForeignKey)
            ):
                filters.append(name)

        return filters

    def _generate_readonly_fields(self, opts) -> tuple[str, ...]:
        """Generate readonly_fields."""
        readonly = []

        for field_name in self.always_readonly:
            if self._has_field(opts, field_name):
                readonly.append(field_name)

        return tuple(readonly)

    def _generate_date_hierarchy(self, opts) -> str | None:
        """Generate date_hierarchy."""
        candidates = ["created_at", "created", "date", "timestamp"]

        for candidate in candidates:
            if self._has_field(opts, candidate):
                field = opts.get_field(candidate)
                if isinstance(field, (models.DateField, models.DateTimeField)):
                    return candidate

        return None

    def _generate_ordering(self, opts) -> list[str]:
        """Generate default ordering."""
        if self._has_field(opts, "created_at"):
            return ["-created_at"]
        if self._has_field(opts, "id"):
            return ["-id"]
        return []

    def _generate_fieldsets(self, opts) -> list[tuple] | None:
        """Generate fieldsets for complex models."""
        fields = []
        audit_fields = []
        other_fields = []

        audit_names = {"created_at", "updated_at", "created_by", "updated_by"}

        for field in opts.get_fields():
            if not hasattr(field, "name"):
                continue

            name = field.name
            if name in self.exclude_fields or name in self.always_readonly:
                continue

            # Skip reverse relations
            if field.is_relation and not isinstance(field, models.ForeignKey):
                continue

            if name in audit_names:
                audit_fields.append(name)
            else:
                other_fields.append(name)

        # Only create fieldsets if we have audit fields
        if audit_fields:
            fieldsets = [
                (None, {"fields": other_fields}),
                (
                    "Audit Information",
                    {
                        "classes": ("collapse",),
                        "fields": audit_fields,
                    },
                ),
            ]
            return fieldsets

        return None

    def _generate_inlines(self, opts) -> list[type]:
        """Generate inline classes for related models.

        Auto-generates TabularInline classes for models that have
        ForeignKey relationships pointing to the current model.
        Uses StackedInline when the related model has many fields (>6).
        """
        from django_matt.admin.base import MattStackedInline, MattTabularInline

        inlines = []
        for relation in opts.get_fields():
            # Only process reverse ForeignKey relations (one-to-many)
            if not (relation.one_to_many and hasattr(relation, "related_model")):
                continue

            related_model = relation.related_model
            if related_model is None:
                continue

            # Skip if the related model is the same as the current model
            if related_model == opts.model:
                continue

            # Count concrete fields to decide TabularInline vs StackedInline
            concrete_fields = [
                f
                for f in related_model._meta.get_fields()
                if hasattr(f, "column") and f.name not in self.exclude_fields
            ]

            # Use StackedInline for complex models, TabularInline for simple ones
            base_inline = MattStackedInline if len(concrete_fields) > 6 else MattTabularInline

            # Build inline class attributes
            inline_attrs = {
                "model": related_model,
                "extra": 0,
                "show_change_link": True,
            }

            # Generate readonly fields for the inline
            readonly = []
            for field_name in self.always_readonly:
                try:
                    related_model._meta.get_field(field_name)
                    readonly.append(field_name)
                except Exception:
                    continue
            if readonly:
                inline_attrs["readonly_fields"] = tuple(readonly)

            inline_class = type(
                f"{related_model.__name__}Inline",
                (base_inline,),
                inline_attrs,
            )
            inlines.append(inline_class)

        return inlines


def generate_admin_class(
    model: type[models.Model],
    base_class: type[admin.ModelAdmin] | None = None,
    **options,
) -> type[admin.ModelAdmin]:
    """
    Generate an admin class for a model.

    Args:
        model: Django model class
        base_class: Base admin class to inherit from
        **options: Additional options passed to AdminGenerator

    Returns:
        Generated admin class
    """
    generator = AdminGenerator(base_class=base_class, **options)
    return generator.generate(model)


def generate_admin_module(
    models: Sequence[type[models.Model]],
    include_imports: bool = True,
    include_audit: bool = True,
    include_soft_delete: bool = False,
    include_export: bool = True,
) -> str:
    """
    Generate Python code for an admin.py module.

    Args:
        models: List of Django model classes
        include_imports: Whether to include import statements
        include_audit: Include audit mixin
        include_soft_delete: Include soft delete mixin
        include_export: Include export mixin

    Returns:
        Python code as a string
    """
    lines = []

    if include_imports:
        lines.extend(
            [
                '"""',
                "Auto-generated admin configuration.",
                "",
                "Generated by django_matt.admin.generator",
                '"""',
                "",
                "from django.contrib import admin",
                "",
                "from django_matt.admin import (",
                "    MattModelAdmin,",
            ]
        )

        if include_audit:
            lines.append("    AuditAdminMixin,")
        if include_soft_delete:
            lines.append("    SoftDeleteAdminMixin,")
        if include_export:
            lines.append("    ExportAdminMixin,")

        lines.extend(
            [
                ")",
                "",
            ]
        )

        # Import models
        model_imports = {}
        for model in models:
            module = model.__module__
            name = model.__name__
            if module not in model_imports:
                model_imports[module] = []
            model_imports[module].append(name)

        for module, names in model_imports.items():
            names_str = ", ".join(sorted(names))
            lines.append(f"from {module} import {names_str}")

        lines.append("")
        lines.append("")

    # Generate admin classes
    generator = AdminGenerator(
        include_audit=include_audit,
        include_soft_delete=include_soft_delete,
        include_export=include_export,
    )

    for model in models:
        opts = model._meta
        model_name = model.__name__

        # Determine mixins
        mixins = []
        if include_audit:
            mixins.append("AuditAdminMixin")
        if include_soft_delete and generator._has_field(opts, "deleted_at"):
            mixins.append("SoftDeleteAdminMixin")
        if include_export:
            mixins.append("ExportAdminMixin")

        mixins_str = ", ".join(mixins + ["MattModelAdmin"])

        # Generate class
        lines.append(f"@admin.register({model_name})")
        lines.append(f"class {model_name}Admin({mixins_str}):")

        # list_display
        list_display = generator._generate_list_display(opts)
        lines.append(f"    list_display = {list_display!r}")

        # search_fields
        search_fields = generator._generate_search_fields(opts)
        if search_fields:
            lines.append(f"    search_fields = {search_fields!r}")

        # list_filter
        list_filter = generator._generate_list_filter(opts)
        if list_filter:
            lines.append(f"    list_filter = {list_filter!r}")

        # readonly_fields
        readonly = generator._generate_readonly_fields(opts)
        if readonly:
            lines.append(f"    readonly_fields = {readonly!r}")

        # date_hierarchy
        date_hierarchy = generator._generate_date_hierarchy(opts)
        if date_hierarchy:
            lines.append(f'    date_hierarchy = "{date_hierarchy}"')

        # ordering
        ordering = generator._generate_ordering(opts)
        if ordering:
            lines.append(f"    ordering = {ordering!r}")

        lines.append("")
        lines.append("")

    return "\n".join(lines)


__all__ = [
    "AdminGenerator",
    "generate_admin_class",
    "generate_admin_module",
]
