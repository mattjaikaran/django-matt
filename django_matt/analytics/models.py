# file-length-max: 1000
"""
Django models for analytics and event tracking.

Provides models for:
- Events: Generic event tracking
- Sessions: User session tracking
- PageViews: Page view tracking
- UserMetrics: Aggregated user metrics
- Funnels: Conversion funnel definitions
- FunnelSteps: Steps within a funnel
"""

import hashlib
import uuid
from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class EventCategory(str, Enum):
    """Categories for events."""

    PAGE_VIEW = "page_view"
    USER_ACTION = "user_action"
    SYSTEM = "system"
    CONVERSION = "conversion"
    ERROR = "error"
    CUSTOM = "custom"

    @classmethod
    def choices(cls):
        return [(c.value, c.name.replace("_", " ").title()) for c in cls]


class SessionStatus(str, Enum):
    """Status of a session."""

    ACTIVE = "active"
    ENDED = "ended"
    EXPIRED = "expired"

    @classmethod
    def choices(cls):
        return [(s.value, s.name.title()) for s in cls]


class AnonymizationLevel(str, Enum):
    """Level of data anonymization for GDPR compliance."""

    NONE = "none"
    PARTIAL = "partial"  # Hash identifiers
    FULL = "full"  # Remove all PII

    @classmethod
    def choices(cls):
        return [(level.value, level.name.title()) for level in cls]


class AnalyticsSessionManager(models.Manager):
    """Custom manager for analytics sessions."""

    def active(self) -> models.QuerySet:
        """Get active sessions."""
        return self.filter(status=SessionStatus.ACTIVE.value)

    def get_or_create_for_request(
        self,
        session_id: str,
        user: "AbstractUser | None" = None,
        ip_address: str | None = None,
        user_agent: str = "",
        **defaults,
    ) -> tuple["AnalyticsSession", bool]:
        """Get or create session for a request."""
        try:
            session = self.get(session_id=session_id)
            # Update last activity
            session.last_activity_at = timezone.now()
            session.save(update_fields=["last_activity_at"])
            return session, False
        except self.model.DoesNotExist:
            return self.create(
                session_id=session_id,
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                **defaults,
            ), True

    def expire_old_sessions(self, timeout_minutes: int = 30) -> int:
        """Expire sessions that have been inactive."""
        cutoff = timezone.now() - timedelta(minutes=timeout_minutes)
        count = self.filter(
            status=SessionStatus.ACTIVE.value,
            last_activity_at__lt=cutoff,
        ).update(status=SessionStatus.EXPIRED.value, ended_at=timezone.now())
        return count


class AnalyticsSession(models.Model):
    """
    Tracks user sessions for analytics.

    A session represents a user's visit, which may span multiple page views
    and events. Sessions expire after inactivity.

    Attributes:
        session_id: Unique session identifier (from cookie/header)
        user: Optional linked user
        anonymous_id: ID for anonymous users (before login)
        started_at: When the session started
        last_activity_at: Last activity timestamp
        ended_at: When the session ended
        status: Current status
        ip_address: Client IP (can be anonymized)
        user_agent: Browser/client user agent
        device_type: Detected device type
        browser: Detected browser
        os: Detected operating system
        country: GeoIP country
        city: GeoIP city
        referrer: Initial referrer URL
        utm_source: UTM source parameter
        utm_medium: UTM medium parameter
        utm_campaign: UTM campaign parameter
        utm_term: UTM term parameter
        utm_content: UTM content parameter
        landing_page: First page viewed
        exit_page: Last page viewed
        page_views: Count of page views
        events_count: Count of events
        duration_seconds: Session duration
        metadata: Additional metadata
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    session_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique session identifier",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_sessions",
    )
    anonymous_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Anonymous user identifier",
    )

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices(),
        default=SessionStatus.ACTIVE.value,
        db_index=True,
    )

    # Client info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    ip_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Hashed IP for anonymized tracking",
    )
    user_agent = models.TextField(blank=True, default="")
    device_type = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="desktop, mobile, tablet, etc.",
    )
    browser = models.CharField(max_length=100, blank=True, default="")
    os = models.CharField(max_length=100, blank=True, default="")

    # Geo info
    country = models.CharField(max_length=100, blank=True, default="")
    country_code = models.CharField(max_length=2, blank=True, default="")
    city = models.CharField(max_length=200, blank=True, default="")
    region = models.CharField(max_length=200, blank=True, default="")

    # Traffic source
    referrer = models.URLField(max_length=2000, blank=True, null=True)
    referrer_domain = models.CharField(max_length=255, blank=True, default="")
    utm_source = models.CharField(max_length=200, blank=True, default="")
    utm_medium = models.CharField(max_length=200, blank=True, default="")
    utm_campaign = models.CharField(max_length=200, blank=True, default="")
    utm_term = models.CharField(max_length=200, blank=True, default="")
    utm_content = models.CharField(max_length=200, blank=True, default="")

    # Session summary
    landing_page = models.CharField(max_length=2000, blank=True, default="")
    exit_page = models.CharField(max_length=2000, blank=True, default="")
    page_views = models.PositiveIntegerField(default=0)
    events_count = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)

    # Privacy
    anonymization_level = models.CharField(
        max_length=20,
        choices=AnonymizationLevel.choices(),
        default=AnonymizationLevel.NONE.value,
    )
    consent_given = models.BooleanField(
        default=False,
        help_text="Whether user gave tracking consent",
    )
    do_not_track = models.BooleanField(
        default=False,
        help_text="DNT header was set",
    )

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    objects = AnalyticsSessionManager()

    class Meta:
        app_label = "django_matt"
        db_table = "analytics_session"
        ordering = ["-started_at"]
        verbose_name = "Analytics Session"
        verbose_name_plural = "Analytics Sessions"
        indexes = [
            models.Index(fields=["session_id"]),
            models.Index(fields=["user", "started_at"]),
            models.Index(fields=["started_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["anonymous_id"]),
        ]

    def __str__(self):
        return f"Session {self.session_id[:8]}... ({self.status})"

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity_at = timezone.now()
        self.save(update_fields=["last_activity_at"])

    def end_session(self):
        """End the session."""
        now = timezone.now()
        self.status = SessionStatus.ENDED.value
        self.ended_at = now
        self.duration_seconds = int((now - self.started_at).total_seconds())
        self.save(update_fields=["status", "ended_at", "duration_seconds"])

    def identify_user(self, user: "AbstractUser"):
        """Link session to a user."""
        self.user = user
        self.save(update_fields=["user"])

    def anonymize(self, level: AnonymizationLevel = AnonymizationLevel.PARTIAL):
        """Anonymize session data for privacy compliance."""
        self.anonymization_level = level.value

        if level in (AnonymizationLevel.PARTIAL, AnonymizationLevel.FULL):
            # Hash IP address
            if self.ip_address:
                self.ip_hash = hashlib.sha256(self.ip_address.encode()).hexdigest()[:32]
                self.ip_address = None

        if level == AnonymizationLevel.FULL:
            # Remove all PII
            self.user = None
            self.user_agent = ""
            self.city = ""
            self.region = ""

        self.save()


class AnalyticsEventManager(models.Manager):
    """Custom manager for analytics events."""

    def track(
        self,
        name: str,
        properties: dict | None = None,
        user: "AbstractUser | None" = None,
        session: AnalyticsSession | None = None,
        anonymous_id: str = "",
        category: str = EventCategory.CUSTOM.value,
        **kwargs,
    ) -> "AnalyticsEvent":
        """Track an event."""
        return self.create(
            name=name,
            properties=properties or {},
            user=user,
            session=session,
            anonymous_id=anonymous_id,
            category=category,
            **kwargs,
        )

    def by_name(self, name: str) -> models.QuerySet:
        """Get events by name."""
        return self.filter(name=name)

    def by_user(self, user: "AbstractUser") -> models.QuerySet:
        """Get events by user."""
        return self.filter(user=user)

    def by_category(self, category: str) -> models.QuerySet:
        """Get events by category."""
        return self.filter(category=category)

    def in_range(
        self,
        start: "timezone.datetime",
        end: "timezone.datetime",
    ) -> models.QuerySet:
        """Get events in date range."""
        return self.filter(timestamp__gte=start, timestamp__lt=end)


class AnalyticsEvent(models.Model):
    """
    Generic event tracking model.

    Tracks any type of event with flexible properties.

    Attributes:
        name: Event name (e.g., "button_click", "purchase_completed")
        category: Event category
        session: Associated session
        user: Associated user
        anonymous_id: Anonymous user identifier
        properties: Event-specific properties
        timestamp: When event occurred
        context: Contextual information
        page_url: URL where event occurred
        page_title: Title of the page
        element_id: DOM element ID if applicable
        element_class: DOM element class if applicable
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Event name (e.g., 'signup_completed', 'button_click')",
    )
    category = models.CharField(
        max_length=50,
        choices=EventCategory.choices(),
        default=EventCategory.CUSTOM.value,
        db_index=True,
    )

    # Associations
    session = models.ForeignKey(
        AnalyticsSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_events",
    )
    anonymous_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )

    # Event data
    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text="Event-specific properties",
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    # Context
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Contextual information (device, locale, etc.)",
    )
    page_url = models.CharField(max_length=2000, blank=True, default="")
    page_title = models.CharField(max_length=500, blank=True, default="")
    page_path = models.CharField(max_length=500, blank=True, default="")

    # Element tracking (for UI events)
    element_id = models.CharField(max_length=255, blank=True, default="")
    element_class = models.CharField(max_length=500, blank=True, default="")
    element_text = models.CharField(max_length=500, blank=True, default="")

    # Revenue tracking
    revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, blank=True, default="")

    # Multi-tenancy support
    organization_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )

    # Processing
    processed = models.BooleanField(
        default=False,
        help_text="Whether this event has been processed by aggregations",
    )

    objects = AnalyticsEventManager()

    class Meta:
        app_label = "django_matt"
        db_table = "analytics_event"
        ordering = ["-timestamp"]
        verbose_name = "Analytics Event"
        verbose_name_plural = "Analytics Events"
        indexes = [
            models.Index(fields=["name", "timestamp"]),
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["session", "timestamp"]),
            models.Index(fields=["category", "timestamp"]),
            models.Index(fields=["timestamp"]),
            models.Index(fields=["organization_id", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.name} at {self.timestamp}"


class PageView(models.Model):
    """
    Page view tracking.

    Specialized model for tracking page views with additional context.

    Attributes:
        path: URL path
        url: Full URL
        title: Page title
        session: Associated session
        user: Associated user
        referrer: Referring URL
        timestamp: When page was viewed
        time_on_page: Time spent on page (seconds)
        scroll_depth: Maximum scroll depth percentage
        is_bounce: Whether this was a bounce
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Page info
    path = models.CharField(
        max_length=2000,
        db_index=True,
        help_text="URL path without domain",
    )
    url = models.URLField(max_length=2000)
    title = models.CharField(max_length=500, blank=True, default="")
    query_string = models.CharField(max_length=2000, blank=True, default="")
    fragment = models.CharField(max_length=500, blank=True, default="")

    # Associations
    session = models.ForeignKey(
        AnalyticsSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="page_view_set",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_page_views",
    )
    anonymous_id = models.CharField(max_length=255, blank=True, default="")

    # Traffic source
    referrer = models.URLField(max_length=2000, blank=True, null=True)
    referrer_domain = models.CharField(max_length=255, blank=True, default="")

    # Timing
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    time_on_page = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Time on page in seconds",
    )

    # Engagement metrics
    scroll_depth = models.PositiveSmallIntegerField(
        default=0,
        help_text="Maximum scroll depth percentage (0-100)",
    )
    is_bounce = models.BooleanField(
        default=False,
        help_text="Whether user bounced from this page",
    )
    is_exit = models.BooleanField(
        default=False,
        help_text="Whether this was the exit page",
    )
    is_entrance = models.BooleanField(
        default=False,
        help_text="Whether this was the landing page",
    )

    # Performance
    load_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Page load time in milliseconds",
    )
    dom_interactive_ms = models.PositiveIntegerField(null=True, blank=True)
    dom_complete_ms = models.PositiveIntegerField(null=True, blank=True)

    # Multi-tenancy
    organization_id = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        app_label = "django_matt"
        db_table = "analytics_page_view"
        ordering = ["-timestamp"]
        verbose_name = "Page View"
        verbose_name_plural = "Page Views"
        indexes = [
            models.Index(fields=["path", "timestamp"]),
            models.Index(fields=["session", "timestamp"]),
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"PageView: {self.path}"


class UserMetric(models.Model):
    """
    Aggregated metrics per user.

    Pre-computed metrics for efficient querying of user analytics.

    Attributes:
        user: The user
        period: Time period (day/week/month)
        period_start: Start of the period
        total_sessions: Number of sessions
        total_events: Number of events
        total_page_views: Number of page views
        total_time_seconds: Total time on site
        events_by_name: Event counts by name
        pages_by_path: Page view counts by path
    """

    class Period(models.TextChoices):
        DAY = "day", "Daily"
        WEEK = "week", "Weekly"
        MONTH = "month", "Monthly"
        YEAR = "year", "Yearly"
        ALL_TIME = "all_time", "All Time"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analytics_metrics",
    )

    # Period
    period = models.CharField(
        max_length=20,
        choices=Period.choices,
        db_index=True,
    )
    period_start = models.DateField(db_index=True)
    period_end = models.DateField()

    # Aggregate counts
    total_sessions = models.PositiveIntegerField(default=0)
    total_events = models.PositiveIntegerField(default=0)
    total_page_views = models.PositiveIntegerField(default=0)
    total_time_seconds = models.PositiveIntegerField(default=0)
    avg_session_duration = models.PositiveIntegerField(default=0)
    bounce_rate = models.FloatField(default=0.0)

    # First and last activity
    first_seen = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    # Breakdown data
    events_by_name = models.JSONField(
        default=dict,
        blank=True,
        help_text="Event counts by event name",
    )
    pages_by_path = models.JSONField(
        default=dict,
        blank=True,
        help_text="Page view counts by path",
    )
    sessions_by_device = models.JSONField(
        default=dict,
        blank=True,
        help_text="Session counts by device type",
    )

    # Revenue metrics
    total_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    transaction_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        db_table = "analytics_user_metric"
        verbose_name = "User Metric"
        verbose_name_plural = "User Metrics"
        unique_together = [["user", "period", "period_start"]]
        indexes = [
            models.Index(fields=["user", "period"]),
            models.Index(fields=["period", "period_start"]),
        ]

    def __str__(self):
        return f"UserMetric: {self.user} ({self.period} - {self.period_start})"


class Funnel(models.Model):
    """
    Conversion funnel definition.

    Defines a series of steps that users should complete for conversion tracking.

    Attributes:
        name: Funnel name
        description: Funnel description
        steps: Ordered list of steps
        is_active: Whether funnel is being tracked
        conversion_window_hours: Time window for conversion
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Funnel name (e.g., 'Signup Funnel')",
    )
    description = models.TextField(blank=True, default="")

    # Configuration
    is_active = models.BooleanField(default=True)
    conversion_window_hours = models.PositiveIntegerField(
        default=168,  # 7 days
        help_text="Time window for funnel completion (hours)",
    )
    strict_order = models.BooleanField(
        default=True,
        help_text="Whether steps must be completed in exact order",
    )

    # Organization scoping
    organization_id = models.CharField(max_length=255, blank=True, default="")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_funnels",
    )

    class Meta:
        app_label = "django_matt"
        db_table = "analytics_funnel"
        ordering = ["name"]
        verbose_name = "Funnel"
        verbose_name_plural = "Funnels"

    def __str__(self):
        return self.name

    @property
    def step_count(self) -> int:
        """Get number of steps in funnel."""
        return self.steps.count()


class FunnelStep(models.Model):
    """
    Step within a conversion funnel.

    Each step defines a condition (event or page view) that must be met.

    Attributes:
        funnel: Parent funnel
        order: Step order (1-based)
        name: Step name
        event_name: Event name to match (optional)
        page_path: Page path to match (optional)
        conditions: Additional conditions as JSON
    """

    class MatchType(models.TextChoices):
        EVENT = "event", "Event"
        PAGE_VIEW = "page_view", "Page View"
        CUSTOM = "custom", "Custom"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    funnel = models.ForeignKey(
        Funnel,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    order = models.PositiveSmallIntegerField(
        help_text="Step order in funnel (1-based)",
    )
    name = models.CharField(
        max_length=255,
        help_text="Step name (e.g., 'Visited pricing page')",
    )

    # Matching criteria
    match_type = models.CharField(
        max_length=20,
        choices=MatchType.choices,
        default=MatchType.EVENT.value,
    )
    event_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Event name to match",
    )
    page_path = models.CharField(
        max_length=2000,
        blank=True,
        default="",
        help_text="Page path pattern to match (supports wildcards)",
    )
    conditions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional conditions (property filters)",
    )

    # Optional timeout for this step
    timeout_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum time to complete this step (hours)",
    )

    class Meta:
        app_label = "django_matt"
        db_table = "analytics_funnel_step"
        ordering = ["funnel", "order"]
        verbose_name = "Funnel Step"
        verbose_name_plural = "Funnel Steps"
        unique_together = [["funnel", "order"]]

    def __str__(self):
        return f"{self.funnel.name} - Step {self.order}: {self.name}"


class FunnelConversion(models.Model):
    """
    Tracks individual funnel conversions.

    Records when users complete funnel steps and conversions.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    funnel = models.ForeignKey(
        Funnel,
        on_delete=models.CASCADE,
        related_name="conversions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="funnel_conversions",
    )
    session = models.ForeignKey(
        AnalyticsSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    anonymous_id = models.CharField(max_length=255, blank=True, default="")

    # Progress
    current_step = models.PositiveSmallIntegerField(default=0)
    completed_steps = models.JSONField(
        default=list,
        blank=True,
        help_text="List of completed step orders with timestamps",
    )
    is_converted = models.BooleanField(default=False)

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    total_time_seconds = models.PositiveIntegerField(null=True, blank=True)

    # Drop-off tracking
    dropped_at_step = models.PositiveSmallIntegerField(null=True, blank=True)
    dropped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "django_matt"
        db_table = "analytics_funnel_conversion"
        ordering = ["-started_at"]
        verbose_name = "Funnel Conversion"
        verbose_name_plural = "Funnel Conversions"
        indexes = [
            models.Index(fields=["funnel", "started_at"]),
            models.Index(fields=["funnel", "is_converted"]),
            models.Index(fields=["user", "funnel"]),
        ]

    def __str__(self):
        status = "converted" if self.is_converted else f"step {self.current_step}"
        return f"{self.funnel.name}: {status}"


class UserIdentity(models.Model):
    """
    Links anonymous IDs to user accounts.

    Used to merge analytics data when users sign up or log in.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analytics_identities",
    )
    anonymous_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )
    traits = models.JSONField(
        default=dict,
        blank=True,
        help_text="User traits at time of identification",
    )
    identified_at = models.DateTimeField(auto_now_add=True)
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Context at time of identification",
    )

    class Meta:
        app_label = "django_matt"
        db_table = "analytics_user_identity"
        verbose_name = "User Identity"
        verbose_name_plural = "User Identities"

    def __str__(self):
        return f"{self.user} <- {self.anonymous_id[:12]}..."


__all__ = [
    "EventCategory",
    "SessionStatus",
    "AnonymizationLevel",
    "AnalyticsSession",
    "AnalyticsSessionManager",
    "AnalyticsEvent",
    "AnalyticsEventManager",
    "PageView",
    "UserMetric",
    "Funnel",
    "FunnelStep",
    "FunnelConversion",
    "UserIdentity",
]
