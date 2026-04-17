"""Predictive prefetch middleware — observe and optimize automatically."""

from __future__ import annotations

import logging
from typing import Any

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("django_matt.prefetch")

# Global learner instance (shared across requests)
_learner = None


def get_learner():
    """Get or create the global AccessPatternLearner."""
    global _learner
    if _learner is None:
        from django_matt.prefetch.learner import AccessPatternLearner

        try:
            from django_matt.conf import get_matt_setting
            threshold = get_matt_setting("PREFETCH_THRESHOLD", 0.3)
            max_prefetches = get_matt_setting("PREFETCH_MAX_RELATIONS", 5)
        except Exception:
            threshold = 0.3
            max_prefetches = 5

        _learner = AccessPatternLearner(
            threshold=threshold, max_prefetches=max_prefetches
        )
    return _learner


class PredictivePrefetchMiddleware:
    """ASGI middleware that observes DB access patterns per request.

    In observation mode, tracks which model relations are accessed.
    Over time, builds a statistical model of access patterns that
    can be used to auto-optimize querysets.

    Add to MIDDLEWARE::

        MIDDLEWARE = [
            "django_matt.prefetch.middleware.PredictivePrefetchMiddleware",
            ...
        ]
    """

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        # Attach learner to request for use in views
        request._prefetch_learner = get_learner()  # type: ignore[attr-defined]

        response = await self.get_response(request)
        return response
