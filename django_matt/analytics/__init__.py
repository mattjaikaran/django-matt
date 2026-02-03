"""
Django Matt Analytics - Comprehensive event tracking and analytics system.

A privacy-focused analytics system with support for:
- Event tracking with batched writes
- Page view tracking
- Session management
- User identification and aliasing
- Multiple storage backends (Database, Redis, Segment, Mixpanel, PostHog, Amplitude)
- Funnel analysis
- Cohort analysis
- Real-time dashboards
- GDPR-compliant data anonymization

Configuration in settings.py:

    DJANGO_MATT_ANALYTICS = {
        "BACKEND": "database",  # or "redis", "segment", "mixpanel", "posthog", "amplitude"
        "BATCH_SIZE": 100,
        "BATCH_TIMEOUT": 5.0,
        "ANONYMIZE_IP": False,
        "RESPECT_DNT": True,

        "BACKEND_SETTINGS": {
            "database": {
                "batch_create_size": 1000,
            },
            "redis": {
                "redis_url": "redis://localhost:6379/0",
                "key_prefix": "analytics:",
                "buffer_size": 1000,
            },
            "segment": {
                "write_key": "YOUR_SEGMENT_WRITE_KEY",
            },
            "mixpanel": {
                "token": "YOUR_MIXPANEL_TOKEN",
            },
            "posthog": {
                "api_key": "YOUR_POSTHOG_API_KEY",
                "host": "https://app.posthog.com",
            },
            "amplitude": {
                "api_key": "YOUR_AMPLITUDE_API_KEY",
            },
        },

        "MIDDLEWARE": {
            "track_sessions": True,
            "track_page_views": True,
            "track_timing": True,
            "session_cookie_name": "_matt_session",
            "session_timeout_minutes": 30,
            "exclude_paths": ["/health", "/static"],
            "exclude_bots": True,
            "anonymize_ip": False,
            "respect_dnt": True,
        },
    }

    MIDDLEWARE = [
        ...
        'django_matt.analytics.AnalyticsMiddleware',
        ...
    ]

Example usage:

    # Track events with the tracker
    from django_matt.analytics import track_event, track_page_view, identify

    track_event("button_click", properties={"button_id": "signup"})
    track_page_view("/pricing")
    identify(user=request.user, traits={"plan": "pro"})

    # Using the tracker directly
    from django_matt.analytics import EventTracker

    tracker = EventTracker()
    tracker.track_event("purchase", properties={"amount": 99.99}, user=request.user)

    # With batch context
    with tracker.batch() as batch:
        batch.track_event("event1", {"key": "value"})
        batch.track_event("event2", {"key": "value"})

    # Using decorators
    from django_matt.analytics import track_event_decorator, track_timing

    @track_event_decorator("api_called")
    async def my_endpoint(request):
        ...

    @track_timing("db_query")
    def expensive_query():
        ...

    # Register API controllers
    from django_matt.analytics import AnalyticsController, MetricsController, FunnelController

    api.register_controller(AnalyticsController, prefix="/analytics")
    api.register_controller(MetricsController, prefix="/analytics")
    api.register_controller(FunnelController, prefix="/analytics")
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


# Lazy imports to avoid circular dependencies
def __getattr__(name: str):
    """Lazy import handler."""
    # Models
    if name == "AnalyticsSession":
        from django_matt.analytics.models import AnalyticsSession

        return AnalyticsSession
    elif name == "AnalyticsEvent":
        from django_matt.analytics.models import AnalyticsEvent

        return AnalyticsEvent
    elif name == "PageView":
        from django_matt.analytics.models import PageView

        return PageView
    elif name == "UserMetric":
        from django_matt.analytics.models import UserMetric

        return UserMetric
    elif name == "Funnel":
        from django_matt.analytics.models import Funnel

        return Funnel
    elif name == "FunnelStep":
        from django_matt.analytics.models import FunnelStep

        return FunnelStep
    elif name == "FunnelConversion":
        from django_matt.analytics.models import FunnelConversion

        return FunnelConversion
    elif name == "UserIdentity":
        from django_matt.analytics.models import UserIdentity

        return UserIdentity
    elif name == "EventCategory":
        from django_matt.analytics.models import EventCategory

        return EventCategory
    elif name == "SessionStatus":
        from django_matt.analytics.models import SessionStatus

        return SessionStatus
    elif name == "AnonymizationLevel":
        from django_matt.analytics.models import AnonymizationLevel

        return AnonymizationLevel

    # Tracker
    elif name == "EventTracker":
        from django_matt.analytics.tracker import EventTracker

        return EventTracker
    elif name == "get_tracker":
        from django_matt.analytics.tracker import get_tracker

        return get_tracker

    # Backends
    elif name == "AnalyticsBackend":
        from django_matt.analytics.backends import AnalyticsBackend

        return AnalyticsBackend
    elif name == "DatabaseBackend":
        from django_matt.analytics.backends import DatabaseBackend

        return DatabaseBackend
    elif name == "RedisBackend":
        from django_matt.analytics.backends import RedisBackend

        return RedisBackend
    elif name == "SegmentBackend":
        from django_matt.analytics.backends import SegmentBackend

        return SegmentBackend
    elif name == "MixpanelBackend":
        from django_matt.analytics.backends import MixpanelBackend

        return MixpanelBackend
    elif name == "PostHogBackend":
        from django_matt.analytics.backends import PostHogBackend

        return PostHogBackend
    elif name == "AmplitudeBackend":
        from django_matt.analytics.backends import AmplitudeBackend

        return AmplitudeBackend
    elif name == "get_backend":
        from django_matt.analytics.backends import get_backend

        return get_backend

    # Middleware
    elif name == "AnalyticsMiddleware":
        from django_matt.analytics.middleware import AnalyticsMiddleware

        return AnalyticsMiddleware
    elif name == "AsyncAnalyticsMiddleware":
        from django_matt.analytics.middleware import AsyncAnalyticsMiddleware

        return AsyncAnalyticsMiddleware

    # Controllers
    elif name == "AnalyticsController":
        from django_matt.analytics.controllers import AnalyticsController

        return AnalyticsController
    elif name == "MetricsController":
        from django_matt.analytics.controllers import MetricsController

        return MetricsController
    elif name == "FunnelController":
        from django_matt.analytics.controllers import FunnelController

        return FunnelController

    # Decorators
    elif name == "track_event_decorator":
        from django_matt.analytics.decorators import track_event

        return track_event
    elif name == "track_timing":
        from django_matt.analytics.decorators import track_timing

        return track_timing
    elif name == "track_page_view_decorator":
        from django_matt.analytics.decorators import track_page_view

        return track_page_view
    elif name == "TrackedMixin":
        from django_matt.analytics.decorators import TrackedMixin

        return TrackedMixin

    # Aggregations
    elif name == "Aggregator":
        from django_matt.analytics.aggregations import Aggregator

        return Aggregator
    elif name == "get_aggregator":
        from django_matt.analytics.aggregations import get_aggregator

        return get_aggregator

    # Tasks
    elif name == "create_daily_rollups":
        from django_matt.analytics.tasks import create_daily_rollups

        return create_daily_rollups
    elif name == "create_weekly_rollups":
        from django_matt.analytics.tasks import create_weekly_rollups

        return create_weekly_rollups
    elif name == "create_monthly_rollups":
        from django_matt.analytics.tasks import create_monthly_rollups

        return create_monthly_rollups
    elif name == "expire_sessions":
        from django_matt.analytics.tasks import expire_sessions

        return expire_sessions
    elif name == "cleanup_old_data":
        from django_matt.analytics.tasks import cleanup_old_data

        return cleanup_old_data
    elif name == "anonymize_old_sessions":
        from django_matt.analytics.tasks import anonymize_old_sessions

        return anonymize_old_sessions
    elif name == "process_funnel_conversions":
        from django_matt.analytics.tasks import process_funnel_conversions

        return process_funnel_conversions

    raise AttributeError(f"module 'django_matt.analytics' has no attribute {name!r}")


# Convenience functions that use the default tracker


def track_event(
    name: str,
    properties: dict[str, Any] | None = None,
    user: "AbstractUser | None" = None,
    anonymous_id: str = "",
    category: str = "custom",
    **kwargs,
) -> str:
    """
    Track a custom event.

    This is a convenience function that uses the default tracker.

    Args:
        name: Event name (e.g., "button_click", "purchase_completed")
        properties: Event-specific properties
        user: Associated user
        anonymous_id: Anonymous user identifier
        category: Event category
        **kwargs: Additional arguments passed to tracker

    Returns:
        Event ID

    Example:
        track_event("signup_completed", properties={"plan": "pro"})
        track_event("button_click", {"button_id": "cta"}, user=request.user)
    """
    from django_matt.analytics.tracker import get_tracker

    tracker = get_tracker()
    return tracker.track_event(
        name=name,
        properties=properties,
        user=user,
        anonymous_id=anonymous_id,
        category=category,
        **kwargs,
    )


def track_page_view(
    path: str,
    url: str = "",
    title: str = "",
    user: "AbstractUser | None" = None,
    anonymous_id: str = "",
    **kwargs,
) -> str:
    """
    Track a page view.

    This is a convenience function that uses the default tracker.

    Args:
        path: URL path
        url: Full URL
        title: Page title
        user: Associated user
        anonymous_id: Anonymous user identifier
        **kwargs: Additional arguments passed to tracker

    Returns:
        Page view ID

    Example:
        track_page_view("/pricing", title="Pricing Page")
        track_page_view("/dashboard", user=request.user)
    """
    from django_matt.analytics.tracker import get_tracker

    tracker = get_tracker()
    return tracker.track_page_view(
        path=path,
        url=url,
        title=title,
        user=user,
        anonymous_id=anonymous_id,
        **kwargs,
    )


def identify(
    user: "AbstractUser",
    anonymous_id: str = "",
    traits: dict[str, Any] | None = None,
    **kwargs,
):
    """
    Identify a user and link anonymous sessions/events.

    Call this when a user signs up or logs in to link their
    anonymous activity to their user account.

    Args:
        user: User to identify
        anonymous_id: Anonymous ID to link to user
        traits: User traits (e.g., plan, role)
        **kwargs: Additional arguments passed to tracker

    Example:
        identify(request.user, anonymous_id=session_id, traits={"plan": "pro"})
    """
    from django_matt.analytics.tracker import get_tracker

    tracker = get_tracker()
    tracker.identify(
        user=user,
        anonymous_id=anonymous_id,
        traits=traits,
        **kwargs,
    )


__all__ = [
    # Convenience functions
    "track_event",
    "track_page_view",
    "identify",
    # Models
    "AnalyticsSession",
    "AnalyticsEvent",
    "PageView",
    "UserMetric",
    "Funnel",
    "FunnelStep",
    "FunnelConversion",
    "UserIdentity",
    "EventCategory",
    "SessionStatus",
    "AnonymizationLevel",
    # Tracker
    "EventTracker",
    "get_tracker",
    # Backends
    "AnalyticsBackend",
    "DatabaseBackend",
    "RedisBackend",
    "SegmentBackend",
    "MixpanelBackend",
    "PostHogBackend",
    "AmplitudeBackend",
    "get_backend",
    # Middleware
    "AnalyticsMiddleware",
    "AsyncAnalyticsMiddleware",
    # Controllers
    "AnalyticsController",
    "MetricsController",
    "FunnelController",
    # Decorators
    "track_event_decorator",
    "track_timing",
    "track_page_view_decorator",
    "TrackedMixin",
    # Aggregations
    "Aggregator",
    "get_aggregator",
    # Tasks
    "create_daily_rollups",
    "create_weekly_rollups",
    "create_monthly_rollups",
    "expire_sessions",
    "cleanup_old_data",
    "anonymize_old_sessions",
    "process_funnel_conversions",
]
