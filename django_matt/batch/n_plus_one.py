"""Runtime N+1 query detection middleware.

Tracks query patterns during a request and warns when the same parameterized
query is repeated more than ``threshold`` times — a strong signal for N+1.

In development:
  - Logs a warning with the offending pattern and count
  - Injects ``X-NPlusOne-Warning`` response headers
  - Optionally raises ``NPlusOneWarning``

In production:
  - Logs a warning (no headers, no exceptions)

Usage::

    # settings.py
    MIDDLEWARE = [
        "django_matt.batch.n_plus_one.NPlusOneMiddleware",
        ...
    ]

    # Or configure
    DJANGO_MATT = {
        "N_PLUS_ONE_THRESHOLD": 5,
    }
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("django_matt.batch.n_plus_one")

# Regex to normalize query parameters for pattern matching
_PARAM_RE = re.compile(r"(?:'[^']*'|\b\d+\b)")


class NPlusOneWarning(UserWarning):
    """Raised when N+1 query pattern is detected."""

    def __init__(self, pattern: str, count: int):
        self.pattern = pattern
        self.count = count
        super().__init__(f"N+1 detected: {pattern} executed {count} times")


class QueryPatternTracker:
    """Track SQL query patterns during a request.

    Normalizes queries by replacing literal values with ``?`` placeholders,
    then counts how many times each normalized pattern appears.
    """

    def __init__(self) -> None:
        self._patterns: Counter[str] = Counter()
        self._raw_queries: list[str] = []

    def track(self, execute: Any, sql: str, params: Any, many: bool, context: Any) -> Any:
        """Database execute wrapper — called for every query."""
        normalized = self._normalize(sql)
        self._patterns[normalized] += 1
        self._raw_queries.append(sql)
        return execute(sql, params, many, context)

    def get_duplicates(self, threshold: int = 5) -> list[tuple[str, int]]:
        """Return query patterns that exceeded the threshold.

        Returns list of (pattern, count) tuples sorted by count descending.
        """
        duplicates = [
            (pattern, count)
            for pattern, count in self._patterns.most_common()
            if count >= threshold
        ]
        return duplicates

    @property
    def total_queries(self) -> int:
        return sum(self._patterns.values())

    @property
    def unique_patterns(self) -> int:
        return len(self._patterns)

    @staticmethod
    def _normalize(sql: str) -> str:
        """Normalize SQL by replacing literals with ? placeholders."""
        return _PARAM_RE.sub("?", sql).strip()


class NPlusOneMiddleware:
    """ASGI middleware that detects N+1 query patterns per request.

    Args:
        get_response: The next middleware/view in the chain.
    """

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response
        self._threshold = self._get_threshold()

    @staticmethod
    def _get_threshold() -> int:
        try:
            from django_matt.conf import get_matt_setting
            return get_matt_setting("N_PLUS_ONE_THRESHOLD", 5)
        except Exception:
            return 5

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        from django.db import connection

        tracker = QueryPatternTracker()

        # Wrap all DB queries during this request
        with connection.execute_wrapper(tracker.track):
            response = await self.get_response(request)

        # Check for N+1 patterns
        duplicates = tracker.get_duplicates(threshold=self._threshold)
        if duplicates:
            self._report(request, duplicates, response)

        return response

    def _report(
        self,
        request: HttpRequest,
        duplicates: list[tuple[str, int]],
        response: HttpResponse,
    ) -> None:
        """Log and optionally inject headers for detected N+1 patterns."""
        from django.conf import settings

        is_debug = getattr(settings, "DEBUG", False)

        for pattern, count in duplicates:
            truncated = pattern[:120] + "..." if len(pattern) > 120 else pattern
            logger.warning(
                "N+1 detected on %s %s: %s (x%d)",
                request.method,
                request.path,
                truncated,
                count,
            )

            if is_debug:
                # Inject warning header in debug mode
                header_val = f"{truncated} (x{count})"
                response["X-NPlusOne-Warning"] = header_val

    def __repr__(self) -> str:
        return f"NPlusOneMiddleware(threshold={self._threshold})"
