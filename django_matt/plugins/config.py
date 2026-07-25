from __future__ import annotations

import logging
import os
from typing import Any

from django_matt.plugins.base import MattPlugin

logger = logging.getLogger("django_matt.plugins")


class PluginConfigError(Exception):
    pass


class PluginConfig:
    """Manages configuration for plugins — validation, defaults, env vars."""

    def __init__(self) -> None:
        self._configs: dict[str, dict[str, Any]] = {}
        self._defaults: dict[str, dict[str, Any]] = {}

    def load_defaults(self, plugin: MattPlugin) -> dict[str, Any]:
        """Extract default values from a plugin's settings schema."""
        schema = plugin.get_settings_schema()
        if not schema:
            return {}

        defaults: dict[str, Any] = {}
        properties = schema.get("properties", {})
        for key, prop in properties.items():
            if "default" in prop:
                defaults[key] = prop["default"]

        self._defaults[plugin.name] = defaults
        return defaults

    def load_env(self, plugin: MattPlugin) -> dict[str, Any]:
        """Load plugin settings from environment variables.

        Uses the plugin's settings_prefix: e.g. MATT_MYPLUGIN_KEY -> key.
        """
        if not plugin.settings_prefix:
            return {}

        prefix = plugin.settings_prefix.upper() + "_"
        env_config: dict[str, Any] = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix) :].lower()
                env_config[config_key] = value

        return env_config

    def load_settings(self, plugin: MattPlugin) -> dict[str, Any]:
        """Load plugin settings from Django settings."""
        if not plugin.settings_prefix:
            return {}

        try:
            from django.conf import settings

            return getattr(settings, plugin.settings_prefix, {})
        except Exception:
            return {}

    def resolve(self, plugin: MattPlugin) -> dict[str, Any]:
        """Resolve final config: defaults < settings < env vars."""
        defaults = self.load_defaults(plugin)
        settings_config = self.load_settings(plugin)
        env_config = self.load_env(plugin)

        merged = {**defaults, **settings_config, **env_config}
        self._configs[plugin.name] = merged
        return merged

    def validate(self, plugin: MattPlugin, config: dict[str, Any] | None = None) -> list[str]:
        """Validate config against plugin's JSON Schema. Returns list of errors."""
        schema = plugin.get_settings_schema()
        if not schema:
            return []

        if config is None:
            config = self._configs.get(plugin.name, {})

        errors: list[str] = []
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Check required fields
        for field in required:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        # Check types
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        for key, value in config.items():
            if key in properties:
                expected_type = properties[key].get("type")
                if expected_type and expected_type in type_map:
                    py_type = type_map[expected_type]
                    if not isinstance(value, py_type):
                        errors.append(
                            f"Field {key!r}: expected {expected_type}, got {type(value).__name__}"
                        )

        return errors

    def get(self, plugin_name: str) -> dict[str, Any]:
        """Get resolved config for a plugin."""
        return self._configs.get(plugin_name, {})

    def reload(self, plugin: MattPlugin) -> dict[str, Any]:
        """Reload config from all sources."""
        return self.resolve(plugin)

    def reset(self) -> None:
        self._configs.clear()
        self._defaults.clear()
