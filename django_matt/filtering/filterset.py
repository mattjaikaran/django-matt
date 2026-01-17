"""
FilterSet for declarative filter definitions.
"""

from typing import Any, Type

from django.db import models
from django.db.models import QuerySet
from django.http import HttpRequest

from .filters import (
    Filter,
    CharFilter,
    IntegerFilter,
    BooleanFilter,
    DateFilter,
    DateTimeFilter,
    UUIDFilter,
)


# Mapping of Django field types to filter classes
FILTER_FOR_DBFIELD = {
    models.CharField: CharFilter,
    models.TextField: CharFilter,
    models.EmailField: CharFilter,
    models.URLField: CharFilter,
    models.SlugField: CharFilter,
    models.IntegerField: IntegerFilter,
    models.SmallIntegerField: IntegerFilter,
    models.BigIntegerField: IntegerFilter,
    models.PositiveIntegerField: IntegerFilter,
    models.PositiveSmallIntegerField: IntegerFilter,
    models.PositiveBigIntegerField: IntegerFilter,
    models.AutoField: IntegerFilter,
    models.BigAutoField: IntegerFilter,
    models.BooleanField: BooleanFilter,
    models.NullBooleanField: BooleanFilter,
    models.DateField: DateFilter,
    models.DateTimeField: DateTimeFilter,
    models.UUIDField: UUIDFilter,
    models.FloatField: IntegerFilter,  # Use IntegerFilter, converts to float
    models.DecimalField: IntegerFilter,
}


class FilterSetOptions:
    """
    Options class for FilterSet Meta configuration.
    """

    def __init__(self, options: Type | None = None):
        self.model: Type[models.Model] | None = getattr(options, "model", None)
        self.fields: list[str] | str | None = getattr(options, "fields", None)
        self.exclude: list[str] = getattr(options, "exclude", [])


class FilterSetMeta(type):
    """
    Metaclass for FilterSet.

    Collects declared filters and auto-generates filters from model fields.
    """

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
        # Collect declared filters from class attributes
        declared_filters = {}
        for key, value in list(namespace.items()):
            if isinstance(value, Filter):
                declared_filters[key] = value
                value.name = key

        # Get filters from base classes
        for base in bases:
            if hasattr(base, "_declared_filters"):
                for key, value in base._declared_filters.items():
                    if key not in declared_filters:
                        declared_filters[key] = value

        namespace["_declared_filters"] = declared_filters

        cls = super().__new__(mcs, name, bases, namespace)

        # Process Meta options
        meta = getattr(cls, "Meta", None)
        cls._meta = FilterSetOptions(meta)

        # Auto-generate filters from model if Meta.fields is specified
        if cls._meta.model and cls._meta.fields:
            cls._filters = mcs._generate_filters(cls)
        else:
            cls._filters = dict(declared_filters)

        # Set parent reference on all filters
        for filter_instance in cls._filters.values():
            filter_instance.parent = None  # Will be set on instantiation

        return cls

    @staticmethod
    def _generate_filters(cls) -> dict[str, Filter]:
        """Generate filters from model fields based on Meta configuration."""
        filters = dict(cls._declared_filters)
        model = cls._meta.model
        fields = cls._meta.fields
        exclude = cls._meta.exclude

        if fields == "__all__":
            # Get all model fields
            model_fields = [f.name for f in model._meta.get_fields() if hasattr(f, "name")]
        elif isinstance(fields, (list, tuple)):
            model_fields = list(fields)
        else:
            model_fields = []

        # Remove excluded fields
        model_fields = [f for f in model_fields if f not in exclude]

        # Generate filters for model fields not already declared
        for field_name in model_fields:
            if field_name in filters:
                continue

            try:
                model_field = model._meta.get_field(field_name)
            except Exception:
                continue

            # Find appropriate filter class
            filter_class = None
            for db_field_class, filter_cls in FILTER_FOR_DBFIELD.items():
                if isinstance(model_field, db_field_class):
                    filter_class = filter_cls
                    break

            if filter_class:
                filter_instance = filter_class(field_name=field_name)
                filter_instance.name = field_name
                filters[field_name] = filter_instance

        return filters


class FilterSet(metaclass=FilterSetMeta):
    """
    Declarative filter set for Django models.

    Define filters as class attributes or auto-generate from model fields.

    Example:
        class UserFilter(FilterSet):
            email = CharFilter(lookup_expr='icontains')
            is_active = BooleanFilter()
            created_after = DateFilter(field_name='created_at', lookup_expr='gte')
            created_before = DateFilter(field_name='created_at', lookup_expr='lte')

            class Meta:
                model = User
                fields = ['email', 'is_active', 'role']

        # Usage
        filterset = UserFilter(request.GET, queryset=User.objects.all())
        filtered_queryset = filterset.qs

    Auto-generated filters:
        class UserFilter(FilterSet):
            class Meta:
                model = User
                fields = '__all__'  # or ['email', 'is_active', 'role']
                exclude = ['password', 'last_login']
    """

    _declared_filters: dict[str, Filter]
    _filters: dict[str, Filter]
    _meta: FilterSetOptions

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        queryset: QuerySet | None = None,
        request: HttpRequest | None = None,
    ):
        self.data = data or {}
        self.queryset = queryset
        self.request = request
        self._filtered_queryset: QuerySet | None = None

        # Set parent reference on filter instances
        for filter_instance in self._filters.values():
            filter_instance.parent = self

    @property
    def qs(self) -> QuerySet:
        """
        Get the filtered queryset.

        Applies all filters based on the provided data.
        """
        if self._filtered_queryset is not None:
            return self._filtered_queryset

        queryset = self.queryset
        if queryset is None:
            if self._meta.model:
                queryset = self._meta.model.objects.all()
            else:
                raise ValueError("No queryset or model provided to FilterSet")

        # Apply each filter
        for name, filter_instance in self._filters.items():
            # Get value from data
            value = self.data.get(name)

            # Skip if no value provided and filter is not required
            if value is None or value == "":
                if filter_instance.required:
                    raise ValueError(f"Filter '{name}' is required")
                continue

            # Apply the filter
            queryset = filter_instance.filter(queryset, value)

        self._filtered_queryset = queryset
        return queryset

    @property
    def filters(self) -> dict[str, Filter]:
        """Get all filter instances."""
        return self._filters

    def get_filter(self, name: str) -> Filter | None:
        """Get a specific filter by name."""
        return self._filters.get(name)

    @classmethod
    def get_filter_fields(cls) -> list[str]:
        """Get list of all filter field names."""
        return list(cls._filters.keys())

    @classmethod
    def get_schema_fields(cls) -> list[dict[str, Any]]:
        """Get OpenAPI schema fields for all filters."""
        fields = []
        for name, filter_instance in cls._filters.items():
            field_info = {
                "name": name,
                "in": "query",
                "required": filter_instance.required,
                "schema": {"type": "string"},
            }
            if filter_instance.label:
                field_info["description"] = filter_instance.label
            elif filter_instance.help_text:
                field_info["description"] = filter_instance.help_text
            fields.append(field_info)
        return fields

    def is_valid(self) -> bool:
        """
        Validate the filter data.

        Currently just checks required filters are present.
        """
        for name, filter_instance in self._filters.items():
            if filter_instance.required:
                value = self.data.get(name)
                if value is None or value == "":
                    return False
        return True

    @property
    def errors(self) -> dict[str, str]:
        """Get validation errors."""
        errors = {}
        for name, filter_instance in self._filters.items():
            if filter_instance.required:
                value = self.data.get(name)
                if value is None or value == "":
                    errors[name] = "This filter is required"
        return errors
