"""
Base utilities for auth decorators.
"""

from django.http import HttpRequest


def get_request(self_or_request, args, kwargs) -> HttpRequest | None:
    """Extract request from various call patterns."""
    if hasattr(self_or_request, "request"):
        return self_or_request.request
    elif isinstance(self_or_request, HttpRequest):
        return self_or_request
    elif args and isinstance(args[0], HttpRequest):
        return args[0]
    return kwargs.get("request")
