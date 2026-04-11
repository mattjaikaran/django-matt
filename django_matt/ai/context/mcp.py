"""
MCP (Model Context Protocol) server generator.

Generates a standalone MCP server from Django project introspection data.
The generated server exposes the project's API endpoints as MCP tools,
allowing LLM agents to interact with the API programmatically.

Usage:
    python manage.py generate_mcp_server
    python manage.py generate_mcp_server --output mcp_server.py
    python manage.py generate_mcp_server --base-url http://localhost:8000

The generated server requires:
    uv add mcp httpx
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django_matt.ai.context.introspection import (
    EndpointInfo,
    EnhancedIntrospector,
    EnhancedProjectInfo,
)


def _python_type_from_schema_field(field_type: str) -> str:
    """Map schema field type strings to Python type hints for MCP tool params."""
    mapping = {
        "str": "str",
        "string": "str",
        "int": "int",
        "integer": "int",
        "float": "float",
        "number": "float",
        "bool": "bool",
        "boolean": "bool",
        "uuid": "str",
        "UUID": "str",
        "datetime": "str",
        "date": "str",
        "list": "list",
        "dict": "dict",
    }
    # Handle Optional[X], list[X], etc.
    base = field_type.split("[")[0].split("|")[0].strip()
    return mapping.get(base, "str")


def _sanitize_tool_name(method: str, path: str) -> str:
    """Convert HTTP method + path to a valid MCP tool name."""
    # /api/users/{id}/activate → api_users_activate
    parts = path.strip("/").split("/")
    clean = [p for p in parts if not p.startswith("{")]
    name = "_".join(clean).replace("-", "_")
    return f"{method.lower()}_{name}" if name else method.lower()


def _build_tool_description(endpoint: EndpointInfo) -> str:
    """Build a concise tool description from endpoint info."""
    parts = []
    parts.append(f"{endpoint.method} {endpoint.path}")
    if hasattr(endpoint, "description") and endpoint.description:
        parts.append(endpoint.description)
    if hasattr(endpoint, "auth") and endpoint.auth:
        parts.append(f"Auth: {endpoint.auth}")
    return " — ".join(parts)


def _extract_path_params(path: str) -> list[str]:
    """Extract path parameter names from a URL pattern like /users/{id}."""
    import re

    return re.findall(r"\{(\w+)\}", path)


def _generate_tool_function(endpoint: EndpointInfo) -> str:
    """Generate a single MCP tool function for an endpoint."""
    tool_name = _sanitize_tool_name(endpoint.method, endpoint.path)
    description = _build_tool_description(endpoint)
    path_params = _extract_path_params(endpoint.path)

    # Build parameter list
    params: list[str] = []
    param_docs: list[str] = []

    for pp in path_params:
        params.append(f"{pp}: str")
        param_docs.append(f"        {pp}: Path parameter")

    # Add body params for POST/PUT/PATCH
    if endpoint.method in ("POST", "PUT", "PATCH"):
        request_schema = getattr(endpoint, "request_schema", None)
        if request_schema and hasattr(request_schema, "fields"):
            for field in request_schema.fields:
                py_type = _python_type_from_schema_field(field.field_type)
                if field.required:
                    params.append(f"{field.name}: {py_type}")
                else:
                    default = repr(field.default) if field.default is not None else "None"
                    params.append(f"{field.name}: {py_type} | None = {default}")
                desc = field.description or field.field_type
                param_docs.append(f"        {field.name}: {desc}")
        else:
            params.append("body: dict | None = None")
            param_docs.append("        body: Request body (JSON)")

    # Add query params for GET
    if endpoint.method == "GET":
        params.extend([
            "limit: int | None = None",
            "offset: int | None = None",
        ])
        param_docs.extend([
            "        limit: Max results to return",
            "        offset: Number of results to skip",
        ])

    params_str = ", ".join(params)
    param_docs_str = "\n".join(param_docs)

    # Build URL with path params
    url_expr = f'f"{{BASE_URL}}{endpoint.path}"' if path_params else f'"{{BASE_URL}}{endpoint.path}"'
    # Replace {param} with {param} for f-string
    url_expr = url_expr.replace("{BASE_URL}", "{BASE_URL}")

    # Build request kwargs
    method_lower = endpoint.method.lower()
    if endpoint.method in ("POST", "PUT", "PATCH"):
        if "body:" in params_str:
            request_body = "body"
        else:
            body_fields = [p.split(":")[0].strip() for p in params if p.split(":")[0].strip() not in path_params and "limit" not in p and "offset" not in p]
            if body_fields:
                request_body = "{" + ", ".join(f'"{f}": {f}' for f in body_fields) + "}"
            else:
                request_body = "None"
        kwargs = f'json={request_body}, headers=headers'
    elif endpoint.method == "GET":
        kwargs = 'params={k: v for k, v in {"limit": limit, "offset": offset}.items() if v is not None}, headers=headers'
    else:
        kwargs = 'headers=headers'

    return f'''
@mcp.tool()
async def {tool_name}({params_str}) -> str:
    """{description}

    Args:
{param_docs_str}
    """
    url = {url_expr}
    response = await client.{method_lower}(url, {kwargs})
    response.raise_for_status()
    return response.text
'''


def generate_mcp_server(
    *,
    base_url: str = "http://localhost:8000",
    server_name: str | None = None,
    introspector: EnhancedIntrospector | None = None,
) -> str:
    """
    Generate a complete MCP server Python file from project introspection.

    Args:
        base_url: Base URL of the Django API server
        server_name: Name for the MCP server (default: project name)
        introspector: Optional pre-configured introspector

    Returns:
        Complete Python source code for the MCP server
    """
    if introspector is None:
        introspector = EnhancedIntrospector(
            include_third_party=False,
            include_examples=True,
        )

    info: EnhancedProjectInfo = introspector.introspect()
    project_name = server_name or getattr(info, "name", "django-api")

    # Generate tool functions
    tool_functions = []
    seen_names: set[str] = set()
    for endpoint in info.endpoints:
        name = _sanitize_tool_name(endpoint.method, endpoint.path)
        if name in seen_names:
            name = f"{name}_{endpoint.method.lower()}"
        seen_names.add(name)
        tool_functions.append(_generate_tool_function(endpoint))

    tools_code = "\n".join(tool_functions)

    # Build schema descriptions for the server docstring
    schema_lines = []
    for schema in getattr(info, "schemas", []):
        fields = ", ".join(f.name for f in schema.fields[:5])
        if len(schema.fields) > 5:
            fields += f", ... ({len(schema.fields)} total)"
        schema_lines.append(f"#   {schema.name}: {fields}")
    schemas_comment = "\n".join(schema_lines) if schema_lines else "#   (none detected)"

    return f'''#!/usr/bin/env python3
"""
MCP Server for {project_name}

Auto-generated by django-matt from project introspection.
Exposes {len(info.endpoints)} API endpoints as MCP tools.

Requires:
    uv add mcp httpx

Run:
    python {project_name.replace("-", "_")}_mcp.py

Available schemas:
{schemas_comment}
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("API_BASE_URL", "{base_url}")
API_TOKEN = os.environ.get("API_TOKEN", "")

mcp = FastMCP("{project_name}")
client = httpx.AsyncClient(timeout=30.0)
headers = {{"Authorization": f"Bearer {{API_TOKEN}}"}} if API_TOKEN else {{}}

{tools_code}

@mcp.tool()
async def list_endpoints() -> str:
    """List all available API endpoints with their methods and paths."""
    endpoints = [
{chr(10).join(f'        "{e.method} {e.path}",' for e in info.endpoints)}
    ]
    return "\\n".join(endpoints)


if __name__ == "__main__":
    mcp.run()
'''


def write_mcp_server(
    output_path: str | Path = "mcp_server.py",
    *,
    base_url: str = "http://localhost:8000",
    server_name: str | None = None,
    introspector: EnhancedIntrospector | None = None,
) -> Path:
    """
    Generate and write an MCP server file.

    Args:
        output_path: Where to write the generated server
        base_url: Base URL of the Django API server
        server_name: Name for the MCP server
        introspector: Optional pre-configured introspector

    Returns:
        Path to the written file
    """
    path = Path(output_path)
    content = generate_mcp_server(
        base_url=base_url,
        server_name=server_name,
        introspector=introspector,
    )
    path.write_text(content)
    return path
