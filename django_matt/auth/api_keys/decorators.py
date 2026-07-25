# file-length-max: 500
"""
API Key authentication decorators.
"""

import inspect
from collections.abc import Callable
from functools import wraps

from django.http import HttpRequest, JsonResponse

from .utils import api_key_config, get_api_key_from_request, get_client_ip


def _get_request(*args, **kwargs) -> HttpRequest | None:
    """Extract request from function arguments."""
    # Check first positional arg
    if args:
        first_arg = args[0]
        if isinstance(first_arg, HttpRequest):
            return first_arg
        # Check if it's a class method (self, request, ...)
        if len(args) > 1 and isinstance(args[1], HttpRequest):
            return args[1]

    # Check kwargs
    return kwargs.get("request")


def api_key_required[F: Callable](func: F) -> F:
    """
    Require a valid API key for the endpoint.

    Extracts the API key from request headers or query params,
    validates it, and attaches the user and api_key to the request.

    Example:
        @api.get("/data")
        @api_key_required
        async def get_data(request):
            # request.user is set to the API key owner
            # request.api_key is the APIKey instance
            return {"user": request.user.email}
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        request = _get_request(*args, **kwargs)
        if request is None:
            return JsonResponse(
                {"detail": "Request not found", "code": "internal_error"},
                status=500,
            )

        # Get API key from request
        raw_key = get_api_key_from_request(request)
        if not raw_key:
            return JsonResponse(
                {"detail": "API key required", "code": "api_key_required"},
                status=401,
            )

        # Validate the key
        # aget_valid → aget_by_key already does select_related("user")
        from .models import APIKey

        api_key = await APIKey.objects.aget_valid(raw_key)

        if api_key is None:
            return JsonResponse(
                {"detail": "Invalid API key", "code": "invalid_api_key"},
                status=401,
            )

        if not api_key.is_valid:
            return JsonResponse(
                {"detail": "API key expired or inactive", "code": "api_key_inactive"},
                status=401,
            )

        # Check IP restrictions
        if api_key.allowed_ips:
            client_ip = get_client_ip(request)
            if not api_key.is_ip_allowed(client_ip):
                return JsonResponse(
                    {"detail": "IP address not allowed", "code": "ip_not_allowed"},
                    status=403,
                )

        # Attach to request
        request.user = api_key.user
        request.api_key = api_key

        # Record usage if tracking is enabled
        if api_key_config.track_usage:
            await api_key.arecord_usage()

        # Call the wrapped function
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        request = _get_request(*args, **kwargs)
        if request is None:
            return JsonResponse(
                {"detail": "Request not found", "code": "internal_error"},
                status=500,
            )

        raw_key = get_api_key_from_request(request)
        if not raw_key:
            return JsonResponse(
                {"detail": "API key required", "code": "api_key_required"},
                status=401,
            )

        from .models import APIKey

        api_key = APIKey.objects.get_valid(raw_key)
        if api_key is None:
            return JsonResponse(
                {"detail": "Invalid API key", "code": "invalid_api_key"},
                status=401,
            )

        if not api_key.is_valid:
            return JsonResponse(
                {"detail": "API key expired or inactive", "code": "api_key_inactive"},
                status=401,
            )

        if api_key.allowed_ips:
            client_ip = get_client_ip(request)
            if not api_key.is_ip_allowed(client_ip):
                return JsonResponse(
                    {"detail": "IP address not allowed", "code": "ip_not_allowed"},
                    status=403,
                )

        request.user = api_key.user
        request.api_key = api_key

        if api_key_config.track_usage:
            api_key.record_usage()

        return func(*args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    return sync_wrapper  # type: ignore


def api_key_optional[F: Callable](func: F) -> F:
    """
    Optionally authenticate with API key.

    If a valid API key is provided, attaches user and api_key to request.
    If no key or invalid key, continues without authentication.

    Example:
        @api.get("/public-data")
        @api_key_optional
        async def get_public_data(request):
            if hasattr(request, 'api_key'):
                # Authenticated request - return more data
                return {"data": "full", "user": request.user.email}
            # Anonymous request
            return {"data": "limited"}
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        request = _get_request(*args, **kwargs)
        if request is None:
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        raw_key = get_api_key_from_request(request)
        if raw_key:
            from .models import APIKey

            api_key = await APIKey.objects.aget_valid(raw_key)
            if api_key and api_key.is_valid:
                if not api_key.allowed_ips or api_key.is_ip_allowed(get_client_ip(request)):
                    request.user = api_key.user
                    request.api_key = api_key
                    if api_key_config.track_usage:
                        await api_key.arecord_usage()

        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        request = _get_request(*args, **kwargs)
        if request is not None:
            raw_key = get_api_key_from_request(request)
            if raw_key:
                from .models import APIKey

                api_key = APIKey.objects.get_valid(raw_key)
                if api_key and api_key.is_valid:
                    if not api_key.allowed_ips or api_key.is_ip_allowed(get_client_ip(request)):
                        request.user = api_key.user
                        request.api_key = api_key
                        if api_key_config.track_usage:
                            api_key.record_usage()

        return func(*args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    return sync_wrapper  # type: ignore


def requires_scope(*scopes: str):
    """
    Require specific scopes for the endpoint.

    Must be used after @api_key_required.

    Example:
        @api.post("/posts")
        @api_key_required
        @requires_scope("write:posts")
        async def create_post(request, data: PostSchema):
            ...

        # Multiple scopes (any of them)
        @api.delete("/posts/{id}")
        @api_key_required
        @requires_scope("write:posts", "delete:posts")
        async def delete_post(request, id: int):
            ...
    """

    def decorator[F: Callable](func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            request = _get_request(*args, **kwargs)
            if request is None or not hasattr(request, "api_key"):
                return JsonResponse(
                    {"detail": "API key required", "code": "api_key_required"},
                    status=401,
                )

            api_key = request.api_key

            # Check if key has any of the required scopes
            has_scope = any(api_key.has_scope(scope) for scope in scopes)
            if not has_scope:
                return JsonResponse(
                    {
                        "detail": f"Missing required scope: {', '.join(scopes)}",
                        "code": "insufficient_scope",
                    },
                    status=403,
                )

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            request = _get_request(*args, **kwargs)
            if request is None or not hasattr(request, "api_key"):
                return JsonResponse(
                    {"detail": "API key required", "code": "api_key_required"},
                    status=401,
                )

            api_key = request.api_key
            has_scope = any(api_key.has_scope(scope) for scope in scopes)
            if not has_scope:
                return JsonResponse(
                    {
                        "detail": f"Missing required scope: {', '.join(scopes)}",
                        "code": "insufficient_scope",
                    },
                    status=403,
                )

            return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def requires_live_key[F: Callable](func: F) -> F:
    """
    Require a live (non-test) API key.

    Must be used after @api_key_required.

    Example:
        @api.post("/payments")
        @api_key_required
        @requires_live_key
        async def create_payment(request, data: PaymentSchema):
            # Only live keys can process real payments
            ...
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        request = _get_request(*args, **kwargs)
        if request is None or not hasattr(request, "api_key"):
            return JsonResponse(
                {"detail": "API key required", "code": "api_key_required"},
                status=401,
            )

        if request.api_key.is_test:
            return JsonResponse(
                {
                    "detail": "Live API key required for this endpoint",
                    "code": "live_key_required",
                },
                status=403,
            )

        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        request = _get_request(*args, **kwargs)
        if request is None or not hasattr(request, "api_key"):
            return JsonResponse(
                {"detail": "API key required", "code": "api_key_required"},
                status=401,
            )

        if request.api_key.is_test:
            return JsonResponse(
                {
                    "detail": "Live API key required for this endpoint",
                    "code": "live_key_required",
                },
                status=403,
            )

        return func(*args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    return sync_wrapper  # type: ignore


def requires_plan(*plans: str):
    """
    Require specific plan tiers for the endpoint.

    Must be used after @api_key_required.

    Example:
        @api.get("/premium-feature")
        @api_key_required
        @requires_plan("pro", "enterprise")
        async def premium_feature(request):
            ...
    """

    def decorator[F: Callable](func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            request = _get_request(*args, **kwargs)
            if request is None or not hasattr(request, "api_key"):
                return JsonResponse(
                    {"detail": "API key required", "code": "api_key_required"},
                    status=401,
                )

            if request.api_key.plan not in plans:
                return JsonResponse(
                    {
                        "detail": f"This feature requires plan: {', '.join(plans)}",
                        "code": "plan_required",
                        "required_plans": list(plans),
                        "current_plan": request.api_key.plan,
                    },
                    status=403,
                )

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            request = _get_request(*args, **kwargs)
            if request is None or not hasattr(request, "api_key"):
                return JsonResponse(
                    {"detail": "API key required", "code": "api_key_required"},
                    status=401,
                )

            if request.api_key.plan not in plans:
                return JsonResponse(
                    {
                        "detail": f"This feature requires plan: {', '.join(plans)}",
                        "code": "plan_required",
                        "required_plans": list(plans),
                        "current_plan": request.api_key.plan,
                    },
                    status=403,
                )

            return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator
