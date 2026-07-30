"""Server configuration defaults and loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ServerConfig:
    """Typed representation of MATT_SERVER settings."""

    backend: str = "uvicorn"
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int | str = "auto"
    http2: bool = False
    http3: bool = False
    ssl_cert: str | None = None
    ssl_key: str | None = None
    threading_mode: str = "workers"
    access_log: bool = True
    graceful_timeout: int = 30
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServerConfig:
        """Create config from a settings dict, ignoring unknown keys."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        known_kwargs = {k: v for k, v in data.items() if k in known}
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(**known_kwargs, extra=extra)


# Defaults used when MATT_SERVER is absent from Django settings.
DEFAULTS: dict[str, Any] = {
    "backend": "uvicorn",
    "host": "0.0.0.0",
    "port": 8000,
    "workers": "auto",
    "http2": False,
    "ssl_cert": None,
    "ssl_key": None,
    "http3": False,
    "threading_mode": "workers",
    "graceful_timeout": 30,
}


def get_server_config() -> ServerConfig:
    """Load MATT_SERVER from Django settings, falling back to defaults."""
    try:
        from django.conf import settings as django_settings

        user = getattr(django_settings, "MATT_SERVER", {})
    except Exception:
        user = {}
    merged = {**DEFAULTS, **user}
    return ServerConfig.from_dict(merged)
