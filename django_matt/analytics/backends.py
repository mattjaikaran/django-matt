"""
Analytics storage backends.

Provides different storage backends for analytics data:
- DatabaseBackend: Uses Django ORM (default)
- RedisBackend: Real-time counters and sessions
- SegmentBackend: Forward to Segment.io
- MixpanelBackend: Forward to Mixpanel
- PostHogBackend: Forward to PostHog
- AmplitudeBackend: Forward to Amplitude

Usage:
    from django_matt.analytics.backends import get_backend

    backend = get_backend()  # Gets default backend from settings
    backend.track_event({...})
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

import orjson

if TYPE_CHECKING:
    pass

logger = logging.getLogger("django_matt.analytics")


class AnalyticsBackend(ABC):
    """Base class for analytics backends."""

    @abstractmethod
    def track_event(self, event_data: dict) -> str:
        """
        Track a single event.

        Args:
            event_data: Event data dictionary

        Returns:
            Event ID
        """

    @abstractmethod
    def track_events_batch(self, events: list[dict]) -> list[str]:
        """
        Track multiple events in batch.

        Args:
            events: List of event data dictionaries

        Returns:
            List of event IDs
        """

    @abstractmethod
    def track_page_view(self, page_view_data: dict) -> str:
        """
        Track a single page view.

        Args:
            page_view_data: Page view data dictionary

        Returns:
            Page view ID
        """

    @abstractmethod
    def track_page_views_batch(self, page_views: list[dict]) -> list[str]:
        """Track multiple page views in batch."""

    @abstractmethod
    def identify(
        self,
        user_id: str,
        anonymous_id: str = "",
        traits: dict | None = None,
        context: dict | None = None,
        timestamp: datetime | None = None,
    ):
        """Identify a user."""

    @abstractmethod
    def alias(self, previous_id: str, user_id: str):
        """Create an alias between IDs."""

    @abstractmethod
    def group(
        self,
        user_id: str,
        group_id: str,
        traits: dict | None = None,
    ):
        """Associate user with a group."""

    # Async methods with default implementations
    async def track_event_async(self, event_data: dict) -> str:
        """Async version of track_event."""
        return await asyncio.to_thread(self.track_event, event_data)

    async def track_events_batch_async(self, events: list[dict]) -> list[str]:
        """Async version of track_events_batch."""
        return await asyncio.to_thread(self.track_events_batch, events)

    async def track_page_view_async(self, page_view_data: dict) -> str:
        """Async version of track_page_view."""
        return await asyncio.to_thread(self.track_page_view, page_view_data)

    async def track_page_views_batch_async(self, page_views: list[dict]) -> list[str]:
        """Async version of track_page_views_batch."""
        return await asyncio.to_thread(self.track_page_views_batch, page_views)

    def close(self):
        """Clean up resources."""


class DatabaseBackend(AnalyticsBackend):
    """
    Database-backed analytics backend.

    Uses Django ORM for storage. Best for small to medium scale.
    """

    def __init__(self, **kwargs):
        self.batch_create_size = kwargs.get("batch_create_size", 1000)

    def track_event(self, event_data: dict) -> str:
        """Track a single event to database."""
        from .models import AnalyticsEvent

        event = AnalyticsEvent.objects.create(
            id=event_data.get("id"),
            name=event_data["name"],
            category=event_data.get("category", "custom"),
            properties=event_data.get("properties", {}),
            user_id=event_data.get("user_id"),
            session_id=event_data.get("session_id"),
            anonymous_id=event_data.get("anonymous_id", ""),
            context=event_data.get("context", {}),
            timestamp=event_data.get("timestamp", timezone.now()),
            page_url=event_data.get("page_url", ""),
            page_title=event_data.get("page_title", ""),
            page_path=event_data.get("page_path", ""),
            element_id=event_data.get("element_id", ""),
            element_class=event_data.get("element_class", ""),
            element_text=event_data.get("element_text", ""),
            revenue=event_data.get("revenue"),
            currency=event_data.get("currency", ""),
            organization_id=event_data.get("organization_id", ""),
        )
        return str(event.id)

    def track_events_batch(self, events: list[dict]) -> list[str]:
        """Track multiple events in batch."""
        from .models import AnalyticsEvent

        event_objs = []
        for event_data in events:
            event_objs.append(
                AnalyticsEvent(
                    id=event_data.get("id"),
                    name=event_data["name"],
                    category=event_data.get("category", "custom"),
                    properties=event_data.get("properties", {}),
                    user_id=event_data.get("user_id"),
                    session_id=event_data.get("session_id"),
                    anonymous_id=event_data.get("anonymous_id", ""),
                    context=event_data.get("context", {}),
                    timestamp=event_data.get("timestamp", timezone.now()),
                    page_url=event_data.get("page_url", ""),
                    page_title=event_data.get("page_title", ""),
                    page_path=event_data.get("page_path", ""),
                    element_id=event_data.get("element_id", ""),
                    element_class=event_data.get("element_class", ""),
                    element_text=event_data.get("element_text", ""),
                    revenue=event_data.get("revenue"),
                    currency=event_data.get("currency", ""),
                    organization_id=event_data.get("organization_id", ""),
                )
            )

        created = AnalyticsEvent.objects.bulk_create(
            event_objs,
            batch_size=self.batch_create_size,
        )
        return [str(e.id) for e in created]

    def track_page_view(self, page_view_data: dict) -> str:
        """Track a single page view."""
        from .models import PageView

        page_view = PageView.objects.create(
            id=page_view_data.get("id"),
            path=page_view_data["path"],
            url=page_view_data.get("url", ""),
            title=page_view_data.get("title", ""),
            user_id=page_view_data.get("user_id"),
            session_id=page_view_data.get("session_id"),
            anonymous_id=page_view_data.get("anonymous_id", ""),
            referrer=page_view_data.get("referrer"),
            timestamp=page_view_data.get("timestamp", timezone.now()),
            time_on_page=page_view_data.get("time_on_page"),
            scroll_depth=page_view_data.get("scroll_depth", 0),
            load_time_ms=page_view_data.get("load_time_ms"),
            organization_id=page_view_data.get("organization_id", ""),
        )
        return str(page_view.id)

    def track_page_views_batch(self, page_views: list[dict]) -> list[str]:
        """Track multiple page views in batch."""
        from .models import PageView

        pv_objs = []
        for pv_data in page_views:
            pv_objs.append(
                PageView(
                    id=pv_data.get("id"),
                    path=pv_data["path"],
                    url=pv_data.get("url", ""),
                    title=pv_data.get("title", ""),
                    user_id=pv_data.get("user_id"),
                    session_id=pv_data.get("session_id"),
                    anonymous_id=pv_data.get("anonymous_id", ""),
                    referrer=pv_data.get("referrer"),
                    timestamp=pv_data.get("timestamp", timezone.now()),
                    time_on_page=pv_data.get("time_on_page"),
                    scroll_depth=pv_data.get("scroll_depth", 0),
                    load_time_ms=pv_data.get("load_time_ms"),
                    organization_id=pv_data.get("organization_id", ""),
                )
            )

        created = PageView.objects.bulk_create(
            pv_objs,
            batch_size=self.batch_create_size,
        )
        return [str(pv.id) for pv in created]

    def identify(
        self,
        user_id: str,
        anonymous_id: str = "",
        traits: dict | None = None,
        context: dict | None = None,
        timestamp: datetime | None = None,
    ):
        """Identify user and link anonymous sessions."""
        from django.contrib.auth import get_user_model

        from .models import AnalyticsEvent, AnalyticsSession, PageView, UserIdentity

        User = get_user_model()

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning(f"User {user_id} not found for identification")
            return

        if anonymous_id:
            # Create identity link
            UserIdentity.objects.update_or_create(
                anonymous_id=anonymous_id,
                defaults={
                    "user": user,
                    "traits": traits or {},
                    "context": context or {},
                },
            )

            # Link sessions
            AnalyticsSession.objects.filter(
                anonymous_id=anonymous_id,
                user__isnull=True,
            ).update(user=user)

            # Link events
            AnalyticsEvent.objects.filter(
                anonymous_id=anonymous_id,
                user__isnull=True,
            ).update(user=user)

            # Link page views
            PageView.objects.filter(
                anonymous_id=anonymous_id,
                user__isnull=True,
            ).update(user=user)

    def alias(self, previous_id: str, user_id: str):
        """Create an alias between IDs."""
        # For database backend, this is handled by identify()

    def group(
        self,
        user_id: str,
        group_id: str,
        traits: dict | None = None,
    ):
        """Associate user with a group (organization)."""
        from .models import AnalyticsSession

        # Store group association in session metadata
        for session in AnalyticsSession.objects.filter(user_id=user_id):
            meta = session.metadata or {}
            meta["organization_id"] = group_id
            if traits:
                meta["organization_traits"] = traits
            session.metadata = meta
            session.save(update_fields=["metadata"])

        # Track group event
        self.track_event(
            {
                "name": "user_grouped",
                "category": "system",
                "user_id": user_id,
                "properties": {
                    "group_id": group_id,
                    "traits": traits or {},
                },
            }
        )


class RedisBackend(AnalyticsBackend):
    """
    Redis-backed analytics backend.

    Optimized for real-time counters and session management.
    Events are buffered in Redis and periodically flushed to database.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        key_prefix: str = "analytics:",
        buffer_size: int = 1000,
        flush_interval: int = 60,
    ):
        self.redis_url = redis_url or getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        self.key_prefix = key_prefix
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self._client = None

    @property
    def client(self):
        """Lazy Redis client initialization."""
        if self._client is None:
            try:
                import redis

                self._client = redis.from_url(self.redis_url)
            except ImportError:
                raise ImportError(
                    "redis package is required for RedisBackend. Install with: uv add redis"
                )
        return self._client

    def _get_key(self, *parts: str) -> str:
        """Build a Redis key."""
        return f"{self.key_prefix}{':'.join(parts)}"

    def track_event(self, event_data: dict) -> str:
        """Track event to Redis list."""
        event_id = event_data.get("id", str(__import__("uuid").uuid4()))

        # Add to events list
        self.client.lpush(
            self._get_key("events", "buffer"),
            orjson.dumps({**event_data, "id": event_id}, default=str).decode(),
        )

        # Increment counters
        timestamp = event_data.get("timestamp", timezone.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        hour_key = timestamp.strftime("%Y-%m-%d:%H")
        day_key = timestamp.strftime("%Y-%m-%d")

        pipeline = self.client.pipeline()
        pipeline.hincrby(self._get_key("events", "hourly", hour_key), event_data["name"], 1)
        pipeline.hincrby(self._get_key("events", "daily", day_key), event_data["name"], 1)
        pipeline.hincrby(self._get_key("events", "total"), event_data["name"], 1)
        pipeline.execute()

        # Check if buffer needs flushing
        buffer_len = self.client.llen(self._get_key("events", "buffer"))
        if buffer_len >= self.buffer_size:
            self._flush_to_database("events")

        return event_id

    def track_events_batch(self, events: list[dict]) -> list[str]:
        """Track multiple events."""
        ids = []
        pipeline = self.client.pipeline()

        for event_data in events:
            event_id = event_data.get("id", str(__import__("uuid").uuid4()))
            ids.append(event_id)

            pipeline.lpush(
                self._get_key("events", "buffer"),
                orjson.dumps({**event_data, "id": event_id}, default=str).decode(),
            )

        pipeline.execute()
        return ids

    def track_page_view(self, page_view_data: dict) -> str:
        """Track page view to Redis."""
        pv_id = page_view_data.get("id", str(__import__("uuid").uuid4()))

        self.client.lpush(
            self._get_key("pageviews", "buffer"),
            orjson.dumps({**page_view_data, "id": pv_id}, default=str).decode(),
        )

        # Increment page counters
        timestamp = page_view_data.get("timestamp", timezone.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        day_key = timestamp.strftime("%Y-%m-%d")
        path = page_view_data["path"]

        pipeline = self.client.pipeline()
        pipeline.hincrby(self._get_key("pageviews", "daily", day_key), path, 1)
        pipeline.hincrby(self._get_key("pageviews", "total"), path, 1)
        pipeline.execute()

        return pv_id

    def track_page_views_batch(self, page_views: list[dict]) -> list[str]:
        """Track multiple page views."""
        ids = []
        pipeline = self.client.pipeline()

        for pv_data in page_views:
            pv_id = pv_data.get("id", str(__import__("uuid").uuid4()))
            ids.append(pv_id)

            pipeline.lpush(
                self._get_key("pageviews", "buffer"),
                orjson.dumps({**pv_data, "id": pv_id}, default=str).decode(),
            )

        pipeline.execute()
        return ids

    def identify(
        self,
        user_id: str,
        anonymous_id: str = "",
        traits: dict | None = None,
        context: dict | None = None,
        timestamp: datetime | None = None,
    ):
        """Store identity mapping in Redis and delegate to database."""
        if anonymous_id:
            self.client.hset(
                self._get_key("identities"),
                anonymous_id,
                user_id,
            )

        # Also write to database
        db_backend = DatabaseBackend()
        db_backend.identify(user_id, anonymous_id, traits, context, timestamp)

    def alias(self, previous_id: str, user_id: str):
        """Create an alias in Redis."""
        self.client.hset(
            self._get_key("aliases"),
            previous_id,
            user_id,
        )

    def group(
        self,
        user_id: str,
        group_id: str,
        traits: dict | None = None,
    ):
        """Associate user with a group."""
        self.client.hset(
            self._get_key("groups", user_id),
            "group_id",
            group_id,
        )
        if traits:
            self.client.hset(
                self._get_key("groups", user_id),
                "traits",
                orjson.dumps(traits).decode(),
            )

    def _flush_to_database(self, data_type: str):
        """Flush buffered data to database."""
        buffer_key = self._get_key(data_type, "buffer")

        # Get all items from buffer
        items = []
        while True:
            item = self.client.rpop(buffer_key)
            if item is None:
                break
            items.append(orjson.loads(item))

        if not items:
            return

        db_backend = DatabaseBackend()
        if data_type == "events":
            db_backend.track_events_batch(items)
        else:
            db_backend.track_page_views_batch(items)

        logger.info(f"Flushed {len(items)} {data_type} to database")

    # Real-time methods specific to Redis

    def get_realtime_metrics(self, minutes: int = 30) -> dict:
        """Get real-time metrics from Redis."""
        now = timezone.now()
        start = now - timedelta(minutes=minutes)

        # Get active sessions (sessions with activity in last N minutes)
        active_sessions = self.client.zrangebyscore(
            self._get_key("sessions", "active"),
            start.timestamp(),
            now.timestamp(),
        )

        # Get event counts
        hour_key = now.strftime("%Y-%m-%d:%H")
        event_counts = self.client.hgetall(self._get_key("events", "hourly", hour_key))

        # Get page view counts
        day_key = now.strftime("%Y-%m-%d")
        page_counts = self.client.hgetall(self._get_key("pageviews", "daily", day_key))

        return {
            "active_sessions": len(active_sessions),
            "events_by_name": {k.decode(): int(v) for k, v in event_counts.items()}
            if event_counts
            else {},
            "pages_by_path": {k.decode(): int(v) for k, v in page_counts.items()}
            if page_counts
            else {},
        }

    def incr_counter(self, name: str, amount: int = 1) -> int:
        """Increment a counter."""
        return self.client.incrby(self._get_key("counters", name), amount)

    def get_counter(self, name: str) -> int:
        """Get counter value."""
        val = self.client.get(self._get_key("counters", name))
        return int(val) if val else 0

    def close(self):
        """Flush buffers and close connection."""
        self._flush_to_database("events")
        self._flush_to_database("pageviews")
        if self._client:
            self._client.close()
            self._client = None


class SegmentBackend(AnalyticsBackend):
    """
    Segment.io analytics backend.

    Forwards events to Segment for distribution to other tools.
    """

    def __init__(
        self,
        write_key: str | None = None,
        on_error: callable | None = None,
        debug: bool = False,
    ):
        self.write_key = write_key or getattr(settings, "SEGMENT_WRITE_KEY", None)
        if not self.write_key:
            raise ValueError("Segment write key is required")

        self.on_error = on_error
        self.debug = debug
        self._client = None

    @property
    def client(self):
        """Lazy Segment client initialization."""
        if self._client is None:
            try:
                import analytics

                analytics.write_key = self.write_key
                analytics.debug = self.debug
                if self.on_error:
                    analytics.on_error = self.on_error
                self._client = analytics
            except ImportError:
                raise ImportError(
                    "analytics-python is required for SegmentBackend. "
                    "Install with: uv add analytics-python"
                )
        return self._client

    def track_event(self, event_data: dict) -> str:
        """Track event to Segment."""
        user_id = event_data.get("user_id")
        anonymous_id = event_data.get("anonymous_id")

        if not user_id and not anonymous_id:
            anonymous_id = str(__import__("uuid").uuid4())

        self.client.track(
            user_id=user_id,
            anonymous_id=anonymous_id,
            event=event_data["name"],
            properties=event_data.get("properties", {}),
            context=event_data.get("context", {}),
            timestamp=event_data.get("timestamp"),
        )

        return event_data.get("id", "")

    def track_events_batch(self, events: list[dict]) -> list[str]:
        """Track multiple events."""
        ids = []
        for event in events:
            ids.append(self.track_event(event))
        return ids

    def track_page_view(self, page_view_data: dict) -> str:
        """Track page view to Segment."""
        user_id = page_view_data.get("user_id")
        anonymous_id = page_view_data.get("anonymous_id")

        if not user_id and not anonymous_id:
            anonymous_id = str(__import__("uuid").uuid4())

        self.client.page(
            user_id=user_id,
            anonymous_id=anonymous_id,
            name=page_view_data.get("title", ""),
            properties={
                "path": page_view_data["path"],
                "url": page_view_data.get("url", ""),
                "referrer": page_view_data.get("referrer"),
            },
            context=page_view_data.get("context", {}),
            timestamp=page_view_data.get("timestamp"),
        )

        return page_view_data.get("id", "")

    def track_page_views_batch(self, page_views: list[dict]) -> list[str]:
        """Track multiple page views."""
        ids = []
        for pv in page_views:
            ids.append(self.track_page_view(pv))
        return ids

    def identify(
        self,
        user_id: str,
        anonymous_id: str = "",
        traits: dict | None = None,
        context: dict | None = None,
        timestamp: datetime | None = None,
    ):
        """Identify user to Segment."""
        self.client.identify(
            user_id=user_id,
            anonymous_id=anonymous_id or None,
            traits=traits or {},
            context=context or {},
            timestamp=timestamp,
        )

    def alias(self, previous_id: str, user_id: str):
        """Create an alias in Segment."""
        self.client.alias(previous_id=previous_id, user_id=user_id)

    def group(
        self,
        user_id: str,
        group_id: str,
        traits: dict | None = None,
    ):
        """Associate user with a group in Segment."""
        self.client.group(
            user_id=user_id,
            group_id=group_id,
            traits=traits or {},
        )

    def close(self):
        """Flush and close Segment client."""
        if self._client:
            self._client.flush()


class MixpanelBackend(AnalyticsBackend):
    """
    Mixpanel analytics backend.

    Forwards events to Mixpanel.
    """

    def __init__(
        self,
        token: str | None = None,
        api_secret: str | None = None,
    ):
        self.token = token or getattr(settings, "MIXPANEL_TOKEN", None)
        self.api_secret = api_secret or getattr(settings, "MIXPANEL_API_SECRET", None)

        if not self.token:
            raise ValueError("Mixpanel token is required")

        self._client = None

    @property
    def client(self):
        """Lazy Mixpanel client initialization."""
        if self._client is None:
            try:
                from mixpanel import Mixpanel

                self._client = Mixpanel(self.token)
            except ImportError:
                raise ImportError(
                    "mixpanel is required for MixpanelBackend. Install with: uv add mixpanel"
                )
        return self._client

    def _get_distinct_id(self, event_data: dict) -> str:
        """Get distinct ID for Mixpanel."""
        return (
            event_data.get("user_id")
            or event_data.get("anonymous_id")
            or str(__import__("uuid").uuid4())
        )

    def track_event(self, event_data: dict) -> str:
        """Track event to Mixpanel."""
        distinct_id = self._get_distinct_id(event_data)

        properties = {
            **event_data.get("properties", {}),
            **event_data.get("context", {}),
        }

        if event_data.get("timestamp"):
            properties["time"] = int(event_data["timestamp"].timestamp())

        self.client.track(
            distinct_id=distinct_id,
            event_name=event_data["name"],
            properties=properties,
        )

        return event_data.get("id", "")

    def track_events_batch(self, events: list[dict]) -> list[str]:
        """Track multiple events."""
        ids = []
        for event in events:
            ids.append(self.track_event(event))
        return ids

    def track_page_view(self, page_view_data: dict) -> str:
        """Track page view to Mixpanel."""
        distinct_id = self._get_distinct_id(page_view_data)

        self.client.track(
            distinct_id=distinct_id,
            event_name="Page View",
            properties={
                "path": page_view_data["path"],
                "url": page_view_data.get("url", ""),
                "title": page_view_data.get("title", ""),
                "referrer": page_view_data.get("referrer"),
            },
        )

        return page_view_data.get("id", "")

    def track_page_views_batch(self, page_views: list[dict]) -> list[str]:
        """Track multiple page views."""
        ids = []
        for pv in page_views:
            ids.append(self.track_page_view(pv))
        return ids

    def identify(
        self,
        user_id: str,
        anonymous_id: str = "",
        traits: dict | None = None,
        context: dict | None = None,
        timestamp: datetime | None = None,
    ):
        """Identify user in Mixpanel."""
        self.client.people_set(user_id, traits or {})

        if anonymous_id:
            # Create alias
            self.client.alias(user_id, anonymous_id)

    def alias(self, previous_id: str, user_id: str):
        """Create an alias in Mixpanel."""
        self.client.alias(user_id, previous_id)

    def group(
        self,
        user_id: str,
        group_id: str,
        traits: dict | None = None,
    ):
        """Associate user with a group in Mixpanel."""
        # Mixpanel uses group analytics
        if traits:
            self.client.group_set(group_id, "company", traits)
        self.client.people_set(user_id, {"$group_id": group_id})


class PostHogBackend(AnalyticsBackend):
    """
    PostHog analytics backend.

    Open source product analytics.
    """

    def __init__(
        self,
        api_key: str | None = None,
        host: str = "https://app.posthog.com",
    ):
        self.api_key = api_key or getattr(settings, "POSTHOG_API_KEY", None)
        self.host = host or getattr(settings, "POSTHOG_HOST", "https://app.posthog.com")

        if not self.api_key:
            raise ValueError("PostHog API key is required")

        self._client = None

    @property
    def client(self):
        """Lazy PostHog client initialization."""
        if self._client is None:
            try:
                from posthog import Posthog

                self._client = Posthog(
                    project_api_key=self.api_key,
                    host=self.host,
                )
            except ImportError:
                raise ImportError(
                    "posthog is required for PostHogBackend. Install with: uv add posthog"
                )
        return self._client

    def _get_distinct_id(self, data: dict) -> str:
        """Get distinct ID for PostHog."""
        return data.get("user_id") or data.get("anonymous_id") or str(__import__("uuid").uuid4())

    def track_event(self, event_data: dict) -> str:
        """Track event to PostHog."""
        distinct_id = self._get_distinct_id(event_data)

        self.client.capture(
            distinct_id=distinct_id,
            event=event_data["name"],
            properties={
                **event_data.get("properties", {}),
                **event_data.get("context", {}),
            },
            timestamp=event_data.get("timestamp"),
        )

        return event_data.get("id", "")

    def track_events_batch(self, events: list[dict]) -> list[str]:
        """Track multiple events."""
        ids = []
        for event in events:
            ids.append(self.track_event(event))
        return ids

    def track_page_view(self, page_view_data: dict) -> str:
        """Track page view to PostHog."""
        distinct_id = self._get_distinct_id(page_view_data)

        self.client.capture(
            distinct_id=distinct_id,
            event="$pageview",
            properties={
                "$current_url": page_view_data.get("url", ""),
                "$pathname": page_view_data["path"],
                "$title": page_view_data.get("title", ""),
                "$referrer": page_view_data.get("referrer"),
            },
            timestamp=page_view_data.get("timestamp"),
        )

        return page_view_data.get("id", "")

    def track_page_views_batch(self, page_views: list[dict]) -> list[str]:
        """Track multiple page views."""
        ids = []
        for pv in page_views:
            ids.append(self.track_page_view(pv))
        return ids

    def identify(
        self,
        user_id: str,
        anonymous_id: str = "",
        traits: dict | None = None,
        context: dict | None = None,
        timestamp: datetime | None = None,
    ):
        """Identify user in PostHog."""
        self.client.identify(
            distinct_id=user_id,
            properties=traits or {},
        )

        if anonymous_id:
            self.client.alias(previous_id=anonymous_id, distinct_id=user_id)

    def alias(self, previous_id: str, user_id: str):
        """Create an alias in PostHog."""
        self.client.alias(previous_id=previous_id, distinct_id=user_id)

    def group(
        self,
        user_id: str,
        group_id: str,
        traits: dict | None = None,
    ):
        """Associate user with a group in PostHog."""
        self.client.group_identify(
            group_type="company",
            group_key=group_id,
            properties=traits or {},
        )

    def close(self):
        """Flush and close PostHog client."""
        if self._client:
            self._client.flush()


class AmplitudeBackend(AnalyticsBackend):
    """
    Amplitude analytics backend.

    Product analytics platform.
    """

    def __init__(
        self,
        api_key: str | None = None,
    ):
        self.api_key = api_key or getattr(settings, "AMPLITUDE_API_KEY", None)

        if not self.api_key:
            raise ValueError("Amplitude API key is required")

        self._client = None

    @property
    def client(self):
        """Lazy Amplitude client initialization."""
        if self._client is None:
            try:
                from amplitude import Amplitude

                self._client = Amplitude(self.api_key)
            except ImportError:
                raise ImportError(
                    "amplitude-analytics is required for AmplitudeBackend. "
                    "Install with: uv add amplitude-analytics"
                )
        return self._client

    def _get_user_id(self, data: dict) -> tuple[str | None, str | None]:
        """Get user_id and device_id for Amplitude."""
        user_id = data.get("user_id")
        device_id = data.get("anonymous_id") or str(__import__("uuid").uuid4())
        return user_id, device_id

    def track_event(self, event_data: dict) -> str:
        """Track event to Amplitude."""
        from amplitude import BaseEvent

        user_id, device_id = self._get_user_id(event_data)

        event = BaseEvent(
            event_type=event_data["name"],
            user_id=user_id,
            device_id=device_id,
            event_properties={
                **event_data.get("properties", {}),
                **event_data.get("context", {}),
            },
            time=int(event_data.get("timestamp", timezone.now()).timestamp() * 1000),
        )

        self.client.track(event)
        return event_data.get("id", "")

    def track_events_batch(self, events: list[dict]) -> list[str]:
        """Track multiple events."""
        ids = []
        for event in events:
            ids.append(self.track_event(event))
        return ids

    def track_page_view(self, page_view_data: dict) -> str:
        """Track page view to Amplitude."""
        from amplitude import BaseEvent

        user_id, device_id = self._get_user_id(page_view_data)

        event = BaseEvent(
            event_type="Page View",
            user_id=user_id,
            device_id=device_id,
            event_properties={
                "path": page_view_data["path"],
                "url": page_view_data.get("url", ""),
                "title": page_view_data.get("title", ""),
                "referrer": page_view_data.get("referrer"),
            },
            time=int(page_view_data.get("timestamp", timezone.now()).timestamp() * 1000),
        )

        self.client.track(event)
        return page_view_data.get("id", "")

    def track_page_views_batch(self, page_views: list[dict]) -> list[str]:
        """Track multiple page views."""
        ids = []
        for pv in page_views:
            ids.append(self.track_page_view(pv))
        return ids

    def identify(
        self,
        user_id: str,
        anonymous_id: str = "",
        traits: dict | None = None,
        context: dict | None = None,
        timestamp: datetime | None = None,
    ):
        """Identify user in Amplitude."""
        from amplitude import Identify

        identify_obj = Identify()
        for key, value in (traits or {}).items():
            identify_obj.set(key, value)

        self.client.identify(identify_obj, user_id=user_id, device_id=anonymous_id)

    def alias(self, previous_id: str, user_id: str):
        """Amplitude uses user_id mapping, not aliases."""

    def group(
        self,
        user_id: str,
        group_id: str,
        traits: dict | None = None,
    ):
        """Associate user with a group in Amplitude."""
        from amplitude import Identify

        # Set group properties
        group_identify = Identify()
        for key, value in (traits or {}).items():
            group_identify.set(key, value)

        self.client.group_identify(
            group_type="company",
            group_name=group_id,
            identify_obj=group_identify,
        )

    def close(self):
        """Flush and close Amplitude client."""
        if self._client:
            self._client.flush()


# Backend registry
_backends: dict[str, type[AnalyticsBackend]] = {
    "database": DatabaseBackend,
    "redis": RedisBackend,
    "segment": SegmentBackend,
    "mixpanel": MixpanelBackend,
    "posthog": PostHogBackend,
    "amplitude": AmplitudeBackend,
}

_default_backend: AnalyticsBackend | None = None


def register_backend(name: str, backend_class: type[AnalyticsBackend]):
    """Register a custom backend."""
    _backends[name] = backend_class


def get_backend(name: str | None = None, **kwargs) -> AnalyticsBackend:
    """
    Get an analytics backend.

    Args:
        name: Backend name (database, redis, segment, mixpanel, posthog, amplitude)
        **kwargs: Backend-specific configuration

    Returns:
        AnalyticsBackend instance
    """
    global _default_backend

    config = getattr(settings, "DJANGO_MATT_ANALYTICS", {})

    if name is None:
        # Return cached default backend
        if _default_backend is not None:
            return _default_backend

        name = config.get("BACKEND", "database")

    if name not in _backends:
        raise ValueError(f"Unknown backend: {name}. Available: {list(_backends.keys())}")

    backend_class = _backends[name]

    # Get backend-specific settings
    backend_settings = config.get("BACKEND_SETTINGS", {}).get(name, {})
    merged_config = {**backend_settings, **kwargs}

    backend = backend_class(**merged_config)

    # Cache as default
    if name == config.get("BACKEND", "database"):
        _default_backend = backend

    return backend


def reset_default_backend():
    """Reset the cached default backend."""
    global _default_backend
    if _default_backend:
        _default_backend.close()
        _default_backend = None


__all__ = [
    "AnalyticsBackend",
    "DatabaseBackend",
    "RedisBackend",
    "SegmentBackend",
    "MixpanelBackend",
    "PostHogBackend",
    "AmplitudeBackend",
    "get_backend",
    "register_backend",
    "reset_default_backend",
]
