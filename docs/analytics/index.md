# Analytics

Event tracking, session management, page view analytics, funnel analysis, cohort retention, and real-time metrics. Supports multiple backends: database, Redis, Segment, Mixpanel, PostHog, and Amplitude.

## Quick Start

```python
from django_matt.analytics import track_event, track_page_view, identify

# Track a custom event
track_event(
    "button_click",
    properties={"button_id": "signup", "page": "/pricing"},
    user=request.user,
    request=request,
)

# Track a page view
track_page_view(
    "/pricing",
    user=request.user,
    referrer="https://google.com",
    request=request,
)

# Identify a user (links anonymous sessions)
identify(user=request.user, traits={"plan": "pro", "company": "Acme"})
```

## Configuration

```python
# settings.py
DJANGO_MATT_ANALYTICS = {
    # Backend: "database", "redis", "segment", "mixpanel", "posthog", "amplitude"
    "BACKEND": "database",

    # Batching
    "BATCH_SIZE": 100,       # Events buffered before flush
    "BATCH_TIMEOUT": 5.0,    # Seconds before auto-flush

    # Privacy
    "ANONYMIZE_IP": False,   # Hash IP addresses
    "RESPECT_DNT": True,     # Skip tracking if DNT header set

    # Backend-specific settings
    "BACKEND_SETTINGS": {
        "redis": {
            "redis_url": "redis://localhost:6379/0",
            "key_prefix": "analytics:",
            "buffer_size": 1000,
            "flush_interval": 60,
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

    # Middleware settings
    "MIDDLEWARE": {
        "track_sessions": True,
        "track_page_views": True,
        "track_timing": True,
        "session_cookie_name": "_matt_session",
        "session_timeout_minutes": 30,
        "exclude_paths": ["/health", "/metrics", "/static"],
        "exclude_bots": True,
        "anonymize_ip": False,
        "respect_dnt": True,
    },
}
```

### Middleware

Auto-track sessions, page views, and request timing:

```python
# settings.py
MIDDLEWARE = [
    ...
    "django_matt.analytics.AnalyticsMiddleware",      # Sync
    # or
    "django_matt.analytics.AsyncAnalyticsMiddleware",  # ASGI
]
```

The middleware sets `request.analytics_session` and `request.analytics_anonymous_id` on every tracked request.

## Key Features

### EventTracker

The main tracking interface with batching, DNT support, and IP anonymization:

```python
from django_matt.analytics.tracker import EventTracker

tracker = EventTracker(
    backend="database",
    batch_size=100,
    batch_timeout=5.0,
    anonymize_ip=True,
    respect_dnt=True,
)

# Track event with full context
event_id = tracker.track_event(
    "purchase_completed",
    properties={"product_id": "abc", "amount": 99.99},
    user=request.user,
    category="conversion",
    revenue=99.99,
    currency="USD",
    request=request,       # Auto-extracts device, IP, referrer, locale
    flush=False,           # Buffer (True = immediate write)
)

# Track page view
pv_id = tracker.track_page_view(
    path="/checkout",
    user=request.user,
    referrer="https://google.com",
    time_on_page=45,
    scroll_depth=80,
    load_time_ms=1200,
    request=request,
)

# Identify user and link anonymous sessions
tracker.identify(
    user=request.user,
    anonymous_id="anon-abc123",
    traits={"plan": "pro", "role": "admin"},
)

# Associate user with organization
tracker.group(user=request.user, group_id="org-123", traits={"name": "Acme"})

# Batch tracking
with tracker.batch() as batch:
    batch.track_event("event1", properties={"key": "value"})
    batch.track_event("event2", properties={"key": "value"})
    batch.track_page_view("/page1")
# All flushed on context exit

# Async batch
async with tracker.async_batch() as batch:
    batch.track_event("event1", properties={"key": "value"})
```

### Models

Seven models for comprehensive analytics storage:

**AnalyticsSession** -- User visit tracking with device, geo, UTM, and privacy fields:

```python
from django_matt.analytics.models import AnalyticsSession

# Get active sessions
active = AnalyticsSession.objects.active()

# Get or create from request
session, created = AnalyticsSession.objects.get_or_create_for_request(
    session_id="sess-abc",
    user=request.user,
    ip_address="1.2.3.4",
    user_agent=request.META["HTTP_USER_AGENT"],
)

# End session
session.end_session()

# Anonymize for GDPR
from django_matt.analytics.models import AnonymizationLevel
session.anonymize(level=AnonymizationLevel.PARTIAL)  # Hashes IP
session.anonymize(level=AnonymizationLevel.FULL)     # Removes all PII

# Expire inactive sessions
expired_count = AnalyticsSession.objects.expire_old_sessions(timeout_minutes=30)
```

**AnalyticsEvent** -- Generic event tracking:

```python
from django_matt.analytics.models import AnalyticsEvent

# Track via manager
event = AnalyticsEvent.objects.track(
    name="signup_completed",
    properties={"method": "google_oauth"},
    user=request.user,
    category="conversion",
)

# Query
events = AnalyticsEvent.objects.by_name("signup_completed").by_user(user)
events = AnalyticsEvent.objects.in_range(start_date, end_date)
```

**PageView** -- Page view tracking with performance metrics (load time, scroll depth, bounce detection).

**UserMetric** -- Pre-aggregated per-user metrics by period (day/week/month/year).

**Funnel / FunnelStep / FunnelConversion** -- Conversion funnel definitions and tracking.

**UserIdentity** -- Links anonymous IDs to user accounts.

### Aggregations

Compute metrics, funnels, cohorts, and rollups:

```python
from django_matt.analytics.aggregations import get_aggregator

aggregator = get_aggregator()

# Event metrics
metrics = await aggregator.get_event_metrics(start, end)
# Returns: total_events, unique_users, events_by_name, events_by_category, events_over_time

# Event metrics by name with granularity
series = await aggregator.get_event_metrics_by_name(
    "signup_completed", start, end, granularity="week"
)
# Returns: [{"date": "2024-01-15", "count": 42}, ...]

# Page metrics
pages = await aggregator.get_page_metrics(start, end)
# Returns: total_page_views, unique_visitors, avg_time_on_page, bounce_rate, top_pages

# Session metrics
sessions = await aggregator.get_session_metrics(start, end)
# Returns: total_sessions, avg_session_duration, avg_pages_per_session, sessions_by_device

# Traffic sources
traffic = await aggregator.get_traffic_metrics(start, end)
# Returns: by_source, by_medium, by_campaign, by_referrer

# Real-time metrics
realtime = await aggregator.get_realtime_metrics(minutes=30)
# Returns: active_users, active_sessions, page_views_per_minute, top_pages, top_events

# Funnel analysis
from django_matt.analytics.models import Funnel
funnel = await Funnel.objects.aget(name="Signup Funnel")
analysis = await aggregator.analyze_funnel(funnel, start, end)
# Returns: total_started, total_converted, overall_conversion_rate, per-step analytics

# Cohort retention
cohorts = await aggregator.get_cohort_retention(
    start, end,
    cohort_period="week",
    retention_period="week",
    event_name="login",  # Optional: track specific event
)

# Daily rollup (for scheduled aggregation)
result = await aggregator.create_daily_rollup(date)
```

### Backends

| Backend | Best For | Dependency |
|---------|----------|-----------|
| `DatabaseBackend` | Small/medium scale | None (Django ORM) |
| `RedisBackend` | Real-time counters, buffered writes | `uv add redis` |
| `SegmentBackend` | Forward to Segment.io | `uv add analytics-python` |
| `MixpanelBackend` | Forward to Mixpanel | `uv add mixpanel` |
| `PostHogBackend` | Open-source product analytics | `uv add posthog` |
| `AmplitudeBackend` | Product analytics | `uv add amplitude-analytics` |

Register custom backends:

```python
from django_matt.analytics.backends import register_backend, AnalyticsBackend

class CustomBackend(AnalyticsBackend):
    def track_event(self, event_data: dict) -> str: ...
    def track_events_batch(self, events: list[dict]) -> list[str]: ...
    def track_page_view(self, page_view_data: dict) -> str: ...
    def track_page_views_batch(self, page_views: list[dict]) -> list[str]: ...
    def identify(self, user_id, anonymous_id="", traits=None, context=None, timestamp=None): ...
    def alias(self, previous_id, user_id): ...
    def group(self, user_id, group_id, traits=None): ...

register_backend("custom", CustomBackend)
```

## Practical Example

Track a signup funnel with automatic session management:

```python
# settings.py
MIDDLEWARE = ["django_matt.analytics.AnalyticsMiddleware", ...]
DJANGO_MATT_ANALYTICS = {"BACKEND": "database", "MIDDLEWARE": {"track_sessions": True}}

# views.py
from django_matt.analytics import track_event, identify

async def signup_page(request):
    track_event("signup_page_viewed", request=request)
    return render(request, "signup.html")

async def signup_submit(request):
    user = await create_user(request.POST)
    identify(user=user, anonymous_id=request.analytics_anonymous_id)
    track_event("signup_completed", properties={"method": "email"}, user=user, request=request)
    return redirect("/dashboard")

async def first_purchase(request):
    track_event(
        "purchase_completed",
        properties={"product": "pro_plan"},
        user=request.user,
        revenue=29.99,
        currency="USD",
        request=request,
    )
    return JsonResponse({"status": "ok"})
```
