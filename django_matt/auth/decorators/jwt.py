"""
JWT authentication decorators.
"""

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from django.http import JsonResponse

from django_matt.auth.decorators.base import get_request

F = TypeVar("F", bound=Callable[..., Any])


def jwt_required(func: F) -> F:
    """
    Decorator that requires a valid JWT token.

    Validates the JWT and attaches the user to the request.

    Example:
        class TaskController(APIController):
            @get("")
            @jwt_required
            async def list_tasks(self, request):
                user = request.user  # Authenticated user
                ...
    """
    # Import here to avoid circular imports
    from django_matt.auth.jwt import (
        ExpiredSignatureError,
        InvalidTokenError,
        get_token_from_request,
        get_user_from_token,
        verify_access_token,
    )

    @wraps(func)
    async def async_wrapper(self_or_request, *args, **kwargs):
        request = get_request(self_or_request, args, kwargs)

        if request is None:
            return JsonResponse(
                {"detail": "Request not found", "code": "internal_error"},
                status=500,
            )

        token = get_token_from_request(request)

        if token is None:
            return JsonResponse(
                {"detail": "Authentication required", "code": "token_missing"},
                status=401,
            )

        try:
            payload = verify_access_token(token)
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

        user = get_user_from_token(token)
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

        if inspect.iscoroutinefunction(func):
            return await func(self_or_request, *args, **kwargs)
        return func(self_or_request, *args, **kwargs)

    @wraps(func)
    def sync_wrapper(self_or_request, *args, **kwargs):
        from django_matt.auth.jwt import (
            ExpiredSignatureError,
            InvalidTokenError,
            get_token_from_request,
            get_user_from_token,
            verify_access_token,
        )

        request = get_request(self_or_request, args, kwargs)

        if request is None:
            return JsonResponse(
                {"detail": "Request not found", "code": "internal_error"},
                status=500,
            )

        token = get_token_from_request(request)

        if token is None:
            return JsonResponse(
                {"detail": "Authentication required", "code": "token_missing"},
                status=401,
            )

        try:
            payload = verify_access_token(token)
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

        user = get_user_from_token(token)
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

        return func(self_or_request, *args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    return sync_wrapper  # type: ignore


def jwt_optional(func: F) -> F:
    """
    Decorator that optionally authenticates with JWT.

    If a valid token is present, attaches the user to the request.
    If no token or invalid token, proceeds without user.

    Example:
        @get("public")
        @jwt_optional
        async def public_endpoint(self, request):
            if request.user.is_authenticated:
                # Personalized response
                ...
            else:
                # Anonymous response
                ...
    """

    @wraps(func)
    async def async_wrapper(self_or_request, *args, **kwargs):
        from django_matt.auth.jwt import (
            ExpiredSignatureError,
            InvalidTokenError,
            get_token_from_request,
            get_user_from_token,
            verify_access_token,
        )

        request = get_request(self_or_request, args, kwargs)

        if request is not None:
            token = get_token_from_request(request)

            if token:
                try:
                    payload = verify_access_token(token)
                    user = get_user_from_token(token)
                    if user and user.is_active:
                        request.user = user
                        request.token_payload = payload
                except (InvalidTokenError, ExpiredSignatureError):
                    pass

        if inspect.iscoroutinefunction(func):
            return await func(self_or_request, *args, **kwargs)
        return func(self_or_request, *args, **kwargs)

    @wraps(func)
    def sync_wrapper(self_or_request, *args, **kwargs):
        from django_matt.auth.jwt import (
            ExpiredSignatureError,
            InvalidTokenError,
            get_token_from_request,
            get_user_from_token,
            verify_access_token,
        )

        request = get_request(self_or_request, args, kwargs)

        if request is not None:
            token = get_token_from_request(request)

            if token:
                try:
                    payload = verify_access_token(token)
                    user = get_user_from_token(token)
                    if user and user.is_active:
                        request.user = user
                        request.token_payload = payload
                except (InvalidTokenError, ExpiredSignatureError):
                    pass

        return func(self_or_request, *args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    return sync_wrapper  # type: ignore


def requires_auth(func: F) -> F:
    """Alias for jwt_required."""
    return jwt_required(func)
