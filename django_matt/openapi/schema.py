"""
OpenAPI schema generation for Django Matt.

Generates OpenAPI 3.1.0 compatible schemas from registered routes and controllers.
"""

import inspect
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints
from uuid import UUID

from django.conf import settings

from pydantic import BaseModel

# Permission class names that indicate auth is required
_AUTH_PERMISSION_NAMES: frozenset[str] = frozenset({
    "IsAuthenticated",
    "IsAdmin",
    "IsStaff",
    "IsSuperUser",
    "IsOwner",
    "HasRole",
    "HasPermission",
})

# Python type to OpenAPI type mapping
TYPE_MAP: dict[type, dict[str, str]] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    bytes: {"type": "string", "format": "binary"},
    datetime: {"type": "string", "format": "date-time"},
    date: {"type": "string", "format": "date"},
    time: {"type": "string", "format": "time"},
    Decimal: {"type": "number"},
    UUID: {"type": "string", "format": "uuid"},
}


class OpenAPISchema:
    """
    Generates OpenAPI 3.1.0 schema from Django Matt routes.

    Usage:
        schema = OpenAPISchema(
            title="My API",
            version="1.0.0",
            description="My awesome API",
        )
        schema.add_routes(router.routes)
        openapi_dict = schema.build()
    """

    def __init__(
        self,
        title: str = "Django Matt API",
        version: str = "1.0.0",
        description: str = "",
        terms_of_service: str | None = None,
        contact: dict[str, str] | None = None,
        license_info: dict[str, str] | None = None,
        servers: list[dict[str, str]] | None = None,
    ):
        self.title = title
        self.version = version
        self.description = description
        self.terms_of_service = terms_of_service
        self.contact = contact
        self.license_info = license_info
        self.servers = servers or []

        self.paths: dict[str, dict] = {}
        self.components: dict[str, dict] = {"schemas": {}}
        self.tags: list[dict[str, str]] = []
        self._tag_names: set[str] = set()
        # Track model classes per base name for collision detection
        self._schema_classes: dict[str, set[type]] = {}
        # Cache of model class -> qualified base name (after collision resolution)
        self._qualified_names: dict[type, str] = {}

    def add_routes(self, routes: list[dict]) -> None:
        """Add routes from a router to the schema."""
        for route in routes:
            self._add_route(route)

    def add_controller(self, controller_class: type) -> None:
        """Add routes from a controller class."""
        controller = controller_class()
        prefix = getattr(controller, "prefix", "")
        tags = getattr(controller, "tags", [])
        permission_classes = getattr(controller, "permission_classes", [])

        for method_name in dir(controller):
            if method_name.startswith("_"):
                continue

            method = getattr(controller, method_name)
            if not callable(method):
                continue

            route_info = getattr(method, "_route_info", None)
            if not route_info:
                continue

            route = {
                "path": prefix + route_info["path"],
                "endpoint": method,
                "methods": route_info["methods"],
                "name": route_info.get("name", method_name),
                "response_model": route_info.get("response_model"),
                "status_code": route_info.get("status_code", 200),
                "tags": route_info.get("tags", []) or tags,
                "permission_classes": permission_classes,
                "responses": route_info.get("responses", {}),
            }
            self._add_route(route)

    def _add_route(self, route: dict) -> None:
        """Add a single route to the schema."""
        path = self._convert_path_params(route["path"])

        if path not in self.paths:
            self.paths[path] = {}

        for method in route["methods"]:
            method_lower = method.lower()
            operation = self._build_operation(route, method)
            self.paths[path][method_lower] = operation

    def _convert_path_params(self, path: str) -> str:
        """Convert Django path params to OpenAPI format.

        Django: /users/<int:user_id>/
        Django Matt: /users/{user_id}/
        OpenAPI: /users/{user_id}
        """
        # Already in OpenAPI format if using {param}
        # Remove trailing slash for OpenAPI consistency
        if path.endswith("/") and path != "/":
            path = path.rstrip("/")
        return path

    def _build_operation(self, route: dict, method: str) -> dict:
        """Build an OpenAPI operation object for a route."""
        endpoint = route["endpoint"]
        operation: dict[str, Any] = {
            "operationId": route["name"],
            "responses": {},
        }

        # Add summary from docstring
        if endpoint.__doc__:
            lines = endpoint.__doc__.strip().split("\n")
            operation["summary"] = lines[0].strip()
            if len(lines) > 1:
                operation["description"] = "\n".join(lines[1:]).strip()

        # Add tags
        tags = route.get("tags", [])
        if tags:
            operation["tags"] = tags
            for tag in tags:
                if tag not in self._tag_names:
                    self._tag_names.add(tag)
                    self.tags.append({"name": tag})

        # Add parameters from function signature
        parameters = self._extract_parameters(endpoint, route["path"])
        if parameters:
            operation["parameters"] = parameters

        # Add request body for POST/PUT/PATCH
        if method.upper() in ("POST", "PUT", "PATCH"):
            request_body = self._extract_request_body(endpoint)
            if request_body:
                operation["requestBody"] = request_body

        # Add response
        response_model = route.get("response_model")
        status_code = route.get("status_code", 200)
        extra_responses: dict[int, type] = route.get("responses", {})
        operation["responses"] = self._build_responses(
            response_model, status_code, extra_responses
        )

        # Add permission extension fields (x-auth-required, x-permissions, x-roles)
        extensions = self._extract_permission_extensions(endpoint, route)
        operation.update(extensions)

        return operation

    def _extract_permission_extensions(
        self, endpoint: Any, route: dict
    ) -> dict[str, Any]:
        """Extract permission metadata from endpoint and route into OpenAPI extensions.

        Returns a dict with any applicable ``x-auth-required``, ``x-permissions``,
        and ``x-roles`` fields. Empty collections are omitted.
        """
        extensions: dict[str, Any] = {}
        roles: list[str] = []
        permissions: list[str] = []
        auth_required = False

        # --- Gather permission classes (controller-level or @guard override) ---
        # Method-level @guard() overrides controller-level permission_classes
        guard_perms = getattr(endpoint, "_guard_permissions", None)
        perm_classes = (
            guard_perms
            if guard_perms is not None
            else route.get("permission_classes", [])
        )

        # Check if _allow_any is set (explicitly public)
        if getattr(endpoint, "_allow_any", False):
            perm_classes = []

        for perm_cls in perm_classes:
            cls = perm_cls if isinstance(perm_cls, type) else type(perm_cls)
            cls_name = cls.__name__

            if cls_name in _AUTH_PERMISSION_NAMES:
                auth_required = True

            # Extract roles from HasRole instances
            if cls_name == "HasRole":
                instance = perm_cls if not isinstance(perm_cls, type) else None
                if instance is not None:
                    instance_roles = getattr(instance, "roles", [])
                    roles.extend(instance_roles)

            # Extract permissions from HasPermission instances
            if cls_name == "HasPermission":
                instance = perm_cls if not isinstance(perm_cls, type) else None
                if instance is not None:
                    instance_perms = getattr(instance, "permissions", [])
                    permissions.extend(instance_perms)

        # --- Check decorator-set attributes ---
        required_roles = getattr(endpoint, "_required_roles", None)
        if required_roles:
            roles.extend(required_roles)
            auth_required = True

        required_permissions = getattr(endpoint, "_required_permissions", None)
        if required_permissions:
            permissions.extend(required_permissions)
            auth_required = True

        # --- Build extension fields (only include when non-empty) ---
        if auth_required:
            extensions["x-auth-required"] = True

        if roles:
            extensions["x-roles"] = sorted(set(roles))

        if permissions:
            extensions["x-permissions"] = sorted(set(permissions))

        return extensions

    def _extract_parameters(self, endpoint: callable, path: str) -> list[dict]:
        """Extract query and path parameters from endpoint signature."""
        parameters = []

        try:
            hints = get_type_hints(endpoint)
        except Exception:
            hints = {}

        sig = inspect.signature(endpoint)

        # Find path parameters from the path string
        path_params = set()
        import re

        for match in re.finditer(r"\{(\w+)\}", path):
            path_params.add(match.group(1))

        for param_name, param in sig.parameters.items():
            # Skip self, request, and body parameters
            if param_name in ("self", "request", "data", "body"):
                continue

            param_type = hints.get(param_name, str)

            # Skip Pydantic models (they're request body)
            if inspect.isclass(param_type) and issubclass(param_type, BaseModel):
                continue

            # Determine if path or query parameter
            in_location = "path" if param_name in path_params else "query"

            param_schema = self._type_to_schema(param_type)
            param_def: dict[str, Any] = {
                "name": param_name,
                "in": in_location,
                "schema": param_schema,
            }

            # Path parameters are always required
            if in_location == "path" or param.default is inspect.Parameter.empty:
                param_def["required"] = True

            parameters.append(param_def)

        return parameters

    def _extract_request_body(self, endpoint: callable) -> dict | None:
        """Extract request body schema from endpoint signature."""
        try:
            hints = get_type_hints(endpoint)
        except Exception:
            return None

        sig = inspect.signature(endpoint)

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "request"):
                continue

            param_type = hints.get(param_name)
            if param_type and inspect.isclass(param_type) and issubclass(param_type, BaseModel):
                schema_ref = self._register_schema(param_type, mode="validation")
                return {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": schema_ref,
                        }
                    },
                }

        return None

    def _build_responses(
        self,
        response_model: type | None,
        status_code: int,
        extra_responses: dict[int, type] | None = None,
    ) -> dict:
        """Build OpenAPI responses object.

        Args:
            response_model: The primary success response Pydantic model.
            status_code: The HTTP status code for the success response.
            extra_responses: Optional mapping of status codes to Pydantic
                models for additional response types (e.g. error schemas).
        """
        responses: dict[str, Any] = {}

        if (
            response_model
            and inspect.isclass(response_model)
            and issubclass(response_model, BaseModel)
        ):
            schema_ref = self._register_schema(response_model, mode="serialization")
            responses[str(status_code)] = {
                "description": "Successful response",
                "content": {
                    "application/json": {
                        "schema": schema_ref,
                    }
                },
            }
        else:
            responses[str(status_code)] = {
                "description": "Successful response",
                "content": {
                    "application/json": {
                        "schema": {"type": "object"},
                    }
                },
            }

        # Merge extra response schemas (do not overwrite the primary success entry)
        if extra_responses:
            for code, model in extra_responses.items():
                code_str = str(code)
                if code_str in responses:
                    # Don't overwrite the primary success response
                    continue
                if (
                    inspect.isclass(model)
                    and issubclass(model, BaseModel)
                ):
                    schema_ref = self._register_schema(model, mode="serialization")
                    responses[code_str] = {
                        "description": model.__doc__ or f"{code} response",
                        "content": {
                            "application/json": {
                                "schema": schema_ref,
                            }
                        },
                    }

        # Add common error responses
        responses["422"] = {
            "description": "Validation Error",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {"type": "string"},
                            "errors": {"type": "array", "items": {"type": "object"}},
                        },
                    }
                }
            },
        }

        return responses

    @staticmethod
    def _qualified_schema_names_enabled() -> bool:
        """Return True if the QUALIFIED_SCHEMA_NAMES setting is enabled."""
        matt_config = getattr(settings, "DJANGO_MATT", {})
        return bool(matt_config.get("QUALIFIED_SCHEMA_NAMES", False))

    @staticmethod
    def _compute_qualified_name(model: type) -> str:
        """Compute a qualified schema name from the model's module.

        Uses the app label (last meaningful module segment before the file
        containing the class) to prefix the class name, e.g.
        ``accounts.UserSchema``.
        """
        module = model.__module__ or ""
        parts = module.split(".")
        # Strip common trailing module names that aren't meaningful qualifiers
        _strip = {"schemas", "models", "serializers", "types"}
        # Walk backwards to find the first meaningful segment
        for part in reversed(parts):
            if part not in _strip:
                return f"{part}.{model.__name__}"
        # Fallback: use last segment
        if parts:
            return f"{parts[-1]}.{model.__name__}"
        return model.__name__

    def _resolve_base_name(self, model: type[BaseModel]) -> str:
        """Resolve the base component name for a model.

        When ``QUALIFIED_SCHEMA_NAMES`` is enabled, always uses qualified
        names.  Otherwise, uses the bare class name but automatically
        qualifies when a collision is detected (two different model classes
        sharing the same ``__name__``).
        """
        # Already resolved — return cached value
        if model in self._qualified_names:
            return self._qualified_names[model]

        class_name = model.__name__
        use_qualified = self._qualified_schema_names_enabled()

        if use_qualified:
            name = self._compute_qualified_name(model)
            self._qualified_names[model] = name
            self._schema_classes.setdefault(class_name, set()).add(model)
            return name

        # Default mode: detect collisions
        existing = self._schema_classes.setdefault(class_name, set())
        existing.add(model)

        if len(existing) > 1:
            # Collision detected — retroactively qualify ALL models with this name
            self._retroactive_qualify(class_name)
            return self._qualified_names[model]

        # No collision — use bare name
        self._qualified_names[model] = class_name
        return class_name

    def _retroactive_qualify(self, class_name: str) -> None:
        """Qualify all models that share *class_name*, rewriting existing refs."""
        models = self._schema_classes[class_name]
        for m in models:
            old_name = self._qualified_names.get(m)
            new_name = self._compute_qualified_name(m)
            self._qualified_names[m] = new_name

            if old_name is not None and old_name != new_name:
                # Rename existing component entries and rewrite $refs
                for mode_suffix in ("Request", "Response"):
                    old_key = f"{old_name}{mode_suffix}"
                    new_key = f"{new_name}{mode_suffix}"
                    if old_key in self.components["schemas"]:
                        self.components["schemas"][new_key] = (
                            self.components["schemas"].pop(old_key)
                        )
                        self._rewrite_refs(
                            f"#/components/schemas/{old_key}",
                            f"#/components/schemas/{new_key}",
                        )
                # Also update _schema_modes keys
                if hasattr(self, "_schema_modes") and old_name in self._schema_modes:
                    self._schema_modes[new_name] = self._schema_modes.pop(old_name)

    def _register_schema(
        self,
        model: type[BaseModel],
        mode: str = "validation",
    ) -> dict:
        """Register a Pydantic model as a component schema and return a reference.

        Args:
            model: The Pydantic model class to register.
            mode: ``'validation'`` for request schemas, ``'serialization'``
                  for response schemas.  Pydantic uses this to decide which
                  fields are required and which computed fields to include.

        Internally, schemas are always stored under a suffixed key
        (``{Name}Request`` / ``{Name}Response``).  During :meth:`build`, if a
        model was only registered in one mode, the suffix is stripped back to
        the bare class name for cleaner output.  When both modes are present
        *and* they differ, both suffixed entries are kept so OpenAPI consumers
        (and ``typegen/``) see accurate types for each direction.
        """
        base_name = self._resolve_base_name(model)
        suffixed_name = self._component_name_for(base_name, mode)

        # Track which modes have been registered per model name.
        if not hasattr(self, "_schema_modes"):
            self._schema_modes: dict[str, dict[str, dict]] = {}

        mode_entry = self._schema_modes.setdefault(base_name, {})

        # Already registered — return the ref immediately.
        if mode in mode_entry:
            return {"$ref": f"#/components/schemas/{suffixed_name}"}

        # Generate the JSON schema with the requested mode.
        try:
            from django_matt.core.schema import _get_camel_case_config

            _by_alias = _get_camel_case_config()
            json_schema = model.model_json_schema(mode=mode, by_alias=_by_alias)
            # Hoist $defs into top-level components
            if "$defs" in json_schema:
                for def_name, def_schema in json_schema["$defs"].items():
                    if def_name not in self.components["schemas"]:
                        self.components["schemas"][def_name] = def_schema
                del json_schema["$defs"]
        except Exception:
            json_schema = {"type": "object"}

        mode_entry[mode] = json_schema
        self.components["schemas"][suffixed_name] = json_schema

        return {"$ref": f"#/components/schemas/{suffixed_name}"}

    # -- helpers for mode-aware component naming --

    @staticmethod
    def _component_name_for(base_name: str, mode: str) -> str:
        """Return the suffixed component name for a given mode."""
        if mode == "serialization":
            return f"{base_name}Response"
        return f"{base_name}Request"

    def _simplify_component_names(self) -> None:
        """Collapse suffixed component names to bare names where possible.

        Called during :meth:`build`.  For each model that was only registered
        in a single mode, or where both modes produced identical schemas,
        the suffixed entry is replaced with the bare class name and all
        ``$ref`` pointers in ``paths`` are rewritten to match.
        """
        if not hasattr(self, "_schema_modes"):
            return

        for base_name, modes in self._schema_modes.items():
            if len(modes) == 1:
                # Single mode — rename suffix to bare name.
                (mode,) = modes
                suffixed = self._component_name_for(base_name, mode)
                if suffixed in self.components["schemas"]:
                    self.components["schemas"][base_name] = self.components["schemas"].pop(
                        suffixed
                    )
                    self._rewrite_refs(
                        f"#/components/schemas/{suffixed}",
                        f"#/components/schemas/{base_name}",
                    )
            elif len(modes) == 2:
                val_schema = modes.get("validation")
                ser_schema = modes.get("serialization")
                if val_schema == ser_schema:
                    # Identical — merge into bare name, drop both suffixed.
                    for m in ("validation", "serialization"):
                        suf = self._component_name_for(base_name, m)
                        if suf in self.components["schemas"]:
                            self.components["schemas"].pop(suf, None)
                            self._rewrite_refs(
                                f"#/components/schemas/{suf}",
                                f"#/components/schemas/{base_name}",
                            )
                    # Store once under bare name.
                    self.components["schemas"][base_name] = val_schema
                # else: schemas differ — keep both suffixed names.

    def _rewrite_refs(self, old_ref: str, new_ref: str) -> None:
        """Rewrite all ``$ref`` values in paths from *old_ref* to *new_ref*."""
        def _walk(obj: Any) -> None:
            if isinstance(obj, dict):
                if obj.get("$ref") == old_ref:
                    obj["$ref"] = new_ref
                for v in obj.values():
                    _walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    _walk(item)

        _walk(self.paths)

    def _type_to_schema(self, python_type: type) -> dict:
        """Convert a Python type to an OpenAPI schema."""
        # Handle None type
        if python_type is type(None):
            return {"type": "null"}

        # Handle basic types
        if python_type in TYPE_MAP:
            return TYPE_MAP[python_type].copy()

        # Handle Optional types (Union with None)
        origin = get_origin(python_type)
        if origin is Union:
            args = get_args(python_type)
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                schema = self._type_to_schema(non_none_args[0])
                schema["nullable"] = True
                return schema

        # Handle Literal types → enum constraint
        if origin is Literal:
            args = get_args(python_type)
            if all(isinstance(v, str) for v in args):
                return {"type": "string", "enum": list(args)}
            if all(isinstance(v, int) and not isinstance(v, bool) for v in args):
                return {"type": "integer", "enum": list(args)}
            return {"enum": list(args)}

        # Handle List types
        if origin is list:
            args = get_args(python_type)
            item_type = args[0] if args else str
            return {
                "type": "array",
                "items": self._type_to_schema(item_type),
            }

        # Handle Dict types
        if origin is dict:
            return {"type": "object"}

        # Handle Enum types
        if inspect.isclass(python_type) and issubclass(python_type, Enum):
            return {
                "type": "string",
                "enum": [e.value for e in python_type],
            }

        # Handle Pydantic models (in parameter context, treat as request/validation)
        if inspect.isclass(python_type) and issubclass(python_type, BaseModel):
            return self._register_schema(python_type, mode="validation")

        # Default to string
        return {"type": "string"}

    def build(self) -> dict:
        """Build the complete OpenAPI schema."""
        # Simplify component names: collapse suffixed entries to bare names
        # when a model was only used in one mode or both modes are identical.
        self._simplify_component_names()

        schema: dict[str, Any] = {
            "openapi": "3.1.0",
            "info": {
                "title": self.title,
                "version": self.version,
            },
            "paths": self.paths,
        }

        if self.description:
            schema["info"]["description"] = self.description

        if self.terms_of_service:
            schema["info"]["termsOfService"] = self.terms_of_service

        if self.contact:
            schema["info"]["contact"] = self.contact

        if self.license_info:
            schema["info"]["license"] = self.license_info

        if self.servers:
            schema["servers"] = self.servers

        if self.tags:
            schema["tags"] = self.tags

        if self.components["schemas"]:
            schema["components"] = self.components

        return schema
