"""
Session utility functions.

Helper functions for session management.
"""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.http import HttpRequest


def get_client_ip(request: "HttpRequest") -> str:
    """
    Extract client IP address from request.

    Handles X-Forwarded-For and other proxy headers.
    """
    forwarded_headers = [
        "HTTP_X_FORWARDED_FOR",
        "HTTP_X_REAL_IP",
        "HTTP_CF_CONNECTING_IP",
        "HTTP_TRUE_CLIENT_IP",
    ]

    for header in forwarded_headers:
        value = request.META.get(header)
        if value:
            ip = value.split(",")[0].strip()
            if ip:
                return ip

    return request.META.get("REMOTE_ADDR", "")


def login_session(
    request: "HttpRequest",
    user: "AbstractUser",
    backend: str | None = None,
) -> None:
    """
    Log a user in via session.

    Creates or updates the session with user information.
    Rotates session key to prevent session fixation.

    Args:
        request: The HTTP request
        user: The user to log in
        backend: Optional authentication backend path
    """
    from django.utils import timezone

    from .config import get_session_config
    from .csrf import rotate_csrf_token

    config = get_session_config()

    # Rotate session key to prevent fixation
    if config.rotate_session_on_login and hasattr(request, "session"):
        request.session.cycle_key()

    # Set user in session
    request.session["_auth_user_id"] = str(user.pk)
    request.session["_auth_user_backend"] = backend or "django.contrib.auth.backends.ModelBackend"
    request.session["_session_created"] = timezone.now().isoformat()
    request.session["_session_fresh"] = True

    # Store device info
    request.session["_device_ip"] = get_client_ip(request)
    request.session["_device_user_agent"] = request.META.get("HTTP_USER_AGENT", "")

    # Track activity
    request.session["_last_activity"] = timezone.now().isoformat()

    # Set user on request
    request.user = user

    # Rotate CSRF token
    rotate_csrf_token(request)

    # Handle single session per user
    if config.single_session_per_user:
        from .backend import delete_user_sessions

        delete_user_sessions(user, except_session=request.session.session_key)

    request.session.modified = True


def logout_session(request: "HttpRequest") -> None:
    """
    Log out the current user.

    Clears session data and optionally deletes the session.

    Args:
        request: The HTTP request
    """
    from django.contrib.auth.models import AnonymousUser

    from .config import get_session_config
    from .csrf import rotate_csrf_token

    config = get_session_config()

    if config.clear_session_on_logout:
        # Clear all session data
        request.session.flush()
    else:
        # Just remove auth data
        request.session.pop("_auth_user_id", None)
        request.session.pop("_auth_user_backend", None)
        request.session.pop("_session_created", None)
        request.session.pop("_session_fresh", None)
        request.session.modified = True

    # Set anonymous user
    request.user = AnonymousUser()

    # Rotate CSRF token
    rotate_csrf_token(request)


def get_session_user(request: "HttpRequest") -> Optional["AbstractUser"]:
    """
    Get the user from the session.

    Args:
        request: The HTTP request

    Returns:
        The user if authenticated, None otherwise
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    if not hasattr(request, "session"):
        return None

    user_id = request.session.get("_auth_user_id")
    if not user_id:
        return None

    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return None


def is_session_authenticated(request: "HttpRequest") -> bool:
    """
    Check if the current session is authenticated.

    Args:
        request: The HTTP request

    Returns:
        True if authenticated, False otherwise
    """
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return True

    return get_session_user(request) is not None


def get_session_data(
    request: "HttpRequest",
    key: str,
    default: Any = None,
) -> Any:
    """
    Get data from the session.

    Args:
        request: The HTTP request
        key: The key to get
        default: Default value if key not found

    Returns:
        The value or default
    """
    if not hasattr(request, "session"):
        return default

    return request.session.get(key, default)


def set_session_data(
    request: "HttpRequest",
    key: str,
    value: Any,
) -> None:
    """
    Set data in the session.

    Args:
        request: The HTTP request
        key: The key to set
        value: The value to store
    """
    if not hasattr(request, "session"):
        return

    # Don't allow overwriting internal keys
    if key.startswith("_auth_") or key.startswith("_session_"):
        raise ValueError(f"Cannot set reserved session key: {key}")

    request.session[key] = value
    request.session.modified = True


def delete_session_data(request: "HttpRequest", key: str) -> None:
    """
    Delete data from the session.

    Args:
        request: The HTTP request
        key: The key to delete
    """
    if not hasattr(request, "session"):
        return

    if key in request.session:
        del request.session[key]
        request.session.modified = True


def flash_message(
    request: "HttpRequest",
    message: str,
    level: str = "info",
) -> None:
    """
    Add a flash message to the session.

    Flash messages are displayed once and then removed.

    Args:
        request: The HTTP request
        message: The message text
        level: Message level (info, success, warning, error)
    """
    if not hasattr(request, "session"):
        return

    messages = request.session.get("_flash_messages", [])
    messages.append({"message": message, "level": level})
    request.session["_flash_messages"] = messages
    request.session.modified = True


def get_flash_messages(request: "HttpRequest") -> list[dict[str, str]]:
    """
    Get and clear flash messages from the session.

    Args:
        request: The HTTP request

    Returns:
        List of message dicts with 'message' and 'level' keys
    """
    if not hasattr(request, "session"):
        return []

    messages = request.session.pop("_flash_messages", [])
    if messages:
        request.session.modified = True

    return messages


def get_session_info(request: "HttpRequest") -> dict[str, Any]:
    """
    Get information about the current session.

    Args:
        request: The HTTP request

    Returns:
        Dict with session information
    """
    if not hasattr(request, "session"):
        return {"authenticated": False}

    session = request.session

    return {
        "authenticated": is_session_authenticated(request),
        "session_key": session.session_key,
        "created": session.get("_session_created"),
        "last_activity": session.get("_last_activity"),
        "fresh": session.get("_session_fresh", False),
        "ip_address": session.get("_device_ip"),
        "user_agent": session.get("_device_user_agent"),
        "expires": session.get_expiry_date().isoformat()
        if hasattr(session, "get_expiry_date")
        else None,
    }


async def alogin_session(
    request: "HttpRequest",
    user: "AbstractUser",
    backend: str | None = None,
) -> None:
    """Async version of login_session."""
    from asgiref.sync import sync_to_async

    await sync_to_async(login_session)(request, user, backend)


async def alogout_session(request: "HttpRequest") -> None:
    """Async version of logout_session."""
    from asgiref.sync import sync_to_async

    await sync_to_async(logout_session)(request)


async def aget_session_user(request: "HttpRequest") -> Optional["AbstractUser"]:
    """Async version of get_session_user."""
    from asgiref.sync import sync_to_async

    return await sync_to_async(get_session_user)(request)
