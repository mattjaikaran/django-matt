"""
Django Matt Schema utilities.

Provides ModelSchema for converting Django models to Pydantic schemas,
inspired by ninja-schema but with enhanced features.
"""

import datetime
import uuid
from decimal import Decimal
from typing import Any, ClassVar, Optional, Union, get_args, get_origin

from django.db import models

from pydantic import BaseModel, Field, create_model, field_validator

# Mapping from Django model field types to Python/Pydantic types
FIELD_TYPE_MAP: dict[type, type] = {
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
    models.JSONField: Any,
    models.BinaryField: bytes,
    models.IPAddressField: str,
    models.GenericIPAddressField: str,
    models.FileField: str,
    models.ImageField: str,
}


def model_validator(*fields: str, mode: str = "after"):
    """
    Decorator to mark a method as a field validator for ModelSchema.

    Similar to ninja-schema's model_validator decorator.

    Usage:
        class UserSchema(ModelSchema):
            class Config:
                model = User
                include = ['email', 'username']

            @model_validator('email')
            def validate_email(cls, v):
                if not v.endswith('@company.com'):
                    raise ValueError('Must be company email')
                return v

    Args:
        *fields: Field names to validate
        mode: Validation mode ('before' or 'after')
    """

    def decorator(func):
        func._matt_validator = True
        func._matt_validator_fields = fields
        func._matt_validator_mode = mode
        return func

    return decorator


class ModelSchemaMetaclass(type(BaseModel)):
    """
    Metaclass for ModelSchema that automatically generates fields from Django model.
    """

    def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
        # Skip processing for ModelSchema base class itself
        if name == "ModelSchema":
            return super().__new__(mcs, name, bases, namespace, **kwargs)

        # Get Config class
        config = namespace.get("Config")
        if not config:
            return super().__new__(mcs, name, bases, namespace, **kwargs)

        # Get model from Config
        django_model = getattr(config, "model", None)
        if not django_model:
            return super().__new__(mcs, name, bases, namespace, **kwargs)

        # Get configuration options
        include = getattr(config, "include", None)
        exclude = getattr(config, "exclude", set())
        optional_fields = getattr(config, "optional", set())
        depth = getattr(config, "depth", 0)

        # Handle special values
        if include == "__all__":
            include = None  # Include all fields
        if optional_fields == "__all__":
            all_optional = True
        else:
            all_optional = False
            if isinstance(optional_fields, str):
                optional_fields = {optional_fields}
            else:
                optional_fields = set(optional_fields) if optional_fields else set()

        if isinstance(exclude, str):
            exclude = {exclude}
        else:
            exclude = set(exclude) if exclude else set()

        # Build annotations and field definitions
        annotations = namespace.get("__annotations__", {})

        for field in django_model._meta.fields:
            field_name = field.name

            # Skip if already defined in the class
            if field_name in annotations:
                continue

            # Handle include/exclude
            if include is not None and field_name not in include:
                continue
            if field_name in exclude:
                continue

            # Get Python type
            python_type = _get_python_type_for_field(field, depth)

            # Handle nullable/optional fields
            is_optional = (
                field.null
                or field.blank
                or all_optional
                or field_name in optional_fields
                or field.has_default()
                or field.primary_key  # PK is optional for creation
            )

            if is_optional and python_type is not type(None):
                python_type = Optional[python_type]

            # Add to annotations
            annotations[field_name] = python_type

            # Set default value
            if field.has_default():
                if callable(field.default):
                    namespace[field_name] = Field(default_factory=field.default)
                elif field.default is not models.NOT_PROVIDED:
                    namespace[field_name] = Field(default=field.default)
            elif is_optional:
                namespace[field_name] = Field(default=None)

        # Also iterate many-to-many fields (not included in _meta.fields)
        for field in django_model._meta.many_to_many:
            field_name = field.name

            # Skip if already defined in the class
            if field_name in annotations:
                continue

            # Handle include/exclude
            if include is not None and field_name not in include:
                continue
            if field_name in exclude:
                continue

            # M2M fields are always optional (can be empty) and default to empty list
            python_type = Optional[list[int]]
            annotations[field_name] = python_type
            namespace[field_name] = Field(default_factory=list)

        namespace["__annotations__"] = annotations

        # Store model reference for from_orm and apply_to_model
        namespace["_django_model"] = django_model
        namespace["_model_config"] = {
            "include": include,
            "exclude": exclude,
            "optional": optional_fields,
            "depth": depth,
        }

        # Collect validators marked with @model_validator
        validators_to_add = {}
        for attr_name, attr_value in list(namespace.items()):
            if callable(attr_value) and getattr(attr_value, "_matt_validator", False):
                fields = attr_value._matt_validator_fields
                mode = attr_value._matt_validator_mode

                # Create Pydantic field validator
                if fields:
                    validator_decorator = field_validator(*fields, mode=mode)
                    validators_to_add[attr_name] = validator_decorator(attr_value)

        namespace.update(validators_to_add)

        return super().__new__(mcs, name, bases, namespace, **kwargs)


class ModelSchema(BaseModel, metaclass=ModelSchemaMetaclass):
    """
    Base class for creating Pydantic schemas from Django models.

    Inspired by ninja-schema, provides automatic schema generation
    with field validation support.

    Usage:
        class UserSchema(ModelSchema):
            class Config:
                model = User
                include = ['id', 'username', 'email']
                # OR exclude = ['password']
                # OR fields = '__all__'
                optional = ['email']  # Make specific fields optional
                depth = 1  # Nested relations depth

            @model_validator('email')
            def validate_email(cls, v):
                if v and not v.endswith('@company.com'):
                    raise ValueError('Must be company email')
                return v
    """

    _django_model: ClassVar[type[models.Model] | None] = None
    _model_config: ClassVar[dict] = {}

    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True,
    }

    @classmethod
    def _extract_data(cls, obj: models.Model) -> dict:
        """Extract field data from a model instance (shared by from_orm and from_orm_fast)."""
        # Build set of M2M field names for this model (cached on class)
        if not hasattr(cls, "_m2m_field_names"):
            if cls._django_model is not None:
                cls._m2m_field_names = frozenset(
                    f.name for f in cls._django_model._meta.many_to_many
                )
            else:
                cls._m2m_field_names = frozenset()

        data = {}
        for field_name in cls.model_fields:
            if hasattr(obj, field_name):
                value = getattr(obj, field_name)
                if isinstance(value, models.Model):
                    value = value.pk
                elif field_name in cls._m2m_field_names:
                    # M2M manager -> list of PKs
                    value = list(value.values_list("pk", flat=True))
                data[field_name] = value
        return data

    @classmethod
    def from_orm(cls, obj: models.Model) -> "ModelSchema":
        """
        Create a schema instance from a Django model instance.

        Uses full Pydantic validation. For bulk serialization of trusted
        DB data, use from_orm_fast() instead.
        """
        if obj is None:
            raise ValueError("Cannot create schema from None")
        return cls(**cls._extract_data(obj))

    @classmethod
    def from_orm_fast(cls, obj: models.Model) -> "ModelSchema":
        """
        Create a schema instance without re-validation (model_construct).

        Use for list serialization where data comes from the database
        and doesn't need Pydantic re-validation. ~3-5x faster than from_orm().
        """
        return cls.model_construct(**cls._extract_data(obj))

    @classmethod
    def from_queryset(cls, queryset) -> list["ModelSchema"]:
        """Create a list of schema instances from a QuerySet (fast, no re-validation)."""
        return [cls.from_orm_fast(obj) for obj in queryset]

    @classmethod
    async def afrom_queryset(cls, queryset) -> list["ModelSchema"]:
        """Async version of from_queryset — uses async iteration."""
        return [cls.from_orm_fast(obj) async for obj in queryset]

    def apply_to_model(
        self,
        model_instance: models.Model,
        exclude_unset: bool = False,
        exclude_none: bool = False,
        exclude: set[str] | None = None,
    ) -> models.Model:
        """
        Apply schema data to a Django model instance.

        Args:
            model_instance: Django model instance to update
            exclude_unset: Exclude fields that were not explicitly set
            exclude_none: Exclude fields with None values
            exclude: Set of field names to exclude

        Returns:
            Updated model instance (not saved)
        """
        data = self.model_dump(
            exclude_unset=exclude_unset,
            exclude_none=exclude_none,
            exclude=exclude,
        )

        for field_name, value in data.items():
            if hasattr(model_instance, field_name):
                setattr(model_instance, field_name, value)

        return model_instance

    def create_model_instance(self, **extra_fields) -> models.Model:
        """
        Create a new Django model instance from this schema.

        Args:
            **extra_fields: Additional fields to set on the model

        Returns:
            New model instance (not saved)
        """
        if self._django_model is None:
            raise ValueError("No Django model associated with this schema")

        data = self.model_dump(exclude_none=True)
        data.update(extra_fields)

        return self._django_model(**data)


def create_schema_from_model(
    model_class: type[models.Model],
    name: str | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    optional: list[str] | None = None,
    depth: int = 0,
    base_class: type[BaseModel] = BaseModel,
) -> type[BaseModel]:
    """
    Dynamically create a Pydantic schema from a Django model.

    For most cases, prefer using ModelSchema class directly.
    This function is useful for programmatic schema creation.

    Args:
        model_class: The Django model class
        name: The name for the generated schema class
        include: List of field names to include (if None, include all)
        exclude: List of field names to exclude
        optional: List of field names to make optional
        depth: Depth for nested relations
        base_class: Base Pydantic model class to inherit from

    Returns:
        A Pydantic model class
    """
    if name is None:
        name = f"{model_class.__name__}Schema"

    if exclude is None:
        exclude = []
    if optional is None:
        optional = []

    # Get all fields from the model
    fields = {}
    field_definitions = {}

    for field in model_class._meta.fields:
        field_name = field.name

        # Skip if not in include or in exclude
        if include is not None and field_name not in include:
            continue
        if field_name in exclude:
            continue

        # Get the Python type for this field
        python_type = _get_python_type_for_field(field, depth)

        # Handle nullable/optional fields
        is_optional = (
            field.null
            or field.blank
            or field_name in optional
            or field.has_default()
            or field.primary_key
        )

        if is_optional:
            python_type = Optional[python_type]

        # Determine default value
        if field.has_default():
            if callable(field.default):
                default = Field(default_factory=field.default)
            elif field.default is not models.NOT_PROVIDED:
                default = Field(default=field.default)
            else:
                default = Field(default=None) if is_optional else ...
        elif is_optional:
            default = Field(default=None)
        else:
            default = ...

        fields[field_name] = (python_type, default)

    # Also iterate many-to-many fields
    for field in model_class._meta.many_to_many:
        field_name = field.name

        if include is not None and field_name not in include:
            continue
        if field_name in exclude:
            continue

        # M2M fields are always optional and default to empty list
        fields[field_name] = (Optional[list[int]], Field(default_factory=list))

    # Create the Pydantic model
    schema_class = create_model(name, __base__=base_class, **fields)

    # Add from_orm method
    @classmethod
    def from_orm(cls, obj):
        data = {}
        for field_name in cls.model_fields:
            if hasattr(obj, field_name):
                value = getattr(obj, field_name)
                if isinstance(value, models.Model):
                    value = value.pk
                data[field_name] = value
        return cls(**data)

    schema_class.from_orm = from_orm
    schema_class._django_model = model_class

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
    for field_name, field_info in schema_class.model_fields.items():
        # Skip if private field
        if field_name.startswith("_"):
            continue

        # Get the Django field for this type
        annotation = schema_class.__annotations__.get(field_name, str)
        django_field = _get_django_field_for_type(annotation)

        # Add field to model
        attrs[field_name] = django_field

    # Create the model class
    model_class = type(name, (base_class,), attrs)

    return model_class


def _get_python_type_for_field(field: models.Field, depth: int = 0) -> type:
    """Get the Python/Pydantic type for a Django model field."""
    # Handle foreign keys and one-to-one relationships
    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        if depth > 0:
            # Return the related model's schema type
            # For now, just return the ID
            return int
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
                    field = _get_django_field_for_type(arg)
                    field.null = True
                    return field

    # Handle List types
    if origin is list:
        return models.JSONField(null=True)

    # Map Python types to Django fields
    type_to_field = {
        int: lambda: models.IntegerField(null=True),
        str: lambda: models.CharField(max_length=255, null=True),
        bool: lambda: models.BooleanField(null=True),
        float: lambda: models.FloatField(null=True),
        datetime.datetime: lambda: models.DateTimeField(null=True),
        datetime.date: lambda: models.DateField(null=True),
        datetime.time: lambda: models.TimeField(null=True),
        uuid.UUID: lambda: models.UUIDField(null=True),
        bytes: lambda: models.BinaryField(null=True),
        dict: lambda: models.JSONField(null=True),
    }

    if type_hint in type_to_field:
        return type_to_field[type_hint]()

    if origin is dict:
        return models.JSONField(null=True)

    # Default to TextField for unknown types
    return models.TextField(null=True)


# Legacy alias for backwards compatibility
class Schema(ModelSchema):
    """
    Legacy alias for ModelSchema.

    Use ModelSchema directly for new code.
    """

    @classmethod
    def from_django_model(cls, model_class: type[models.Model], **kwargs) -> type["Schema"]:
        """Create a schema from a Django model."""
        return create_schema_from_model(model_class, base_class=cls, **kwargs)

    @classmethod
    def to_django_model(cls, **kwargs) -> type[models.Model]:
        """Create a Django model from this schema."""
        return create_model_from_schema(cls, **kwargs)
