# file-length-max: 650
"""
Built-in model factory system for Django models.

Replaces factory-boy dependency with a native implementation.
Provides model factories for generating test data.

Usage:
    from django_matt.testing import ModelFactory, Field, SubFactory, Sequence

    class UserFactory(ModelFactory):
        class Meta:
            model = "auth.User"

        username = Sequence(lambda n: f"user{n}")
        email = Field(lambda self: f"{self.username}@example.com")
        first_name = Field(fake.first_name)
        is_active = True

    # Create instances
    user = UserFactory.create()
    users = UserFactory.create_batch(5)

    # Build without saving
    user = UserFactory.build()

    # Override fields
    admin = UserFactory.create(is_staff=True, is_superuser=True)
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from django.apps import apps
from django.db import models

from django_matt.testing.generators import fake

T = TypeVar("T", bound=models.Model)


@dataclass
class FieldDefinition:
    """Base class for factory field definitions."""


@dataclass
class Field(FieldDefinition):
    """
    A computed field value.

    The callable receives the factory instance (for accessing other fields).

    Usage:
        email = Field(lambda self: f"{self.username}@example.com")
        name = Field(fake.name)
    """

    func: Callable[[Any], Any]

    def __init__(self, func: Callable):
        if not callable(func):
            # If it's not callable, wrap it in a lambda
            value = func
            func = lambda self: value
        self.func = func


@dataclass
class LazyAttribute(FieldDefinition):
    """
    Alias for Field - a lazily computed attribute.

    Usage:
        email = LazyAttribute(lambda obj: f"{obj.username}@example.com")
    """

    func: Callable[[Any], Any]


@dataclass
class Sequence(FieldDefinition):
    """
    A sequentially generated field value.

    The callable receives the sequence number (starting from 0).

    Usage:
        username = Sequence(lambda n: f"user{n}")
        email = Sequence(lambda n: f"user{n}@example.com")
    """

    func: Callable[[int], Any]
    _counter: int = 0

    def __init__(self, func: Callable[[int], Any]):
        self.func = func

    @classmethod
    def reset_counter(cls):
        """Reset all sequence counters."""
        cls._counter = 0


@dataclass
class SubFactory(FieldDefinition):
    """
    A field that creates a related model using another factory.

    Usage:
        organization = SubFactory(OrganizationFactory)
        user = SubFactory(UserFactory, is_staff=True)
    """

    factory: type["ModelFactory"]
    kwargs: dict[str, Any]

    def __init__(self, factory: type["ModelFactory"], **kwargs):
        self.factory = factory
        self.kwargs = kwargs


@dataclass
class PostGeneration(FieldDefinition):
    """
    A hook called after the instance is created.

    Useful for many-to-many relationships or post-processing.

    Usage:
        @PostGeneration
        def groups(self, create, extracted, **kwargs):
            if extracted:
                for group in extracted:
                    self.groups.add(group)
    """

    func: Callable[[Any, bool, Any], None]


@dataclass
class RelatedFactory(FieldDefinition):
    """
    Creates related objects after the main object.

    Usage:
        memberships = RelatedFactory(MembershipFactory, "organization")
    """

    factory: type["ModelFactory"]
    factory_related_name: str
    kwargs: dict[str, Any]

    def __init__(self, factory: type["ModelFactory"], factory_related_name: str, **kwargs):
        self.factory = factory
        self.factory_related_name = factory_related_name
        self.kwargs = kwargs


class FactoryMeta:
    """Metaclass configuration for ModelFactory."""

    model: str | type[models.Model] = None
    abstract: bool = False
    django_get_or_create: tuple | None = None
    exclude: tuple = ()


class ModelFactoryMeta(type):
    """Metaclass that processes factory field definitions."""

    def __new__(mcs, name: str, bases: tuple, namespace: dict):
        # Extract Meta class
        meta = namespace.pop("Meta", None)

        # Create the class
        cls = super().__new__(mcs, name, bases, namespace)

        # Process Meta
        if meta:
            cls._meta = meta
        elif not hasattr(cls, "_meta"):
            cls._meta = type("Meta", (), {"model": None, "abstract": True})

        # Track field definitions
        cls._field_definitions = {}
        cls._post_generations = {}
        cls._related_factories = {}
        cls._sequence_counters = {}

        # Collect field definitions from base classes
        for base in bases:
            if hasattr(base, "_field_definitions"):
                cls._field_definitions.update(base._field_definitions)
            if hasattr(base, "_post_generations"):
                cls._post_generations.update(base._post_generations)
            if hasattr(base, "_related_factories"):
                cls._related_factories.update(base._related_factories)

        # Process field definitions in this class
        for key, value in list(namespace.items()):
            if key.startswith("_"):
                continue

            if isinstance(value, (Field, LazyAttribute)):
                cls._field_definitions[key] = ("lazy", value.func)
            elif isinstance(value, Sequence):
                cls._field_definitions[key] = ("sequence", value.func)
                cls._sequence_counters[key] = 0
            elif isinstance(value, SubFactory):
                cls._field_definitions[key] = ("subfactory", value.factory, value.kwargs)
            elif isinstance(value, PostGeneration):
                cls._post_generations[key] = value.func
            elif isinstance(value, RelatedFactory):
                cls._related_factories[key] = (
                    value.factory,
                    value.factory_related_name,
                    value.kwargs,
                )
            elif not callable(value) and not isinstance(
                value, (classmethod, staticmethod, property)
            ):
                # Static value
                cls._field_definitions[key] = ("static", value)

        return cls


class ModelFactory(metaclass=ModelFactoryMeta):
    """
    Base class for model factories.

    Subclass and define a Meta class with the model to create.

    Example:
        class UserFactory(ModelFactory):
            class Meta:
                model = "auth.User"

            username = Sequence(lambda n: f"user{n}")
            email = Field(lambda self: f"{self.username}@example.com")
            is_active = True

        user = UserFactory.create()
    """

    _meta: type[FactoryMeta]
    _field_definitions: dict[str, tuple]
    _post_generations: dict[str, Callable]
    _related_factories: dict[str, tuple]
    _sequence_counters: dict[str, int]

    # Instance attributes for lazy evaluation
    _values: dict[str, Any]

    def __init__(self, **kwargs):
        self._values = kwargs

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._values.get(name)

    @classmethod
    def _get_model(cls) -> type[models.Model]:
        """Get the Django model class."""
        model = getattr(cls._meta, "model", None)
        if model is None:
            raise ValueError(f"{cls.__name__} has no model defined in Meta")

        if isinstance(model, str):
            # Parse "app_label.ModelName" format
            if "." in model:
                return apps.get_model(model)
            raise ValueError(f"Model must be in 'app_label.ModelName' format: {model}")

        return model

    @classmethod
    def _get_next_sequence(cls, field_name: str) -> int:
        """Get the next sequence number for a field."""
        current = cls._sequence_counters.get(field_name, 0)
        cls._sequence_counters[field_name] = current + 1
        return current

    @classmethod
    def _resolve_field_value(
        cls,
        field_name: str,
        definition: tuple,
        instance: "ModelFactory",
        override: Any = None,
    ) -> Any:
        """Resolve a field definition to its actual value."""
        if override is not None:
            return override

        field_type = definition[0]

        if field_type == "static":
            return definition[1]

        if field_type == "lazy":
            func = definition[1]
            # Check if function takes self parameter
            import inspect

            sig = inspect.signature(func)
            if len(sig.parameters) > 0:
                return func(instance)
            return func()

        if field_type == "sequence":
            func = definition[1]
            seq_num = cls._get_next_sequence(field_name)
            return func(seq_num)

        if field_type == "subfactory":
            factory_cls = definition[1]
            factory_kwargs = definition[2]
            return factory_cls.create(**factory_kwargs)

        return None

    @classmethod
    def _generate_auto_value(cls, field: models.Field) -> Any:
        """Generate an automatic value for a Django field based on its type."""
        if field.has_default():
            default = field.default
            if callable(default):
                return default()
            return default

        if isinstance(field, models.AutoField):
            return None  # Let Django handle auto fields

        if isinstance(field, (models.CharField, models.TextField)):
            max_length = getattr(field, "max_length", 100) or 100
            if "email" in field.name.lower():
                return fake.email()[:max_length]
            if "name" in field.name.lower():
                return fake.name()[:max_length]
            if "title" in field.name.lower():
                return fake.sentence()[:max_length]
            if "slug" in field.name.lower():
                return fake.uuid4()[:max_length]
            if "description" in field.name.lower():
                return fake.paragraph()[:max_length]
            if "url" in field.name.lower():
                return fake.url()[:max_length]
            return fake.word()[:max_length]

        if isinstance(field, models.EmailField):
            return fake.email()

        if isinstance(field, models.URLField):
            return fake.url()

        if isinstance(field, models.SlugField):
            return fake.uuid4()[:50]

        if isinstance(field, models.IntegerField):
            return fake.random_int(0, 1000)

        if isinstance(field, models.PositiveIntegerField):
            return fake.random_int(0, 1000)

        if isinstance(field, models.FloatField):
            return fake.random_float(0, 1000)

        if isinstance(field, models.DecimalField):
            from decimal import Decimal

            return Decimal(str(fake.random_float(0, 1000, field.decimal_places)))

        if isinstance(field, models.BooleanField):
            return fake.boolean()

        if isinstance(field, models.DateField):
            return fake.date_this_year()

        if isinstance(field, models.DateTimeField):
            return fake.datetime_this_year()

        if isinstance(field, models.TimeField):
            return fake.time_object()

        if isinstance(field, models.UUIDField):
            return uuid.uuid4()

        if isinstance(field, models.IPAddressField):
            return fake.ipv4()

        if isinstance(field, models.GenericIPAddressField):
            return fake.ipv4()

        if isinstance(field, models.JSONField):
            return {}

        if isinstance(field, models.ForeignKey):
            return None  # Must be handled by SubFactory

        return None

    @classmethod
    def build(cls, **kwargs) -> T:
        """
        Build a model instance without saving to database.

        Args:
            **kwargs: Field overrides

        Returns:
            Unsaved model instance
        """
        model = cls._get_model()
        instance = cls(**kwargs)
        build_kwargs = {}

        # Get model fields
        model_fields = {f.name: f for f in model._meta.get_fields() if hasattr(f, "name")}

        # Process defined fields
        for field_name, definition in cls._field_definitions.items():
            value = cls._resolve_field_value(
                field_name,
                definition,
                instance,
                kwargs.get(field_name),
            )
            if value is not None:
                build_kwargs[field_name] = value
                instance._values[field_name] = value

        # Add explicit overrides
        for key, value in kwargs.items():
            if key not in build_kwargs:
                build_kwargs[key] = value

        # Auto-generate missing required fields
        for field_name, field in model_fields.items():
            if field_name in build_kwargs:
                continue
            if field_name in cls._post_generations:
                continue
            if field_name in cls._related_factories:
                continue

            # Skip auto fields, primary keys, and relations
            if isinstance(field, (models.AutoField, models.BigAutoField)):
                continue
            if isinstance(
                field, (models.ManyToManyField, models.ManyToOneRel, models.ManyToManyRel)
            ):
                continue
            if getattr(field, "primary_key", False):
                continue

            # Check if field allows null/blank
            allows_null = getattr(field, "null", False)
            allows_blank = getattr(field, "blank", False)

            if not allows_null and not allows_blank:
                value = cls._generate_auto_value(field)
                if value is not None:
                    build_kwargs[field_name] = value

        return model(**build_kwargs)

    @classmethod
    def create(cls, **kwargs) -> T:
        """
        Create and save a model instance.

        Args:
            **kwargs: Field overrides

        Returns:
            Saved model instance
        """
        # Check for get_or_create
        get_or_create = getattr(cls._meta, "django_get_or_create", None)

        if get_or_create:
            model = cls._get_model()
            lookup_kwargs = {}
            for field in get_or_create:
                if field in kwargs:
                    lookup_kwargs[field] = kwargs[field]
                elif field in cls._field_definitions:
                    instance = cls(**kwargs)
                    value = cls._resolve_field_value(
                        field,
                        cls._field_definitions[field],
                        instance,
                        None,
                    )
                    lookup_kwargs[field] = value

            if lookup_kwargs:
                try:
                    obj = model.objects.get(**lookup_kwargs)
                    # Update with provided kwargs
                    for key, value in kwargs.items():
                        if key not in lookup_kwargs:
                            setattr(obj, key, value)
                    obj.save()
                    return obj
                except model.DoesNotExist:
                    pass

        instance = cls.build(**kwargs)
        instance.save()

        # Run post-generation hooks
        for pg_name, pg_func in cls._post_generations.items():
            extracted = kwargs.get(pg_name)
            pg_kwargs = {
                k.replace(f"{pg_name}__", ""): v
                for k, v in kwargs.items()
                if k.startswith(f"{pg_name}__")
            }
            pg_func(instance, True, extracted, **pg_kwargs)

        # Create related factories
        for rel_name, (rel_factory, rel_field, rel_kwargs) in cls._related_factories.items():
            final_kwargs = dict(rel_kwargs)
            final_kwargs[rel_field] = instance
            rel_factory.create(**final_kwargs)

        return instance

    @classmethod
    def create_batch(cls, size: int, **kwargs) -> list[T]:
        """
        Create multiple model instances.

        Args:
            size: Number of instances to create
            **kwargs: Field overrides (applied to all instances)

        Returns:
            List of saved model instances
        """
        return [cls.create(**kwargs) for _ in range(size)]

    @classmethod
    def build_batch(cls, size: int, **kwargs) -> list[T]:
        """
        Build multiple model instances without saving.

        Args:
            size: Number of instances to build
            **kwargs: Field overrides (applied to all instances)

        Returns:
            List of unsaved model instances
        """
        return [cls.build(**kwargs) for _ in range(size)]

    @classmethod
    def reset_sequences(cls) -> None:
        """Reset all sequence counters for this factory."""
        for key in cls._sequence_counters:
            cls._sequence_counters[key] = 0


# Convenience function to create a factory from a model
def factory_for_model(model: str | type[models.Model], **field_definitions) -> type[ModelFactory]:
    """
    Dynamically create a factory for a model.

    Args:
        model: Model class or string "app_label.ModelName"
        **field_definitions: Field definitions for the factory

    Returns:
        A new ModelFactory subclass

    Example:
        UserFactory = factory_for_model(
            "auth.User",
            username=Sequence(lambda n: f"user{n}"),
            email=Field(lambda self: f"{self.username}@example.com"),
        )
    """
    meta = type("Meta", (), {"model": model})
    namespace = {"Meta": meta}
    namespace.update(field_definitions)
    return type(f"{model}Factory", (ModelFactory,), namespace)


# Export all
__all__ = [
    "Field",
    "LazyAttribute",
    "ModelFactory",
    "PostGeneration",
    "RelatedFactory",
    "Sequence",
    "SubFactory",
    "factory_for_model",
]
