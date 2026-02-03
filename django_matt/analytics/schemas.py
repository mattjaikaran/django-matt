"""
Pydantic schemas for analytics API.

Provides request/response schemas for the analytics REST API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class EventCategoryEnum(str, Enum):
    """Categories for events."""

    PAGE_VIEW = "page_view"
    USER_ACTION = "user_action"
    SYSTEM = "system"
    CONVERSION = "conversion"
    ERROR = "error"
    CUSTOM = "custom"


class SessionStatusEnum(str, Enum):
    """Status of a session."""

    ACTIVE = "active"
    ENDED = "ended"
    EXPIRED = "expired"


class MetricPeriodEnum(str, Enum):
    """Time periods for metrics."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class FunnelStepMatchTypeEnum(str, Enum):
    """Match types for funnel steps."""

    EVENT = "event"
    PAGE_VIEW = "page_view"
    CUSTOM = "custom"


# -----------------------------------------------------------------------------
# Event Schemas
# -----------------------------------------------------------------------------


class EventContext(BaseModel):
    """Contextual information for an event."""

    page_url: str = Field(default="", description="Current page URL")
    page_title: str = Field(default="", description="Current page title")
    page_path: str = Field(default="", description="Current page path")
    locale: str = Field(default="", description="User locale")
    timezone: str = Field(default="", description="User timezone")
    screen_width: int | None = Field(default=None, description="Screen width")
    screen_height: int | None = Field(default=None, description="Screen height")
    viewport_width: int | None = Field(default=None, description="Viewport width")
    viewport_height: int | None = Field(default=None, description="Viewport height")
    device_type: str = Field(default="", description="Device type (desktop/mobile/tablet)")
    browser: str = Field(default="", description="Browser name")
    os: str = Field(default="", description="Operating system")
    referrer: str | None = Field(default=None, description="Referrer URL")


class TrackEventRequest(BaseModel):
    """Request to track a custom event."""

    name: str = Field(..., min_length=1, max_length=255, description="Event name")
    properties: dict[str, Any] = Field(default_factory=dict, description="Event properties")
    context: EventContext = Field(default_factory=EventContext, description="Event context")
    timestamp: datetime | None = Field(default=None, description="Event timestamp (defaults to now)")
    category: EventCategoryEnum = Field(default=EventCategoryEnum.CUSTOM, description="Event category")
    anonymous_id: str = Field(default="", description="Anonymous user ID")
    session_id: str = Field(default="", description="Session ID")

    # Revenue tracking
    revenue: float | None = Field(default=None, description="Revenue amount")
    currency: str = Field(default="", description="Currency code (USD, EUR, etc.)")

    # Element tracking
    element_id: str = Field(default="", description="DOM element ID")
    element_class: str = Field(default="", description="DOM element class")
    element_text: str = Field(default="", description="DOM element text")


class TrackEventResponse(BaseModel):
    """Response after tracking an event."""

    id: str
    name: str
    timestamp: datetime
    success: bool = True


class EventResponse(BaseModel):
    """Full event response."""

    id: str
    name: str
    category: str
    properties: dict[str, Any]
    context: dict[str, Any]
    timestamp: datetime
    user_id: str | None = None
    session_id: str | None = None
    anonymous_id: str = ""
    page_url: str = ""
    page_title: str = ""
    revenue: float | None = None
    currency: str = ""

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """List of events response."""

    items: list[EventResponse]
    total: int
    page: int = 1
    page_size: int = 50


# -----------------------------------------------------------------------------
# Page View Schemas
# -----------------------------------------------------------------------------


class TrackPageViewRequest(BaseModel):
    """Request to track a page view."""

    path: str = Field(..., max_length=2000, description="Page path")
    url: str = Field(..., max_length=2000, description="Full URL")
    title: str = Field(default="", max_length=500, description="Page title")
    referrer: str | None = Field(default=None, description="Referrer URL")
    timestamp: datetime | None = Field(default=None)
    anonymous_id: str = Field(default="", description="Anonymous user ID")
    session_id: str = Field(default="", description="Session ID")

    # Engagement
    time_on_page: int | None = Field(default=None, description="Time on previous page (seconds)")
    scroll_depth: int = Field(default=0, ge=0, le=100, description="Scroll depth percentage")

    # Performance
    load_time_ms: int | None = Field(default=None, description="Page load time (ms)")
    dom_interactive_ms: int | None = Field(default=None)
    dom_complete_ms: int | None = Field(default=None)


class TrackPageViewResponse(BaseModel):
    """Response after tracking a page view."""

    id: str
    path: str
    timestamp: datetime
    success: bool = True


class PageViewResponse(BaseModel):
    """Full page view response."""

    id: str
    path: str
    url: str
    title: str
    timestamp: datetime
    user_id: str | None = None
    session_id: str | None = None
    referrer: str | None = None
    time_on_page: int | None = None
    scroll_depth: int = 0
    is_bounce: bool = False
    is_entrance: bool = False
    is_exit: bool = False

    class Config:
        from_attributes = True


class PageViewListResponse(BaseModel):
    """List of page views response."""

    items: list[PageViewResponse]
    total: int
    page: int = 1
    page_size: int = 50


# -----------------------------------------------------------------------------
# Identity Schemas
# -----------------------------------------------------------------------------


class IdentifyRequest(BaseModel):
    """Request to identify a user."""

    user_id: str | None = Field(default=None, description="User ID to identify")
    anonymous_id: str = Field(..., description="Anonymous ID to link")
    traits: dict[str, Any] = Field(default_factory=dict, description="User traits")
    context: EventContext = Field(default_factory=EventContext)
    timestamp: datetime | None = Field(default=None)


class IdentifyResponse(BaseModel):
    """Response after identifying a user."""

    user_id: str
    anonymous_id: str
    success: bool = True
    message: str = "User identified"


# -----------------------------------------------------------------------------
# Session Schemas
# -----------------------------------------------------------------------------


class SessionResponse(BaseModel):
    """Session response."""

    id: str
    session_id: str
    user_id: str | None = None
    anonymous_id: str = ""
    status: str
    started_at: datetime
    last_activity_at: datetime
    ended_at: datetime | None = None
    device_type: str = ""
    browser: str = ""
    os: str = ""
    country: str = ""
    city: str = ""
    referrer: str | None = None
    landing_page: str = ""
    exit_page: str = ""
    page_views: int = 0
    events_count: int = 0
    duration_seconds: int = 0
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """List of sessions response."""

    items: list[SessionResponse]
    total: int
    page: int = 1
    page_size: int = 50


# -----------------------------------------------------------------------------
# Metrics Schemas
# -----------------------------------------------------------------------------


class MetricsQuery(BaseModel):
    """Query parameters for metrics."""

    period: MetricPeriodEnum = Field(default=MetricPeriodEnum.DAY)
    start_date: datetime | None = Field(default=None)
    end_date: datetime | None = Field(default=None)
    timezone: str = Field(default="UTC")
    group_by: list[str] = Field(default_factory=list, description="Fields to group by")
    filters: dict[str, Any] = Field(default_factory=dict, description="Filters to apply")


class EventMetrics(BaseModel):
    """Aggregated event metrics."""

    total_events: int = 0
    unique_users: int = 0
    events_by_name: dict[str, int] = Field(default_factory=dict)
    events_by_category: dict[str, int] = Field(default_factory=dict)
    events_over_time: list[dict[str, Any]] = Field(default_factory=list)


class PageMetrics(BaseModel):
    """Aggregated page view metrics."""

    total_page_views: int = 0
    unique_visitors: int = 0
    avg_time_on_page: float = 0
    bounce_rate: float = 0
    top_pages: list[dict[str, Any]] = Field(default_factory=list)
    pages_over_time: list[dict[str, Any]] = Field(default_factory=list)


class SessionMetrics(BaseModel):
    """Aggregated session metrics."""

    total_sessions: int = 0
    unique_users: int = 0
    avg_session_duration: float = 0
    avg_pages_per_session: float = 0
    bounce_rate: float = 0
    sessions_by_device: dict[str, int] = Field(default_factory=dict)
    sessions_by_country: dict[str, int] = Field(default_factory=dict)
    sessions_over_time: list[dict[str, Any]] = Field(default_factory=list)


class TrafficMetrics(BaseModel):
    """Traffic source metrics."""

    total_visits: int = 0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_medium: dict[str, int] = Field(default_factory=dict)
    by_campaign: dict[str, int] = Field(default_factory=dict)
    by_referrer: dict[str, int] = Field(default_factory=dict)


class RevenueMetrics(BaseModel):
    """Revenue metrics."""

    total_revenue: float = 0
    transaction_count: int = 0
    avg_order_value: float = 0
    revenue_by_day: list[dict[str, Any]] = Field(default_factory=list)
    top_products: list[dict[str, Any]] = Field(default_factory=list)


class DashboardMetrics(BaseModel):
    """Combined dashboard metrics."""

    events: EventMetrics
    pages: PageMetrics
    sessions: SessionMetrics
    traffic: TrafficMetrics
    revenue: RevenueMetrics | None = None


# -----------------------------------------------------------------------------
# Funnel Schemas
# -----------------------------------------------------------------------------


class FunnelStepCreate(BaseModel):
    """Schema for creating a funnel step."""

    name: str = Field(..., max_length=255)
    order: int = Field(..., ge=1)
    match_type: FunnelStepMatchTypeEnum = Field(default=FunnelStepMatchTypeEnum.EVENT)
    event_name: str = Field(default="")
    page_path: str = Field(default="")
    conditions: dict[str, Any] = Field(default_factory=dict)
    timeout_hours: int | None = Field(default=None)


class FunnelStepResponse(BaseModel):
    """Funnel step response."""

    id: str
    name: str
    order: int
    match_type: str
    event_name: str = ""
    page_path: str = ""
    conditions: dict[str, Any] = {}
    timeout_hours: int | None = None

    class Config:
        from_attributes = True


class FunnelCreate(BaseModel):
    """Schema for creating a funnel."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    conversion_window_hours: int = Field(default=168, ge=1)
    strict_order: bool = Field(default=True)
    steps: list[FunnelStepCreate] = Field(default_factory=list)


class FunnelUpdate(BaseModel):
    """Schema for updating a funnel."""

    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    conversion_window_hours: int | None = Field(default=None, ge=1)
    strict_order: bool | None = None


class FunnelResponse(BaseModel):
    """Funnel response."""

    id: str
    name: str
    description: str = ""
    is_active: bool = True
    conversion_window_hours: int = 168
    strict_order: bool = True
    steps: list[FunnelStepResponse] = []
    step_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FunnelListResponse(BaseModel):
    """List of funnels response."""

    items: list[FunnelResponse]
    total: int


class FunnelStepAnalytics(BaseModel):
    """Analytics for a single funnel step."""

    step_order: int
    step_name: str
    visitors: int
    conversion_rate: float
    drop_off_rate: float
    avg_time_to_complete: float | None = None


class FunnelAnalytics(BaseModel):
    """Funnel analytics response."""

    funnel_id: str
    funnel_name: str
    period_start: datetime
    period_end: datetime
    total_started: int
    total_converted: int
    overall_conversion_rate: float
    avg_conversion_time: float | None = None
    steps: list[FunnelStepAnalytics]


# -----------------------------------------------------------------------------
# Cohort Schemas
# -----------------------------------------------------------------------------


class CohortQuery(BaseModel):
    """Query for cohort analysis."""

    cohort_type: Literal["signup_date", "first_event", "first_purchase"] = "signup_date"
    cohort_period: MetricPeriodEnum = MetricPeriodEnum.WEEK
    retention_period: MetricPeriodEnum = MetricPeriodEnum.WEEK
    start_date: datetime
    end_date: datetime
    event_name: str | None = Field(default=None, description="Event to measure retention by")


class CohortRow(BaseModel):
    """Single cohort row."""

    cohort: str
    cohort_start: datetime
    cohort_size: int
    retention: list[float] = Field(description="Retention percentages by period")


class CohortAnalysis(BaseModel):
    """Cohort analysis response."""

    query: CohortQuery
    cohorts: list[CohortRow]
    periods: list[str] = Field(description="Period labels")


# -----------------------------------------------------------------------------
# Real-time Schemas
# -----------------------------------------------------------------------------


class RealtimeMetrics(BaseModel):
    """Real-time metrics (last 30 minutes)."""

    active_users: int = 0
    active_sessions: int = 0
    page_views_per_minute: float = 0
    events_per_minute: float = 0
    top_pages: list[dict[str, Any]] = Field(default_factory=list)
    top_events: list[dict[str, Any]] = Field(default_factory=list)
    users_by_country: dict[str, int] = Field(default_factory=dict)
    users_by_device: dict[str, int] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Utility Schemas
# -----------------------------------------------------------------------------


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
    code: str = "error"
    errors: list[dict[str, Any]] = Field(default_factory=list)


class BatchTrackRequest(BaseModel):
    """Batch tracking request."""

    events: list[TrackEventRequest] = Field(default_factory=list)
    page_views: list[TrackPageViewRequest] = Field(default_factory=list)


class BatchTrackResponse(BaseModel):
    """Batch tracking response."""

    events_tracked: int = 0
    page_views_tracked: int = 0
    errors: list[str] = Field(default_factory=list)
    success: bool = True


__all__ = [
    # Enums
    "EventCategoryEnum",
    "SessionStatusEnum",
    "MetricPeriodEnum",
    "FunnelStepMatchTypeEnum",
    # Event schemas
    "EventContext",
    "TrackEventRequest",
    "TrackEventResponse",
    "EventResponse",
    "EventListResponse",
    # Page view schemas
    "TrackPageViewRequest",
    "TrackPageViewResponse",
    "PageViewResponse",
    "PageViewListResponse",
    # Identity schemas
    "IdentifyRequest",
    "IdentifyResponse",
    # Session schemas
    "SessionResponse",
    "SessionListResponse",
    # Metrics schemas
    "MetricsQuery",
    "EventMetrics",
    "PageMetrics",
    "SessionMetrics",
    "TrafficMetrics",
    "RevenueMetrics",
    "DashboardMetrics",
    # Funnel schemas
    "FunnelStepCreate",
    "FunnelStepResponse",
    "FunnelCreate",
    "FunnelUpdate",
    "FunnelResponse",
    "FunnelListResponse",
    "FunnelStepAnalytics",
    "FunnelAnalytics",
    # Cohort schemas
    "CohortQuery",
    "CohortRow",
    "CohortAnalysis",
    # Real-time schemas
    "RealtimeMetrics",
    # Utility schemas
    "MessageResponse",
    "ErrorResponse",
    "BatchTrackRequest",
    "BatchTrackResponse",
]
