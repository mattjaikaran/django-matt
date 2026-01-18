"""
HTMX middleware.

Provides middleware for automatic HTMX request detection and
response handling.
"""

from typing import Callable, Optional
from django.http import HttpRequest, HttpResponse

from django_matt.htmx.request import HtmxDetails


class HtmxMiddleware:
    """
    Middleware that adds HTMX details to requests.

    Adds `request.htmx` attribute with HtmxDetails instance
    (or None for non-HTMX requests).

    Also handles:
    - Adding Vary: HX-Request header for proper caching
    - Processing 286 status for stopping polls

    Usage:
        # settings.py
        MIDDLEWARE = [
            ...
            'django_matt.htmx.HtmxMiddleware',
        ]

        # views.py
        def my_view(request):
            if request.htmx:
                return render(request, "partial.html", context)
            return render(request, "full.html", context)
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Add htmx details to request
        request.htmx = HtmxDetails.from_request(request)

        # Process request
        response = self.get_response(request)

        # Add Vary header for HTMX requests
        if request.htmx:
            self._add_vary_header(response)

        return response

    def _add_vary_header(self, response: HttpResponse) -> None:
        """Add HX-Request to Vary header for proper caching."""
        existing_vary = response.get("Vary", "")
        if "HX-Request" not in existing_vary:
            if existing_vary:
                response["Vary"] = f"{existing_vary}, HX-Request"
            else:
                response["Vary"] = "HX-Request"


class AsyncHtmxMiddleware:
    """
    Async version of HtmxMiddleware.

    Usage:
        # settings.py
        MIDDLEWARE = [
            ...
            'django_matt.htmx.AsyncHtmxMiddleware',
        ]
    """

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        # Add htmx details to request
        request.htmx = HtmxDetails.from_request(request)

        # Process request
        response = await self.get_response(request)

        # Add Vary header for HTMX requests
        if request.htmx:
            existing_vary = response.get("Vary", "")
            if "HX-Request" not in existing_vary:
                if existing_vary:
                    response["Vary"] = f"{existing_vary}, HX-Request"
                else:
                    response["Vary"] = "HX-Request"

        return response


class HtmxTemplateContextMiddleware:
    """
    Middleware that adds HTMX utilities to template context.

    Makes `htmx` variable available in all templates automatically.

    Usage:
        # settings.py
        MIDDLEWARE = [
            ...
            'django_matt.htmx.HtmxTemplateContextMiddleware',
        ]

        # template.html
        {% if htmx %}
            <!-- This is an HTMX request -->
        {% endif %}

        {% if htmx.boosted %}
            <!-- This is a boosted request -->
        {% endif %}
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Ensure htmx is on request
        if not hasattr(request, "htmx"):
            request.htmx = HtmxDetails.from_request(request)

        return self.get_response(request)


def htmx_context_processor(request: HttpRequest) -> dict:
    """
    Context processor that adds HTMX details to template context.

    Alternative to middleware - add to TEMPLATES context_processors.

    Usage:
        # settings.py
        TEMPLATES = [{
            ...
            'OPTIONS': {
                'context_processors': [
                    ...
                    'django_matt.htmx.htmx_context_processor',
                ],
            },
        }]

        # template.html
        {% if htmx %}
            <div>HTMX request from {{ htmx.trigger }}</div>
        {% endif %}
    """
    htmx = getattr(request, "htmx", None)
    if htmx is None:
        htmx = HtmxDetails.from_request(request)
    return {"htmx": htmx}


__all__ = [
    "HtmxMiddleware",
    "AsyncHtmxMiddleware",
    "HtmxTemplateContextMiddleware",
    "htmx_context_processor",
]
