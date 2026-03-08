"""
Pydantic schemas for notifications app.

Includes:
- Notification schemas
- Preference schemas
- Analytics schemas
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from core.schemas import UserMiniResponse

# =============================================================================
# Notification Schemas
# =============================================================================

class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    message: str
    actor: UserMiniResponse | None = None
    resource_type: str = ""
    resource_id: str = ""
    action_url: str = ""
    action_label: str = ""
    data: dict = {}
    is_read: bool
    read_at: datetime | None = None
    email_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


class NotificationMarkReadRequest(BaseModel):
    notification_ids: list[UUID]


class NotificationMarkAllReadRequest(BaseModel):
    organization_id: UUID | None = None  # If None, mark all for user


class NotificationCountResponse(BaseModel):
    total: int
    unread: int
    by_type: dict[str, int] = {}


# =============================================================================
# Notification Preference Schemas
# =============================================================================

class NotificationTypePreference(BaseModel):
    email: bool = True
    push: bool = True
    in_app: bool = True


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool | None = None
    email_digest: str | None = None
    push_enabled: bool | None = None
    in_app_enabled: bool | None = None
    type_preferences: dict[str, NotificationTypePreference] | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: str | None = None  # "22:00"
    quiet_hours_end: str | None = None  # "08:00"
    quiet_hours_timezone: str | None = None


class NotificationPreferenceResponse(BaseModel):
    id: UUID
    email_enabled: bool
    email_digest: str
    push_enabled: bool
    in_app_enabled: bool
    type_preferences: dict = {}
    quiet_hours_enabled: bool
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    quiet_hours_timezone: str = "UTC"

    class Config:
        from_attributes = True


# =============================================================================
# Analytics Event Schemas
# =============================================================================

class AnalyticsEventCreate(BaseModel):
    event_name: str = Field(min_length=1, max_length=100)
    event_category: str = ""
    properties: dict = {}
    page_url: str = ""
    page_title: str = ""
    referrer: str = ""
    experiment_id: str = ""
    variant: str = ""


class AnalyticsEventResponse(BaseModel):
    id: UUID
    event_name: str
    event_category: str
    properties: dict
    page_url: str
    timestamp: datetime

    class Config:
        from_attributes = True


class AnalyticsBatchCreate(BaseModel):
    """Batch create analytics events."""
    events: list[AnalyticsEventCreate]
    session_id: str | None = None
    anonymous_id: str | None = None


class AnalyticsBatchResponse(BaseModel):
    processed: int
    failed: int
    errors: list[str] = []


# =============================================================================
# Analytics Dashboard Schemas
# =============================================================================

class TimeSeriesDataPoint(BaseModel):
    timestamp: datetime
    value: Decimal


class MetricSummary(BaseModel):
    metric_name: str
    current_value: Decimal
    previous_value: Decimal | None = None
    change_percentage: float | None = None
    trend: str = "neutral"  # "up", "down", "neutral"


class AnalyticsDashboardResponse(BaseModel):
    """Analytics dashboard data."""
    period_start: datetime
    period_end: datetime
    metrics: list[MetricSummary]
    time_series: dict[str, list[TimeSeriesDataPoint]] = {}


class EventCountResponse(BaseModel):
    event_name: str
    count: int
    unique_users: int


class TopEventsResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    events: list[EventCountResponse]


# =============================================================================
# A/B Testing Schemas
# =============================================================================

class ExperimentResponse(BaseModel):
    experiment_id: str
    variant: str
    properties: dict = {}


class ExperimentResultResponse(BaseModel):
    experiment_id: str
    variants: dict[str, dict]  # variant -> {"count": 100, "conversion_rate": 0.15}
    winner: str | None = None
    confidence: float | None = None


# =============================================================================
# Real-time Schemas (for WebSocket)
# =============================================================================

class WebSocketMessage(BaseModel):
    """Base WebSocket message."""
    type: str
    payload: dict = {}


class NotificationPushMessage(BaseModel):
    """Real-time notification push."""
    type: str = "notification"
    notification: NotificationResponse


class TaskUpdateMessage(BaseModel):
    """Real-time task update."""
    type: str = "task_update"
    action: str  # "created", "updated", "deleted"
    task_id: UUID
    project_id: UUID
    data: dict = {}


class PresenceMessage(BaseModel):
    """User presence update."""
    type: str = "presence"
    user_id: UUID
    status: str  # "online", "offline", "away"
    last_seen: datetime | None = None


class TypingIndicatorMessage(BaseModel):
    """Typing indicator for comments."""
    type: str = "typing"
    user_id: UUID
    task_id: UUID
    is_typing: bool
