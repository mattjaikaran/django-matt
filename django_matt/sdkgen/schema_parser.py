"""OpenAPI schema parser — extract endpoints, models, and auth from OpenAPI 3.0/3.1."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EndpointParam:
    """A single parameter for an endpoint."""

    name: str
    location: str  # path, query, header, cookie
    type_str: str  # target-agnostic type string
    required: bool = True
    description: str = ""
    schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class Endpoint:
    """Parsed API endpoint."""

    operation_id: str
    path: str
    method: str  # GET, POST, etc.
    summary: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    parameters: list[EndpointParam] = field(default_factory=list)
    request_body_ref: str | None = None
    request_body_schema: dict[str, Any] = field(default_factory=dict)
    response_ref: str | None = None
    response_schema: dict[str, Any] = field(default_factory=dict)
    auth_required: bool = False
    status_code: int = 200


@dataclass
class SchemaModel:
    """Parsed schema model (component)."""

    name: str
    properties: dict[str, dict[str, Any]] = field(default_factory=dict)
    required_fields: list[str] = field(default_factory=list)
    description: str = ""
    enum_values: list[Any] | None = None
    all_of: list[dict[str, Any]] = field(default_factory=list)
    one_of: list[dict[str, Any]] = field(default_factory=list)
    any_of: list[dict[str, Any]] = field(default_factory=list)
    raw_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedAPI:
    """Complete parsed API structure."""

    title: str
    version: str
    description: str
    base_url: str
    endpoints: list[Endpoint]
    models: dict[str, SchemaModel]
    auth_schemes: dict[str, dict[str, Any]]


class SchemaParser:
    """Parse OpenAPI 3.0/3.1 schema into structured data."""

    def __init__(self, schema: dict[str, Any]) -> None:
        self._schema = schema
        self._resolved_cache: dict[str, Any] = {}

    def parse(self) -> ParsedAPI:
        """Parse the full OpenAPI schema."""
        info = self._schema.get("info", {})
        servers = self._schema.get("servers", [])
        base_url = servers[0]["url"] if servers else ""

        models = self._parse_models()
        endpoints = self._parse_endpoints()
        auth_schemes = self._parse_auth_schemes()

        return ParsedAPI(
            title=info.get("title", "API"),
            version=info.get("version", "0.0.0"),
            description=info.get("description", ""),
            base_url=base_url,
            endpoints=endpoints,
            models=models,
            auth_schemes=auth_schemes,
        )

    def resolve_ref(self, ref_or_schema: dict[str, Any]) -> dict[str, Any]:
        """Resolve a $ref pointer to its target schema."""
        if "$ref" not in ref_or_schema:
            return ref_or_schema

        ref = ref_or_schema["$ref"]
        if ref in self._resolved_cache:
            return self._resolved_cache[ref]

        # Only handle local references (#/components/schemas/Name)
        parts = ref.lstrip("#/").split("/")
        current: Any = self._schema
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, {})
            else:
                current = {}
                break

        resolved = current if isinstance(current, dict) else {}
        self._resolved_cache[ref] = resolved
        return resolved

    def ref_name(self, ref_or_schema: dict[str, Any]) -> str | None:
        """Extract the model name from a $ref string."""
        ref = ref_or_schema.get("$ref", "")
        if ref:
            return ref.rsplit("/", 1)[-1]
        return None

    def _parse_models(self) -> dict[str, SchemaModel]:
        """Parse all component schemas into SchemaModel objects."""
        schemas = self._schema.get("components", {}).get("schemas", {})
        models: dict[str, SchemaModel] = {}

        for name, schema in schemas.items():
            resolved = self.resolve_ref(schema) if "$ref" in schema else schema
            model = SchemaModel(
                name=name,
                properties=resolved.get("properties", {}),
                required_fields=resolved.get("required", []),
                description=resolved.get("description", ""),
                enum_values=resolved.get("enum"),
                all_of=resolved.get("allOf", []),
                one_of=resolved.get("oneOf", []),
                any_of=resolved.get("anyOf", []),
                raw_schema=resolved,
            )
            models[name] = model

        return models

    def _parse_endpoints(self) -> list[Endpoint]:
        """Parse all path operations into Endpoint objects."""
        endpoints: list[Endpoint] = []
        paths = self._schema.get("paths", {})

        for path, methods in paths.items():
            for method, operation in methods.items():
                if method in ("parameters", "summary", "description"):
                    continue
                endpoint = self._parse_operation(path, method.upper(), operation)
                endpoints.append(endpoint)

        return endpoints

    def _parse_operation(
        self, path: str, method: str, operation: dict[str, Any]
    ) -> Endpoint:
        """Parse a single path operation."""
        op_id = operation.get("operationId", self._generate_op_id(path, method))

        # Parameters
        params: list[EndpointParam] = []
        for param_def in operation.get("parameters", []):
            resolved = self.resolve_ref(param_def)
            params.append(EndpointParam(
                name=resolved.get("name", ""),
                location=resolved.get("in", "query"),
                type_str=self._schema_to_type_str(resolved.get("schema", {})),
                required=resolved.get("required", False),
                description=resolved.get("description", ""),
                schema=resolved.get("schema", {}),
            ))

        # Request body
        request_body = operation.get("requestBody", {})
        rb_ref: str | None = None
        rb_schema: dict[str, Any] = {}
        if request_body:
            content = request_body.get("content", {})
            json_content = content.get("application/json", {})
            rb_raw = json_content.get("schema", {})
            rb_ref = self.ref_name(rb_raw)
            rb_schema = self.resolve_ref(rb_raw) if "$ref" in rb_raw else rb_raw

        # Response
        responses = operation.get("responses", {})
        resp_ref: str | None = None
        resp_schema: dict[str, Any] = {}
        status_code = 200

        for code in ("200", "201", "202", "204"):
            if code in responses:
                status_code = int(code)
                resp_content = responses[code].get("content", {})
                json_resp = resp_content.get("application/json", {})
                resp_raw = json_resp.get("schema", {})
                resp_ref = self.ref_name(resp_raw)
                resp_schema = self.resolve_ref(resp_raw) if "$ref" in resp_raw else resp_raw
                break

        # Auth
        auth_required = bool(
            operation.get("security")
            or operation.get("x-auth-required", False)
        )

        return Endpoint(
            operation_id=op_id,
            path=path,
            method=method,
            summary=operation.get("summary", ""),
            description=operation.get("description", ""),
            tags=operation.get("tags", []),
            parameters=params,
            request_body_ref=rb_ref,
            request_body_schema=rb_schema,
            response_ref=resp_ref,
            response_schema=resp_schema,
            auth_required=auth_required,
            status_code=status_code,
        )

    def _parse_auth_schemes(self) -> dict[str, dict[str, Any]]:
        """Parse security schemes from components."""
        return self._schema.get("components", {}).get("securitySchemes", {})

    def _generate_op_id(self, path: str, method: str) -> str:
        """Generate an operation ID from path and method."""
        clean = re.sub(r"[{}]", "", path)
        clean = re.sub(r"[^a-zA-Z0-9]", "_", clean).strip("_")
        return f"{method.lower()}_{clean}"

    @staticmethod
    def _schema_to_type_str(schema: dict[str, Any]) -> str:
        """Convert an OpenAPI schema to a generic type string."""
        t = schema.get("type", "any")
        fmt = schema.get("format", "")
        if t == "array":
            items = schema.get("items", {})
            inner = SchemaParser._schema_to_type_str(items)
            return f"array<{inner}>"
        if t == "integer":
            return "integer"
        if t == "number":
            return "number"
        if t == "boolean":
            return "boolean"
        if t == "string":
            if fmt == "date-time":
                return "datetime"
            if fmt == "date":
                return "date"
            if fmt == "uuid":
                return "uuid"
            if fmt == "binary":
                return "binary"
            return "string"
        if t == "object":
            return "object"
        return "any"
