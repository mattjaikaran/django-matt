"""
GraphQL query resolvers for Django Matt.

Provides utilities for generating query resolvers from Django models.
"""

from __future__ import annotations

from typing import Any, TypeVar

from django.db import models
from django.db.models import QuerySet

try:
    import strawberry
    from strawberry import UNSET
    from strawberry.types import Info

    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False
    UNSET = None
    Info = Any


T = TypeVar("T")


def _require_strawberry():
    """Raise an error if strawberry is not installed."""
    if not STRAWBERRY_AVAILABLE:
        raise ImportError(
            "strawberry-graphql is required for GraphQL queries. "
            "Install it with: pip install strawberry-graphql[django]"
        )


class QueryGenerator:
    """
    Generate GraphQL queries for a Django model.

    Usage:
        generator = QueryGenerator(User, UserType)

        @strawberry.type
        class Query:
            users = generator.list_query()
            user = generator.detail_query()
            users_connection = generator.connection_query()
    """

    def __init__(
        self,
        model: type[models.Model],
        type_class: type,
        input_class: type | None = None,
        filter_class: type | None = None,
        connection_class: type | None = None,
    ):
        """
        Initialize the query generator.

        Args:
            model: Django model class
            type_class: Strawberry type class for the model
            input_class: Optional input type class
            filter_class: Optional filter input class
            connection_class: Optional connection type class
        """
        _require_strawberry()
        self.model = model
        self.type_class = type_class
        self.input_class = input_class
        self.filter_class = filter_class
        self.connection_class = connection_class

    def list_query(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        filterable: bool = True,
        orderable: bool = True,
        paginated: bool = True,
        default_limit: int = 100,
        max_limit: int = 1000,
    ) -> strawberry.field:
        """
        Generate a list query resolver.

        Args:
            name: Query field name
            description: Query description
            permission_classes: Permission classes to apply
            filterable: Enable filtering
            orderable: Enable ordering
            paginated: Enable pagination
            default_limit: Default number of items
            max_limit: Maximum number of items

        Returns:
            Strawberry field descriptor
        """
        _require_strawberry()
        model = self.model
        type_class = self.type_class

        async def resolver(
            info: Info,
            filter: Any | None = UNSET,
            order_by: list[str] | None = None,
            limit: int | None = None,
            offset: int | None = None,
        ) -> list:
            queryset = model.objects.all()

            # Apply filters
            if filterable and filter is not UNSET and filter is not None:
                queryset = apply_filters(queryset, filter)

            # Apply ordering
            if orderable and order_by:
                queryset = queryset.order_by(*order_by)

            # Apply pagination
            if paginated:
                actual_limit = min(limit or default_limit, max_limit)
                actual_offset = offset or 0
                queryset = queryset[actual_offset : actual_offset + actual_limit]

            # Convert to type
            results = []
            async for obj in queryset:
                if hasattr(type_class, "from_orm"):
                    results.append(type_class.from_orm(obj))
                else:
                    results.append(obj)
            return results

        # Sync version for non-async contexts
        def sync_resolver(
            info: Info,
            filter: Any | None = UNSET,
            order_by: list[str] | None = None,
            limit: int | None = None,
            offset: int | None = None,
        ) -> list:
            queryset = model.objects.all()

            # Apply filters
            if filterable and filter is not UNSET and filter is not None:
                queryset = apply_filters(queryset, filter)

            # Apply ordering
            if orderable and order_by:
                queryset = queryset.order_by(*order_by)

            # Apply pagination
            if paginated:
                actual_limit = min(limit or default_limit, max_limit)
                actual_offset = offset or 0
                queryset = queryset[actual_offset : actual_offset + actual_limit]

            # Convert to type
            results = []
            for obj in queryset:
                if hasattr(type_class, "from_orm"):
                    results.append(type_class.from_orm(obj))
                else:
                    results.append(obj)
            return results

        return strawberry.field(
            resolver=sync_resolver,
            name=name,
            description=description or f"List all {model.__name__} objects",
            permission_classes=permission_classes or [],
        )

    def detail_query(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        lookup_field: str = "id",
    ) -> strawberry.field:
        """
        Generate a detail query resolver.

        Args:
            name: Query field name
            description: Query description
            permission_classes: Permission classes to apply
            lookup_field: Field to look up by (default: "id")

        Returns:
            Strawberry field descriptor
        """
        _require_strawberry()
        model = self.model
        type_class = self.type_class

        def resolver(
            info: Info,
            id: strawberry.ID,
        ):
            try:
                obj = model.objects.get(**{lookup_field: id})
                if hasattr(type_class, "from_orm"):
                    return type_class.from_orm(obj)
                return obj
            except model.DoesNotExist:
                return None

        return strawberry.field(
            resolver=resolver,
            name=name,
            description=description or f"Get a single {model.__name__} by ID",
            permission_classes=permission_classes or [],
        )

    def connection_query(
        self,
        name: str | None = None,
        description: str | None = None,
        permission_classes: list | None = None,
        filterable: bool = True,
        orderable: bool = True,
    ) -> strawberry.field:
        """
        Generate a Relay-style connection query resolver.

        Args:
            name: Query field name
            description: Query description
            permission_classes: Permission classes to apply
            filterable: Enable filtering
            orderable: Enable ordering

        Returns:
            Strawberry field descriptor
        """
        _require_strawberry()
        from django_matt.graphql.types import ConnectionType

        model = self.model
        type_class = self.type_class
        connection_class = self.connection_class or ConnectionType[type_class]

        def resolver(
            info: Info,
            first: int | None = None,
            after: str | None = None,
            last: int | None = None,
            before: str | None = None,
            filter: Any | None = UNSET,
            order_by: list[str] | None = None,
        ):
            queryset = model.objects.all()

            # Apply filters
            if filterable and filter is not UNSET and filter is not None:
                queryset = apply_filters(queryset, filter)

            # Apply ordering
            if orderable and order_by:
                queryset = queryset.order_by(*order_by)

            return ConnectionType.from_queryset(
                queryset,
                type_class,
                first=first,
                after=after,
                last=last,
                before=before,
            )

        return strawberry.field(
            resolver=resolver,
            name=name,
            description=description or f"Paginated list of {model.__name__} objects",
            permission_classes=permission_classes or [],
        )


def apply_filters(queryset: QuerySet, filter_input: Any) -> QuerySet:
    """
    Apply filter input to a queryset.

    Args:
        queryset: Django queryset
        filter_input: Filter input object

    Returns:
        Filtered queryset
    """
    if filter_input is None:
        return queryset

    filter_dict = {}

    # Get all filter fields from the input
    for field_name, value in vars(filter_input).items():
        if value is UNSET or value is None:
            continue

        # Skip AND/OR combinators for now
        if field_name in ("AND", "OR"):
            continue

        # Map filter suffixes to Django lookups
        if field_name.endswith("_contains"):
            base_field = field_name.replace("_contains", "")
            filter_dict[f"{base_field}__contains"] = value
        elif field_name.endswith("_icontains"):
            base_field = field_name.replace("_icontains", "")
            filter_dict[f"{base_field}__icontains"] = value
        elif field_name.endswith("_startswith"):
            base_field = field_name.replace("_startswith", "")
            filter_dict[f"{base_field}__startswith"] = value
        elif field_name.endswith("_endswith"):
            base_field = field_name.replace("_endswith", "")
            filter_dict[f"{base_field}__endswith"] = value
        elif field_name.endswith("_gt"):
            base_field = field_name.replace("_gt", "")
            filter_dict[f"{base_field}__gt"] = value
        elif field_name.endswith("_gte"):
            base_field = field_name.replace("_gte", "")
            filter_dict[f"{base_field}__gte"] = value
        elif field_name.endswith("_lt"):
            base_field = field_name.replace("_lt", "")
            filter_dict[f"{base_field}__lt"] = value
        elif field_name.endswith("_lte"):
            base_field = field_name.replace("_lte", "")
            filter_dict[f"{base_field}__lte"] = value
        elif field_name.endswith("_in"):
            base_field = field_name.replace("_in", "")
            filter_dict[f"{base_field}__in"] = value
        else:
            # Exact match
            filter_dict[field_name] = value

    return queryset.filter(**filter_dict)


def generate_list_query(
    model: type[models.Model],
    type_class: type,
    name: str | None = None,
    description: str | None = None,
    permission_classes: list | None = None,
    **kwargs,
) -> strawberry.field:
    """
    Convenience function to generate a list query.

    Args:
        model: Django model class
        type_class: Strawberry type class
        name: Query field name
        description: Query description
        permission_classes: Permission classes
        **kwargs: Additional arguments for QueryGenerator.list_query

    Returns:
        Strawberry field descriptor
    """
    generator = QueryGenerator(model, type_class)
    return generator.list_query(
        name=name,
        description=description,
        permission_classes=permission_classes,
        **kwargs,
    )


def generate_detail_query(
    model: type[models.Model],
    type_class: type,
    name: str | None = None,
    description: str | None = None,
    permission_classes: list | None = None,
    **kwargs,
) -> strawberry.field:
    """
    Convenience function to generate a detail query.

    Args:
        model: Django model class
        type_class: Strawberry type class
        name: Query field name
        description: Query description
        permission_classes: Permission classes
        **kwargs: Additional arguments for QueryGenerator.detail_query

    Returns:
        Strawberry field descriptor
    """
    generator = QueryGenerator(model, type_class)
    return generator.detail_query(
        name=name,
        description=description,
        permission_classes=permission_classes,
        **kwargs,
    )


def generate_connection_query(
    model: type[models.Model],
    type_class: type,
    name: str | None = None,
    description: str | None = None,
    permission_classes: list | None = None,
    **kwargs,
) -> strawberry.field:
    """
    Convenience function to generate a connection query.

    Args:
        model: Django model class
        type_class: Strawberry type class
        name: Query field name
        description: Query description
        permission_classes: Permission classes
        **kwargs: Additional arguments for QueryGenerator.connection_query

    Returns:
        Strawberry field descriptor
    """
    generator = QueryGenerator(model, type_class)
    return generator.connection_query(
        name=name,
        description=description,
        permission_classes=permission_classes,
        **kwargs,
    )


__all__ = [
    "QueryGenerator",
    "apply_filters",
    "generate_list_query",
    "generate_detail_query",
    "generate_connection_query",
]
