"""Tests for JWT authentication middleware variants."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from asgiref.sync import sync_to_async

from django_matt.auth.jwt import acreate_access_token, create_access_token, create_refresh_token
from django_matt.auth.middleware import (
    JWTAuthenticationMiddleware,
    JWTAuthenticationMiddlewareAsync,
    JWTStrictAuthenticationMiddleware,
    _set_request_auser,
)

User = get_user_model()


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
@pytest.mark.django_db
def user(db):
    return User.objects.create_user(
        username="mwuser",
        email="mw@example.com",
        password="TestPass123!",
        is_active=True,
    )


@pytest.fixture
@pytest.mark.django_db
def inactive_user(db):
    return User.objects.create_user(
        username="mwinactive",
        email="mwinactive@example.com",
        password="TestPass123!",
        is_active=False,
    )


def _make_response(content="ok"):
    from django.http import HttpResponse

    return HttpResponse(content)


# =============================================================================
# _set_request_auser
# =============================================================================


class TestSetRequestAuser:
    async def test_auser_returns_provided_user(self, rf):
        request = rf.get("/")
        user = AnonymousUser()
        _set_request_auser(request, user)
        result = await request.auser()
        assert result is user

    async def test_auser_returns_authenticated_user(self, rf, user):
        request = rf.get("/")
        _set_request_auser(request, user)
        result = await request.auser()
        assert result.pk == user.pk


# =============================================================================
# JWTAuthenticationMiddleware (sync)
# =============================================================================


class TestJWTAuthenticationMiddleware:
    @pytest.mark.django_db
    def test_valid_token_sets_user(self, rf, user):
        token = create_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        middleware = JWTAuthenticationMiddleware(lambda r: _make_response())
        middleware(request)

        assert request.user.is_authenticated
        assert request.user.pk == user.pk
        assert hasattr(request, "token_payload")

    @pytest.mark.django_db
    def test_no_token_sets_anonymous(self, rf):
        request = rf.get("/")
        # Remove any pre-set user
        if hasattr(request, "user"):
            delattr(request, "user")

        middleware = JWTAuthenticationMiddleware(lambda r: _make_response())
        middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @pytest.mark.django_db
    def test_invalid_token_sets_anonymous(self, rf):
        request = rf.get("/", HTTP_AUTHORIZATION="Bearer invalid.token.here")

        middleware = JWTAuthenticationMiddleware(lambda r: _make_response())
        middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @pytest.mark.django_db
    def test_expired_token_sets_anonymous(self, rf, user):
        from datetime import timedelta

        token = create_access_token(user, lifetime=timedelta(seconds=-1))

        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        middleware = JWTAuthenticationMiddleware(lambda r: _make_response())
        middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @pytest.mark.django_db
    def test_inactive_user_token_sets_anonymous(self, rf, inactive_user):
        token = create_access_token(inactive_user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        middleware = JWTAuthenticationMiddleware(lambda r: _make_response())
        middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @pytest.mark.django_db
    def test_preserves_existing_user_when_no_token(self, rf, user):
        request = rf.get("/")
        request.user = user  # pre-set by another middleware

        middleware = JWTAuthenticationMiddleware(lambda r: _make_response())
        middleware(request)

        # Should keep existing user, not overwrite with anonymous
        assert request.user.pk == user.pk

    @pytest.mark.django_db
    def test_auser_set_on_request(self, rf, user):
        token = create_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        middleware = JWTAuthenticationMiddleware(lambda r: _make_response())
        middleware(request)

        assert hasattr(request, "auser")
        assert callable(request.auser)

    @pytest.mark.django_db
    def test_refresh_token_rejected(self, rf, user):
        """Middleware should reject refresh tokens (access tokens only)."""
        token = create_refresh_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        middleware = JWTAuthenticationMiddleware(lambda r: _make_response())
        middleware(request)

        assert isinstance(request.user, AnonymousUser)


# =============================================================================
# JWTAuthenticationMiddlewareAsync
# =============================================================================


class TestJWTAuthenticationMiddlewareAsync:
    @pytest.mark.django_db(transaction=True)
    async def test_valid_token_sets_user(self, rf):
        user = await User.objects.acreate_user(
            username="async_mw_user",
            email="async_mw@example.com",
            password="TestPass123!",
        )
        token = await acreate_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        async def get_response(r):
            return _make_response()

        middleware = JWTAuthenticationMiddlewareAsync(get_response)
        await middleware(request)

        assert request.user.is_authenticated
        assert request.user.pk == user.pk

    @pytest.mark.django_db(transaction=True)
    async def test_no_token_sets_anonymous(self, rf):
        request = rf.get("/")
        if hasattr(request, "user"):
            delattr(request, "user")

        async def get_response(r):
            return _make_response()

        middleware = JWTAuthenticationMiddlewareAsync(get_response)
        await middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @pytest.mark.django_db(transaction=True)
    async def test_invalid_token_sets_anonymous(self, rf):
        request = rf.get("/", HTTP_AUTHORIZATION="Bearer garbage")

        async def get_response(r):
            return _make_response()

        middleware = JWTAuthenticationMiddlewareAsync(get_response)
        await middleware(request)

        assert isinstance(request.user, AnonymousUser)

    @pytest.mark.django_db(transaction=True)
    async def test_inactive_user_sets_anonymous(self, rf):
        inactive_user = await User.objects.acreate_user(
            username="async_mw_inactive",
            email="async_mw_inactive@example.com",
            password="TestPass123!",
            is_active=False,
        )
        token = await acreate_access_token(inactive_user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        async def get_response(r):
            return _make_response()

        middleware = JWTAuthenticationMiddlewareAsync(get_response)
        await middleware(request)

        assert isinstance(request.user, AnonymousUser)


# =============================================================================
# JWTStrictAuthenticationMiddleware
# =============================================================================


class TestJWTStrictAuthenticationMiddleware:
    @pytest.mark.django_db
    def test_valid_token_passes_through(self, rf, user):
        token = create_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        middleware = JWTStrictAuthenticationMiddleware(lambda r: _make_response())
        response = middleware(request)

        assert response.status_code == 200
        assert request.user.pk == user.pk
        assert hasattr(request, "token_payload")

    @pytest.mark.django_db
    def test_no_token_allows_anonymous(self, rf):
        request = rf.get("/")
        if hasattr(request, "user"):
            delattr(request, "user")

        middleware = JWTStrictAuthenticationMiddleware(lambda r: _make_response())
        response = middleware(request)

        assert response.status_code == 200
        assert isinstance(request.user, AnonymousUser)

    @pytest.mark.django_db
    def test_invalid_token_returns_401(self, rf):
        request = rf.get("/", HTTP_AUTHORIZATION="Bearer bad.token.here")

        middleware = JWTStrictAuthenticationMiddleware(lambda r: _make_response())
        response = middleware(request)

        assert response.status_code == 401
        body = json.loads(response.content)
        assert body["code"] == "token_invalid"

    @pytest.mark.django_db
    def test_expired_token_returns_401(self, rf, user):
        from datetime import timedelta

        token = create_access_token(user, lifetime=timedelta(seconds=-1))

        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        middleware = JWTStrictAuthenticationMiddleware(lambda r: _make_response())
        response = middleware(request)

        assert response.status_code == 401
        body = json.loads(response.content)
        assert body["code"] == "token_expired"

    @pytest.mark.django_db
    def test_deleted_user_returns_401(self, rf, user):
        token = create_access_token(user)
        user.delete()

        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        middleware = JWTStrictAuthenticationMiddleware(lambda r: _make_response())
        response = middleware(request)

        assert response.status_code == 401
        body = json.loads(response.content)
        assert body["code"] == "user_not_found"

    @pytest.mark.django_db
    def test_inactive_user_returns_401(self, rf, inactive_user):
        token = create_access_token(inactive_user)

        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        middleware = JWTStrictAuthenticationMiddleware(lambda r: _make_response())
        response = middleware(request)

        assert response.status_code == 401
        body = json.loads(response.content)
        assert body["code"] == "user_inactive"
