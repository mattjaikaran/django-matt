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
    
    Example:
        class UserViewSet(APIViewSet):
            list_users = ListView(
                response_schema=UserListSchema,
                pagination=True,
                page_size=20,
            )
    
    Attributes:
        pagination: Enable pagination (default: True)
        page_size: Default page size (default: 20)
        max_page_size: Maximum allowed page size (default: 100)
        ordering: Default ordering field(s)
        filter_fields: Fields that can be filtered via query params
        search_fields: Fields to search in via ?search= param
    """
    
    path: str = ""
    methods: list[str] = ["GET"]
    
    # Pagination settings
    pagination: bool = True
    page_size: int = 20
    max_page_size: int = 100
    
    # Filtering and ordering
    ordering: str | list[str] | None = None
    filter_fields: list[str] | None = None
    search_fields: list[str] | None = None
    
    def __init__(
        self,
        pagination: bool | None = None,
        page_size: int | None = None,
        max_page_size: int | None = None,
        ordering: str | list[str] | None = None,
        filter_fields: list[str] | None = None,
        search_fields: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if pagination is not None:
            self.pagination = pagination
        if page_size is not None:
            self.page_size = page_size
        if max_page_size is not None:
            self.max_page_size = max_page_size
        if ordering is not None:
            self.ordering = ordering
        if filter_fields is not None:
            self.filter_fields = filter_fields
        if search_fields is not None:
            self.search_fields = search_fields
    
    async def handle(self, request: HttpRequest, **kwargs) -> dict[str, Any]:
        """Handle GET request to list resources."""
        queryset = self.get_queryset(request)
        
        # Apply ordering
        queryset = self._apply_ordering(queryset, request)
        
        # Apply filtering
        queryset = self._apply_filters(queryset, request)
        
        # Apply search
        queryset = self._apply_search(queryset, request)
        
        # Get total count before pagination
        total = await self._count_queryset(queryset)
        
        # Apply pagination
        if self.pagination:
            queryset, pagination_info = self._apply_pagination(queryset, request)
        else:
            pagination_info = None
        
        # Serialize results
        items = self.serialize_list(queryset)
        
        # Build response
        response = {
            "items": items,
            "count": len(items),
            "total": total,
        }
        
        if pagination_info:
            response.update(pagination_info)
        
        return response
    
    def _apply_ordering(
        self, queryset: models.QuerySet, request: HttpRequest
    ) -> models.QuerySet:
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
    
    def _apply_filters(
        self, queryset: models.QuerySet, request: HttpRequest
    ) -> models.QuerySet:
        """Apply filters from query parameters."""
        filter_fields = self.filter_fields or []
        
        if not filter_fields and self._viewset:
            model = self._viewset.model
            filter_fields = [f.name for f in model._meta.fields]
        
        filters = {}
        for key, value in request.GET.items():
            if key in ("page", "page_size", "ordering", "order_by", "search"):
                continue
            
            base_field = key.split("__")[0]
            if base_field in filter_fields:
                filters[key] = value
        
        if filters:
            queryset = queryset.filter(**filters)
        
        return queryset
    
    def _apply_search(
        self, queryset: models.QuerySet, request: HttpRequest
    ) -> models.QuerySet:
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
        paginated = queryset[offset:offset + page_size]
        
        pagination_info = {
            "page": page,
            "page_size": page_size,
        }
        
        return paginated, pagination_info
    
    async def _count_queryset(self, queryset: models.QuerySet) -> int:
        """Get the total count of items in the queryset."""
        if hasattr(queryset, "acount"):
            return await queryset.acount()
        return queryset.count()
    
    def _is_valid_order_field(self, field_name: str) -> bool:
        """Check if a field is valid for ordering."""
        if self._viewset is None:
            return False
        
        model = self._viewset.model
        field_names = [f.name for f in model._meta.fields]
        return field_name in field_names
