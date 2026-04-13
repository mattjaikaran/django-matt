"""
ReadView for retrieving a single resource.

Supports lifecycle hooks:
- before_read: Called before fetching, receives lookup_value, can modify it
- after_read: Called after fetching, receives instance, can modify response
"""

from typing import Any

from django.http import HttpRequest

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
    _lookup_field_explicit: bool = False

    def __init__(self, lookup_field: str | None = None, **kwargs):
        super().__init__(**kwargs)
        if lookup_field is not None:
            old_field = self.lookup_field
            self.lookup_field = lookup_field
            self._lookup_field_explicit = True
            # Update path if it still uses the old default placeholder
            if self.path == f"{{{old_field}}}":
                self.path = f"{{{lookup_field}}}"

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

        # Parse dynamic field selection (?fields=id,name,email)
        selected_fields = self._parse_field_selection(request)

        instance = await self._get_instance(lookup_value, selected_fields)

        # Run after_read hooks - allows modifying instance or response
        instance = await self._run_hooks(
            HookType.AFTER_READ,
            request,
            value=instance,
            instance=instance,
        )

        result = self.serialize_single(instance)
        return self._filter_dict_fields(result, selected_fields)

    # _get_instance is inherited from APIView (base.py)


# Alias for ReadView (common naming convention)
RetrieveView = ReadView
