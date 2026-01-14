"""
ReadView for retrieving a single resource.
"""

from typing import Any

from django.db import models
from django.http import HttpRequest

from django_matt.core.errors import NotFoundAPIError
from django_matt.views.base import APIView


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
        lookup_value = kwargs.get(self.lookup_field) or kwargs.get("id")
        
        if lookup_value is None:
            raise ValueError(f"Missing {self.lookup_field} in URL")
        
        instance = await self._get_instance(lookup_value)
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
