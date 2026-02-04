from __future__ import annotations

import inspect
import json
from functools import wraps
from typing import TYPE_CHECKING, Any, get_type_hints

import django
from django.conf import settings

if TYPE_CHECKING:
    pass
from django.db.models import ForeignKey, ManyToManyField, ManyToOneRel
from django.http import HttpRequest, JsonResponse

from pydantic import BaseModel, ValidationError

from django_matt.core.errors import APIError, ErrorHandler, NotFoundAPIError


def _get_error_config() -> dict[str, Any]:
    """Get error handling configuration from settings."""
    config = getattr(settings, "DJANGO_MATT_ERRORS", {})
    return {
        "debug": config.get("DEBUG", getattr(settings, "DEBUG", False)),
        "include_traceback": config.get("INCLUDE_TRACEBACK", getattr(settings, "DEBUG", False)),
        "include_snippet": config.get("INCLUDE_SNIPPET", getattr(settings, "DEBUG", False)),
    }


# Django version detection for compatibility
DJANGO_VERSION = tuple(map(int, django.__version__.split(".")[:2]))
DJANGO_5_2_PLUS = DJANGO_VERSION >= (5, 2)
DJANGO_6_0_PLUS = DJANGO_VERSION >= (6, 0)


class Controller:
    """
    Base controller class for Django Matt framework.

    Controllers provide a class-based approach to defining API endpoints.
    Methods can be decorated with route decorators to define endpoints.
    """

    prefix: str = ""
    tags: list[str] = []
    auto_error_handling: bool = True  # Enable automatic error handling by default

    def __init__(self):
        self._setup_dependencies()
        if self.auto_error_handling:
            self._setup_error_handling()

    def _setup_dependencies(self):
        """
        Set up dependencies for controller methods based on type hints.
        This allows for automatic dependency injection in controller methods.
        """
        for method_name in dir(self):
            if method_name.startswith("_"):
                continue

            method = getattr(self, method_name)
            if not callable(method) or not hasattr(method, "_route_info"):
                continue

            # Get type hints for the method
            hints = get_type_hints(method)

            # Create a wrapper that injects dependencies
            @wraps(method)
            async def wrapper(request, *args, **kwargs):
                # Process request body if it exists
                body_data = {}
                if request.body and request.content_type == "application/json":
                    try:
                        body_data = json.loads(request.body)
                    except json.JSONDecodeError:
                        return JsonResponse({"detail": "Invalid JSON"}, status=400)

                # Inject dependencies based on type hints
                for param_name, param_type in hints.items():
                    if param_name == "return":
                        continue

                    if param_name == "request":
                        kwargs[param_name] = request
                        continue

                    # Check if the parameter is a Pydantic model
                    if inspect.isclass(param_type) and issubclass(param_type, BaseModel):
                        try:
                            # Try to create the model from body data
                            model_instance = param_type(**body_data)
                            kwargs[param_name] = model_instance
                        except ValidationError as e:
                            return JsonResponse(
                                {"detail": "Validation error", "errors": e.errors()},
                                status=422,
                            )

                # Call the original method
                if inspect.iscoroutinefunction(method):
                    result = await method(*args, **kwargs)
                else:
                    result = method(*args, **kwargs)

                return result

            # Replace the original method with the wrapper
            setattr(self, method_name, wrapper)

    def _setup_error_handling(self):
        """
        Set up automatic error handling for controller methods.
        This wraps all route methods with try/except blocks.
        """
        # Get error configuration from settings
        error_config = _get_error_config()
        error_handler_instance = ErrorHandler(debug=error_config["debug"])

        for method_name in dir(self):
            if method_name.startswith("_"):
                continue

            method = getattr(self, method_name)
            if not callable(method) or not hasattr(method, "_route_info"):
                continue

            # Create a wrapper that adds error handling
            @wraps(method)
            async def error_wrapper(request, *args, **kwargs):
                try:
                    if inspect.iscoroutinefunction(method):
                        result = await method(request, *args, **kwargs)
                    else:
                        result = method(request, *args, **kwargs)
                    return result
                except Exception as e:
                    # Use the handle_exception method if available
                    if hasattr(self, "handle_exception"):
                        return self.handle_exception(e, request)

                    # Otherwise use the default error handler
                    cfg = _get_error_config()
                    error_detail = error_handler_instance.capture_exception(e, request)
                    return error_detail.to_response(
                        include_traceback=cfg["include_traceback"],
                        include_snippet=cfg["include_snippet"],
                    )

            # Replace the method with the error-handling wrapper
            setattr(self, method_name, error_wrapper)


class APIController(Controller):
    """
    Controller specifically for API endpoints.
    Provides additional functionality for API-specific concerns.
    """

    def handle_exception(self, exc: Exception, request: HttpRequest = None) -> JsonResponse:
        """
        Handle exceptions raised during request processing.
        Override this method to customize exception handling.

        Args:
                exc: The exception that was raised
                request: The HTTP request that caused the exception

        Returns:
                A JsonResponse with error details
        """
        # Get error configuration from settings
        error_config = _get_error_config()
        error_handler_instance = ErrorHandler(debug=error_config["debug"])

        # Handle specific API exceptions
        if isinstance(exc, APIError):
            return JsonResponse(
                {
                    "detail": str(exc),
                    "code": getattr(exc, "code", "error"),
                    "context": getattr(exc, "context", {}),
                },
                status=getattr(exc, "status_code", 500),
            )

        # Handle validation errors
        if isinstance(exc, ValidationError):
            return JsonResponse(
                {
                    "detail": "Validation error",
                    "errors": exc.errors(),
                },
                status=422,
            )

        # Handle model DoesNotExist exceptions
        if hasattr(exc, "__class__") and exc.__class__.__name__ == "DoesNotExist":
            model_name = exc.__class__.__module__.split(".")[-2]  # Get model name from module path
            return JsonResponse(
                {
                    "detail": f"{model_name} not found",
                    "code": "not_found",
                },
                status=404,
            )

        # Use the error handler for other exceptions
        error_detail = error_handler_instance.capture_exception(exc, request)
        return error_detail.to_response(
            include_traceback=error_config["include_traceback"],
            include_snippet=error_config["include_snippet"],
        )


class CRUDController(APIController):
    """
    Base controller for CRUD operations with async ORM support and query optimization.

    Provides common CRUD methods that can be customized by subclasses.
    Uses Django 4.1+ async ORM methods for true non-blocking database access.

    Attributes:
        model: The Django model class for this controller
        schema: Pydantic schema for serializing model instances
        create_schema: Pydantic schema for create operations (defaults to schema)
        update_schema: Pydantic schema for update operations (defaults to schema)
        auto_optimize: Whether to automatically optimize queries (default: True)
        select_related_fields: List of fields to select_related (auto-detected if None)
        prefetch_related_fields: List of fields to prefetch_related (auto-detected if None)
        lookup_field: Field to use for single object lookups (default: "id")
        ordering: Default ordering for list queries (default: None)

    Example:
        class UserController(CRUDController):
            model = User
            schema = UserSchema
            select_related_fields = ["profile", "organization"]
            prefetch_related_fields = ["groups", "permissions"]
            ordering = ["-created_at"]
    """

    model = None
    schema = None
    create_schema = None
    update_schema = None

    # Query optimization settings
    auto_optimize: bool = True
    select_related_fields: list[str] | None = None
    prefetch_related_fields: list[str] | None = None
    include_reverse_relations: bool = False

    # Query settings
    lookup_field: str = "id"
    ordering: list[str] | None = None

    def get_queryset(self):
        """
        Get the base queryset for this controller.

        Override this method to customize the base queryset (e.g., filtering by user).

        Returns:
            QuerySet: The base queryset for this model
        """
        if not self.model:
            raise NotImplementedError("Model not specified")
        return self.model.objects.all()

    def get_optimized_queryset(self):
        """
        Get an optimized queryset with select_related and prefetch_related applied.

        If auto_optimize is True and no explicit fields are specified,
        this method will automatically detect foreign key and many-to-many
        relationships and optimize the query accordingly.

        Returns:
            QuerySet: The optimized queryset
        """
        queryset = self.get_queryset()

        if not self.auto_optimize:
            return queryset

        # Use explicitly configured fields if provided
        if self.select_related_fields:
            queryset = queryset.select_related(*self.select_related_fields)
        elif self.auto_optimize:
            # Auto-detect foreign key relationships
            select_fields = self._get_foreign_key_fields()
            if select_fields:
                queryset = queryset.select_related(*select_fields)

        if self.prefetch_related_fields:
            queryset = queryset.prefetch_related(*self.prefetch_related_fields)
        elif self.auto_optimize:
            # Auto-detect many-to-many relationships
            prefetch_fields = self._get_many_to_many_fields()
            if self.include_reverse_relations:
                prefetch_fields.extend(self._get_reverse_relation_fields())
            if prefetch_fields:
                queryset = queryset.prefetch_related(*prefetch_fields)

        # Apply default ordering
        if self.ordering:
            queryset = queryset.order_by(*self.ordering)

        return queryset

    def _get_foreign_key_fields(self) -> list[str]:
        """Get all foreign key field names for auto select_related."""
        if not self.model:
            return []
        fields = []
        for field in self.model._meta.get_fields():
            if isinstance(field, ForeignKey):
                fields.append(field.name)
        return fields

    def _get_many_to_many_fields(self) -> list[str]:
        """Get all many-to-many field names for auto prefetch_related."""
        if not self.model:
            return []
        fields = []
        for field in self.model._meta.get_fields():
            if isinstance(field, ManyToManyField):
                fields.append(field.name)
        return fields

    def _get_reverse_relation_fields(self) -> list[str]:
        """Get all reverse relation field names for auto prefetch_related."""
        if not self.model:
            return []
        fields = []
        for field in self.model._meta.get_fields():
            if isinstance(field, ManyToOneRel):
                accessor_name = field.get_accessor_name()
                if accessor_name:
                    fields.append(accessor_name)
        return fields

    def filter_queryset(self, queryset, request: HttpRequest):
        """
        Apply filters from request query parameters to the queryset.

        Override this method to customize filtering behavior.

        Args:
            queryset: The queryset to filter
            request: The HTTP request containing query parameters

        Returns:
            QuerySet: The filtered queryset
        """
        # Get valid filter fields from model
        valid_fields = {f.name for f in self.model._meta.fields}

        for key, value in request.GET.items():
            # Skip pagination and special parameters
            if key in ("page", "page_size", "limit", "offset", "ordering", "format"):
                continue

            # Handle field lookups (e.g., name__icontains)
            field_name = key.split("__")[0]
            if field_name in valid_fields:
                queryset = queryset.filter(**{key: value})

        return queryset

    async def list(self, request: HttpRequest) -> dict[str, Any]:
        """
        List all instances of the model with async iteration.

        Uses Django's async ORM methods for non-blocking database access.

        Args:
            request: The HTTP request

        Returns:
            Dict with 'items' list and 'count' of total items
        """
        if not self.model:
            raise NotImplementedError("Model not specified")

        queryset = self.get_optimized_queryset()
        queryset = self.filter_queryset(queryset, request)

        # Use async iteration (Django 4.1+)
        items = []
        async for item in queryset:
            items.append(self._model_to_dict(item))

        # Get count asynchronously
        count = await queryset.acount()

        return {"items": items, "count": count}

    async def retrieve(self, request: HttpRequest, id: str) -> dict[str, Any]:
        """
        Retrieve a single instance of the model by ID using async ORM.

        Args:
            request: The HTTP request
            id: The ID of the object to retrieve

        Returns:
            Dict representation of the model instance
        """
        if not self.model:
            raise NotImplementedError("Model not specified")

        queryset = self.get_optimized_queryset()

        try:
            # Use async get (Django 4.1+)
            instance = await queryset.aget(**{self.lookup_field: id})
            return self._model_to_dict(instance)
        except self.model.DoesNotExist:
            raise NotFoundAPIError(
                message=f"{self.model.__name__} not found",
                resource_type=self.model.__name__,
                resource_id=str(id),
            )

    async def create(self, request: HttpRequest, data: BaseModel) -> dict[str, Any]:
        """
        Create a new instance of the model using async ORM.

        Args:
            request: The HTTP request
            data: Pydantic model with the data to create

        Returns:
            Dict representation of the created model instance
        """
        if not self.model:
            raise NotImplementedError("Model not specified")

        # Convert Pydantic model to dictionary, excluding unset values
        data_dict = data.model_dump(exclude_unset=True)

        # Use async create (Django 4.1+)
        instance = await self.model.objects.acreate(**data_dict)

        return self._model_to_dict(instance)

    async def update(self, request: HttpRequest, id: str, data: BaseModel) -> dict[str, Any]:
        """
        Update an existing instance of the model using async ORM.

        Args:
            request: The HTTP request
            id: The ID of the object to update
            data: Pydantic model with the data to update

        Returns:
            Dict representation of the updated model instance
        """
        if not self.model:
            raise NotImplementedError("Model not specified")

        queryset = self.get_optimized_queryset()

        try:
            # Use async get (Django 4.1+)
            instance = await queryset.aget(**{self.lookup_field: id})

            # Convert Pydantic model to dictionary, excluding unset values
            data_dict = data.model_dump(exclude_unset=True)

            # Update the instance fields
            for key, value in data_dict.items():
                setattr(instance, key, value)

            # Use async save (Django 4.1+)
            await instance.asave()

            return self._model_to_dict(instance)
        except self.model.DoesNotExist:
            raise NotFoundAPIError(
                message=f"{self.model.__name__} not found",
                resource_type=self.model.__name__,
                resource_id=str(id),
            )

    async def partial_update(
        self, request: HttpRequest, id: str, data: BaseModel
    ) -> dict[str, Any]:
        """
        Partially update an existing instance (PATCH semantics).

        Only updates fields that are explicitly set in the request data.

        Args:
            request: The HTTP request
            id: The ID of the object to update
            data: Pydantic model with the partial data to update

        Returns:
            Dict representation of the updated model instance
        """
        # partial_update uses the same logic as update with exclude_unset=True
        return await self.update(request, id, data)

    async def delete(self, request: HttpRequest, id: str) -> dict[str, Any]:
        """
        Delete an instance of the model using async ORM.

        Args:
            request: The HTTP request
            id: The ID of the object to delete

        Returns:
            Empty dict on success
        """
        if not self.model:
            raise NotImplementedError("Model not specified")

        try:
            # Use async get and delete (Django 4.1+)
            instance = await self.model.objects.aget(**{self.lookup_field: id})
            await instance.adelete()
            return {"deleted": True, "id": id}
        except self.model.DoesNotExist:
            raise NotFoundAPIError(
                message=f"{self.model.__name__} not found",
                resource_type=self.model.__name__,
                resource_id=str(id),
            )

    async def bulk_create(self, request: HttpRequest, items: list[BaseModel]) -> dict[str, Any]:
        """
        Bulk create multiple instances using async ORM.

        Args:
            request: The HTTP request
            items: List of Pydantic models with data to create

        Returns:
            Dict with 'items' list and 'count' of created items
        """
        if not self.model:
            raise NotImplementedError("Model not specified")

        # Convert Pydantic models to model instances
        model_instances = [self.model(**item.model_dump(exclude_unset=True)) for item in items]

        # Use async bulk_create (Django 4.1+)
        created = await self.model.objects.abulk_create(model_instances)

        return {
            "items": [self._model_to_dict(instance) for instance in created],
            "count": len(created),
        }

    async def bulk_update(
        self, request: HttpRequest, items: list[dict[str, Any]], fields: list[str]
    ) -> dict[str, Any]:
        """
        Bulk update multiple instances using async ORM.

        Args:
            request: The HTTP request
            items: List of dicts with 'id' and fields to update
            fields: List of field names to update

        Returns:
            Dict with 'updated_count' of modified rows
        """
        if not self.model:
            raise NotImplementedError("Model not specified")

        # Fetch existing instances
        ids = [item[self.lookup_field] for item in items]
        instances = {}
        async for instance in self.model.objects.filter(**{f"{self.lookup_field}__in": ids}):
            instances[getattr(instance, self.lookup_field)] = instance

        # Update instances
        to_update = []
        for item in items:
            instance = instances.get(item[self.lookup_field])
            if instance:
                for field in fields:
                    if field in item:
                        setattr(instance, field, item[field])
                to_update.append(instance)

        # Use async bulk_update (Django 4.1+)
        updated_count = await self.model.objects.abulk_update(to_update, fields)

        return {"updated_count": updated_count}

    async def exists(self, request: HttpRequest, id: str) -> dict[str, Any]:
        """
        Check if an instance exists using async ORM.

        Args:
            request: The HTTP request
            id: The ID to check

        Returns:
            Dict with 'exists' boolean
        """
        if not self.model:
            raise NotImplementedError("Model not specified")

        exists = await self.model.objects.filter(**{self.lookup_field: id}).aexists()
        return {"exists": exists}

    async def count(self, request: HttpRequest) -> dict[str, Any]:
        """
        Get the count of instances using async ORM.

        Args:
            request: The HTTP request

        Returns:
            Dict with 'count' integer
        """
        if not self.model:
            raise NotImplementedError("Model not specified")

        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset, request)
        total = await queryset.acount()
        return {"count": total}

    def _model_to_dict(self, instance) -> dict[str, Any]:
        """
        Convert a model instance to a dictionary.

        Uses the configured schema if available, otherwise falls back
        to a simple field-by-field conversion.

        Args:
            instance: The model instance to convert

        Returns:
            Dict representation of the model instance
        """
        if self.schema:
            # Use the schema to convert the model to a dictionary
            return self.schema.from_orm(instance).model_dump()

        # Fallback to a simple conversion
        result = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            # Handle foreign keys - return the ID
            if isinstance(field, ForeignKey):
                value = getattr(instance, f"{field.name}_id")
            result[field.name] = value
        return result

    def get_query_optimization_info(self) -> dict[str, Any]:
        """
        Get information about query optimizations applied to this controller.

        Useful for debugging and understanding what optimizations are active.

        Returns:
            Dict with optimization details
        """
        return {
            "auto_optimize": self.auto_optimize,
            "select_related_fields": (
                self.select_related_fields or self._get_foreign_key_fields()
                if self.auto_optimize
                else []
            ),
            "prefetch_related_fields": (
                self.prefetch_related_fields or self._get_many_to_many_fields()
                if self.auto_optimize
                else []
            ),
            "include_reverse_relations": self.include_reverse_relations,
            "ordering": self.ordering,
            "lookup_field": self.lookup_field,
        }
