"""
Page number pagination for django-matt.

Standard page-based pagination: ?page=1&page_size=20
"""

import math
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest

from .base import BasePagination


class PageNumberPagination(BasePagination):
    """
    Page number based pagination.

    Query parameters:
        - page: Page number (1-indexed)
        - page_size: Number of items per page

    Example:
        GET /api/users?page=2&page_size=25

    Response:
        {
            "items": [...],
            "total": 150,
            "page": 2,
            "page_size": 25,
            "pages": 6,
            "has_next": true,
            "has_previous": true
        }

    Usage:
        pagination = PageNumberPagination(page_size=25)

        # In view
        queryset = pagination.paginate_queryset(User.objects.all(), request)
        users = [UserSchema.from_orm(u) for u in queryset]
        return pagination.get_paginated_response(users)
    """

    page_query_param: str = "page"
    page_size_query_param: str = "page_size"
    # Allow client to request all results with page_size=0
    allow_empty_page_size: bool = False

    def __init__(
        self,
        page_size: int | None = None,
        max_page_size: int | None = None,
        max_unpaginated: int | None = None,
        page_query_param: str | None = None,
        page_size_query_param: str | None = None,
    ):
        super().__init__(page_size, max_page_size, max_unpaginated)
        if page_query_param is not None:
            self.page_query_param = page_query_param
        if page_size_query_param is not None:
            self.page_size_query_param = page_size_query_param

        # State
        self._page: int = 1
        self._page_size: int = self.page_size
        self._total_pages: int = 1

    def get_page_number(self, request: HttpRequest) -> int:
        """Get the page number from request, defaulting to 1."""
        try:
            page = int(request.GET.get(self.page_query_param, 1))
        except (ValueError, TypeError):
            page = 1
        return max(1, page)

    def paginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> QuerySet:
        """
        Apply page number pagination to queryset.

        If ``?no_page=1`` or the ``X-No-Pagination`` header is present,
        pagination is skipped and results are capped at ``max_unpaginated``.

        Args:
            queryset: Django queryset
            request: HTTP request with page/page_size params

        Returns:
            Sliced queryset for the requested page
        """
        self._request = request

        if self._should_skip_pagination(request):
            self._pagination_skipped = True
            self._count = self.get_count(queryset)
            return self._apply_unpaginated_limit(queryset)
        self._pagination_skipped = False

        self._count = self.get_count(queryset)
        self._page = self.get_page_number(request)
        self._page_size = self.get_page_size(request)

        if self._page_size == 0 and self.allow_empty_page_size:
            # Return all results
            self._total_pages = 1
            return queryset

        self._total_pages = max(1, math.ceil(self._count / self._page_size))

        # Clamp page to valid range
        self._page = min(self._page, self._total_pages)

        offset = (self._page - 1) * self._page_size
        return queryset[offset : offset + self._page_size]

    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> QuerySet:
        """Async version of paginate_queryset."""
        self._request = request

        if self._should_skip_pagination(request):
            self._pagination_skipped = True
            self._count = await self.aget_count(queryset)
            return self._apply_unpaginated_limit(queryset)
        self._pagination_skipped = False

        self._count = await self.aget_count(queryset)
        self._page = self.get_page_number(request)
        self._page_size = self.get_page_size(request)

        if self._page_size == 0 and self.allow_empty_page_size:
            self._total_pages = 1
            return queryset

        self._total_pages = max(1, math.ceil(self._count / self._page_size))

        self._page = min(self._page, self._total_pages)

        offset = (self._page - 1) * self._page_size
        return queryset[offset : offset + self._page_size]

    def get_paginated_response(self, data: list[Any]) -> dict[str, Any] | list[Any]:
        """
        Build paginated response with page metadata.

        When pagination is skipped, returns a plain list.

        Args:
            data: List of serialized items

        Returns:
            Dict with items, total, page info — or plain list when skipped
        """
        if self._pagination_skipped:
            return data

        return {
            "items": data,
            "total": self._count or 0,
            "page": self._page,
            "page_size": self._page_size,
            "pages": self._total_pages,
            "has_next": self._page < self._total_pages,
            "has_previous": self._page > 1,
        }

    @property
    def count(self) -> int | None:
        """Total count of items."""
        return self._count

    @property
    def num_pages(self) -> int:
        """Total number of pages."""
        return self._total_pages
