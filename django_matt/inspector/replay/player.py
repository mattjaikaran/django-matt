"""Request replayer — replay recorded traces against current code.

Compares DB queries, response shape, and timing to detect regressions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.test import RequestFactory

from django_matt.inspector.replay.recorder import QueryRecord, RequestTrace


@dataclass
class QueryDiff:
    """Difference between original and replayed queries."""

    original_count: int = 0
    replayed_count: int = 0
    new_queries: list[str] = field(default_factory=list)
    missing_queries: list[str] = field(default_factory=list)
    changed_queries: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ResponseDiff:
    """Difference between original and replayed response."""

    status_changed: bool = False
    original_status: int = 0
    replayed_status: int = 0
    body_changed: bool = False
    headers_changed: list[str] = field(default_factory=list)


@dataclass
class ReplayResult:
    """Result of replaying a request trace."""

    trace_id: str
    success: bool = True
    error: str = ""

    # Response comparison
    response_diff: ResponseDiff = field(default_factory=ResponseDiff)

    # Query comparison
    query_diff: QueryDiff = field(default_factory=QueryDiff)

    # Timing
    original_total_ms: float = 0.0
    replayed_total_ms: float = 0.0

    # Replayed queries
    replayed_queries: list[QueryRecord] = field(default_factory=list)


class RequestReplayer:
    """Replay a recorded request trace against current code.

    Compares:
    - DB queries (same queries? different? new N+1?)
    - Response (same status? same shape? new errors?)
    - Timing (faster? slower?)

    Usage::

        replayer = RequestReplayer()
        result = await replayer.replay(trace)
        if not result.success:
            print(f"Regression detected: {result.error}")
    """

    def __init__(self, mock_externals: bool = True) -> None:
        self.mock_externals = mock_externals
        self._factory = RequestFactory()

    async def replay(self, trace: RequestTrace) -> ReplayResult:
        """Replay a request trace and compare results."""
        import time

        from django.db import connection
        from django.urls import resolve

        from django_matt.inspector.replay.recorder import _QueryTracker

        result = ReplayResult(
            trace_id=trace.trace_id,
            original_total_ms=trace.timing.total_ms,
        )

        try:
            # Build the request
            request = self._build_request(trace)

            # Resolve URL
            match = resolve(trace.path)
            view = match.func
            kwargs = match.kwargs

            # Track queries during replay
            tracker = _QueryTracker()
            start = time.perf_counter()

            with connection.execute_wrapper(tracker):
                import asyncio
                import inspect

                if inspect.iscoroutinefunction(view):
                    response = await view(request, **kwargs)
                else:
                    response = view(request, **kwargs)

            replayed_ms = (time.perf_counter() - start) * 1000
            result.replayed_total_ms = round(replayed_ms, 3)
            result.replayed_queries = tracker.queries

            # Compare response
            result.response_diff = self._diff_response(trace, response)

            # Compare queries
            result.query_diff = self._diff_queries(
                trace.queries, tracker.queries
            )

            result.success = (
                not result.response_diff.status_changed
                and not result.query_diff.new_queries
            )

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result

    def _build_request(self, trace: RequestTrace) -> Any:
        """Reconstruct a Django request from a trace."""
        method_lower = trace.method.lower()
        factory_method = getattr(self._factory, method_lower, self._factory.get)

        path = trace.path
        if trace.query_string:
            path = f"{path}?{trace.query_string}"

        kwargs: dict[str, Any] = {}
        if trace.body and method_lower in ("post", "put", "patch"):
            kwargs["data"] = trace.body
            content_type = trace.headers.get("content-type", "application/json")
            kwargs["content_type"] = content_type

        request = factory_method(path, **kwargs)

        # Apply headers
        for key, value in trace.headers.items():
            header_key = f"HTTP_{key.upper().replace('-', '_')}"
            request.META[header_key] = value

        return request

    @staticmethod
    def _diff_response(trace: RequestTrace, response: Any) -> ResponseDiff:
        """Compare original and replayed response."""
        diff = ResponseDiff(
            original_status=trace.status_code,
            replayed_status=response.status_code,
            status_changed=trace.status_code != response.status_code,
        )

        # Compare body
        replayed_body = getattr(response, "content", b"")
        diff.body_changed = trace.response_body != replayed_body

        # Compare headers
        replayed_headers = {k: v for k, v in response.items()}
        for key in set(trace.response_headers) | set(replayed_headers):
            if trace.response_headers.get(key) != replayed_headers.get(key):
                diff.headers_changed.append(key)

        return diff

    @staticmethod
    def _diff_queries(
        original: list[QueryRecord], replayed: list[QueryRecord]
    ) -> QueryDiff:
        """Compare original and replayed DB queries."""
        import re

        param_re = re.compile(r"(?:'[^']*'|\b\d+\b)")

        def normalize(sql: str) -> str:
            return param_re.sub("?", sql).strip()

        original_patterns = [normalize(q.sql) for q in original]
        replayed_patterns = [normalize(q.sql) for q in replayed]

        original_set = set(original_patterns)
        replayed_set = set(replayed_patterns)

        return QueryDiff(
            original_count=len(original),
            replayed_count=len(replayed),
            new_queries=sorted(replayed_set - original_set),
            missing_queries=sorted(original_set - replayed_set),
        )
