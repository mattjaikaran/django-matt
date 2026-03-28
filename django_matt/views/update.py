"""
UpdateView and PatchView for updating resources.

Supports lifecycle hooks:
- before_update: Called before update, receives (instance, data) tuple, can modify both
- after_update: Called after update, receives updated instance, can modify response
"""

from typing import Any

from django.db import models
from django.http import HttpRequest

from django_matt.core.errors import NotFoundAPIError
from django_matt.views.base import APIView
from django_matt.views.hooks import HookType


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

        # Run before_update hooks - allows modifying instance and data
        # Returns tuple of (instance, data_dict)
        hook_result = await self._run_hooks(
            HookType.BEFORE_UPDATE,
            request,
            value=(instance, data_dict),
            instance=instance,
            data=data_dict,
        )
        if isinstance(hook_result, tuple) and len(hook_result) == 2:
            instance, data_dict = hook_result

        if self._viewset and hasattr(self._viewset, "perform_update"):
            if self._should_validate_model():
                # Validate with new data before perform_update saves
                for key, value in data_dict.items():
                    setattr(instance, key, value)
                await self._validate_model_instance(instance)
            instance = await self._viewset.perform_update(instance, data_dict, request)
        else:
            for key, value in data_dict.items():
                setattr(instance, key, value)
            await self._save_instance(instance)

        # Run after_update hooks - allows modifying instance or response
        instance = await self._run_hooks(
            HookType.AFTER_UPDATE,
            request,
            value=instance,
            instance=instance,
            data=data_dict,
        )

        return self.serialize_single(instance)

    async def _get_instance(self, lookup_value: Any) -> models.Model:
        """Get the model instance by lookup value."""
        queryset = self.get_queryset(None)

        try:
            return await queryset.aget(**{self.lookup_field: lookup_value})
        except queryset.model.DoesNotExist:
            model_name = self.get_model().__name__
            raise NotFoundAPIError(
                message=f"{model_name} not found",
                resource_type=model_name,
                resource_id=str(lookup_value),
            )

    async def _save_instance(self, instance: models.Model):
        """Save the model instance asynchronously."""
        await self._validate_model_instance(instance)
        await instance.asave()


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

        # Only update fields explicitly sent in the request body.
        # Uses model_fields_set to distinguish "not sent" from "sent as null".
        data_dict = {k: v for k, v in data.model_dump().items() if k in data.model_fields_set}

        # Run before_update hooks - allows modifying instance and data
        # Returns tuple of (instance, data_dict)
        hook_result = await self._run_hooks(
            HookType.BEFORE_UPDATE,
            request,
            value=(instance, data_dict),
            instance=instance,
            data=data_dict,
        )
        if isinstance(hook_result, tuple) and len(hook_result) == 2:
            instance, data_dict = hook_result

        if self._viewset and hasattr(self._viewset, "perform_update"):
            if self._should_validate_model():
                for key, value in data_dict.items():
                    setattr(instance, key, value)
                await self._validate_model_instance(instance)
            instance = await self._viewset.perform_update(instance, data_dict, request)
        else:
            field_names = {f.name for f in instance._meta.get_fields()}
            for key, value in data_dict.items():
                # Coerce None to "" for CharField/TextField that disallow NULL.
                # PATCH requests may send explicit nulls to clear a field; Django
                # CharField/TextField require empty string instead of NULL at DB level.
                if value is None and key in field_names:
                    field = instance._meta.get_field(key)
                    if (
                        hasattr(field, "get_internal_type")
                        and field.get_internal_type() in ("CharField", "TextField")
                        and not field.null
                    ):
                        value = ""
                setattr(instance, key, value)
            await self._save_instance(instance)

        # Run after_update hooks - allows modifying instance or response
        instance = await self._run_hooks(
            HookType.AFTER_UPDATE,
            request,
            value=instance,
            instance=instance,
            data=data_dict,
        )

        return self.serialize_single(instance)
