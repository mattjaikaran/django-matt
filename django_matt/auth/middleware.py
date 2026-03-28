"""
Authentication middleware for Django Matt.

Provides middleware for JWT authentication that automatically
attaches authenticated users to requests.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse, JsonResponse

from django_matt.auth.jwt import (
    ExpiredSignatureError,
    InvalidTokenError,
    aget_user_from_token,
    get_token_from_request,
    get_user_from_token,
    verify_access_token,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

# Singleton -- avoids per-request allocation for unauthenticated traffic
_ANONYMOUS_USER = AnonymousUser()


def _set_request_auser(
    request: HttpRequest, user: AbstractBaseUser | AnonymousUser
) -> None:
    """Set ``request.auser`` as an async callable returning *user*.

    Mirrors Django's ``AuthenticationMiddleware`` contract so that
    ``await request.auser()`` works in async views regardless of
    whether Django's own auth middleware is installed.
    """

    async def _auser() -> AbstractBaseUser | AnonymousUser:
        return user

    request.auser = _auser  # type: ignore[attr-defined]


class JWTAuthenticationMiddleware:
    """
    Middleware that authenticates requests using JWT tokens.

    If a valid JWT token is present in the Authorization header,
    the user is attached to the request. Otherwise, request.user
    is set to AnonymousUser.

    Usage in settings.py:
        MIDDLEWARE = [
            ...
            'django_matt.auth.middleware.JWTAuthenticationMiddleware',
            ...
        ]

    This middleware does NOT block unauthenticated requests. Use
    permission decorators or permission_classes to protect endpoints.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Try to authenticate
        self._authenticate(request)
        return self.get_response(request)

    def _authenticate(self, request: HttpRequest):
        """Attempt to authenticate the request with JWT."""
        token = get_token_from_request(request)

        if token is None:
            if not hasattr(request, "user") or request.user is None:
                request.user = _ANONYMOUS_USER
            _set_request_auser(request, request.user)
            return

        try:
            # Decode once, pass payload to avoid double-decode
            payload = verify_access_token(token)
            user = get_user_from_token(token, _payload=payload)

            if user and user.is_active:
                request.user = user
                request.token_payload = payload
            else:
                request.user = _ANONYMOUS_USER

        except (InvalidTokenError, ExpiredSignatureError):
            request.user = _ANONYMOUS_USER

        _set_request_auser(request, request.user)


class JWTAuthenticationMiddlewareAsync:
    """
    Async version of JWT authentication middleware.

    Usage in settings.py:
        MIDDLEWARE = [
            ...
            'django_matt.auth.middleware.JWTAuthenticationMiddlewareAsync',
            ...
        ]
    """

    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        await self._authenticate(request)
        return await self.get_response(request)

    async def _authenticate(self, request: HttpRequest):
        """Attempt to authenticate the request with JWT."""
        token = get_token_from_request(request)

        if token is None:
            if not hasattr(request, "user") or request.user is None:
                request.user = _ANONYMOUS_USER
            _set_request_auser(request, request.user)
            return

        try:
            # Decode once, pass payload to async user lookup
            payload = verify_access_token(token)
            user = await aget_user_from_token(token, _payload=payload)

            if user and user.is_active:
                request.user = user
                request.token_payload = payload
            else:
                request.user = _ANONYMOUS_USER

        except (InvalidTokenError, ExpiredSignatureError):
            request.user = _ANONYMOUS_USER

        _set_request_auser(request, request.user)


class JWTStrictAuthenticationMiddleware:
    """
    Strict JWT authentication middleware.

    Unlike JWTAuthenticationMiddleware, this middleware returns 401
    for requests with invalid tokens (rather than proceeding anonymously).

    Requests without tokens are still allowed through as anonymous.

    Usage in settings.py:
        MIDDLEWARE = [
            ...
            'django_matt.auth.middleware.JWTStrictAuthenticationMiddleware',
            ...
        ]
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        result = self._authenticate(request)

        if isinstance(result, HttpResponse):
            return result

        return self.get_response(request)

    def _authenticate(self, request: HttpRequest) -> HttpResponse | None:
        """Attempt to authenticate the request with JWT."""
        token = get_token_from_request(request)

        if token is None:
            if not hasattr(request, "user") or request.user is None:
                request.user = _ANONYMOUS_USER
            _set_request_auser(request, request.user)
            return None

        # Token present - must be valid
        try:
            # Decode once, pass payload to avoid double-decode
            payload = verify_access_token(token)
            user = get_user_from_token(token, _payload=payload)

            if user is None:
                return JsonResponse(
                    {"detail": "User not found", "code": "user_not_found"},
                    status=401,
                )

            if not user.is_active:
                return JsonResponse(
                    {"detail": "User is inactive", "code": "user_inactive"},
                    status=401,
                )

            request.user = user
            request.token_payload = payload
            _set_request_auser(request, request.user)
            return None

        except ExpiredSignatureError:
            return JsonResponse(
                {"detail": "Token has expired", "code": "token_expired"},
                status=401,
            )
        except InvalidTokenError as e:
            return JsonResponse(
                {"detail": f"Invalid token: {e}", "code": "token_invalid"},
                status=401,
            )


__all__ = [
    "JWTAuthenticationMiddleware",
    "JWTAuthenticationMiddlewareAsync",
    "JWTStrictAuthenticationMiddleware",
    "_set_request_auser",
]
