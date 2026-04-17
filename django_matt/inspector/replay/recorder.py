"""Request recorder — capture full request lifecycle for replay.

Captures request, response, DB queries, timing, and metadata into a
RequestTrace that can be serialized, stored, and replayed later.
"""

from __future__ import annotations

import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

import orjson


@dataclass
class QueryRecord:
    """A single database query captured during a request."""

    sql: str
    params: list[Any] = field(default_factory=list)
    duration_ms: float = 0.0
    stack: str = ""


@dataclass
class TimingRecord:
    """Timing breakdown for request phases."""

    total_ms: float = 0.0
    middleware_ms: float = 0.0
    auth_ms: float = 0.0
    handler_ms: float = 0.0
    serialization_ms: float = 0.0
    db_ms: float = 0.0


@dataclass
class RequestTrace:
    """Complete trace of a request lifecycle."""

    trace_id: str = ""
    timestamp: str = ""

    # Request
    method: str = ""
    path: str = ""
    query_string: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    user_id: str | int | None = None
    auth_type: str = ""

    # Response
    status_code: int = 0
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: bytes = b""

    # DB queries
    queries: list[QueryRecord] = field(default_factory=list)

    # Timing
    timing: TimingRecord = field(default_factory=TimingRecord)

    # Metadata
    django_version: str = ""
    python_version: str = ""
    git_sha: str = ""

    def to_json(self) -> bytes:
        """Serialize to JSON bytes."""
        data = asdict(self)
        # Convert bytes to base64 for JSON
        import base64
        data["body"] = base64.b64encode(self.body).decode("ascii")
        data["response_body"] = base64.b64encode(self.response_body).decode("ascii")
        return orjson.dumps(data)

    @classmethod
    def from_json(cls, data: bytes) -> RequestTrace:
        """Deserialize from JSON bytes."""
        import base64
        raw = orjson.loads(data)
        raw["body"] = base64.b64decode(raw.get("body", ""))
        raw["response_body"] = base64.b64decode(raw.get("response_body", ""))
        raw["queries"] = [QueryRecord(**q) for q in raw.get("queries", [])]
        raw["timing"] = TimingRecord(**raw.get("timing", {}))
        return cls(**raw)


class _QueryTracker:
    """Database execute wrapper that captures queries."""

    def __init__(self) -> None:
        self.queries: list[QueryRecord] = []
        self._total_ms: float = 0.0

    def __call__(self, execute, sql, params, many, context):
        start = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self._total_ms += duration_ms
            self.queries.append(
                QueryRecord(
                    sql=sql,
                    params=list(params) if params else [],
                    duration_ms=round(duration_ms, 3),
                    stack=self._short_stack(),
                )
            )

    @staticmethod
    def _short_stack() -> str:
        """Get a shortened stack trace (skip framework internals)."""
        frames = traceback.extract_stack()
        relevant = [
            f for f in frames
            if "django_matt" not in f.filename
            and "django/" not in f.filename
            and "site-packages" not in f.filename
        ]
        return "\n".join(
            f"{f.filename}:{f.lineno} in {f.name}" for f in relevant[-5:]
        )


class RequestRecorder:
    """Capture full request lifecycle for replay.

    Usage as middleware::

        class ReplayRecorderMiddleware:
            def __init__(self, get_response):
                self.get_response = get_response
                self.recorder = RequestRecorder()

            async def __call__(self, request):
                trace, response = await self.recorder.record_request(
                    request, self.get_response
                )
                store.save(trace)
                return response
    """

    def __init__(self, capture_stacks: bool = True) -> None:
        self.capture_stacks = capture_stacks

    async def record_request(
        self, request: Any, get_response: Any
    ) -> tuple[RequestTrace, Any]:
        """Record a request lifecycle and return (trace, response)."""
        from django.db import connection

        trace = RequestTrace(
            trace_id=uuid.uuid4().hex[:16],
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        # Capture request
        trace.method = request.method
        trace.path = request.path
        trace.query_string = request.META.get("QUERY_STRING", "")
        trace.headers = self._extract_headers(request)
        trace.body = getattr(request, "body", b"") or b""
        trace.user_id = getattr(getattr(request, "user", None), "pk", None)
        trace.auth_type = type(getattr(request, "auth", None)).__name__

        # Capture environment
        self._capture_env(trace)

        # Track DB queries
        tracker = _QueryTracker()
        start = time.perf_counter()

        with connection.execute_wrapper(tracker):
            response = await get_response(request)

        total_ms = (time.perf_counter() - start) * 1000

        # Capture response
        trace.status_code = response.status_code
        trace.response_headers = {k: v for k, v in response.items()}
        trace.response_body = getattr(response, "content", b"") or b""

        # Capture queries and timing
        trace.queries = tracker.queries
        trace.timing = TimingRecord(
            total_ms=round(total_ms, 3),
            db_ms=round(tracker._total_ms, 3),
        )

        return trace, response

    @staticmethod
    def _extract_headers(request: Any) -> dict[str, str]:
        headers = {}
        for key, value in request.META.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-").lower()
                headers[header_name] = value
            elif key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
                headers[key.lower().replace("_", "-")] = value
        return headers

    @staticmethod
    def _capture_env(trace: RequestTrace) -> None:
        import sys
        trace.python_version = sys.version.split()[0]
        try:
            import django
            trace.django_version = django.__version__
        except ImportError:
            pass
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, check=True,
            )
            trace.git_sha = result.stdout.strip()
        except Exception:
            pass
