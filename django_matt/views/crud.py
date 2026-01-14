"""
CRUD view classes for Django Matt.

Provides composable view classes for common CRUD operations:
- ListView: List all resources
- CreateView: Create a new resource
- ReadView: Retrieve a single resource
- UpdateView: Update a resource (full replacement)
- PatchView: Partially update a resource
- DeleteView: Delete a resource
"""

from typing import Any

from django.db import models
from django.http import HttpRequest, JsonResponse

from django_matt.core.errors import NotFoundAPIError
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
        # Check for ordering in query params
        order_param = request.GET.get("ordering") or request.GET.get("order_by")
        
        if order_param:
            # Validate ordering field
            fields = order_param.split(",")
            valid_fields = []
            for field in fields:
                field_name = field.lstrip("-")
                if self._is_valid_order_field(field_name):
                    valid_fields.append(field)
            if valid_fields:
                return queryset.order_by(*valid_fields)
        
        # Fall back to default ordering
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
        
        # Also allow filtering by any model field if filter_fields not specified
        if not filter_fields and self._viewset:
            model = self._viewset.model
            filter_fields = [f.name for f in model._meta.fields]
        
        filters = {}
        for key, value in request.GET.items():
            # Skip special params
            if key in ("page", "page_size", "ordering", "order_by", "search"):
                continue
            
            # Parse filter operators (e.g., field__gte, field__contains)
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
        # Get page number and size from query params
        try:
            page = int(request.GET.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        
        try:
            page_size = int(request.GET.get("page_size", self.page_size))
        except (TypeError, ValueError):
            page_size = self.page_size
        
        # Clamp page size
        page_size = min(page_size, self.max_page_size)
        page_size = max(page_size, 1)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Slice queryset
        paginated = queryset[offset:offset + page_size]
        
        pagination_info = {
            "page": page,
            "page_size": page_size,
        }
        
        return paginated, pagination_info
    
    async def _count_queryset(self, queryset: models.QuerySet) -> int:
        """Get the total count of items in the queryset."""
        # Use async count if available (Django 4.1+)
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


class CreateView(APIView):
    """
    View for creating a new resource.
    
    Example:
        class UserViewSet(APIViewSet):
            create_user = CreateView(
                request_schema=UserCreateSchema,
                response_schema=UserSchema,
            )
    """
    
    path: str = ""
    methods: list[str] = ["POST"]
    
    async def handle(self, request: HttpRequest, **kwargs) -> dict[str, Any]:
        """Handle POST request to create a resource."""
        # Validate request body
        data = self.validate_request(request)
        
        if data is None:
            raise ValueError("Request body is required")
        
        # Get the model
        model = self.get_model()
        
        # Create the instance
        data_dict = data.model_dump(exclude_unset=True)
        
        # Allow ViewSet to customize creation
        if self._viewset and hasattr(self._viewset, "perform_create"):
            instance = await self._viewset.perform_create(data_dict, request)
        else:
            instance = model(**data_dict)
            await self._save_instance(instance)
        
        # Serialize and return
        return self.serialize(instance)
    
    async def _save_instance(self, instance: models.Model):
        """Save the model instance."""
        if hasattr(instance, "asave"):
            await instance.asave()
        else:
            instance.save()


class ReadView(APIView):
    """
    View for retrieving a single resource.
    
    Example:
        class UserViewSet(APIViewSet):
            read_user = ReadView(
                path="{id}",
                response_schema=UserSchema,
            )
    """
    
    path: str = "{id}"
    methods: list[str] = ["GET"]
    lookup_field: str = "id"
    
    def __init__(self, lookup_field: str | None = None, **kwargs):
        super().__init__(**kwargs)
        if lookup_field is not None:
            self.lookup_field = lookup_field
    
    async def handle(self, request: HttpRequest, **kwargs) -> dict[str, Any]:
        """Handle GET request to retrieve a resource."""
        # Get the lookup value from URL kwargs
        lookup_value = kwargs.get(self.lookup_field) or kwargs.get("id")
        
        if lookup_value is None:
            raise ValueError(f"Missing {self.lookup_field} in URL")
        
        # Get the instance
        instance = await self._get_instance(lookup_value)
        
        # Serialize and return
        return self.serialize(instance)
    
    async def _get_instance(self, lookup_value: Any) -> models.Model:
        """Get the model instance by lookup value."""
        queryset = self.get_queryset(None)
        
        try:
            if hasattr(queryset, "aget"):
                return await queryset.aget(**{self.lookup_field: lookup_value})
            return queryset.get(**{self.lookup_field: lookup_value})
        except queryset.model.DoesNotExist:
            model_name = self.get_model().__name__
            raise NotFoundAPIError(
                message=f"{model_name} not found",
                resource_type=model_name,
                resource_id=str(lookup_value),
            )


# Alias for ReadView (common naming convention)
RetrieveView = ReadView


class UpdateView(APIView):
    """
    View for updating a resource (full replacement).
    
    Example:
        class UserViewSet(APIViewSet):
            update_user = UpdateView(
                path="{id}",
                request_schema=UserUpdateSchema,
                response_schema=UserSchema,
            )
    """
    
    path: str = "{id}"
    methods: list[str] = ["PUT"]
    lookup_field: str = "id"
    
    def __init__(self, lookup_field: str | None = None, **kwargs):
        super().__init__(**kwargs)
        if lookup_field is not None:
            self.lookup_field = lookup_field
    
    async def handle(self, request: HttpRequest, **kwargs) -> dict[str, Any]:
        """Handle PUT request to update a resource."""
        # Get the lookup value
        lookup_value = kwargs.get(self.lookup_field) or kwargs.get("id")
        
        if lookup_value is None:
            raise ValueError(f"Missing {self.lookup_field} in URL")
        
        # Validate request body
        data = self.validate_request(request)
        if data is None:
            raise ValueError("Request body is required")
        
        # Get the instance
        instance = await self._get_instance(lookup_value)
        
        # Update the instance
        data_dict = data.model_dump(exclude_unset=True)
        
        # Allow ViewSet to customize update
        if self._viewset and hasattr(self._viewset, "perform_update"):
            instance = await self._viewset.perform_update(instance, data_dict, request)
        else:
            for key, value in data_dict.items():
                setattr(instance, key, value)
            await self._save_instance(instance)
        
        # Serialize and return
        return self.serialize(instance)
    
    async def _get_instance(self, lookup_value: Any) -> models.Model:
        """Get the model instance by lookup value."""
        queryset = self.get_queryset(None)
        
        try:
            if hasattr(queryset, "aget"):
                return await queryset.aget(**{self.lookup_field: lookup_value})
            return queryset.get(**{self.lookup_field: lookup_value})
        except queryset.model.DoesNotExist:
            model_name = self.get_model().__name__
            raise NotFoundAPIError(
                message=f"{model_name} not found",
                resource_type=model_name,
                resource_id=str(lookup_value),
            )
    
    async def _save_instance(self, instance: models.Model):
        """Save the model instance."""
        if hasattr(instance, "asave"):
            await instance.asave()
        else:
            instance.save()


class PatchView(UpdateView):
    """
    View for partially updating a resource.
    
    Similar to UpdateView but uses PATCH method and only updates
    provided fields.
    
    Example:
        class UserViewSet(APIViewSet):
            patch_user = PatchView(
                path="{id}",
                request_schema=UserPatchSchema,
                response_schema=UserSchema,
            )
    """
    
    methods: list[str] = ["PATCH"]
    
    async def handle(self, request: HttpRequest, **kwargs) -> dict[str, Any]:
        """Handle PATCH request to partially update a resource."""
        # Get the lookup value
        lookup_value = kwargs.get(self.lookup_field) or kwargs.get("id")
        
        if lookup_value is None:
            raise ValueError(f"Missing {self.lookup_field} in URL")
        
        # Validate request body (allow partial data)
        data = self.validate_request(request)
        if data is None:
            raise ValueError("Request body is required")
        
        # Get the instance
        instance = await self._get_instance(lookup_value)
        
        # Only update provided fields
        data_dict = data.model_dump(exclude_unset=True, exclude_none=True)
        
        # Allow ViewSet to customize update
        if self._viewset and hasattr(self._viewset, "perform_update"):
            instance = await self._viewset.perform_update(instance, data_dict, request)
        else:
            for key, value in data_dict.items():
                setattr(instance, key, value)
            await self._save_instance(instance)
        
        # Serialize and return
        return self.serialize(instance)


class DeleteView(APIView):
    """
    View for deleting a resource.
    
    Example:
        class UserViewSet(APIViewSet):
            delete_user = DeleteView(path="{id}")
    """
    
    path: str = "{id}"
    methods: list[str] = ["DELETE"]
    lookup_field: str = "id"
    
    # Response options
    return_deleted: bool = False  # Return the deleted object's data
    
    def __init__(
        self,
        lookup_field: str | None = None,
        return_deleted: bool | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if lookup_field is not None:
            self.lookup_field = lookup_field
        if return_deleted is not None:
            self.return_deleted = return_deleted
    
    async def handle(self, request: HttpRequest, **kwargs) -> dict[str, Any]:
        """Handle DELETE request to delete a resource."""
        # Get the lookup value
        lookup_value = kwargs.get(self.lookup_field) or kwargs.get("id")
        
        if lookup_value is None:
            raise ValueError(f"Missing {self.lookup_field} in URL")
        
        # Get the instance
        instance = await self._get_instance(lookup_value)
        
        # Optionally serialize before deletion
        deleted_data = None
        if self.return_deleted:
            deleted_data = self.serialize(instance)
        
        # Allow ViewSet to customize deletion
        if self._viewset and hasattr(self._viewset, "perform_delete"):
            await self._viewset.perform_delete(instance, request)
        else:
            await self._delete_instance(instance)
        
        # Return response
        if self.return_deleted and deleted_data:
            return {"deleted": True, "data": deleted_data}
        return {"deleted": True}
    
    async def _get_instance(self, lookup_value: Any) -> models.Model:
        """Get the model instance by lookup value."""
        queryset = self.get_queryset(None)
        
        try:
            if hasattr(queryset, "aget"):
                return await queryset.aget(**{self.lookup_field: lookup_value})
            return queryset.get(**{self.lookup_field: lookup_value})
        except queryset.model.DoesNotExist:
            model_name = self.get_model().__name__
            raise NotFoundAPIError(
                message=f"{model_name} not found",
                resource_type=model_name,
                resource_id=str(lookup_value),
            )
    
    async def _delete_instance(self, instance: models.Model):
        """Delete the model instance."""
        if hasattr(instance, "adelete"):
            await instance.adelete()
        else:
            instance.delete()
