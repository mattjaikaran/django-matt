"""
Limit/offset pagination for django-matt.

Simple offset-based pagination: ?limit=20&offset=40
"""

from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest

from .base import BasePagination


class LimitOffsetPagination(BasePagination):
    """
    Limit/offset based pagination.

    Query parameters:
        - limit: Maximum number of items to return
        - offset: Number of items to skip

    Example:
        GET /api/users?limit=25&offset=50

    Response:
        {
            "items": [...],
            "total": 150,
            "limit": 25,
            "offset": 50,
            "has_next": true,
            "has_previous": true
        }

    Usage:
        pagination = LimitOffsetPagination(default_limit=25, max_limit=100)

        # In view
        queryset = pagination.paginate_queryset(User.objects.all(), request)
        users = [UserSchema.from_orm(u) for u in queryset]
        return pagination.get_paginated_response(users)

    Note:
        This is less efficient than cursor pagination for large datasets
        because offset queries still need to scan skipped rows.
    """

    default_limit: int = 20
    max_limit: int = 100
    limit_query_param: str = "limit"
    offset_query_param: str = "offset"

    def __init__(
        self,
        default_limit: int | None = None,
        max_limit: int | None = None,
        limit_query_param: str | None = None,
        offset_query_param: str | None = None,
    ):
        # Map to base class attributes
        super().__init__(
            page_size=default_limit or self.default_limit,
            max_page_size=max_limit or self.max_limit,
        )
        self.default_limit = self.page_size
        self.max_limit = self.max_page_size

        if limit_query_param is not None:
            self.limit_query_param = limit_query_param
        if offset_query_param is not None:
            self.offset_query_param = offset_query_param

        # State
        self._limit: int = self.default_limit
        self._offset: int = 0

    def get_limit(self, request: HttpRequest) -> int:
        """Get the limit from request or use default."""
        try:
            limit = int(request.GET.get(self.limit_query_param, self.default_limit))
        except (ValueError, TypeError):
            limit = self.default_limit

        if limit <= 0:
            limit = self.default_limit

        return min(limit, self.max_limit)

    def get_offset(self, request: HttpRequest) -> int:
        """Get the offset from request, defaulting to 0."""
        try:
            offset = int(request.GET.get(self.offset_query_param, 0))
        except (ValueError, TypeError):
            offset = 0
        return max(0, offset)

    def paginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> QuerySet:
        """
        Apply limit/offset pagination to queryset.

        Args:
            queryset: Django queryset
            request: HTTP request with limit/offset params

        Returns:
            Sliced queryset
        """
        self._request = request
        self._count = self.get_count(queryset)
        self._limit = self.get_limit(request)
        self._offset = self.get_offset(request)

        # Ensure offset doesn't exceed count
        if self._offset >= self._count and self._count > 0:
            self._offset = max(0, self._count - self._limit)

        return queryset[self._offset : self._offset + self._limit]

    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> QuerySet:
        """Async version of paginate_queryset."""
        self._request = request
        self._count = await self.aget_count(queryset)
        self._limit = self.get_limit(request)
        self._offset = self.get_offset(request)

        if self._offset >= self._count and self._count > 0:
            self._offset = max(0, self._count - self._limit)

        return queryset[self._offset : self._offset + self._limit]

    def get_paginated_response(self, data: list[Any]) -> dict[str, Any]:
        """
        Build paginated response with limit/offset metadata.

        Args:
            data: List of serialized items

        Returns:
            Dict with items, total, limit/offset info
        """
        count = self._count or 0
        return {
            "items": data,
            "total": count,
            "limit": self._limit,
            "offset": self._offset,
            "has_next": self._offset + self._limit < count,
            "has_previous": self._offset > 0,
        }

    @property
    def count(self) -> int | None:
        """Total count of items."""
        return self._count

    def get_next_offset(self) -> int | None:
        """Get offset for next page, or None if no next page."""
        if self._count is None:
            return None
        next_offset = self._offset + self._limit
        if next_offset >= self._count:
            return None
        return next_offset

    def get_previous_offset(self) -> int | None:
        """Get offset for previous page, or None if no previous page."""
        if self._offset <= 0:
            return None
        return max(0, self._offset - self._limit)
