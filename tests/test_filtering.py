"""
Tests for the filtering module in Django Matt.
"""

from datetime import date, datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from django.test import RequestFactory, TestCase

from django_matt.filtering import (
    BaseFilterBackend,
    BooleanFilter,
    CharFilter,
    ChoiceFilter,
    DateFilter,
    DateRangeFilter,
    DateTimeFilter,
    DjangoFilterBackend,
    Filter,
    FilterSet,
    InFilter,
    IntegerFilter,
    MultipleChoiceFilter,
    NumberRangeFilter,
    OrderingBackend,
    RangeFilter,
    SearchBackend,
    UUIDFilter,
)


# =============================================================================
# Mock QuerySet for Testing
# =============================================================================


class MockQuerySet:
    """Mock Django QuerySet for testing filtering."""

    def __init__(self, items=None):
        self._items = items or []
        self._filters = []
        self._ordering = []
        self._distinct = False

    def filter(self, *args, **kwargs):
        new_qs = MockQuerySet(self._items)
        if args:
            new_qs._filters = self._filters + [{"Q": args}]
        else:
            new_qs._filters = self._filters + [kwargs]
        new_qs._ordering = self._ordering
        return new_qs

    def exclude(self, **kwargs):
        new_qs = MockQuerySet(self._items)
        new_qs._filters = self._filters + [{"exclude": kwargs}]
        new_qs._ordering = self._ordering
        return new_qs

    def order_by(self, *fields):
        new_qs = MockQuerySet(self._items)
        new_qs._filters = self._filters
        new_qs._ordering = list(fields)
        return new_qs

    def distinct(self):
        new_qs = MockQuerySet(self._items)
        new_qs._filters = self._filters
        new_qs._ordering = self._ordering
        new_qs._distinct = True
        return new_qs

    def all(self):
        return self

    @property
    def model(self):
        return MagicMock()


# =============================================================================
# Filter Tests
# =============================================================================


class TestFilter(TestCase):
    """Tests for base Filter class."""

    def test_default_values(self):
        """Test default filter values."""
        f = Filter()
        self.assertEqual(f.lookup_expr, "exact")
        self.assertFalse(f.required)
        self.assertFalse(f.exclude)
        self.assertFalse(f.distinct)

    def test_custom_values(self):
        """Test custom filter values."""
        f = Filter(
            field_name="user_email",
            lookup_expr="icontains",
            required=True,
            exclude=True,
            distinct=True,
            label="User Email",
            help_text="Filter by email",
        )
        self.assertEqual(f.field_name, "user_email")
        self.assertEqual(f.lookup_expr, "icontains")
        self.assertTrue(f.required)
        self.assertTrue(f.exclude)
        self.assertTrue(f.distinct)
        self.assertEqual(f.label, "User Email")

    def test_get_field_name_from_field_name(self):
        """Test get_field_name uses field_name."""
        f = Filter(field_name="email")
        self.assertEqual(f.get_field_name(), "email")

    def test_get_field_name_from_name(self):
        """Test get_field_name falls back to name."""
        f = Filter()
        f.name = "email"
        self.assertEqual(f.get_field_name(), "email")

    def test_get_filter_lookup_with_lookup(self):
        """Test get_filter_lookup with custom lookup."""
        f = Filter(field_name="email", lookup_expr="icontains")
        self.assertEqual(f.get_filter_lookup(), "email__icontains")

    def test_get_filter_lookup_exact(self):
        """Test get_filter_lookup with exact (default)."""
        f = Filter(field_name="email", lookup_expr="exact")
        self.assertEqual(f.get_filter_lookup(), "email")

    def test_filter_applies_filter(self):
        """Test filter method applies queryset filter."""
        f = Filter(field_name="email", lookup_expr="exact")
        queryset = MockQuerySet()

        result = f.filter(queryset, "test@example.com")
        self.assertIn({"email": "test@example.com"}, result._filters)

    def test_filter_with_exclude(self):
        """Test filter with exclude=True."""
        f = Filter(field_name="status", exclude=True)
        queryset = MockQuerySet()

        result = f.filter(queryset, "deleted")
        self.assertIn({"exclude": {"status": "deleted"}}, result._filters)

    def test_filter_skips_empty_value(self):
        """Test filter skips empty values."""
        f = Filter(field_name="email")
        queryset = MockQuerySet()

        result = f.filter(queryset, "")
        self.assertEqual(result._filters, [])

        result = f.filter(queryset, None)
        self.assertEqual(result._filters, [])

    def test_filter_with_custom_method(self):
        """Test filter with custom method."""
        def custom_filter(queryset, field, value):
            return queryset.filter(custom_field=value)

        f = Filter(method=custom_filter)
        queryset = MockQuerySet()

        result = f.filter(queryset, "test")
        self.assertIn({"custom_field": "test"}, result._filters)


class TestCharFilter(TestCase):
    """Tests for CharFilter."""

    def test_default_lookup_is_icontains(self):
        """Test default lookup is icontains."""
        f = CharFilter()
        self.assertEqual(f.lookup_expr, "icontains")

    def test_convert_value(self):
        """Test value conversion to string."""
        f = CharFilter()
        self.assertEqual(f.convert_value(123), "123")
        self.assertEqual(f.convert_value("test"), "test")


class TestIntegerFilter(TestCase):
    """Tests for IntegerFilter."""

    def test_convert_value(self):
        """Test value conversion to integer."""
        f = IntegerFilter()
        self.assertEqual(f.convert_value("42"), 42)
        self.assertEqual(f.convert_value(42), 42)

    def test_invalid_value(self):
        """Test invalid value raises error."""
        f = IntegerFilter()
        with self.assertRaises(ValueError):
            f.convert_value("not a number")


class TestBooleanFilter(TestCase):
    """Tests for BooleanFilter."""

    def test_true_values(self):
        """Test truthy values."""
        f = BooleanFilter()
        for value in ["true", "1", "yes", "on", "t", "y", True]:
            self.assertTrue(f.convert_value(value))

    def test_false_values(self):
        """Test falsy values."""
        f = BooleanFilter()
        for value in ["false", "0", "no", "off", "f", "n", False]:
            self.assertFalse(f.convert_value(value))

    def test_case_insensitive(self):
        """Test case insensitive conversion."""
        f = BooleanFilter()
        self.assertTrue(f.convert_value("TRUE"))
        self.assertTrue(f.convert_value("True"))
        self.assertFalse(f.convert_value("FALSE"))


class TestDateFilter(TestCase):
    """Tests for DateFilter."""

    def test_convert_value_from_string(self):
        """Test conversion from ISO string."""
        f = DateFilter()
        result = f.convert_value("2024-06-15")
        self.assertEqual(result, date(2024, 6, 15))

    def test_convert_value_from_date(self):
        """Test pass-through of date object."""
        f = DateFilter()
        d = date(2024, 6, 15)
        result = f.convert_value(d)
        self.assertEqual(result, d)


class TestDateTimeFilter(TestCase):
    """Tests for DateTimeFilter."""

    def test_convert_value_from_string(self):
        """Test conversion from ISO string."""
        f = DateTimeFilter()
        result = f.convert_value("2024-06-15T10:30:00")
        self.assertEqual(result, datetime(2024, 6, 15, 10, 30, 0))


class TestUUIDFilter(TestCase):
    """Tests for UUIDFilter."""

    def test_convert_value_from_string(self):
        """Test conversion from string."""
        f = UUIDFilter()
        result = f.convert_value("12345678-1234-5678-1234-567812345678")
        self.assertIsInstance(result, UUID)

    def test_convert_value_from_uuid(self):
        """Test pass-through of UUID object."""
        f = UUIDFilter()
        u = UUID("12345678-1234-5678-1234-567812345678")
        result = f.convert_value(u)
        self.assertEqual(result, u)


class TestChoiceFilter(TestCase):
    """Tests for ChoiceFilter."""

    def test_valid_choice(self):
        """Test valid choice is accepted."""
        f = ChoiceFilter(choices=[("a", "A"), ("b", "B"), ("c", "C")])
        result = f.convert_value("a")
        self.assertEqual(result, "a")

    def test_invalid_choice(self):
        """Test invalid choice raises error."""
        f = ChoiceFilter(choices=[("a", "A"), ("b", "B")])
        with self.assertRaises(ValueError):
            f.convert_value("x")


class TestMultipleChoiceFilter(TestCase):
    """Tests for MultipleChoiceFilter."""

    def test_default_lookup_is_in(self):
        """Test default lookup is 'in'."""
        f = MultipleChoiceFilter()
        self.assertEqual(f.lookup_expr, "in")

    def test_convert_comma_separated(self):
        """Test conversion of comma-separated values."""
        f = MultipleChoiceFilter()
        result = f.convert_value("a,b,c")
        self.assertEqual(result, ["a", "b", "c"])

    def test_convert_list(self):
        """Test conversion of list."""
        f = MultipleChoiceFilter()
        result = f.convert_value(["a", "b", "c"])
        self.assertEqual(result, ["a", "b", "c"])


class TestInFilter(TestCase):
    """Tests for InFilter."""

    def test_default_lookup_is_in(self):
        """Test default lookup is 'in'."""
        f = InFilter()
        self.assertEqual(f.lookup_expr, "in")

    def test_convert_comma_separated(self):
        """Test conversion of comma-separated values."""
        f = InFilter()
        result = f.convert_value("1,2,3")
        self.assertEqual(result, ["1", "2", "3"])


class TestRangeFilter(TestCase):
    """Tests for RangeFilter."""

    def test_filter_with_dict(self):
        """Test filtering with min/max dict."""
        f = NumberRangeFilter(field_name="price")
        queryset = MockQuerySet()

        result = f.filter(queryset, {"min": "10", "max": "100"})
        self.assertIn({"price__gte": 10.0}, result._filters)
        self.assertIn({"price__lte": 100.0}, result._filters)

    def test_filter_with_min_only(self):
        """Test filtering with min only."""
        f = NumberRangeFilter(field_name="price")
        queryset = MockQuerySet()

        result = f.filter(queryset, {"min": "10"})
        self.assertIn({"price__gte": 10.0}, result._filters)
        self.assertEqual(len(result._filters), 1)


class TestDateRangeFilter(TestCase):
    """Tests for DateRangeFilter."""

    def test_convert_value(self):
        """Test date conversion."""
        f = DateRangeFilter()
        result = f.convert_value("2024-06-15")
        self.assertEqual(result, date(2024, 6, 15))


# =============================================================================
# FilterSet Tests
# =============================================================================


class TestFilterSet(TestCase):
    """Tests for FilterSet."""

    def test_declared_filters_collected(self):
        """Test declared filters are collected."""

        class MyFilterSet(FilterSet):
            email = CharFilter()
            age = IntegerFilter()

        self.assertIn("email", MyFilterSet._filters)
        self.assertIn("age", MyFilterSet._filters)

    def test_filter_names_set(self):
        """Test filter names are set."""

        class MyFilterSet(FilterSet):
            email = CharFilter()

        self.assertEqual(MyFilterSet._filters["email"].name, "email")

    def test_qs_property_applies_filters(self):
        """Test qs property applies filters."""

        class MyFilterSet(FilterSet):
            email = CharFilter()

        queryset = MockQuerySet()
        fs = MyFilterSet(data={"email": "test"}, queryset=queryset)

        result = fs.qs
        self.assertEqual(len(result._filters), 1)

    def test_qs_skips_empty_values(self):
        """Test qs skips empty filter values."""

        class MyFilterSet(FilterSet):
            email = CharFilter()
            name = CharFilter()

        queryset = MockQuerySet()
        fs = MyFilterSet(data={"email": "test", "name": ""}, queryset=queryset)

        result = fs.qs
        self.assertEqual(len(result._filters), 1)

    def test_required_filter_raises(self):
        """Test required filter raises if missing."""

        class MyFilterSet(FilterSet):
            email = CharFilter(required=True)

        queryset = MockQuerySet()
        fs = MyFilterSet(data={}, queryset=queryset)

        with self.assertRaises(ValueError):
            _ = fs.qs

    def test_is_valid(self):
        """Test is_valid method."""

        class MyFilterSet(FilterSet):
            email = CharFilter(required=True)
            name = CharFilter()

        queryset = MockQuerySet()

        # Invalid - missing required
        fs = MyFilterSet(data={}, queryset=queryset)
        self.assertFalse(fs.is_valid())

        # Valid - has required
        fs = MyFilterSet(data={"email": "test"}, queryset=queryset)
        self.assertTrue(fs.is_valid())

    def test_errors(self):
        """Test errors property."""

        class MyFilterSet(FilterSet):
            email = CharFilter(required=True)
            name = CharFilter(required=True)

        queryset = MockQuerySet()
        fs = MyFilterSet(data={"email": "test"}, queryset=queryset)

        errors = fs.errors
        self.assertNotIn("email", errors)
        self.assertIn("name", errors)

    def test_get_filter_fields(self):
        """Test get_filter_fields classmethod."""

        class MyFilterSet(FilterSet):
            email = CharFilter()
            name = CharFilter()

        fields = MyFilterSet.get_filter_fields()
        self.assertIn("email", fields)
        self.assertIn("name", fields)

    def test_get_schema_fields(self):
        """Test get_schema_fields classmethod."""

        class MyFilterSet(FilterSet):
            email = CharFilter(label="User email")

        schema = MyFilterSet.get_schema_fields()
        self.assertEqual(len(schema), 1)
        self.assertEqual(schema[0]["name"], "email")
        self.assertEqual(schema[0]["description"], "User email")


# =============================================================================
# DjangoFilterBackend Tests
# =============================================================================


class TestDjangoFilterBackend(TestCase):
    """Tests for DjangoFilterBackend."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.backend = DjangoFilterBackend()

    def test_filter_with_filterset(self):
        """Test filtering with FilterSet class."""

        class MyFilterSet(FilterSet):
            email = CharFilter()

        class MockView:
            filterset_class = MyFilterSet

        request = self.factory.get("/?email=test")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        self.assertEqual(len(result._filters), 1)

    def test_auto_filter_with_filter_fields(self):
        """Test auto-filtering with filter_fields."""

        class MockView:
            filter_fields = ["email", "name"]

        request = self.factory.get("/?email=test")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        self.assertIn({"email": "test"}, result._filters)

    def test_reserved_params_skipped(self):
        """Test reserved params are skipped."""

        class MockView:
            filter_fields = ["page", "email"]

        request = self.factory.get("/?page=1&email=test")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        # Only email should be filtered, not page
        self.assertEqual(len(result._filters), 1)
        self.assertIn({"email": "test"}, result._filters)

    def test_in_lookup_splits_values(self):
        """Test __in lookup splits comma-separated values."""

        class MockView:
            filter_fields = ["status"]

        request = self.factory.get("/?status__in=active,pending")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        self.assertIn({"status__in": ["active", "pending"]}, result._filters)


# =============================================================================
# SearchBackend Tests
# =============================================================================


class TestSearchBackend(TestCase):
    """Tests for SearchBackend."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.backend = SearchBackend()

    def test_no_search_without_term(self):
        """Test no filtering without search term."""

        class MockView:
            search_fields = ["email", "name"]

        request = self.factory.get("/")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        self.assertEqual(result._filters, [])

    def test_search_across_fields(self):
        """Test search applies to all configured fields."""

        class MockView:
            search_fields = ["email", "name"]

        request = self.factory.get("/?search=test")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        self.assertEqual(len(result._filters), 1)  # One Q object
        self.assertTrue(result._distinct)

    def test_get_search_terms(self):
        """Test search terms are split."""
        request = self.factory.get("/?search=hello world")
        terms = self.backend.get_search_terms(request)
        self.assertEqual(terms, ["hello", "world"])

    def test_get_lookup_default(self):
        """Test default lookup is icontains."""
        lookup = self.backend._get_lookup("email")
        self.assertEqual(lookup, "email__icontains")

    def test_get_lookup_startswith(self):
        """Test ^ prefix gives istartswith."""
        lookup = self.backend._get_lookup("^name")
        self.assertEqual(lookup, "name__istartswith")

    def test_get_lookup_exact(self):
        """Test = prefix gives iexact."""
        lookup = self.backend._get_lookup("=username")
        self.assertEqual(lookup, "username__iexact")

    def test_get_lookup_search(self):
        """Test @ prefix gives search."""
        lookup = self.backend._get_lookup("@bio")
        self.assertEqual(lookup, "bio__search")

    def test_get_lookup_regex(self):
        """Test $ prefix gives iregex."""
        lookup = self.backend._get_lookup("$pattern")
        self.assertEqual(lookup, "pattern__iregex")

    def test_get_field_name_strips_prefix(self):
        """Test field name extraction strips prefix."""
        self.assertEqual(self.backend._get_field_name("^name"), "name")
        self.assertEqual(self.backend._get_field_name("=name"), "name")
        self.assertEqual(self.backend._get_field_name("@name"), "name")
        self.assertEqual(self.backend._get_field_name("name"), "name")


# =============================================================================
# OrderingBackend Tests
# =============================================================================


class TestOrderingBackend(TestCase):
    """Tests for OrderingBackend."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.backend = OrderingBackend()

    def test_no_ordering_without_param(self):
        """Test no ordering without param or default."""

        class MockView:
            ordering_fields = ["email", "created_at"]

        request = self.factory.get("/")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        self.assertEqual(result._ordering, [])

    def test_ordering_from_request(self):
        """Test ordering from request param."""

        class MockView:
            ordering_fields = ["email", "created_at"]

        request = self.factory.get("/?ordering=-created_at")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        self.assertEqual(result._ordering, ["-created_at"])

    def test_ordering_multiple_fields(self):
        """Test ordering by multiple fields."""

        class MockView:
            ordering_fields = ["email", "created_at", "name"]

        request = self.factory.get("/?ordering=-created_at,name")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        self.assertEqual(result._ordering, ["-created_at", "name"])

    def test_ordering_validates_fields(self):
        """Test ordering validates against allowed fields."""

        class MockView:
            ordering_fields = ["email", "name"]

        request = self.factory.get("/?ordering=-created_at,name")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        # created_at should be filtered out
        self.assertEqual(result._ordering, ["name"])

    def test_default_ordering(self):
        """Test default ordering from view."""

        class MockView:
            ordering_fields = ["email", "created_at"]
            ordering = "-created_at"

        request = self.factory.get("/")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        self.assertEqual(result._ordering, ["-created_at"])

    def test_default_ordering_list(self):
        """Test default ordering as list."""

        class MockView:
            ordering_fields = ["email", "created_at"]
            ordering = ["-created_at", "email"]

        request = self.factory.get("/")
        queryset = MockQuerySet()

        result = self.backend.filter_queryset(request, queryset, MockView())
        self.assertEqual(result._ordering, ["-created_at", "email"])

    def test_get_ordering(self):
        """Test get_ordering method."""

        class MockView:
            ordering_fields = ["email", "created_at"]
            ordering = "-created_at"

        request = self.factory.get("/?ordering=email")
        ordering = self.backend.get_ordering(request, MockView())
        self.assertEqual(ordering, ["email"])


# =============================================================================
# BaseFilterBackend Tests
# =============================================================================


class ConcreteFilterBackend(BaseFilterBackend):
    """Concrete implementation for testing."""

    def filter_queryset(self, request, queryset, view=None):
        return queryset


class TestBaseFilterBackend(TestCase):
    """Tests for BaseFilterBackend."""

    def test_get_schema_fields_default(self):
        """Test default schema fields is empty."""
        backend = ConcreteFilterBackend()
        fields = backend.get_schema_fields()
        self.assertEqual(fields, [])

    def test_get_schema_operation_parameters_alias(self):
        """Test get_schema_operation_parameters aliases get_schema_fields."""
        backend = ConcreteFilterBackend()
        fields = backend.get_schema_operation_parameters()
        self.assertEqual(fields, backend.get_schema_fields())
