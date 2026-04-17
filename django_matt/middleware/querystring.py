"""
Middleware that parses the URL query string via Rust (when available)
and caches the result on ``request._parsed_qs``.

This makes the structured parse result available to **all** consumers —
filter backends, ordering backends, pagination classes, controllers,
and custom views — without requiring each one to call a helper method.

When Rust extensions are not installed the middleware is a no-op and
downstream code falls back to reading ``request.GET`` as usual.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from django_matt._accel import HAS_RUST, parse_query_string_rust


class QueryStringParserMiddleware:
    """
    Parse the raw query string once with the Rust accelerator and attach
    the structured result to ``request._parsed_qs``.

    Add to ``MIDDLEWARE`` **before** any middleware or view that reads
    filter / ordering / pagination parameters::

        MIDDLEWARE = [
            ...
            "django_matt.middleware.querystring.QueryStringParserMiddleware",
            ...
        ]

    The parsed dict contains:

    - ``fields``     – list of field names from ``?fields=id,name``
    - ``filters``    – dict from ``?filter[status]=active``
    - ``sort``       – list of ``(field, ascending)`` tuples
    - ``pagination`` – dict with ``page``, ``page_size``, ``limit``, ``offset``, ``cursor``
    - ``extras``     – dict of remaining key=value pairs (Django ORM lookups)
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._enabled = HAS_RUST and parse_query_string_rust is not None

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if self._enabled:
            qs = request.META.get("QUERY_STRING", "")
            if qs:
                request._parsed_qs = parse_query_string_rust(qs)  # type: ignore[attr-defined]
        return self.get_response(request)
