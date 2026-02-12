"""
CreateView for creating new resources.

Supports lifecycle hooks:
- before_create: Called before creation, receives data dict, can modify it
- after_create: Called after creation, receives instance, can modify response
"""

from typing import Any

from django.db import models
from django.http import HttpRequest

from django_matt.views.base import APIView
from django_matt.views.hooks import HookType


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

        # Run before_create hooks - allows modifying data
        data_dict = await self._run_hooks(
            HookType.BEFORE_CREATE,
            request,
            value=data_dict,
            data=data_dict,
        )

        # Allow ViewSet to customize creation
        if self._viewset and hasattr(self._viewset, "perform_create"):
            instance = await self._viewset.perform_create(data_dict, request)
        else:
            instance = model(**data_dict)
            await self._save_instance(instance)

        # Run after_create hooks - allows modifying instance or response
        instance = await self._run_hooks(
            HookType.AFTER_CREATE,
            request,
            value=instance,
            instance=instance,
            data=data_dict,
        )

        # Serialize and return
        return self.serialize(instance)

    async def _save_instance(self, instance: models.Model):
        """Save the model instance asynchronously."""
        if hasattr(instance, "asave"):
            await instance.asave()
        else:
            from asgiref.sync import sync_to_async

            await sync_to_async(instance.save)()
