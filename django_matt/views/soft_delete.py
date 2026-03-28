"""
SoftDeleteMixin for ViewSets.

Provides reusable soft_delete/restore endpoints that integrate with
the SoftDeleteMixin model from django_matt.db.soft_delete.

Usage:
    from django_matt.db import SoftDeleteMixin as SoftDeleteModel
    from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView
    from django_matt.views.soft_delete import SoftDeleteMixin

    class Article(SoftDeleteModel, models.Model):
        title = models.CharField(max_length=200)

    class ArticleViewSet(SoftDeleteMixin, APIViewSet):
        model = Article
        prefix = "articles"
        default_response_schema = ArticleSchema

        list_articles = ListView()
        create_article = CreateView()
        read_article = ReadView()
        update_article = UpdateView()
        delete_article = DeleteView()  # Will soft-delete instead of hard-delete

        # SoftDeleteMixin automatically adds:
        # - POST /{id}/restore/  (restore a soft-deleted item)
        # - DELETE /{id}/permanent/  (permanently delete, if allow_hard_delete=True)
"""

from typing import Any, ClassVar

from django.db import models
from django.http import HttpRequest

from django_matt.core.errors import NotFoundAPIError
from django_matt.views.base import APIView


class RestoreView(APIView):
    """
    View for restoring a soft-deleted resource.

    Expects the model to have an `arestore()` method (from SoftDeleteMixin).
    """

    path: str = "{id}/restore"
    methods: list[str] = ["POST"]
    lookup_field: str = "id"

    def __init__(self, lookup_field: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if lookup_field is not None:
            self.lookup_field = lookup_field

    async def handle(self, request: HttpRequest, **kwargs: Any) -> dict[str, Any]:
        """Handle POST request to restore a soft-deleted resource."""
        lookup_value = kwargs.get(self.lookup_field) or kwargs.get("id")
        if lookup_value is None:
            raise ValueError(f"Missing {self.lookup_field} in URL")

        instance = await self._get_deleted_instance(lookup_value)

        # Run before hooks if the viewset defines before_restore
        if self._viewset and hasattr(self._viewset, "before_restore"):
            instance = await self._viewset.before_restore(request, instance)

        # Perform the restore
        if self._viewset and hasattr(self._viewset, "perform_restore"):
            await self._viewset.perform_restore(instance, request)
        else:
            await instance.arestore()

        # Refresh to get updated state
        await instance.arefresh_from_db()

        # Run after hooks if the viewset defines after_restore
        if self._viewset and hasattr(self._viewset, "after_restore"):
            instance = await self._viewset.after_restore(request, instance)

        return {"restored": True, "data": self.serialize_single(instance)}

    async def _get_deleted_instance(self, lookup_value: Any) -> models.Model:
        """Get a soft-deleted model instance by lookup value."""
        model = self.get_model()

        # Use all_objects or with_deleted() to find soft-deleted instances
        if hasattr(model, "all_objects"):
            queryset = model.all_objects.all()
        elif hasattr(model.objects, "with_deleted"):
            queryset = model.objects.with_deleted()
        else:
            queryset = model.objects.all()

        try:
            instance = await queryset.aget(**{self.lookup_field: lookup_value})
        except model.DoesNotExist:
            raise NotFoundAPIError(
                message=f"{model.__name__} not found",
                resource_type=model.__name__,
                resource_id=str(lookup_value),
            )

        # Verify it's actually soft-deleted
        if hasattr(instance, "is_deleted") and not instance.is_deleted:
            raise ValueError(f"{model.__name__} is not deleted")

        return instance


class PermanentDeleteView(APIView):
    """
    View for permanently deleting a resource (hard delete).

    Bypasses soft delete and removes the record from the database entirely.
    """

    path: str = "{id}/permanent"
    methods: list[str] = ["DELETE"]
    lookup_field: str = "id"

    def __init__(self, lookup_field: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if lookup_field is not None:
            self.lookup_field = lookup_field

    async def handle(self, request: HttpRequest, **kwargs: Any) -> dict[str, Any]:
        """Handle DELETE request to permanently delete a resource."""
        lookup_value = kwargs.get(self.lookup_field) or kwargs.get("id")
        if lookup_value is None:
            raise ValueError(f"Missing {self.lookup_field} in URL")

        instance = await self._get_instance(lookup_value)

        # Run before hooks if the viewset defines before_permanent_delete
        if self._viewset and hasattr(self._viewset, "before_permanent_delete"):
            instance = await self._viewset.before_permanent_delete(request, instance)

        # Perform the hard delete
        if hasattr(instance, "ahard_delete"):
            await instance.ahard_delete()
        else:
            await instance.adelete()

        # Run after hooks if the viewset defines after_permanent_delete
        if self._viewset and hasattr(self._viewset, "after_permanent_delete"):
            await self._viewset.after_permanent_delete(request, instance)

        return {"permanently_deleted": True}

    async def _get_instance(self, lookup_value: Any) -> models.Model:
        """Get a model instance (including soft-deleted) by lookup value."""
        model = self.get_model()

        # Use all_objects to find any instance (including soft-deleted)
        if hasattr(model, "all_objects"):
            queryset = model.all_objects.all()
        elif hasattr(model.objects, "with_deleted"):
            queryset = model.objects.with_deleted()
        else:
            queryset = model.objects.all()

        try:
            return await queryset.aget(**{self.lookup_field: lookup_value})
        except model.DoesNotExist:
            raise NotFoundAPIError(
                message=f"{model.__name__} not found",
                resource_type=model.__name__,
                resource_id=str(lookup_value),
            )


class SoftDeleteMixin:
    """
    Mixin for APIViewSet that adds soft delete behavior.

    When mixed into a ViewSet:
    - DeleteView performs soft delete instead of hard delete
    - List queries automatically exclude soft-deleted items (via SoftDeleteManager)
    - Adds a restore endpoint (POST /{id}/restore/)
    - Optionally adds a permanent delete endpoint (DELETE /{id}/permanent/)

    The model MUST use `django_matt.db.SoftDeleteMixin` (or have `deleted_at`,
    `arestore()`, and `ahard_delete()` methods).

    Configuration:
        allow_hard_delete: bool = False  — whether to expose the permanent delete endpoint
        include_deleted_in_detail: bool = False — whether read/update can access deleted items

    Example:
        class ArticleViewSet(SoftDeleteMixin, APIViewSet):
            model = Article  # Must use SoftDeleteMixin
            allow_hard_delete = True

            list_articles = ListView()
            create_article = CreateView()
            read_article = ReadView()
            update_article = UpdateView()
            delete_article = DeleteView()
            # restore_article and permanently_delete_article are added automatically
    """

    allow_hard_delete: ClassVar[bool] = False
    include_deleted_in_detail: ClassVar[bool] = False

    # These are added by __init_subclass__ or the metaclass
    restore: RestoreView
    permanently_delete: PermanentDeleteView

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        # Only add views to concrete subclasses (not SoftDeleteMixin itself)
        # and skip if the class already defines these attributes
        if not hasattr(cls, "restore") or not isinstance(
            getattr(cls, "restore", None), RestoreView
        ):
            cls.restore = RestoreView()

        allow_hard = getattr(cls, "allow_hard_delete", False)
        if allow_hard and (
            not hasattr(cls, "permanently_delete")
            or not isinstance(getattr(cls, "permanently_delete", None), PermanentDeleteView)
        ):
            cls.permanently_delete = PermanentDeleteView()

    async def perform_delete(self, instance: models.Model, request: HttpRequest) -> None:
        """Soft delete instead of hard delete."""
        if hasattr(instance, "adelete"):
            # SoftDeleteMixin.adelete() sets deleted_at
            await instance.adelete()
        else:
            raise TypeError(
                f"{instance.__class__.__name__} does not support soft delete. "
                "Ensure it uses django_matt.db.SoftDeleteMixin."
            )

    async def perform_restore(self, instance: models.Model, request: HttpRequest) -> None:
        """Restore a soft-deleted instance."""
        if hasattr(instance, "arestore"):
            await instance.arestore()
        else:
            raise TypeError(
                f"{instance.__class__.__name__} does not support restore. "
                "Ensure it uses django_matt.db.SoftDeleteMixin."
            )

    def get_queryset(self, request: HttpRequest | None = None) -> models.QuerySet:
        """
        Return queryset excluding soft-deleted items.

        If the model uses SoftDeleteManager (from django_matt.db.SoftDeleteMixin),
        `model.objects.all()` already excludes deleted items. This method just
        delegates to the default behavior.
        """
        if self.model is None:
            raise ValueError("ViewSet.model must be set")
        return self.model.objects.all()
