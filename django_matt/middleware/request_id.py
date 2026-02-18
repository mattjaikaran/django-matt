"""Request ID middleware — UUID per request via contextvar."""

import uuid
from contextvars import ContextVar

from django.conf import settings

# Module-level contextvar — async-safe, no thread-local overhead
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request ID from the contextvar."""
    return request_id_var.get()


class RequestIDMiddleware:
    """
    Assigns a unique ID to every request.

    - Reads incoming X-Request-ID header (trusts proxy if configured)
    - Falls back to generating a UUID4
    - Sets the contextvar so downstream code can access it
    - Adds X-Request-ID to the response
    """

    def __init__(self, get_response):
        self.get_response = get_response
        matt_config = getattr(settings, "DJANGO_MATT", {})
        self.header_name = matt_config.get("REQUEST_ID_HEADER", "X-Request-ID")
        self.trust_proxy = matt_config.get("TRUST_PROXY_REQUEST_ID", True)

    def __call__(self, request):
        # Read from upstream proxy or generate new
        rid = None
        if self.trust_proxy:
            rid = request.META.get(f"HTTP_{self.header_name.upper().replace('-', '_')}")
        if not rid:
            rid = uuid.uuid4().hex

        # Set on contextvar and request
        token = request_id_var.set(rid)
        request.request_id = rid

        try:
            response = self.get_response(request)
            response[self.header_name] = rid
            return response
        finally:
            request_id_var.reset(token)
