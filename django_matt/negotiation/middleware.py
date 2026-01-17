"""
Content negotiation middleware.

Automatically handles content negotiation for all API responses.
"""

import json
from typing import Any, Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from django_matt.negotiation.negotiator import (
    ContentNegotiator,
    NotAcceptable,
    NegotiatedFormat,
)
from django_matt.negotiation.parsers import ParseError


class ContentNegotiationMiddleware:
    """
    Middleware that handles content negotiation for API responses.

    Automatically converts JsonResponse and dict responses to the
    format requested by the client.

    Usage:
        # settings.py
        MIDDLEWARE = [
            ...
            'django_matt.negotiation.ContentNegotiationMiddleware',
            ...
        ]

    Configuration:
        DJANGO_MATT_NEGOTIATION = {
            "DEFAULT_FORMAT": "json",
            "FORMAT_QUERY_PARAM": "format",
            "FORMATS": ["json", "xml", "csv", "yaml"],
        }
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        self.negotiator = ContentNegotiator()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Store negotiated format on request for later use
        try:
            request.negotiated_format = self.negotiator.negotiate(request)
        except NotAcceptable:
            request.negotiated_format = None

        # Parse request body if needed
        if request.method in ("POST", "PUT", "PATCH") and request.body:
            try:
                request.parsed_data = self.negotiator.parse(request)
            except ParseError:
                request.parsed_data = None

        response = self.get_response(request)

        # Transform response if needed
        return self._transform_response(request, response)

    def _transform_response(
        self,
        request: HttpRequest,
        response: HttpResponse,
    ) -> HttpResponse:
        """Transform response to negotiated format if applicable."""
        negotiated: NegotiatedFormat | None = getattr(request, "negotiated_format", None)

        if not negotiated:
            return response

        # Skip if already the right format or if it's a non-API response
        if negotiated.format == "json" and isinstance(response, JsonResponse):
            return response

        # Skip for certain response types
        if response.status_code in (204, 304):  # No content / Not modified
            return response

        if not self._is_transformable(response):
            return response

        # Extract data from response
        data = self._extract_data(response)
        if data is None:
            return response

        # Re-render in the negotiated format
        return negotiated.renderer.to_response(data, status=response.status_code)

    def _is_transformable(self, response: HttpResponse) -> bool:
        """Check if response can be transformed."""
        content_type = response.get("Content-Type", "")

        # Only transform JSON responses
        if "application/json" in content_type:
            return True

        # Also transform if it's a JsonResponse
        if isinstance(response, JsonResponse):
            return True

        return False

    def _extract_data(self, response: HttpResponse) -> Any | None:
        """Extract data from response for re-rendering."""
        try:
            if isinstance(response, JsonResponse):
                return json.loads(response.content)
            elif response.get("Content-Type", "").startswith("application/json"):
                return json.loads(response.content)
        except (json.JSONDecodeError, ValueError):
            pass
        return None


class AsyncContentNegotiationMiddleware:
    """
    Async version of ContentNegotiationMiddleware.

    Usage:
        # settings.py
        MIDDLEWARE = [
            ...
            'django_matt.negotiation.AsyncContentNegotiationMiddleware',
            ...
        ]
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        self.negotiator = ContentNegotiator()
        self._is_coroutine = None

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        # Store negotiated format on request
        try:
            request.negotiated_format = self.negotiator.negotiate(request)
        except NotAcceptable:
            request.negotiated_format = None

        # Parse request body if needed
        if request.method in ("POST", "PUT", "PATCH") and request.body:
            try:
                request.parsed_data = self.negotiator.parse(request)
            except ParseError:
                request.parsed_data = None

        response = await self.get_response(request)

        # Transform response if needed
        return self._transform_response(request, response)

    def _transform_response(
        self,
        request: HttpRequest,
        response: HttpResponse,
    ) -> HttpResponse:
        """Transform response to negotiated format if applicable."""
        negotiated: NegotiatedFormat | None = getattr(request, "negotiated_format", None)

        if not negotiated:
            return response

        if negotiated.format == "json" and isinstance(response, JsonResponse):
            return response

        if response.status_code in (204, 304):
            return response

        if not self._is_transformable(response):
            return response

        data = self._extract_data(response)
        if data is None:
            return response

        return negotiated.renderer.to_response(data, status=response.status_code)

    def _is_transformable(self, response: HttpResponse) -> bool:
        """Check if response can be transformed."""
        content_type = response.get("Content-Type", "")

        if "application/json" in content_type:
            return True

        if isinstance(response, JsonResponse):
            return True

        return False

    def _extract_data(self, response: HttpResponse) -> Any | None:
        """Extract data from response for re-rendering."""
        try:
            if isinstance(response, JsonResponse):
                return json.loads(response.content)
            elif response.get("Content-Type", "").startswith("application/json"):
                return json.loads(response.content)
        except (json.JSONDecodeError, ValueError):
            pass
        return None
