"""
Custom admin filters for enhanced filtering capabilities.

Compatible with Django Unfold's filter styling.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.contrib import admin
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from django.http import HttpRequest


class DateRangeFilter(admin.SimpleListFilter):
    """
    Filter by date ranges (today, this week, this month, etc.).

    Usage:
        class MyAdmin(MattModelAdmin):
            list_filter = [
                ('created_at', DateRangeFilter),
            ]
    """

    title = "date range"
    parameter_name = "date_range"

    # Field to filter on (set by subclass or dynamically)
    field_name: str = "created_at"

    def lookups(self, request: HttpRequest, model_admin):
        return [
            ("today", "Today"),
            ("yesterday", "Yesterday"),
            ("this_week", "This week"),
            ("last_week", "Last week"),
            ("this_month", "This month"),
            ("last_month", "Last month"),
            ("this_year", "This year"),
            ("last_7_days", "Last 7 days"),
            ("last_30_days", "Last 30 days"),
            ("last_90_days", "Last 90 days"),
        ]

    def queryset(self, request: HttpRequest, queryset):
        if not self.value():
            return queryset

        today = timezone.now().date()
        value = self.value()

        if value == "today":
            return queryset.filter(**{f"{self.field_name}__date": today})

        if value == "yesterday":
            yesterday = today - timedelta(days=1)
            return queryset.filter(**{f"{self.field_name}__date": yesterday})

        if value == "this_week":
            start = today - timedelta(days=today.weekday())
            return queryset.filter(**{f"{self.field_name}__date__gte": start})

        if value == "last_week":
            start = today - timedelta(days=today.weekday() + 7)
            end = start + timedelta(days=6)
            return queryset.filter(
                **{
                    f"{self.field_name}__date__gte": start,
                    f"{self.field_name}__date__lte": end,
                }
            )

        if value == "this_month":
            return queryset.filter(
                **{
                    f"{self.field_name}__year": today.year,
                    f"{self.field_name}__month": today.month,
                }
            )

        if value == "last_month":
            if today.month == 1:
                year, month = today.year - 1, 12
            else:
                year, month = today.year, today.month - 1
            return queryset.filter(
                **{
                    f"{self.field_name}__year": year,
                    f"{self.field_name}__month": month,
                }
            )

        if value == "this_year":
            return queryset.filter(**{f"{self.field_name}__year": today.year})

        if value == "last_7_days":
            start = today - timedelta(days=7)
            return queryset.filter(**{f"{self.field_name}__date__gte": start})

        if value == "last_30_days":
            start = today - timedelta(days=30)
            return queryset.filter(**{f"{self.field_name}__date__gte": start})

        if value == "last_90_days":
            start = today - timedelta(days=90)
            return queryset.filter(**{f"{self.field_name}__date__gte": start})

        return queryset


def create_date_range_filter(field_name: str, title: str | None = None):
    """
    Factory to create a DateRangeFilter for a specific field.

    Usage:
        class MyAdmin(MattModelAdmin):
            list_filter = [
                create_date_range_filter('created_at', 'Created'),
                create_date_range_filter('updated_at', 'Updated'),
            ]
    """

    class FieldDateRangeFilter(DateRangeFilter):
        pass

    FieldDateRangeFilter.field_name = field_name
    FieldDateRangeFilter.title = title or field_name.replace("_", " ")
    FieldDateRangeFilter.parameter_name = f"{field_name}_range"

    return FieldDateRangeFilter


class BooleanFilter(admin.SimpleListFilter):
    """
    Enhanced boolean filter with Yes/No/All options.

    Usage:
        class MyAdmin(MattModelAdmin):
            list_filter = [
                ('is_active', BooleanFilter),
            ]
    """

    title = "status"
    parameter_name = "status"
    field_name: str = "is_active"

    def lookups(self, request: HttpRequest, model_admin):
        return [
            ("yes", "Yes"),
            ("no", "No"),
        ]

    def queryset(self, request: HttpRequest, queryset):
        if self.value() == "yes":
            return queryset.filter(**{self.field_name: True})
        if self.value() == "no":
            return queryset.filter(**{self.field_name: False})
        return queryset


def create_boolean_filter(
    field_name: str,
    title: str | None = None,
    true_label: str = "Yes",
    false_label: str = "No",
):
    """
    Factory to create a BooleanFilter for a specific field.

    Usage:
        class MyAdmin(MattModelAdmin):
            list_filter = [
                create_boolean_filter('is_active', 'Active', 'Active', 'Inactive'),
                create_boolean_filter('is_verified', 'Verified'),
            ]
    """

    class FieldBooleanFilter(BooleanFilter):
        def lookups(self, request, model_admin):
            return [
                ("yes", true_label),
                ("no", false_label),
            ]

    FieldBooleanFilter.field_name = field_name
    FieldBooleanFilter.title = title or field_name.replace("_", " ")
    FieldBooleanFilter.parameter_name = field_name

    return FieldBooleanFilter


class ChoicesFilter(admin.SimpleListFilter):
    """
    Filter for choice fields with dynamic choices.

    Usage:
        class MyAdmin(MattModelAdmin):
            list_filter = [
                ('status', ChoicesFilter),
            ]
    """

    title = "status"
    parameter_name = "status"
    field_name: str = "status"

    def lookups(self, request: HttpRequest, model_admin):
        # Get choices from model field
        try:
            field = model_admin.model._meta.get_field(self.field_name)
            if hasattr(field, "choices") and field.choices:
                return field.choices
        except Exception:
            pass
        return []

    def queryset(self, request: HttpRequest, queryset):
        if self.value():
            return queryset.filter(**{self.field_name: self.value()})
        return queryset


def create_choices_filter(field_name: str, title: str | None = None):
    """
    Factory to create a ChoicesFilter for a specific field.
    """

    class FieldChoicesFilter(ChoicesFilter):
        pass

    FieldChoicesFilter.field_name = field_name
    FieldChoicesFilter.title = title or field_name.replace("_", " ")
    FieldChoicesFilter.parameter_name = field_name

    return FieldChoicesFilter


class RelatedFilter(admin.SimpleListFilter):
    """
    Filter by related model with optimized queryset.

    Usage:
        class MyAdmin(MattModelAdmin):
            list_filter = [
                ('author', RelatedFilter),
            ]
    """

    title = "related"
    parameter_name = "related"
    field_name: str = "author"

    # Limit number of choices shown
    max_choices: int = 50

    # Field to display for choices
    display_field: str = "__str__"

    def lookups(self, request: HttpRequest, model_admin):
        try:
            field = model_admin.model._meta.get_field(self.field_name)
            if isinstance(field, models.ForeignKey):
                related_model = field.related_model
                qs = related_model.objects.all()[: self.max_choices]

                choices = []
                for obj in qs:
                    if self.display_field == "__str__":
                        label = str(obj)
                    else:
                        label = getattr(obj, self.display_field, str(obj))
                    choices.append((str(obj.pk), label))

                return choices
        except Exception:
            pass
        return []

    def queryset(self, request: HttpRequest, queryset):
        if self.value():
            return queryset.filter(**{f"{self.field_name}_id": self.value()})
        return queryset


def create_related_filter(
    field_name: str,
    title: str | None = None,
    max_choices: int = 50,
    display_field: str = "__str__",
):
    """
    Factory to create a RelatedFilter for a specific field.
    """

    class FieldRelatedFilter(RelatedFilter):
        pass

    FieldRelatedFilter.field_name = field_name
    FieldRelatedFilter.title = title or field_name.replace("_", " ")
    FieldRelatedFilter.parameter_name = field_name
    FieldRelatedFilter.max_choices = max_choices
    FieldRelatedFilter.display_field = display_field

    return FieldRelatedFilter


class TenantFilter(admin.SimpleListFilter):
    """
    Filter by tenant/organization for multi-tenant admins.

    Shows only tenants the user has access to.

    Usage:
        class MyAdmin(MattModelAdmin):
            list_filter = [TenantFilter]
    """

    title = "organization"
    parameter_name = "organization"
    field_name: str = "organization"

    def lookups(self, request: HttpRequest, model_admin):
        user = request.user

        # Get user's organizations
        orgs = []

        if hasattr(user, "organizations"):
            orgs = user.organizations.all()
        elif hasattr(user, "memberships"):
            orgs = [m.organization for m in user.memberships.all()]
        elif hasattr(user, "organization"):
            if user.organization:
                orgs = [user.organization]

        return [(str(org.pk), str(org)) for org in orgs]

    def queryset(self, request: HttpRequest, queryset):
        if self.value():
            return queryset.filter(**{f"{self.field_name}_id": self.value()})
        return queryset


class NullFilter(admin.SimpleListFilter):
    """
    Filter for null/not null values.

    Usage:
        class MyAdmin(MattModelAdmin):
            list_filter = [
                ('deleted_at', NullFilter),
            ]
    """

    title = "has value"
    parameter_name = "has_value"
    field_name: str = "deleted_at"

    def lookups(self, request: HttpRequest, model_admin):
        return [
            ("yes", "Has value"),
            ("no", "Is empty"),
        ]

    def queryset(self, request: HttpRequest, queryset):
        if self.value() == "yes":
            return queryset.exclude(**{f"{self.field_name}__isnull": True})
        if self.value() == "no":
            return queryset.filter(**{f"{self.field_name}__isnull": True})
        return queryset


def create_null_filter(
    field_name: str,
    title: str | None = None,
    has_label: str = "Has value",
    empty_label: str = "Is empty",
):
    """
    Factory to create a NullFilter for a specific field.
    """

    class FieldNullFilter(NullFilter):
        def lookups(self, request, model_admin):
            return [
                ("yes", has_label),
                ("no", empty_label),
            ]

    FieldNullFilter.field_name = field_name
    FieldNullFilter.title = title or field_name.replace("_", " ")
    FieldNullFilter.parameter_name = f"{field_name}_null"

    return FieldNullFilter


__all__ = [
    "DateRangeFilter",
    "create_date_range_filter",
    "BooleanFilter",
    "create_boolean_filter",
    "ChoicesFilter",
    "create_choices_filter",
    "RelatedFilter",
    "create_related_filter",
    "TenantFilter",
    "NullFilter",
    "create_null_filter",
]
