"""
Presence service.

Handles typing indicators, online status, and last seen tracking.
"""

from typing import Any

from django.core.cache import cache
from django.utils import timezone


class PresenceService:
    """
    Service for managing user presence and typing indicators.

    Uses cache for real-time state management.
    """

    # Cache key prefixes
    ONLINE_PREFIX = "messaging:online:"
    TYPING_PREFIX = "messaging:typing:"
    LAST_SEEN_PREFIX = "messaging:last_seen:"

    # Timeouts
    ONLINE_TIMEOUT = 300  # 5 minutes
    TYPING_TIMEOUT = 5  # 5 seconds

    @classmethod
    def _online_key(cls, user_id: int) -> str:
        """Get cache key for online status."""
        return f"{cls.ONLINE_PREFIX}{user_id}"

    @classmethod
    def _typing_key(cls, conversation_id: int, user_id: int) -> str:
        """Get cache key for typing indicator."""
        return f"{cls.TYPING_PREFIX}{conversation_id}:{user_id}"

    @classmethod
    def _last_seen_key(cls, user_id: int) -> str:
        """Get cache key for last seen."""
        return f"{cls.LAST_SEEN_PREFIX}{user_id}"

    @classmethod
    def set_online(cls, user_id: int) -> None:
        """Mark user as online."""
        cache.set(cls._online_key(user_id), True, timeout=cls.ONLINE_TIMEOUT)
        cache.set(
            cls._last_seen_key(user_id),
            timezone.now().isoformat(),
            timeout=86400,  # 24 hours
        )

    @classmethod
    def set_offline(cls, user_id: int) -> None:
        """Mark user as offline."""
        cache.delete(cls._online_key(user_id))
        cache.set(
            cls._last_seen_key(user_id),
            timezone.now().isoformat(),
            timeout=86400,
        )

    @classmethod
    def is_online(cls, user_id: int) -> bool:
        """Check if user is online."""
        return cache.get(cls._online_key(user_id), False)

    @classmethod
    def get_online_users(cls, user_ids: list[int]) -> list[int]:
        """Get list of online user IDs from a list."""
        keys = [cls._online_key(uid) for uid in user_ids]
        results = cache.get_many(keys)
        return [uid for uid in user_ids if results.get(cls._online_key(uid), False)]

    @classmethod
    def get_last_seen(cls, user_id: int) -> str | None:
        """Get user's last seen timestamp."""
        return cache.get(cls._last_seen_key(user_id))

    @classmethod
    def get_last_seen_many(cls, user_ids: list[int]) -> dict[int, str | None]:
        """Get last seen for multiple users."""
        keys = [cls._last_seen_key(uid) for uid in user_ids]
        results = cache.get_many(keys)
        return {uid: results.get(cls._last_seen_key(uid)) for uid in user_ids}

    @classmethod
    def set_typing(cls, conversation_id: int, user_id: int) -> None:
        """Set typing indicator for user in conversation."""
        key = cls._typing_key(conversation_id, user_id)
        cache.set(key, True, timeout=cls.TYPING_TIMEOUT)

    @classmethod
    def clear_typing(cls, conversation_id: int, user_id: int) -> None:
        """Clear typing indicator for user in conversation."""
        key = cls._typing_key(conversation_id, user_id)
        cache.delete(key)

    @classmethod
    def is_typing(cls, conversation_id: int, user_id: int) -> bool:
        """Check if user is typing in conversation."""
        key = cls._typing_key(conversation_id, user_id)
        return cache.get(key, False)

    @classmethod
    def get_typing_users(
        cls,
        conversation_id: int,
        user_ids: list[int],
    ) -> list[int]:
        """Get list of users currently typing in a conversation."""
        keys = [cls._typing_key(conversation_id, uid) for uid in user_ids]
        results = cache.get_many(keys)
        return [
            uid for uid in user_ids if results.get(cls._typing_key(conversation_id, uid), False)
        ]

    @classmethod
    def get_presence_info(
        cls,
        user_ids: list[int],
        conversation_id: int | None = None,
    ) -> dict[int, dict[str, Any]]:
        """
        Get full presence info for multiple users.

        Returns dict mapping user_id to presence info:
        {
            user_id: {
                "online": bool,
                "last_seen": str | None,
                "typing": bool (if conversation_id provided)
            }
        }
        """
        result = {}

        # Get online status
        online_keys = {uid: cls._online_key(uid) for uid in user_ids}
        online_results = cache.get_many(list(online_keys.values()))

        # Get last seen
        last_seen_keys = {uid: cls._last_seen_key(uid) for uid in user_ids}
        last_seen_results = cache.get_many(list(last_seen_keys.values()))

        # Get typing status if conversation provided
        typing_results = {}
        if conversation_id:
            typing_keys = {uid: cls._typing_key(conversation_id, uid) for uid in user_ids}
            typing_results = cache.get_many(list(typing_keys.values()))

        for uid in user_ids:
            info: dict[str, Any] = {
                "online": online_results.get(online_keys[uid], False),
                "last_seen": last_seen_results.get(last_seen_keys[uid]),
            }
            if conversation_id:
                info["typing"] = typing_results.get(cls._typing_key(conversation_id, uid), False)
            result[uid] = info

        return result

    @classmethod
    def heartbeat(cls, user_id: int, conversation_id: int | None = None) -> None:
        """
        Update user's online status and optionally typing indicator.

        Should be called periodically by clients to maintain presence.
        """
        cls.set_online(user_id)
        if conversation_id:
            cls.set_typing(conversation_id, user_id)

    @classmethod
    def cleanup_stale_presence(cls) -> None:
        """
        Cleanup stale presence data.

        This is handled automatically by cache TTL, but can be called
        for explicit cleanup in testing or maintenance.
        """
        # Cache handles expiration automatically
