import datetime
import uuid
from typing import Any, Optional, Union, get_args, get_origin

from django.db import models
from pydantic import BaseModel, Field, create_model

# Mapping from Django model field types to Python/Pydantic types
FIELD_TYPE_MAP = {
    models.AutoField: int,
    models.BigAutoField: int,
    models.BigIntegerField: int,
    models.BooleanField: bool,
    models.CharField: str,
    models.DateField: datetime.date,
    models.DateTimeField: datetime.datetime,
    models.DecimalField: float,
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
    models.JSONField: dict[str, Any],
}


def create_schema_from_model(
    model_class: type[models.Model],
    name: str | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    base_class: type[BaseModel] = BaseModel,
) -> type[BaseModel]:
    """
    Create a Pydantic schema from a Django model.

    Args:
        model_class: The Django model class
        name: The name for the generated schema class
        include: List of field names to include (if None, include all)
        exclude: List of field names to exclude
        base_class: Base Pydantic model class to inherit from

    Returns:
        A Pydantic model class
    """
    if name is None:
        name = f"{model_class.__name__}Schema"

    # Get all fields from the model
    fields = {}
    for field in model_class._meta.fields:
        # Skip if not in include or in exclude
        if include is not None and field.name not in include:
            continue
        if exclude is not None and field.name in exclude:
            continue

        # Get the Python type for this field
        python_type = _get_python_type_for_field(field)

        # Handle nullable fields
        if field.null:
            python_type = Optional[python_type]

        # Add field to schema with appropriate metadata
        fields[field.name] = (
            python_type,
            Field(
                title=(
                    field.verbose_name.title()
                    if field.verbose_name
                    else field.name.replace("_", " ").title()
                ),
                description=field.help_text if field.help_text else None,
                default=field.default if field.default != models.NOT_PROVIDED else ...,
            ),
        )

    # Create the Pydantic model
    schema_class = create_model(name, __base__=base_class, **fields)

    # Add a method to convert from Django model to Pydantic model
    @classmethod
    def from_orm(cls, obj):
        return cls(**{field: getattr(obj, field) for field in cls.__fields__})

    schema_class.from_orm = from_orm

    return schema_class


def create_model_from_schema(
    schema_class: type[BaseModel],
    name: str | None = None,
    app_label: str | None = None,
    base_class: type[models.Model] = models.Model,
) -> type[models.Model]:
    """
    Create a Django model from a Pydantic schema.

    Args:
        schema_class: The Pydantic schema class
        name: The name for the generated model class
        app_label: The app label for the model
        base_class: Base Django model class to inherit from

    Returns:
        A Django model class
    """
    if name is None:
        name = schema_class.__name__.replace("Schema", "")

    # Create a new model class
    attrs = {
        "__module__": schema_class.__module__,
        "Meta": type("Meta", (), {"app_label": app_label} if app_label else {}),
    }

    # Add fields based on the schema
    for field_name, field_info in schema_class.__annotations__.items():
        # Skip if private field
        if field_name.startswith("_"):
            continue

        # Get the Django field for this type
        django_field = _get_django_field_for_type(field_info)

        # Add field to model
        attrs[field_name] = django_field

    # Create the model class
    model_class = type(name, (base_class,), attrs)

    return model_class


def _get_python_type_for_field(field: models.Field) -> type:
    """Get the Python/Pydantic type for a Django model field."""
    # Handle foreign keys and one-to-one relationships
    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        return int  # Use the ID for relationships

    # Handle many-to-many relationships
    if isinstance(field, models.ManyToManyField):
        return list[int]  # Use a list of IDs for M2M

    # Look up the type in the mapping
    for field_class, python_type in FIELD_TYPE_MAP.items():
        if isinstance(field, field_class):
            return python_type

    # Default to Any for unknown field types
    return Any


def _get_django_field_for_type(type_hint: type) -> models.Field:
    """Get the Django field for a Python/Pydantic type."""
    # Handle Optional types
    origin = get_origin(type_hint)
    if origin is Union:
        args = get_args(type_hint)
        if type(None) in args:
            # It's an Optional type
            for arg in args:
                if arg is not type(None):
                    return _get_django_field_for_type(arg)

    # Handle List types
    if origin is list or origin is list:
        # It's a list type, likely for M2M
        return models.JSONField()

    # Map Python types to Django fields
    if type_hint is int:
        return models.IntegerField(null=True)
    elif type_hint is str:
        return models.CharField(max_length=255, null=True)
    elif type_hint is bool:
        return models.BooleanField(null=True)
    elif type_hint is float:
        return models.FloatField(null=True)
    elif type_hint is datetime.datetime:
        return models.DateTimeField(null=True)
    elif type_hint is datetime.date:
        return models.DateField(null=True)
    elif type_hint is datetime.time:
        return models.TimeField(null=True)
    elif type_hint is uuid.UUID:
        return models.UUIDField(null=True)
    elif type_hint is dict or origin is dict:
        return models.JSONField(null=True)

    # Default to TextField for unknown types
    return models.TextField(null=True)


class Schema(BaseModel):
    """
    Base schema class with additional utilities.
    """

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True

    @classmethod
    def from_django_model(
        cls, model_class: type[models.Model], **kwargs
    ) -> type["Schema"]:
        """Create a schema from a Django model."""
        return create_schema_from_model(model_class, base_class=cls, **kwargs)

    @classmethod
    def to_django_model(cls, **kwargs) -> type[models.Model]:
        """Create a Django model from this schema."""
        return create_model_from_schema(cls, **kwargs)
