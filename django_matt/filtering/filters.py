"""
Filter classes for django-matt.

Individual filter types for building FilterSets.
"""

from datetime import date, datetime
from typing import Any, Callable, Sequence
from uuid import UUID

from django.db.models import QuerySet


class Filter:
    """
    Base filter class.

    A filter defines how a single query parameter maps to a queryset filter.

    Attributes:
        field_name: Model field to filter on (defaults to filter name)
        lookup_expr: Django ORM lookup expression (default: 'exact')
        required: Whether the filter is required
        method: Custom filter method name or callable
        exclude: If True, use exclude() instead of filter()

    Usage:
        class UserFilter(FilterSet):
            email = Filter(lookup_expr='icontains')
            is_active = BooleanFilter()
            created_after = DateFilter(field_name='created_at', lookup_expr='gte')

            class Meta:
                model = User
                fields = ['email', 'is_active']
    """

    creation_counter = 0

    def __init__(
        self,
        field_name: str | None = None,
        lookup_expr: str = "exact",
        *,
        required: bool = False,
        method: str | Callable | None = None,
        exclude: bool = False,
        label: str | None = None,
        help_text: str | None = None,
        distinct: bool = False,
    ):
        self.field_name = field_name
        self.lookup_expr = lookup_expr
        self.required = required
        self.method = method
        self.exclude = exclude
        self.label = label
        self.help_text = help_text
        self.distinct = distinct

        # Set by FilterSetMeta
        self.name: str | None = None
        self.parent: Any = None

        # For ordering filters in declaration order
        self.creation_counter = Filter.creation_counter
        Filter.creation_counter += 1

    def get_field_name(self) -> str:
        """Get the model field name to filter on."""
        return self.field_name or self.name or ""

    def get_lookup_expr(self) -> str:
        """Get the Django ORM lookup expression."""
        return self.lookup_expr

    def get_filter_lookup(self) -> str:
        """Get the full filter lookup string (field__lookup)."""
        field = self.get_field_name()
        lookup = self.get_lookup_expr()
        if lookup and lookup != "exact":
            return f"{field}__{lookup}"
        return field

    def convert_value(self, value: Any) -> Any:
        """
        Convert the raw query parameter value to the appropriate type.
        Override in subclasses for type-specific conversion.
        """
        return value

    def filter(self, queryset: QuerySet, value: Any) -> QuerySet:
        """
        Apply this filter to the queryset.

        Args:
            queryset: Django queryset
            value: Filter value from request

        Returns:
            Filtered queryset
        """
        if value is None or value == "":
            return queryset

        # Convert value to appropriate type
        try:
            value = self.convert_value(value)
        except (ValueError, TypeError):
            return queryset

        # Use custom method if specified
        if self.method:
            if callable(self.method):
                return self.method(queryset, self.get_field_name(), value)
            elif self.parent and hasattr(self.parent, self.method):
                method = getattr(self.parent, self.method)
                return method(queryset, self.get_field_name(), value)
            return queryset

        # Build filter kwargs
        lookup = self.get_filter_lookup()
        filter_kwargs = {lookup: value}

        if self.exclude:
            queryset = queryset.exclude(**filter_kwargs)
        else:
            queryset = queryset.filter(**filter_kwargs)

        if self.distinct:
            queryset = queryset.distinct()

        return queryset


class CharFilter(Filter):
    """Filter for character/text fields."""

    def __init__(self, **kwargs):
        kwargs.setdefault("lookup_expr", "icontains")
        super().__init__(**kwargs)

    def convert_value(self, value: Any) -> str:
        return str(value)


class IntegerFilter(Filter):
    """Filter for integer fields."""

    def convert_value(self, value: Any) -> int:
        return int(value)


class BooleanFilter(Filter):
    """Filter for boolean fields."""

    TRUE_VALUES = {"true", "1", "yes", "on", "t", "y"}
    FALSE_VALUES = {"false", "0", "no", "off", "f", "n"}

    def convert_value(self, value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lower = value.lower()
            if lower in self.TRUE_VALUES:
                return True
            if lower in self.FALSE_VALUES:
                return False
        return None


class DateFilter(Filter):
    """Filter for date fields."""

    def convert_value(self, value: Any) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise ValueError(f"Cannot convert {value} to date")


class DateTimeFilter(Filter):
    """Filter for datetime fields."""

    def convert_value(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError(f"Cannot convert {value} to datetime")


class UUIDFilter(Filter):
    """Filter for UUID fields."""

    def convert_value(self, value: Any) -> UUID:
        if isinstance(value, UUID):
            return value
        return UUID(str(value))


class ChoiceFilter(Filter):
    """Filter for fields with a fixed set of choices."""

    def __init__(self, choices: Sequence[tuple[Any, str]] | None = None, **kwargs):
        super().__init__(**kwargs)
        self.choices = choices or []

    def convert_value(self, value: Any) -> Any:
        if self.choices:
            valid_values = [choice[0] for choice in self.choices]
            if value not in valid_values:
                raise ValueError(f"Invalid choice: {value}")
        return value


class MultipleChoiceFilter(Filter):
    """Filter for multiple values (IN query)."""

    def __init__(self, choices: Sequence[tuple[Any, str]] | None = None, **kwargs):
        kwargs.setdefault("lookup_expr", "in")
        super().__init__(**kwargs)
        self.choices = choices or []

    def convert_value(self, value: Any) -> list:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",")]
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]


class InFilter(Filter):
    """Filter for IN queries with comma-separated values."""

    def __init__(self, **kwargs):
        kwargs.setdefault("lookup_expr", "in")
        super().__init__(**kwargs)

    def convert_value(self, value: Any) -> list:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",")]
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]


class RangeFilter(Filter):
    """
    Base class for range filters.

    Handles min/max query parameters for a single field.
    """

    def __init__(
        self,
        min_param: str | None = None,
        max_param: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.min_param = min_param
        self.max_param = max_param

    def filter(self, queryset: QuerySet, value: Any) -> QuerySet:
        """Range filter expects a dict with 'min' and/or 'max' keys."""
        if not isinstance(value, dict):
            return super().filter(queryset, value)

        field = self.get_field_name()
        min_val = value.get("min")
        max_val = value.get("max")

        if min_val is not None:
            try:
                min_val = self.convert_value(min_val)
                queryset = queryset.filter(**{f"{field}__gte": min_val})
            except (ValueError, TypeError):
                pass

        if max_val is not None:
            try:
                max_val = self.convert_value(max_val)
                queryset = queryset.filter(**{f"{field}__lte": max_val})
            except (ValueError, TypeError):
                pass

        return queryset


class NumberRangeFilter(RangeFilter):
    """Range filter for numeric fields."""

    def convert_value(self, value: Any) -> float:
        return float(value)


class DateRangeFilter(RangeFilter):
    """Range filter for date fields."""

    def convert_value(self, value: Any) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))


class ModelChoiceFilter(Filter):
    """Filter for foreign key fields."""

    def __init__(self, queryset: QuerySet | None = None, **kwargs):
        super().__init__(**kwargs)
        self.queryset = queryset

    def convert_value(self, value: Any) -> int:
        # Assume FK uses integer IDs
        return int(value)
