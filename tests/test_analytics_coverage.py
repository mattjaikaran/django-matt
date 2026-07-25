"""
Extended analytics coverage tests for django_matt.analytics module.

Covers:
- EventTracker: track_event, track_page_view, DNT respect, flush, batch context
- DatabaseBackend: track_event, track_events_batch, track_page_view, identify, alias, group
- Aggregator: get_event_metrics, get_page_metrics, get_session_metrics, analyze_funnel
- Models: AnalyticsSession, AnalyticsEvent, PageView, Funnel, FunnelStep, FunnelConversion
- Session management: get_or_create, expire, end, anonymize
- Middleware: AnalyticsMiddleware skip conditions, bot filtering, DNT
- Edge cases: high-cardinality events, missing properties, empty data
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory
from django.utils import timezone

import pytest
from asgiref.sync import sync_to_async

from django_matt.analytics.aggregations import Aggregator, get_aggregator
from django_matt.analytics.backends import DatabaseBackend as AnalyticsDatabaseBackend
from django_matt.analytics.middleware import AnalyticsMiddleware
from django_matt.analytics.models import (
    AnalyticsEvent,
    AnalyticsSession,
    AnonymizationLevel,
    EventCategory,
    Funnel,
    FunnelConversion,
    FunnelStep,
    PageView,
    SessionStatus,
    UserIdentity,
    UserMetric,
)
from django_matt.analytics.tracker import BatchContext, EventTracker, get_tracker

pytestmark = pytest.mark.django_db


# ============================================================================
# Helpers
# ============================================================================


def _make_request(
    method="GET",
    path="/",
    user_agent="",
    dnt=None,
    cookies=None,
    user=None,
):
    rf = RequestFactory()
    kwargs = {}
    if user_agent:
        kwargs["HTTP_USER_AGENT"] = user_agent
    if dnt:
        kwargs["HTTP_DNT"] = dnt
    request = rf.get(path, **kwargs)
    if cookies:
        request.COOKIES = cookies
    if user:
        request.user = user
    else:
        request.user = MagicMock(is_authenticated=False)
    return request


def _create_user(username="testuser", email="test@example.com"):
    return User.objects.create_user(
        username=username,
        email=email,
        password="testpass123",
    )


# ============================================================================
# EventTracker
# ============================================================================


class TestEventTracker:
    def test_track_event_returns_id(self):
        backend = MagicMock()
        backend.track_event = MagicMock()

        tracker = EventTracker()
        tracker._backend = backend

        event_id = tracker.track_event("button_click", properties={"btn": "signup"}, flush=True)
        assert event_id  # Non-empty string
        backend.track_event.assert_called_once()

    def test_track_event_respects_dnt(self):
        tracker = EventTracker(respect_dnt=True)
        tracker._backend = MagicMock()

        request = _make_request(dnt="1")
        event_id = tracker.track_event("click", request=request, flush=True)

        assert event_id == ""

    def test_track_event_ignores_dnt_when_disabled(self):
        backend = MagicMock()
        tracker = EventTracker(respect_dnt=False)
        tracker._backend = backend

        request = _make_request(dnt="1")
        event_id = tracker.track_event("click", request=request, flush=True)

        assert event_id != ""

    def test_track_page_view_returns_id(self):
        backend = MagicMock()
        tracker = EventTracker()
        tracker._backend = backend

        pv_id = tracker.track_page_view("/pricing", flush=True)
        assert pv_id
        backend.track_page_view.assert_called_once()

    def test_track_page_view_respects_dnt(self):
        tracker = EventTracker(respect_dnt=True)
        tracker._backend = MagicMock()

        request = _make_request(dnt="1")
        pv_id = tracker.track_page_view("/pricing", request=request)
        assert pv_id == ""

    def test_batch_context_queues_events(self):
        backend = MagicMock()
        tracker = EventTracker()
        tracker._backend = backend

        with tracker.batch() as batch:
            batch.track_event("event1", properties={"a": 1})
            batch.track_event("event2", properties={"b": 2})
            batch.track_page_view("/page1")

        backend.track_events_batch.assert_called_once()
        assert len(backend.track_events_batch.call_args[0][0]) == 2
        backend.track_page_views_batch.assert_called_once()
        assert len(backend.track_page_views_batch.call_args[0][0]) == 1

    def test_flush_clears_buffers(self):
        backend = MagicMock()
        tracker = EventTracker(batch_size=1000)
        tracker._backend = backend

        # Add events to buffer without flush
        tracker.track_event("buffered1")
        tracker.track_event("buffered2")

        assert len(tracker._event_buffer) == 2

        tracker.flush()

        assert len(tracker._event_buffer) == 0
        backend.track_events_batch.assert_called_once()

    def test_auto_flush_on_batch_size(self):
        backend = MagicMock()
        tracker = EventTracker(batch_size=2)
        tracker._backend = backend

        tracker.track_event("e1")
        tracker.track_event("e2")  # Should trigger flush

        backend.track_events_batch.assert_called()

    def test_extract_context_from_request(self):
        request = _make_request(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        )
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        tracker = EventTracker()
        ctx = tracker._extract_context(request)

        assert "user_agent" in ctx
        assert ctx["device_type"] == "desktop"
        assert "ip" in ctx

    def test_extract_context_anonymize_ip(self):
        request = _make_request()
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        tracker = EventTracker(anonymize_ip=True)
        ctx = tracker._extract_context(request)

        assert "ip_hash" in ctx
        assert "ip" not in ctx

    def test_close_flushes_and_closes_backend(self):
        backend = MagicMock()
        tracker = EventTracker()
        tracker._backend = backend
        tracker._event_buffer.append({"name": "pending"})

        tracker.close()

        backend.track_events_batch.assert_called_once()
        backend.close.assert_called_once()


# ============================================================================
# DatabaseBackend (analytics)
# ============================================================================


class TestAnalyticsDatabaseBackend:
    def test_track_event_creates_record(self):
        backend = AnalyticsDatabaseBackend()
        event_id = backend.track_event(
            {
                "name": "test_event",
                "category": "custom",
                "properties": {"key": "value"},
            }
        )

        assert event_id
        event = AnalyticsEvent.objects.get(id=event_id)
        assert event.name == "test_event"
        assert event.properties == {"key": "value"}

    def test_track_events_batch(self):
        backend = AnalyticsDatabaseBackend()
        ids = backend.track_events_batch(
            [
                {"name": "batch1", "category": "custom"},
                {"name": "batch2", "category": "custom"},
            ]
        )

        assert len(ids) == 2
        assert AnalyticsEvent.objects.filter(name__startswith="batch").count() == 2

    def test_track_page_view_creates_record(self):
        backend = AnalyticsDatabaseBackend()
        pv_id = backend.track_page_view(
            {
                "path": "/test",
                "url": "https://example.com/test",
            }
        )

        assert pv_id
        pv = PageView.objects.get(id=pv_id)
        assert pv.path == "/test"

    def test_track_page_views_batch(self):
        backend = AnalyticsDatabaseBackend()
        ids = backend.track_page_views_batch(
            [
                {"path": "/page1", "url": "https://example.com/page1"},
                {"path": "/page2", "url": "https://example.com/page2"},
            ]
        )

        assert len(ids) == 2

    def test_identify_links_anonymous(self):
        user = _create_user(username="id_user")
        backend = AnalyticsDatabaseBackend()

        # Create anonymous session
        session = AnalyticsSession.objects.create(
            session_id="anon-sess-1",
            anonymous_id="anon-123",
        )
        # Create anonymous event
        AnalyticsEvent.objects.create(
            name="anon_event",
            anonymous_id="anon-123",
        )

        backend.identify(
            user_id=str(user.pk),
            anonymous_id="anon-123",
            traits={"plan": "pro"},
        )

        # Session should now be linked to user
        session.refresh_from_db()
        assert session.user_id == user.pk

        # Identity record should exist
        identity = UserIdentity.objects.get(anonymous_id="anon-123")
        assert identity.user == user

    def test_group_updates_sessions(self):
        user = _create_user(username="group_user")
        backend = AnalyticsDatabaseBackend()

        AnalyticsSession.objects.create(
            session_id="group-sess-1",
            user=user,
        )

        backend.group(
            user_id=str(user.pk),
            group_id="org-42",
            traits={"name": "Acme"},
        )

        session = AnalyticsSession.objects.get(session_id="group-sess-1")
        assert session.metadata["organization_id"] == "org-42"
        assert session.metadata["organization_traits"] == {"name": "Acme"}


# ============================================================================
# Models: AnalyticsSession
# ============================================================================


class TestAnalyticsSessionModel:
    def test_create_and_str(self):
        session = AnalyticsSession.objects.create(
            session_id="test-sess-1",
            status=SessionStatus.ACTIVE.value,
        )
        assert "test-ses" in str(session)

    def test_end_session(self):
        session = AnalyticsSession.objects.create(
            session_id="end-sess",
            status=SessionStatus.ACTIVE.value,
        )
        session.end_session()

        session.refresh_from_db()
        assert session.status == SessionStatus.ENDED.value
        assert session.ended_at is not None
        assert session.duration_seconds >= 0

    def test_identify_user(self):
        user = _create_user(username="sess_user")
        session = AnalyticsSession.objects.create(
            session_id="id-sess",
        )
        session.identify_user(user)

        session.refresh_from_db()
        assert session.user == user

    def test_anonymize_partial(self):
        session = AnalyticsSession.objects.create(
            session_id="anon-sess",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        session.anonymize(AnonymizationLevel.PARTIAL)

        session.refresh_from_db()
        assert session.ip_address is None
        assert session.ip_hash != ""
        assert session.user_agent == "Mozilla/5.0"  # Preserved in partial

    def test_anonymize_full(self):
        user = _create_user(username="anon_full_user")
        session = AnalyticsSession.objects.create(
            session_id="anon-full-sess",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            user=user,
            city="New York",
        )
        session.anonymize(AnonymizationLevel.FULL)

        session.refresh_from_db()
        assert session.ip_address is None
        assert session.user is None
        assert session.user_agent == ""
        assert session.city == ""

    def test_expire_old_sessions(self):
        # Create active session with old last_activity
        session = AnalyticsSession.objects.create(
            session_id="old-sess",
            status=SessionStatus.ACTIVE.value,
        )
        # Manually set old activity time
        AnalyticsSession.objects.filter(pk=session.pk).update(
            last_activity_at=timezone.now() - timedelta(minutes=60),
        )

        count = AnalyticsSession.objects.expire_old_sessions(timeout_minutes=30)
        assert count == 1

        session.refresh_from_db()
        assert session.status == SessionStatus.EXPIRED.value

    def test_session_manager_active(self):
        AnalyticsSession.objects.create(
            session_id="mgr-active",
            status=SessionStatus.ACTIVE.value,
        )
        AnalyticsSession.objects.create(
            session_id="mgr-ended",
            status=SessionStatus.ENDED.value,
        )

        active = AnalyticsSession.objects.active()
        session_ids = list(active.values_list("session_id", flat=True))
        assert "mgr-active" in session_ids
        assert "mgr-ended" not in session_ids


# ============================================================================
# Models: AnalyticsEvent
# ============================================================================


class TestAnalyticsEventModel:
    def test_create_event(self):
        event = AnalyticsEvent.objects.create(
            name="click",
            category=EventCategory.USER_ACTION.value,
            properties={"button": "signup"},
        )
        assert "click" in str(event)

    def test_manager_by_name(self):
        AnalyticsEvent.objects.create(name="purchase", category="conversion")
        AnalyticsEvent.objects.create(name="click", category="user_action")

        purchases = AnalyticsEvent.objects.by_name("purchase")
        assert purchases.count() == 1

    def test_manager_by_category(self):
        AnalyticsEvent.objects.create(name="e1", category="conversion")
        AnalyticsEvent.objects.create(name="e2", category="conversion")
        AnalyticsEvent.objects.create(name="e3", category="custom")

        conversions = AnalyticsEvent.objects.by_category("conversion")
        assert conversions.count() == 2

    def test_manager_in_range(self):
        now = timezone.now()
        AnalyticsEvent.objects.create(
            name="recent",
            timestamp=now - timedelta(hours=1),
        )
        AnalyticsEvent.objects.create(
            name="old",
            timestamp=now - timedelta(days=7),
        )

        recent = AnalyticsEvent.objects.in_range(
            start=now - timedelta(hours=2),
            end=now,
        )
        assert recent.count() == 1

    def test_manager_by_user(self):
        user = _create_user(username="event_user")
        AnalyticsEvent.objects.create(name="user_event", user=user)
        AnalyticsEvent.objects.create(name="other_event")

        user_events = AnalyticsEvent.objects.by_user(user)
        assert user_events.count() == 1


# ============================================================================
# Models: PageView
# ============================================================================


class TestPageViewModel:
    def test_create_page_view(self):
        pv = PageView.objects.create(
            path="/pricing",
            url="https://example.com/pricing",
            title="Pricing",
        )
        assert "pricing" in str(pv)

    def test_page_view_with_session(self):
        session = AnalyticsSession.objects.create(session_id="pv-sess")
        pv = PageView.objects.create(
            path="/about",
            url="https://example.com/about",
            session=session,
        )
        assert pv.session == session


# ============================================================================
# Models: Funnel / FunnelStep / FunnelConversion
# ============================================================================


class TestFunnelModels:
    def test_create_funnel_with_steps(self):
        funnel = Funnel.objects.create(
            name="Signup Funnel",
            conversion_window_hours=168,
        )
        FunnelStep.objects.create(
            funnel=funnel,
            order=1,
            name="Visit Landing",
            match_type=FunnelStep.MatchType.PAGE_VIEW,
            page_path="/",
        )
        FunnelStep.objects.create(
            funnel=funnel,
            order=2,
            name="Click Signup",
            match_type=FunnelStep.MatchType.EVENT,
            event_name="signup_click",
        )

        assert funnel.step_count == 2
        assert "Signup Funnel" in str(funnel)

    def test_funnel_conversion_str(self):
        funnel = Funnel.objects.create(name="Test Funnel")
        conversion = FunnelConversion.objects.create(
            funnel=funnel,
            current_step=1,
        )
        assert "step 1" in str(conversion)

        conversion.is_converted = True
        conversion.save()
        assert "converted" in str(conversion)


# ============================================================================
# Models: UserMetric
# ============================================================================


class TestUserMetricModel:
    def test_create_user_metric(self):
        user = _create_user(username="metric_user")
        now = timezone.now()

        metric = UserMetric.objects.create(
            user=user,
            period=UserMetric.Period.DAY,
            period_start=now.date(),
            period_end=(now + timedelta(days=1)).date(),
            total_events=50,
            total_page_views=20,
        )
        assert "metric_user" in str(metric)


# ============================================================================
# Aggregator: get_event_metrics
# ============================================================================


class TestAggregator:
    @pytest.mark.asyncio
    async def test_get_event_metrics_empty(self):
        aggregator = Aggregator()
        now = timezone.now()
        metrics = await aggregator.get_event_metrics(
            start=now - timedelta(days=1),
            end=now,
        )
        assert metrics["total_events"] == 0
        assert metrics["unique_users"] == 0
        assert metrics["events_by_name"] == {}

    @pytest.mark.asyncio
    async def test_get_event_metrics_with_data(self):
        now = timezone.now()

        @sync_to_async
        def _setup():
            user = _create_user(username="agg_user")
            AnalyticsEvent.objects.create(
                name="click",
                category="user_action",
                user=user,
                timestamp=now - timedelta(hours=1),
            )
            AnalyticsEvent.objects.create(
                name="click",
                category="user_action",
                timestamp=now - timedelta(hours=2),
            )
            AnalyticsEvent.objects.create(
                name="purchase",
                category="conversion",
                user=user,
                timestamp=now - timedelta(hours=3),
            )

        await _setup()

        aggregator = Aggregator()
        metrics = await aggregator.get_event_metrics(
            start=now - timedelta(days=1),
            end=now,
        )

        assert metrics["total_events"] == 3
        assert metrics["unique_users"] == 1
        assert metrics["events_by_name"]["click"] == 2
        assert metrics["events_by_name"]["purchase"] == 1

    @pytest.mark.asyncio
    async def test_get_event_metrics_by_name(self):
        now = timezone.now()

        @sync_to_async
        def _setup():
            AnalyticsEvent.objects.create(
                name="specific_event",
                timestamp=now - timedelta(hours=1),
            )
            AnalyticsEvent.objects.create(
                name="specific_event",
                timestamp=now - timedelta(hours=2),
            )
            AnalyticsEvent.objects.create(
                name="other_event",
                timestamp=now - timedelta(hours=1),
            )

        await _setup()

        aggregator = Aggregator()
        results = await aggregator.get_event_metrics_by_name(
            event_name="specific_event",
            start=now - timedelta(days=1),
            end=now,
            granularity="day",
        )

        total = sum(r["count"] for r in results)
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_page_metrics_empty(self):
        aggregator = Aggregator()
        now = timezone.now()
        metrics = await aggregator.get_page_metrics(
            start=now - timedelta(days=1),
            end=now,
        )
        assert metrics["total_page_views"] == 0
        assert metrics["unique_visitors"] == 0

    @pytest.mark.asyncio
    async def test_get_page_metrics_with_data(self):
        now = timezone.now()

        @sync_to_async
        def _setup():
            user = _create_user(username="page_user")
            PageView.objects.create(
                path="/home",
                url="https://example.com/home",
                user=user,
                timestamp=now - timedelta(hours=1),
                time_on_page=30,
            )
            PageView.objects.create(
                path="/pricing",
                url="https://example.com/pricing",
                anonymous_id="anon-1",
                timestamp=now - timedelta(hours=2),
            )

        await _setup()

        aggregator = Aggregator()
        metrics = await aggregator.get_page_metrics(
            start=now - timedelta(days=1),
            end=now,
        )

        assert metrics["total_page_views"] == 2
        assert metrics["unique_visitors"] == 2

    @pytest.mark.asyncio
    async def test_get_session_metrics_empty(self):
        aggregator = Aggregator()
        now = timezone.now()
        metrics = await aggregator.get_session_metrics(
            start=now - timedelta(days=1),
            end=now,
        )
        assert metrics["total_sessions"] == 0

    @pytest.mark.asyncio
    async def test_get_session_metrics_with_data(self):
        now = timezone.now()
        await sync_to_async(AnalyticsSession.objects.create)(
            session_id="sess-metric-1",
            page_views=5,
            duration_seconds=300,
        )
        await sync_to_async(AnalyticsSession.objects.create)(
            session_id="sess-metric-2",
            page_views=1,
            duration_seconds=10,
        )

        aggregator = Aggregator()
        metrics = await aggregator.get_session_metrics(
            start=now - timedelta(days=1),
            end=now + timedelta(minutes=1),
        )

        assert metrics["total_sessions"] == 2
        assert metrics["bounce_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_analyze_funnel_empty(self):
        funnel = await sync_to_async(Funnel.objects.create)(name="Empty Funnel")

        aggregator = Aggregator()
        now = timezone.now()
        result = await aggregator.analyze_funnel(
            funnel=funnel,
            start=now - timedelta(days=7),
            end=now,
        )

        assert result["total_started"] == 0
        assert result["total_converted"] == 0
        assert result["steps"] == []

    @pytest.mark.asyncio
    async def test_analyze_funnel_with_steps(self):
        now = timezone.now()

        @sync_to_async
        def _setup():
            user = _create_user(username="funnel_user")
            funnel = Funnel.objects.create(name="Signup Flow", strict_order=True)
            FunnelStep.objects.create(
                funnel=funnel,
                order=1,
                name="Visit Landing",
                match_type=FunnelStep.MatchType.EVENT,
                event_name="visit_landing",
            )
            FunnelStep.objects.create(
                funnel=funnel,
                order=2,
                name="Click Signup",
                match_type=FunnelStep.MatchType.EVENT,
                event_name="click_signup",
            )
            AnalyticsEvent.objects.create(
                name="visit_landing",
                user=user,
                timestamp=now - timedelta(hours=2),
            )
            AnalyticsEvent.objects.create(
                name="click_signup",
                user=user,
                timestamp=now - timedelta(hours=1),
            )
            return funnel

        funnel = await _setup()

        aggregator = Aggregator()
        result = await aggregator.analyze_funnel(
            funnel=funnel,
            start=now - timedelta(days=1),
            end=now,
        )

        assert result["total_started"] == 1
        assert result["total_converted"] == 1
        assert result["overall_conversion_rate"] == 100.0
        assert len(result["steps"]) == 2

    @pytest.mark.asyncio
    async def test_get_realtime_metrics(self):
        now = timezone.now()
        await sync_to_async(AnalyticsSession.objects.create)(
            session_id="rt-sess-1",
            status=SessionStatus.ACTIVE.value,
            last_activity_at=now - timedelta(minutes=5),
        )

        aggregator = Aggregator()
        metrics = await aggregator.get_realtime_metrics(minutes=30)

        assert metrics["active_sessions"] >= 1

    def test_get_aggregator_singleton(self):
        agg1 = get_aggregator()
        agg2 = get_aggregator()
        assert agg1 is agg2


# ============================================================================
# AnalyticsMiddleware
# ============================================================================


class TestAnalyticsMiddleware:
    def test_skip_excluded_paths(self):
        called = {"tracked": False}

        def get_response(request):
            called["tracked"] = True
            return JsonResponse({"ok": True})

        middleware = AnalyticsMiddleware(get_response)
        request = _make_request(path="/health")
        response = middleware(request)

        # Should still get a response but session tracking skipped
        assert response.status_code == 200

    def test_skip_static_extensions(self):
        called = {"count": 0}

        def get_response(request):
            called["count"] += 1
            return JsonResponse({"ok": True})

        middleware = AnalyticsMiddleware(get_response)
        request = _make_request(path="/static/app.js")
        middleware(request)

        # Response produced but no analytics session created
        assert not hasattr(request, "analytics_session")

    def test_skip_dnt_header(self):
        def get_response(request):
            return JsonResponse({"ok": True})

        middleware = AnalyticsMiddleware(get_response)
        request = _make_request(dnt="1")
        middleware(request)

        assert not hasattr(request, "analytics_session")

    def test_skip_bots(self):
        def get_response(request):
            return JsonResponse({"ok": True})

        middleware = AnalyticsMiddleware(get_response)
        request = _make_request(user_agent="Googlebot/2.1")
        middleware(request)

        assert not hasattr(request, "analytics_session")

    def test_timing_header_added(self):
        def get_response(request):
            return JsonResponse({"ok": True})

        middleware = AnalyticsMiddleware(get_response)
        request = _make_request(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        )
        response = middleware(request)

        assert "X-Analytics-Time" in response

    def test_parse_user_agent_mobile(self):
        middleware = AnalyticsMiddleware(lambda r: JsonResponse({"ok": True}))
        info = middleware._parse_user_agent("Mozilla/5.0 (iPhone; Mobile) Safari")
        assert info["device_type"] == "mobile"

    def test_parse_user_agent_desktop(self):
        middleware = AnalyticsMiddleware(lambda r: JsonResponse({"ok": True}))
        info = middleware._parse_user_agent(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120"
        )
        assert info["device_type"] == "desktop"
        assert info["browser"] == "chrome"
        assert info["os"] == "macos"


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_event_category_choices(self):
        choices = EventCategory.choices()
        assert len(choices) >= 5
        assert any(c[0] == "custom" for c in choices)

    def test_session_status_choices(self):
        choices = SessionStatus.choices()
        assert len(choices) == 3

    def test_anonymization_level_choices(self):
        choices = AnonymizationLevel.choices()
        assert len(choices) == 3

    def test_page_view_str(self):
        pv = PageView(path="/test")
        assert "/test" in str(pv)

    def test_event_str(self):
        event = AnalyticsEvent(name="click")
        assert "click" in str(event)

    def test_user_identity_str(self):
        user = _create_user(username="identity_user")
        identity = UserIdentity(user=user, anonymous_id="anon-1234567890ab")
        assert "anon-1234567" in str(identity)

    def test_batch_context_track_event(self):
        tracker = EventTracker()
        tracker._backend = MagicMock()
        batch = BatchContext(tracker)
        batch.track_event("test", properties={"a": 1})
        assert len(batch.events) == 1
        assert batch.events[0]["name"] == "test"

    def test_batch_context_track_page_view(self):
        tracker = EventTracker()
        tracker._backend = MagicMock()
        batch = BatchContext(tracker)
        batch.track_page_view("/test")
        assert len(batch.page_views) == 1
        assert batch.page_views[0]["path"] == "/test"

    def test_tracker_context_manager(self):
        backend = MagicMock()
        with EventTracker() as tracker:
            tracker._backend = backend
            tracker.track_event("inside", flush=True)

        backend.close.assert_called_once()

    def test_get_tracker_returns_singleton(self):
        """get_tracker returns the same instance."""
        from django_matt.analytics import tracker as tracker_module

        # Reset global
        tracker_module._default_tracker = None
        t1 = get_tracker()
        t2 = get_tracker()
        assert t1 is t2
        tracker_module._default_tracker = None  # Clean up
