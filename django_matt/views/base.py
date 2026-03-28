"""
Base view classes for Django Matt.

Provides the foundational APIView class that all other views inherit from.
Includes lifecycle hook support for before/after operations.
"""

from typing import Any, Generic, TypeVar

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.http import HttpRequest, JsonResponse

import orjson
from asgiref.sync import sync_to_async
from pydantic import BaseModel, ValidationError

from django_matt.core.errors import APIError, NotFoundAPIError

ModelT = TypeVar("ModelT", bound=models.Model)
SchemaT = TypeVar("SchemaT", bound=BaseModel)


# Import hook system
from django_matt.views.hooks import (
    HookContext,
    HookType,
    StopHookChain,
    create_hook_context,
    run_hooks,
)


class APIView(Generic[ModelT, SchemaT]):
    """
    Base class for composable API views.

    Views are descriptors that can be attached to ViewSets to provide
    specific CRUD operations. Each view defines a single operation
    (list, create, read, update, delete).

    Attributes:
        path: URL path suffix for this view (e.g., "", "{id}")
        methods: HTTP methods this view responds to
        response_schema: Pydantic schema for response serialization
        request_schema: Pydantic schema for request body validation
        summary: OpenAPI summary for this endpoint
        description: OpenAPI description for this endpoint
        tags: OpenAPI tags for this endpoint
        operation_id: OpenAPI operation ID
        enable_hooks: Whether to enable lifecycle hooks (default: True)
    """

    path: str = ""
    methods: list[str] = ["GET"]
    response_schema: type[BaseModel] | None = None
    request_schema: type[BaseModel] | None = None
    summary: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    operation_id: str | None = None
    enable_hooks: bool = True
    validate_model: bool | None = None

    # Set by the ViewSet when attached
    _viewset: "ViewSet | None" = None
    _viewset_attr_name: str | None = None

    def __init__(
        self,
        path: str | None = None,
        response_schema: type[BaseModel] | None = None,
        request_schema: type[BaseModel] | None = None,
        summary: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        operation_id: str | None = None,
        enable_hooks: bool | None = None,
        validate_model: bool | None = None,
        **kwargs,
    ):
        """
        Initialize the view.

        Args:
            path: URL path suffix (overrides class default)
            response_schema: Response serialization schema
            request_schema: Request body validation schema
            summary: OpenAPI summary
            description: OpenAPI description
            tags: OpenAPI tags
            operation_id: OpenAPI operation ID
            enable_hooks: Whether to enable lifecycle hooks (default: True)
        """
        if path is not None:
            self.path = path
        if response_schema is not None:
            self.response_schema = response_schema
        if request_schema is not None:
            self.request_schema = request_schema
        if summary is not None:
            self.summary = summary
        if description is not None:
            self.description = description
        if tags is not None:
            self.tags = tags
        if operation_id is not None:
            self.operation_id = operation_id
        if enable_hooks is not None:
            self.enable_hooks = enable_hooks
        if validate_model is not None:
            self.validate_model = validate_model

        # Store any additional kwargs for subclass customization
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __set_name__(self, owner: type, name: str):
        """Called when the view is assigned to a ViewSet class attribute."""
        self._viewset_attr_name = name

    def __get__(self, obj, objtype=None):
        """Descriptor protocol - return bound view when accessed on instance."""
        if obj is None:
            return self
        return BoundView(self, obj)

    def get_model(self) -> type[models.Model]:
        """Get the Django model from the ViewSet."""
        if self._viewset is None:
            raise ValueError("View not attached to a ViewSet")
        return self._viewset.model

    def get_queryset(self, request: HttpRequest) -> models.QuerySet:
        """
        Get the base queryset for this view.

        Override in subclasses to customize filtering.
        """
        if self._viewset is None:
            raise ValueError("View not attached to a ViewSet")

        if hasattr(self._viewset, "get_queryset"):
            return self._viewset.get_queryset(request)

        return self._viewset.model.objects.all()

    def get_response_schema(self) -> type[BaseModel] | None:
        """Get the response schema, falling back to ViewSet default."""
        if self.response_schema is not None:
            return self.response_schema
        if self._viewset is not None:
            return getattr(self._viewset, "default_response_schema", None)
        return None

    def get_request_schema(self) -> type[BaseModel] | None:
        """Get the request schema, falling back to ViewSet default."""
        if self.request_schema is not None:
            return self.request_schema
        if self._viewset is not None:
            return getattr(self._viewset, "default_request_schema", None)
        return None

    def serialize(self, instance: models.Model) -> dict[str, Any]:
        """Serialize a model instance (with full validation)."""
        schema = self.get_response_schema()
        if schema is not None:
            if hasattr(schema, "from_orm"):
                schema_instance = schema.from_orm(instance)
            else:
                schema_instance = schema.model_validate(instance, from_attributes=True)
            if hasattr(schema_instance, "model_dump_response"):
                return schema_instance.model_dump_response()
            return schema_instance.model_dump()
        return self._model_to_dict(instance)

    def serialize_single(self, instance: models.Model) -> dict[str, Any]:
        """Serialize a single ORM instance without re-validation (model_construct).

        Use for single-object responses (create, read, update) where
        the data comes directly from the database and doesn't need
        Pydantic re-validation. Same fast path as serialize_fast() for lists.
        """
        schema = self.get_response_schema()
        if schema is not None and hasattr(schema, "from_orm_fast"):
            schema_instance = schema.from_orm_fast(instance)
            if hasattr(schema_instance, "model_dump_response"):
                return schema_instance.model_dump_response()
            return schema_instance.model_dump()
        # Fall back to full validation if from_orm_fast not available
        return self.serialize(instance)

    def serialize_fast(self, instance: models.Model) -> dict[str, Any]:
        """Serialize a model instance without re-validation (for lists)."""
        schema = self.get_response_schema()
        if schema is not None and hasattr(schema, "from_orm_fast"):
            schema_instance = schema.from_orm_fast(instance)
            if hasattr(schema_instance, "model_dump_response"):
                return schema_instance.model_dump_response()
            return schema_instance.model_dump()
        return self._model_to_dict(instance)

    def serialize_list(self, queryset: models.QuerySet) -> list[dict[str, Any]]:
        """Serialize a queryset to a list of dicts (fast path, no re-validation)."""
        return [self.serialize_fast(obj) for obj in queryset]

    async def aserialize_list(self, queryset: models.QuerySet) -> list[dict[str, Any]]:
        """Async serialize a queryset to a list of dicts (uses async iteration)."""
        return [self.serialize_fast(obj) async for obj in queryset]

    def optimize_queryset(self, queryset: models.QuerySet) -> models.QuerySet:
        """Auto-apply select_related/prefetch_related based on response schema."""
        schema = self.get_response_schema()
        if schema is None:
            return queryset

        model = queryset.model
        meta = model._meta
        select_fields = []
        prefetch_fields = []

        for field_name in schema.model_fields:
            try:
                field = meta.get_field(field_name)
            except Exception:
                continue
            if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                select_fields.append(field_name)
            elif isinstance(field, models.ManyToManyField):
                prefetch_fields.append(field_name)

        if select_fields:
            queryset = queryset.select_related(*select_fields)
        if prefetch_fields:
            queryset = queryset.prefetch_related(*prefetch_fields)

        return queryset

    def _model_to_dict(self, instance: models.Model) -> dict[str, Any]:
        """Simple model to dict conversion."""
        result = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            elif hasattr(value, "pk"):
                value = value.pk
            result[field.name] = value
        return result

    def validate_request(self, request: HttpRequest) -> BaseModel | None:
        """Validate request body against the request schema."""
        schema = self.get_request_schema()
        if schema is None:
            return None

        try:
            body = orjson.loads(request.body) if request.body else {}
        except (ValueError, orjson.JSONDecodeError):
            raise ValueError("Invalid JSON in request body")

        return schema.model_validate(body)

    def _should_validate_model(self) -> bool:
        """Check if model validation is enabled (per-view overrides ViewSet)."""
        if self.validate_model is not None:
            return self.validate_model
        if self._viewset is not None:
            return getattr(self._viewset, "validate_model", False)
        return False

    async def _validate_model_instance(self, instance: models.Model) -> None:
        """Run Django model full_clean() validation if enabled.

        Raises DjangoValidationError if validation fails.
        """
        if self._should_validate_model():
            await sync_to_async(instance.full_clean)()

    async def handle(self, request: HttpRequest, **kwargs) -> Any:
        """
        Handle the request. Override in subclasses.

        Args:
            request: The HTTP request
            **kwargs: URL path parameters

        Returns:
            Response data (will be serialized to JSON)
        """
        raise NotImplementedError("Subclasses must implement handle()")

    def get_route_info(self) -> dict[str, Any]:
        """Get route information for OpenAPI schema generation."""
        return {
            "path": self.path,
            "methods": self.methods,
            "response_schema": self.get_response_schema(),
            "request_schema": self.get_request_schema(),
            "summary": self.summary or self._generate_summary(),
            "description": self.description,
            "tags": self.tags or (self._viewset.tags if self._viewset else None),
            "operation_id": self.operation_id or self._generate_operation_id(),
        }

    def _generate_summary(self) -> str:
        """Generate a summary from the class name and viewset."""
        class_name = self.__class__.__name__
        if self._viewset is not None:
            model_name = self._viewset.model.__name__
            if "List" in class_name:
                return f"List {model_name}s"
            if "Create" in class_name:
                return f"Create {model_name}"
            if "Read" in class_name or "Retrieve" in class_name:
                return f"Get {model_name}"
            if "Update" in class_name:
                return f"Update {model_name}"
            if "Delete" in class_name:
                return f"Delete {model_name}"
        return class_name

    def _generate_operation_id(self) -> str:
        """Generate an operation ID from the attribute name."""
        if self._viewset_attr_name:
            return self._viewset_attr_name
        return self.__class__.__name__.lower()

    def _create_hook_context(
        self,
        request: HttpRequest,
        hook_type: HookType | None = None,
        instance: models.Model | None = None,
        data: dict[str, Any] | BaseModel | None = None,
        queryset: models.QuerySet | None = None,
        **extra: Any,
    ) -> HookContext:
        """
        Create a HookContext for this view.

        This is used internally by view handlers to create contexts
        for hook execution.
        """
        return create_hook_context(
            request=request,
            viewset=self._viewset,
            view_class=self.__class__,
            hook_type=hook_type,
            instance=instance,
            data=data,
            queryset=queryset,
            **extra,
        )

    async def _run_hooks(
        self,
        hook_type: HookType | str,
        request: HttpRequest,
        value: Any = None,
        instance: models.Model | None = None,
        data: dict[str, Any] | BaseModel | None = None,
        queryset: models.QuerySet | None = None,
        **extra: Any,
    ) -> Any:
        """
        Execute hooks for this view.

        Args:
            hook_type: The type of hook to execute
            request: The HTTP request
            value: The value to pass through the hook chain
            instance: Optional model instance
            data: Optional request data
            queryset: Optional queryset
            **extra: Additional context data

        Returns:
            The transformed value after hooks execute
        """
        if not self.enable_hooks:
            return value

        if isinstance(hook_type, str):
            hook_type = HookType(hook_type)

        context = self._create_hook_context(
            request=request,
            hook_type=hook_type,
            instance=instance,
            data=data,
            queryset=queryset,
            **extra,
        )

        return await run_hooks(
            hook_type=hook_type,
            context=context,
            value=value,
            include_class_hooks=True,
        )

    async def _handle_error(
        self,
        request: HttpRequest,
        error: Exception,
        instance: models.Model | None = None,
    ) -> None:
        """
        Execute error hooks when an exception occurs.

        Args:
            request: The HTTP request
            error: The exception that occurred
            instance: Optional model instance involved
        """
        if not self.enable_hooks:
            return

        context = self._create_hook_context(
            request=request,
            hook_type=HookType.ON_ERROR,
            instance=instance,
            error=error,
        )
        context.error = error

        try:
            await run_hooks(
                hook_type=HookType.ON_ERROR,
                context=context,
                value=error,
                include_class_hooks=True,
            )
        except StopHookChain:
            # Error hooks can stop the chain
            pass
        except Exception:
            # Don't let error hooks cause additional failures
            pass


class BoundView:
    """
    A view bound to a specific ViewSet instance.

    This allows views to access the ViewSet's configuration
    when handling requests. Also handles lifecycle hook error handling.
    """

    def __init__(self, view: APIView, viewset: "ViewSet"):
        self.view = view
        self.viewset = viewset
        # Bind the view to this viewset
        view._viewset = viewset

    async def __call__(self, request: HttpRequest, **kwargs) -> JsonResponse:
        """Handle the request and return a JSON response."""
        # Enforce HTTP method declared on the view
        allowed_methods = getattr(self.view, "methods", None)
        if allowed_methods:
            allowed_upper = {m.upper() for m in allowed_methods}
            if request.method not in allowed_upper:
                response = JsonResponse(
                    {"detail": "Method not allowed"}, status=405
                )
                response["Allow"] = ", ".join(sorted(allowed_upper))
                return response

        # Check per-operation permission overrides first, then viewset-level
        permission_classes = None
        overrides = getattr(self.viewset, "_permission_overrides", None)
        if overrides and self.view._viewset_attr_name:
            permission_classes = overrides.get(self.view._viewset_attr_name)
        if permission_classes is None:
            permission_classes = getattr(self.viewset, "permission_classes", None)
        if permission_classes:
            for perm_class in permission_classes:
                # Support both class references and pre-instantiated instances
                perm = perm_class() if isinstance(perm_class, type) else perm_class
                if not perm.has_permission(request, self.view):
                    status_code = getattr(perm, "status_code", 403)
                    message = getattr(perm, "message", "Permission denied.")
                    return JsonResponse({"detail": message}, status=status_code)

        try:
            result = await self.view.handle(request, **kwargs)

            if isinstance(result, JsonResponse):
                return result

            return JsonResponse(result, safe=False)

        except StopHookChain as e:
            # Hook chain was stopped early - use the stored value
            if e.value is not None:
                if isinstance(e.value, JsonResponse):
                    return e.value
                return JsonResponse(e.value, safe=False)
            return JsonResponse({"detail": "Operation cancelled"}, status=200)

        except DjangoValidationError as e:
            await self.view._handle_error(request, e)
            errors = []
            message_dict = e.message_dict if hasattr(e, "message_dict") else {"__all__": e.messages}
            for field, messages in message_dict.items():
                for msg in messages:
                    errors.append({"field": field, "message": msg})
            return JsonResponse(
                {"detail": "Model validation failed", "errors": errors},
                status=422,
            )
        except ValidationError as e:
            await self.view._handle_error(request, e)
            return JsonResponse(
                {"detail": "Validation error", "errors": e.errors()},
                status=422,
            )
        except NotFoundAPIError as e:
            await self.view._handle_error(request, e)
            return JsonResponse(
                {"detail": str(e), "code": "not_found"},
                status=404,
            )
        except APIError as e:
            await self.view._handle_error(request, e)
            return JsonResponse(
                {"detail": str(e), "code": getattr(e, "code", "error")},
                status=getattr(e, "status_code", 500),
            )
        except ValueError as e:
            await self.view._handle_error(request, e)
            return JsonResponse(
                {"detail": str(e)},
                status=400,
            )
        except Exception as e:
            # Log the error in production
            await self.view._handle_error(request, e)
            return JsonResponse(
                {"detail": str(e)},
                status=500,
            )


# Import ViewSet here to avoid circular import
from django_matt.views.viewset import ViewSet
