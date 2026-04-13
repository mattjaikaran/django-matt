"""
Vite configuration for Django Matt.

Provides centralized configuration for Vite dev server and build settings.
"""

from __future__ import annotations

from django.conf import settings

from pydantic import BaseModel, Field


class ViteConfig(BaseModel):
    """
    Vite integration configuration.

    Configure via Django settings:
        MATT_VITE = {
            "DEV_SERVER_URL": "http://localhost:5173",
            "BUILD_DIR": "static/dist",
            "MANIFEST_PATH": "static/dist/.vite/manifest.json",
            "ENTRY_POINTS": ["src/main.js"],
            "HMR_ENABLED": True,
            "REACT_REFRESH": False,
            "STATIC_URL_PREFIX": "/static/dist/",
        }
    """

    dev_server_url: str = Field(default="http://localhost:5173")
    build_dir: str = Field(default="static/dist")
    manifest_path: str = Field(default="static/dist/.vite/manifest.json")
    entry_points: list[str] = Field(default_factory=lambda: ["src/main.js"])
    hmr_enabled: bool = Field(default=True)
    react_refresh: bool = Field(default=False)
    static_url_prefix: str = Field(default="/static/dist/")

    @classmethod
    def from_settings(cls) -> ViteConfig:
        """Create config from Django settings."""
        config_dict = getattr(settings, "MATT_VITE", {})

        field_map = {
            "DEV_SERVER_URL": "dev_server_url",
            "BUILD_DIR": "build_dir",
            "MANIFEST_PATH": "manifest_path",
            "ENTRY_POINTS": "entry_points",
            "HMR_ENABLED": "hmr_enabled",
            "REACT_REFRESH": "react_refresh",
            "STATIC_URL_PREFIX": "static_url_prefix",
        }

        kwargs: dict[str, object] = {}
        for settings_key, field_name in field_map.items():
            if settings_key in config_dict:
                kwargs[field_name] = config_dict[settings_key]

        return cls(**kwargs)

    @property
    def is_dev(self) -> bool:
        """Check if running in development mode."""
        return getattr(settings, "DEBUG", False)


# Cached config instance
_config: ViteConfig | None = None


def get_vite_config() -> ViteConfig:
    """Get the global Vite configuration instance."""
    global _config
    if _config is None:
        _config = ViteConfig.from_settings()
    return _config


def reset_vite_config() -> None:
    """Reset the cached configuration (useful for testing)."""
    global _config
    _config = None


__all__ = [
    "ViteConfig",
    "get_vite_config",
    "reset_vite_config",
]
