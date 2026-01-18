"""
ListView for listing resources with pagination, filtering, and search.
"""

from typing import Any

from django.db import models
from django.http import HttpRequest

from django_matt.views.base import APIView


class ListView(APIView):
    """
    View for listing resources.

    Returns a paginated list of resources with optional filtering.

    Example (simple):
        class UserViewSet(APIViewSet):
            list_users = ListView(
                response_schema=UserListSchema,
                pagination=True,
                page_size=20,
            )

    Example (with pagination class):
        from django_matt.pagination import CursorPagination

        class UserViewSet(APIViewSet):
            list_users = ListView(
                response_schema=UserSchema,
                pagination_class=CursorPagination(ordering='-created_at'),
            )

    Example (with filter backends):
        from django_matt.filtering import DjangoFilterBackend, SearchBackend, OrderingBackend

        class UserViewSet(APIViewSet):
            filter_backends = [DjangoFilterBackend(), SearchBackend(), OrderingBackend()]
            filter_fields = ['email', 'is_active', 'role']
            search_fields = ['email', 'first_name', 'last_name']
            ordering_fields = ['email', 'created_at']
            ordering = '-created_at'

            list_users = ListView(response_schema=UserSchema)

    Example (with FilterSet):
        from django_matt.filtering import FilterSet, CharFilter, BooleanFilter

        class UserFilter(FilterSet):
            email = CharFilter(lookup_expr='icontains')
            is_active = BooleanFilter()

            class Meta:
                model = User
                fields = ['email', 'is_active']

        class UserViewSet(APIViewSet):
            filterset_class = UserFilter
            list_users = ListView(response_schema=UserSchema)

    Attributes:
        pagination: Enable pagination (default: True)
        pagination_class: Pagination class instance (PageNumberPagination, etc.)
        page_size: Default page size (default: 20)
        max_page_size: Maximum allowed page size (default: 100)
        ordering: Default ordering field(s)
        ordering_fields: Fields allowed for ordering
        filter_fields: Fields that can be filtered via query params
        filter_backends: List of filter backend instances
        filterset_class: FilterSet class for declarative filtering
        search_fields: Fields to search in via ?search= param
    """

    path: str = ""
    methods: list[str] = ["GET"]

    # Pagination settings
    pagination: bool = True
    pagination_class: Any | None = None  # Pagination class instance
    page_size: int = 20
    max_page_size: int = 100

    # Filtering and ordering
    ordering: str | list[str] | None = None
    ordering_fields: list[str] | None = None  # Allowed fields for ordering
    filter_fields: list[str] | None = None
    filter_backends: list[Any] | None = None  # List of filter backend instances
    filterset_class: type | None = None  # FilterSet class
    search_fields: list[str] | None = None

    def __init__(
        self,
        pagination: bool | None = None,
        pagination_class: Any | None = None,
        page_size: int | None = None,
        max_page_size: int | None = None,
        ordering: str | list[str] | None = None,
        ordering_fields: list[str] | None = None,
        filter_fields: list[str] | None = None,
        filter_backends: list[Any] | None = None,
        filterset_class: type | None = None,
        search_fields: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if pagination is not None:
            self.pagination = pagination
        if pagination_class is not None:
            self.pagination_class = pagination_class
        if page_size is not None:
            self.page_size = page_size
        if max_page_size is not None:
            self.max_page_size = max_page_size
        if ordering is not None:
            self.ordering = ordering
        if ordering_fields is not None:
            self.ordering_fields = ordering_fields
        if filter_fields is not None:
            self.filter_fields = filter_fields
        if filter_backends is not None:
            self.filter_backends = filter_backends
        if filterset_class is not None:
            self.filterset_class = filterset_class
        if search_fields is not None:
            self.search_fields = search_fields

    def _get_filter_backends(self) -> list[Any]:
        """Get filter backends from view or viewset."""
        if self.filter_backends is not None:
            return self.filter_backends
        if self._viewset and hasattr(self._viewset, "filter_backends"):
            return self._viewset.filter_backends or []
        return []

    def _get_filterset_class(self) -> type | None:
        """Get FilterSet class from view or viewset."""
        if self.filterset_class is not None:
            return self.filterset_class
        if self._viewset and hasattr(self._viewset, "filterset_class"):
            return self._viewset.filterset_class
        return None

    def _get_pagination_class(self) -> Any | None:
        """Get pagination class from view or viewset."""
        if self.pagination_class is not None:
            return self.pagination_class
        if self._viewset and hasattr(self._viewset, "pagination_class"):
            return self._viewset.pagination_class
        return None

    async def handle(self, request: HttpRequest, **kwargs) -> dict[str, Any]:
        """Handle GET request to list resources."""
        queryset = self.get_queryset(request)

        # Apply filter backends if configured
        filter_backends = self._get_filter_backends()
        if filter_backends:
            queryset = await self._apply_filter_backends(queryset, request, filter_backends)
        else:
            # Fall back to simple filtering
            queryset = self._apply_ordering(queryset, request)
            queryset = self._apply_filters(queryset, request)
            queryset = self._apply_search(queryset, request)

        # Get total count before pagination
        total = await self._count_queryset(queryset)

        # Apply pagination
        pagination_class = self._get_pagination_class()
        if pagination_class and self.pagination:
            # Use pluggable pagination class
            queryset = await pagination_class.apaginate_queryset(queryset, request)
            items = self.serialize_list(queryset)
            response = pagination_class.get_paginated_response(items)
            response["total"] = total
            response["count"] = len(items)
        elif self.pagination:
            # Use simple built-in pagination
            queryset, pagination_info = self._apply_pagination(queryset, request)
            items = self.serialize_list(queryset)
            response = {
                "items": items,
                "count": len(items),
                "total": total,
            }
            if pagination_info:
                response.update(pagination_info)
        else:
            # No pagination
            items = self.serialize_list(queryset)
            response = {
                "items": items,
                "count": len(items),
                "total": total,
            }

        return response

    async def _apply_filter_backends(
        self,
        queryset: models.QuerySet,
        request: HttpRequest,
        backends: list[Any],
    ) -> models.QuerySet:
        """Apply all configured filter backends."""
        for backend in backends:
            if hasattr(backend, "afilter_queryset"):
                queryset = await backend.afilter_queryset(request, queryset, self)
            else:
                queryset = backend.filter_queryset(request, queryset, self)
        return queryset

    def _apply_ordering(self, queryset: models.QuerySet, request: HttpRequest) -> models.QuerySet:
        """Apply ordering to the queryset."""
        order_param = request.GET.get("ordering") or request.GET.get("order_by")

        if order_param:
            fields = order_param.split(",")
            valid_fields = []
            for field in fields:
                field_name = field.lstrip("-")
                if self._is_valid_order_field(field_name):
                    valid_fields.append(field)
            if valid_fields:
                return queryset.order_by(*valid_fields)

        if self.ordering:
            if isinstance(self.ordering, str):
                return queryset.order_by(self.ordering)
            return queryset.order_by(*self.ordering)

        return queryset

    def _apply_filters(self, queryset: models.QuerySet, request: HttpRequest) -> models.QuerySet:
        """Apply filters from query parameters."""
        # Check for FilterSet first
        filterset_class = self._get_filterset_class()
        if filterset_class:
            filterset = filterset_class(
                data=dict(request.GET),
                queryset=queryset,
                request=request,
            )
            return filterset.qs

        # Fall back to simple filtering
        filter_fields = self.filter_fields or []

        if not filter_fields and self._viewset:
            model = self._viewset.model
            filter_fields = [f.name for f in model._meta.fields]

        filters = {}
        for key, value in request.GET.items():
            if key in (
                "page",
                "page_size",
                "ordering",
                "order_by",
                "search",
                "cursor",
                "limit",
                "offset",
            ):
                continue

            base_field = key.split("__")[0]
            if base_field in filter_fields:
                # Handle comma-separated values for __in lookups
                if key.endswith("__in"):
                    value = [v.strip() for v in value.split(",")]
                filters[key] = value

        if filters:
            queryset = queryset.filter(**filters)

        return queryset

    def _apply_search(self, queryset: models.QuerySet, request: HttpRequest) -> models.QuerySet:
        """Apply search filter."""
        search = request.GET.get("search")
        if not search or not self.search_fields:
            return queryset

        from django.db.models import Q

        query = Q()
        for field in self.search_fields:
            query |= Q(**{f"{field}__icontains": search})

        return queryset.filter(query)

    def _apply_pagination(
        self, queryset: models.QuerySet, request: HttpRequest
    ) -> tuple[models.QuerySet, dict[str, Any]]:
        """Apply pagination to the queryset."""
        try:
            page = int(request.GET.get("page", 1))
        except (TypeError, ValueError):
            page = 1

        try:
            page_size = int(request.GET.get("page_size", self.page_size))
        except (TypeError, ValueError):
            page_size = self.page_size

        page_size = min(page_size, self.max_page_size)
        page_size = max(page_size, 1)

        offset = (page - 1) * page_size
        paginated = queryset[offset : offset + page_size]

        pagination_info = {
            "page": page,
            "page_size": page_size,
        }

        return paginated, pagination_info

    async def _count_queryset(self, queryset: models.QuerySet) -> int:
        """Get the total count of items in the queryset."""
        # If queryset is already a list (from cursor pagination), return length
        if isinstance(queryset, list):
            return len(queryset)
        if hasattr(queryset, "acount"):
            return await queryset.acount()
        return queryset.count()

    def _is_valid_order_field(self, field_name: str) -> bool:
        """Check if a field is valid for ordering."""
        # Check ordering_fields first
        if self.ordering_fields is not None:
            return field_name in self.ordering_fields

        if self._viewset is None:
            return False

        # Check viewset ordering_fields
        if hasattr(self._viewset, "ordering_fields") and self._viewset.ordering_fields:
            return field_name in self._viewset.ordering_fields

        # Fall back to model fields
        model = self._viewset.model
        field_names = [f.name for f in model._meta.fields]
        return field_name in field_names
