"""
Content negotiator for determining request/response formats.

The negotiator determines the best format based on:
1. Query parameter (e.g., ?format=xml)
2. URL suffix (e.g., /users.xml)
3. Accept header (e.g., Accept: application/xml)
4. Default format
"""

import re
from dataclasses import dataclass
from typing import Any

from django.http import HttpRequest, HttpResponse

from django_matt.negotiation.config import FormatType, get_negotiation_config
from django_matt.negotiation.parsers import (
    BaseParser,
    get_parser_for_media_type,
    parse_request_body,
)
from django_matt.negotiation.renderers import (
    MEDIA_TYPE_MAP,
    RENDERERS,
    BaseRenderer,
    get_renderer,
)


@dataclass
class NegotiatedFormat:
    """Result of content negotiation."""

    format: FormatType
    renderer: BaseRenderer
    media_type: str
    quality: float = 1.0


class NotAcceptable(Exception):
    """Raised when no acceptable format is found."""

    def __init__(self, requested: str, available: list[str]):
        self.requested = requested
        self.available = available
        super().__init__(
            f"Cannot satisfy Accept header '{requested}'. Available formats: {', '.join(available)}"
        )


class ContentNegotiator:
    """
    Determines the best content format for requests and responses.

    Usage:
        negotiator = ContentNegotiator()

        # Determine response format
        negotiated = negotiator.negotiate(request)
        response = negotiated.renderer.to_response(data)

        # Or use convenience method
        response = negotiator.render(request, data)
    """

    def __init__(self):
        self.config = get_negotiation_config()

    def negotiate(self, request: HttpRequest) -> NegotiatedFormat:
        """
        Negotiate the best response format for the request.

        Priority:
        1. Query parameter (?format=xml)
        2. URL suffix (.xml)
        3. Accept header
        4. Default format
        """
        # 1. Check query parameter
        format_param = request.GET.get(self.config.format_query_param)
        if format_param:
            format_name = self._resolve_format(format_param)
            if format_name and format_name in self.config.formats:
                return self._create_negotiated(format_name)

        # 2. Check URL suffix
        path = request.path_info
        suffix_match = re.search(r"\.(\w+)$", path)
        if suffix_match:
            suffix = suffix_match.group(1).lower()
            format_name = self._resolve_format(suffix)
            if format_name and format_name in self.config.formats:
                return self._create_negotiated(format_name)

        # 3. Parse Accept header
        accept_header = request.META.get("HTTP_ACCEPT", "*/*")
        negotiated = self._negotiate_accept(accept_header)
        if negotiated:
            return negotiated

        # 4. Strict mode - return 406 if no match
        if self.config.strict_accept and accept_header != "*/*":
            raise NotAcceptable(accept_header, self.config.formats)

        # 5. Fall back to default
        return self._create_negotiated(self.config.default_format)

    def _resolve_format(self, format_str: str) -> FormatType | None:
        """Resolve format string to canonical format name."""
        format_str = format_str.lower()

        # Check direct match
        if format_str in RENDERERS:
            return format_str  # type: ignore

        # Check aliases
        return self.config.format_aliases.get(format_str)

    def _negotiate_accept(self, accept_header: str) -> NegotiatedFormat | None:
        """
        Parse Accept header and find best matching format.

        Handles quality values (q=0.9) and wildcards (*/*).
        """
        if not accept_header or accept_header == "*/*":
            return None

        # Parse Accept header into list of (media_type, quality)
        accepts = []
        for part in accept_header.split(","):
            part = part.strip()
            if not part:
                continue

            # Parse quality value
            quality = 1.0
            if ";q=" in part:
                media_part, q_part = part.split(";q=", 1)
                try:
                    quality = float(q_part.split(";")[0])
                except ValueError:
                    quality = 1.0
                part = media_part.strip()
            elif ";" in part:
                part = part.split(";")[0].strip()

            accepts.append((part.lower(), quality))

        # Sort by quality (highest first)
        accepts.sort(key=lambda x: x[1], reverse=True)

        # Find best match
        for media_type, quality in accepts:
            # Handle wildcards
            if media_type == "*/*":
                return self._create_negotiated(self.config.default_format, quality)

            if media_type.endswith("/*"):
                # Type wildcard (e.g., application/*)
                type_prefix = media_type[:-2]
                for fmt in self.config.formats:
                    renderer_class = RENDERERS.get(fmt)
                    if renderer_class and renderer_class.media_type.startswith(type_prefix):
                        return self._create_negotiated(fmt, quality)
            else:
                # Exact match
                format_name = MEDIA_TYPE_MAP.get(media_type)
                if format_name and format_name in self.config.formats:
                    return self._create_negotiated(format_name, quality)

        return None

    def _create_negotiated(
        self,
        format_name: FormatType,
        quality: float = 1.0,
    ) -> NegotiatedFormat:
        """Create a NegotiatedFormat result."""
        renderer = get_renderer(format_name)
        return NegotiatedFormat(
            format=format_name,
            renderer=renderer,
            media_type=renderer.media_type,
            quality=quality,
        )

    def render(
        self,
        request: HttpRequest,
        data: Any,
        status: int = 200,
        **kwargs,
    ) -> HttpResponse:
        """
        Render data to appropriate format based on request.

        Convenience method that combines negotiation and rendering.
        """
        try:
            negotiated = self.negotiate(request)
            return negotiated.renderer.to_response(data, status=status, **kwargs)
        except NotAcceptable as e:
            # Return 406 Not Acceptable
            return HttpResponse(
                content=f'{{"error": "{e}"}}',
                status=406,
                content_type="application/json",
            )

    def render_format(
        self,
        data: Any,
        format_name: FormatType,
        status: int = 200,
        **kwargs,
    ) -> HttpResponse:
        """
        Render data to a specific format.

        Bypasses negotiation - useful when format is predetermined.
        """
        renderer = get_renderer(format_name)
        return renderer.to_response(data, status=status, **kwargs)

    def parse(self, request: HttpRequest) -> Any:
        """
        Parse request body based on Content-Type.

        Returns parsed data or None.
        """
        return parse_request_body(request)

    def get_parser(self, request: HttpRequest) -> BaseParser:
        """Get the appropriate parser for the request Content-Type."""
        content_type = request.content_type or "application/json"
        return get_parser_for_media_type(content_type)


# Global negotiator instance
_negotiator: ContentNegotiator | None = None


def get_negotiator() -> ContentNegotiator:
    """Get the global ContentNegotiator instance."""
    global _negotiator
    if _negotiator is None:
        _negotiator = ContentNegotiator()
    return _negotiator


def negotiate(request: HttpRequest) -> NegotiatedFormat:
    """Negotiate content format for a request."""
    return get_negotiator().negotiate(request)


def render(
    request: HttpRequest,
    data: Any,
    status: int = 200,
    **kwargs,
) -> HttpResponse:
    """Render data based on content negotiation."""
    return get_negotiator().render(request, data, status=status, **kwargs)


def render_format(
    data: Any,
    format_name: FormatType,
    status: int = 200,
    **kwargs,
) -> HttpResponse:
    """Render data to a specific format."""
    return get_negotiator().render_format(data, format_name, status=status, **kwargs)


def parse(request: HttpRequest) -> Any:
    """Parse request body based on Content-Type."""
    return get_negotiator().parse(request)
