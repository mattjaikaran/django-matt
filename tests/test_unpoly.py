"""Tests for django_matt.unpoly module."""

from __future__ import annotations

from django.http import HttpResponse
from django.template import Context, Template
from django.test import RequestFactory

import orjson
import pytest

from django_matt.unpoly import (
    UnpolyResponse,
    up_redirect,
)
from django_matt.unpoly.config import UnpolyConfig, get_unpoly_config
from django_matt.unpoly.decorators import (
    up_fail_target,
    up_layer,
    up_only,
    up_target,
    up_validate,
    vary_on_unpoly,
)
from django_matt.unpoly.middleware import (
    UnpolyMiddleware,
    _add_vary_header,
    _append_event,
    unpoly_context_processor,
)
from django_matt.unpoly.request import (
    UnpolyDetails,
    get_up_mode,
    get_up_target,
    get_up_validate,
    is_unpoly_request,
)


@pytest.fixture
def rf():
    return RequestFactory()


# ---------------------------------------------------------------------------
# Request detection
# ---------------------------------------------------------------------------


class TestUnpolyDetails:
    def test_from_request_unpoly(self, rf):
        request = rf.get("/", HTTP_X_UP_TARGET=".main")
        details = UnpolyDetails.from_request(request)
        assert details.is_unpoly is True
        assert details.target == ".main"
        assert bool(details) is True

    def test_from_request_not_unpoly(self, rf):
        request = rf.get("/")
        details = UnpolyDetails.from_request(request)
        assert details.is_unpoly is False
        assert details.target is None
        assert bool(details) is False

    def test_all_headers_parsed(self, rf):
        ctx = orjson.dumps({"user": "admin"}).decode()
        request = rf.get(
            "/",
            HTTP_X_UP_TARGET=".content",
            HTTP_X_UP_FAIL_TARGET=".errors",
            HTTP_X_UP_MODE="modal",
            HTTP_X_UP_FAIL_MODE="root",
            HTTP_X_UP_VALIDATE="email",
            HTTP_X_UP_CONTEXT=ctx,
            HTTP_X_UP_VERSION="3.7.0",
        )
        details = UnpolyDetails.from_request(request)
        assert details.target == ".content"
        assert details.fail_target == ".errors"
        assert details.mode == "modal"
        assert details.fail_mode == "root"
        assert details.validate == "email"
        assert details.context == {"user": "admin"}
        assert details.version == "3.7.0"
        assert details.is_validating is True

    def test_invalid_context_json(self, rf):
        request = rf.get("/", HTTP_X_UP_TARGET=".x", HTTP_X_UP_CONTEXT="not-json")
        details = UnpolyDetails.from_request(request)
        assert details.context is None

    def test_bool_false_when_no_target(self, rf):
        # Only X-Up-Mode, no X-Up-Target — not considered an Unpoly request
        request = rf.get("/", HTTP_X_UP_MODE="modal")
        details = UnpolyDetails.from_request(request)
        assert bool(details) is False


class TestRequestHelpers:
    def test_is_unpoly_request_true(self, rf):
        request = rf.get("/", HTTP_X_UP_TARGET=".main")
        assert is_unpoly_request(request) is True

    def test_is_unpoly_request_false(self, rf):
        request = rf.get("/")
        assert is_unpoly_request(request) is False

    def test_get_up_target(self, rf):
        request = rf.get("/", HTTP_X_UP_TARGET=".sidebar")
        assert get_up_target(request) == ".sidebar"

    def test_get_up_target_none(self, rf):
        request = rf.get("/")
        assert get_up_target(request) is None

    def test_get_up_mode(self, rf):
        request = rf.get("/", HTTP_X_UP_MODE="drawer")
        assert get_up_mode(request) == "drawer"

    def test_get_up_validate(self, rf):
        request = rf.get("/", HTTP_X_UP_VALIDATE="username")
        assert get_up_validate(request) == "username"


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


def _simple_view(request):
    return HttpResponse("ok")


def _redirect_view(request):
    return HttpResponse(status=302, headers={"Location": "/next/"})


class TestUnpolyMiddleware:
    def test_attaches_up_to_request(self, rf):
        request = rf.get("/", HTTP_X_UP_TARGET=".main")
        middleware = UnpolyMiddleware(_simple_view)
        middleware(request)
        assert hasattr(request, "up")
        assert request.up.target == ".main"

    def test_non_unpoly_no_response_headers(self, rf):
        request = rf.get("/")
        middleware = UnpolyMiddleware(_simple_view)
        response = middleware(request)
        assert "X-Up-Location" not in response
        assert "X-Up-Method" not in response

    def test_sets_location_and_method(self, rf):
        request = rf.get("/page/", HTTP_X_UP_TARGET=".main")
        middleware = UnpolyMiddleware(_simple_view)
        response = middleware(request)
        assert response["X-Up-Location"] == "/page/"
        assert response["X-Up-Method"] == "GET"

    def test_adds_vary_header(self, rf):
        request = rf.get("/", HTTP_X_UP_TARGET=".main")
        middleware = UnpolyMiddleware(_simple_view)
        response = middleware(request)
        assert "X-Up-Target" in response.get("Vary", "")

    def test_version_mismatch_emits_expired_event(self, rf, settings):
        settings.UNPOLY = {"version": "3.8.0"}
        # Reset cached config
        import django_matt.unpoly.config as cfg

        cfg._config = None
        try:
            request = rf.get("/", HTTP_X_UP_TARGET=".main", HTTP_X_UP_VERSION="3.7.0")
            middleware = UnpolyMiddleware(_simple_view)
            response = middleware(request)
            events = orjson.loads(response["X-Up-Events"])
            assert any(e["type"] == "up:fragment:expired" for e in events)
        finally:
            cfg._config = None

    def test_redirect_preserves_target(self, rf):
        request = rf.get(
            "/",
            HTTP_X_UP_TARGET=".content",
            HTTP_X_UP_CONTEXT=orjson.dumps({"key": "val"}).decode(),
        )
        middleware = UnpolyMiddleware(_redirect_view)
        response = middleware(request)
        assert response["X-Up-Target"] == ".content"
        ctx = orjson.loads(response["X-Up-Context"])
        assert ctx == {"key": "val"}


class TestAddVaryHeader:
    def test_adds_to_empty(self):
        response = HttpResponse()
        _add_vary_header(response, "X-Up-Target")
        assert response["Vary"] == "X-Up-Target"

    def test_appends_to_existing(self):
        response = HttpResponse()
        response["Vary"] = "Accept"
        _add_vary_header(response, "X-Up-Target")
        assert response["Vary"] == "Accept, X-Up-Target"

    def test_no_duplicate(self):
        response = HttpResponse()
        response["Vary"] = "X-Up-Target"
        _add_vary_header(response, "X-Up-Target")
        assert response["Vary"] == "X-Up-Target"


class TestAppendEvent:
    def test_single_event(self):
        response = HttpResponse()
        _append_event(response, "item:created")
        events = orjson.loads(response["X-Up-Events"])
        assert events == [{"type": "item:created"}]

    def test_event_with_data(self):
        response = HttpResponse()
        _append_event(response, "item:created", {"id": 42})
        events = orjson.loads(response["X-Up-Events"])
        assert events == [{"type": "item:created", "id": 42}]

    def test_multiple_events(self):
        response = HttpResponse()
        _append_event(response, "a")
        _append_event(response, "b")
        events = orjson.loads(response["X-Up-Events"])
        assert len(events) == 2
        assert events[0]["type"] == "a"
        assert events[1]["type"] == "b"


class TestContextProcessor:
    def test_returns_up_from_request_attr(self, rf):
        request = rf.get("/", HTTP_X_UP_TARGET=".main")
        request.up = UnpolyDetails.from_request(request)
        ctx = unpoly_context_processor(request)
        assert ctx["up"].target == ".main"

    def test_parses_if_no_up_attr(self, rf):
        request = rf.get("/", HTTP_X_UP_TARGET=".sidebar")
        # No request.up attribute
        ctx = unpoly_context_processor(request)
        assert ctx["up"].target == ".sidebar"


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


class TestUpTarget:
    def test_sets_target_header(self, rf):
        @up_target(".content")
        def view(request):
            return HttpResponse("ok")

        request = rf.get("/")
        response = view(request)
        assert response["X-Up-Target"] == ".content"

    def test_does_not_override_existing(self, rf):
        @up_target(".content")
        def view(request):
            resp = HttpResponse("ok")
            resp["X-Up-Target"] = ".override"
            return resp

        request = rf.get("/")
        response = view(request)
        assert response["X-Up-Target"] == ".override"

    def test_stores_attr(self):
        @up_target(".nav")
        def view(request):
            return HttpResponse()

        assert view.up_target == ".nav"


class TestUpLayer:
    def test_sets_mode_header(self, rf):
        @up_layer("modal")
        def view(request):
            return HttpResponse("ok")

        response = view(rf.get("/"))
        assert response["X-Up-Mode"] == "modal"

    def test_does_not_override_existing(self, rf):
        @up_layer("modal")
        def view(request):
            resp = HttpResponse()
            resp["X-Up-Mode"] = "drawer"
            return resp

        response = view(rf.get("/"))
        assert response["X-Up-Mode"] == "drawer"


class TestUpFailTarget:
    def test_sets_fail_target_header(self, rf):
        @up_fail_target(".errors")
        def view(request):
            return HttpResponse("ok")

        response = view(rf.get("/"))
        assert response["X-Up-Fail-Target"] == ".errors"


class TestUpOnly:
    def test_allows_unpoly_request(self, rf):
        @up_only
        def view(request):
            return HttpResponse("allowed")

        request = rf.get("/", HTTP_X_UP_TARGET=".main")
        request.up = UnpolyDetails.from_request(request)
        response = view(request)
        assert response.status_code == 200

    def test_rejects_non_unpoly_request(self, rf):
        @up_only
        def view(request):
            return HttpResponse("allowed")

        request = rf.get("/")
        response = view(request)
        assert response.status_code == 422


class TestUpValidate:
    def test_allows_validation_request(self, rf):
        @up_validate
        def view(request):
            return HttpResponse("valid")

        request = rf.get("/", HTTP_X_UP_TARGET=".main", HTTP_X_UP_VALIDATE="email")
        request.up = UnpolyDetails.from_request(request)
        response = view(request)
        assert response.status_code == 200

    def test_rejects_non_validation_request(self, rf):
        @up_validate
        def view(request):
            return HttpResponse("valid")

        request = rf.get("/", HTTP_X_UP_TARGET=".main")
        request.up = UnpolyDetails.from_request(request)
        response = view(request)
        assert response.status_code == 422


class TestVaryOnUnpoly:
    def test_adds_vary_header(self, rf):
        @vary_on_unpoly
        def view(request):
            return HttpResponse("ok")

        response = view(rf.get("/"))
        assert response["Vary"] == "X-Up-Target"

    def test_appends_to_existing_vary(self, rf):
        @vary_on_unpoly
        def view(request):
            resp = HttpResponse("ok")
            resp["Vary"] = "Accept-Language"
            return resp

        response = view(rf.get("/"))
        assert "Accept-Language" in response["Vary"]
        assert "X-Up-Target" in response["Vary"]


# ---------------------------------------------------------------------------
# UnpolyResponse
# ---------------------------------------------------------------------------


class TestUnpolyResponse:
    def test_set_target(self):
        resp = UnpolyResponse("ok").set_target(".main")
        assert resp["X-Up-Target"] == ".main"

    def test_emit_event(self):
        resp = UnpolyResponse("ok").emit_event("item:saved", id=1)
        events = orjson.loads(resp["X-Up-Events"])
        assert len(events) == 1
        assert events[0]["type"] == "item:saved"
        assert events[0]["id"] == 1

    def test_emit_multiple_events(self):
        resp = (
            UnpolyResponse("ok")
            .emit_event("a")
            .emit_event("b", key="val")
        )
        events = orjson.loads(resp["X-Up-Events"])
        assert len(events) == 2
        assert events[1]["key"] == "val"

    def test_clear_cache_with_patterns(self):
        resp = UnpolyResponse("ok").clear_cache("/items/*", "/users/*")
        assert resp["X-Up-Clear-Cache"] == "/items/* /users/*"

    def test_clear_cache_all(self):
        resp = UnpolyResponse("ok").clear_cache()
        assert resp["X-Up-Clear-Cache"] == "*"

    def test_accept_layer_with_value(self):
        resp = UnpolyResponse("ok").accept_layer(status="saved", id=5)
        data = orjson.loads(resp["X-Up-Accept-Layer"])
        assert data["status"] == "saved"
        assert data["id"] == 5

    def test_accept_layer_empty(self):
        resp = UnpolyResponse("ok").accept_layer()
        assert resp["X-Up-Accept-Layer"] == "true"

    def test_dismiss_layer_with_value(self):
        resp = UnpolyResponse("ok").dismiss_layer(reason="cancelled")
        data = orjson.loads(resp["X-Up-Dismiss-Layer"])
        assert data["reason"] == "cancelled"

    def test_dismiss_layer_empty(self):
        resp = UnpolyResponse("ok").dismiss_layer()
        assert resp["X-Up-Dismiss-Layer"] == "true"

    def test_set_context(self):
        resp = UnpolyResponse("ok").set_context(role="admin", tenant=42)
        ctx = orjson.loads(resp["X-Up-Context"])
        assert ctx == {"role": "admin", "tenant": 42}

    def test_chained_methods(self):
        resp = (
            UnpolyResponse("<div>ok</div>")
            .set_target(".content")
            .emit_event("saved")
            .clear_cache("/items/*")
            .set_context(user="matt")
        )
        assert resp["X-Up-Target"] == ".content"
        assert "saved" in resp["X-Up-Events"]
        assert resp["X-Up-Clear-Cache"] == "/items/*"
        ctx = orjson.loads(resp["X-Up-Context"])
        assert ctx["user"] == "matt"


class TestUpRedirect:
    def test_redirect_sets_location_header(self):
        resp = up_redirect("/dashboard/")
        assert resp.status_code == 302
        assert resp["X-Up-Location"] == "/dashboard/"
        assert resp["Location"] == "/dashboard/"


# ---------------------------------------------------------------------------
# Template tags
# ---------------------------------------------------------------------------


class TestTemplateTags:
    @pytest.fixture(autouse=True)
    def _register_tags(self):
        """Register unpoly_tags library so {% load unpoly_tags %} works."""
        from django.template import engines

        from django_matt.unpoly.templatetags import unpoly_tags

        engine = engines["django"]
        engine.engine.template_libraries["unpoly_tags"] = unpoly_tags.register
        yield

    def test_up_current(self):
        t = Template('{% load unpoly_tags %}{% up_current "/dash/" %}')
        result = t.render(Context())
        assert '[up-current="/dash/"]' in result

    def test_up_nav(self):
        t = Template('{% load unpoly_tags %}{% up_nav %}<a href="/">Home</a>{% end_up_nav %}')
        result = t.render(Context())
        assert "<nav up-nav>" in result
        assert '<a href="/">Home</a>' in result
        assert "</nav>" in result

    def test_up_config_empty(self, settings):
        import django_matt.unpoly.config as cfg

        settings.UNPOLY = {}
        cfg._config = None
        try:
            t = Template("{% load unpoly_tags %}{% up_config %}")
            result = t.render(Context())
            # No config to emit — empty string
            assert result.strip() == ""
        finally:
            cfg._config = None

    def test_up_config_with_version(self, settings):
        import django_matt.unpoly.config as cfg

        settings.UNPOLY = {"version": "3.8.0"}
        cfg._config = None
        try:
            t = Template("{% load unpoly_tags %}{% up_config %}")
            result = t.render(Context())
            assert "up.network.config.update" in result
            assert "3.8.0" in result
        finally:
            cfg._config = None

    def test_up_config_disabled(self, settings):
        import django_matt.unpoly.config as cfg

        settings.UNPOLY = {"enabled": False}
        cfg._config = None
        try:
            t = Template("{% load unpoly_tags %}{% up_config %}")
            result = t.render(Context())
            assert '"enabled":false' in result or '"enabled": false' in result
        finally:
            cfg._config = None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestUnpolyConfig:
    def test_defaults(self):
        config = UnpolyConfig()
        assert config.enabled is True
        assert config.version is None
        assert "GET" in config.safe_methods

    def test_frozen(self):
        config = UnpolyConfig()
        with pytest.raises((AttributeError, TypeError, ValueError)):
            config.enabled = False

    def test_get_unpoly_config_reads_settings(self, settings):
        import django_matt.unpoly.config as cfg

        settings.UNPOLY = {"version": "3.9.0", "enabled": False}
        cfg._config = None
        try:
            config = get_unpoly_config()
            assert config.version == "3.9.0"
            assert config.enabled is False
        finally:
            cfg._config = None
