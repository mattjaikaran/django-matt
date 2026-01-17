"""
Base pagination classes for django-matt.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from django.db.models import QuerySet
from django.http import HttpRequest
from pydantic import BaseModel

T = TypeVar("T")


class PaginationResult(BaseModel, Generic[T]):
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
    # Query parameter names
    page_query_param: str = "page"
    page_size_query_param: str = "page_size"

    def __init__(
        self,
        page_size: int | None = None,
        max_page_size: int | None = None,
    ):
        if page_size is not None:
            self.page_size = page_size
        if max_page_size is not None:
            self.max_page_size = max_page_size

        # State set during pagination
        self._count: int | None = None
        self._request: HttpRequest | None = None

    def get_page_size(self, request: HttpRequest) -> int:
        """
        Get the page size from request or use default.
        Respects max_page_size limit.
        """
        try:
            page_size = int(
                request.GET.get(self.page_size_query_param, self.page_size)
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
        pass

    @abstractmethod
    def get_paginated_response(self, data: list[Any]) -> dict[str, Any]:
        """
        Build the paginated response dictionary.

        Args:
            data: List of serialized items

        Returns:
            Dict with items, count, and pagination metadata
        """
        pass

    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        request: HttpRequest,
    ) -> QuerySet:
        """
        Async version of paginate_queryset.
        Default implementation calls sync version.
        """
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
