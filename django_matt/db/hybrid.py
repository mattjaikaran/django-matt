"""
Hybrid properties for Django ORM.

SQLAlchemy-style hybrid properties that work as Python properties on model
instances and generate SQL expressions for queryset operations.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar, overload

from django.db import models
from django.db.models import Manager, QuerySet
from django.db.models.expressions import BaseExpression

T = TypeVar("T")
M = TypeVar("M", bound=models.Model)


class hybrid_property:
    """Descriptor that works as a property on instances and generates SQL
    expressions for querysets.

    On instance access: calls the decorated function.
    On class access: returns the SQL expression (if defined via @prop.expression)
    or the descriptor itself for queryset operations.
    """

    def __init__(self, fget: Callable[..., Any] | None = None) -> None:
        self.fget = fget
        self.fset: Callable[..., None] | None = None
        self.fdel: Callable[..., None] | None = None
        self.expr: Callable[..., BaseExpression] | None = None
        self._name: str = fget.__name__ if fget else ""
        if fget:
            self.__doc__ = fget.__doc__

    @overload
    def __get__(self, obj: None, objtype: type[M]) -> HybridExpressionAccessor: ...

    @overload
    def __get__(self, obj: M, objtype: type[M] | None = None) -> Any: ...

    def __get__(
        self, obj: M | None, objtype: type[M] | None = None
    ) -> Any | HybridExpressionAccessor:
        if obj is None:
            return HybridExpressionAccessor(self)
        if self.fget is None:
            raise AttributeError(f"hybrid property '{self._name}' has no getter")
        return self.fget(obj)

    def __set__(self, obj: Any, value: Any) -> None:
        if self.fset is None:
            raise AttributeError(f"hybrid property '{self._name}' has no setter")
        self.fset(obj, value)

    def __delete__(self, obj: Any) -> None:
        if self.fdel is None:
            raise AttributeError(f"hybrid property '{self._name}' has no deleter")
        self.fdel(obj)

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def setter(self, fset: Callable[..., None]) -> hybrid_property:
        """Define a setter for this hybrid property."""
        self.fset = fset
        return self

    def deleter(self, fdel: Callable[..., None]) -> hybrid_property:
        """Define a deleter for this hybrid property."""
        self.fdel = fdel
        return self

    def expression(self, expr: Callable[..., BaseExpression]) -> hybrid_property:
        """Define the SQL expression equivalent for queryset operations."""
        self.expr = expr
        return self

    def get_expression(self, model_class: type[models.Model]) -> BaseExpression:
        """Resolve the SQL expression for this hybrid property."""
        if self.expr is not None:
            return self.expr(model_class)
        raise AttributeError(
            f"hybrid property '{self._name}' has no SQL expression defined. "
            f"Use @{self._name}.expression to define one."
        )


class HybridExpressionAccessor:
    """Returned when a hybrid_property is accessed on the class (not an instance).

    Holds a reference to the descriptor so HybridManager can resolve expressions.
    """

    __slots__ = ("_prop",)

    def __init__(self, prop: hybrid_property) -> None:
        self._prop = prop

    @property
    def name(self) -> str:
        return self._prop._name

    def resolve(self, model_class: type[models.Model]) -> BaseExpression:
        return self._prop.get_expression(model_class)


class hybrid_method:
    """Descriptor for hybrid methods that accept arguments.

    On instance access: calls the decorated method with arguments.
    On class access: returns the SQL expression factory.
    """

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func
        self.expr: Callable[..., Any] | None = None
        self._name: str = func.__name__
        self.__doc__ = func.__doc__

    @overload
    def __get__(self, obj: None, objtype: type[M]) -> HybridMethodClassAccessor: ...

    @overload
    def __get__(self, obj: M, objtype: type[M] | None = None) -> Callable[..., Any]: ...

    def __get__(
        self, obj: M | None, objtype: type[M] | None = None
    ) -> Callable[..., Any] | HybridMethodClassAccessor:
        if obj is None:
            if self.expr is None:
                raise AttributeError(
                    f"hybrid method '{self._name}' has no SQL expression defined. "
                    f"Use @{self._name}.expression to define one."
                )
            return HybridMethodClassAccessor(self, objtype)
        # Bind the function to the instance
        return self.func.__get__(obj, objtype)

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def expression(self, expr: Callable[..., Any]) -> hybrid_method:
        """Define the SQL expression equivalent for queryset operations."""
        self.expr = expr
        return self


class HybridMethodClassAccessor:
    """Returned when a hybrid_method is accessed on the class.

    Callable — invokes the SQL expression factory with the provided arguments.
    """

    __slots__ = ("_method", "_model_class")

    def __init__(
        self, method: hybrid_method, model_class: type[models.Model] | None
    ) -> None:
        self._method = method
        self._model_class = model_class

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if self._method.expr is None:
            raise AttributeError(
                f"hybrid method '{self._method._name}' has no SQL expression"
            )
        return self._method.expr(self._model_class, *args, **kwargs)


def _get_hybrid_descriptors(
    model: type[models.Model],
) -> dict[str, hybrid_property]:
    """Collect all hybrid_property descriptors from a model class."""
    result: dict[str, hybrid_property] = {}
    for klass in type.mro(model):
        for attr_name, attr_value in vars(klass).items():
            if isinstance(attr_value, hybrid_property) and attr_name not in result:
                result[attr_name] = attr_value
    return result


class HybridQuerySet(QuerySet[M]):
    """QuerySet mixin that supports hybrid property operations."""

    def annotate_hybrid(self, *names: str) -> HybridQuerySet[M]:
        """Annotate the queryset with hybrid property expressions."""
        descriptors = _get_hybrid_descriptors(self.model)
        annotations: dict[str, BaseExpression] = {}
        for name in names:
            if name not in descriptors:
                raise ValueError(
                    f"'{name}' is not a hybrid property on {self.model.__name__}"
                )
            prop = descriptors[name]
            annotations[name] = prop.get_expression(self.model)
        return self.annotate(**annotations)  # type: ignore[return-value]

    def filter_hybrid(self, **kwargs: Any) -> HybridQuerySet[M]:
        """Filter using hybrid property expressions (supports lookups like __icontains)."""
        descriptors = _get_hybrid_descriptors(self.model)
        annotations: dict[str, BaseExpression] = {}
        filters: dict[str, Any] = {}

        for key, value in kwargs.items():
            # Split "full_name__icontains" into ("full_name", "icontains")
            parts = key.split("__", 1)
            prop_name = parts[0]

            if prop_name not in descriptors:
                raise ValueError(
                    f"'{prop_name}' is not a hybrid property on {self.model.__name__}"
                )

            prop = descriptors[prop_name]
            annotations[prop_name] = prop.get_expression(self.model)

            # Reconstruct the filter key using the annotation name
            filter_key = key  # e.g., "full_name" or "full_name__icontains"
            filters[filter_key] = value

        return self.annotate(**annotations).filter(**filters)  # type: ignore[return-value]

    def order_by_hybrid(self, *names: str) -> HybridQuerySet[M]:
        """Order by hybrid property expressions. Prefix with '-' for descending."""
        descriptors = _get_hybrid_descriptors(self.model)
        annotations: dict[str, BaseExpression] = {}
        order_fields: list[str] = []

        for name in names:
            descending = name.startswith("-")
            prop_name = name.lstrip("-")

            if prop_name not in descriptors:
                raise ValueError(
                    f"'{prop_name}' is not a hybrid property on {self.model.__name__}"
                )

            prop = descriptors[prop_name]
            annotations[prop_name] = prop.get_expression(self.model)
            order_fields.append(name)

        return self.annotate(**annotations).order_by(*order_fields)  # type: ignore[return-value]


class HybridManager(Manager[M]):
    """Manager that provides hybrid property queryset methods.

    Usage::

        class UserManager(HybridManager, models.Manager):
            pass

        class User(models.Model):
            objects = UserManager()
    """

    def get_queryset(self) -> HybridQuerySet[M]:
        return HybridQuerySet(self.model, using=self._db)

    def annotate_hybrid(self, *names: str) -> HybridQuerySet[M]:
        return self.get_queryset().annotate_hybrid(*names)

    def filter_hybrid(self, **kwargs: Any) -> HybridQuerySet[M]:
        return self.get_queryset().filter_hybrid(**kwargs)

    def order_by_hybrid(self, *names: str) -> HybridQuerySet[M]:
        return self.get_queryset().order_by_hybrid(*names)


__all__ = [
    "HybridManager",
    "HybridQuerySet",
    "hybrid_method",
    "hybrid_property",
]
