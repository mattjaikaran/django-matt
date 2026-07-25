"""
Base pagination classes for django-matt.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest

from pydantic import BaseModel


class PaginationResult[T](BaseModel):
    """Standard pagination response structure."""

    items: list[T]
    total: int
    page: int | None = None
    page_size: int | None = None
    pages: int | None = None
    # For limit/offset
    limit: int | None = None
    offset: int | None = None
    # For cursor
    next_cursor: str | None = None
    previous_cursor: str | None = None
    has_next: bool = False
    has_previous: bool = False

    class Config:
        arbitrary_types_allowed = True


@dataclass
class PaginationParams:
    """Parsed pagination parameters from request."""

    # Page number pagination
    page: int | None = None
    page_size: int | None = None
    # Limit/offset pagination
    limit: int | None = None
    offset: int | None = None
    # Cursor pagination
    cursor: str | None = None
    # Common
    ordering: str | None = None


class BasePagination(ABC):
    """
    Abstract base class for pagination.

    Subclasses must implement:
    - paginate_queryset(): Apply pagination to queryset
    - get_paginated_response(): Build response dict

    Conditional pagination:
        Clients can skip pagination by passing ``?no_page=1`` or the
        ``X-No-Pagination`` header. When skipped, results are capped at
        ``max_unpaginated`` (default 10 000) and returned as a plain list
        without pagination metadata.

    Usage:
        class MyPagination(BasePagination):
            page_size = 25

        pagination = MyPagination()
        queryset = pagination.paginate_queryset(queryset, request)
        response = pagination.get_paginated_response(list(queryset))
    """

    # Default page size
    page_size: int = 20
    # Maximum allowed page size
    max_page_size: int = 100
    # Safety cap when pagination is skipped (e.g. CSV export)
    max_unpaginated: int = 10_000
    # Query parameter names
    page_query_param: str = "page"
    page_size_query_param: str = "page_size"
    # Query param / header used to skip pagination
    no_page_query_param: str = "no_page"
    no_page_header: str = "X-No-Pagination"

    def __init__(
        self,
        page_size: int | None = None,
        max_page_size: int | None = None,
        max_unpaginated: int | None = None,
    ):
        if page_size is not None:
            self.page_size = page_size
        if max_page_size is not None:
            self.max_page_size = max_page_size
        if max_unpaginated is not None:
            self.max_unpaginated = max_unpaginated

        # State set during pagination
        self._count: int | None = None
        self._request: HttpRequest | None = None
        self._pagination_skipped: bool = False

    def _should_skip_pagination(self, request: HttpRequest) -> bool:
        """Check if the client requested to skip pagination."""
        if request.GET.get(self.no_page_query_param) == "1":
            return True
        if request.headers.get(self.no_page_header):
            return True
        return False

    def _apply_unpaginated_limit(self, queryset: QuerySet) -> QuerySet:
        """Return the full queryset capped at max_unpaginated."""
        return queryset[: self.max_unpaginated]

    @property
    def pagination_skipped(self) -> bool:
        """Whether pagination was skipped for the last request."""
        return self._pagination_skipped

    def get_page_size(self, request: HttpRequest) -> int:
        """
        Get the page size from request or use default.
        Respects max_page_size limit.

        Uses Rust-parsed ``pagination`` dict when available on
        ``request._parsed_qs``.
        """
        parsed_qs = getattr(request, "_parsed_qs", None)
        raw = None
        if parsed_qs is not None:
            raw = parsed_qs.get("pagination", {}).get(self.page_size_query_param)
        try:
            page_size = (
                int(raw)
                if raw is not None
                else int(request.GET.get(self.page_size_query_param, self.page_size))
            )
        except (ValueError, TypeError):
            page_size = self.page_size

        if page_size <= 0:
            page_size = self.page_size

        return min(page_size, self.max_page_size)

    @abstractmethod
    def paginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> QuerySet:
        """
        Apply pagination to the queryset.

        Args:
            queryset: Django queryset to paginate
            request: HTTP request with pagination params

        Returns:
            Paginated queryset slice
        """

    @abstractmethod
    def get_paginated_response(self, data: list[Any]) -> dict[str, Any]:
        """
        Build the paginated response dictionary.

        Args:
            data: List of serialized items

        Returns:
            Dict with items, count, and pagination metadata
        """

    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> QuerySet:
        """
        Async version of paginate_queryset.
        Default implementation calls sync version.
        """
        if self._should_skip_pagination(request):
            self._request = request
            self._pagination_skipped = True
            self._count = await self.aget_count(queryset)
            return self._apply_unpaginated_limit(queryset)
        self._pagination_skipped = False
        return self.paginate_queryset(queryset, request)

    def get_count(self, queryset: QuerySet) -> int:
        """Get total count of queryset."""
        try:
            return queryset.count()
        except (AttributeError, TypeError):
            return len(queryset)

    async def aget_count(self, queryset: QuerySet) -> int:
        """Async version of get_count."""
        try:
            return await queryset.acount()
        except (AttributeError, TypeError):
            return self.get_count(queryset)
