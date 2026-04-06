"""Tests for session authentication: config, decorators, middleware."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory

from django_matt.auth.session.config import SessionConfig, get_session_config, set_session_config
from django_matt.auth.session.decorators import (
    fresh_session_required,
    login_required,
    session_optional,
    session_required,
)

User = get_user_model()


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
@pytest.mark.django_db
def user(db):
    return User.objects.create_user(
        username="sessuser",
        email="sess@example.com",
        password="TestPass123!",
        is_active=True,
    )


@pytest.fixture
@pytest.mark.django_db
def inactive_user(db):
    return User.objects.create_user(
        username="sessinactive",
        email="sessinactive@example.com",
        password="TestPass123!",
        is_active=False,
    )


@pytest.fixture(autouse=True)
def _reset_session_config():
    """Reset global session config between tests."""
    set_session_config(None)
    yield
    set_session_config(None)


# =============================================================================
# SessionConfig
# =============================================================================


class TestSessionConfig:
    def test_defaults(self):
        config = SessionConfig()
        assert config.cookie_name == "sessionid"
        assert config.cookie_age == 86400 * 14
        assert config.cookie_secure is True
        assert config.cookie_httponly is True
        assert config.csrf_enabled is True
        assert config.csrf_cookie_name == "csrftoken"
        assert config.rotate_session_on_login is True
        assert config.fresh_session_duration == 300

    def test_from_django_settings(self):
        config = SessionConfig.from_django_settings()
        assert isinstance(config, SessionConfig)

    def test_custom_config(self):
        config = SessionConfig(
            cookie_name="my_session",
            cookie_age=3600,
            csrf_enabled=False,
            single_session_per_user=True,
        )
        assert config.cookie_name == "my_session"
        assert config.cookie_age == 3600
        assert config.csrf_enabled is False
        assert config.single_session_per_user is True

    def test_get_set_global_config(self):
        custom = SessionConfig(cookie_name="custom_sess")
        set_session_config(custom)
        retrieved = get_session_config()
        assert retrieved.cookie_name == "custom_sess"


# =============================================================================
# session_required decorator
# =============================================================================


class TestSessionRequired:
    def test_authenticated_user_passes(self, rf, user):
        @session_required
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/api/test", HTTP_ACCEPT="application/json")
        request.user = user
        response = view(request)
        assert response.status_code == 200

    def test_unauthenticated_returns_401_for_api(self, rf):
        @session_required
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/api/test", HTTP_ACCEPT="application/json")
        request.user = AnonymousUser()
        response = view(request)
        assert response.status_code == 401

    def test_unauthenticated_redirects_with_url(self, rf):
        @session_required(redirect_url="/login")
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/dashboard")
        request.user = AnonymousUser()
        response = view(request)
        assert response.status_code == 302
        assert "/login" in response.url

    async def test_async_authenticated_passes(self, rf, user):
        @session_required
        async def view(request):
            return HttpResponse("ok")

        request = rf.get("/api/test", HTTP_ACCEPT="application/json")
        request.user = user
        response = await view(request)
        assert response.status_code == 200

    async def test_async_unauthenticated_returns_401(self, rf):
        @session_required
        async def view(request):
            return HttpResponse("ok")

        request = rf.get("/api/test", HTTP_ACCEPT="application/json")
        request.user = AnonymousUser()
        response = await view(request)
        assert response.status_code == 401


# =============================================================================
# session_optional decorator
# =============================================================================


class TestSessionOptional:
    def test_authenticated_user(self, rf, user):
        @session_optional
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user
        response = view(request)
        assert response.status_code == 200

    def test_anonymous_user(self, rf):
        @session_optional
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = AnonymousUser()
        response = view(request)
        assert response.status_code == 200

    async def test_async_pass_through(self, rf, user):
        @session_optional
        async def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user
        response = await view(request)
        assert response.status_code == 200


# =============================================================================
# login_required decorator
# =============================================================================


class TestLoginRequired:
    def test_authenticated_passes(self, rf, user):
        @login_required
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/page")
        request.user = user
        response = view(request)
        assert response.status_code == 200

    def test_unauthenticated_redirects(self, rf):
        @login_required(login_url="/auth/login")
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/page")
        request.user = AnonymousUser()
        response = view(request)
        assert response.status_code == 302
        assert "/auth/login" in response.url
        assert "next=" in response.url

    def test_api_request_returns_401(self, rf):
        @login_required
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/api/data", HTTP_ACCEPT="application/json")
        request.user = AnonymousUser()
        response = view(request)
        assert response.status_code == 401

    async def test_async_authenticated_passes(self, rf, user):
        @login_required
        async def view(request):
            return HttpResponse("ok")

        request = rf.get("/page")
        request.user = user
        response = await view(request)
        assert response.status_code == 200

    async def test_async_unauthenticated_redirects(self, rf):
        @login_required(login_url="/login")
        async def view(request):
            return HttpResponse("ok")

        request = rf.get("/page")
        request.user = AnonymousUser()
        response = await view(request)
        assert response.status_code == 302


# =============================================================================
# fresh_session_required decorator
# =============================================================================


class TestFreshSessionRequired:
    def test_fresh_session_passes(self, rf, user):
        from django.utils import timezone

        @fresh_session_required(max_age=300)
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/api/change-password", HTTP_ACCEPT="application/json")
        request.user = user
        request.session = {
            "_session_created": timezone.now().isoformat(),
        }

        response = view(request)
        assert response.status_code == 200

    def test_stale_session_returns_403(self, rf, user):
        from django.utils import timezone
        from datetime import timedelta

        @fresh_session_required(max_age=300)
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/api/change-password", HTTP_ACCEPT="application/json")
        request.user = user
        # Session created 10 minutes ago — beyond 5 minute max_age
        created = (timezone.now() - timedelta(minutes=10)).isoformat()
        request.session = {"_session_created": created}

        response = view(request)
        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, rf):
        @fresh_session_required
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/api/sensitive", HTTP_ACCEPT="application/json")
        request.user = AnonymousUser()
        response = view(request)
        assert response.status_code == 401

    def test_no_session_returns_403(self, rf, user):
        @fresh_session_required(max_age=300)
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/api/sensitive", HTTP_ACCEPT="application/json")
        request.user = user
        # No session attribute
        response = view(request)
        assert response.status_code == 403

    async def test_async_fresh_passes(self, rf, user):
        from django.utils import timezone

        @fresh_session_required(max_age=300)
        async def view(request):
            return HttpResponse("ok")

        request = rf.get("/api/sensitive", HTTP_ACCEPT="application/json")
        request.user = user
        request.session = {
            "_session_created": timezone.now().isoformat(),
        }
        response = await view(request)
        assert response.status_code == 200


# =============================================================================
# SessionAuthMiddleware
# =============================================================================


class TestSessionAuthMiddleware:
    @pytest.mark.django_db
    def test_authenticated_user_from_session(self, rf, user):
        from django_matt.auth.session.middleware import SessionAuthMiddleware

        request = rf.get("/")
        request.session = {"_auth_user_id": str(user.pk)}

        middleware = SessionAuthMiddleware(lambda r: HttpResponse("ok"))
        middleware(request)

        assert request.user.is_authenticated
        assert request.user.pk == user.pk

    @pytest.mark.django_db
    def test_no_user_id_in_session(self, rf):
        from django_matt.auth.session.middleware import SessionAuthMiddleware

        request = rf.get("/")
        request.session = {}

        middleware = SessionAuthMiddleware(lambda r: HttpResponse("ok"))
        middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @pytest.mark.django_db
    def test_nonexistent_user_in_session(self, rf):
        from django_matt.auth.session.middleware import SessionAuthMiddleware

        request = rf.get("/")
        request.session = {"_auth_user_id": "99999"}

        middleware = SessionAuthMiddleware(lambda r: HttpResponse("ok"))
        middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @pytest.mark.django_db
    def test_inactive_user_in_session(self, rf, inactive_user):
        from django_matt.auth.session.middleware import SessionAuthMiddleware

        request = rf.get("/")
        request.session = {"_auth_user_id": str(inactive_user.pk)}

        middleware = SessionAuthMiddleware(lambda r: HttpResponse("ok"))
        middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @pytest.mark.django_db
    def test_no_session_attribute(self, rf):
        from django_matt.auth.session.middleware import SessionAuthMiddleware

        request = rf.get("/")
        # No session attribute at all

        middleware = SessionAuthMiddleware(lambda r: HttpResponse("ok"))
        response = middleware(request)

        assert isinstance(request.user, AnonymousUser)
        assert response.status_code == 200


# =============================================================================
# AsyncSessionAuthMiddleware
# =============================================================================


class TestAsyncSessionAuthMiddleware:
    @pytest.mark.django_db(transaction=True)
    async def test_authenticated_user(self, rf):
        from django_matt.auth.session.middleware import AsyncSessionAuthMiddleware

        user = await User.objects.acreate_user(
            username="async_sess_user",
            email="async_sess@example.com",
            password="TestPass123!",
        )
        request = rf.get("/")
        request.session = {"_auth_user_id": str(user.pk)}

        async def get_response(r):
            return HttpResponse("ok")

        middleware = AsyncSessionAuthMiddleware(get_response)
        await middleware(request)

        assert request.user.is_authenticated
        assert request.user.pk == user.pk

    @pytest.mark.django_db(transaction=True)
    async def test_no_session(self, rf):
        from django_matt.auth.session.middleware import AsyncSessionAuthMiddleware

        request = rf.get("/")

        async def get_response(r):
            return HttpResponse("ok")

        middleware = AsyncSessionAuthMiddleware(get_response)
        await middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @pytest.mark.django_db(transaction=True)
    async def test_nonexistent_user(self, rf):
        from django_matt.auth.session.middleware import AsyncSessionAuthMiddleware

        request = rf.get("/")
        request.session = {"_auth_user_id": "99999"}

        async def get_response(r):
            return HttpResponse("ok")

        middleware = AsyncSessionAuthMiddleware(get_response)
        await middleware(request)

        assert isinstance(request.user, AnonymousUser)
