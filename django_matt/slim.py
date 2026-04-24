"""
Slim Mode — module registry for controlling which django-matt features load.

Controls middleware, URL patterns, and optional module loading based on
which features the application actually uses.

Modes:
    "full"    — everything loaded (default, backwards-compatible)
    "slim"    — only explicitly enabled modules load
    "minimal" — only core + auth + error handling
    "auto"    — detect which modules are imported/configured and load those
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Mapping from module name to the middleware class dotted paths it requires.
# These are lazy strings so we don't import anything at module level.
MODULE_MIDDLEWARE: dict[str, list[str]] = {
    "auth": ["django_matt.auth.middleware.JWTAuthenticationMiddleware"],
    "cors": ["django_matt.middleware.cors.CORSMiddleware"],
    "security": ["django_matt.middleware.security.SecurityHeadersMiddleware"],
    "request_id": ["django_matt.middleware.request_id.RequestIDMiddleware"],
    "logging": ["django_matt.middleware.logging.RequestLoggingMiddleware"],
    "timing": ["django_matt.middleware.timing.TimingMiddleware"],
    "observability": [
        "django_matt.observability.TracingMiddleware",
        "django_matt.observability.MetricsMiddleware",
        "django_matt.observability.LoggingMiddleware",
    ],
    "flags": ["django_matt.flags.FlagMiddleware"],
    "experiments": ["django_matt.experiments.ExperimentMiddleware"],
    "di": ["django_matt.di.DependencyInjectionMiddleware"],
    "negotiation": ["django_matt.negotiation.ContentNegotiationMiddleware"],
}

# Modules that map to URL patterns in MattAPI.get_urls()
MODULE_URL_FEATURES: dict[str, str] = {
    "observability": "health_url",
    "openapi": "openapi_url",
    "docs": "docs_url",
    "redoc": "redoc_url",
}

# Core modules that are always loaded regardless of mode
CORE_MODULES: frozenset[str] = frozenset({
    "core",
    "router",
    "controller",
    "schema",
    "errors",
    "openapi",
    "docs",
    "redoc",
})

# Settings keys that imply a module is in use
_SETTINGS_MODULE_MAP: dict[str, str] = {
    "AUTH_BACKEND": "auth",
    "JWT_AUTH": "auth",
    "CORS": "cors",
    "SECURITY_HEADERS": "security",
    "REQUEST_ID_HEADER": "request_id",
    "REQUEST_LOGGING": "logging",
    "TIMING": "timing",
    "THROTTLE": "throttling",
    "MIDDLEWARE_STACK": "middleware_stack",
    "DI_AUTO_WIRE": "di",
    "FEATURE_FLAGS": "flags",
    "EXPERIMENTS": "experiments",
    "OBSERVABILITY": "observability",
    "BILLING": "billing",
    "MULTITENANCY": "multitenancy",
    "ANALYTICS": "analytics",
    "WEBSOCKETS": "websockets",
    "GRAPHQL": "graphql",
}

Mode = Literal["full", "slim", "minimal", "auto"]


class SlimConfig(BaseModel):
    """Configuration for slim mode module loading."""

    mode: Mode = "full"
    enabled_modules: list[str] | None = None  # None = all, list = only these
    disabled_modules: list[str] = []
    lazy_imports: bool = True  # defer heavy module imports


# Module-level cache for SlimConfig
_slim_config: SlimConfig | None = None


def get_slim_config() -> SlimConfig:
    """Return the cached SlimConfig, creating it from Django settings if needed."""
    global _slim_config
    if _slim_config is not None:
        return _slim_config
    try:
        from django.conf import settings
        matt_config = getattr(settings, "DJANGO_MATT", {})
        slim_data = matt_config.get("SLIM_MODE", {})
        _slim_config = SlimConfig(**slim_data) if slim_data else SlimConfig()
    except Exception:
        _slim_config = SlimConfig()
    return _slim_config


def reset_slim_config() -> None:
    """Clear the cached SlimConfig so it is re-read on next access."""
    global _slim_config
    _slim_config = None


def is_module_enabled(module_name: str) -> bool:
    """Check whether a module is enabled under the current slim mode config."""
    config = get_slim_config()
    if module_name in CORE_MODULES:
        return True
    if config.mode == "full":
        return module_name not in config.disabled_modules
    if config.mode == "minimal":
        return module_name in {"auth"} and module_name not in config.disabled_modules
    if config.mode == "slim":
        if config.enabled_modules is not None:
            return module_name in config.enabled_modules and module_name not in config.disabled_modules
        return module_name not in config.disabled_modules
    # auto mode — defer to registry
    return module_name not in config.disabled_modules


class ModuleRegistry:
    """
    Tracks which django-matt modules are active.

    In "full" mode, everything is considered active.
    In "minimal" mode, only core + explicitly activated modules load.
    In "auto" mode, modules are detected from Django settings.
    """

    def __init__(self, mode: Mode = "full") -> None:
        self._mode: Mode = mode
        self._active_modules: set[str] = set(CORE_MODULES)
        self._frozen: bool = False

        if mode == "full":
            # In full mode, mark everything as active
            self._all_active = True
        else:
            self._all_active = False

        if mode == "slim":
            # Slim mode: start with core + auth only, user adds what they need
            self._active_modules.add("auth")

        if mode == "minimal":
            # Minimal mode: core + auth + error handling only
            self._active_modules.add("auth")

        if mode == "auto":
            self._detect_from_settings()

    def _detect_from_settings(self) -> None:
        """Scan DJANGO_MATT settings to detect which modules are configured."""
        try:
            from django.conf import settings
            matt_config = getattr(settings, "DJANGO_MATT", {})
        except Exception:
            # Settings not ready yet; skip auto-detection
            return

        for setting_key, module_name in _SETTINGS_MODULE_MAP.items():
            value = matt_config.get(setting_key)
            if value is not None and value is not False:
                self._active_modules.add(module_name)

        # If a middleware stack is set, activate the middleware modules it implies
        stack = matt_config.get("MIDDLEWARE_STACK")
        if stack == "production":
            self._active_modules.update(
                {"security", "request_id", "cors", "logging", "timing"}
            )
        elif stack == "development":
            self._active_modules.update(
                {"request_id", "cors", "logging", "timing"}
            )

    @property
    def mode(self) -> Mode:
        return self._mode

    def activate(self, *modules: str) -> None:
        """Activate one or more modules by name."""
        if self._frozen:
            raise RuntimeError(
                "Cannot activate modules after the registry has been frozen. "
                "Call activate() before get_urls()."
            )
        self._active_modules.update(modules)

    def deactivate(self, *modules: str) -> None:
        """Deactivate one or more modules. Cannot deactivate core modules."""
        if self._frozen:
            raise RuntimeError(
                "Cannot deactivate modules after the registry has been frozen."
            )
        for module in modules:
            if module in CORE_MODULES:
                raise ValueError(f"Cannot deactivate core module: {module!r}")
            self._active_modules.discard(module)

    def is_active(self, module: str) -> bool:
        """Check if a module is active."""
        if self._all_active:
            return True
        return module in self._active_modules

    @property
    def active_modules(self) -> frozenset[str]:
        """Return the set of currently active modules."""
        if self._all_active:
            return frozenset(self._active_modules | set(MODULE_MIDDLEWARE.keys()))
        return frozenset(self._active_modules)

    def get_active_middleware(self) -> list[str]:
        """
        Return middleware class dotted paths for active modules only.

        In "full" mode, returns all middleware. In "minimal"/"auto", returns
        only middleware for activated modules.
        """
        result: list[str] = []
        for module_name, middleware_paths in MODULE_MIDDLEWARE.items():
            if self.is_active(module_name):
                result.extend(middleware_paths)
        return result

    def freeze(self) -> None:
        """Freeze the registry to prevent further modifications."""
        self._frozen = True

    def __repr__(self) -> str:
        count = len(self.active_modules)
        return f"<ModuleRegistry mode={self._mode!r} active={count}>"
