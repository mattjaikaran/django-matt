"""
ViewSet classes for Django Matt.

Provides the APIViewSet class for grouping related views together.
Includes support for lifecycle hooks via class methods or decorators.
"""

from typing import Any, ClassVar

from django.db import models
from django.http import HttpRequest

from pydantic import BaseModel

from django_matt.views.hooks import HooksMixin


class ViewSetMeta(type):
    """
    Metaclass for ViewSet that collects views from class attributes.
    """

    def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Skip for base ViewSet class
        if name in ("ViewSet", "APIViewSet"):
            return cls

        # Collect all view instances
        views = {}
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue

            attr = getattr(cls, attr_name, None)
            # Check if it's an APIView instance
            if attr is not None and hasattr(attr, "handle") and hasattr(attr, "path"):
                views[attr_name] = attr

        cls._views = views
        return cls


class ViewSet(metaclass=ViewSetMeta):
    """
    Base class for grouping related views.

    ViewSets provide a way to organize related API operations together.
    Each view is defined as a class attribute using one of the view classes
    (ListView, CreateView, etc.).

    Attributes:
        model: The Django model this ViewSet operates on
        prefix: URL prefix for all routes in this ViewSet
        tags: OpenAPI tags for all routes
        default_response_schema: Default response schema for all views
        default_request_schema: Default request schema for all views
    """

    model: ClassVar[type[models.Model] | None] = None
    prefix: ClassVar[str] = ""
    tags: ClassVar[list[str]] = []
    default_response_schema: ClassVar[type[BaseModel] | None] = None
    default_request_schema: ClassVar[type[BaseModel] | None] = None

    # Collected by metaclass
    _views: ClassVar[dict[str, Any]] = {}

    def __init__(self):
        """Initialize the ViewSet and bind all views."""
        # Bind views to this instance
        for attr_name in self._views:
            view = getattr(self.__class__, attr_name, None)
            if view is not None:
                view._viewset = self

    def get_queryset(self, request: HttpRequest | None = None) -> models.QuerySet:
        """
        Get the base queryset for this ViewSet.

        Override to customize filtering based on request (e.g., user permissions).

        Args:
            request: The HTTP request (may be None for some operations)

        Returns:
            QuerySet to use for this ViewSet
        """
        if self.model is None:
            raise ValueError("ViewSet.model must be set")
        return self.model.objects.all()

    def get_routes(self) -> list[dict[str, Any]]:
        """
        Get route information for all views in this ViewSet.

        Returns:
            List of route dictionaries for URL configuration
        """
        routes = []
        for attr_name, view in self._views.items():
            view._viewset = self
            route_info = view.get_route_info()

            # Build full path
            full_path = self.prefix
            if view.path:
                if full_path and not full_path.endswith("/"):
                    full_path += "/"
                full_path += view.path

            routes.append(
                {
                    **route_info,
                    "name": attr_name,
                    "path": full_path,
                    "view": view,
                }
            )

        return routes

    @classmethod
    def as_urls(cls):
        """
        Generate Django URL patterns for this ViewSet.

        Returns:
            List of Django URL patterns
        """
        from django.urls import path

        instance = cls()
        patterns = []

        for route in instance.get_routes():
            view = route["view"]
            view._viewset = instance

            # Convert {param} to <param> for Django URLs
            url_path = route["path"]
            # Handle {id} -> <id> conversion
            import re

            url_path = re.sub(r"\{(\w+)\}", r"<\1>", url_path)

            # Create the bound view callable
            bound_view = getattr(instance, route["name"])

            patterns.append(path(url_path, bound_view, name=route["name"]))

        return patterns


class APIViewSet(HooksMixin, ViewSet):
    """
    ViewSet specifically for API endpoints.

    Provides additional functionality for API-specific concerns
    like authentication, permissions, response formatting, and lifecycle hooks.

    Lifecycle Hooks:
        Override these methods to hook into CRUD operations:

        - before_list(request, queryset) -> queryset
        - after_list(request, result) -> result
        - before_create(request, data) -> data
        - after_create(request, instance) -> instance
        - before_read(request, lookup_value) -> lookup_value
        - after_read(request, instance) -> instance
        - before_update(request, instance, data) -> (instance, data)
        - after_update(request, instance) -> instance
        - before_delete(request, instance) -> instance
        - after_delete(request, instance) -> None
        - on_error(request, error) -> None

    Example:
        from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView

        class UserViewSet(APIViewSet):
            model = User
            prefix = "users"
            tags = ["Users"]
            default_response_schema = UserSchema
            default_request_schema = UserCreateSchema

            list_users = ListView(
                pagination=True,
                page_size=20,
                filter_fields=["is_active", "role"],
                search_fields=["username", "email"],
            )
            create_user = CreateView()
            read_user = ReadView()
            update_user = UpdateView(request_schema=UserUpdateSchema)
            delete_user = DeleteView()

            # Lifecycle hooks as class methods
            async def before_create(self, request, data):
                data["created_by_id"] = request.user.id
                return data

            async def after_create(self, request, instance):
                await send_notification(f"User {instance.email} created")
                return instance

        # In urls.py:
        urlpatterns = [
            path("api/", include(UserViewSet.as_urls())),
        ]
    """

    # Authentication and permissions (for future implementation)
    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list] = []

    # Enable/disable hooks for all views in this viewset
    enable_hooks: ClassVar[bool] = True

    # Opt-in Django model full_clean() validation before save
    validate_model: ClassVar[bool] = False

    async def perform_create(self, data: dict[str, Any], request: HttpRequest) -> models.Model:
        """
        Create a new model instance.

        Override to customize creation logic (e.g., set user from request).

        Args:
            data: Validated data dictionary
            request: The HTTP request

        Returns:
            Created model instance
        """
        instance = self.model(**data)
        await instance.asave()
        return instance

    async def perform_update(
        self, instance: models.Model, data: dict[str, Any], request: HttpRequest
    ) -> models.Model:
        """
        Update a model instance.

        Override to customize update logic.

        Args:
            instance: The model instance to update
            data: Validated data dictionary
            request: The HTTP request

        Returns:
            Updated model instance
        """
        for key, value in data.items():
            setattr(instance, key, value)

        await instance.asave()

        return instance

    async def perform_delete(self, instance: models.Model, request: HttpRequest) -> None:
        """
        Delete a model instance.

        Override to customize deletion logic (e.g., soft delete).

        Args:
            instance: The model instance to delete
            request: The HTTP request
        """
        await instance.adelete()
