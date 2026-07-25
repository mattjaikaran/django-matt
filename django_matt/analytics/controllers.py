# file-length-max: 1050
"""
Analytics REST API controllers.

Provides REST API endpoints for analytics tracking and querying.

Usage:
    from django_matt.analytics import AnalyticsController, MetricsController

    api = DjangoMattAPI()
    api.register_controller(AnalyticsController, prefix="/analytics")
    api.register_controller(MetricsController, prefix="/analytics")
"""

from datetime import datetime, timedelta

from django.http import HttpRequest, JsonResponse
from django.utils import timezone

import orjson

from django_matt.core.controller import APIController
from django_matt.core.router import delete, get, post, put

from .schemas import (
    BatchTrackRequest,
    BatchTrackResponse,
    DashboardMetrics,
    ErrorResponse,
    EventListResponse,
    EventMetrics,
    EventResponse,
    FunnelAnalytics,
    FunnelCreate,
    FunnelListResponse,
    FunnelResponse,
    FunnelStepAnalytics,
    FunnelUpdate,
    IdentifyRequest,
    IdentifyResponse,
    MessageResponse,
    PageMetrics,
    PageViewListResponse,
    PageViewResponse,
    RealtimeMetrics,
    SessionListResponse,
    SessionMetrics,
    SessionResponse,
    TrackEventRequest,
    TrackEventResponse,
    TrackPageViewRequest,
    TrackPageViewResponse,
    TrafficMetrics,
)
from .tracker import get_tracker


class AnalyticsController(APIController):
    """
    Analytics tracking controller.

    Provides endpoints for tracking events, page views, and user identity.

    Endpoints:
        POST /analytics/track       - Track custom event
        POST /analytics/page        - Track page view
        POST /analytics/identify    - Identify user
        POST /analytics/batch       - Batch track events
        GET  /analytics/events      - Query events (admin)
        GET  /analytics/events/{id} - Get event by ID
        GET  /analytics/pages       - Query page views
        GET  /analytics/sessions    - Query sessions
    """

    prefix = "analytics"
    tags = ["Analytics"]

    @post("track")
    async def track_event(self, request: HttpRequest) -> JsonResponse:
        """
        Track a custom event.

        Events are buffered and written in batches for performance.
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = TrackEventRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(),
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(),
                status=422,
            )

        tracker = get_tracker()

        # Get user and session from request if available
        user = request.user if request.user.is_authenticated else None
        session = getattr(request, "analytics_session", None)

        event_id = tracker.track_event(
            name=data.name,
            properties=data.properties,
            user=user,
            session=session,
            anonymous_id=data.anonymous_id or getattr(request, "analytics_anonymous_id", ""),
            category=data.category.value,
            context=data.context.model_dump() if data.context else {},
            timestamp=data.timestamp,
            page_url=data.context.page_url if data.context else "",
            page_title=data.context.page_title if data.context else "",
            element_id=data.element_id,
            element_class=data.element_class,
            element_text=data.element_text,
            revenue=data.revenue,
            currency=data.currency,
            request=request,
        )

        response = TrackEventResponse(
            id=event_id,
            name=data.name,
            timestamp=data.timestamp or timezone.now(),
            success=True,
        )
        return JsonResponse(response.model_dump(), status=201)

    @post("page")
    async def track_page_view(self, request: HttpRequest) -> JsonResponse:
        """
        Track a page view.

        Page views are automatically tracked by middleware, but this
        endpoint allows client-side tracking for SPAs.
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = TrackPageViewRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(),
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(),
                status=422,
            )

        tracker = get_tracker()

        user = request.user if request.user.is_authenticated else None
        session = getattr(request, "analytics_session", None)

        pv_id = tracker.track_page_view(
            path=data.path,
            url=data.url,
            title=data.title,
            user=user,
            session=session,
            anonymous_id=data.anonymous_id or getattr(request, "analytics_anonymous_id", ""),
            referrer=data.referrer,
            timestamp=data.timestamp,
            time_on_page=data.time_on_page,
            scroll_depth=data.scroll_depth,
            load_time_ms=data.load_time_ms,
            request=request,
        )

        response = TrackPageViewResponse(
            id=pv_id,
            path=data.path,
            timestamp=data.timestamp or timezone.now(),
            success=True,
        )
        return JsonResponse(response.model_dump(), status=201)

    @post("identify")
    async def identify_user(self, request: HttpRequest) -> JsonResponse:
        """
        Identify a user and link anonymous sessions/events.

        Call this when a user signs up or logs in to link their
        anonymous activity to their user account.
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = IdentifyRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(),
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(),
                status=422,
            )

        # Use provided user_id or get from authenticated user
        user_id = data.user_id
        if not user_id and request.user.is_authenticated:
            user_id = str(request.user.pk)

        if not user_id:
            return JsonResponse(
                ErrorResponse(
                    detail="user_id is required or user must be authenticated",
                    code="user_required",
                ).model_dump(),
                status=400,
            )

        tracker = get_tracker()
        tracker.identify(
            user=request.user if request.user.is_authenticated else None,
            anonymous_id=data.anonymous_id,
            traits=data.traits,
            context=data.context.model_dump() if data.context else {},
            timestamp=data.timestamp,
        )

        response = IdentifyResponse(
            user_id=user_id,
            anonymous_id=data.anonymous_id,
            success=True,
            message="User identified successfully",
        )
        return JsonResponse(response.model_dump())

    @post("batch")
    async def batch_track(self, request: HttpRequest) -> JsonResponse:
        """
        Batch track multiple events and page views.

        More efficient than individual tracking calls for high-volume scenarios.
        """
        try:
            body = orjson.loads(request.body) if request.body else {}
            data = BatchTrackRequest.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(),
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(),
                status=422,
            )

        tracker = get_tracker()
        errors = []
        events_tracked = 0
        page_views_tracked = 0

        user = request.user if request.user.is_authenticated else None
        session = getattr(request, "analytics_session", None)

        # Track events
        for event in data.events:
            try:
                tracker.track_event(
                    name=event.name,
                    properties=event.properties,
                    user=user,
                    session=session,
                    anonymous_id=event.anonymous_id,
                    category=event.category.value,
                    timestamp=event.timestamp,
                )
                events_tracked += 1
            except Exception as e:
                errors.append(f"Event '{event.name}': {e!s}")

        # Track page views
        for pv in data.page_views:
            try:
                tracker.track_page_view(
                    path=pv.path,
                    url=pv.url,
                    title=pv.title,
                    user=user,
                    session=session,
                    anonymous_id=pv.anonymous_id,
                    timestamp=pv.timestamp,
                )
                page_views_tracked += 1
            except Exception as e:
                errors.append(f"Page view '{pv.path}': {e!s}")

        response = BatchTrackResponse(
            events_tracked=events_tracked,
            page_views_tracked=page_views_tracked,
            errors=errors,
            success=len(errors) == 0,
        )
        return JsonResponse(response.model_dump(), status=201 if response.success else 207)

    @get("events")
    async def list_events(self, request: HttpRequest) -> JsonResponse:
        """
        Query events.

        Query params:
            - name: Filter by event name
            - category: Filter by category
            - user_id: Filter by user
            - start_date: Start of date range
            - end_date: End of date range
            - page: Page number
            - page_size: Items per page
        """
        from .models import AnalyticsEvent

        # Build queryset
        qs = AnalyticsEvent.objects.all()

        # Filters
        name = request.GET.get("name")
        if name:
            qs = qs.filter(name=name)

        category = request.GET.get("category")
        if category:
            qs = qs.filter(category=category)

        user_id = request.GET.get("user_id")
        if user_id:
            qs = qs.filter(user_id=user_id)

        start_date = request.GET.get("start_date")
        if start_date:
            qs = qs.filter(timestamp__gte=start_date)

        end_date = request.GET.get("end_date")
        if end_date:
            qs = qs.filter(timestamp__lt=end_date)

        # Pagination
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 50))
        page_size = min(page_size, 200)

        total = await qs.acount()
        offset = (page - 1) * page_size
        events = [e async for e in qs.order_by("-timestamp")[offset : offset + page_size]]

        items = []
        for event in events:
            items.append(
                EventResponse(
                    id=str(event.id),
                    name=event.name,
                    category=event.category,
                    properties=event.properties,
                    context=event.context,
                    timestamp=event.timestamp,
                    user_id=str(event.user_id) if event.user_id else None,
                    session_id=str(event.session_id) if event.session_id else None,
                    anonymous_id=event.anonymous_id,
                    page_url=event.page_url,
                    page_title=event.page_title,
                    revenue=float(event.revenue) if event.revenue else None,
                    currency=event.currency,
                ).model_dump()
            )

        response = EventListResponse(items=items, total=total, page=page, page_size=page_size)
        return JsonResponse(response.model_dump())

    @get("events/{event_id}")
    async def get_event(self, request: HttpRequest, event_id: str) -> JsonResponse:
        """Get a single event by ID."""
        from .models import AnalyticsEvent

        try:
            event = await AnalyticsEvent.objects.aget(id=event_id)
        except AnalyticsEvent.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail="Event not found", code="not_found").model_dump(),
                status=404,
            )

        response = EventResponse(
            id=str(event.id),
            name=event.name,
            category=event.category,
            properties=event.properties,
            context=event.context,
            timestamp=event.timestamp,
            user_id=str(event.user_id) if event.user_id else None,
            session_id=str(event.session_id) if event.session_id else None,
            anonymous_id=event.anonymous_id,
            page_url=event.page_url,
            page_title=event.page_title,
            revenue=float(event.revenue) if event.revenue else None,
            currency=event.currency,
        )
        return JsonResponse(response.model_dump())

    @get("pages")
    async def list_page_views(self, request: HttpRequest) -> JsonResponse:
        """Query page views."""
        from .models import PageView

        qs = PageView.objects.all()

        # Filters
        path = request.GET.get("path")
        if path:
            qs = qs.filter(path=path)

        user_id = request.GET.get("user_id")
        if user_id:
            qs = qs.filter(user_id=user_id)

        start_date = request.GET.get("start_date")
        if start_date:
            qs = qs.filter(timestamp__gte=start_date)

        end_date = request.GET.get("end_date")
        if end_date:
            qs = qs.filter(timestamp__lt=end_date)

        # Pagination
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 50))
        page_size = min(page_size, 200)

        total = await qs.acount()
        offset = (page - 1) * page_size
        page_views = [pv async for pv in qs.order_by("-timestamp")[offset : offset + page_size]]

        items = []
        for pv in page_views:
            items.append(
                PageViewResponse(
                    id=str(pv.id),
                    path=pv.path,
                    url=pv.url,
                    title=pv.title,
                    timestamp=pv.timestamp,
                    user_id=str(pv.user_id) if pv.user_id else None,
                    session_id=str(pv.session_id) if pv.session_id else None,
                    referrer=pv.referrer,
                    time_on_page=pv.time_on_page,
                    scroll_depth=pv.scroll_depth,
                    is_bounce=pv.is_bounce,
                    is_entrance=pv.is_entrance,
                    is_exit=pv.is_exit,
                ).model_dump()
            )

        response = PageViewListResponse(items=items, total=total, page=page, page_size=page_size)
        return JsonResponse(response.model_dump())

    @get("sessions")
    async def list_sessions(self, request: HttpRequest) -> JsonResponse:
        """Query sessions."""
        from .models import AnalyticsSession

        qs = AnalyticsSession.objects.all()

        # Filters
        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        user_id = request.GET.get("user_id")
        if user_id:
            qs = qs.filter(user_id=user_id)

        start_date = request.GET.get("start_date")
        if start_date:
            qs = qs.filter(started_at__gte=start_date)

        end_date = request.GET.get("end_date")
        if end_date:
            qs = qs.filter(started_at__lt=end_date)

        # Pagination
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 50))
        page_size = min(page_size, 200)

        total = await qs.acount()
        offset = (page - 1) * page_size
        sessions = [s async for s in qs.order_by("-started_at")[offset : offset + page_size]]

        items = []
        for session in sessions:
            items.append(
                SessionResponse(
                    id=str(session.id),
                    session_id=session.session_id,
                    user_id=str(session.user_id) if session.user_id else None,
                    anonymous_id=session.anonymous_id,
                    status=session.status,
                    started_at=session.started_at,
                    last_activity_at=session.last_activity_at,
                    ended_at=session.ended_at,
                    device_type=session.device_type,
                    browser=session.browser,
                    os=session.os,
                    country=session.country,
                    city=session.city,
                    referrer=session.referrer,
                    landing_page=session.landing_page,
                    exit_page=session.exit_page,
                    page_views=session.page_views,
                    events_count=session.events_count,
                    duration_seconds=session.duration_seconds,
                    utm_source=session.utm_source,
                    utm_medium=session.utm_medium,
                    utm_campaign=session.utm_campaign,
                ).model_dump()
            )

        response = SessionListResponse(items=items, total=total, page=page, page_size=page_size)
        return JsonResponse(response.model_dump())


class MetricsController(APIController):
    """
    Analytics metrics controller.

    Provides endpoints for aggregated metrics, dashboards, and reports.

    Endpoints:
        GET  /analytics/metrics          - Get dashboard metrics
        GET  /analytics/metrics/realtime - Get real-time metrics
        GET  /analytics/metrics/events   - Get event metrics
        GET  /analytics/metrics/pages    - Get page metrics
        GET  /analytics/metrics/sessions - Get session metrics
        GET  /analytics/metrics/traffic  - Get traffic metrics
    """

    prefix = "analytics"
    tags = ["Analytics Metrics"]

    @get("metrics")
    async def get_dashboard_metrics(self, request: HttpRequest) -> JsonResponse:
        """
        Get combined dashboard metrics.

        Query params:
            - period: day, week, month (default: week)
            - start_date: Start date (ISO format)
            - end_date: End date (ISO format)
        """
        from .aggregations import get_aggregator

        period = request.GET.get("period", "week")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        # Parse dates
        if start_date:
            start = datetime.fromisoformat(start_date)
        elif period == "day":
            start = timezone.now() - timedelta(days=1)
        elif period == "week":
            start = timezone.now() - timedelta(weeks=1)
        else:
            start = timezone.now() - timedelta(days=30)

        if end_date:
            end = datetime.fromisoformat(end_date)
        else:
            end = timezone.now()

        aggregator = get_aggregator()

        events = await aggregator.get_event_metrics(start, end)
        pages = await aggregator.get_page_metrics(start, end)
        sessions = await aggregator.get_session_metrics(start, end)
        traffic = await aggregator.get_traffic_metrics(start, end)

        response = DashboardMetrics(
            events=EventMetrics(**events),
            pages=PageMetrics(**pages),
            sessions=SessionMetrics(**sessions),
            traffic=TrafficMetrics(**traffic),
        )
        return JsonResponse(response.model_dump())

    @get("metrics/realtime")
    async def get_realtime_metrics(self, request: HttpRequest) -> JsonResponse:
        """
        Get real-time metrics (last 30 minutes).

        Shows currently active users, live page views, etc.
        """
        from .aggregations import get_aggregator

        minutes = int(request.GET.get("minutes", 30))
        minutes = min(minutes, 60)  # Max 60 minutes

        aggregator = get_aggregator()
        metrics = await aggregator.get_realtime_metrics(minutes)

        response = RealtimeMetrics(**metrics)
        return JsonResponse(response.model_dump())

    @get("metrics/events")
    async def get_event_metrics(self, request: HttpRequest) -> JsonResponse:
        """Get detailed event metrics."""
        from .aggregations import get_aggregator

        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        if start_date:
            start = datetime.fromisoformat(start_date)
        else:
            start = timezone.now() - timedelta(weeks=1)

        if end_date:
            end = datetime.fromisoformat(end_date)
        else:
            end = timezone.now()

        aggregator = get_aggregator()
        metrics = await aggregator.get_event_metrics(start, end)

        response = EventMetrics(**metrics)
        return JsonResponse(response.model_dump())

    @get("metrics/pages")
    async def get_page_metrics(self, request: HttpRequest) -> JsonResponse:
        """Get detailed page view metrics."""
        from .aggregations import get_aggregator

        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        if start_date:
            start = datetime.fromisoformat(start_date)
        else:
            start = timezone.now() - timedelta(weeks=1)

        if end_date:
            end = datetime.fromisoformat(end_date)
        else:
            end = timezone.now()

        aggregator = get_aggregator()
        metrics = await aggregator.get_page_metrics(start, end)

        response = PageMetrics(**metrics)
        return JsonResponse(response.model_dump())

    @get("metrics/sessions")
    async def get_session_metrics(self, request: HttpRequest) -> JsonResponse:
        """Get detailed session metrics."""
        from .aggregations import get_aggregator

        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        if start_date:
            start = datetime.fromisoformat(start_date)
        else:
            start = timezone.now() - timedelta(weeks=1)

        if end_date:
            end = datetime.fromisoformat(end_date)
        else:
            end = timezone.now()

        aggregator = get_aggregator()
        metrics = await aggregator.get_session_metrics(start, end)

        response = SessionMetrics(**metrics)
        return JsonResponse(response.model_dump())

    @get("metrics/traffic")
    async def get_traffic_metrics(self, request: HttpRequest) -> JsonResponse:
        """Get traffic source metrics."""
        from .aggregations import get_aggregator

        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        if start_date:
            start = datetime.fromisoformat(start_date)
        else:
            start = timezone.now() - timedelta(weeks=1)

        if end_date:
            end = datetime.fromisoformat(end_date)
        else:
            end = timezone.now()

        aggregator = get_aggregator()
        metrics = await aggregator.get_traffic_metrics(start, end)

        response = TrafficMetrics(**metrics)
        return JsonResponse(response.model_dump())


class FunnelController(APIController):
    """
    Funnel management and analysis controller.

    Endpoints:
        GET    /analytics/funnels              - List funnels
        POST   /analytics/funnels              - Create funnel
        GET    /analytics/funnels/{id}         - Get funnel
        PUT    /analytics/funnels/{id}         - Update funnel
        DELETE /analytics/funnels/{id}         - Delete funnel
        GET    /analytics/funnels/{id}/analyze - Get funnel analytics
    """

    prefix = "analytics"
    tags = ["Funnels"]

    @get("funnels")
    async def list_funnels(self, request: HttpRequest) -> JsonResponse:
        """List all funnels."""
        from .models import Funnel

        funnels = [f async for f in Funnel.objects.prefetch_related("steps").all()]

        items = []
        for funnel in funnels:
            steps = [s async for s in funnel.steps.all().order_by("order")]
            items.append(
                FunnelResponse(
                    id=str(funnel.id),
                    name=funnel.name,
                    description=funnel.description,
                    is_active=funnel.is_active,
                    conversion_window_hours=funnel.conversion_window_hours,
                    strict_order=funnel.strict_order,
                    steps=[
                        {
                            "id": str(s.id),
                            "name": s.name,
                            "order": s.order,
                            "match_type": s.match_type,
                            "event_name": s.event_name,
                            "page_path": s.page_path,
                            "conditions": s.conditions,
                            "timeout_hours": s.timeout_hours,
                        }
                        for s in steps
                    ],
                    step_count=len(steps),
                    created_at=funnel.created_at,
                    updated_at=funnel.updated_at,
                ).model_dump()
            )

        response = FunnelListResponse(items=items, total=len(items))
        return JsonResponse(response.model_dump())

    @post("funnels")
    async def create_funnel(self, request: HttpRequest) -> JsonResponse:
        """Create a new funnel."""
        from .models import Funnel, FunnelStep

        try:
            body = orjson.loads(request.body) if request.body else {}
            data = FunnelCreate.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(),
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(),
                status=422,
            )

        # Check for duplicate name
        if await Funnel.objects.filter(name=data.name).aexists():
            return JsonResponse(
                ErrorResponse(
                    detail=f"Funnel with name '{data.name}' already exists",
                    code="duplicate_name",
                ).model_dump(),
                status=400,
            )

        # Create funnel
        funnel = await Funnel.objects.acreate(
            name=data.name,
            description=data.description,
            conversion_window_hours=data.conversion_window_hours,
            strict_order=data.strict_order,
            created_by=request.user if request.user.is_authenticated else None,
        )

        # Create steps
        steps = []
        for step_data in data.steps:
            step = await FunnelStep.objects.acreate(
                funnel=funnel,
                order=step_data.order,
                name=step_data.name,
                match_type=step_data.match_type.value,
                event_name=step_data.event_name,
                page_path=step_data.page_path,
                conditions=step_data.conditions,
                timeout_hours=step_data.timeout_hours,
            )
            steps.append(step)

        response = FunnelResponse(
            id=str(funnel.id),
            name=funnel.name,
            description=funnel.description,
            is_active=funnel.is_active,
            conversion_window_hours=funnel.conversion_window_hours,
            strict_order=funnel.strict_order,
            steps=[
                {
                    "id": str(s.id),
                    "name": s.name,
                    "order": s.order,
                    "match_type": s.match_type,
                    "event_name": s.event_name,
                    "page_path": s.page_path,
                    "conditions": s.conditions,
                    "timeout_hours": s.timeout_hours,
                }
                for s in steps
            ],
            step_count=len(steps),
            created_at=funnel.created_at,
            updated_at=funnel.updated_at,
        )
        return JsonResponse(response.model_dump(), status=201)

    @get("funnels/{funnel_id}")
    async def get_funnel(self, request: HttpRequest, funnel_id: str) -> JsonResponse:
        """Get a funnel by ID."""
        from .models import Funnel

        try:
            funnel = await Funnel.objects.prefetch_related("steps").aget(id=funnel_id)
        except Funnel.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail="Funnel not found", code="not_found").model_dump(),
                status=404,
            )

        steps = [s async for s in funnel.steps.all().order_by("order")]

        response = FunnelResponse(
            id=str(funnel.id),
            name=funnel.name,
            description=funnel.description,
            is_active=funnel.is_active,
            conversion_window_hours=funnel.conversion_window_hours,
            strict_order=funnel.strict_order,
            steps=[
                {
                    "id": str(s.id),
                    "name": s.name,
                    "order": s.order,
                    "match_type": s.match_type,
                    "event_name": s.event_name,
                    "page_path": s.page_path,
                    "conditions": s.conditions,
                    "timeout_hours": s.timeout_hours,
                }
                for s in steps
            ],
            step_count=len(steps),
            created_at=funnel.created_at,
            updated_at=funnel.updated_at,
        )
        return JsonResponse(response.model_dump())

    @put("funnels/{funnel_id}")
    async def update_funnel(self, request: HttpRequest, funnel_id: str) -> JsonResponse:
        """Update a funnel."""
        from .models import Funnel

        try:
            funnel = await Funnel.objects.aget(id=funnel_id)
        except Funnel.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail="Funnel not found", code="not_found").model_dump(),
                status=404,
            )

        try:
            body = orjson.loads(request.body) if request.body else {}
            data = FunnelUpdate.model_validate(body)
        except orjson.JSONDecodeError:
            return JsonResponse(
                ErrorResponse(detail="Invalid JSON", code="invalid_json").model_dump(),
                status=400,
            )
        except Exception as e:
            return JsonResponse(
                ErrorResponse(detail=str(e), code="validation_error").model_dump(),
                status=422,
            )

        # Update fields
        if data.name is not None:
            funnel.name = data.name
        if data.description is not None:
            funnel.description = data.description
        if data.is_active is not None:
            funnel.is_active = data.is_active
        if data.conversion_window_hours is not None:
            funnel.conversion_window_hours = data.conversion_window_hours
        if data.strict_order is not None:
            funnel.strict_order = data.strict_order

        await funnel.asave()

        steps = [s async for s in funnel.steps.all().order_by("order")]

        response = FunnelResponse(
            id=str(funnel.id),
            name=funnel.name,
            description=funnel.description,
            is_active=funnel.is_active,
            conversion_window_hours=funnel.conversion_window_hours,
            strict_order=funnel.strict_order,
            steps=[
                {
                    "id": str(s.id),
                    "name": s.name,
                    "order": s.order,
                    "match_type": s.match_type,
                    "event_name": s.event_name,
                    "page_path": s.page_path,
                    "conditions": s.conditions,
                    "timeout_hours": s.timeout_hours,
                }
                for s in steps
            ],
            step_count=len(steps),
            created_at=funnel.created_at,
            updated_at=funnel.updated_at,
        )
        return JsonResponse(response.model_dump())

    @delete("funnels/{funnel_id}")
    async def delete_funnel(self, request: HttpRequest, funnel_id: str) -> JsonResponse:
        """Delete a funnel."""
        from .models import Funnel

        try:
            funnel = await Funnel.objects.aget(id=funnel_id)
        except Funnel.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail="Funnel not found", code="not_found").model_dump(),
                status=404,
            )

        await funnel.adelete()

        response = MessageResponse(message=f"Funnel '{funnel.name}' deleted")
        return JsonResponse(response.model_dump())

    @get("funnels/{funnel_id}/analyze")
    async def analyze_funnel(self, request: HttpRequest, funnel_id: str) -> JsonResponse:
        """
        Get funnel analysis.

        Query params:
            - start_date: Start of analysis period
            - end_date: End of analysis period
        """
        from .aggregations import get_aggregator
        from .models import Funnel

        try:
            funnel = await Funnel.objects.prefetch_related("steps").aget(id=funnel_id)
        except Funnel.DoesNotExist:
            return JsonResponse(
                ErrorResponse(detail="Funnel not found", code="not_found").model_dump(),
                status=404,
            )

        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        if start_date:
            start = datetime.fromisoformat(start_date)
        else:
            start = timezone.now() - timedelta(days=30)

        if end_date:
            end = datetime.fromisoformat(end_date)
        else:
            end = timezone.now()

        aggregator = get_aggregator()
        analysis = await aggregator.analyze_funnel(funnel, start, end)

        response = FunnelAnalytics(
            funnel_id=str(funnel.id),
            funnel_name=funnel.name,
            period_start=start,
            period_end=end,
            total_started=analysis["total_started"],
            total_converted=analysis["total_converted"],
            overall_conversion_rate=analysis["overall_conversion_rate"],
            avg_conversion_time=analysis.get("avg_conversion_time"),
            steps=[FunnelStepAnalytics(**step) for step in analysis["steps"]],
        )
        return JsonResponse(response.model_dump())


__all__ = [
    "AnalyticsController",
    "MetricsController",
    "FunnelController",
]
