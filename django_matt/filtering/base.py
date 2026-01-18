"""
Base filter backend for django-matt.
"""

from abc import ABC, abstractmethod
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest


class BaseFilterBackend(ABC):
    """
    Abstract base class for filter backends.

    Filter backends are responsible for filtering querysets based on
    request parameters.

    Usage:
        class MyFilterBackend(BaseFilterBackend):
            def filter_queryset(self, request, queryset, view):
                # Apply filters based on request params
                return queryset.filter(...)

        # In view
        backend = MyFilterBackend()
        queryset = backend.filter_queryset(request, queryset, view)
    """

    @abstractmethod
    def filter_queryset(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        view: Any = None,
    ) -> QuerySet:
        """
        Filter the queryset based on request parameters.

        Args:
            request: HTTP request with query parameters
            queryset: Django queryset to filter
            view: Optional view instance for context

        Returns:
            Filtered queryset
        """

    async def afilter_queryset(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        view: Any = None,
    ) -> QuerySet:
        """
        Async version of filter_queryset.
        Default implementation calls sync version.
        """
        return self.filter_queryset(request, queryset, view)

    def get_schema_fields(self, view: Any = None) -> list[dict[str, Any]]:
        """
        Return OpenAPI schema fields for this filter backend.

        Override this to add filter parameters to API documentation.

        Returns:
            List of parameter dicts for OpenAPI schema
        """
        return []

    def get_schema_operation_parameters(self, view: Any = None) -> list[dict[str, Any]]:
        """
        Alias for get_schema_fields for compatibility.
        """
        return self.get_schema_fields(view)
