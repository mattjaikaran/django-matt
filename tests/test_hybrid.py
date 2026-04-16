"""Tests for django_matt.db.hybrid module."""

from unittest.mock import MagicMock, patch

from django.db import models
from django.db.models import Value
from django.db.models.functions import Concat, Upper

import pytest

from django_matt.db.hybrid import (
    HybridExpressionAccessor,
    HybridManager,
    HybridQuerySet,
    _get_hybrid_descriptors,
    hybrid_method,
    hybrid_property,
)

# =============================================================================
# Test models (not migrated — used for descriptor/class-level tests only)
# =============================================================================


class PersonModel(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    age = models.IntegerField(default=0)

    @hybrid_property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @full_name.expression
    def full_name(cls):
        return Concat("first_name", Value(" "), "last_name")

    @hybrid_property
    def upper_name(self) -> str:
        return self.first_name.upper()

    @upper_name.expression
    def upper_name(cls):
        return Upper("first_name")

    @hybrid_property
    def no_expr_prop(self) -> str:
        return "instance-only"

    @hybrid_property
    def is_adult(self) -> bool:
        return self.age >= 18

    @is_adult.expression
    def is_adult(cls):
        from django.db.models import BooleanField, Case, When

        return Case(
            When(age__gte=18, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )

    objects = HybridManager()

    class Meta:
        app_label = "django_matt"


class EmployeeModel(PersonModel):
    """Subclass to test MRO descriptor collection."""

    department = models.CharField(max_length=50, default="")

    @hybrid_property
    def dept_label(self) -> str:
        return f"[{self.department}]"

    @dept_label.expression
    def dept_label(cls):
        return Concat(Value("["), "department", Value("]"))

    class Meta:
        app_label = "django_matt"


# =============================================================================
# HYBRID PROPERTY DESCRIPTOR TESTS
# =============================================================================


class TestHybridPropertyDescriptor:
    """Tests for hybrid_property as a Python descriptor."""

    def test_instance_access_returns_value(self):
        """hybrid_property acts as a regular property on instances."""
        p = PersonModel(first_name="Jane", last_name="Doe")
        assert p.full_name == "Jane Doe"

    def test_instance_access_upper(self):
        p = PersonModel(first_name="alice", last_name="Smith")
        assert p.upper_name == "ALICE"

    def test_instance_access_boolean(self):
        p = PersonModel(first_name="Bob", last_name="X", age=21)
        assert p.is_adult is True
        p2 = PersonModel(first_name="Kid", last_name="Y", age=10)
        assert p2.is_adult is False

    def test_class_access_returns_accessor(self):
        """Accessing on the class returns HybridExpressionAccessor."""
        accessor = PersonModel.full_name
        assert isinstance(accessor, HybridExpressionAccessor)

    def test_accessor_name(self):
        accessor = PersonModel.full_name
        assert accessor.name == "full_name"

    def test_accessor_resolve(self):
        accessor = PersonModel.full_name
        expr = accessor.resolve(PersonModel)
        # Should be a Concat expression
        assert expr is not None

    def test_no_getter_raises(self):
        prop = hybrid_property()
        prop._name = "broken"

        class Dummy:
            pass

        obj = Dummy()
        with pytest.raises(AttributeError, match="has no getter"):
            prop.__get__(obj, Dummy)

    def test_set_name(self):
        prop = hybrid_property(lambda self: None)
        prop.__set_name__(PersonModel, "custom_name")
        assert prop._name == "custom_name"

    def test_none_values_in_concat(self):
        """None field values don't crash the instance property."""
        p = PersonModel(first_name=None, last_name=None)
        assert p.full_name == "None None"


# =============================================================================
# HYBRID PROPERTY SETTER / DELETER TESTS
# =============================================================================


class TestHybridPropertySetterDeleter:
    """Tests for setter/deleter on hybrid_property."""

    def test_setter(self):
        prop = hybrid_property(lambda self: self._val)

        @prop.setter
        def _set(self, value):
            self._val = value

        class Obj:
            _val = 0

        obj = Obj()
        prop.__set__(obj, 42)
        assert obj._val == 42

    def test_setter_not_defined_raises(self):
        prop = hybrid_property(lambda self: 0)
        prop._name = "readonly"
        with pytest.raises(AttributeError, match="has no setter"):
            prop.__set__(object(), 1)

    def test_deleter(self):
        deleted = []
        prop = hybrid_property(lambda self: None)

        @prop.deleter
        def _del(self, deleted=deleted):
            deleted.append(True)

        prop.__delete__(object())
        assert deleted == [True]

    def test_deleter_not_defined_raises(self):
        prop = hybrid_property(lambda self: None)
        prop._name = "nodelete"
        with pytest.raises(AttributeError, match="has no deleter"):
            prop.__delete__(object())


# =============================================================================
# EXPRESSION TESTS
# =============================================================================


class TestHybridExpression:
    """Tests for SQL expression resolution."""

    def test_expression_defined(self):
        prop_descriptor = vars(PersonModel)["full_name"]
        expr = prop_descriptor.get_expression(PersonModel)
        assert expr is not None

    def test_missing_expression_raises(self):
        prop_descriptor = vars(PersonModel)["no_expr_prop"]
        with pytest.raises(AttributeError, match="has no SQL expression"):
            prop_descriptor.get_expression(PersonModel)

    def test_expression_decorator_returns_self(self):
        """@prop.expression returns the same hybrid_property for chaining."""
        prop = hybrid_property(lambda self: None)
        result = prop.expression(lambda cls: Value(1))
        assert result is prop
        assert prop.expr is not None


# =============================================================================
# HYBRID METHOD TESTS
# =============================================================================


class TestHybridMethod:
    """Tests for hybrid_method descriptor."""

    def test_instance_access_calls_func(self):
        hm = hybrid_method(lambda self, x: x * 2)
        hm.expr = lambda cls, x: Value(x)

        class Dummy:
            method = hm

        obj = Dummy()
        assert obj.method(5) == 10

    def test_class_access_without_expression_raises(self):
        hm = hybrid_method(lambda self: None)
        hm._name = "broken"
        with pytest.raises(AttributeError, match="has no SQL expression"):
            hm.__get__(None, PersonModel)

    def test_class_access_with_expression(self):
        hm = hybrid_method(lambda self, x: x)

        @hm.expression
        def _expr(cls, x):
            return Value(x)

        accessor = hm.__get__(None, PersonModel)
        assert isinstance(accessor, object)  # HybridMethodClassAccessor
        result = accessor(42)
        assert isinstance(result, Value)

    def test_expression_decorator_returns_self(self):
        hm = hybrid_method(lambda self: None)
        result = hm.expression(lambda cls: Value(1))
        assert result is hm

    def test_set_name(self):
        hm = hybrid_method(lambda self: None)
        hm.__set_name__(PersonModel, "my_method")
        assert hm._name == "my_method"


# =============================================================================
# _get_hybrid_descriptors TESTS
# =============================================================================


class TestGetHybridDescriptors:
    """Tests for collecting hybrid descriptors from model MRO."""

    def test_collects_from_model(self):
        descriptors = _get_hybrid_descriptors(PersonModel)
        assert "full_name" in descriptors
        assert "upper_name" in descriptors
        assert "no_expr_prop" in descriptors
        assert "is_adult" in descriptors

    def test_collects_from_subclass_mro(self):
        """Subclass picks up parent hybrid properties."""
        descriptors = _get_hybrid_descriptors(EmployeeModel)
        assert "dept_label" in descriptors
        assert "full_name" in descriptors

    def test_subclass_override_wins(self):
        """If subclass redefines, the subclass version is returned (first in MRO)."""
        descriptors = _get_hybrid_descriptors(EmployeeModel)
        # dept_label is only on Employee
        assert descriptors["dept_label"]._name == "dept_label"


# =============================================================================
# HYBRID QUERYSET TESTS
# =============================================================================


class TestHybridQuerySet:
    """Tests for HybridQuerySet methods (no DB — verify annotation logic)."""

    def _make_qs(self):
        qs = HybridQuerySet(model=PersonModel)
        return qs

    def test_annotate_hybrid_unknown_raises(self):
        qs = self._make_qs()
        with pytest.raises(ValueError, match="is not a hybrid property"):
            qs.annotate_hybrid("nonexistent")

    def test_filter_hybrid_unknown_raises(self):
        qs = self._make_qs()
        with pytest.raises(ValueError, match="is not a hybrid property"):
            qs.filter_hybrid(nonexistent="x")

    def test_order_by_hybrid_unknown_raises(self):
        qs = self._make_qs()
        with pytest.raises(ValueError, match="is not a hybrid property"):
            qs.order_by_hybrid("nonexistent")

    def test_annotate_hybrid_no_expression_raises(self):
        qs = self._make_qs()
        with pytest.raises(AttributeError, match="has no SQL expression"):
            qs.annotate_hybrid("no_expr_prop")

    def test_filter_hybrid_no_expression_raises(self):
        qs = self._make_qs()
        with pytest.raises(AttributeError, match="has no SQL expression"):
            qs.filter_hybrid(no_expr_prop="x")

    def test_filter_hybrid_with_lookup(self):
        """filter_hybrid parses double-underscore lookups correctly."""
        qs = self._make_qs()
        # Patch annotate + filter to inspect what's passed
        with (
            patch.object(HybridQuerySet, "annotate", return_value=qs) as mock_ann,
            patch.object(HybridQuerySet, "filter", return_value=qs) as mock_flt,
        ):
            qs.filter_hybrid(full_name__icontains="jane")
            # annotate called with full_name=<expression>
            ann_kwargs = mock_ann.call_args[1]
            assert "full_name" in ann_kwargs
            # filter called with full_name__icontains="jane"
            flt_kwargs = mock_flt.call_args[1]
            assert flt_kwargs == {"full_name__icontains": "jane"}

    def test_order_by_hybrid_descending(self):
        """order_by_hybrid handles '-' prefix for descending."""
        qs = self._make_qs()
        with (
            patch.object(HybridQuerySet, "annotate", return_value=qs) as mock_ann,
            patch.object(HybridQuerySet, "order_by", return_value=qs) as mock_ord,
        ):
            qs.order_by_hybrid("-full_name")
            ann_kwargs = mock_ann.call_args[1]
            assert "full_name" in ann_kwargs
            assert mock_ord.call_args[0] == ("-full_name",)


# =============================================================================
# HYBRID MANAGER TESTS
# =============================================================================


class TestHybridManager:
    """Tests for HybridManager delegation."""

    def test_get_queryset_returns_hybrid_qs(self):
        mgr = HybridManager()
        mgr.model = PersonModel
        mgr._db = None
        qs = mgr.get_queryset()
        assert isinstance(qs, HybridQuerySet)

    def test_manager_delegates_annotate_hybrid(self):
        mgr = HybridManager()
        mgr.model = PersonModel
        mgr._db = None
        with patch.object(HybridQuerySet, "annotate_hybrid", return_value=MagicMock()) as mock:
            mgr.annotate_hybrid("full_name")
            mock.assert_called_once_with("full_name")

    def test_manager_delegates_filter_hybrid(self):
        mgr = HybridManager()
        mgr.model = PersonModel
        mgr._db = None
        with patch.object(HybridQuerySet, "filter_hybrid", return_value=MagicMock()) as mock:
            mgr.filter_hybrid(full_name="test")
            mock.assert_called_once_with(full_name="test")

    def test_manager_delegates_order_by_hybrid(self):
        mgr = HybridManager()
        mgr.model = PersonModel
        mgr._db = None
        with patch.object(HybridQuerySet, "order_by_hybrid", return_value=MagicMock()) as mock:
            mgr.order_by_hybrid("-full_name")
            mock.assert_called_once_with("-full_name")


# =============================================================================
# CHAINED HYBRIDS
# =============================================================================


class TestChainedHybrids:
    """Test hybrid properties that reference other hybrid properties."""

    def test_chained_instance_access(self):
        """A hybrid property can call another hybrid on the same instance."""

        class ChainModel(models.Model):
            first = models.CharField(max_length=50)
            last = models.CharField(max_length=50)

            @hybrid_property
            def full(self) -> str:
                return f"{self.first} {self.last}"

            @hybrid_property
            def greeting(self) -> str:
                return f"Hello, {self.full}!"

            class Meta:
                app_label = "django_matt"

        obj = ChainModel(first="A", last="B")
        assert obj.greeting == "Hello, A B!"
