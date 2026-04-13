"""
Storage backends for the Request Inspector.

Provides in-memory and Redis storage options for captured requests.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from django.conf import settings

import orjson


@dataclass
class CapturedRequest:
    """Represents a captured HTTP request/response pair."""

    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time.time)
    method: str = ""
    path: str = ""
    full_url: str = ""
    query_string: str = ""
    request_headers: Dict[str, str] = field(default_factory=dict)
    request_body: Optional[str] = None
    request_content_type: Optional[str] = None
    response_status: int = 0
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_body: Optional[str] = None
    response_content_type: Optional[str] = None
    duration_ms: float = 0.0
    client_ip: str = ""
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    exception: Optional[str] = None
    traceback: Optional[str] = None
    db_queries: list[dict[str, Any]] = field(default_factory=list)
    db_query_count: int = 0
    db_query_time_ms: float = 0.0
    n_plus_one_warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CapturedRequest:
        """Create from dictionary."""
        return cls(**data)

    @property
    def timestamp_dt(self) -> datetime:
        """Get timestamp as datetime object."""
        return datetime.fromtimestamp(self.timestamp)

    @property
    def is_success(self) -> bool:
        """Check if response was successful (2xx)."""
        return 200 <= self.response_status < 300

    @property
    def is_redirect(self) -> bool:
        """Check if response was a redirect (3xx)."""
        return 300 <= self.response_status < 400

    @property
    def is_client_error(self) -> bool:
        """Check if response was a client error (4xx)."""
        return 400 <= self.response_status < 500

    @property
    def is_server_error(self) -> bool:
        """Check if response was a server error (5xx)."""
        return self.response_status >= 500

    @property
    def status_category(self) -> str:
        """Get the status category (success, redirect, client_error, server_error)."""
        if self.is_success:
            return "success"
        if self.is_redirect:
            return "redirect"
        if self.is_client_error:
            return "client_error"
        if self.is_server_error:
            return "server_error"
        return "unknown"


class InspectorStorage(ABC):
    """Abstract base class for inspector storage backends."""

    @abstractmethod
    def add(self, request: CapturedRequest) -> None:
        """Add a captured request to storage."""

    @abstractmethod
    def get(self, request_id: str) -> Optional[CapturedRequest]:
        """Get a specific captured request by ID."""

    @abstractmethod
    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        method: Optional[str] = None,
        status: Optional[int] = None,
        status_min: Optional[int] = None,
        status_max: Optional[int] = None,
        path_contains: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> List[CapturedRequest]:
        """List captured requests with optional filtering."""

    @abstractmethod
    def clear(self) -> int:
        """Clear all captured requests. Returns number of cleared requests."""

    @abstractmethod
    def count(self) -> int:
        """Get total number of captured requests."""

    @abstractmethod
    def is_capturing(self) -> bool:
        """Check if capture is currently enabled."""

    @abstractmethod
    def pause_capture(self) -> None:
        """Pause request capture."""

    @abstractmethod
    def resume_capture(self) -> None:
        """Resume request capture."""


class MemoryStorage(InspectorStorage):
    """In-memory storage for captured requests using a bounded deque."""

    def __init__(self, max_requests: int = 100):
        self.max_requests = max_requests
        self._requests: deque[CapturedRequest] = deque(maxlen=max_requests)
        self._lock = threading.RLock()
        self._capturing = True
        self._requests_by_id: Dict[str, CapturedRequest] = {}

    def add(self, request: CapturedRequest) -> None:
        """Add a captured request to storage."""
        if not self._capturing:
            return

        with self._lock:
            # If we're at capacity, remove the oldest from the lookup dict
            if len(self._requests) >= self.max_requests:
                oldest = self._requests[0]
                self._requests_by_id.pop(oldest.id, None)

            self._requests.append(request)
            self._requests_by_id[request.id] = request

    def get(self, request_id: str) -> Optional[CapturedRequest]:
        """Get a specific captured request by ID."""
        with self._lock:
            return self._requests_by_id.get(request_id)

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        method: Optional[str] = None,
        status: Optional[int] = None,
        status_min: Optional[int] = None,
        status_max: Optional[int] = None,
        path_contains: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> List[CapturedRequest]:
        """List captured requests with optional filtering."""
        with self._lock:
            # Start with all requests, newest first
            result = list(reversed(self._requests))

            # Apply filters
            if method:
                method_upper = method.upper()
                result = [r for r in result if r.method == method_upper]

            if status is not None:
                result = [r for r in result if r.response_status == status]

            if status_min is not None:
                result = [r for r in result if r.response_status >= status_min]

            if status_max is not None:
                result = [r for r in result if r.response_status < status_max]

            if path_contains:
                path_lower = path_contains.lower()
                result = [r for r in result if path_lower in r.path.lower()]

            if since is not None:
                result = [r for r in result if r.timestamp >= since]

            if until is not None:
                result = [r for r in result if r.timestamp <= until]

            # Apply pagination
            return result[offset : offset + limit]

    def clear(self) -> int:
        """Clear all captured requests."""
        with self._lock:
            count = len(self._requests)
            self._requests.clear()
            self._requests_by_id.clear()
            return count

    def count(self) -> int:
        """Get total number of captured requests."""
        with self._lock:
            return len(self._requests)

    def is_capturing(self) -> bool:
        """Check if capture is currently enabled."""
        return self._capturing

    def pause_capture(self) -> None:
        """Pause request capture."""
        self._capturing = False

    def resume_capture(self) -> None:
        """Resume request capture."""
        self._capturing = True


class RedisStorage(InspectorStorage):
    """Redis storage for captured requests with automatic expiration."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        max_requests: int = 100,
        ttl_seconds: int = 3600,
        key_prefix: str = "django_matt:inspector:",
    ):
        self.max_requests = max_requests
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix

        # Import redis lazily
        try:
            import redis
        except ImportError:
            raise ImportError(
                "Redis package is required for RedisStorage. Install it with: uv add redis"
            )

        # Get Redis URL from settings or parameter
        if redis_url is None:
            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")

        self._redis = redis.from_url(redis_url)
        self._list_key = f"{key_prefix}requests"
        self._capturing_key = f"{key_prefix}capturing"

        # Initialize capturing state if not set
        if self._redis.get(self._capturing_key) is None:
            self._redis.set(self._capturing_key, "1")

    def _request_key(self, request_id: str) -> str:
        """Get the Redis key for a specific request."""
        return f"{self.key_prefix}request:{request_id}"

    def add(self, request: CapturedRequest) -> None:
        """Add a captured request to storage."""
        if not self.is_capturing():
            return

        request_key = self._request_key(request.id)
        data = orjson.dumps(request.to_dict())

        # Use pipeline for atomic operation
        pipe = self._redis.pipeline()

        # Store the request data with TTL
        pipe.setex(request_key, self.ttl_seconds, data)

        # Add to the list (newest first)
        pipe.lpush(self._list_key, request.id)

        # Trim the list to max_requests
        pipe.ltrim(self._list_key, 0, self.max_requests - 1)

        pipe.execute()

    def get(self, request_id: str) -> Optional[CapturedRequest]:
        """Get a specific captured request by ID."""
        request_key = self._request_key(request_id)
        data = self._redis.get(request_key)

        if data is None:
            return None

        return CapturedRequest.from_dict(orjson.loads(data))

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        method: Optional[str] = None,
        status: Optional[int] = None,
        status_min: Optional[int] = None,
        status_max: Optional[int] = None,
        path_contains: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> List[CapturedRequest]:
        """List captured requests with optional filtering."""
        # Get all request IDs from the list
        request_ids = self._redis.lrange(self._list_key, 0, -1)

        if not request_ids:
            return []

        # Fetch all requests in a pipeline
        pipe = self._redis.pipeline()
        for request_id in request_ids:
            pipe.get(
                self._request_key(
                    request_id.decode() if isinstance(request_id, bytes) else request_id
                )
            )

        results = pipe.execute()

        # Parse and filter requests
        requests = []
        for data in results:
            if data is None:
                continue

            request = CapturedRequest.from_dict(orjson.loads(data))

            # Apply filters
            if method and request.method != method.upper():
                continue
            if status is not None and request.response_status != status:
                continue
            if status_min is not None and request.response_status < status_min:
                continue
            if status_max is not None and request.response_status >= status_max:
                continue
            if path_contains and path_contains.lower() not in request.path.lower():
                continue
            if since is not None and request.timestamp < since:
                continue
            if until is not None and request.timestamp > until:
                continue

            requests.append(request)

        # Apply pagination
        return requests[offset : offset + limit]

    def clear(self) -> int:
        """Clear all captured requests."""
        # Get all request IDs
        request_ids = self._redis.lrange(self._list_key, 0, -1)
        count = len(request_ids)

        if request_ids:
            # Delete all request data
            pipe = self._redis.pipeline()
            for request_id in request_ids:
                pipe.delete(
                    self._request_key(
                        request_id.decode() if isinstance(request_id, bytes) else request_id
                    )
                )
            pipe.delete(self._list_key)
            pipe.execute()

        return count

    def count(self) -> int:
        """Get total number of captured requests."""
        return self._redis.llen(self._list_key)

    def is_capturing(self) -> bool:
        """Check if capture is currently enabled."""
        value = self._redis.get(self._capturing_key)
        return value == b"1" or value == "1"

    def pause_capture(self) -> None:
        """Pause request capture."""
        self._redis.set(self._capturing_key, "0")

    def resume_capture(self) -> None:
        """Resume request capture."""
        self._redis.set(self._capturing_key, "1")


# Global storage instance
_storage: Optional[InspectorStorage] = None
_storage_lock = threading.Lock()


def get_storage() -> InspectorStorage:
    """Get or create the global storage instance based on settings."""
    global _storage

    if _storage is not None:
        return _storage

    with _storage_lock:
        # Double-check after acquiring lock
        if _storage is not None:
            return _storage

        # Get configuration from settings
        config = getattr(settings, "DJANGO_MATT_INSPECTOR", {})
        storage_backend = config.get("STORAGE_BACKEND", "memory")
        max_requests = config.get("MAX_REQUESTS", 100)

        if storage_backend == "redis":
            redis_url = config.get("REDIS_URL")
            ttl = config.get("TTL_SECONDS", 3600)
            _storage = RedisStorage(
                redis_url=redis_url,
                max_requests=max_requests,
                ttl_seconds=ttl,
            )
        else:
            _storage = MemoryStorage(max_requests=max_requests)

        return _storage


def reset_storage() -> None:
    """Reset the global storage instance. Useful for testing."""
    global _storage
    with _storage_lock:
        _storage = None
