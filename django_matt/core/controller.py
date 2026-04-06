from __future__ import annotations

import inspect
from functools import wraps
from typing import TYPE_CHECKING, Any, get_type_hints

import django
from django.conf import settings

import orjson

if TYPE_CHECKING:
    pass
from django.db.models import ForeignKey, ManyToManyField, ManyToOneRel
from django.http import HttpRequest, JsonResponse

from pydantic import BaseModel, ValidationError

from django_matt.core.errors import (
    APIError,
    ConfigurationError,
    ErrorHandler,
    NotFoundAPIError,
    ValidationAPIError,
)

# Module-level cache: avoids re-reading settings on every error
_error_config: dict[str, Any] | None = None

# --- DI auto-wire config (cached at module level) ---
_di_config: bool | None = None


def _get_di_config() -> bool:
    """Check if DI auto-wire is enabled. Cached after first call."""
    global _di_config
    if _di_config is None:
        matt_config = getattr(settings, "DJANGO_MATT", {})
        _di_config = matt_config.get("DI_AUTO_WIRE", False)
    return _di_config


def _reset_di_config() -> None:
    """Reset the cached DI config. Used in tests."""
    global _di_config
    _di_config = None


def _get_error_config() -> dict[str, Any]:
    """Get error handling configuration from settings (cached after first call)."""
    global _error_config
    if _error_config is None:
        config = getattr(settings, "DJANGO_MATT_ERRORS", {})
        _error_config = {
            "debug": config.get("DEBUG", getattr(settings, "DEBUG", False)),
            "include_traceback": config.get("INCLUDE_TRACEBACK", getattr(settings, "DEBUG", False)),
            "include_snippet": config.get("INCLUDE_SNIPPET", getattr(settings, "DEBUG", False)),
        }
    return _error_config


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
    # Each subclass gets its own independent tags list via __init_subclass__.
    # Never use a shared mutable class-level default (tags = []) here —
    # that single list object is shared across ALL subclasses.
    tags: list[str] = []
    auto_error_handling: bool = True  # Enable automatic error handling by default
    permission_classes: list = []
    middleware_classes: list = []

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Give every subclass its own independent tags list so that
        # appending to one subclass never bleeds into another.
        if "tags" not in cls.__dict__:
            cls.tags = []
        if "permission_classes" not in cls.__dict__:
            cls.permission_classes = list(cls.permission_classes)
        if "middleware_classes" not in cls.__dict__:
            cls.middleware_classes = list(cls.middleware_classes)

    def __init__(self):
        self._setup_methods()

    def _setup_methods(self):
        """
        Single-pass setup: dependency injection + error handling for all route methods.

        Caches type hints at init time (not per-request) and wraps each method
        once instead of twice.
        """
        error_config = _get_error_config() if self.auto_error_handling else None
        error_handler = ErrorHandler(debug=error_config["debug"]) if error_config else None

        for method_name in dir(self):
            if method_name.startswith("_"):
                continue

            method = getattr(self, method_name)
            if not callable(method) or not hasattr(method, "_route_info"):
                continue

            # Cache type hints once at init — not per-request
            hints = get_type_hints(method)
            is_coro = inspect.iscoroutinefunction(method)
            takes_request = "request" in inspect.signature(method).parameters

            # Pre-compute which params need Pydantic injection
            pydantic_params = {
                name: ptype
                for name, ptype in hints.items()
                if name != "return"
                and name != "request"
                and inspect.isclass(ptype)
                and issubclass(ptype, BaseModel)
            }

            # Analyze DI params once at init — not per-request
            di_params = None
            if _get_di_config():
                from django_matt.di.depends import DependencyMarker

                sig = inspect.signature(method)
                di_params_found = {}
                for pname, pparam in sig.parameters.items():
                    if pname in ("self", "cls", "request"):
                        continue
                    if pparam.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                        continue
                    if isinstance(pparam.default, DependencyMarker):
                        di_params_found[pname] = pparam.default
                di_params = di_params_found if di_params_found else None

            # Pre-resolve permission instances once at init — not per-request
            # Method-level @guard() overrides controller-level permission_classes
            _guard = getattr(method, "_guard_permissions", None)
            _perm_sources = _guard if _guard is not None else self.permission_classes
            _permission_instances = None
            if _perm_sources:
                _permission_instances = [
                    cls() if isinstance(cls, type) else cls
                    for cls in _perm_sources
                ]

            # Pre-resolve route-scoped middleware stack once at init
            _mw_stack = None
            if self.middleware_classes or getattr(method, "_use_middleware", None):
                from django_matt.middleware.scoped import _resolve_middleware_stack

                _mw_stack = _resolve_middleware_stack(
                    self.middleware_classes,
                    getattr(method, "_use_middleware", None),
                    getattr(method, "_skip_middleware", None),
                )

            @wraps(method)
            async def wrapper(
                request,
                *args,
                _method=method,
                _is_coro=is_coro,
                _pydantic_params=pydantic_params,
                _error_handler=error_handler,
                _error_config=error_config,
                _di_params=di_params,
                _perms=_permission_instances,
                _takes_request=takes_request,
                _middleware_stack=_mw_stack,
                **kwargs,
            ):
                try:
                    # Check controller-level permissions (auth middleware already ran)
                    if _perms:
                        for perm in _perms:
                            if not perm.has_permission(request, None):
                                status_code = getattr(perm, "status_code", 403)
                                message = getattr(perm, "message", "Permission denied.")
                                return JsonResponse({"detail": message}, status=status_code)

                    # Parse body once with orjson if needed
                    if (
                        _pydantic_params
                        and request.body
                        and request.content_type == "application/json"
                    ):
                        try:
                            body_data = orjson.loads(request.body)
                        except (ValueError, orjson.JSONDecodeError):
                            return JsonResponse({"detail": "Invalid JSON"}, status=400)

                        for param_name, param_type in _pydantic_params.items():
                            try:
                                kwargs[param_name] = param_type(**body_data)
                            except ValidationError as e:
                                return JsonResponse(
                                    {"detail": "Validation error", "errors": e.errors()},
                                    status=422,
                                )

                    # Inner handler: DI resolution + method call
                    async def _inner_handler(
                        _request,
                        *_args,
                        _method=_method,
                        _is_coro=_is_coro,
                        _di_params=_di_params,
                        _takes_request=_takes_request,
                        **_kwargs,
                    ):
                        scope_token = None
                        if _di_params is not None:
                            from django_matt.di.container import _scoped_instances
                            from django_matt.di.depends import aresolve_dependencies

                            if _scoped_instances.get() is None:
                                scope_token = _scoped_instances.set({})

                            try:
                                deps = await aresolve_dependencies(
                                    _method,
                                    request=_request,
                                    **_kwargs,
                                )
                                _kwargs.update(deps)
                            except Exception:
                                if scope_token is not None:
                                    _scoped_instances.reset(scope_token)
                                raise

                        try:
                            if _takes_request:
                                call_args = (_request, *_args)
                            else:
                                call_args = _args
                            if _is_coro:
                                result = await _method(*call_args, **_kwargs)
                            else:
                                result = _method(*call_args, **_kwargs)

                            return result
                        finally:
                            if scope_token is not None:
                                _scoped_instances.reset(scope_token)

                    # Execute through middleware stack or call directly
                    if _middleware_stack is not None:
                        return await _middleware_stack.execute(
                            request, _inner_handler, *args, **kwargs
                        )
                    return await _inner_handler(request, *args, **kwargs)

                except Exception as e:
                    if _error_config is None:
                        raise  # error handling disabled
                    if hasattr(self, "handle_exception"):
                        return self.handle_exception(e, request)
                    error_detail = _error_handler.capture_exception(e, request)
                    return error_detail.to_response(
                        include_traceback=_error_config["include_traceback"],
                        include_snippet=_error_config["include_snippet"],
                    )

            setattr(self, method_name, wrapper)


class APIController(Controller):
    """
    Controller specifically for API endpoints.
    Provides additional functionality for API-specific concerns.
    """

    # Class-level error handler — shared across all instances
    _error_handler: ErrorHandler | None = None

    def handle_exception(self, exc: Exception, request: HttpRequest = None) -> JsonResponse:
        """
        Handle exceptions raised during request processing.
        Override this method to customize exception handling.
        """
        error_config = _get_error_config()

        # Lazy-init class-level error handler
        if APIController._error_handler is None:
            APIController._error_handler = ErrorHandler(debug=error_config["debug"])

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
        error_detail = APIController._error_handler.capture_exception(exc, request)
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

    # Pagination settings
    default_limit: int = 20
    max_limit: int = 100

    # Allowed lookup suffixes for filter_queryset security
    ALLOWED_LOOKUPS: frozenset[str] = frozenset(
        {
            "exact",
            "iexact",
            "contains",
            "icontains",
            "gt",
            "gte",
            "lt",
            "lte",
            "in",
            "startswith",
            "istartswith",
            "endswith",
            "iendswith",
            "isnull",
            "range",
            "date",
            "year",
            "month",
            "day",
        }
    )

    def __init__(self):
        super().__init__()
        # Cache field introspection once at init — not per-request
        if self.model:
            self._valid_filter_fields = frozenset(f.name for f in self.model._meta.fields)
            self._fk_fields = self._get_foreign_key_fields()
            self._m2m_fields = self._get_many_to_many_fields()
        else:
            self._valid_filter_fields = frozenset()
            self._fk_fields = []
            self._m2m_fields = []

    def get_queryset(self):
        """
        Get the base queryset for this controller.

        Override this method to customize the base queryset (e.g., filtering by user).

        Returns:
            QuerySet: The base queryset for this model
        """
        if not self.model:
            raise ConfigurationError("Model not specified")
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

        # Use explicitly configured fields or cached auto-detected fields
        if self.select_related_fields:
            queryset = queryset.select_related(*self.select_related_fields)
        elif self.auto_optimize and self._fk_fields:
            queryset = queryset.select_related(*self._fk_fields)

        if self.prefetch_related_fields:
            queryset = queryset.prefetch_related(*self.prefetch_related_fields)
        elif self.auto_optimize:
            prefetch_fields = list(self._m2m_fields)
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

        Validates lookup suffixes against ALLOWED_LOOKUPS whitelist to prevent
        traversal attacks (e.g., field__password, field__secret).

        Override this method to customize filtering behavior.

        Args:
            queryset: The queryset to filter
            request: The HTTP request containing query parameters

        Returns:
            QuerySet: The filtered queryset

        Raises:
            ValidationAPIError: If an unknown lookup suffix is used
        """
        for key, value in request.GET.items():
            # Skip pagination and special parameters
            if key in ("page", "page_size", "limit", "offset", "ordering", "format"):
                continue

            # Handle field lookups (e.g., name__icontains) — uses cached field set
            parts = key.split("__")
            field_name = parts[0]
            if field_name in self._valid_filter_fields:
                # Validate lookup suffix if present
                if len(parts) > 1:
                    lookup = parts[-1]
                    if lookup not in self.ALLOWED_LOOKUPS:
                        raise ValidationAPIError(
                            message=f"Invalid lookup '{lookup}' for field '{field_name}'",
                            field=field_name,
                            code="invalid_lookup",
                        )
                queryset = queryset.filter(**{key: value})

        return queryset

    def _get_pagination_params(self, request: HttpRequest) -> tuple[int, int]:
        """
        Extract and validate limit/offset from request query parameters.

        Returns:
            Tuple of (limit, offset) with bounds enforced.
        """
        try:
            limit = int(request.GET.get("limit", self.default_limit))
        except (ValueError, TypeError):
            limit = self.default_limit
        if limit <= 0:
            limit = self.default_limit
        limit = min(limit, self.max_limit)

        try:
            offset = int(request.GET.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        offset = max(0, offset)

        return limit, offset

    async def list(self, request: HttpRequest) -> dict[str, Any]:
        """
        List instances of the model with limit/offset pagination and async iteration.

        Uses Django's async ORM methods for non-blocking database access.

        Query parameters:
            limit: Maximum items to return (default: 20, max: 100)
            offset: Number of items to skip (default: 0)

        Args:
            request: The HTTP request

        Returns:
            Dict with 'items', 'count' (total), 'limit', and 'offset'
        """
        queryset = self.get_optimized_queryset()
        queryset = self.filter_queryset(queryset, request)

        # Count total before slicing
        count = await queryset.acount()

        # Apply pagination
        limit, offset = self._get_pagination_params(request)
        paginated_qs = queryset[offset : offset + limit]

        # Use fast serialization (model_construct, no re-validation)
        items = []
        async for item in paginated_qs:
            items.append(self._model_to_dict_fast(item))

        return {
            "items": items,
            "count": count,
            "limit": limit,
            "offset": offset,
        }

    async def retrieve(self, request: HttpRequest, id: str) -> dict[str, Any]:
        """
        Retrieve a single instance of the model by ID using async ORM.

        Args:
            request: The HTTP request
            id: The ID of the object to retrieve

        Returns:
            Dict representation of the model instance
        """
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
            raise ConfigurationError("Model not specified")

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

        Uses get_queryset() to respect controller-level filtering
        (e.g., tenant isolation, soft-delete scoping).

        Args:
            request: The HTTP request
            id: The ID of the object to delete

        Returns:
            Dict with 'deleted' and 'id' on success
        """
        try:
            # Use get_queryset() — never bypass controller filtering
            instance = await self.get_queryset().aget(**{self.lookup_field: id})
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
            raise ConfigurationError("Model not specified")

        # Convert Pydantic models to model instances
        model_instances = [self.model(**item.model_dump(exclude_unset=True)) for item in items]

        # Use async bulk_create (Django 4.1+)
        created = await self.model.objects.abulk_create(model_instances)

        return {
            "items": [self._model_to_dict_fast(instance) for instance in created],
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
            raise ConfigurationError("Model not specified")

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
            raise ConfigurationError("Model not specified")

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
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset, request)
        total = await queryset.acount()
        return {"count": total}

    def _model_to_dict(self, instance) -> dict[str, Any]:
        """Convert a model instance to a dict (with full validation)."""
        if self.schema:
            schema_instance = self.schema.from_orm(instance)
            if hasattr(schema_instance, "model_dump_response"):
                return schema_instance.model_dump_response()
            return schema_instance.model_dump()
        return self._model_to_dict_raw(instance)

    def _model_to_dict_fast(self, instance) -> dict[str, Any]:
        """Convert a model instance to a dict (no re-validation, for list serialization)."""
        if self.schema and hasattr(self.schema, "from_orm_fast"):
            schema_instance = self.schema.from_orm_fast(instance)
            if hasattr(schema_instance, "model_dump_response"):
                return schema_instance.model_dump_response()
            return schema_instance.model_dump()
        return self._model_to_dict_raw(instance)

    def _model_to_dict_raw(self, instance) -> dict[str, Any]:
        """Fallback: field-by-field conversion without schema."""
        result = {}
        for field in instance._meta.fields:
            if isinstance(field, ForeignKey):
                result[field.name] = getattr(instance, f"{field.name}_id")
            else:
                result[field.name] = getattr(instance, field.name)
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
