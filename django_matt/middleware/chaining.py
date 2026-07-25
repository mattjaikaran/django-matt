"""Auto-chaining middleware — wraps the internal middleware stack."""

import os

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from django_matt.core.errors import ErrorHandler, ErrorMiddleware


class DjangoMattMiddleware(MiddlewareMixin):
    """
    Main middleware for Django Matt.

    This middleware integrates all Django Matt features, including:
    - Error handling with detailed error messages
    - Hot reloading during development
    - Auto-chained internal middleware stack (security, CORS, request ID, etc.)

    Configure the internal stack via settings.DJANGO_MATT["MIDDLEWARE_STACK"]:
    - "production" → SecurityHeaders + RequestID + CORS + Logging + Timing
    - "development" → RequestID + CORS + Logging + Timing
    - list of classes → custom stack
    - None → no internal stack (default, backwards-compatible)
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.error_middleware = ErrorMiddleware(get_response)

        # Only use LiveReloadMiddleware in debug mode
        if os.environ.get("DJANGO_DEBUG", "False").lower() == "true":
            from django_matt.dev.hot_reload import LiveReloadMiddleware

            self.live_reload_middleware = LiveReloadMiddleware(get_response)
        else:
            self.live_reload_middleware = None

        # Build internal middleware chain from settings (cached at init)
        self._inner_chain = self._build_inner_chain()

    def _build_inner_chain(self):
        """Build the internal middleware chain at init time."""
        from django.conf import settings

        matt_config = getattr(settings, "DJANGO_MATT", {})
        stack_config = matt_config.get("MIDDLEWARE_STACK")

        if stack_config is None:
            return None

        # Resolve named stacks
        if isinstance(stack_config, str):
            from django_matt.middleware import DEVELOPMENT_STACK, PRODUCTION_STACK

            stacks = {
                "production": PRODUCTION_STACK,
                "development": DEVELOPMENT_STACK,
            }
            stack_classes = stacks.get(stack_config, [])
        else:
            stack_classes = list(stack_config)

        if not stack_classes:
            return None

        # Filter by module registry if SLIM_REGISTRY is set
        registry = matt_config.get("SLIM_REGISTRY")
        if registry is not None:
            from django_matt.middleware.cors import CORSMiddleware
            from django_matt.middleware.logging import RequestLoggingMiddleware
            from django_matt.middleware.request_id import RequestIDMiddleware
            from django_matt.middleware.security import SecurityHeadersMiddleware
            from django_matt.middleware.timing import TimingMiddleware

            _cls_to_module = {
                SecurityHeadersMiddleware: "security",
                RequestIDMiddleware: "request_id",
                CORSMiddleware: "cors",
                RequestLoggingMiddleware: "logging",
                TimingMiddleware: "timing",
            }
            stack_classes = [
                cls
                for cls in stack_classes
                if _cls_to_module.get(cls) is None or registry.is_active(_cls_to_module[cls])
            ]

        if not stack_classes:
            return None

        # Chain: last middleware wraps get_response, first wraps last, etc.
        chain = self.get_response
        for middleware_cls in reversed(stack_classes):
            chain = middleware_cls(chain)
        return chain

    def __call__(self, request):
        # If we have an internal chain, use it instead of plain get_response
        if self._inner_chain is not None:
            response = self._inner_chain(request)
        else:
            response = self.get_response(request)

        return response

    def process_exception(self, request, exception):
        """Process exceptions using the error middleware."""
        return self.error_middleware.process_exception(request, exception)


class APIExceptionMiddleware:
    """
    Middleware for handling API exceptions.

    Catches exceptions in API views and returns formatted JSON responses
    for any request path starting with /api/.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.error_handler = ErrorHandler(
            debug=os.environ.get("DJANGO_DEBUG", "False").lower() == "true"
        )

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            if not request.path.startswith("/api/"):
                raise
            return self._handle_exception(request, exc)

    def _handle_exception(self, request, exception):
        """Capture and format an API exception as JSON."""
        error_detail = self.error_handler.capture_exception(exception, request)
        return error_detail.to_response(
            include_traceback=self.error_handler.debug,
            include_snippet=self.error_handler.debug,
        )


class JSONResponseMiddleware:
    """
    Middleware for automatically converting dictionaries to JSON responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if isinstance(response, dict):
            return JsonResponse(response, safe=False)
        return response
