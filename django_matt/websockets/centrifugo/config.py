"""
Centrifugo configuration for django-matt.

Settings in settings.py:

    DJANGO_MATT_CENTRIFUGO = {
        "API_URL": "http://localhost:8000/api",
        "API_KEY": "your-api-key",
        "SECRET": "your-centrifugo-secret",
        "WS_URL": "ws://localhost:8001/connection/websocket",
        "TOKEN_EXPIRE": 3600,
        "PROXY_CONNECT_PATH": "/centrifugo/connect/",
        "PROXY_SUBSCRIBE_PATH": "/centrifugo/subscribe/",
        "PROXY_PUBLISH_PATH": "/centrifugo/publish/",
        "PROXY_RPC_PATH": "/centrifugo/rpc/",
    }
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass
class CentrifugoConfig:
    """Centrifugo connection and proxy configuration."""

    api_url: str = "http://localhost:8000/api"
    api_key: str = ""
    secret: str = ""
    ws_url: str = "ws://localhost:8001/connection/websocket"
    token_expire: int = 3600

    # Proxy paths (used by get_centrifugo_urls)
    proxy_connect_path: str = "connect/"
    proxy_subscribe_path: str = "subscribe/"
    proxy_publish_path: str = "publish/"
    proxy_rpc_path: str = "rpc/"

    @classmethod
    def from_settings(cls) -> CentrifugoConfig:
        """Load configuration from Django settings."""
        cfg = getattr(settings, "DJANGO_MATT_CENTRIFUGO", {})
        return cls(
            api_url=cfg.get("API_URL", "http://localhost:8000/api"),
            api_key=cfg.get("API_KEY", ""),
            secret=cfg.get("SECRET", ""),
            ws_url=cfg.get("WS_URL", "ws://localhost:8001/connection/websocket"),
            token_expire=cfg.get("TOKEN_EXPIRE", 3600),
            proxy_connect_path=cfg.get("PROXY_CONNECT_PATH", "connect/").lstrip("/"),
            proxy_subscribe_path=cfg.get("PROXY_SUBSCRIBE_PATH", "subscribe/").lstrip("/"),
            proxy_publish_path=cfg.get("PROXY_PUBLISH_PATH", "publish/").lstrip("/"),
            proxy_rpc_path=cfg.get("PROXY_RPC_PATH", "rpc/").lstrip("/"),
        )


_config: CentrifugoConfig | None = None


def get_centrifugo_config() -> CentrifugoConfig:
    """Return the global CentrifugoConfig singleton."""
    global _config
    if _config is None:
        _config = CentrifugoConfig.from_settings()
    return _config
