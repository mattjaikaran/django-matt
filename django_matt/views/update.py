"""
UpdateView and PatchView for updating resources.
"""

from typing import Any

from django.db import models
from django.http import HttpRequest

from django_matt.core.errors import NotFoundAPIError
from django_matt.views.base import APIView


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
        lookup_value = kwargs.get(self.lookup_field) or kwargs.get("id")

        if lookup_value is None:
            raise ValueError(f"Missing {self.lookup_field} in URL")

        data = self.validate_request(request)
        if data is None:
            raise ValueError("Request body is required")

        instance = await self._get_instance(lookup_value)
        data_dict = data.model_dump(exclude_unset=True)

        if self._viewset and hasattr(self._viewset, "perform_update"):
            instance = await self._viewset.perform_update(instance, data_dict, request)
        else:
            for key, value in data_dict.items():
                setattr(instance, key, value)
            await self._save_instance(instance)

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
        lookup_value = kwargs.get(self.lookup_field) or kwargs.get("id")

        if lookup_value is None:
            raise ValueError(f"Missing {self.lookup_field} in URL")

        data = self.validate_request(request)
        if data is None:
            raise ValueError("Request body is required")

        instance = await self._get_instance(lookup_value)

        # Only update provided fields (exclude_none for partial updates)
        data_dict = data.model_dump(exclude_unset=True, exclude_none=True)

        if self._viewset and hasattr(self._viewset, "perform_update"):
            instance = await self._viewset.perform_update(instance, data_dict, request)
        else:
            for key, value in data_dict.items():
                setattr(instance, key, value)
            await self._save_instance(instance)

        return self.serialize(instance)
