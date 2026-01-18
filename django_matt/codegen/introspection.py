"""
Django model introspection for code generation.

Extracts field types, relationships, and metadata from Django models
to inform frontend code generation.

Usage:
    from django_matt.codegen.introspection import ModelIntrospector
    from myapp.models import User

    info = ModelIntrospector(User).introspect()
    print(info.fields)  # List of FieldInfo
    print(info.relations)  # List of RelationInfo
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union

from django.db import models


@dataclass
class FieldInfo:
    """Information about a Django model field."""

    name: str
    field_type: str  # Django field class name
    python_type: str  # Python type hint
    typescript_type: str  # TypeScript type
    nullable: bool
    blank: bool
    has_default: bool
    default_value: Any
    max_length: Optional[int]
    choices: Optional[List[tuple]]
    help_text: str
    verbose_name: str
    validators: List[str]
    is_primary_key: bool
    is_unique: bool
    is_editable: bool
    is_auto: bool  # AutoField, auto_now, etc.

    @property
    def is_required(self) -> bool:
        """Whether the field is required for creation."""
        return not (self.nullable or self.blank or self.has_default or self.is_auto)


@dataclass
class RelationInfo:
    """Information about a Django model relationship."""

    name: str
    relation_type: str  # "foreign_key", "one_to_one", "many_to_many"
    related_model: str  # "app_label.ModelName"
    related_name: Optional[str]
    nullable: bool
    on_delete: str  # CASCADE, SET_NULL, etc.
    is_reverse: bool  # Reverse relation


@dataclass
class ModelInfo:
    """Complete information about a Django model."""

    name: str
    app_label: str
    verbose_name: str
    verbose_name_plural: str
    db_table: str
    fields: List[FieldInfo] = field(default_factory=list)
    relations: List[RelationInfo] = field(default_factory=list)
    ordering: List[str] = field(default_factory=list)
    unique_together: List[tuple] = field(default_factory=list)
    indexes: List[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        """Full model name as app_label.ModelName."""
        return f"{self.app_label}.{self.name}"

    @property
    def required_fields(self) -> List[FieldInfo]:
        """Fields required for creation."""
        return [f for f in self.fields if f.is_required]

    @property
    def editable_fields(self) -> List[FieldInfo]:
        """Fields that can be edited."""
        return [f for f in self.fields if f.is_editable]


class ModelIntrospector:
    """
    Introspect Django models to extract type information.

    Usage:
        introspector = ModelIntrospector(User)
        info = introspector.introspect()
    """

    # Mapping of Django field types to Python types
    PYTHON_TYPE_MAP = {
        "AutoField": "int",
        "BigAutoField": "int",
        "SmallAutoField": "int",
        "IntegerField": "int",
        "SmallIntegerField": "int",
        "BigIntegerField": "int",
        "PositiveIntegerField": "int",
        "PositiveSmallIntegerField": "int",
        "PositiveBigIntegerField": "int",
        "FloatField": "float",
        "DecimalField": "Decimal",
        "CharField": "str",
        "TextField": "str",
        "EmailField": "str",
        "URLField": "str",
        "SlugField": "str",
        "UUIDField": "UUID",
        "BooleanField": "bool",
        "NullBooleanField": "bool | None",
        "DateField": "date",
        "DateTimeField": "datetime",
        "TimeField": "time",
        "DurationField": "timedelta",
        "BinaryField": "bytes",
        "FileField": "str",  # File path
        "ImageField": "str",  # Image path
        "FilePathField": "str",
        "IPAddressField": "str",
        "GenericIPAddressField": "str",
        "JSONField": "dict[str, Any]",
    }

    # Mapping of Django field types to TypeScript types
    TYPESCRIPT_TYPE_MAP = {
        "AutoField": "number",
        "BigAutoField": "number",
        "SmallAutoField": "number",
        "IntegerField": "number",
        "SmallIntegerField": "number",
        "BigIntegerField": "number",
        "PositiveIntegerField": "number",
        "PositiveSmallIntegerField": "number",
        "PositiveBigIntegerField": "number",
        "FloatField": "number",
        "DecimalField": "string",  # Decimals as strings for precision
        "CharField": "string",
        "TextField": "string",
        "EmailField": "string",
        "URLField": "string",
        "SlugField": "string",
        "UUIDField": "string",
        "BooleanField": "boolean",
        "NullBooleanField": "boolean | null",
        "DateField": "string",  # ISO date string
        "DateTimeField": "string",  # ISO datetime string
        "TimeField": "string",  # ISO time string
        "DurationField": "string",  # Duration as string
        "BinaryField": "string",  # Base64 encoded
        "FileField": "string",  # URL
        "ImageField": "string",  # URL
        "FilePathField": "string",
        "IPAddressField": "string",
        "GenericIPAddressField": "string",
        "JSONField": "Record<string, unknown>",
    }

    def __init__(self, model: Type[models.Model]):
        self.model = model
        self.meta = model._meta

    def introspect(self) -> ModelInfo:
        """Extract all information from the model."""
        return ModelInfo(
            name=self.meta.object_name,
            app_label=self.meta.app_label,
            verbose_name=str(self.meta.verbose_name),
            verbose_name_plural=str(self.meta.verbose_name_plural),
            db_table=self.meta.db_table,
            fields=self._get_fields(),
            relations=self._get_relations(),
            ordering=list(self.meta.ordering or []),
            unique_together=list(self.meta.unique_together or []),
            indexes=[str(idx) for idx in (self.meta.indexes or [])],
        )

    def _get_fields(self) -> List[FieldInfo]:
        """Extract field information."""
        fields = []

        for field in self.meta.get_fields():
            # Skip reverse relations and many-to-many
            if field.is_relation:
                continue

            # Skip fields without a column (reverse FKs, M2M, etc.)
            if not hasattr(field, "column"):
                continue

            field_type = field.__class__.__name__

            # Get Python type
            python_type = self.PYTHON_TYPE_MAP.get(field_type, "Any")
            if getattr(field, "null", False):
                python_type = f"{python_type} | None"

            # Get TypeScript type
            ts_type = self.TYPESCRIPT_TYPE_MAP.get(field_type, "unknown")
            if getattr(field, "null", False):
                ts_type = f"{ts_type} | null"

            # Handle choices
            choices = None
            if hasattr(field, "choices") and field.choices:
                choices = list(field.choices)
                # For choices, TypeScript type is a union
                choice_values = [f'"{c[0]}"' for c in choices]
                ts_type = " | ".join(choice_values)

            # Get validators
            validators = []
            if hasattr(field, "validators"):
                for v in field.validators:
                    validators.append(v.__class__.__name__)

            fields.append(FieldInfo(
                name=field.name,
                field_type=field_type,
                python_type=python_type,
                typescript_type=ts_type,
                nullable=getattr(field, "null", False),
                blank=getattr(field, "blank", False),
                has_default=field.has_default(),
                default_value=field.default if field.has_default() else None,
                max_length=getattr(field, "max_length", None),
                choices=choices,
                help_text=str(getattr(field, "help_text", "")),
                verbose_name=str(getattr(field, "verbose_name", field.name)),
                validators=validators,
                is_primary_key=getattr(field, "primary_key", False),
                is_unique=getattr(field, "unique", False),
                is_editable=getattr(field, "editable", True),
                is_auto=self._is_auto_field(field),
            ))

        return fields

    def _get_relations(self) -> List[RelationInfo]:
        """Extract relationship information."""
        relations = []

        for field in self.meta.get_fields():
            if not field.is_relation:
                continue

            # Determine relation type
            if field.many_to_many:
                relation_type = "many_to_many"
            elif field.one_to_one:
                relation_type = "one_to_one"
            elif field.many_to_one:
                relation_type = "foreign_key"
            else:
                # Reverse relation
                if hasattr(field, "field"):
                    if field.field.many_to_many:
                        relation_type = "many_to_many_reverse"
                    elif field.field.one_to_one:
                        relation_type = "one_to_one_reverse"
                    else:
                        relation_type = "foreign_key_reverse"
                else:
                    continue

            # Get related model
            related_model = field.related_model
            if related_model:
                related_model_name = f"{related_model._meta.app_label}.{related_model._meta.object_name}"
            else:
                related_model_name = "unknown"

            # Get on_delete
            on_delete = "CASCADE"
            if hasattr(field, "remote_field") and hasattr(field.remote_field, "on_delete"):
                on_delete = field.remote_field.on_delete.__name__

            relations.append(RelationInfo(
                name=field.name,
                relation_type=relation_type,
                related_model=related_model_name,
                related_name=getattr(field, "related_query_name", None),
                nullable=getattr(field, "null", False),
                on_delete=on_delete,
                is_reverse="_reverse" in relation_type,
            ))

        return relations

    def _is_auto_field(self, field) -> bool:
        """Check if field is automatically generated."""
        field_type = field.__class__.__name__

        # Auto fields
        if field_type in ("AutoField", "BigAutoField", "SmallAutoField"):
            return True

        # auto_now and auto_now_add
        if hasattr(field, "auto_now") and field.auto_now:
            return True
        if hasattr(field, "auto_now_add") and field.auto_now_add:
            return True

        return False


def introspect_model(model: Type[models.Model]) -> ModelInfo:
    """Convenience function to introspect a model."""
    return ModelIntrospector(model).introspect()


def introspect_models(models: List[Type[models.Model]]) -> Dict[str, ModelInfo]:
    """Introspect multiple models."""
    return {m._meta.object_name: introspect_model(m) for m in models}


__all__ = [
    "FieldInfo",
    "RelationInfo",
    "ModelInfo",
    "ModelIntrospector",
    "introspect_model",
    "introspect_models",
]
