"""
Event tracker for analytics.

Provides the main interface for tracking events, page views, and user identity.

Usage:
    from django_matt.analytics import EventTracker

    tracker = EventTracker()

    # Track an event
    tracker.track_event(
        "button_click",
        properties={"button_id": "signup"},
        user=request.user,
        session=session,
    )

    # Track page view
    tracker.track_page_view(
        path="/pricing",
        user=request.user,
        referrer="https://google.com",
    )

    # Identify user
    tracker.identify(user=request.user, traits={"plan": "pro"})

    # Batch tracking
    async with tracker.batch() as batch:
        batch.track_event("event1", {...})
        batch.track_event("event2", {...})
        batch.track_page_view("/page1", {...})
"""

import hashlib
import logging
import threading
import uuid
from collections import deque
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.http import HttpRequest

    from .models import AnalyticsSession

logger = logging.getLogger("django_matt.analytics")


class BatchContext:
    """Context for batched event tracking."""

    def __init__(self, tracker: "EventTracker"):
        self.tracker = tracker
        self.events: list[dict] = []
        self.page_views: list[dict] = []

    def track_event(
        self,
        name: str,
        properties: dict | None = None,
        **kwargs,
    ):
        """Queue an event for batch tracking."""
        self.events.append(
            {
                "name": name,
                "properties": properties or {},
                **kwargs,
            }
        )

    def track_page_view(
        self,
        path: str,
        **kwargs,
    ):
        """Queue a page view for batch tracking."""
        self.page_views.append(
            {
                "path": path,
                **kwargs,
            }
        )


class EventTracker:
    """
    Main event tracking interface.

    Provides methods for tracking events, page views, and user identification
    with support for batched writes, anonymization, and multiple backends.

    Attributes:
        backend: Storage backend for events
        batch_size: Number of events to batch before flush
        batch_timeout: Maximum time to wait before flushing batch
        anonymize_ip: Whether to hash IP addresses
        respect_dnt: Whether to respect Do Not Track header
    """

    def __init__(
        self,
        backend: str | None = None,
        batch_size: int = 100,
        batch_timeout: float = 5.0,
        anonymize_ip: bool = False,
        respect_dnt: bool = True,
    ):
        """
        Initialize the event tracker.

        Args:
            backend: Backend name (database, redis, segment, etc.)
            batch_size: Events to buffer before flush
            batch_timeout: Seconds to wait before auto-flush
            anonymize_ip: Hash IP addresses for privacy
            respect_dnt: Skip tracking if DNT header is set
        """
        self._backend_name = backend
        self._backend = None
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.anonymize_ip = anonymize_ip
        self.respect_dnt = respect_dnt

        # Batching state
        self._event_buffer: deque = deque()
        self._page_view_buffer: deque = deque()
        self._buffer_lock = threading.Lock()
        self._flush_timer: threading.Timer | None = None

        # Load config from settings
        self._load_config()

    def _load_config(self):
        """Load configuration from Django settings."""
        config = getattr(settings, "DJANGO_MATT_ANALYTICS", {})

        self._backend_name = self._backend_name or config.get("BACKEND", "database")
        self.batch_size = config.get("BATCH_SIZE", self.batch_size)
        self.batch_timeout = config.get("BATCH_TIMEOUT", self.batch_timeout)
        self.anonymize_ip = config.get("ANONYMIZE_IP", self.anonymize_ip)
        self.respect_dnt = config.get("RESPECT_DNT", self.respect_dnt)

    @property
    def backend(self):
        """Lazy backend initialization."""
        if self._backend is None:
            from .backends import get_backend

            self._backend = get_backend(self._backend_name)
        return self._backend

    def track_event(
        self,
        name: str,
        properties: dict | None = None,
        user: "AbstractUser | None" = None,
        session: "AnalyticsSession | None" = None,
        anonymous_id: str = "",
        category: str = "custom",
        context: dict | None = None,
        timestamp: datetime | None = None,
        page_url: str = "",
        page_title: str = "",
        element_id: str = "",
        element_class: str = "",
        element_text: str = "",
        revenue: float | None = None,
        currency: str = "",
        organization_id: str = "",
        flush: bool = False,
        request: "HttpRequest | None" = None,
    ) -> str:
        """
        Track a custom event.

        Args:
            name: Event name (e.g., "button_click", "purchase_completed")
            properties: Event-specific properties
            user: Associated user
            session: Associated session
            anonymous_id: Anonymous user identifier
            category: Event category
            context: Contextual information
            timestamp: Event timestamp (defaults to now)
            page_url: URL where event occurred
            page_title: Page title
            element_id: DOM element ID
            element_class: DOM element class
            element_text: DOM element text
            revenue: Revenue amount for conversion events
            currency: Currency code
            organization_id: Organization/tenant ID
            flush: Force immediate write
            request: HTTP request for extracting context

        Returns:
            Event ID
        """
        # Check DNT
        if request and self.respect_dnt:
            dnt = request.META.get("HTTP_DNT", "0")
            if dnt == "1":
                logger.debug("Skipping event tracking due to DNT header")
                return ""

        # Generate event ID
        event_id = str(uuid.uuid4())

        # Extract context from request if provided
        if request and not context:
            context = self._extract_context(request)

        # Build event data
        event_data = {
            "id": event_id,
            "name": name,
            "category": category,
            "properties": properties or {},
            "user_id": str(user.pk) if user else None,
            "session_id": str(session.pk) if session else None,
            "anonymous_id": anonymous_id,
            "context": context or {},
            "timestamp": timestamp or timezone.now(),
            "page_url": page_url,
            "page_title": page_title,
            "element_id": element_id,
            "element_class": element_class,
            "element_text": element_text,
            "revenue": revenue,
            "currency": currency,
            "organization_id": organization_id,
        }

        if flush:
            # Immediate write
            self.backend.track_event(event_data)
        else:
            # Add to buffer
            self._add_to_buffer("event", event_data)

        return event_id

    def track_page_view(
        self,
        path: str,
        url: str = "",
        title: str = "",
        user: "AbstractUser | None" = None,
        session: "AnalyticsSession | None" = None,
        anonymous_id: str = "",
        referrer: str | None = None,
        timestamp: datetime | None = None,
        time_on_page: int | None = None,
        scroll_depth: int = 0,
        load_time_ms: int | None = None,
        organization_id: str = "",
        flush: bool = False,
        request: "HttpRequest | None" = None,
    ) -> str:
        """
        Track a page view.

        Args:
            path: URL path
            url: Full URL
            title: Page title
            user: Associated user
            session: Associated session
            anonymous_id: Anonymous user identifier
            referrer: Referrer URL
            timestamp: Page view timestamp
            time_on_page: Time spent on previous page (seconds)
            scroll_depth: Maximum scroll depth percentage
            load_time_ms: Page load time in milliseconds
            organization_id: Organization/tenant ID
            flush: Force immediate write
            request: HTTP request for extracting context

        Returns:
            Page view ID
        """
        # Check DNT
        if request and self.respect_dnt:
            dnt = request.META.get("HTTP_DNT", "0")
            if dnt == "1":
                return ""

        page_view_id = str(uuid.uuid4())

        # Extract referrer from request if not provided
        if request and not referrer:
            referrer = request.META.get("HTTP_REFERER")

        # Extract URL from request if not provided
        if request and not url:
            url = request.build_absolute_uri()

        page_view_data = {
            "id": page_view_id,
            "path": path,
            "url": url or f"https://example.com{path}",
            "title": title,
            "user_id": str(user.pk) if user else None,
            "session_id": str(session.pk) if session else None,
            "anonymous_id": anonymous_id,
            "referrer": referrer,
            "timestamp": timestamp or timezone.now(),
            "time_on_page": time_on_page,
            "scroll_depth": scroll_depth,
            "load_time_ms": load_time_ms,
            "organization_id": organization_id,
        }

        if flush:
            self.backend.track_page_view(page_view_data)
        else:
            self._add_to_buffer("page_view", page_view_data)

        return page_view_id

    def identify(
        self,
        user: "AbstractUser",
        anonymous_id: str = "",
        traits: dict | None = None,
        context: dict | None = None,
        timestamp: datetime | None = None,
    ):
        """
        Identify a user and link anonymous sessions.

        Args:
            user: User to identify
            anonymous_id: Anonymous ID to link to user
            traits: User traits
            context: Contextual information
            timestamp: Identification timestamp
        """
        self.backend.identify(
            user_id=str(user.pk),
            anonymous_id=anonymous_id,
            traits=traits or {},
            context=context or {},
            timestamp=timestamp or timezone.now(),
        )

        # Link anonymous sessions/events if anonymous_id provided
        if anonymous_id:
            self.backend.alias(anonymous_id, str(user.pk))

    def alias(self, previous_id: str, user_id: str):
        """
        Create an alias between two user IDs.

        Useful for linking anonymous users to authenticated users.

        Args:
            previous_id: Previous ID (usually anonymous_id)
            user_id: New user ID
        """
        self.backend.alias(previous_id, user_id)

    def group(
        self,
        user: "AbstractUser",
        group_id: str,
        traits: dict | None = None,
    ):
        """
        Associate a user with a group (organization/company).

        Args:
            user: User to associate
            group_id: Group/organization ID
            traits: Group traits
        """
        self.backend.group(
            user_id=str(user.pk),
            group_id=group_id,
            traits=traits or {},
        )

    @contextmanager
    def batch(self):
        """
        Context manager for batch tracking.

        Usage:
            with tracker.batch() as batch:
                batch.track_event("event1", {...})
                batch.track_event("event2", {...})
                batch.track_page_view("/page1", {...})
            # All events/page views are flushed on exit
        """
        batch_ctx = BatchContext(self)
        try:
            yield batch_ctx
        finally:
            # Flush batch
            if batch_ctx.events:
                self.backend.track_events_batch(batch_ctx.events)
            if batch_ctx.page_views:
                self.backend.track_page_views_batch(batch_ctx.page_views)

    @asynccontextmanager
    async def async_batch(self):
        """Async version of batch context manager."""
        batch_ctx = BatchContext(self)
        try:
            yield batch_ctx
        finally:
            if batch_ctx.events:
                await self.backend.track_events_batch_async(batch_ctx.events)
            if batch_ctx.page_views:
                await self.backend.track_page_views_batch_async(batch_ctx.page_views)

    def flush(self):
        """Flush all buffered events and page views."""
        with self._buffer_lock:
            events = list(self._event_buffer)
            page_views = list(self._page_view_buffer)
            self._event_buffer.clear()
            self._page_view_buffer.clear()

        if events:
            try:
                self.backend.track_events_batch(events)
                logger.debug(f"Flushed {len(events)} events")
            except Exception as e:
                logger.error(f"Error flushing events: {e}")
                # Re-queue on failure
                with self._buffer_lock:
                    self._event_buffer.extendleft(events)

        if page_views:
            try:
                self.backend.track_page_views_batch(page_views)
                logger.debug(f"Flushed {len(page_views)} page views")
            except Exception as e:
                logger.error(f"Error flushing page views: {e}")
                with self._buffer_lock:
                    self._page_view_buffer.extendleft(page_views)

    async def flush_async(self):
        """Async version of flush."""
        with self._buffer_lock:
            events = list(self._event_buffer)
            page_views = list(self._page_view_buffer)
            self._event_buffer.clear()
            self._page_view_buffer.clear()

        if events:
            try:
                await self.backend.track_events_batch_async(events)
            except Exception as e:
                logger.error(f"Error flushing events: {e}")

        if page_views:
            try:
                await self.backend.track_page_views_batch_async(page_views)
            except Exception as e:
                logger.error(f"Error flushing page views: {e}")

    def _add_to_buffer(self, event_type: str, data: dict):
        """Add item to buffer and schedule flush if needed."""
        with self._buffer_lock:
            if event_type == "event":
                self._event_buffer.append(data)
                should_flush = len(self._event_buffer) >= self.batch_size
            else:
                self._page_view_buffer.append(data)
                should_flush = len(self._page_view_buffer) >= self.batch_size

        if should_flush:
            self.flush()
        else:
            self._schedule_flush()

    def _schedule_flush(self):
        """Schedule a timed flush."""
        if self._flush_timer is None or not self._flush_timer.is_alive():
            self._flush_timer = threading.Timer(self.batch_timeout, self.flush)
            self._flush_timer.daemon = True
            self._flush_timer.start()

    def _extract_context(self, request: "HttpRequest") -> dict:
        """Extract context from HTTP request."""
        context = {
            "page_url": request.build_absolute_uri(),
            "page_path": request.path,
        }

        # User agent parsing
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        if user_agent:
            context["user_agent"] = user_agent
            # Basic device type detection
            ua_lower = user_agent.lower()
            if "mobile" in ua_lower:
                context["device_type"] = "mobile"
            elif "tablet" in ua_lower:
                context["device_type"] = "tablet"
            else:
                context["device_type"] = "desktop"

        # IP address
        ip = self._get_client_ip(request)
        if ip:
            if self.anonymize_ip:
                context["ip_hash"] = hashlib.sha256(ip.encode()).hexdigest()[:16]
            else:
                context["ip"] = ip

        # Referrer
        referrer = request.META.get("HTTP_REFERER")
        if referrer:
            context["referrer"] = referrer

        # Accept-Language
        locale = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
        if locale:
            context["locale"] = locale.split(",")[0]

        return context

    def _get_client_ip(self, request: "HttpRequest") -> str | None:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def close(self):
        """Clean up resources."""
        # Cancel any pending flush timer
        if self._flush_timer:
            self._flush_timer.cancel()

        # Flush remaining events
        self.flush()

        # Close backend
        if self._backend:
            self._backend.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Global tracker instance
_default_tracker: EventTracker | None = None


def get_tracker() -> EventTracker:
    """Get the default tracker instance."""
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = EventTracker()
    return _default_tracker


def track_event(name: str, **kwargs) -> str:
    """Track an event using the default tracker."""
    return get_tracker().track_event(name, **kwargs)


def track_page_view(path: str, **kwargs) -> str:
    """Track a page view using the default tracker."""
    return get_tracker().track_page_view(path, **kwargs)


def identify(user: "AbstractUser", **kwargs):
    """Identify a user using the default tracker."""
    get_tracker().identify(user, **kwargs)


__all__ = [
    "EventTracker",
    "BatchContext",
    "get_tracker",
    "track_event",
    "track_page_view",
    "identify",
]
