"""
Django Matt Configuration System.

This module provides a more organized and flexible approach to Django settings
by separating concerns into different modules and supporting multiple environments.
"""

import importlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from django.conf import settings as django_settings


class ConfigurationManager:
    """
    Manages the configuration for Django Matt applications.

    This class provides methods to load settings from different modules,
    merge them together, and apply them to Django's settings.
    """

    def __init__(self):
        self._settings = {}
        self._loaded_components = set()
        self._loaded_environments = set()
        self._base_loaded = False
        self._django_settings_applied = False

    def load_base(self) -> dict[str, Any]:
        """
        Load the base settings.

        Returns:
            The base settings dictionary.
        """
        if not self._base_loaded:
            from django_matt.config.base import settings as base_settings

            self._settings.update(base_settings)
            self._base_loaded = True

        return self._settings

    def load_environment(self, environment: str) -> dict[str, Any]:
        """
        Load settings for a specific environment.

        Args:
            environment: The name of the environment (e.g., 'development', 'production').

        Returns:
            The updated settings dictionary.

        Raises:
            ImportError: If the environment module cannot be found.
        """
        if environment in self._loaded_environments:
            return self._settings

        try:
            env_module = importlib.import_module(f"django_matt.config.environments.{environment}")
            env_settings = getattr(env_module, "settings", {})
            self._settings.update(env_settings)
            self._loaded_environments.add(environment)
        except ImportError:
            raise ImportError(f"Could not import environment settings for '{environment}'")

        return self._settings

    def load_component(self, component: str) -> dict[str, Any]:
        """
        Load settings for a specific component.

        Args:
            component: The name of the component (e.g., 'database', 'cache').

        Returns:
            The updated settings dictionary.

        Raises:
            ImportError: If the component module cannot be found.
        """
        if component in self._loaded_components:
            return self._settings

        try:
            component_module = importlib.import_module(f"django_matt.config.components.{component}")
            component_settings = getattr(component_module, "settings", {})
            self._settings.update(component_settings)
            self._loaded_components.add(component)
        except ImportError:
            raise ImportError(f"Could not import component settings for '{component}'")

        return self._settings

    def load_components(self, components: list[str]) -> dict[str, Any]:
        """
        Load settings for multiple components.

        Args:
            components: A list of component names.

        Returns:
            The updated settings dictionary.
        """
        for component in components:
            self.load_component(component)

        return self._settings

    def get_settings(self) -> dict[str, Any]:
        """
        Get the current settings dictionary.

        Returns:
            The settings dictionary.
        """
        return self._settings

    def apply_to_django_settings(self) -> None:
        """
        Apply the loaded settings to Django's settings module.

        This method should be called after all settings have been loaded.
        """
        if self._django_settings_applied:
            return

        for key, value in self._settings.items():
            setattr(django_settings, key, value)

        self._django_settings_applied = True

    def configure(
        self,
        environment: str = "development",
        components: list[str] | None = None,
        extra_settings: dict[str, Any] | None = None,
        apply_to_django: bool = True,
    ) -> dict[str, Any]:
        """
        Configure the application with the specified settings.

        This is the main method to use when setting up your Django application.

        Args:
            environment: The name of the environment to load.
            components: A list of component names to load.
            extra_settings: Additional settings to apply.
            apply_to_django: Whether to apply the settings to Django's settings module.

        Returns:
            The final settings dictionary.
        """
        # Load base settings first
        self.load_base()

        # Load environment settings
        self.load_environment(environment)

        # Load component settings
        if components:
            self.load_components(components)

        # Apply extra settings
        if extra_settings:
            self._settings.update(extra_settings)

        # Apply to Django settings if requested
        if apply_to_django:
            self.apply_to_django_settings()

        return self._settings


# Create a singleton instance
config = ConfigurationManager()


def configure(
    environment: str = "development",
    components: list[str] | None = None,
    extra_settings: dict[str, Any] | None = None,
    apply_to_django: bool = True,
) -> dict[str, Any]:
    """
    Configure the application with the specified settings.

    This is a convenience function that delegates to the ConfigurationManager.

    Args:
        environment: The name of the environment to load.
        components: A list of component names to load.
        extra_settings: Additional settings to apply.
        apply_to_django: Whether to apply the settings to Django's settings module.

    Returns:
        The final settings dictionary.
    """
    return config.configure(
        environment=environment,
        components=components,
        extra_settings=extra_settings,
        apply_to_django=apply_to_django,
    )


def get_settings() -> dict[str, Any]:
    """
    Get the current settings dictionary.

    Returns:
        The settings dictionary.
    """
    return config.get_settings()


__all__ = ["configure", "get_settings", "config"]
