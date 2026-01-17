"""
WebSocket configuration for django-matt.

Requires: pip install channels channels-redis

Configuration in settings.py:

    DJANGO_MATT_WEBSOCKETS = {
        "ENABLED": True,
        "AUTH_REQUIRED": False,  # Require authentication by default
        "AUTH_METHODS": ["jwt", "session"],  # Supported auth methods
        "HEARTBEAT_INTERVAL": 30,  # Seconds between heartbeats
        "MAX_MESSAGE_SIZE": 65536,  # Max message size in bytes
        "CLOSE_TIMEOUT": 5,  # Seconds to wait before force closing

        # Rate limiting
        "RATE_LIMIT": {
            "ENABLED": True,
            "MESSAGES_PER_SECOND": 10,
            "BURST_SIZE": 20,
        },

        # Groups/Rooms
        "GROUP_PREFIX": "matt_",
        "MAX_GROUPS_PER_USER": 100,
    }

    # Channel layers configuration (standard Django Channels)
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [("127.0.0.1", 6379)],
            },
        },
    }
"""

from dataclasses import dataclass, field
from typing import Literal

from django.conf import settings


AuthMethod = Literal["jwt", "session", "token", "anonymous"]


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    enabled: bool = True
    messages_per_second: int = 10
    burst_size: int = 20


@dataclass
class WebSocketConfig:
    """Main WebSocket configuration."""

    enabled: bool = True
    auth_required: bool = False
    auth_methods: list[AuthMethod] = field(default_factory=lambda: ["jwt", "session"])
    heartbeat_interval: int = 30  # seconds
    max_message_size: int = 65536  # 64KB
    close_timeout: int = 5  # seconds

    # Rate limiting
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)

    # Groups/Rooms
    group_prefix: str = "matt_"
    max_groups_per_user: int = 100

    # Reconnection
    allow_reconnect: bool = True
    reconnect_timeout: int = 60  # seconds to keep state for reconnection

    @classmethod
    def from_settings(cls) -> "WebSocketConfig":
        """Load configuration from Django settings."""
        config_dict = getattr(settings, "DJANGO_MATT_WEBSOCKETS", {})

        rate_limit_dict = config_dict.get("RATE_LIMIT", {})
        rate_limit = RateLimitConfig(
            enabled=rate_limit_dict.get("ENABLED", True),
            messages_per_second=rate_limit_dict.get("MESSAGES_PER_SECOND", 10),
            burst_size=rate_limit_dict.get("BURST_SIZE", 20),
        )

        return cls(
            enabled=config_dict.get("ENABLED", True),
            auth_required=config_dict.get("AUTH_REQUIRED", False),
            auth_methods=config_dict.get("AUTH_METHODS", ["jwt", "session"]),
            heartbeat_interval=config_dict.get("HEARTBEAT_INTERVAL", 30),
            max_message_size=config_dict.get("MAX_MESSAGE_SIZE", 65536),
            close_timeout=config_dict.get("CLOSE_TIMEOUT", 5),
            rate_limit=rate_limit,
            group_prefix=config_dict.get("GROUP_PREFIX", "matt_"),
            max_groups_per_user=config_dict.get("MAX_GROUPS_PER_USER", 100),
            allow_reconnect=config_dict.get("ALLOW_RECONNECT", True),
            reconnect_timeout=config_dict.get("RECONNECT_TIMEOUT", 60),
        )


# Global config instance (lazy-loaded)
_websocket_config: WebSocketConfig | None = None


def get_websocket_config() -> WebSocketConfig:
    """Get the WebSocket configuration singleton."""
    global _websocket_config
    if _websocket_config is None:
        _websocket_config = WebSocketConfig.from_settings()
    return _websocket_config


def websocket_config() -> WebSocketConfig:
    """Alias for get_websocket_config()."""
    return get_websocket_config()
