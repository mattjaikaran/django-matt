# file-length-max: 500
"""
Filter backends for django-matt.

Pluggable backends for filtering, searching, and ordering querysets.
"""

from typing import Any

from django.db.models import Q, QuerySet
from django.http import HttpRequest

from .base import BaseFilterBackend
from .filterset import FilterSet


class DjangoFilterBackend(BaseFilterBackend):
    """
    Filter backend using Django ORM lookups.

    Supports two modes:
    1. FilterSet class: Declarative filter definitions
    2. Auto-filter: Automatically filter based on query params and model fields

    Usage with FilterSet:
        class UserFilter(FilterSet):
            email = CharFilter(lookup_expr='icontains')
            class Meta:
                model = User
                fields = ['email', 'is_active']

        class UserListView:
            filterset_class = UserFilter
            filter_backends = [DjangoFilterBackend()]

    Usage with auto-filter:
        class UserListView:
            filter_fields = ['email', 'is_active', 'role']
            filter_backends = [DjangoFilterBackend()]

    Query parameters support Django ORM lookups:
        ?email__icontains=test
        ?created_at__gte=2024-01-01
        ?role__in=admin,user
    """

    # Reserved query params that should not be treated as filters
    RESERVED_PARAMS = {
        "page",
        "page_size",
        "limit",
        "offset",
        "cursor",
        "ordering",
        "order_by",
        "search",
        "q",
        "format",
        "fields",
    }

    def get_filterset_class(self, view: Any) -> type[FilterSet] | None:
        """Get the FilterSet class from the view."""
        return getattr(view, "filterset_class", None)

    def get_filter_fields(self, view: Any) -> list[str] | None:
        """Get the list of allowed filter fields from the view."""
        return getattr(view, "filter_fields", None)

    def filter_queryset(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        view: Any = None,
    ) -> QuerySet:
        """
        Filter the queryset based on request parameters.
        """
        # Try FilterSet first
        filterset_class = self.get_filterset_class(view)
        if filterset_class:
            filterset = filterset_class(
                data=dict(request.GET),
                queryset=queryset,
                request=request,
            )
            return filterset.qs

        # Fall back to auto-filtering
        filter_fields = self.get_filter_fields(view)
        return self._auto_filter(request, queryset, filter_fields)

    def _auto_filter(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        allowed_fields: list[str] | None = None,
    ) -> QuerySet:
        """
        Automatically filter based on query parameters.

        When a Rust-parsed query is available on ``request._parsed_qs``, uses
        the pre-parsed ``filters`` and ``extras`` dicts instead of
        re-iterating ``request.GET``.

        Supports Django ORM lookup syntax:
            ?field=value (exact match)
            ?field__icontains=value (case-insensitive contains)
            ?field__gte=value (greater than or equal)
            etc.
        """
        # Get model fields if no allowed fields specified
        if allowed_fields is None:
            try:
                model = queryset.model
                allowed_fields = [f.name for f in model._meta.get_fields() if hasattr(f, "name")]
            except Exception:
                allowed_fields = []

        parsed_qs = getattr(request, "_parsed_qs", None)
        if parsed_qs is not None:
            # Use Rust-parsed params: filter[field]=value → filters dict,
            # field=value → extras dict
            items: list[tuple[str, str]] = []
            for key, value in parsed_qs.get("filters", {}).items():
                items.append((key, value))
            for key, value in parsed_qs.get("extras", {}).items():
                if key not in self.RESERVED_PARAMS:
                    items.append((key, value))
        else:
            items = [(k, v) for k, v in request.GET.items()]

        # Process query parameters
        for param, value in items:
            # Skip reserved params (only needed for non-Rust path)
            if parsed_qs is None and param in self.RESERVED_PARAMS:
                continue

            # Skip empty values
            if not value:
                continue

            # Parse field name and lookup
            parts = param.split("__")
            field_name = parts[0]

            # Check if field is allowed
            if field_name not in allowed_fields:
                continue

            # Build filter kwargs
            try:
                # Handle special lookups
                if param.endswith("__in"):
                    # Split comma-separated values
                    value = [v.strip() for v in value.split(",")]

                queryset = queryset.filter(**{param: value})
            except Exception:
                # Invalid filter, skip it
                continue

        return queryset

    def get_schema_fields(self, view: Any = None) -> list[dict[str, Any]]:
        """Get OpenAPI schema fields for filtering."""
        fields = []

        # If using FilterSet, get fields from it
        filterset_class = self.get_filterset_class(view)
        if filterset_class:
            return filterset_class.get_schema_fields()

        # Otherwise, document allowed filter fields
        filter_fields = self.get_filter_fields(view) or []
        for field in filter_fields:
            fields.append(
                {
                    "name": field,
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": f"Filter by {field}",
                }
            )

        return fields


class SearchBackend(BaseFilterBackend):
    """
    Search backend for full-text search across multiple fields.

    Searches across configured fields using case-insensitive contains.

    Usage:
        class UserListView:
            search_fields = ['email', 'first_name', 'last_name', 'bio']
            filter_backends = [SearchBackend()]

        # Query
        GET /api/users?search=john

    Configuration:
        search_param: Query parameter name (default: 'search')
        search_fields: List of fields to search (set on view)

    Advanced search with field prefixes:
        search_fields = [
            'email',           # icontains
            '^first_name',     # istartswith
            '=username',       # iexact
            '@bio',            # Full-text search (PostgreSQL)
        ]
    """

    search_param: str = "search"
    search_fields_attr: str = "search_fields"

    def __init__(self, search_param: str | None = None):
        if search_param:
            self.search_param = search_param

    def get_search_fields(self, view: Any) -> list[str]:
        """Get search fields from view."""
        return getattr(view, self.search_fields_attr, [])

    def get_search_terms(self, request: HttpRequest) -> list[str]:
        """
        Get search terms from request.

        Uses Rust-parsed ``extras`` when available on ``request._parsed_qs``,
        falling back to ``request.GET``.

        Splits on whitespace for multi-term search.
        """
        parsed_qs = getattr(request, "_parsed_qs", None)
        if parsed_qs is not None:
            extras = parsed_qs.get("extras", {})
            search = extras.get(self.search_param, "")
        else:
            search = request.GET.get(self.search_param, "")
        search = search.strip()
        if not search:
            return []
        return search.split()

    def filter_queryset(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        view: Any = None,
    ) -> QuerySet:
        """
        Apply search filter to queryset.
        """
        search_fields = self.get_search_fields(view)
        search_terms = self.get_search_terms(request)

        if not search_fields or not search_terms:
            return queryset

        # Build search query
        # All terms must match (AND), any field can match (OR)
        for term in search_terms:
            term_query = Q()
            for field in search_fields:
                lookup = self._get_lookup(field)
                field_name = self._get_field_name(field)
                term_query |= Q(**{lookup: term})
            queryset = queryset.filter(term_query)

        return queryset.distinct()

    def _get_field_name(self, field: str) -> str:
        """Extract field name, removing any prefix."""
        if field.startswith(("^", "=", "@", "$")):
            return field[1:]
        return field

    def _get_lookup(self, field: str) -> str:
        """Get the lookup expression for a search field."""
        field_name = self._get_field_name(field)

        if field.startswith("^"):
            # Start of string
            return f"{field_name}__istartswith"
        if field.startswith("="):
            # Exact match
            return f"{field_name}__iexact"
        if field.startswith("@"):
            # Full-text search (PostgreSQL)
            return f"{field_name}__search"
        if field.startswith("$"):
            # Regex
            return f"{field_name}__iregex"
        # Default: case-insensitive contains
        return f"{field_name}__icontains"

    def get_schema_fields(self, view: Any = None) -> list[dict[str, Any]]:
        """Get OpenAPI schema for search parameter."""
        search_fields = self.get_search_fields(view) if view else []
        description = "Search query"
        if search_fields:
            field_names = [self._get_field_name(f) for f in search_fields]
            description = f"Search across: {', '.join(field_names)}"

        return [
            {
                "name": self.search_param,
                "in": "query",
                "required": False,
                "schema": {"type": "string"},
                "description": description,
            }
        ]


class OrderingBackend(BaseFilterBackend):
    """
    Ordering backend for sorting querysets.

    Usage:
        class UserListView:
            ordering_fields = ['email', 'created_at', 'last_name']
            ordering = '-created_at'  # Default ordering
            filter_backends = [OrderingBackend()]

        # Query
        GET /api/users?ordering=-created_at,email

    Configuration:
        ordering_param: Query parameter name (default: 'ordering')
        ordering_fields: Allowed fields for ordering (set on view)
        ordering: Default ordering (set on view)
    """

    ordering_param: str = "ordering"
    ordering_fields_attr: str = "ordering_fields"
    default_ordering_attr: str = "ordering"

    def __init__(self, ordering_param: str | None = None):
        if ordering_param:
            self.ordering_param = ordering_param

    def get_ordering_fields(self, view: Any) -> list[str] | None:
        """Get allowed ordering fields from view."""
        return getattr(view, self.ordering_fields_attr, None)

    def get_default_ordering(self, view: Any) -> str | list[str] | None:
        """Get default ordering from view."""
        return getattr(view, self.default_ordering_attr, None)

    def _get_model_ordering(self, queryset: QuerySet) -> list[str]:
        """Extract default ordering from model Meta.ordering."""
        try:
            model = queryset.model
            meta_ordering = getattr(model._meta, "ordering", None)
            if meta_ordering:
                return list(meta_ordering)
        except Exception:
            pass
        return []

    def _is_valid_ordering_field(self, field_name: str, allowed_fields: list[str]) -> bool:
        """Check if a field is valid for ordering.

        Supports relation traversal (e.g. ``author__name``) when the
        base field or the full dotted path is listed in *allowed_fields*,
        or when ``allowed_fields`` contains ``"__all__"``.
        """
        if "__all__" in allowed_fields:
            return True
        # Exact match (covers both simple fields and explicit traversals)
        if field_name in allowed_fields:
            return True
        # Allow traversal when the root field is listed
        if "__" in field_name:
            root = field_name.split("__")[0]
            if root in allowed_fields:
                return True
        return False

    def get_ordering(
        self,
        request: HttpRequest,
        view: Any,
        queryset: QuerySet | None = None,
    ) -> list[str]:
        """
        Get ordering from request or default.

        Falls back to the view's ``ordering`` attribute, then to the model's
        ``Meta.ordering`` when no explicit ``?ordering=`` parameter is provided.

        Returns list of ordering fields (with optional - prefix for descending).
        """
        # Try Rust-parsed sort tuples first, then fall back to request.GET
        ordering: list[str] = []
        parsed_qs = getattr(request, "_parsed_qs", None)
        if parsed_qs is not None:
            sort_tuples = parsed_qs.get("sort", [])
            if sort_tuples:
                ordering = [
                    f"-{field}" if not ascending else field for field, ascending in sort_tuples
                ]
        else:
            ordering_str = request.GET.get(self.ordering_param, "")
            if ordering_str:
                ordering = [f.strip() for f in ordering_str.split(",") if f.strip()]

        if not ordering:
            # Use view default
            default = self.get_default_ordering(view)
            if isinstance(default, str):
                ordering = [default]
            elif isinstance(default, (list, tuple)):
                ordering = list(default)
            else:
                ordering = []

            # Fall back to model Meta.ordering
            if not ordering and queryset is not None:
                ordering = self._get_model_ordering(queryset)

        # Validate against allowed fields
        allowed_fields = self.get_ordering_fields(view)
        if allowed_fields is not None:
            validated = []
            for field in ordering:
                # Remove - prefix for validation
                field_name = field.lstrip("-")
                if self._is_valid_ordering_field(field_name, allowed_fields):
                    validated.append(field)
            ordering = validated

        return ordering

    def filter_queryset(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        view: Any = None,
    ) -> QuerySet:
        """
        Apply ordering to queryset.
        """
        ordering = self.get_ordering(request, view, queryset)

        if ordering:
            queryset = queryset.order_by(*ordering)

        return queryset

    def get_schema_fields(self, view: Any = None) -> list[dict[str, Any]]:
        """Get OpenAPI schema for ordering parameter.

        When ``ordering_fields`` is set (and is not ``["__all__"]``),
        emits an ``enum`` on the schema so TypeScript codegen can
        produce a union type for allowed values.
        """
        ordering_fields = self.get_ordering_fields(view) if view else []
        description = "Order by field (prefix with - for descending)"

        schema: dict[str, Any] = {"type": "string"}

        if ordering_fields and ordering_fields != ["__all__"]:
            description = f"Order by: {', '.join(ordering_fields)} (prefix with - for descending)"
            # Build enum: each field + its descending variant
            enum_values: list[str] = []
            for field in ordering_fields:
                enum_values.append(field)
                enum_values.append(f"-{field}")
            schema["enum"] = enum_values

        return [
            {
                "name": self.ordering_param,
                "in": "query",
                "required": False,
                "schema": schema,
                "description": description,
            }
        ]
