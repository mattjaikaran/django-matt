from __future__ import annotations

from django_matt.plugins.base import CheckMessage, MattPlugin
from django_matt.plugins.config import PluginConfig, PluginConfigError
from django_matt.plugins.hooks import (
    AFTER_RESPONSE,
    AUTH_FAILURE,
    AUTH_SUCCESS,
    BEFORE_REQUEST,
    CONTROLLER_REGISTERED,
    MODEL_REGISTERED,
    ON_ERROR,
    PLUGIN_LOADED,
    PLUGIN_UNLOADED,
    SCHEMA_VALIDATED,
    clear_hooks,
    fire_hook,
    fire_hook_sync,
    get_hooks,
    hook,
    list_hook_events,
)
from django_matt.plugins.loader import PluginLoader
from django_matt.plugins.registry import (
    PluginConflictError,
    PluginDependencyError,
    PluginError,
    PluginNotFoundError,
    PluginRegistry,
    PluginStatus,
    PluginVersionError,
    get_plugin_registry,
    reset_plugin_registry,
)
from django_matt.plugins.scaffold import PluginScaffolder
from django_matt.plugins.testing import (
    PluginTestCase,
    create_test_api,
    mock_plugin,
)

__all__ = [
    "CheckMessage",
    "MattPlugin",
    "PluginConfig",
    "PluginConfigError",
    "PluginConflictError",
    "PluginDependencyError",
    "PluginError",
    "PluginLoader",
    "PluginNotFoundError",
    "PluginRegistry",
    "PluginScaffolder",
    "PluginStatus",
    "PluginTestCase",
    "PluginVersionError",
    "clear_hooks",
    "create_test_api",
    "fire_hook",
    "fire_hook_sync",
    "get_hooks",
    "get_plugin_registry",
    "hook",
    "list_hook_events",
    "mock_plugin",
    "reset_plugin_registry",
    # Hook event constants
    "BEFORE_REQUEST",
    "AFTER_RESPONSE",
    "ON_ERROR",
    "MODEL_REGISTERED",
    "CONTROLLER_REGISTERED",
    "SCHEMA_VALIDATED",
    "AUTH_SUCCESS",
    "AUTH_FAILURE",
    "PLUGIN_LOADED",
    "PLUGIN_UNLOADED",
]
