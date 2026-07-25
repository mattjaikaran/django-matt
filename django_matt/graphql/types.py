# file-length-max: 650
"""
GraphQL type definitions for Django Matt.

Provides utilities for creating GraphQL types from Django models.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any, Generic, TypeVar, get_args, get_origin

from django.db import models

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
            "strawberry-graphql is required for GraphQL types. "
            'Install it with: uv add "strawberry-graphql[django]"'
        )


# Django field to GraphQL type mapping
DJANGO_TO_GRAPHQL_TYPE: dict[type, type] = {}

if STRAWBERRY_AVAILABLE:
    DJANGO_TO_GRAPHQL_TYPE = {
        models.AutoField: int,
        models.BigAutoField: int,
        models.BigIntegerField: int,
        models.BooleanField: bool,
        models.CharField: str,
        models.DateField: datetime.date,
        models.DateTimeField: datetime.datetime,
        models.DecimalField: Decimal,
        models.EmailField: str,
        models.FloatField: float,
        models.IntegerField: int,
        models.PositiveIntegerField: int,
        models.PositiveSmallIntegerField: int,
        models.SlugField: str,
        models.SmallIntegerField: int,
        models.TextField: str,
        models.TimeField: datetime.time,
        models.URLField: str,
        models.UUIDField: uuid.UUID,
        models.JSONField: strawberry.scalars.JSON,
        models.BinaryField: str,  # Base64 encoded
        models.IPAddressField: str,
        models.GenericIPAddressField: str,
        models.FileField: str,  # URL
        models.ImageField: str,  # URL
    }


def get_graphql_type_for_field(field: models.Field, nullable: bool = False) -> type:
    """
    Get the GraphQL type for a Django model field.

    Args:
        field: Django model field
        nullable: Whether to make the type nullable

    Returns:
        The corresponding GraphQL/Python type
    """
    _require_strawberry()

    # Handle foreign keys
    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        return strawberry.ID  # Return ID type for relationships

    # Handle many-to-many
    if isinstance(field, models.ManyToManyField):
        return list[strawberry.ID]

    # Look up type
    for field_class, graphql_type in DJANGO_TO_GRAPHQL_TYPE.items():
        if isinstance(field, field_class):
            if nullable or field.null:
                return graphql_type | None
            return graphql_type

    # Default to JSON for unknown types
    return strawberry.scalars.JSON


def get_graphql_type_for_python_type(python_type: type) -> type:
    """
    Convert a Python type to a GraphQL-compatible type.

    Args:
        python_type: Python type annotation

    Returns:
        GraphQL-compatible type
    """
    _require_strawberry()

    # Handle basic types
    type_map = {
        int: int,
        str: str,
        bool: bool,
        float: float,
        datetime.date: datetime.date,
        datetime.datetime: datetime.datetime,
        datetime.time: datetime.time,
        uuid.UUID: uuid.UUID,
        Decimal: Decimal,
        bytes: str,
        dict: strawberry.scalars.JSON,
    }

    if python_type in type_map:
        return type_map[python_type]

    # Handle Optional types
    origin = get_origin(python_type)
    args = get_args(python_type)

    if origin is list:
        inner_type = args[0] if args else Any
        return list[get_graphql_type_for_python_type(inner_type)]

    return python_type


if STRAWBERRY_AVAILABLE:

    @strawberry.interface
    class NodeInterface:
        """
        Relay Node interface for global object identification.

        All types that implement this interface can be fetched by their global ID.
        """

        id: strawberry.ID

        @classmethod
        def resolve_type(cls, obj: Any, info: Info) -> str:
            """Resolve the concrete type for a node."""
            return obj.__class__.__name__

    @strawberry.type
    class PageInfoType:
        """
        Relay PageInfo type for cursor-based pagination.
        """

        has_next_page: bool
        has_previous_page: bool
        start_cursor: str | None = None
        end_cursor: str | None = None
        total_count: int | None = None

    @strawberry.type
    class EdgeType(Generic[T]):
        """
        Relay Edge type for cursor-based pagination.
        """

        node: T
        cursor: str

    @strawberry.type
    class ConnectionType(Generic[T]):
        """
        Relay Connection type for cursor-based pagination.
        """

        page_info: PageInfoType
        edges: list[EdgeType[T]]
        total_count: int | None = None

        @staticmethod
        def from_queryset(
            queryset,
            node_type: type[T],
            first: int | None = None,
            after: str | None = None,
            last: int | None = None,
            before: str | None = None,
        ) -> ConnectionType[T]:
            """
            Create a connection from a Django queryset.

            Args:
                queryset: Django queryset
                node_type: The GraphQL type for nodes
                first: Number of items from the start
                after: Cursor to start after
                last: Number of items from the end
                before: Cursor to end before

            Returns:
                Connection with edges and page info
            """
            import base64

            total_count = queryset.count()
            items = list(queryset)

            # Apply cursor-based pagination
            start_index = 0
            end_index = len(items)

            if after:
                try:
                    start_index = int(base64.b64decode(after).decode()) + 1
                except (ValueError, UnicodeDecodeError):
                    pass

            if before:
                try:
                    end_index = int(base64.b64decode(before).decode())
                except (ValueError, UnicodeDecodeError):
                    pass

            if first is not None:
                end_index = min(start_index + first, end_index)

            if last is not None:
                start_index = max(end_index - last, start_index)

            sliced_items = items[start_index:end_index]

            # Create edges
            edges = []
            for i, item in enumerate(sliced_items, start=start_index):
                cursor = base64.b64encode(str(i).encode()).decode()
                # Convert Django model to GraphQL type if needed
                if hasattr(node_type, "from_orm"):
                    node = node_type.from_orm(item)
                elif hasattr(node_type, "from_django"):
                    node = node_type.from_django(item)
                else:
                    node = item
                edges.append(EdgeType(node=node, cursor=cursor))

            # Create page info
            page_info = PageInfoType(
                has_previous_page=start_index > 0,
                has_next_page=end_index < len(items),
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
                total_count=total_count,
            )

            return ConnectionType(
                page_info=page_info,
                edges=edges,
                total_count=total_count,
            )


class DjangoModelType:
    """
    Base class for creating GraphQL types from Django models.

    This is a helper class that provides utilities for converting
    between Django models and Strawberry types.

    Usage:
        @strawberry.type
        class UserType(DjangoModelType):
            class Meta:
                model = User
                fields = ["id", "email", "username"]
                exclude = ["password"]

    Or use the factory function:
        UserType = create_type_from_model(User, fields=["id", "email"])
    """

    _django_model: type[models.Model] | None = None
    _field_map: dict[str, str] = {}

    @classmethod
    def from_orm(cls, obj: models.Model) -> DjangoModelType:
        """Create a GraphQL type instance from a Django model."""
        data = {}
        for field_name in cls.__annotations__:
            if hasattr(obj, field_name):
                value = getattr(obj, field_name)
                # Handle related fields
                if isinstance(value, models.Model):
                    value = value.pk
                data[field_name] = value
        return cls(**data)

    @classmethod
    def from_django(cls, obj: models.Model) -> DjangoModelType:
        """Alias for from_orm."""
        return cls.from_orm(obj)

    @classmethod
    def from_queryset(cls, queryset) -> list[DjangoModelType]:
        """Create a list of GraphQL types from a queryset."""
        return [cls.from_orm(obj) for obj in queryset]


def create_type_from_model(
    model: type[models.Model],
    name: str | None = None,
    fields: list[str] | None = None,
    exclude: list[str] | None = None,
    description: str | None = None,
    interfaces: list[type] | None = None,
) -> type:
    """
    Create a Strawberry GraphQL type from a Django model.

    Args:
        model: Django model class
        name: Name for the GraphQL type (defaults to ModelName + "Type")
        fields: List of field names to include (None = all)
        exclude: List of field names to exclude
        description: Description for the type
        interfaces: List of interfaces to implement

    Returns:
        Strawberry type class

    Example:
        UserType = create_type_from_model(
            User,
            fields=["id", "email", "username"],
            exclude=["password"],
        )
    """
    _require_strawberry()

    if name is None:
        name = f"{model.__name__}Type"

    if exclude is None:
        exclude = []

    # Build annotations
    annotations = {}
    defaults = {}

    for field in model._meta.fields:
        field_name = field.name

        # Apply include/exclude filters
        if fields is not None and field_name not in fields:
            continue
        if field_name in exclude:
            continue

        # Get GraphQL type
        graphql_type = get_graphql_type_for_field(field)
        annotations[field_name] = graphql_type

        # Set default for nullable fields
        if field.null or field.blank or field.has_default():
            defaults[field_name] = None

    # Create the class dynamically
    class_dict = {
        "__annotations__": annotations,
        "_django_model": model,
        **defaults,
    }

    # Add from_orm method
    def from_orm(cls, obj: models.Model):
        data = {}
        for fname in cls.__annotations__:
            if hasattr(obj, fname):
                value = getattr(obj, fname)
                if isinstance(value, models.Model):
                    value = value.pk
                data[fname] = value
        return cls(**data)

    class_dict["from_orm"] = classmethod(from_orm)
    class_dict["from_django"] = classmethod(from_orm)

    # Create class
    type_class = type(name, (DjangoModelType,), class_dict)

    # Apply strawberry decorator
    type_class = strawberry.type(
        type_class,
        name=name,
        description=description or f"GraphQL type for {model.__name__}",
    )

    return type_class


def create_input_from_model(
    model: type[models.Model],
    name: str | None = None,
    fields: list[str] | None = None,
    exclude: list[str] | None = None,
    optional_fields: list[str] | None = None,
    description: str | None = None,
) -> type:
    """
    Create a Strawberry GraphQL input type from a Django model.

    Args:
        model: Django model class
        name: Name for the input type (defaults to ModelName + "Input")
        fields: List of field names to include (None = all)
        exclude: List of field names to exclude
        optional_fields: List of field names to make optional
        description: Description for the type

    Returns:
        Strawberry input type class
    """
    _require_strawberry()

    if name is None:
        name = f"{model.__name__}Input"

    if exclude is None:
        exclude = ["id"]  # Usually exclude ID for input

    if optional_fields is None:
        optional_fields = []

    # Build annotations
    annotations = {}
    defaults = {}

    for field in model._meta.fields:
        field_name = field.name

        # Apply include/exclude filters
        if fields is not None and field_name not in fields:
            continue
        if field_name in exclude:
            continue

        # Get GraphQL type
        graphql_type = get_graphql_type_for_field(field)

        # Make optional if needed
        is_optional = (
            field_name in optional_fields or field.null or field.blank or field.has_default()
        )

        if is_optional:
            annotations[field_name] = graphql_type | None
            defaults[field_name] = UNSET
        else:
            annotations[field_name] = graphql_type

    # Create the class dynamically
    class_dict = {
        "__annotations__": annotations,
        "_django_model": model,
        **defaults,
    }

    # Create class
    input_class = type(name, (), class_dict)

    # Apply strawberry decorator
    input_class = strawberry.input(
        input_class,
        name=name,
        description=description or f"Input type for {model.__name__}",
    )

    return input_class


def create_filter_input_from_model(
    model: type[models.Model],
    name: str | None = None,
    fields: list[str] | None = None,
    exclude: list[str] | None = None,
    description: str | None = None,
) -> type:
    """
    Create a filter input type for a Django model.

    Generates filter fields like field_eq, field_contains, field_in, etc.

    Args:
        model: Django model class
        name: Name for the filter type
        fields: List of field names to include
        exclude: List of field names to exclude
        description: Description for the type

    Returns:
        Strawberry input type class for filtering
    """
    _require_strawberry()

    if name is None:
        name = f"{model.__name__}Filter"

    if exclude is None:
        exclude = []

    # Build annotations with filter operators
    annotations = {}
    defaults = {}

    for field in model._meta.fields:
        field_name = field.name

        if fields is not None and field_name not in fields:
            continue
        if field_name in exclude:
            continue

        graphql_type = get_graphql_type_for_field(field, nullable=True)

        # Add filter variants
        # Exact match
        annotations[field_name] = graphql_type | None
        defaults[field_name] = UNSET

        # For string fields, add contains, starts_with, ends_with
        if isinstance(field, (models.CharField, models.TextField)):
            annotations[f"{field_name}_contains"] = str | None
            annotations[f"{field_name}_icontains"] = str | None
            annotations[f"{field_name}_startswith"] = str | None
            annotations[f"{field_name}_endswith"] = str | None
            defaults[f"{field_name}_contains"] = UNSET
            defaults[f"{field_name}_icontains"] = UNSET
            defaults[f"{field_name}_startswith"] = UNSET
            defaults[f"{field_name}_endswith"] = UNSET

        # For numeric/date fields, add gt, gte, lt, lte
        if isinstance(
            field,
            (
                models.IntegerField,
                models.FloatField,
                models.DecimalField,
                models.DateField,
                models.DateTimeField,
            ),
        ):
            base_type = get_graphql_type_for_field(field, nullable=True)
            annotations[f"{field_name}_gt"] = base_type | None
            annotations[f"{field_name}_gte"] = base_type | None
            annotations[f"{field_name}_lt"] = base_type | None
            annotations[f"{field_name}_lte"] = base_type | None
            defaults[f"{field_name}_gt"] = UNSET
            defaults[f"{field_name}_gte"] = UNSET
            defaults[f"{field_name}_lt"] = UNSET
            defaults[f"{field_name}_lte"] = UNSET

        # For all fields, add _in filter
        annotations[f"{field_name}_in"] = list[graphql_type] | None
        defaults[f"{field_name}_in"] = UNSET

    # Add AND/OR combinators
    annotations["AND"] = f"list[{name}] | None"
    annotations["OR"] = f"list[{name}] | None"
    defaults["AND"] = UNSET
    defaults["OR"] = UNSET

    # Create the class
    class_dict = {
        "__annotations__": annotations,
        **defaults,
    }

    filter_class = type(name, (), class_dict)

    filter_class = strawberry.input(
        filter_class,
        name=name,
        description=description or f"Filter input for {model.__name__}",
    )

    return filter_class


# Export types only if strawberry is available
if STRAWBERRY_AVAILABLE:
    __all__ = [
        "DjangoModelType",
        "NodeInterface",
        "PageInfoType",
        "EdgeType",
        "ConnectionType",
        "create_type_from_model",
        "create_input_from_model",
        "create_filter_input_from_model",
        "get_graphql_type_for_field",
        "get_graphql_type_for_python_type",
        "DJANGO_TO_GRAPHQL_TYPE",
    ]
else:
    __all__ = [
        "DjangoModelType",
        "create_type_from_model",
        "get_graphql_type_for_field",
    ]
