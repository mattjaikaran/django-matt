# file-length-max: 500
"""
Resource abstraction — collapse CRUD boilerplate to 1-10 lines.

All schema generation, field detection, and ViewSet construction happens
at registration time. Zero per-request overhead beyond the underlying views.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from django.db import models

from django_matt.core.schema import create_schema_from_model
from django_matt.resources.actions import ActionDescriptor
from django_matt.views.base import APIView
from django_matt.views.create import CreateView
from django_matt.views.delete import DeleteView
from django_matt.views.list import ListView
from django_matt.views.read import ReadView
from django_matt.views.update import UpdateView
from django_matt.views.viewset import APIViewSet


def _pluralize(name: str) -> str:
    """Simple pluralization for URL prefix generation."""
    if name.endswith("y") and not name.endswith(("ay", "ey", "oy", "uy")):
        return name[:-1] + "ies"
    if name.endswith(("s", "x", "z", "ch", "sh")):
        return name + "es"
    return name + "s"


def _model_name_to_prefix(model: type[models.Model]) -> str:
    """Convert ModelName to /model-names/ URL prefix."""
    # CamelCase to kebab-case
    name = re.sub(r"(?<=[a-z0-9])([A-Z])", r"-\1", model.__name__).lower()
    return "/" + _pluralize(name)


def _detect_search_fields(model: type[models.Model]) -> list[str]:
    """Auto-detect search fields (CharField/TextField) from model."""
    search = []
    for f in model._meta.fields:
        if isinstance(f, (models.CharField, models.TextField)) and not f.primary_key:
            search.append(f.name)
    return search


def _detect_filter_fields(model: type[models.Model]) -> list[str]:
    """Auto-detect filterable fields from model."""
    skip_types = (models.BinaryField, models.FileField, models.ImageField)
    result = []
    for f in model._meta.fields:
        if isinstance(f, skip_types):
            continue
        result.append(f.name)
    return result


@dataclass
class ResourceConfig:
    """Configuration for a resource registration."""

    model: type[models.Model]
    prefix: str | None = None
    tags: list[str] | None = None

    # Schema overrides
    response_schema: Any = None
    create_schema: Any = None
    update_schema: Any = None
    schema_exclude: list[str] | None = None

    # Filtering / search / ordering
    search_fields: list[str] | None = None
    filter_fields: list[str] | None = None
    ordering: str | list[str] | None = None
    ordering_fields: list[str] | None = None

    # Pagination
    page_size: int = 20
    max_page_size: int = 100
    pagination: bool = True

    # Permissions — global or per-operation
    permission_classes: list | None = None
    permissions: dict[str, list] | None = None

    # Operations to include (default: all CRUD)
    operations: list[str] | None = None  # e.g. ["list", "create", "read"]

    # Nested resources
    children: dict[str, Any] | None = None

    # Custom queryset
    get_queryset: Any = None

    # Custom actions
    actions: list[ActionDescriptor] = field(default_factory=list)

    # Lookup field
    lookup_field: str = "id"


def build_viewset(config: ResourceConfig) -> type[APIViewSet]:
    """
    Dynamically build an APIViewSet subclass from a ResourceConfig.

    All schema generation, field detection, and view construction happens here
    at registration time — zero per-request overhead.
    """
    model = config.model
    model_name = model.__name__

    # --- Determine prefix ---
    prefix = config.prefix or _model_name_to_prefix(model)

    # --- Auto-generate schemas at registration time ---
    response_schema = config.response_schema
    if response_schema is None:
        response_schema = create_schema_from_model(
            model,
            name=f"{model_name}Schema",
            exclude=config.schema_exclude,
        )

    create_schema = config.create_schema
    if create_schema is None:
        create_schema = create_schema_from_model(
            model,
            name=f"{model_name}CreateSchema",
            exclude=(config.schema_exclude or []) + ["id"],
        )

    update_schema = config.update_schema
    if update_schema is None:
        # All fields optional for updates
        all_field_names = [
            f.name
            for f in model._meta.fields
            if f.name != "id" and f.name not in (config.schema_exclude or [])
        ]
        update_schema = create_schema_from_model(
            model,
            name=f"{model_name}UpdateSchema",
            exclude=(config.schema_exclude or []) + ["id"],
            optional=all_field_names,
        )

    # --- Auto-detect fields ---
    search_fields = config.search_fields
    if search_fields is None:
        search_fields = _detect_search_fields(model)

    filter_fields = config.filter_fields
    if filter_fields is None:
        filter_fields = _detect_filter_fields(model)

    tags = config.tags or [model_name]

    # --- Determine which operations to include ---
    ops = set(config.operations or ["list", "create", "read", "update", "delete"])

    # --- Per-operation permissions ---
    per_op_perms = config.permissions or {}

    def _perm_classes_for(op: str) -> list | None:
        if op in per_op_perms:
            return per_op_perms[op]
        return config.permission_classes

    # --- Build class attributes ---
    attrs: dict[str, Any] = {
        "model": model,
        "prefix": prefix.strip("/"),
        "tags": tags,
        "default_response_schema": response_schema,
        "permission_classes": config.permission_classes or [],
        "_permission_overrides": per_op_perms,
    }

    lookup_path = "{" + config.lookup_field + "}"

    if "list" in ops:
        attrs["list"] = ListView(
            response_schema=response_schema,
            pagination=config.pagination,
            page_size=config.page_size,
            max_page_size=config.max_page_size,
            search_fields=search_fields,
            filter_fields=filter_fields,
            ordering=config.ordering,
            ordering_fields=config.ordering_fields,
        )

    if "create" in ops:
        attrs["create"] = CreateView(
            request_schema=create_schema,
            response_schema=response_schema,
        )

    if "read" in ops:
        attrs["read"] = ReadView(
            path=lookup_path,
            response_schema=response_schema,
        )

    if "update" in ops:
        attrs["update"] = UpdateView(
            path=lookup_path,
            request_schema=update_schema,
            response_schema=response_schema,
        )

    if "delete" in ops:
        attrs["delete"] = DeleteView(
            path=lookup_path,
        )

    # --- Custom get_queryset ---
    if config.get_queryset is not None:
        _custom_qs = config.get_queryset
        attrs["get_queryset"] = lambda self, request=None, _fn=_custom_qs: _fn(request)

    # --- Build the class name early (needed by action factory) ---
    viewset_name = f"{model_name}AutoViewSet"

    # --- Wire custom actions as additional views ---
    for act in config.actions:
        if act.handler is None:
            continue

        action_path = act.path.strip("/")
        if not action_path:
            action_path = act.handler_name.replace("_", "-")

        # Factory avoids closure capture — all loop vars bound as defaults
        def _make_action_view(
            _path=action_path,
            _method=act.method,
            _handler=act.handler,
            _summary=act.summary,
            _tags=act.tags,
            _name=act.handler_name,
        ):
            class ActionView(APIView):
                path = _path
                methods = [_method]
                summary = _summary

                async def handle(self_view, request, **kwargs):
                    return await _handler(request, **kwargs)

            ActionView.__name__ = f"{_name}_view"
            ActionView.__qualname__ = f"{viewset_name}.{_name}"
            return ActionView(path=_path, summary=_summary, tags=_tags or tags)

        attrs[act.handler_name] = _make_action_view()

    # --- Build the class ---
    viewset_cls = type(viewset_name, (APIViewSet,), attrs)

    # --- Wire nested/child resources ---
    if config.children:
        viewset_cls._child_viewsets = []
        for child_name, child_resource in config.children.items():
            child_viewset = _build_child_viewset(
                parent_model=model,
                parent_prefix=prefix.strip("/"),
                child_name=child_name,
                child_resource=child_resource,
                lookup_field=config.lookup_field,
            )
            viewset_cls._child_viewsets.append(child_viewset)

        # Override as_urls to include children
        _original_as_urls = viewset_cls.as_urls

        @classmethod  # type: ignore[misc]
        def _as_urls_with_children(cls):
            patterns = _original_as_urls.__func__(cls)
            for child_vs in cls._child_viewsets:
                patterns.extend(child_vs.as_urls())
            return patterns

        viewset_cls.as_urls = _as_urls_with_children

    return viewset_cls


def _find_fk_field(child_model: type[models.Model], parent_model: type[models.Model]) -> str:
    """Find the FK field name on child_model that points to parent_model."""
    for f in child_model._meta.fields:
        if isinstance(f, models.ForeignKey) and f.related_model == parent_model:
            return f.attname  # e.g. "project_id"
    raise ValueError(
        f"No ForeignKey from {child_model.__name__} to {parent_model.__name__}. "
        f"Nested resources require a FK relationship."
    )


def _build_child_viewset(
    parent_model: type[models.Model],
    parent_prefix: str,
    child_name: str,
    child_resource,
    lookup_field: str,
) -> type[APIViewSet]:
    """Build a child ViewSet with URL routes scoped under the parent."""
    # child_resource can be a Model class or another resource/viewset
    if isinstance(child_resource, type) and issubclass(child_resource, models.Model):
        child_model = child_resource
        child_config = ResourceConfig(model=child_model)
    elif isinstance(child_resource, type) and issubclass(child_resource, APIViewSet):
        # Already a viewset — just adjust prefix
        child_resource.prefix = f"{parent_prefix}/{{{lookup_field}}}/{child_name}"
        return child_resource
    elif hasattr(child_resource, "model"):
        child_model = child_resource.model
        child_config = ResourceConfig(model=child_model)
    else:
        raise ValueError(
            f"Cannot resolve child resource '{child_name}': must be a Model or ViewSet"
        )

    fk_field = _find_fk_field(child_model, parent_model)
    parent_name = parent_model.__name__.lower()

    child_config.prefix = f"/{parent_prefix}/{{{parent_name}_id}}/{child_name}"

    child_viewset = build_viewset(child_config)

    # Override get_queryset to scope by parent FK
    _fk = fk_field
    _parent_key = f"{parent_name}_id"

    def scoped_get_queryset(self, request=None, _fk_field=_fk, _pk=_parent_key):
        qs = child_model.objects.all()
        if request is not None:
            parent_id = getattr(request, "resolver_match", None)
            if parent_id and parent_id.kwargs:
                pid = parent_id.kwargs.get(_pk)
                if pid:
                    qs = qs.filter(**{_fk_field: pid})
        return qs

    child_viewset.get_queryset = scoped_get_queryset

    return child_viewset


def resource(
    api_or_model=None,
    prefix: str | None = None,
    *,
    permissions: dict[str, list] | list | None = None,
    permission_classes: list | None = None,
    search_fields: list[str] | None = None,
    filter_fields: list[str] | None = None,
    ordering: str | list[str] | None = None,
    ordering_fields: list[str] | None = None,
    page_size: int = 20,
    max_page_size: int = 100,
    pagination: bool = True,
    operations: list[str] | None = None,
    children: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    response_schema: Any = None,
    create_schema: Any = None,
    update_schema: Any = None,
    schema_exclude: list[str] | None = None,
    lookup_field: str = "id",
):
    """
    Register a resource on an API. Works three ways:

    1. One-liner on MattAPI:
       api.resource(Product)

    2. With options on MattAPI:
       api.resource(Product, prefix="/products", permissions={"delete": [IsAdmin]})

    3. As a class decorator:
       @resource(api, prefix="/products")
       class ProductResource:
           model = Product
           search_fields = ["name"]

    Returns the generated APIViewSet subclass.
    """
    # Normalize permissions arg
    if isinstance(permissions, list):
        permission_classes = permissions
        permissions = None
    elif isinstance(permissions, dict):
        pass  # permissions dict stays as-is, permission_classes unchanged

    # --- Case 1 & 2: api.resource(Model, ...) ---
    # Check if api_or_model is a Django model class
    if (
        api_or_model is not None
        and isinstance(api_or_model, type)
        and issubclass(api_or_model, models.Model)
    ):
        config = ResourceConfig(
            model=api_or_model,
            prefix=prefix,
            tags=tags,
            response_schema=response_schema,
            create_schema=create_schema,
            update_schema=update_schema,
            schema_exclude=schema_exclude,
            search_fields=search_fields,
            filter_fields=filter_fields,
            ordering=ordering,
            ordering_fields=ordering_fields,
            page_size=page_size,
            max_page_size=max_page_size,
            pagination=pagination,
            permission_classes=permission_classes,
            permissions=permissions,
            operations=operations,
            children=children,
            lookup_field=lookup_field,
        )
        viewset_cls = build_viewset(config)
        return viewset_cls

    # --- Case 3: @resource(api, prefix="/products") class decorator ---
    api_instance = api_or_model

    def decorator(cls):
        model = getattr(cls, "model", None)
        if model is None:
            raise ValueError(f"Resource class {cls.__name__} must define a 'model' attribute")

        # Collect actions from the class
        actions = []
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name, None)
            if isinstance(attr, ActionDescriptor):
                actions.append(attr)

        # Read overrides from class attributes
        config = ResourceConfig(
            model=model,
            prefix=prefix or getattr(cls, "prefix", None),
            tags=tags or getattr(cls, "tags", None),
            response_schema=response_schema or getattr(cls, "response_schema", None),
            create_schema=create_schema or getattr(cls, "create_schema", None),
            update_schema=update_schema or getattr(cls, "update_schema", None),
            schema_exclude=schema_exclude or getattr(cls, "schema_exclude", None),
            search_fields=search_fields or getattr(cls, "search_fields", None),
            filter_fields=filter_fields or getattr(cls, "filter_fields", None),
            ordering=ordering or getattr(cls, "ordering", None),
            ordering_fields=ordering_fields or getattr(cls, "ordering_fields", None),
            page_size=getattr(cls, "page_size", page_size),
            max_page_size=getattr(cls, "max_page_size", max_page_size),
            pagination=getattr(cls, "pagination", pagination),
            permission_classes=permission_classes or getattr(cls, "permission_classes", None),
            permissions=permissions or getattr(cls, "permissions", None),
            operations=operations or getattr(cls, "operations", None),
            children=children or getattr(cls, "children", None),
            lookup_field=getattr(cls, "lookup_field", lookup_field),
            get_queryset=getattr(cls, "get_queryset", None),
            actions=actions,
        )

        viewset_cls = build_viewset(config)

        # Register with the API if provided
        if api_instance is not None and hasattr(api_instance, "_resource_viewsets"):
            api_instance._resource_viewsets.append(viewset_cls)

        return viewset_cls

    return decorator
