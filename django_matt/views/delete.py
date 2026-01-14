"""
DeleteView for deleting resources.
"""

from typing import Any

from django.db import models
from django.http import HttpRequest

from django_matt.core.errors import NotFoundAPIError
from django_matt.views.base import APIView


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
        lookup_value = kwargs.get(self.lookup_field) or kwargs.get("id")
        
        if lookup_value is None:
            raise ValueError(f"Missing {self.lookup_field} in URL")
        
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
