"""
Bulk CRUD views for Django Matt.

Provides BulkCreateView, BulkUpdateView, and BulkDeleteView for batch operations.
All operations are wrapped in database transactions and support configurable limits.

Supports lifecycle hooks:
- before_bulk_create / after_bulk_create
- before_bulk_update / after_bulk_update
- before_bulk_delete / after_bulk_delete
"""

from typing import Any

from django.db import models, transaction
from django.http import HttpRequest

import orjson

from django_matt.views.base import APIView
from django_matt.views.hooks import HookType


class BulkCreateView(APIView):
    """
    View for creating multiple resources in a single request.

    Accepts a JSON array of objects, validates each against request_schema,
    and creates them all within a database transaction.

    Attributes:
        max_items: Maximum number of items allowed per request (default: 100).

    Example:
        class ProductViewSet(APIViewSet):
            bulk_create = BulkCreateView(
                path="bulk",
                request_schema=ProductCreateSchema,
                response_schema=ProductSchema,
                max_items=50,
            )
    """

    path: str = "bulk"
    methods: list[str] = ["POST"]
    max_items: int = 100

    def __init__(self, max_items: int | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if max_items is not None:
            self.max_items = max_items

    async def handle(self, request: HttpRequest, **kwargs: Any) -> list[dict[str, Any]]:
        """Handle POST request to bulk-create resources."""
        items_data = self._parse_body(request)
        self._validate_count(items_data)

        schema = self.get_request_schema()
        validated: list[dict[str, Any]] = []
        for item in items_data:
            if schema is not None:
                obj = schema.model_validate(item)
                validated.append(obj.model_dump(exclude_unset=True))
            else:
                validated.append(item)

        # Run before_bulk_create hooks
        validated = await self._run_hooks(
            HookType.BEFORE_BULK_CREATE,
            request,
            value=validated,
            data=validated,
        )

        model = self.get_model()
        instances = await self._bulk_create(model, validated)

        # Run after_bulk_create hooks
        instances = await self._run_hooks(
            HookType.AFTER_BULK_CREATE,
            request,
            value=instances,
            data=validated,
        )

        return [self.serialize_single(inst) for inst in instances]

    async def _bulk_create(
        self, model: type[models.Model], items: list[dict[str, Any]]
    ) -> list[models.Model]:
        """Create all instances inside a transaction using async ORM."""
        objs = [model(**data) for data in items]

        @transaction.atomic
        def _do_create() -> list[models.Model]:
            return model.objects.bulk_create(objs)

        from asgiref.sync import sync_to_async

        return await sync_to_async(_do_create)()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_body(self, request: HttpRequest) -> list[dict[str, Any]]:
        """Parse the request body as a JSON array."""
        try:
            body = orjson.loads(request.body) if request.body else []
        except (ValueError, orjson.JSONDecodeError):
            raise ValueError("Invalid JSON in request body")

        if not isinstance(body, list):
            raise ValueError("Request body must be a JSON array")
        return body

    def _validate_count(self, items: list[Any]) -> None:
        """Ensure the item count does not exceed max_items."""
        if not items:
            raise ValueError("Request body must contain at least one item")
        if len(items) > self.max_items:
            raise ValueError(
                f"Too many items: {len(items)} exceeds maximum of {self.max_items}"
            )


class BulkUpdateView(APIView):
    """
    View for updating multiple resources in a single request.

    Accepts a JSON array of objects, each containing an identifier and the
    fields to update. All updates run within a database transaction.

    Attributes:
        max_items: Maximum number of items allowed per request (default: 100).
        lookup_field: Field used to identify each object (default: "id").

    Example:
        class ProductViewSet(APIViewSet):
            bulk_update = BulkUpdateView(
                path="bulk",
                request_schema=ProductUpdateSchema,
                response_schema=ProductSchema,
            )
    """

    path: str = "bulk"
    methods: list[str] = ["PUT"]
    max_items: int = 100
    lookup_field: str = "id"

    def __init__(
        self,
        max_items: int | None = None,
        lookup_field: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if max_items is not None:
            self.max_items = max_items
        if lookup_field is not None:
            self.lookup_field = lookup_field

    async def handle(self, request: HttpRequest, **kwargs: Any) -> list[dict[str, Any]]:
        """Handle PUT request to bulk-update resources."""
        items_data = self._parse_body(request)
        self._validate_count(items_data)

        schema = self.get_request_schema()
        entries: list[tuple[Any, dict[str, Any]]] = []
        for item in items_data:
            lookup_value = item.pop(self.lookup_field, None)
            if lookup_value is None:
                raise ValueError(
                    f"Each item must include '{self.lookup_field}'"
                )
            if schema is not None:
                obj = schema.model_validate(item)
                data_dict = obj.model_dump(exclude_unset=True)
            else:
                data_dict = item
            entries.append((lookup_value, data_dict))

        # Run before_bulk_update hooks
        entries = await self._run_hooks(
            HookType.BEFORE_BULK_UPDATE,
            request,
            value=entries,
            data=entries,
        )

        instances = await self._bulk_update(entries)

        # Run after_bulk_update hooks
        instances = await self._run_hooks(
            HookType.AFTER_BULK_UPDATE,
            request,
            value=instances,
            data=entries,
        )

        return [self.serialize_single(inst) for inst in instances]

    async def _bulk_update(
        self, entries: list[tuple[Any, dict[str, Any]]]
    ) -> list[models.Model]:
        """Fetch, update, and save all instances in a transaction."""
        model = self.get_model()
        lookup_values = [lv for lv, _ in entries]
        data_by_lookup: dict[Any, dict[str, Any]] = {}
        for lv, data in entries:
            data_by_lookup[lv] = data

        queryset = self.get_queryset(None)

        from asgiref.sync import sync_to_async

        @transaction.atomic
        def _do_update() -> list[models.Model]:
            qs = queryset.filter(**{f"{self.lookup_field}__in": lookup_values})
            instances_map: dict[Any, models.Model] = {
                getattr(inst, self.lookup_field): inst for inst in qs
            }

            # Check all requested items exist
            missing = set(str(lv) for lv in lookup_values) - set(
                str(k) for k in instances_map.keys()
            )
            if missing:
                from django_matt.core.errors import NotFoundAPIError

                raise NotFoundAPIError(
                    message=f"{model.__name__} not found: {', '.join(missing)}",
                    resource_type=model.__name__,
                    resource_id=", ".join(missing),
                )

            # Collect all fields that need updating
            update_fields: set[str] = set()
            updated: list[models.Model] = []
            for lv in lookup_values:
                inst = instances_map[lv]
                data = data_by_lookup[lv]
                for key, value in data.items():
                    setattr(inst, key, value)
                    update_fields.add(key)
                updated.append(inst)

            if update_fields:
                model.objects.bulk_update(updated, list(update_fields))
            return updated

        return await sync_to_async(_do_update)()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_body(self, request: HttpRequest) -> list[dict[str, Any]]:
        """Parse the request body as a JSON array."""
        try:
            body = orjson.loads(request.body) if request.body else []
        except (ValueError, orjson.JSONDecodeError):
            raise ValueError("Invalid JSON in request body")

        if not isinstance(body, list):
            raise ValueError("Request body must be a JSON array")
        return body

    def _validate_count(self, items: list[Any]) -> None:
        """Ensure the item count does not exceed max_items."""
        if not items:
            raise ValueError("Request body must contain at least one item")
        if len(items) > self.max_items:
            raise ValueError(
                f"Too many items: {len(items)} exceeds maximum of {self.max_items}"
            )


class BulkDeleteView(APIView):
    """
    View for deleting multiple resources in a single request.

    Accepts a JSON array of identifiers and deletes all matching objects
    within a database transaction.

    Attributes:
        max_items: Maximum number of items allowed per request (default: 100).
        lookup_field: Field used to identify each object (default: "id").

    Example:
        class ProductViewSet(APIViewSet):
            bulk_delete = BulkDeleteView(
                path="bulk",
                response_schema=None,
            )
    """

    path: str = "bulk"
    methods: list[str] = ["DELETE"]
    max_items: int = 100
    lookup_field: str = "id"

    def __init__(
        self,
        max_items: int | None = None,
        lookup_field: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if max_items is not None:
            self.max_items = max_items
        if lookup_field is not None:
            self.lookup_field = lookup_field

    async def handle(self, request: HttpRequest, **kwargs: Any) -> dict[str, Any]:
        """Handle DELETE request to bulk-delete resources."""
        ids = self._parse_body(request)
        self._validate_count(ids)

        # Run before_bulk_delete hooks
        ids = await self._run_hooks(
            HookType.BEFORE_BULK_DELETE,
            request,
            value=ids,
            data=ids,
        )

        deleted_count = await self._bulk_delete(ids)

        # Run after_bulk_delete hooks
        await self._run_hooks(
            HookType.AFTER_BULK_DELETE,
            request,
            value=ids,
            data=ids,
        )

        return {"deleted": True, "count": deleted_count}

    async def _bulk_delete(self, ids: list[Any]) -> int:
        """Delete all matching instances in a transaction."""
        queryset = self.get_queryset(None)

        from asgiref.sync import sync_to_async

        @transaction.atomic
        def _do_delete() -> int:
            qs = queryset.filter(**{f"{self.lookup_field}__in": ids})
            count, _ = qs.delete()
            return count

        return await sync_to_async(_do_delete)()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_body(self, request: HttpRequest) -> list[Any]:
        """Parse the request body as a JSON array of IDs."""
        try:
            body = orjson.loads(request.body) if request.body else []
        except (ValueError, orjson.JSONDecodeError):
            raise ValueError("Invalid JSON in request body")

        if not isinstance(body, list):
            raise ValueError("Request body must be a JSON array of IDs")
        return body

    def _validate_count(self, items: list[Any]) -> None:
        """Ensure the item count does not exceed max_items."""
        if not items:
            raise ValueError("Request body must contain at least one ID")
        if len(items) > self.max_items:
            raise ValueError(
                f"Too many items: {len(items)} exceeds maximum of {self.max_items}"
            )
