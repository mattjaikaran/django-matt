"""
Session backend utilities.

Enhanced session management with user tracking and multiple session support.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from django.contrib.sessions.backends.db import SessionStore as DjangoSessionStore
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.http import HttpRequest


class SessionStore(DjangoSessionStore):
    """
    Enhanced session store with additional features.

    Extends Django's default session store with:
    - User tracking
    - Activity timestamps
    - Device/browser info
    - Session metadata
    """

    def __init__(self, session_key: Optional[str] = None):
        super().__init__(session_key)
        self._user_id = None

    def set_user(self, user: "AbstractUser") -> None:
        """Associate session with a user."""
        self._user_id = user.pk
        self["_auth_user_id"] = str(user.pk)
        self["_session_created"] = timezone.now().isoformat()
        self["_session_fresh"] = True

    def get_user_id(self) -> Optional[int]:
        """Get the associated user ID."""
        user_id = self.get("_auth_user_id")
        if user_id:
            try:
                return int(user_id)
            except (ValueError, TypeError):
                pass
        return None

    def mark_activity(self) -> None:
        """Update last activity timestamp."""
        self["_last_activity"] = timezone.now().isoformat()

    def get_last_activity(self) -> Optional[datetime]:
        """Get last activity time."""
        timestamp = self.get("_last_activity")
        if timestamp:
            try:
                return datetime.fromisoformat(timestamp)
            except ValueError:
                pass
        return None

    def mark_stale(self) -> None:
        """Mark session as no longer fresh."""
        self["_session_fresh"] = False

    def is_fresh(self, max_age: int = 300) -> bool:
        """Check if session is fresh (recently authenticated)."""
        if not self.get("_session_fresh", False):
            return False

        created = self.get("_session_created")
        if created:
            try:
                created_time = datetime.fromisoformat(created)
                age = (timezone.now() - created_time).total_seconds()
                return age < max_age
            except ValueError:
                pass
        return False

    def set_device_info(
        self,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Store device information."""
        self["_device_ip"] = ip_address
        self["_device_user_agent"] = user_agent
        self["_device_fingerprint"] = self._generate_fingerprint(ip_address, user_agent)

    def _generate_fingerprint(self, ip: str, user_agent: str) -> str:
        """Generate a device fingerprint."""
        data = f"{ip}:{user_agent}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


def create_session(
    user: "AbstractUser",
    request: Optional["HttpRequest"] = None,
    data: Optional[Dict[str, Any]] = None,
) -> SessionStore:
    """
    Create a new session for a user.

    Args:
        user: The user to create session for
        request: Optional request for device info
        data: Optional additional session data

    Returns:
        The created session
    """
    from .config import get_session_config

    config = get_session_config()
    session = SessionStore()

    # Create new session
    session.create()

    # Set user
    session.set_user(user)

    # Set device info if request provided
    if request:
        from ..session.utils import get_client_ip

        ip = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        session.set_device_info(ip, user_agent)

    # Set additional data
    if data:
        for key, value in data.items():
            if not key.startswith("_"):
                session[key] = value

    # Mark initial activity
    session.mark_activity()

    session.save()

    return session


def get_session(session_key: str) -> Optional[SessionStore]:
    """
    Get an existing session by key.

    Args:
        session_key: The session key

    Returns:
        The session if found and valid, None otherwise
    """
    if not session_key:
        return None

    session = SessionStore(session_key)

    if session.exists(session_key):
        return session

    return None


def delete_session(session_key: str) -> bool:
    """
    Delete a session.

    Args:
        session_key: The session key to delete

    Returns:
        True if deleted, False if not found
    """
    session = get_session(session_key)
    if session:
        session.delete()
        return True
    return False


def refresh_session(session_key: str) -> Optional[str]:
    """
    Refresh a session (create new key, preserve data).

    Useful for session rotation after login.

    Args:
        session_key: The current session key

    Returns:
        The new session key, or None if session not found
    """
    session = get_session(session_key)
    if not session:
        return None

    # Cycle the key (creates new key, copies data)
    session.cycle_key()
    session.mark_activity()
    session.save()

    return session.session_key


def get_user_sessions(user: "AbstractUser") -> List[Dict[str, Any]]:
    """
    Get all active sessions for a user.

    Args:
        user: The user to get sessions for

    Returns:
        List of session info dicts
    """
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    sessions = []
    user_id_str = str(user.pk)

    # Get all non-expired sessions
    for session in Session.objects.filter(expire_date__gt=timezone.now()):
        try:
            data = session.get_decoded()
            if data.get("_auth_user_id") == user_id_str:
                sessions.append({
                    "session_key": session.session_key,
                    "created": data.get("_session_created"),
                    "last_activity": data.get("_last_activity"),
                    "ip_address": data.get("_device_ip"),
                    "user_agent": data.get("_device_user_agent"),
                    "expires": session.expire_date.isoformat(),
                })
        except Exception:
            continue

    return sessions


def delete_user_sessions(
    user: "AbstractUser",
    except_session: Optional[str] = None,
) -> int:
    """
    Delete all sessions for a user.

    Args:
        user: The user whose sessions to delete
        except_session: Optional session key to keep

    Returns:
        Number of sessions deleted
    """
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    count = 0
    user_id_str = str(user.pk)

    for session in Session.objects.filter(expire_date__gt=timezone.now()):
        if except_session and session.session_key == except_session:
            continue

        try:
            data = session.get_decoded()
            if data.get("_auth_user_id") == user_id_str:
                session.delete()
                count += 1
        except Exception:
            continue

    return count


def delete_other_sessions(
    user: "AbstractUser",
    current_session_key: str,
) -> int:
    """
    Delete all sessions for a user except the current one.

    Args:
        user: The user whose other sessions to delete
        current_session_key: The session to keep

    Returns:
        Number of sessions deleted
    """
    return delete_user_sessions(user, except_session=current_session_key)


def cleanup_expired_sessions() -> int:
    """
    Remove all expired sessions.

    Returns:
        Number of sessions cleaned up
    """
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    expired = Session.objects.filter(expire_date__lt=timezone.now())
    count = expired.count()
    expired.delete()
    return count


async def aget_user_sessions(user: "AbstractUser") -> List[Dict[str, Any]]:
    """Async version of get_user_sessions."""
    from asgiref.sync import sync_to_async

    return await sync_to_async(get_user_sessions)(user)


async def adelete_user_sessions(
    user: "AbstractUser",
    except_session: Optional[str] = None,
) -> int:
    """Async version of delete_user_sessions."""
    from asgiref.sync import sync_to_async

    return await sync_to_async(delete_user_sessions)(user, except_session)
