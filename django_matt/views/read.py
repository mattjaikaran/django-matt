"""
ReadView for retrieving a single resource.

Supports lifecycle hooks:
- before_read: Called before fetching, receives lookup_value, can modify it
- after_read: Called after fetching, receives instance, can modify response
"""

from typing import Any

from django.db import models
from django.http import HttpRequest

from django_matt.core.errors import NotFoundAPIError
from django_matt.views.base import APIView
from django_matt.views.hooks import HookType


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

        # Run before_read hooks - allows modifying lookup value
        lookup_value = await self._run_hooks(
            HookType.BEFORE_READ,
            request,
            value=lookup_value,
        )

        instance = await self._get_instance(lookup_value)

        # Run after_read hooks - allows modifying instance or response
        instance = await self._run_hooks(
            HookType.AFTER_READ,
            request,
            value=instance,
            instance=instance,
        )

        return self.serialize(instance)

    async def _get_instance(self, lookup_value: Any) -> models.Model:
        """Get the model instance by lookup value."""
        queryset = self.get_queryset(None)

        # Auto-optimize for single object retrieval too
        queryset = self.optimize_queryset(queryset)

        try:
            return await queryset.aget(**{self.lookup_field: lookup_value})
        except queryset.model.DoesNotExist:
            model_name = self.get_model().__name__
            raise NotFoundAPIError(
                message=f"{model_name} not found",
                resource_type=model_name,
                resource_id=str(lookup_value),
            )


# Alias for ReadView (common naming convention)
RetrieveView = ReadView
