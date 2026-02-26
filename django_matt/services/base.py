"""
Base service classes for django-matt.

Keep controllers thin — they handle HTTP concerns only.
Services own the business logic.

Usage:

    # Internal CRUD service
    class ProductService(CRUDService["Product"]):
        model = Product

        async def get_featured(self) -> list[Product]:
            return [p async for p in self.get_queryset().filter(featured=True)]

    # Controller: thin HTTP adapter
    class ProductController(APIController):
        prefix = "/products"

        def __init__(self):
            self.service = ProductService()
            super().__init__()

        @api.get("/")
        async def list_products(self, request):
            items, total = await self.service.list()
            return {"items": items, "total": total}

        @api.post("/")
        async def create_product(self, request, data: ProductCreateSchema):
            return await self.service.create(data.model_dump(), user=request.user)
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.db.models import QuerySet


class ServiceError(Exception):
    """Base service exception."""

    def __init__(self, message: str, code: str = "service_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(ServiceError):
    """Resource not found."""

    def __init__(self, message: str):
        super().__init__(message, code="not_found")


class ValidationError(ServiceError):
    """Validation failed."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message, code="validation_error")
        self.field = field


class ConflictError(ServiceError):
    """Resource already exists / state conflict."""

    def __init__(self, message: str):
        super().__init__(message, code="conflict")


class BaseService[ModelT: models.Model]:
    """
    Base service with read-only helpers.

    Subclass this when you need custom query methods but not full CRUD,
    or to build domain-specific service logic on top of a model.

    Attributes:
        model: The Django model class this service operates on.
    """

    model: type[ModelT]

    def __init__(self) -> None:
        self._log = logging.getLogger(f"django_matt.services.{self.__class__.__name__}")

    # ------------------------------------------------------------------
    # Queryset
    # ------------------------------------------------------------------

    def get_queryset(self) -> QuerySet[ModelT]:
        """
        Base queryset. Override to add select_related, default filters, etc.

            class OrderService(CRUDService["Order"]):
                def get_queryset(self):
                    return super().get_queryset().select_related("user", "product")
        """
        return self.model.objects.all()

    def get_active_queryset(self) -> QuerySet[ModelT]:
        """Queryset filtered to active records (respects ``is_active`` field)."""
        qs = self.get_queryset()
        if hasattr(self.model, "is_active"):
            return qs.filter(is_active=True)
        return qs

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def get(self, pk: Any) -> ModelT:
        """
        Fetch by primary key. Raises ``NotFoundError`` if missing.

            product = await service.get(pk=42)
        """
        try:
            return await self.get_queryset().aget(pk=pk)
        except ObjectDoesNotExist:
            raise NotFoundError(f"{self.model.__name__} {pk} not found")

    async def get_or_none(self, pk: Any) -> ModelT | None:
        """Fetch by primary key. Returns ``None`` if missing (never raises)."""
        try:
            return await self.get_queryset().aget(pk=pk)
        except ObjectDoesNotExist:
            return None

    async def get_by(self, **lookup) -> ModelT:
        """
        Fetch by arbitrary field lookup. Raises ``NotFoundError`` if missing.

            user = await service.get_by(email="alice@example.com")
        """
        try:
            return await self.get_queryset().aget(**lookup)
        except ObjectDoesNotExist:
            raise NotFoundError(
                f"{self.model.__name__} matching {lookup} not found"
            )

    async def exists(self, **lookup) -> bool:
        """Return True if at least one matching record exists."""
        return await self.get_queryset().filter(**lookup).aexists()

    async def count(self, **filters) -> int:
        """Count records matching ``filters``."""
        return await self.get_queryset().filter(**filters).acount()


class CRUDService[ModelT: models.Model](BaseService[ModelT]):
    """
    Full async CRUD service.

    Provides list, get, create, update, partial_update, delete, and bulk
    operations. All methods are ``async`` and use Django's async ORM.

    Quick start:

        class TodoService(CRUDService["Todo"]):
            model = Todo

            def get_queryset(self):
                return super().get_queryset().select_related("user")

            async def for_user(self, user) -> list[Todo]:
                return [t async for t in self.get_queryset().filter(user=user)]

        # In controller __init__:
        self.service = TodoService()

        # One-liner endpoints:
        async def create_todo(self, request, data: TodoCreateSchema):
            return await self.service.create(data.model_dump(), user=request.user)
    """

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        ordering: str | list[str] | None = None,
        **filters: Any,
    ) -> tuple[list[ModelT], int]:
        """
        Paginated list with optional filtering and ordering.

        Returns ``(items, total_count)`` so controllers can build
        pagination envelopes without extra queries.

            items, total = await service.list(page=2, page_size=10, status="active")
            return {"items": items, "total": total, "page": 2}
        """
        qs = self.get_queryset()

        # Apply filters (skip None values so callers can pass query params directly)
        active_filters = {k: v for k, v in filters.items() if v is not None}
        if active_filters:
            qs = qs.filter(**active_filters)

        if ordering:
            qs = qs.order_by(*([ordering] if isinstance(ordering, str) else ordering))

        total = await qs.acount()
        offset = (page - 1) * page_size
        items = [item async for item in qs[offset : offset + page_size]]
        return items, total

    async def all(self, **filters: Any) -> list[ModelT]:
        """
        Return all matching records (no pagination).
        Use for small datasets or when you need the full set.
        """
        qs = self.get_queryset()
        active_filters = {k: v for k, v in filters.items() if v is not None}
        if active_filters:
            qs = qs.filter(**active_filters)
        return [item async for item in qs]

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(self, data: dict[str, Any], user=None) -> ModelT:
        """
        Create a new record inside a transaction.

        Populates ``created_by`` / ``updated_by`` audit fields automatically
        when the model supports them.

            todo = await service.create({"title": "Buy milk"}, user=request.user)
        """
        if user is not None and hasattr(self.model, "created_by"):
            data = {**data, "created_by": user}

        try:
            async with transaction.atomic():
                instance = self.model(**data)
                await instance.aclean_fields(exclude=None)  # type: ignore[attr-defined]
                await instance.asave()
        except Exception as exc:
            self._log.exception("create %s failed: %s", self.model.__name__, exc)
            raise ValidationError(str(exc)) from exc

        self._log.info("created %s pk=%s", self.model.__name__, instance.pk)
        return instance

    async def get_or_create(
        self, defaults: dict[str, Any] | None = None, user=None, **lookup: Any
    ) -> tuple[ModelT, bool]:
        """
        Fetch or create by ``lookup`` fields. Returns ``(instance, created)``.

            obj, created = await service.get_or_create(defaults={"name": "Default"}, slug="default")
        """
        try:
            return await self.get_queryset().aget(**lookup), False
        except ObjectDoesNotExist:
            create_data = {**lookup, **(defaults or {})}
            return await self.create(create_data, user=user), True

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(
        self, pk: Any, data: dict[str, Any], user=None, *, partial: bool = False
    ) -> ModelT:
        """
        Update a record by primary key inside a transaction.

        With ``partial=True``, ``None`` values in ``data`` are skipped
        (equivalent to a PATCH operation).

            updated = await service.update(pk, {"title": "New title"}, user=request.user)
            patched = await service.update(pk, payload.model_dump(), user=request.user, partial=True)
        """
        instance = await self.get(pk)
        update_data = (
            {k: v for k, v in data.items() if v is not None} if partial else data
        )

        if user is not None and hasattr(instance, "updated_by"):
            instance.updated_by = user  # type: ignore[attr-defined]

        try:
            async with transaction.atomic():
                for field, value in update_data.items():
                    if hasattr(instance, field):
                        setattr(instance, field, value)
                await instance.asave()
        except Exception as exc:
            self._log.exception("update %s pk=%s failed: %s", self.model.__name__, pk, exc)
            raise ValidationError(str(exc)) from exc

        self._log.info("updated %s pk=%s", self.model.__name__, pk)
        return instance

    async def update_fields(self, pk: Any, user=None, **fields: Any) -> ModelT:
        """
        Convenience wrapper — update specific fields by keyword.

            await service.update_fields(pk, completed=True, user=request.user)
        """
        return await self.update(pk, fields, user=user)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(
        self, pk: Any, user=None, *, hard: bool = False
    ) -> bool:
        """
        Delete a record.

        Soft-deletes by default when the model has ``is_active`` + ``soft_delete()``.
        Pass ``hard=True`` to permanently delete regardless.

            await service.delete(pk)             # soft delete if supported
            await service.delete(pk, hard=True)  # always permanent
        """
        from asgiref.sync import sync_to_async

        instance = await self.get(pk)

        if not hard and hasattr(instance, "soft_delete"):
            await sync_to_async(instance.soft_delete)(user=user)  # type: ignore[attr-defined]
            self._log.info("soft-deleted %s pk=%s", self.model.__name__, pk)
        else:
            await instance.adelete()
            self._log.info("deleted %s pk=%s", self.model.__name__, pk)

        return True

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    async def bulk_create(
        self,
        items: list[dict[str, Any]],
        user=None,
        *,
        batch_size: int = 500,
        ignore_conflicts: bool = False,
    ) -> list[ModelT]:
        """
        Create many records in one query. Skips ``full_clean()``.
        Use when you need throughput and have already validated data.

            created = await service.bulk_create([{"title": "A"}, {"title": "B"}])
        """
        instances = []
        for data in items:
            if user is not None and hasattr(self.model, "created_by"):
                data = {**data, "created_by": user}
            instances.append(self.model(**data))

        result = await self.model.objects.abulk_create(
            instances, batch_size=batch_size, ignore_conflicts=ignore_conflicts
        )
        self._log.info(
            "bulk_create %s: %d records", self.model.__name__, len(result)
        )
        return result

    async def bulk_update(
        self,
        instances: list[ModelT],
        fields: list[str],
        user=None,
        *,
        batch_size: int = 500,
    ) -> int:
        """
        Update many records in one query.

            count = await service.bulk_update(todos, fields=["completed", "updated_at"])
        """
        if user is not None and "updated_by" not in fields and hasattr(self.model, "updated_by"):
            for inst in instances:
                inst.updated_by = user  # type: ignore[attr-defined]
            fields = [*fields, "updated_by"]

        count = await self.model.objects.abulk_update(
            instances, fields, batch_size=batch_size
        )
        self._log.info("bulk_update %s: %d records", self.model.__name__, count)
        return count

    async def bulk_delete(
        self,
        pks: list[Any],
        user=None,
        *,
        hard: bool = False,
    ) -> int:
        """
        Delete many records by primary key list.

            count = await service.bulk_delete([1, 2, 3])
        """
        qs = self.get_queryset().filter(pk__in=pks)

        if not hard and hasattr(self.model, "is_active"):
            update_kwargs: dict[str, Any] = {"is_active": False}
            if user is not None and hasattr(self.model, "updated_by"):
                update_kwargs["updated_by"] = user
            count = await qs.aupdate(**update_kwargs)
        else:
            count, _ = await qs.adelete()

        self._log.info("bulk_delete %s: %d records", self.model.__name__, count)
        return count
