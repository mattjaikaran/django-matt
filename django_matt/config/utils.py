"""
Utility functions for the Django Matt configuration system.
"""

import os
from typing import Any


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries.

    Args:
        base: The base dictionary.
        override: The dictionary to override the base.

    Returns:
        A new dictionary with the merged values.
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # If both values are dictionaries, merge them recursively
            result[key] = deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            # If both values are lists, extend the base list with the override list
            result[key] = result[key] + [item for item in value if item not in result[key]]
        else:
            # Otherwise, override the base value with the override value
            result[key] = value

    return result


def get_env_bool(name: str, default: bool = False) -> bool:
    """
    Get a boolean value from an environment variable.

    Args:
        name: The name of the environment variable.
        default: The default value if the environment variable is not set.

    Returns:
        The boolean value of the environment variable.
    """
    value = os.environ.get(name, str(default)).lower()
    return value in ("true", "yes", "1", "y", "t")


def get_env_int(name: str, default: int = 0) -> int:
    """
    Get an integer value from an environment variable.

    Args:
        name: The name of the environment variable.
        default: The default value if the environment variable is not set.

    Returns:
        The integer value of the environment variable.
    """
    try:
        return int(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default


def get_env_float(name: str, default: float = 0.0) -> float:
    """
    Get a float value from an environment variable.

    Args:
        name: The name of the environment variable.
        default: The default value if the environment variable is not set.

    Returns:
        The float value of the environment variable.
    """
    try:
        return float(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default


def get_env_list(name: str, default: list[str] | None = None, separator: str = ",") -> list[str]:
    """
    Get a list value from an environment variable.

    Args:
        name: The name of the environment variable.
        default: The default value if the environment variable is not set.
        separator: The separator to split the environment variable value.

    Returns:
        The list value of the environment variable.
    """
    if default is None:
        default = []

    value = os.environ.get(name)
    if value is None:
        return default

    return [item.strip() for item in value.split(separator) if item.strip()]


def get_env_dict(
    name: str, default: dict[str, str] | None = None, separator: str = ",", key_value_separator: str = "="
) -> dict[str, str]:
    """
    Get a dictionary value from an environment variable.

    Args:
        name: The name of the environment variable.
        default: The default value if the environment variable is not set.
        separator: The separator to split the environment variable value.
        key_value_separator: The separator to split the key-value pairs.

    Returns:
        The dictionary value of the environment variable.
    """
    if default is None:
        default = {}

    value = os.environ.get(name)
    if value is None:
        return default

    result = {}
    for item in value.split(separator):
        if key_value_separator in item:
            key, value = item.split(key_value_separator, 1)
            result[key.strip()] = value.strip()

    return result
