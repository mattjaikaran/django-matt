"""
Django Matt Configuration System.

This module provides a more organized and flexible approach to Django settings
by separating concerns into different modules and supporting multiple environments.
"""

import importlib
from typing import Any, Optional

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


def _build_shortcut_settings(
    auth: str | None = None,
    database: str | None = None,
    cache: str | None = None,
    middleware: str | None = None,
    throttle: str | None = None,
    cors: list[str] | bool | None = None,
) -> dict[str, Any]:
    """
    Translate shortcut params into DJANGO_MATT settings dict entries.

    Called once at configure() time — no per-request overhead.
    """
    matt: dict[str, Any] = {}

    # Auth shortcut
    if auth == "jwt":
        matt["AUTH_BACKEND"] = "jwt"
        matt["JWT_AUTH"] = {
            "ACCESS_TOKEN_LIFETIME_MINUTES": 60,
            "REFRESH_TOKEN_LIFETIME_DAYS": 7,
            "ALGORITHM": "HS256",
        }
    elif auth == "session":
        matt["AUTH_BACKEND"] = "session"

    # Database shortcut
    if database == "postgresql":
        matt["DATABASE_ENGINE"] = "django.db.backends.postgresql"
        matt["CONNECTION_POOL"] = {"ENABLED": True, "MIN_SIZE": 2, "MAX_SIZE": 10}
    elif database == "sqlite":
        matt["DATABASE_ENGINE"] = "django.db.backends.sqlite3"

    # Cache shortcut
    if cache == "redis":
        matt["CACHE_BACKEND"] = "django.core.cache.backends.redis.RedisCache"
    elif cache == "memory":
        matt["CACHE_BACKEND"] = "django.core.cache.backends.locmem.LocMemCache"

    # Middleware stack shortcut
    if middleware in ("production", "development"):
        matt["MIDDLEWARE_STACK"] = middleware

    # Throttle shortcut
    if throttle:
        matt["THROTTLE"] = {"DEFAULT_RATE": throttle}

    # CORS shortcut
    if cors is not None:
        if cors is True:
            matt["CORS"] = {"ALLOWED_ORIGINS": True, "ENABLED": True}
        elif isinstance(cors, list):
            matt["CORS"] = {"ALLOWED_ORIGINS": cors, "ENABLED": True}

    return matt


def configure(
    environment: str = "development",
    components: list[str] | None = None,
    extra_settings: dict[str, Any] | None = None,
    apply_to_django: bool = True,
    *,
    auth: str | None = None,
    database: str | None = None,
    cache: str | None = None,
    middleware: str | None = None,
    throttle: str | None = None,
    cors: list[str] | bool | None = None,
) -> dict[str, Any]:
    """
    Configure the application with the specified settings.

    Supports shortcut params for common setups:
        configure(
            auth="jwt",              # auto-wires JWT middleware + settings
            database="postgresql",   # connection pooling, health checks
            cache="redis",           # Redis cache backend
            middleware="production",  # security + CORS + request ID + logging + timing
            throttle="100/hour",     # global rate limit
            cors=["https://app.example.com"],  # or True for "*"
        )

    Args:
        environment: The name of the environment to load.
        components: A list of component names to load.
        extra_settings: Additional settings to apply.
        apply_to_django: Whether to apply the settings to Django's settings module.
        auth: Auth backend shortcut ("jwt" or "session").
        database: Database shortcut ("postgresql" or "sqlite").
        cache: Cache shortcut ("redis" or "memory").
        middleware: Middleware stack shortcut ("production" or "development").
        throttle: Global throttle rate (e.g. "100/hour").
        cors: CORS origins list, or True for "*".

    Returns:
        The final settings dictionary.
    """
    # Build shortcut settings first
    matt_settings = _build_shortcut_settings(
        auth=auth,
        database=database,
        cache=cache,
        middleware=middleware,
        throttle=throttle,
        cors=cors,
    )

    # Merge into extra_settings under DJANGO_MATT key
    if matt_settings:
        if extra_settings is None:
            extra_settings = {}
        existing_matt = extra_settings.get("DJANGO_MATT", {})
        existing_matt.update(matt_settings)
        extra_settings["DJANGO_MATT"] = existing_matt

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


__all__ = ["config", "configure", "get_settings"]
