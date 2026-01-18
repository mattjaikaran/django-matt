"""
Group/Room management utilities for WebSockets.

Provides utilities for:
- Broadcasting to groups
- Managing user presence
- Tracking room membership

Usage:
    from django_matt.websockets.groups import broadcast, get_group_users

    # Broadcast to a group
    await broadcast("chat_room_1", {
        "type": "chat_message",
        "message": "Hello!",
        "user": "john",
    })

    # Get users in a room (requires presence tracking)
    users = await get_group_users("chat_room_1")
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from django_matt.websockets.config import get_websocket_config

logger = logging.getLogger(__name__)


@dataclass
class PresenceInfo:
    """Information about a user's presence in a group."""

    user_id: str
    channel_name: str
    joined_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class PresenceManager:
    """
    Manages user presence in groups.

    Uses cache backend for distributed presence tracking.

    Usage:
        presence = PresenceManager()

        # Track user joining
        await presence.user_joined("room_1", user_id="123", channel_name="specific.abc")

        # Get users in room
        users = await presence.get_users("room_1")

        # Track user leaving
        await presence.user_left("room_1", user_id="123")
    """

    def __init__(self, cache_alias: str = "default"):
        self.config = get_websocket_config()
        self.cache_alias = cache_alias
        self._prefix = f"{self.config.group_prefix}presence:"

    def _get_cache(self):
        """Get cache backend."""
        from django.core.cache import caches

        return caches[self.cache_alias]

    def _presence_key(self, group_name: str) -> str:
        """Get cache key for presence data."""
        return f"{self._prefix}{group_name}"

    async def user_joined(
        self,
        group_name: str,
        user_id: str,
        channel_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record user joining a group."""
        cache = self._get_cache()
        key = self._presence_key(group_name)

        # Get current presence data
        data = cache.get(key) or {}

        # Add user
        data[user_id] = {
            "channel_name": channel_name,
            "joined_at": datetime.now(UTC).isoformat(),
            "metadata": metadata or {},
        }

        # Store with TTL
        cache.set(key, data, timeout=86400)  # 24 hours

        logger.debug(f"User {user_id} joined group {group_name}")

    async def user_left(self, group_name: str, user_id: str) -> None:
        """Record user leaving a group."""
        cache = self._get_cache()
        key = self._presence_key(group_name)

        data = cache.get(key) or {}
        if user_id in data:
            del data[user_id]
            cache.set(key, data, timeout=86400)

        logger.debug(f"User {user_id} left group {group_name}")

    async def get_users(self, group_name: str) -> list[PresenceInfo]:
        """Get all users in a group."""
        cache = self._get_cache()
        key = self._presence_key(group_name)

        data = cache.get(key) or {}

        users = []
        for user_id, info in data.items():
            try:
                joined_at = datetime.fromisoformat(info["joined_at"])
            except (KeyError, ValueError):
                joined_at = datetime.now(UTC)

            users.append(
                PresenceInfo(
                    user_id=user_id,
                    channel_name=info.get("channel_name", ""),
                    joined_at=joined_at,
                    metadata=info.get("metadata", {}),
                )
            )

        return users

    async def get_user_count(self, group_name: str) -> int:
        """Get number of users in a group."""
        cache = self._get_cache()
        key = self._presence_key(group_name)
        data = cache.get(key) or {}
        return len(data)

    async def is_user_in_group(self, group_name: str, user_id: str) -> bool:
        """Check if user is in a group."""
        cache = self._get_cache()
        key = self._presence_key(group_name)
        data = cache.get(key) or {}
        return user_id in data

    async def get_user_groups(self, user_id: str) -> list[str]:
        """Get all groups a user is in."""
        # This requires scanning all groups - not efficient for large scale
        # Consider using a reverse index in production
        cache = self._get_cache()

        # This is a simplified implementation
        # In production, maintain a user -> groups index
        groups = []
        # Would need to iterate through all group keys
        return groups

    async def clear_group(self, group_name: str) -> None:
        """Clear all presence data for a group."""
        cache = self._get_cache()
        key = self._presence_key(group_name)
        cache.delete(key)


# Global presence manager
_presence_manager: PresenceManager | None = None


def get_presence_manager() -> PresenceManager:
    """Get the global presence manager."""
    global _presence_manager
    if _presence_manager is None:
        _presence_manager = PresenceManager()
    return _presence_manager


async def get_channel_layer():
    """Get the default channel layer."""
    try:
        from channels.layers import get_channel_layer as channels_get_layer

        return channels_get_layer()
    except ImportError:
        logger.warning("channels package not installed")
        return None


async def broadcast(
    group_name: str,
    data: dict,
    message_type: str = "group_message",
) -> bool:
    """
    Broadcast a message to a group.

    Args:
        group_name: Name of the group to broadcast to
        data: Data to send
        message_type: Type of channel layer message

    Returns:
        True if broadcast was sent, False otherwise
    """
    channel_layer = await get_channel_layer()
    if not channel_layer:
        return False

    config = get_websocket_config()
    prefixed_name = f"{config.group_prefix}{group_name}"

    try:
        await channel_layer.group_send(
            prefixed_name,
            {
                "type": message_type,
                "data": data,
            },
        )
        return True
    except Exception as e:
        logger.error(f"Failed to broadcast to {group_name}: {e}")
        return False


async def send_to_user(
    user_id: str,
    data: dict,
    group_prefix: str = "user_",
) -> bool:
    """
    Send a message to a specific user.

    Requires the user to have joined a user-specific group.

    Args:
        user_id: User ID to send to
        data: Data to send
        group_prefix: Prefix for user groups (default: "user_")

    Returns:
        True if message was sent, False otherwise
    """
    group_name = f"{group_prefix}{user_id}"
    return await broadcast(group_name, data)


async def send_to_channel(
    channel_name: str,
    data: dict,
    message_type: str = "direct_message",
) -> bool:
    """
    Send a message directly to a channel.

    Args:
        channel_name: Channel name to send to
        data: Data to send
        message_type: Type of channel layer message

    Returns:
        True if message was sent, False otherwise
    """
    channel_layer = await get_channel_layer()
    if not channel_layer:
        return False

    try:
        await channel_layer.send(
            channel_name,
            {
                "type": message_type,
                "data": data,
            },
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send to channel {channel_name}: {e}")
        return False


async def get_group_users(group_name: str) -> list[PresenceInfo]:
    """
    Get all users in a group.

    Requires presence tracking to be enabled.
    """
    return await get_presence_manager().get_users(group_name)


async def get_group_count(group_name: str) -> int:
    """Get the number of users in a group."""
    return await get_presence_manager().get_user_count(group_name)
