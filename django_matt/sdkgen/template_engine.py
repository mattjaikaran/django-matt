"""Code template engine — naming conventions and language-specific formatting."""

from __future__ import annotations

import re
import textwrap
from typing import Any


def to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = re.split(r"[_\-]", name)
    if not parts:
        return name
    return parts[0].lower() + "".join((p[0].upper() + p[1:]) if p else "" for p in parts[1:])


def to_pascal_case(name: str) -> str:
    """Convert snake_case or kebab-case to PascalCase."""
    parts = re.split(r"[_\-]", name)
    return "".join((p[0].upper() + p[1:]) if p else "" for p in parts)


def to_snake_case(name: str) -> str:
    """Convert camelCase or PascalCase to snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower().replace("-", "_")


def to_kebab_case(name: str) -> str:
    """Convert to kebab-case."""
    return to_snake_case(name).replace("_", "-")


def indent(text: str, level: int = 1, width: int = 4) -> str:
    """Indent text by level * width spaces."""
    prefix = " " * (level * width)
    return textwrap.indent(text, prefix)


def dedent(text: str) -> str:
    """Remove common leading whitespace."""
    return textwrap.dedent(text).strip()


# --- OpenAPI type mapping ---

_TS_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "object": "Record<string, unknown>",
    "any": "unknown",
    "datetime": "string",
    "date-time": "string",
    "date": "string",
    "uuid": "string",
    "binary": "File",
}

_PYTHON_TYPE_MAP: dict[str, str] = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "object": "dict[str, Any]",
    "any": "Any",
    "datetime": "datetime",
    "date-time": "datetime",
    "date": "date",
    "uuid": "str",
    "binary": "bytes",
}

_SWIFT_TYPE_MAP: dict[str, str] = {
    "string": "String",
    "integer": "Int",
    "number": "Double",
    "boolean": "Bool",
    "object": "[String: Any]",
    "any": "Any",
    "datetime": "Date",
    "date-time": "Date",
    "date": "Date",
    "uuid": "UUID",
    "binary": "Data",
}


def openapi_type_to_ts(schema: dict[str, Any]) -> str:
    """Map an OpenAPI schema to a TypeScript type string."""
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]

    t = schema.get("type", "any")
    fmt = schema.get("format", "")
    nullable = schema.get("nullable", False)

    if t == "array":
        items = schema.get("items", {})
        inner = openapi_type_to_ts(items)
        base = f"{inner}[]"
    elif t == "string" and "enum" in schema:
        vals = " | ".join(f'"{v}"' for v in schema["enum"])
        base = vals
    elif t == "string" and fmt:
        base = _TS_TYPE_MAP.get(fmt, "string")
    else:
        base = _TS_TYPE_MAP.get(t, "unknown")

    # Handle oneOf/anyOf
    if "oneOf" in schema or "anyOf" in schema:
        variants = schema.get("oneOf") or schema.get("anyOf", [])
        types = [openapi_type_to_ts(v) for v in variants]
        base = " | ".join(types)

    if nullable:
        return f"{base} | null"
    return base


def openapi_type_to_python(schema: dict[str, Any]) -> str:
    """Map an OpenAPI schema to a Python type string."""
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]

    t = schema.get("type", "any")
    fmt = schema.get("format", "")
    nullable = schema.get("nullable", False)

    if t == "array":
        items = schema.get("items", {})
        inner = openapi_type_to_python(items)
        base = f"list[{inner}]"
    elif t == "string" and "enum" in schema:
        base = "str"
    elif t == "string" and fmt:
        base = _PYTHON_TYPE_MAP.get(fmt, "str")
    else:
        base = _PYTHON_TYPE_MAP.get(t, "Any")

    if "oneOf" in schema or "anyOf" in schema:
        variants = schema.get("oneOf") or schema.get("anyOf", [])
        types = [openapi_type_to_python(v) for v in variants]
        base = " | ".join(types)

    if nullable:
        return f"{base} | None"
    return base


def openapi_type_to_swift(schema: dict[str, Any]) -> str:
    """Map an OpenAPI schema to a Swift type string."""
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]

    t = schema.get("type", "any")
    fmt = schema.get("format", "")
    nullable = schema.get("nullable", False)

    if t == "array":
        items = schema.get("items", {})
        inner = openapi_type_to_swift(items)
        base = f"[{inner}]"
    elif t == "string" and "enum" in schema:
        base = "String"
    elif t == "string" and fmt:
        base = _SWIFT_TYPE_MAP.get(fmt, "String")
    else:
        base = _SWIFT_TYPE_MAP.get(t, "Any")

    if nullable:
        return f"{base}?"
    return base


def sanitize_identifier(name: str) -> str:
    """Sanitize a string into a valid identifier."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if clean and clean[0].isdigit():
        clean = f"_{clean}"
    return clean
