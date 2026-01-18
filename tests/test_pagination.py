"""
Tests for the pagination module in Django Matt.
"""

from unittest.mock import MagicMock

from django.test import RequestFactory, TestCase

from django_matt.pagination import (
    BasePagination,
    CursorPagination,
    LimitOffsetPagination,
    PageNumberPagination,
    PaginationResult,
)

# =============================================================================
# Mock QuerySet for Testing
# =============================================================================


class MockQuerySet:
    """Mock Django QuerySet for testing pagination."""

    def __init__(self, items):
        self._items = items
        self._count = len(items)
        self._sliced = False

    def count(self):
        return self._count

    async def acount(self):
        return self._count

    def order_by(self, *fields):
        # Return self for chaining
        return self

    def filter(self, *args, **kwargs):
        # Return self for chaining
        return self

    def __getitem__(self, key):
        if isinstance(key, slice):
            return MockQuerySet(self._items[key])
        return self._items[key]

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __list__(self):
        return self._items


# =============================================================================
# PaginationResult Tests
# =============================================================================


class TestPaginationResult(TestCase):
    """Tests for PaginationResult model."""

    def test_basic_creation(self):
        """Test creating a basic pagination result."""
        result = PaginationResult(items=[1, 2, 3], total=10)
        self.assertEqual(result.items, [1, 2, 3])
        self.assertEqual(result.total, 10)

    def test_page_number_fields(self):
        """Test page number pagination fields."""
        result = PaginationResult(
            items=[1, 2, 3],
            total=100,
            page=2,
            page_size=10,
            pages=10,
            has_next=True,
            has_previous=True,
        )
        self.assertEqual(result.page, 2)
        self.assertEqual(result.page_size, 10)
        self.assertEqual(result.pages, 10)
        self.assertTrue(result.has_next)
        self.assertTrue(result.has_previous)

    def test_limit_offset_fields(self):
        """Test limit/offset pagination fields."""
        result = PaginationResult(
            items=[1, 2, 3],
            total=100,
            limit=10,
            offset=20,
            has_next=True,
            has_previous=True,
        )
        self.assertEqual(result.limit, 10)
        self.assertEqual(result.offset, 20)

    def test_cursor_fields(self):
        """Test cursor pagination fields."""
        result = PaginationResult(
            items=[1, 2, 3],
            total=100,
            next_cursor="abc123",
            previous_cursor="xyz789",
            has_next=True,
            has_previous=True,
        )
        self.assertEqual(result.next_cursor, "abc123")
        self.assertEqual(result.previous_cursor, "xyz789")


# =============================================================================
# PageNumberPagination Tests
# =============================================================================


class TestPageNumberPagination(TestCase):
    """Tests for PageNumberPagination."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.items = list(range(1, 101))  # 100 items
        self.queryset = MockQuerySet(self.items)

    def test_default_values(self):
        """Test default values."""
        pagination = PageNumberPagination()
        self.assertEqual(pagination.page_size, 20)
        self.assertEqual(pagination.max_page_size, 100)
        self.assertEqual(pagination.page_query_param, "page")
        self.assertEqual(pagination.page_size_query_param, "page_size")

    def test_custom_values(self):
        """Test custom initialization."""
        pagination = PageNumberPagination(
            page_size=25,
            max_page_size=50,
            page_query_param="p",
            page_size_query_param="size",
        )
        self.assertEqual(pagination.page_size, 25)
        self.assertEqual(pagination.max_page_size, 50)
        self.assertEqual(pagination.page_query_param, "p")
        self.assertEqual(pagination.page_size_query_param, "size")

    def test_first_page(self):
        """Test getting first page."""
        pagination = PageNumberPagination(page_size=10)
        request = self.factory.get("/api/items/")

        result = pagination.paginate_queryset(self.queryset, request)
        self.assertEqual(list(result), list(range(1, 11)))

        response = pagination.get_paginated_response(list(result))
        self.assertEqual(response["total"], 100)
        self.assertEqual(response["page"], 1)
        self.assertEqual(response["page_size"], 10)
        self.assertEqual(response["pages"], 10)
        self.assertTrue(response["has_next"])
        self.assertFalse(response["has_previous"])

    def test_middle_page(self):
        """Test getting a middle page."""
        pagination = PageNumberPagination(page_size=10)
        request = self.factory.get("/api/items/?page=5")

        result = pagination.paginate_queryset(self.queryset, request)
        self.assertEqual(list(result), list(range(41, 51)))

        response = pagination.get_paginated_response(list(result))
        self.assertEqual(response["page"], 5)
        self.assertTrue(response["has_next"])
        self.assertTrue(response["has_previous"])

    def test_last_page(self):
        """Test getting last page."""
        pagination = PageNumberPagination(page_size=10)
        request = self.factory.get("/api/items/?page=10")

        result = pagination.paginate_queryset(self.queryset, request)
        self.assertEqual(list(result), list(range(91, 101)))

        response = pagination.get_paginated_response(list(result))
        self.assertEqual(response["page"], 10)
        self.assertFalse(response["has_next"])
        self.assertTrue(response["has_previous"])

    def test_custom_page_size_from_request(self):
        """Test custom page size from request."""
        pagination = PageNumberPagination(page_size=10, max_page_size=50)
        request = self.factory.get("/api/items/?page_size=25")

        result = pagination.paginate_queryset(self.queryset, request)
        self.assertEqual(len(list(result)), 25)

        response = pagination.get_paginated_response(list(result))
        self.assertEqual(response["page_size"], 25)
        self.assertEqual(response["pages"], 4)

    def test_page_size_capped_at_max(self):
        """Test page size is capped at max."""
        pagination = PageNumberPagination(page_size=10, max_page_size=30)
        request = self.factory.get("/api/items/?page_size=100")

        result = pagination.paginate_queryset(self.queryset, request)
        self.assertEqual(len(list(result)), 30)

    def test_invalid_page_number_defaults_to_one(self):
        """Test invalid page number defaults to 1."""
        pagination = PageNumberPagination(page_size=10)
        request = self.factory.get("/api/items/?page=invalid")

        result = pagination.paginate_queryset(self.queryset, request)
        response = pagination.get_paginated_response(list(result))
        self.assertEqual(response["page"], 1)

    def test_negative_page_defaults_to_one(self):
        """Test negative page defaults to 1."""
        pagination = PageNumberPagination(page_size=10)
        request = self.factory.get("/api/items/?page=-5")

        result = pagination.paginate_queryset(self.queryset, request)
        response = pagination.get_paginated_response(list(result))
        self.assertEqual(response["page"], 1)

    def test_page_beyond_total_clamped(self):
        """Test page beyond total is clamped."""
        pagination = PageNumberPagination(page_size=10)
        request = self.factory.get("/api/items/?page=999")

        result = pagination.paginate_queryset(self.queryset, request)
        response = pagination.get_paginated_response(list(result))
        self.assertEqual(response["page"], 10)  # Last page

    def test_empty_queryset(self):
        """Test pagination with empty queryset."""
        pagination = PageNumberPagination(page_size=10)
        request = self.factory.get("/api/items/")
        empty_qs = MockQuerySet([])

        result = pagination.paginate_queryset(empty_qs, request)
        response = pagination.get_paginated_response(list(result))

        self.assertEqual(response["total"], 0)
        self.assertEqual(response["pages"], 1)
        self.assertFalse(response["has_next"])
        self.assertFalse(response["has_previous"])

    def test_count_property(self):
        """Test count property."""
        pagination = PageNumberPagination(page_size=10)
        request = self.factory.get("/api/items/")
        pagination.paginate_queryset(self.queryset, request)

        self.assertEqual(pagination.count, 100)

    def test_num_pages_property(self):
        """Test num_pages property."""
        pagination = PageNumberPagination(page_size=10)
        request = self.factory.get("/api/items/")
        pagination.paginate_queryset(self.queryset, request)

        self.assertEqual(pagination.num_pages, 10)


# =============================================================================
# LimitOffsetPagination Tests
# =============================================================================


class TestLimitOffsetPagination(TestCase):
    """Tests for LimitOffsetPagination."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.items = list(range(1, 101))  # 100 items
        self.queryset = MockQuerySet(self.items)

    def test_default_values(self):
        """Test default values."""
        pagination = LimitOffsetPagination()
        self.assertEqual(pagination.default_limit, 20)
        self.assertEqual(pagination.max_limit, 100)
        self.assertEqual(pagination.limit_query_param, "limit")
        self.assertEqual(pagination.offset_query_param, "offset")

    def test_custom_values(self):
        """Test custom initialization."""
        pagination = LimitOffsetPagination(
            default_limit=25,
            max_limit=50,
            limit_query_param="l",
            offset_query_param="o",
        )
        self.assertEqual(pagination.default_limit, 25)
        self.assertEqual(pagination.max_limit, 50)
        self.assertEqual(pagination.limit_query_param, "l")
        self.assertEqual(pagination.offset_query_param, "o")

    def test_default_offset_zero(self):
        """Test default offset is zero."""
        pagination = LimitOffsetPagination(default_limit=10)
        request = self.factory.get("/api/items/")

        result = pagination.paginate_queryset(self.queryset, request)
        self.assertEqual(list(result), list(range(1, 11)))

        response = pagination.get_paginated_response(list(result))
        self.assertEqual(response["offset"], 0)

    def test_custom_limit_and_offset(self):
        """Test custom limit and offset."""
        pagination = LimitOffsetPagination(default_limit=10, max_limit=100)
        request = self.factory.get("/api/items/?limit=20&offset=40")

        result = pagination.paginate_queryset(self.queryset, request)
        self.assertEqual(list(result), list(range(41, 61)))

        response = pagination.get_paginated_response(list(result))
        self.assertEqual(response["limit"], 20)
        self.assertEqual(response["offset"], 40)
        self.assertTrue(response["has_next"])
        self.assertTrue(response["has_previous"])

    def test_last_batch(self):
        """Test getting last batch."""
        pagination = LimitOffsetPagination(default_limit=20)
        request = self.factory.get("/api/items/?offset=80")

        result = pagination.paginate_queryset(self.queryset, request)
        response = pagination.get_paginated_response(list(result))

        self.assertEqual(response["offset"], 80)
        self.assertFalse(response["has_next"])
        self.assertTrue(response["has_previous"])

    def test_limit_capped_at_max(self):
        """Test limit is capped at max."""
        pagination = LimitOffsetPagination(default_limit=10, max_limit=30)
        request = self.factory.get("/api/items/?limit=100")

        result = pagination.paginate_queryset(self.queryset, request)
        self.assertEqual(len(list(result)), 30)

    def test_invalid_limit_uses_default(self):
        """Test invalid limit uses default."""
        pagination = LimitOffsetPagination(default_limit=10)
        request = self.factory.get("/api/items/?limit=invalid")

        result = pagination.paginate_queryset(self.queryset, request)
        response = pagination.get_paginated_response(list(result))
        self.assertEqual(response["limit"], 10)

    def test_negative_offset_defaults_to_zero(self):
        """Test negative offset defaults to zero."""
        pagination = LimitOffsetPagination(default_limit=10)
        request = self.factory.get("/api/items/?offset=-10")

        result = pagination.paginate_queryset(self.queryset, request)
        response = pagination.get_paginated_response(list(result))
        self.assertEqual(response["offset"], 0)

    def test_get_next_offset(self):
        """Test get_next_offset method."""
        pagination = LimitOffsetPagination(default_limit=20)
        request = self.factory.get("/api/items/?offset=40")
        pagination.paginate_queryset(self.queryset, request)

        self.assertEqual(pagination.get_next_offset(), 60)

    def test_get_next_offset_at_end(self):
        """Test get_next_offset returns None at end."""
        pagination = LimitOffsetPagination(default_limit=20)
        request = self.factory.get("/api/items/?offset=80")
        pagination.paginate_queryset(self.queryset, request)

        self.assertIsNone(pagination.get_next_offset())

    def test_get_previous_offset(self):
        """Test get_previous_offset method."""
        pagination = LimitOffsetPagination(default_limit=20)
        request = self.factory.get("/api/items/?offset=40")
        pagination.paginate_queryset(self.queryset, request)

        self.assertEqual(pagination.get_previous_offset(), 20)

    def test_get_previous_offset_at_start(self):
        """Test get_previous_offset returns None at start."""
        pagination = LimitOffsetPagination(default_limit=20)
        request = self.factory.get("/api/items/")
        pagination.paginate_queryset(self.queryset, request)

        self.assertIsNone(pagination.get_previous_offset())

    def test_empty_queryset(self):
        """Test pagination with empty queryset."""
        pagination = LimitOffsetPagination(default_limit=10)
        request = self.factory.get("/api/items/")
        empty_qs = MockQuerySet([])

        result = pagination.paginate_queryset(empty_qs, request)
        response = pagination.get_paginated_response(list(result))

        self.assertEqual(response["total"], 0)
        self.assertFalse(response["has_next"])
        self.assertFalse(response["has_previous"])


# =============================================================================
# CursorPagination Tests
# =============================================================================


class TestCursorPagination(TestCase):
    """Tests for CursorPagination."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        # Create mock items with pk attribute
        self.items = [MagicMock(pk=i, id=i) for i in range(1, 101)]
        self.queryset = MockQuerySet(self.items)

    def test_default_values(self):
        """Test default values."""
        pagination = CursorPagination()
        self.assertEqual(pagination.page_size, 20)
        self.assertEqual(pagination.cursor_query_param, "cursor")
        self.assertEqual(pagination.ordering, "pk")

    def test_custom_values(self):
        """Test custom initialization."""
        pagination = CursorPagination(
            page_size=25,
            max_page_size=50,
            ordering="-created_at",
            cursor_query_param="c",
        )
        self.assertEqual(pagination.page_size, 25)
        self.assertEqual(pagination.max_page_size, 50)
        self.assertEqual(pagination.ordering, "-created_at")
        self.assertEqual(pagination.cursor_query_param, "c")

    def test_first_page_no_cursor(self):
        """Test getting first page without cursor."""
        pagination = CursorPagination(page_size=10)
        request = self.factory.get("/api/items/")

        result = pagination.paginate_queryset(self.queryset, request)
        self.assertEqual(len(result), 10)

        response = pagination.get_paginated_response(result)
        self.assertEqual(response["page_size"], 10)
        self.assertTrue(response["has_next"])
        self.assertFalse(response["has_previous"])
        self.assertIsNotNone(response["next_cursor"])

    def test_encode_decode_cursor(self):
        """Test cursor encoding and decoding."""
        pagination = CursorPagination()
        position = {"pk": 50}

        encoded = pagination._encode_cursor(position)
        decoded = pagination._decode_cursor(encoded)

        self.assertEqual(decoded, position)

    def test_encode_decode_cursor_with_secret(self):
        """Test cursor encoding/decoding with secret."""
        pagination = CursorPagination(cursor_secret="mysecret")
        position = {"pk": 50}

        encoded = pagination._encode_cursor(position)
        decoded = pagination._decode_cursor(encoded)

        self.assertEqual(decoded, position)

    def test_tampered_cursor_with_secret_returns_none(self):
        """Test tampered cursor with secret returns None."""
        pagination = CursorPagination(cursor_secret="mysecret")
        position = {"pk": 50}

        encoded = pagination._encode_cursor(position)
        # Tamper with the cursor
        tampered = encoded[:-1] + "x"
        decoded = pagination._decode_cursor(tampered)

        self.assertIsNone(decoded)

    def test_invalid_cursor_returns_none(self):
        """Test invalid cursor returns None."""
        pagination = CursorPagination()

        self.assertIsNone(pagination._decode_cursor("invalid"))
        self.assertIsNone(pagination._decode_cursor(""))
        self.assertIsNone(pagination._decode_cursor(None))

    def test_ordering_fields_single(self):
        """Test _get_ordering_fields with single field."""
        pagination = CursorPagination(ordering="pk")
        self.assertEqual(pagination._get_ordering_fields(), ["pk"])

    def test_ordering_fields_list(self):
        """Test _get_ordering_fields with list."""
        pagination = CursorPagination(ordering=["-created_at", "pk"])
        self.assertEqual(pagination._get_ordering_fields(), ["-created_at", "pk"])

    def test_ordering_directions(self):
        """Test _get_ordering_directions."""
        pagination = CursorPagination(ordering=["-created_at", "pk"])
        directions = pagination._get_ordering_directions()

        self.assertEqual(directions, [("created_at", True), ("pk", False)])

    def test_get_position(self):
        """Test _get_position extracts values from instance."""
        pagination = CursorPagination(ordering="pk")
        item = MagicMock(pk=42)

        position = pagination._get_position(item)
        self.assertEqual(position, {"pk": 42})

    def test_next_cursor_property(self):
        """Test next_cursor property."""
        pagination = CursorPagination(page_size=10)
        request = self.factory.get("/api/items/")
        pagination.paginate_queryset(self.queryset, request)

        self.assertIsNotNone(pagination.next_cursor)

    def test_previous_cursor_property(self):
        """Test previous_cursor property on first page."""
        pagination = CursorPagination(page_size=10)
        request = self.factory.get("/api/items/")
        pagination.paginate_queryset(self.queryset, request)

        # First page has no previous cursor
        self.assertIsNone(pagination.previous_cursor)

    def test_get_paginated_response_structure(self):
        """Test get_paginated_response returns correct structure."""
        pagination = CursorPagination(page_size=10)
        request = self.factory.get("/api/items/")
        result = pagination.paginate_queryset(self.queryset, request)
        response = pagination.get_paginated_response(result)

        self.assertIn("items", response)
        self.assertIn("page_size", response)
        self.assertIn("next_cursor", response)
        self.assertIn("previous_cursor", response)
        self.assertIn("has_next", response)
        self.assertIn("has_previous", response)


# =============================================================================
# BasePagination Tests
# =============================================================================


class ConcretePagination(BasePagination):
    """Concrete implementation for testing BasePagination."""

    def paginate_queryset(self, queryset, request):
        return queryset[: self.page_size]

    def get_paginated_response(self, data):
        return {"items": data, "count": self._count}


class TestBasePagination(TestCase):
    """Tests for BasePagination base class."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_default_values(self):
        """Test default values."""
        pagination = ConcretePagination()
        self.assertEqual(pagination.page_size, 20)
        self.assertEqual(pagination.max_page_size, 100)

    def test_custom_values(self):
        """Test custom initialization."""
        pagination = ConcretePagination(page_size=50, max_page_size=200)
        self.assertEqual(pagination.page_size, 50)
        self.assertEqual(pagination.max_page_size, 200)

    def test_get_page_size_from_request(self):
        """Test get_page_size reads from request."""
        pagination = ConcretePagination()
        request = self.factory.get("/api/items/?page_size=30")

        size = pagination.get_page_size(request)
        self.assertEqual(size, 30)

    def test_get_page_size_respects_max(self):
        """Test get_page_size respects max_page_size."""
        pagination = ConcretePagination(max_page_size=50)
        request = self.factory.get("/api/items/?page_size=100")

        size = pagination.get_page_size(request)
        self.assertEqual(size, 50)

    def test_get_page_size_invalid_value(self):
        """Test get_page_size with invalid value uses default."""
        pagination = ConcretePagination(page_size=20)
        request = self.factory.get("/api/items/?page_size=invalid")

        size = pagination.get_page_size(request)
        self.assertEqual(size, 20)

    def test_get_page_size_negative_uses_default(self):
        """Test get_page_size with negative uses default."""
        pagination = ConcretePagination(page_size=20)
        request = self.factory.get("/api/items/?page_size=-10")

        size = pagination.get_page_size(request)
        self.assertEqual(size, 20)

    def test_get_count_with_queryset(self):
        """Test get_count with queryset."""
        pagination = ConcretePagination()
        queryset = MockQuerySet(list(range(50)))

        count = pagination.get_count(queryset)
        self.assertEqual(count, 50)

    def test_get_count_with_list(self):
        """Test get_count with list fallback."""
        pagination = ConcretePagination()
        items = list(range(30))

        count = pagination.get_count(items)
        self.assertEqual(count, 30)
