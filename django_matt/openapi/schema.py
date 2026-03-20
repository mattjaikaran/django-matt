"""
OpenAPI schema generation for Django Matt.

Generates OpenAPI 3.1.0 compatible schemas from registered routes and controllers.
"""

import inspect
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Union, get_args, get_origin, get_type_hints
from uuid import UUID

from pydantic import BaseModel

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

    def add_routes(self, routes: list[dict]) -> None:
        """Add routes from a router to the schema."""
        for route in routes:
            self._add_route(route)

    def add_controller(self, controller_class: type) -> None:
        """Add routes from a controller class."""
        controller = controller_class()
        prefix = getattr(controller, "prefix", "")
        tags = getattr(controller, "tags", [])

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
        operation["responses"] = self._build_responses(response_model, status_code)

        return operation

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
                schema_ref = self._register_schema(param_type)
                return {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": schema_ref,
                        }
                    },
                }

        return None

    def _build_responses(self, response_model: type | None, status_code: int) -> dict:
        """Build OpenAPI responses object."""
        responses: dict[str, Any] = {}

        if (
            response_model
            and inspect.isclass(response_model)
            and issubclass(response_model, BaseModel)
        ):
            schema_ref = self._register_schema(response_model)
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

    def _register_schema(self, model: type[BaseModel]) -> dict:
        """Register a Pydantic model as a component schema and return a reference."""
        schema_name = model.__name__

        if schema_name not in self.components["schemas"]:
            # Get JSON schema from Pydantic model
            try:
                from django_matt.core.schema import _get_camel_case_config

                _by_alias = _get_camel_case_config()
                json_schema = model.model_json_schema(by_alias=_by_alias)
                # Remove $defs and inline them if needed
                if "$defs" in json_schema:
                    for def_name, def_schema in json_schema["$defs"].items():
                        if def_name not in self.components["schemas"]:
                            self.components["schemas"][def_name] = def_schema
                    del json_schema["$defs"]
                self.components["schemas"][schema_name] = json_schema
            except Exception:
                # Fallback for models that don't support model_json_schema
                self.components["schemas"][schema_name] = {"type": "object"}

        return {"$ref": f"#/components/schemas/{schema_name}"}

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

        # Handle Pydantic models
        if inspect.isclass(python_type) and issubclass(python_type, BaseModel):
            return self._register_schema(python_type)

        # Default to string
        return {"type": "string"}

    def build(self) -> dict:
        """Build the complete OpenAPI schema."""
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
