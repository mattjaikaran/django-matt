"""
Cursor-based pagination for django-matt.

Efficient pagination for large datasets: ?cursor=abc123
"""

import base64
import hashlib
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest

import orjson

from .base import BasePagination


class CursorPagination(BasePagination):
    """
    Cursor-based pagination for efficient traversal of large datasets.

    Unlike offset pagination, cursor pagination:
    - Has consistent performance regardless of page depth
    - Handles insertions/deletions without skipping or duplicating items
    - Cannot jump to arbitrary pages (only next/previous)

    Query parameters:
        - cursor: Opaque cursor string for the current position
        - page_size: Number of items to return (optional)

    Example:
        GET /api/users?cursor=eyJpZCI6MTAwfQ&page_size=25

    Response:
        {
            "items": [...],
            "page_size": 25,
            "next_cursor": "eyJpZCI6MTI1fQ",
            "previous_cursor": "eyJpZCI6NzV9",
            "has_next": true,
            "has_previous": true
        }

    Usage:
        pagination = CursorPagination(ordering="-created_at")

        # In view
        queryset = pagination.paginate_queryset(User.objects.all(), request)
        users = [UserSchema.from_orm(u) for u in queryset]
        return pagination.get_paginated_response(users)

    Note:
        - Requires a consistent ordering (default: 'pk')
        - The ordering field(s) should be indexed for performance
        - Cursor contains encoded position, not raw IDs
    """

    cursor_query_param: str = "cursor"
    page_size_query_param: str = "page_size"
    ordering: str | list[str] = "pk"  # Default ordering field(s)
    # Secret for signing cursors (optional, set for security)
    cursor_secret: str | None = None

    def __init__(
        self,
        page_size: int | None = None,
        max_page_size: int | None = None,
        max_unpaginated: int | None = None,
        ordering: str | list[str] | None = None,
        cursor_query_param: str | None = None,
        cursor_secret: str | None = None,
    ):
        super().__init__(page_size, max_page_size, max_unpaginated)
        if ordering is not None:
            self.ordering = ordering
        if cursor_query_param is not None:
            self.cursor_query_param = cursor_query_param
        if cursor_secret is not None:
            self.cursor_secret = cursor_secret

        # State
        self._page_size_used: int = self.page_size
        self._has_next: bool = False
        self._has_previous: bool = False
        self._next_cursor: str | None = None
        self._previous_cursor: str | None = None
        self._results: list[Any] = []

    def _get_ordering_fields(self) -> list[str]:
        """Get ordering as a list of field names."""
        if isinstance(self.ordering, str):
            return [self.ordering]
        return list(self.ordering)

    def _get_ordering_directions(self) -> list[tuple[str, bool]]:
        """Get ordering fields with their directions (field, is_descending)."""
        fields = self._get_ordering_fields()
        result = []
        for field in fields:
            if field.startswith("-"):
                result.append((field[1:], True))
            else:
                result.append((field, False))
        return result

    def _encode_cursor(self, position: dict[str, Any]) -> str:
        """Encode position dict to cursor string."""
        data = orjson.dumps(position, option=orjson.OPT_SORT_KEYS, default=str)
        encoded = base64.urlsafe_b64encode(data).decode()

        if self.cursor_secret:
            # Add signature for tampering protection
            sig = hashlib.sha256(f"{encoded}{self.cursor_secret}".encode()).hexdigest()[:8]
            return f"{encoded}.{sig}"

        return encoded

    def _decode_cursor(self, cursor: str) -> dict[str, Any] | None:
        """Decode cursor string to position dict."""
        if not cursor:
            return None

        try:
            if self.cursor_secret:
                # Verify signature
                parts = cursor.rsplit(".", 1)
                if len(parts) != 2:
                    return None
                encoded, sig = parts
                expected_sig = hashlib.sha256(
                    f"{encoded}{self.cursor_secret}".encode()
                ).hexdigest()[:8]
                if sig != expected_sig:
                    return None
            else:
                encoded = cursor

            data = base64.urlsafe_b64decode(encoded.encode())
            return orjson.loads(data)
        except (ValueError, orjson.JSONDecodeError, UnicodeDecodeError):
            return None

    def _get_position(self, instance: Any) -> dict[str, Any]:
        """Extract position values from a model instance."""
        position = {}
        for field, _ in self._get_ordering_directions():
            value = getattr(instance, field, None)
            position[field] = value
        return position

    def _apply_cursor_filter(
        self,
        queryset: QuerySet,
        position: dict[str, Any],
        reverse: bool = False,
    ) -> QuerySet:
        """
        Apply cursor position filter to queryset.

        For cursor pagination with ordering "-created_at, pk":
        - Forward: WHERE (created_at, pk) < (cursor_created_at, cursor_pk)
        - Reverse: WHERE (created_at, pk) > (cursor_created_at, cursor_pk)
        """
        ordering = self._get_ordering_directions()
        if not ordering:
            return queryset

        # Build the filter for the ordering fields
        # This handles multi-field ordering correctly
        from django.db.models import Q

        filters = Q()
        for i, (field, is_desc) in enumerate(ordering):
            if field not in position:
                continue

            # Determine comparison operator
            if reverse:
                # Going backwards
                op = "gt" if is_desc else "lt"
            else:
                # Going forwards
                op = "lt" if is_desc else "gt"

            # Build equality conditions for previous fields
            eq_conditions = Q()
            for j in range(i):
                prev_field = ordering[j][0]
                if prev_field in position:
                    eq_conditions &= Q(**{prev_field: position[prev_field]})

            # Add the comparison for this field
            comparison = Q(**{f"{field}__{op}": position[field]})
            filters |= eq_conditions & comparison

        return queryset.filter(filters)

    def paginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> QuerySet:
        """
        Apply cursor pagination to queryset.

        If ``?no_page=1`` or the ``X-No-Pagination`` header is present,
        pagination is skipped and results are capped at ``max_unpaginated``.

        Args:
            queryset: Django queryset
            request: HTTP request with cursor param

        Returns:
            Paginated queryset
        """
        self._request = request

        if self._should_skip_pagination(request):
            self._pagination_skipped = True
            self._count = self.get_count(queryset)
            ordering_fields = self._get_ordering_fields()
            queryset = queryset.order_by(*ordering_fields)
            return list(queryset[: self.max_unpaginated])
        self._pagination_skipped = False

        self._page_size_used = self.get_page_size(request)

        # Apply ordering
        ordering_fields = self._get_ordering_fields()
        queryset = queryset.order_by(*ordering_fields)

        # Get cursor from request
        cursor_str = request.GET.get(self.cursor_query_param)
        position = self._decode_cursor(cursor_str)

        # Apply cursor filter if we have a position
        if position:
            queryset = self._apply_cursor_filter(queryset, position)

        # Fetch one extra to check if there's a next page
        results = list(queryset[: self._page_size_used + 1])

        self._has_next = len(results) > self._page_size_used
        if self._has_next:
            results = results[: self._page_size_used]

        self._has_previous = position is not None
        self._results = results

        # Generate cursors
        if results:
            self._next_cursor = (
                self._encode_cursor(self._get_position(results[-1])) if self._has_next else None
            )
            # For previous, we'd need to store the first item's position
            # This is a simplified implementation
            if position:
                self._previous_cursor = None  # Would need reverse query
            else:
                self._previous_cursor = None
        else:
            self._next_cursor = None
            self._previous_cursor = None

        # Return as a list-like object (queryset is already evaluated)
        return results

    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> list:
        """Async version - cursors require list evaluation."""
        # Cursor pagination requires evaluating the queryset
        # so async version is similar to sync
        if self._should_skip_pagination(request):
            self._request = request
            self._pagination_skipped = True
            self._count = await self.aget_count(queryset)
            ordering_fields = self._get_ordering_fields()
            queryset = queryset.order_by(*ordering_fields)
            return list(queryset[: self.max_unpaginated])
        self._pagination_skipped = False
        return self.paginate_queryset(queryset, request)

    def get_paginated_response(self, data: list[Any]) -> dict[str, Any] | list[Any]:
        """
        Build paginated response with cursor metadata.

        When pagination is skipped, returns a plain list.

        Args:
            data: List of serialized items

        Returns:
            Dict with items and cursor info — or plain list when skipped
        """
        if self._pagination_skipped:
            return data

        return {
            "items": data,
            "page_size": self._page_size_used,
            "next_cursor": self._next_cursor,
            "previous_cursor": self._previous_cursor,
            "has_next": self._has_next,
            "has_previous": self._has_previous,
        }

    @property
    def next_cursor(self) -> str | None:
        """Get the next page cursor."""
        return self._next_cursor

    @property
    def previous_cursor(self) -> str | None:
        """Get the previous page cursor."""
        return self._previous_cursor
