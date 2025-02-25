import os

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from django_matt.core.errors import ErrorHandler, ErrorMiddleware
from django_matt.dev.hot_reload import LiveReloadMiddleware


class DjangoMattMiddleware(MiddlewareMixin):
    """
    Main middleware for Django Matt.

    This middleware integrates all Django Matt features, including:
    - Error handling with detailed error messages
    - Hot reloading during development
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.error_middleware = ErrorMiddleware(get_response)

        # Only use LiveReloadMiddleware in debug mode
        if os.environ.get("DJANGO_DEBUG", "False").lower() == "true":
            self.live_reload_middleware = LiveReloadMiddleware(get_response)
        else:
            self.live_reload_middleware = None

    def __call__(self, request):
        response = self.get_response(request)

        # Apply live reload middleware in debug mode
        if self.live_reload_middleware:
            response = self.live_reload_middleware(request)

        return response

    def process_exception(self, request, exception):
        """Process exceptions using the error middleware."""
        return self.error_middleware.process_exception(request, exception)


class APIExceptionMiddleware:
    """
    Middleware for handling API exceptions.

    This middleware catches exceptions in API views and returns
    formatted JSON responses with appropriate status codes.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.error_handler = ErrorHandler(debug=os.environ.get("DJANGO_DEBUG", "False").lower() == "true")

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        """Process an exception and return a formatted JSON response."""
        # Only handle exceptions for API requests
        if not request.path.startswith("/api/"):
            return None

        error_detail = self.error_handler.capture_exception(exception, request)

        # Determine if we should include debug information
        include_traceback = self.error_handler.debug
        include_snippet = self.error_handler.debug

        # Return a JSON response with error details
        return error_detail.to_response(include_traceback=include_traceback, include_snippet=include_snippet)


class JSONResponseMiddleware:
    """
    Middleware for automatically converting dictionaries to JSON responses.

    This middleware converts dictionary return values from views to
    JsonResponse objects, making it easier to return JSON from views.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # If the response is a dictionary, convert it to a JsonResponse
        if isinstance(response, dict):
            return JsonResponse(response, safe=False)

        return response
