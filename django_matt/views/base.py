"""
Base view classes for Django Matt.

Provides the foundational APIView class that all other views inherit from.
"""

from typing import Any, Generic, TypeVar

from django.db import models
from django.http import HttpRequest, JsonResponse

from pydantic import BaseModel, ValidationError

from django_matt.core.errors import APIError, NotFoundAPIError

ModelT = TypeVar("ModelT", bound=models.Model)
SchemaT = TypeVar("SchemaT", bound=BaseModel)


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
    """

    path: str = ""
    methods: list[str] = ["GET"]
    response_schema: type[BaseModel] | None = None
    request_schema: type[BaseModel] | None = None
    summary: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    operation_id: str | None = None

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
        """
        Serialize a model instance to a dictionary.

        Uses the response schema if available, otherwise falls back
        to basic field serialization.
        """
        schema = self.get_response_schema()
        if schema is not None:
            if hasattr(schema, "from_orm"):
                return schema.from_orm(instance).model_dump()
            return schema.model_validate(instance, from_attributes=True).model_dump()

        # Fallback to simple serialization
        return self._model_to_dict(instance)

    def serialize_list(self, queryset: models.QuerySet) -> list[dict[str, Any]]:
        """Serialize a queryset to a list of dictionaries."""
        return [self.serialize(obj) for obj in queryset]

    def _model_to_dict(self, instance: models.Model) -> dict[str, Any]:
        """Simple model to dict conversion."""
        result = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            # Handle special types
            if hasattr(value, "isoformat"):  # datetime, date, time
                value = value.isoformat()
            elif hasattr(value, "pk"):  # ForeignKey
                value = value.pk
            result[field.name] = value
        return result

    def validate_request(self, request: HttpRequest) -> BaseModel | None:
        """
        Validate request body against the request schema.

        Returns:
            Validated Pydantic model instance, or None if no schema

        Raises:
            ValidationError: If validation fails
        """
        schema = self.get_request_schema()
        if schema is None:
            return None

        import json

        try:
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in request body")

        return schema.model_validate(body)

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


class BoundView:
    """
    A view bound to a specific ViewSet instance.

    This allows views to access the ViewSet's configuration
    when handling requests.
    """

    def __init__(self, view: APIView, viewset: "ViewSet"):
        self.view = view
        self.viewset = viewset
        # Bind the view to this viewset
        view._viewset = viewset

    async def __call__(self, request: HttpRequest, **kwargs) -> JsonResponse:
        """Handle the request and return a JSON response."""
        try:
            result = await self.view.handle(request, **kwargs)

            if isinstance(result, JsonResponse):
                return result

            return JsonResponse(result, safe=False)

        except ValidationError as e:
            return JsonResponse(
                {"detail": "Validation error", "errors": e.errors()},
                status=422,
            )
        except NotFoundAPIError as e:
            return JsonResponse(
                {"detail": str(e), "code": "not_found"},
                status=404,
            )
        except APIError as e:
            return JsonResponse(
                {"detail": str(e), "code": getattr(e, "code", "error")},
                status=getattr(e, "status_code", 500),
            )
        except ValueError as e:
            return JsonResponse(
                {"detail": str(e)},
                status=400,
            )
        except Exception as e:
            # Log the error in production
            return JsonResponse(
                {"detail": str(e)},
                status=500,
            )


# Import ViewSet here to avoid circular import
from django_matt.views.viewset import ViewSet
