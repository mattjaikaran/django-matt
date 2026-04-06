"""
Utility functions for type generation.
"""

import datetime
import decimal
import importlib
import inspect
import uuid
from enum import Enum
from typing import (
    Any,
    Literal,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel

# Python type to TypeScript type mapping
PYTHON_TO_TYPESCRIPT: dict[type, str] = {
    str: "string",
    int: "number",
    float: "number",
    bool: "boolean",
    bytes: "string",  # Base64 encoded
    type(None): "null",
    None: "null",
    Any: "any",
    datetime.datetime: "string",  # ISO format
    datetime.date: "string",  # ISO format
    datetime.time: "string",  # ISO format
    datetime.timedelta: "string",
    decimal.Decimal: "number",
    uuid.UUID: "string",
    dict: "Record<string, any>",
    list: "any[]",
    set: "any[]",
    tuple: "any[]",
}

# Python type to Zod type mapping
PYTHON_TO_ZOD: dict[type, str] = {
    str: "z.string()",
    int: "z.number().int()",
    float: "z.number()",
    bool: "z.boolean()",
    bytes: "z.string()",
    type(None): "z.null()",
    None: "z.null()",
    Any: "z.any()",
    datetime.datetime: "z.string().datetime()",
    datetime.date: "z.string().date()",
    datetime.time: "z.string().time()",
    datetime.timedelta: "z.string()",
    decimal.Decimal: "z.number()",
    uuid.UUID: "z.string().uuid()",
    dict: "z.record(z.string(), z.any())",
    list: "z.array(z.any())",
    set: "z.array(z.any())",
    tuple: "z.tuple([])",
}


def get_type_name(python_type: type) -> str:
    """
    Get a clean type name from a Python type.

    Args:
        python_type: The Python type

    Returns:
        Clean type name string
    """
    if hasattr(python_type, "__name__"):
        return python_type.__name__

    # Handle generic types
    origin = get_origin(python_type)
    if origin is not None:
        args = get_args(python_type)
        if origin is Union:
            if len(args) == 2 and type(None) in args:
                # Optional type
                inner = [a for a in args if a is not type(None)][0]
                return f"Optional[{get_type_name(inner)}]"
            return " | ".join(get_type_name(a) for a in args)
        if origin is list or origin is list:
            if args:
                return f"List[{get_type_name(args[0])}]"
            return "List"
        if origin is dict or origin is dict:
            if args:
                return f"Dict[{get_type_name(args[0])}, {get_type_name(args[1])}]"
            return "Dict"
        if origin is set or origin is set:
            if args:
                return f"Set[{get_type_name(args[0])}]"
            return "Set"
        if origin is tuple or origin is tuple:
            if args:
                return f"Tuple[{', '.join(get_type_name(a) for a in args)}]"
            return "Tuple"

    return str(python_type)


def python_type_to_typescript(
    python_type: type,
    schema_names: set[str] | None = None,
) -> str:
    """
    Convert a Python type to its TypeScript equivalent.

    Args:
        python_type: The Python type to convert
        schema_names: Set of known schema names (for references)

    Returns:
        TypeScript type string
    """
    schema_names = schema_names or set()

    # Handle None type
    if python_type is None or python_type is type(None):
        return "null"

    # Handle basic types
    if python_type in PYTHON_TO_TYPESCRIPT:
        return PYTHON_TO_TYPESCRIPT[python_type]

    # Handle Pydantic models
    if inspect.isclass(python_type) and issubclass(python_type, BaseModel):
        return python_type.__name__

    # Handle Enums
    if inspect.isclass(python_type) and issubclass(python_type, Enum):
        # Return union of literal values
        values = [f'"{m.value}"' if isinstance(m.value, str) else str(m.value) for m in python_type]
        return " | ".join(values)

    # Handle generic types
    origin = get_origin(python_type)
    if origin is not None:
        args = get_args(python_type)

        # Literal types → TypeScript union of literal values
        if origin is Literal:
            parts = []
            for v in args:
                if isinstance(v, str):
                    parts.append(f'"{v}"')
                elif isinstance(v, bool):
                    parts.append("true" if v else "false")
                elif isinstance(v, (int, float)):
                    parts.append(str(v))
                else:
                    parts.append(f'"{v}"')
            return " | ".join(parts)

        # Union types (including Optional)
        if origin is Union:
            # Check for Optional (Union with None)
            non_none_args = [a for a in args if a is not type(None)]
            if len(args) == 2 and type(None) in args:
                # Optional type
                inner_type = python_type_to_typescript(non_none_args[0], schema_names)
                return f"{inner_type} | null"

            # Regular union
            return " | ".join(python_type_to_typescript(a, schema_names) for a in args)

        # List types
        if origin is list or origin is list:
            if args:
                inner_type = python_type_to_typescript(args[0], schema_names)
                return f"{inner_type}[]"
            return "any[]"

        # Dict types
        if origin is dict or origin is dict:
            if args and len(args) == 2:
                key_type = python_type_to_typescript(args[0], schema_names)
                value_type = python_type_to_typescript(args[1], schema_names)
                return f"Record<{key_type}, {value_type}>"
            return "Record<string, any>"

        # Set types
        if origin is set or origin is set:
            if args:
                inner_type = python_type_to_typescript(args[0], schema_names)
                return f"{inner_type}[]"
            return "any[]"

        # Tuple types
        if origin is tuple or origin is tuple:
            if args:
                types = [python_type_to_typescript(a, schema_names) for a in args]
                return f"[{', '.join(types)}]"
            return "any[]"

    # Check if it's a known schema name
    if hasattr(python_type, "__name__") and python_type.__name__ in schema_names:
        return python_type.__name__

    # Default to any
    return "any"


def python_type_to_zod(
    python_type: type,
    schema_names: set[str] | None = None,
) -> str:
    """
    Convert a Python type to its Zod equivalent.

    Args:
        python_type: The Python type to convert
        schema_names: Set of known schema names (for references)

    Returns:
        Zod schema string
    """
    schema_names = schema_names or set()

    # Handle None type
    if python_type is None or python_type is type(None):
        return "z.null()"

    # Handle basic types
    if python_type in PYTHON_TO_ZOD:
        return PYTHON_TO_ZOD[python_type]

    # Handle Pydantic models (reference to schema)
    if inspect.isclass(python_type) and issubclass(python_type, BaseModel):
        return f"{python_type.__name__}Schema"

    # Handle Enums
    if inspect.isclass(python_type) and issubclass(python_type, Enum):
        values = [f'"{m.value}"' if isinstance(m.value, str) else str(m.value) for m in python_type]
        return f"z.enum([{', '.join(values)}])"

    # Handle generic types
    origin = get_origin(python_type)
    if origin is not None:
        args = get_args(python_type)

        # Literal types → z.enum([...]) for strings, z.union([z.literal(...)]) for mixed
        if origin is Literal:
            if all(isinstance(v, str) for v in args):
                values = ", ".join(f'"{v}"' for v in args)
                return f"z.enum([{values}])"
            parts = []
            for v in args:
                if isinstance(v, str):
                    parts.append(f'z.literal("{v}")')
                elif isinstance(v, bool):
                    parts.append(f"z.literal({'true' if v else 'false'})")
                elif isinstance(v, (int, float)):
                    parts.append(f"z.literal({v})")
                else:
                    parts.append(f'z.literal("{v}")')
            return f"z.union([{', '.join(parts)}])"

        # Union types (including Optional)
        if origin is Union:
            non_none_args = [a for a in args if a is not type(None)]
            has_none = type(None) in args

            if len(non_none_args) == 1:
                # Optional type
                inner_schema = python_type_to_zod(non_none_args[0], schema_names)
                if has_none:
                    return f"{inner_schema}.nullable()"
                return inner_schema

            # Regular union
            schemas = [python_type_to_zod(a, schema_names) for a in non_none_args]
            result = f"z.union([{', '.join(schemas)}])"
            if has_none:
                result = f"{result}.nullable()"
            return result

        # List types
        if origin is list or origin is list:
            if args:
                inner_schema = python_type_to_zod(args[0], schema_names)
                return f"z.array({inner_schema})"
            return "z.array(z.any())"

        # Dict types
        if origin is dict or origin is dict:
            if args and len(args) == 2:
                value_schema = python_type_to_zod(args[1], schema_names)
                return f"z.record(z.string(), {value_schema})"
            return "z.record(z.string(), z.any())"

        # Set types
        if origin is set or origin is set:
            if args:
                inner_schema = python_type_to_zod(args[0], schema_names)
                return f"z.array({inner_schema})"
            return "z.array(z.any())"

        # Tuple types
        if origin is tuple or origin is tuple:
            if args:
                schemas = [python_type_to_zod(a, schema_names) for a in args]
                return f"z.tuple([{', '.join(schemas)}])"
            return "z.tuple([])"

    # Check if it's a known schema name
    if hasattr(python_type, "__name__") and python_type.__name__ in schema_names:
        return f"{python_type.__name__}Schema"

    # Default to any
    return "z.any()"


def collect_schemas_from_module(module_path: str) -> list[type[BaseModel]]:
    """
    Collect all Pydantic BaseModel schemas from a module.

    Args:
        module_path: Dotted module path (e.g., 'myapp.schemas')

    Returns:
        List of Pydantic model classes
    """
    module = importlib.import_module(module_path)
    schemas = []

    for name in dir(module):
        obj = getattr(module, name)
        if (
            inspect.isclass(obj)
            and issubclass(obj, BaseModel)
            and obj is not BaseModel
            and obj.__module__ == module.__name__
        ):
            schemas.append(obj)

    return schemas


def collect_models_from_app(app_label: str) -> list[type]:
    """
    Collect all Django models from an app.

    Args:
        app_label: Django app label

    Returns:
        List of Django model classes
    """
    from django.apps import apps

    try:
        app_config = apps.get_app_config(app_label)
        return list(app_config.get_models())
    except LookupError:
        return []


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(x.title() for x in name.split("_"))
