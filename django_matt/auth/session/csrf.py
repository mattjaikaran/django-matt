"""
CSRF protection utilities.

Provides CSRF token generation, validation, and protection utilities.
"""

import functools
import hmac
import secrets
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest


# CSRF token length
CSRF_TOKEN_LENGTH = 32
CSRF_SECRET_LENGTH = 32


def _get_secret_key() -> bytes:
    """Get the Django SECRET_KEY as bytes."""
    from django.conf import settings

    secret = getattr(settings, "SECRET_KEY", "fallback-secret-key")
    if isinstance(secret, str):
        return secret.encode()
    return secret


def _generate_csrf_secret() -> str:
    """Generate a random CSRF secret."""
    return secrets.token_hex(CSRF_SECRET_LENGTH)


def _mask_token(secret: str) -> str:
    """
    Mask a CSRF secret to create a token.

    This creates a unique token each time while remaining verifiable.
    """
    mask = secrets.token_hex(CSRF_SECRET_LENGTH)
    # XOR the secret with the mask
    masked = "".join(chr(ord(a) ^ ord(b)) for a, b in zip(secret, mask, strict=False))
    # Return mask + masked (both hex encoded)
    return mask + masked.encode().hex()


def _unmask_token(token: str) -> str | None:
    """
    Unmask a CSRF token to get the original secret.

    Returns None if token is invalid.
    """
    try:
        if len(token) < CSRF_SECRET_LENGTH * 4:
            return None

        mask = token[: CSRF_SECRET_LENGTH * 2]
        masked_hex = token[CSRF_SECRET_LENGTH * 2 :]
        masked = bytes.fromhex(masked_hex).decode()

        # XOR to get original
        secret = "".join(chr(ord(a) ^ ord(b)) for a, b in zip(masked, mask, strict=False))
        return secret
    except Exception:
        return None


def get_csrf_token(request: "HttpRequest") -> str:
    """
    Get or create a CSRF token for the request.

    The token is stored in the session and returned.
    Each call returns a differently masked version of the same secret.

    Args:
        request: The HTTP request

    Returns:
        The CSRF token
    """
    # Get or create the secret from session
    if hasattr(request, "session"):
        secret = request.session.get("_csrf_secret")
        if not secret:
            secret = _generate_csrf_secret()
            request.session["_csrf_secret"] = secret
    else:
        # Fallback if no session
        if not hasattr(request, "_csrf_secret"):
            request._csrf_secret = _generate_csrf_secret()
        secret = request._csrf_secret

    # Return a masked token
    return _mask_token(secret)


def verify_csrf_token(request: "HttpRequest", token: str) -> bool:
    """
    Verify a CSRF token against the request's secret.

    Args:
        request: The HTTP request
        token: The token to verify

    Returns:
        True if valid, False otherwise
    """
    if not token:
        return False

    # Get the secret from session
    if hasattr(request, "session"):
        secret = request.session.get("_csrf_secret")
    else:
        secret = getattr(request, "_csrf_secret", None)

    if not secret:
        return False

    # Unmask the token
    token_secret = _unmask_token(token)
    if not token_secret:
        return False

    # Compare secrets using constant-time comparison
    return hmac.compare_digest(secret, token_secret)


def rotate_csrf_token(request: "HttpRequest") -> str:
    """
    Generate a new CSRF secret and token.

    Should be called after login to prevent session fixation.

    Args:
        request: The HTTP request

    Returns:
        The new CSRF token
    """
    secret = _generate_csrf_secret()

    if hasattr(request, "session"):
        request.session["_csrf_secret"] = secret
    else:
        request._csrf_secret = secret

    return _mask_token(secret)


def csrf_exempt(view_func: Callable) -> Callable:
    """
    Decorator to mark a view as exempt from CSRF verification.

    Usage:
        @api.post("/webhook")
        @csrf_exempt
        async def webhook(request):
            # External webhooks don't have CSRF tokens
            ...
    """

    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        return view_func(*args, **kwargs)

    wrapper._csrf_exempt = True
    return wrapper


def csrf_protect(view_func: Callable) -> Callable:
    """
    Decorator to explicitly require CSRF protection on a view.

    Useful for views that might otherwise be exempt.

    Usage:
        @api.post("/sensitive-action")
        @csrf_protect
        async def sensitive_action(request):
            ...
    """

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.http import HttpResponseForbidden

        # Get token from request
        from .config import get_session_config

        config = get_session_config()
        header_name = f"HTTP_{config.csrf_header_name.upper().replace('-', '_')}"

        token = request.META.get(header_name)
        if not token and hasattr(request, "POST"):
            token = request.POST.get("csrfmiddlewaretoken")
        if not token:
            token = request.COOKIES.get(config.csrf_cookie_name)

        if not token or not verify_csrf_token(request, token):
            return HttpResponseForbidden("CSRF token required")

        return view_func(request, *args, **kwargs)

    @functools.wraps(view_func)
    async def async_wrapper(request, *args, **kwargs):
        from django.http import HttpResponseForbidden

        from .config import get_session_config

        config = get_session_config()
        header_name = f"HTTP_{config.csrf_header_name.upper().replace('-', '_')}"

        token = request.META.get(header_name)
        if not token and hasattr(request, "POST"):
            token = request.POST.get("csrfmiddlewaretoken")
        if not token:
            token = request.COOKIES.get(config.csrf_cookie_name)

        if not token or not verify_csrf_token(request, token):
            return HttpResponseForbidden("CSRF token required")

        return await view_func(request, *args, **kwargs)

    import asyncio

    if asyncio.iscoroutinefunction(view_func):
        return async_wrapper
    return wrapper


def ensure_csrf_cookie(view_func: Callable) -> Callable:
    """
    Decorator to ensure the CSRF cookie is set on the response.

    Useful for views that need to provide the token to JavaScript.

    Usage:
        @api.get("/csrf-token")
        @ensure_csrf_cookie
        async def get_csrf(request):
            return {"detail": "CSRF cookie set"}
    """

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)

        # Ensure token is generated
        token = get_csrf_token(request)

        # Set cookie on response
        from .config import get_session_config

        config = get_session_config()

        if hasattr(response, "set_cookie"):
            response.set_cookie(
                config.csrf_cookie_name,
                token,
                max_age=config.csrf_cookie_age,
                path="/",
                secure=config.csrf_cookie_secure,
                httponly=config.csrf_cookie_httponly,
                samesite=config.csrf_cookie_samesite,
            )

        return response

    @functools.wraps(view_func)
    async def async_wrapper(request, *args, **kwargs):
        response = await view_func(request, *args, **kwargs)

        token = get_csrf_token(request)

        from .config import get_session_config

        config = get_session_config()

        if hasattr(response, "set_cookie"):
            response.set_cookie(
                config.csrf_cookie_name,
                token,
                max_age=config.csrf_cookie_age,
                path="/",
                secure=config.csrf_cookie_secure,
                httponly=config.csrf_cookie_httponly,
                samesite=config.csrf_cookie_samesite,
            )

        return response

    import asyncio

    if asyncio.iscoroutinefunction(view_func):
        return async_wrapper
    return wrapper
