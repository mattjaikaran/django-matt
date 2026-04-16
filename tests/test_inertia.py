from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.template import Context, Template
from django.test import RequestFactory, override_settings

import orjson
import pytest

from django_matt.inertia.config import InertiaConfig, _reset_config, get_inertia_config
from django_matt.inertia.middleware import AsyncInertiaMiddleware, InertiaMiddleware
from django_matt.inertia.response import (
    DeferredProp,
    InertiaResponse,
    LazyProp,
    MergeProp,
    _build_page_data,
    _resolve_props,
    defer,
    inertia,
    lazy,
    merge,
)
from django_matt.inertia.share import SharedDataMiddleware, share
from django_matt.inertia.ssr import SSRResponse, render_ssr
from django_matt.inertia.testing import (
    InertiaTestMixin,
    get_inertia_page,
    inertia_headers,
)
from django_matt.inertia.views import InertiaView, inertia_view


@pytest.fixture(autouse=True)
def _reset_inertia_config():
    _reset_config()
    yield
    _reset_config()


@pytest.fixture
def rf():
    return RequestFactory()


def _make_request(rf: RequestFactory, method: str = "GET", path: str = "/test/", **headers) -> HttpRequest:
    factory_method = getattr(rf, method.lower())
    return factory_method(path, **headers)


def _inertia_request(rf: RequestFactory, method: str = "GET", path: str = "/test/", **extra_headers) -> HttpRequest:
    headers = {"HTTP_X_INERTIA": "true", **extra_headers}
    return _make_request(rf, method, path, **headers)


# ---------------------------------------------------------------------------
# InertiaConfig
# ---------------------------------------------------------------------------


class TestInertiaConfig:
    def test_defaults(self):
        config = InertiaConfig()
        assert config.root_template == "base.html"
        assert config.version is None
        assert config.ssr_enabled is False
        assert config.ssr_url == "http://localhost:13714"
        assert config.json_encoder == "orjson"

    def test_custom_settings(self):
        config = InertiaConfig(
            root_template="app.html",
            version="2.0",
            ssr_enabled=True,
            ssr_url="http://ssr:3000",
            json_encoder="json",
        )
        assert config.root_template == "app.html"
        assert config.version == "2.0"
        assert config.ssr_enabled is True
        assert config.ssr_url == "http://ssr:3000"
        assert config.json_encoder == "json"

    def test_callable_version(self):
        config = InertiaConfig(version=lambda: "dynamic-v1")
        assert callable(config.version)
        assert config.version() == "dynamic-v1"

    @override_settings(INERTIA={"root_template": "custom.html", "version": "3.0"})
    def test_get_inertia_config_from_settings(self):
        config = get_inertia_config()
        assert config.root_template == "custom.html"
        assert config.version == "3.0"

    @override_settings(INERTIA={})
    def test_get_inertia_config_empty_settings(self):
        config = get_inertia_config()
        assert config.root_template == "base.html"
        assert config.version is None

    def test_get_inertia_config_no_setting(self):
        config = get_inertia_config()
        assert config.root_template == "base.html"

    @override_settings(INERTIA={"version": "cached"})
    def test_config_caching(self):
        c1 = get_inertia_config()
        c2 = get_inertia_config()
        assert c1 is c2

    @override_settings(INERTIA={"version": "v1"})
    def test_reset_config(self):
        c1 = get_inertia_config()
        _reset_config()
        c2 = get_inertia_config()
        assert c1 is not c2


# ---------------------------------------------------------------------------
# InertiaMiddleware
# ---------------------------------------------------------------------------


class TestInertiaMiddleware:
    def test_non_inertia_request_passthrough(self, rf):
        request = _make_request(rf)
        response = HttpResponse("ok")

        mw = InertiaMiddleware(lambda r: response)
        result = mw(request)

        assert result is response
        assert result.status_code == 200

    def test_inertia_header_sets_flag(self, rf):
        request = _inertia_request(rf)
        captured = {}

        def get_response(r):
            captured["_inertia"] = getattr(r, "_inertia", False)
            return HttpResponse("ok")

        mw = InertiaMiddleware(get_response)
        mw(request)
        assert captured["_inertia"] is True

    def test_non_inertia_header_flag_false(self, rf):
        request = _make_request(rf)
        captured = {}

        def get_response(r):
            captured["_inertia"] = getattr(r, "_inertia", False)
            return HttpResponse("ok")

        mw = InertiaMiddleware(get_response)
        mw(request)
        assert captured["_inertia"] is False

    @override_settings(INERTIA={"version": "1.0"})
    def test_version_mismatch_returns_409(self, rf):
        request = _inertia_request(rf, HTTP_X_INERTIA_VERSION="0.9")
        response = HttpResponse("ok")

        mw = InertiaMiddleware(lambda r: response)
        result = mw(request)

        assert result.status_code == 409
        assert result["X-Inertia-Location"] == "/test/"

    @override_settings(INERTIA={"version": "1.0"})
    def test_version_match_passes(self, rf):
        request = _inertia_request(rf, HTTP_X_INERTIA_VERSION="1.0")
        response = HttpResponse("ok")

        mw = InertiaMiddleware(lambda r: response)
        result = mw(request)

        assert result.status_code == 200

    @override_settings(INERTIA={})
    def test_no_version_configured_passes(self, rf):
        request = _inertia_request(rf, HTTP_X_INERTIA_VERSION="anything")
        response = HttpResponse("ok")

        mw = InertiaMiddleware(lambda r: response)
        result = mw(request)

        assert result.status_code == 200

    @override_settings(INERTIA={"version": "1.0"})
    def test_version_check_only_on_get(self, rf):
        request = _inertia_request(rf, method="POST", HTTP_X_INERTIA_VERSION="0.9")
        response = HttpResponse("ok")

        mw = InertiaMiddleware(lambda r: response)
        result = mw(request)

        assert result.status_code == 200

    def test_302_to_303_for_put(self, rf):
        request = _inertia_request(rf, method="PUT")
        response = HttpResponseRedirect("/next/")

        mw = InertiaMiddleware(lambda r: response)
        result = mw(request)

        assert result.status_code == 303

    def test_302_to_303_for_patch(self, rf):
        request = _inertia_request(rf, method="PATCH")
        response = HttpResponseRedirect("/next/")

        mw = InertiaMiddleware(lambda r: response)
        result = mw(request)

        assert result.status_code == 303

    def test_302_to_303_for_delete(self, rf):
        request = _inertia_request(rf, method="DELETE")
        response = HttpResponseRedirect("/next/")

        mw = InertiaMiddleware(lambda r: response)
        result = mw(request)

        assert result.status_code == 303

    def test_302_unchanged_for_get(self, rf):
        request = _inertia_request(rf)
        response = HttpResponseRedirect("/next/")

        mw = InertiaMiddleware(lambda r: response)
        result = mw(request)

        assert result.status_code == 302

    def test_302_unchanged_for_post(self, rf):
        request = _inertia_request(rf, method="POST")
        response = HttpResponseRedirect("/next/")

        mw = InertiaMiddleware(lambda r: response)
        result = mw(request)

        assert result.status_code == 302

    def test_initializes_shared_data_dict(self, rf):
        request = _make_request(rf)
        captured = {}

        def get_response(r):
            captured["has_shared"] = hasattr(r, "_inertia_shared")
            return HttpResponse("ok")

        mw = InertiaMiddleware(get_response)
        mw(request)
        assert captured["has_shared"] is True


# ---------------------------------------------------------------------------
# AsyncInertiaMiddleware
# ---------------------------------------------------------------------------


class TestAsyncInertiaMiddleware:
    @pytest.mark.asyncio
    async def test_sets_inertia_flag(self, rf):
        request = _inertia_request(rf)
        captured = {}

        async def get_response(r):
            captured["_inertia"] = getattr(r, "_inertia", False)
            return HttpResponse("ok")

        mw = AsyncInertiaMiddleware(get_response)
        await mw(request)
        assert captured["_inertia"] is True

    @pytest.mark.asyncio
    @override_settings(INERTIA={"version": "2.0"})
    async def test_version_mismatch_409(self, rf):
        request = _inertia_request(rf, HTTP_X_INERTIA_VERSION="1.0")

        async def get_response(r):
            return HttpResponse("ok")

        mw = AsyncInertiaMiddleware(get_response)
        result = await mw(request)

        assert result.status_code == 409
        assert result["X-Inertia-Location"] == "/test/"

    @pytest.mark.asyncio
    async def test_302_to_303_for_put(self, rf):
        request = _inertia_request(rf, method="PUT")

        async def get_response(r):
            return HttpResponseRedirect("/next/")

        mw = AsyncInertiaMiddleware(get_response)
        result = await mw(request)

        assert result.status_code == 303

    @pytest.mark.asyncio
    async def test_non_inertia_passthrough(self, rf):
        request = _make_request(rf)

        async def get_response(r):
            return HttpResponse("ok")

        mw = AsyncInertiaMiddleware(get_response)
        result = await mw(request)

        assert result.status_code == 200


# ---------------------------------------------------------------------------
# Prop wrappers
# ---------------------------------------------------------------------------


class TestPropWrappers:
    def test_lazy_prop_resolve(self):
        prop = lazy(lambda: [1, 2, 3])
        assert isinstance(prop, LazyProp)
        assert prop.resolve() == [1, 2, 3]

    def test_deferred_prop_resolve(self):
        prop = defer(lambda: {"key": "value"})
        assert isinstance(prop, DeferredProp)
        assert prop.group == "default"
        assert prop.resolve() == {"key": "value"}

    def test_deferred_prop_custom_group(self):
        prop = defer(lambda: "data", group="sidebar")
        assert prop.group == "sidebar"

    def test_merge_prop(self):
        prop = merge({"items": [1, 2]})
        assert isinstance(prop, MergeProp)
        assert prop.data == {"items": [1, 2]}


# ---------------------------------------------------------------------------
# _resolve_props
# ---------------------------------------------------------------------------


class TestResolveProps:
    def test_regular_props_full_load(self):
        props = {"title": "Hello", "count": 5}
        resolved = _resolve_props(props, None, "Page", None)
        assert resolved == {"title": "Hello", "count": 5}

    def test_callable_props_resolved(self):
        props = {"items": lambda: [1, 2, 3]}
        resolved = _resolve_props(props, None, "Page", None)
        assert resolved == {"items": [1, 2, 3]}

    def test_lazy_props_excluded_on_full_load(self):
        props = {"title": "Hello", "notifications": lazy(lambda: [1, 2])}
        resolved = _resolve_props(props, None, "Page", None)
        assert "title" in resolved
        assert "notifications" not in resolved

    def test_lazy_props_included_on_partial_reload(self):
        props = {"title": "Hello", "notifications": lazy(lambda: [1, 2])}
        resolved = _resolve_props(props, "Page", "Page", ["notifications"])
        assert resolved == {"notifications": [1, 2]}

    def test_deferred_props_excluded_on_full_load(self):
        props = {"title": "Hello", "activity": defer(lambda: "data")}
        resolved = _resolve_props(props, None, "Page", None)
        assert "title" in resolved
        assert "activity" not in resolved

    def test_deferred_props_included_on_partial_reload(self):
        props = {"title": "Hello", "activity": defer(lambda: "data")}
        resolved = _resolve_props(props, "Page", "Page", ["activity"])
        assert resolved == {"activity": "data"}

    def test_merge_props_always_included(self):
        props = {"items": merge([1, 2, 3])}
        resolved = _resolve_props(props, None, "Page", None)
        assert resolved == {"items": [1, 2, 3]}

    def test_partial_reload_only_requested_keys(self):
        props = {"a": 1, "b": 2, "c": 3}
        resolved = _resolve_props(props, "Page", "Page", ["a", "c"])
        assert resolved == {"a": 1, "c": 3}

    def test_partial_reload_wrong_component_treated_as_full(self):
        props = {"a": 1, "b": 2}
        resolved = _resolve_props(props, "OtherPage", "Page", ["a"])
        assert resolved == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# InertiaResponse
# ---------------------------------------------------------------------------


class TestInertiaResponse:
    def test_headers(self):
        page_data = {"component": "Test", "props": {}, "url": "/", "version": ""}
        response = InertiaResponse(page_data)

        assert response["X-Inertia"] == "true"
        assert response["Vary"] == "X-Inertia"
        assert response["Content-Type"] == "application/json"

    def test_body_is_orjson(self):
        page_data = {"component": "Test", "props": {"x": 1}, "url": "/", "version": ""}
        response = InertiaResponse(page_data)

        body = orjson.loads(response.content)
        assert body["component"] == "Test"
        assert body["props"]["x"] == 1


# ---------------------------------------------------------------------------
# inertia() helper
# ---------------------------------------------------------------------------


class TestInertiaHelper:
    @override_settings(INERTIA={})
    def test_json_response_for_inertia_request(self, rf):
        request = _inertia_request(rf)
        request._inertia_shared = {}

        response = inertia(request, "Dashboard/Index", {"count": 42})

        assert response.status_code == 200
        assert response["X-Inertia"] == "true"

        data = orjson.loads(response.content)
        assert data["component"] == "Dashboard/Index"
        assert data["props"]["count"] == 42
        assert data["url"] == "/test/"

    @override_settings(INERTIA={"version": "5.0"})
    def test_version_in_page_data(self, rf):
        request = _inertia_request(rf)
        request._inertia_shared = {}

        response = inertia(request, "Page", {})
        data = orjson.loads(response.content)
        assert data["version"] == "5.0"

    @override_settings(INERTIA={})
    def test_kwargs_merged_into_props(self, rf):
        request = _inertia_request(rf)
        request._inertia_shared = {}

        response = inertia(request, "Page", {"a": 1}, b=2)
        data = orjson.loads(response.content)
        assert data["props"]["a"] == 1
        assert data["props"]["b"] == 2

    @override_settings(INERTIA={})
    def test_shared_data_merged(self, rf):
        request = _inertia_request(rf)
        request._inertia_shared = {"app_name": "MyApp"}

        response = inertia(request, "Page", {"title": "Home"})
        data = orjson.loads(response.content)
        assert data["props"]["app_name"] == "MyApp"
        assert data["props"]["title"] == "Home"

    @override_settings(INERTIA={})
    def test_deferred_props_in_page_data(self, rf):
        request = _inertia_request(rf)
        request._inertia_shared = {}

        response = inertia(request, "Page", {
            "title": "Home",
            "sidebar": defer(lambda: "sidebar_data", group="sidebar"),
            "feed": defer(lambda: "feed_data"),
        })
        data = orjson.loads(response.content)

        assert "sidebar" not in data["props"]
        assert "feed" not in data["props"]
        assert "deferredProps" in data
        assert "sidebar" in data["deferredProps"]["sidebar"]
        assert "feed" in data["deferredProps"]["default"]

    @override_settings(INERTIA={})
    def test_merge_props_in_page_data(self, rf):
        request = _inertia_request(rf)
        request._inertia_shared = {}

        response = inertia(request, "Page", {"items": merge([1, 2, 3])})
        data = orjson.loads(response.content)

        assert data["props"]["items"] == [1, 2, 3]
        assert "mergeProps" in data
        assert "items" in data["mergeProps"]

    @override_settings(
        INERTIA={"root_template": "inertia_test.html"},
        TEMPLATES=[{
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [],
            "OPTIONS": {
                "loaders": [
                    ("django.template.loaders.locmem.Loader", {
                        "inertia_test.html": '<!DOCTYPE html><html><body><div id="app" data-page="{{ page }}"></div></body></html>',
                    }),
                ],
            },
        }],
    )
    def test_full_page_html_for_non_inertia_request(self, rf):
        request = _make_request(rf)
        request._inertia_shared = {}

        response = inertia(request, "Dashboard", {"title": "Home"})

        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="app"' in content
        assert "data-page" in content


# ---------------------------------------------------------------------------
# _build_page_data
# ---------------------------------------------------------------------------


class TestBuildPageData:
    @override_settings(INERTIA={})
    def test_basic_page_data(self, rf):
        request = _make_request(rf)
        request._inertia_shared = {}
        config = get_inertia_config()

        page = _build_page_data(request, "Users/Index", {"users": []}, config)

        assert page["component"] == "Users/Index"
        assert page["props"] == {"users": []}
        assert page["url"] == "/test/"
        assert page["version"] == ""

    @override_settings(INERTIA={})
    def test_partial_reload_headers(self, rf):
        request = _inertia_request(
            rf,
            HTTP_X_INERTIA_PARTIAL_COMPONENT="Page",
            HTTP_X_INERTIA_PARTIAL_DATA="title",
        )
        request._inertia_shared = {}
        config = get_inertia_config()

        page = _build_page_data(
            request,
            "Page",
            {"title": "Hello", "description": "World"},
            config,
        )

        assert page["props"] == {"title": "Hello"}


# ---------------------------------------------------------------------------
# share()
# ---------------------------------------------------------------------------


class TestShare:
    def test_share_sets_value(self, rf):
        request = _make_request(rf)
        share(request, "flash", {"success": "Item created"})
        assert request._inertia_shared["flash"] == {"success": "Item created"}

    def test_share_initializes_dict(self, rf):
        request = _make_request(rf)
        assert not hasattr(request, "_inertia_shared")
        share(request, "key", "value")
        assert request._inertia_shared == {"key": "value"}

    def test_share_multiple_values(self, rf):
        request = _make_request(rf)
        share(request, "a", 1)
        share(request, "b", 2)
        assert request._inertia_shared == {"a": 1, "b": 2}

    def test_share_overwrites(self, rf):
        request = _make_request(rf)
        share(request, "x", "old")
        share(request, "x", "new")
        assert request._inertia_shared["x"] == "new"


# ---------------------------------------------------------------------------
# SharedDataMiddleware
# ---------------------------------------------------------------------------


class TestSharedDataMiddleware:
    def test_shares_auth_unauthenticated(self, rf):
        request = _make_request(rf)
        request.user = MagicMock()
        request.user.is_authenticated = False

        mw = SharedDataMiddleware(lambda r: HttpResponse("ok"))
        mw(request)

        assert request._inertia_shared["auth"] == {"user": None}

    def test_shares_auth_authenticated(self, rf):
        request = _make_request(rf)
        user = MagicMock()
        user.is_authenticated = True
        user.pk = 1
        user.email = "user@example.com"
        user.is_staff = False
        user.is_superuser = False
        user.get_full_name.return_value = "Test User"
        user.get_all_permissions.return_value = {"auth.view_user"}
        del user.roles  # no RBAC roles
        request.user = user

        mw = SharedDataMiddleware(lambda r: HttpResponse("ok"))
        mw(request)

        auth = request._inertia_shared["auth"]
        assert auth["user"]["id"] == 1
        assert auth["user"]["email"] == "user@example.com"
        assert auth["user"]["name"] == "Test User"
        assert auth["user"]["is_staff"] is False
        assert auth["user"]["permissions"] == ["auth.view_user"]

    def test_shares_csrf(self, rf):
        request = _make_request(rf)
        request.user = MagicMock()
        request.user.is_authenticated = False

        mw = SharedDataMiddleware(lambda r: HttpResponse("ok"))
        mw(request)

        assert "csrf_token" in request._inertia_shared
        assert isinstance(request._inertia_shared["csrf_token"], str)
        assert len(request._inertia_shared["csrf_token"]) > 0

    def test_shares_flash_messages(self, rf):
        request = _make_request(rf)
        request.user = MagicMock()
        request.user.is_authenticated = False

        mock_messages = [
            MagicMock(level_tag="success", __str__=lambda self: "Item saved"),
        ]

        def get_response(r):
            return HttpResponse("ok")

        mw = SharedDataMiddleware(get_response)

        with patch("django.contrib.messages.get_messages", return_value=mock_messages):
            mw(request)

        assert "flash" in request._inertia_shared
        assert request._inertia_shared["flash"][0]["level"] == "success"
        assert request._inertia_shared["flash"][0]["message"] == "Item saved"

    def test_display_name_fallback_to_email(self, rf):
        request = _make_request(rf)
        user = MagicMock()
        user.is_authenticated = True
        user.pk = 1
        user.email = "user@example.com"
        user.is_staff = False
        user.is_superuser = False
        user.get_full_name.return_value = ""
        user.get_all_permissions.return_value = set()
        del user.roles
        request.user = user

        mw = SharedDataMiddleware(lambda r: HttpResponse("ok"))
        mw(request)

        assert request._inertia_shared["auth"]["user"]["name"] == "user@example.com"

    def test_roles_included_when_available(self, rf):
        request = _make_request(rf)
        user = MagicMock()
        user.is_authenticated = True
        user.pk = 1
        user.email = "admin@example.com"
        user.is_staff = True
        user.is_superuser = False
        user.get_full_name.return_value = "Admin"
        user.get_all_permissions.return_value = set()
        user.roles.values_list.return_value = ["admin", "editor"]
        request.user = user

        mw = SharedDataMiddleware(lambda r: HttpResponse("ok"))
        mw(request)

        assert request._inertia_shared["auth"]["user"]["roles"] == ["admin", "editor"]


# ---------------------------------------------------------------------------
# SSR
# ---------------------------------------------------------------------------


class TestSSR:
    @pytest.mark.asyncio
    @override_settings(INERTIA={"ssr_enabled": False})
    async def test_render_ssr_disabled(self):
        result = await render_ssr({"component": "Page", "props": {}})
        assert result is None

    @pytest.mark.asyncio
    @override_settings(INERTIA={"ssr_enabled": True, "ssr_url": "http://localhost:13714"})
    async def test_render_ssr_success(self):
        import httpx as httpx_mod

        mock_response = MagicMock()
        mock_response.content = orjson.dumps({
            "head": ["<title>Test</title>"],
            "body": '<div id="app">SSR content</div>',
        })
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(httpx_mod, "AsyncClient", return_value=mock_client):
            result = await render_ssr({"component": "Page", "props": {}})

        assert result is not None
        assert isinstance(result, SSRResponse)
        assert result.head == ["<title>Test</title>"]
        assert "SSR content" in result.body

    @pytest.mark.asyncio
    @override_settings(INERTIA={"ssr_enabled": True, "ssr_url": "http://localhost:13714"})
    async def test_render_ssr_connection_error_returns_none(self):
        import httpx as httpx_mod

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx_mod.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(httpx_mod, "AsyncClient", return_value=mock_client):
            result = await render_ssr({"component": "Page", "props": {}})

        assert result is None

    def test_ssr_response_dataclass(self):
        ssr = SSRResponse()
        assert ssr.head == []
        assert ssr.body == ""

        ssr = SSRResponse(head=["<title>Hi</title>"], body="<div>body</div>")
        assert ssr.head == ["<title>Hi</title>"]
        assert ssr.body == "<div>body</div>"


# ---------------------------------------------------------------------------
# InertiaView
# ---------------------------------------------------------------------------


class TestInertiaView:
    @override_settings(INERTIA={})
    def test_get_component_raises_when_empty(self):
        view = InertiaView()
        with pytest.raises(ValueError, match="must define a 'component' attribute"):
            view.get_component()

    def test_get_component_returns_value(self):
        class MyView(InertiaView):
            component = "Dashboard/Index"

        view = MyView()
        assert view.get_component() == "Dashboard/Index"

    def test_get_props_default_empty(self, rf):
        view = InertiaView()
        request = _make_request(rf)
        assert view.get_props(request) == {}


# ---------------------------------------------------------------------------
# @inertia_view decorator
# ---------------------------------------------------------------------------


class TestInertiaViewDecorator:
    @override_settings(INERTIA={})
    def test_decorator_returns_inertia_response(self, rf):
        @inertia_view("Dashboard/Index")
        def dashboard(request):
            return {"title": "Home"}

        request = _inertia_request(rf)
        request._inertia_shared = {}
        response = dashboard(request)

        assert response["X-Inertia"] == "true"
        data = orjson.loads(response.content)
        assert data["component"] == "Dashboard/Index"
        assert data["props"]["title"] == "Home"

    @override_settings(INERTIA={})
    def test_decorator_none_return(self, rf):
        @inertia_view("Page")
        def page(request):
            return None

        request = _inertia_request(rf)
        request._inertia_shared = {}
        response = page(request)

        data = orjson.loads(response.content)
        assert data["component"] == "Page"
        assert data["props"] == {}

    def test_decorator_passthrough_http_response(self, rf):
        redirect = HttpResponseRedirect("/login/")

        @inertia_view("Page")
        def page(request):
            return redirect

        request = _make_request(rf)
        response = page(request)

        assert response is redirect
        assert response.status_code == 302

    def test_decorator_sets_component_attr(self):
        @inertia_view("Dashboard/Index")
        def dashboard(request):
            return {}

        assert dashboard.inertia_component == "Dashboard/Index"


# ---------------------------------------------------------------------------
# Testing utilities
# ---------------------------------------------------------------------------


class TestTestingUtilities:
    def test_inertia_headers(self):
        headers = inertia_headers()
        assert headers == {"HTTP_X_INERTIA": "true"}

    def test_get_inertia_page_from_json(self):
        page_data = {"component": "Page", "props": {"x": 1}, "url": "/", "version": ""}
        response = InertiaResponse(page_data)

        page = get_inertia_page(response)
        assert page["component"] == "Page"
        assert page["props"]["x"] == 1

    def test_get_inertia_page_from_html_double_quotes(self):
        page_json = '{"component":"Page","props":{"x":1}}'
        escaped = page_json.replace("&", "&amp;").replace('"', "&quot;")
        html = f'<html><body><div id="app" data-page="{escaped}">content</div></body></html>'
        response = HttpResponse(html)

        page = get_inertia_page(response)
        assert page["component"] == "Page"

    def test_get_inertia_page_from_html_single_quotes(self):
        page_json = '{"component":"Page","props":{}}'
        escaped = page_json.replace("'", "&#x27;")
        html = f"<html><body><div id='app' data-page='{escaped}'>content</div></body></html>"
        response = HttpResponse(html)

        page = get_inertia_page(response)
        assert page["component"] == "Page"

    def test_get_inertia_page_raises_on_missing(self):
        response = HttpResponse("<html><body>No inertia</body></html>")

        with pytest.raises(ValueError, match="does not contain Inertia page data"):
            get_inertia_page(response)


class TestInertiaTestMixin:
    def setup_method(self):
        class _TestCase(InertiaTestMixin):
            pass

        self.tc = _TestCase()

    def test_assert_inertia_component_pass(self):
        page_data = {"component": "Dashboard", "props": {}, "url": "/", "version": ""}
        response = InertiaResponse(page_data)
        self.tc.assert_inertia_component(response, "Dashboard")

    def test_assert_inertia_component_fail(self):
        page_data = {"component": "Dashboard", "props": {}, "url": "/", "version": ""}
        response = InertiaResponse(page_data)
        with pytest.raises(AssertionError, match="Expected Inertia component 'Other'"):
            self.tc.assert_inertia_component(response, "Other")

    def test_assert_inertia_props_pass(self):
        page_data = {"component": "P", "props": {"a": 1, "b": 2}, "url": "/", "version": ""}
        response = InertiaResponse(page_data)
        self.tc.assert_inertia_props(response, {"a": 1})

    def test_assert_inertia_props_missing_key(self):
        page_data = {"component": "P", "props": {"a": 1}, "url": "/", "version": ""}
        response = InertiaResponse(page_data)
        with pytest.raises(AssertionError, match="Expected prop 'z' not found"):
            self.tc.assert_inertia_props(response, {"z": 1})

    def test_assert_inertia_props_wrong_value(self):
        page_data = {"component": "P", "props": {"a": 1}, "url": "/", "version": ""}
        response = InertiaResponse(page_data)
        with pytest.raises(AssertionError, match="Prop 'a'"):
            self.tc.assert_inertia_props(response, {"a": 99})

    def test_mixin_inertia_headers(self):
        assert self.tc.inertia_headers() == {"HTTP_X_INERTIA": "true"}

    def test_mixin_get_inertia_page(self):
        page_data = {"component": "X", "props": {}, "url": "/", "version": ""}
        response = InertiaResponse(page_data)
        page = self.tc.get_inertia_page(response)
        assert page["component"] == "X"


# ---------------------------------------------------------------------------
# Template tags
# ---------------------------------------------------------------------------


class TestTemplateTags:
    """Test the inertia template tag functions directly."""

    def test_inertia_tag_renders_div(self):
        from django_matt.inertia.templatetags.inertia_tags import inertia as inertia_tag

        page_json = '{"component":"Page","props":{}}'
        context = {"page": page_json}

        rendered = inertia_tag(context)
        assert 'id="app"' in rendered
        assert "data-page=" in rendered

    def test_inertia_tag_with_ssr_body(self):
        from django_matt.inertia.templatetags.inertia_tags import inertia as inertia_tag

        context = {
            "page": '{"component":"Page"}',
            "ssr_body": "<h1>SSR Content</h1>",
        }

        rendered = inertia_tag(context)
        assert "<h1>SSR Content</h1>" in rendered

    def test_inertia_tag_escapes_html(self):
        from django_matt.inertia.templatetags.inertia_tags import inertia as inertia_tag

        page_json = '{"component":"Page","props":{"title":"A & B"}}'
        context = {"page": page_json}

        rendered = inertia_tag(context)
        assert "&amp;" in rendered
        assert "&quot;" in rendered

    def test_inertia_tag_empty_page(self):
        from django_matt.inertia.templatetags.inertia_tags import inertia as inertia_tag

        context = {}

        rendered = inertia_tag(context)
        assert 'id="app"' in rendered
        assert "data-page=" in rendered

    def test_inertia_head_tag_empty(self):
        from django_matt.inertia.templatetags.inertia_tags import inertia_head

        context = {}
        rendered = inertia_head(context)
        assert rendered == ""

    def test_inertia_head_tag_with_ssr_head(self):
        from django_matt.inertia.templatetags.inertia_tags import inertia_head

        context = {
            "ssr_head": ["<title>SSR Title</title>", '<meta name="desc" content="test">'],
        }

        rendered = inertia_head(context)
        assert "<title>SSR Title</title>" in rendered
        assert '<meta name="desc" content="test">' in rendered


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


class TestExports:
    def test_all_exports_accessible(self):
        import django_matt.inertia as mod

        expected = [
            "InertiaConfig",
            "get_inertia_config",
            "AsyncInertiaMiddleware",
            "InertiaMiddleware",
            "DeferredProp",
            "InertiaResponse",
            "LazyProp",
            "MergeProp",
            "defer",
            "inertia",
            "lazy",
            "merge",
            "AsyncSharedDataMiddleware",
            "SharedDataMiddleware",
            "share",
            "SSRResponse",
            "render_ssr",
            "InertiaTestMixin",
            "get_inertia_page",
            "inertia_headers",
            "InertiaView",
            "inertia_view",
        ]
        for name in expected:
            assert hasattr(mod, name), f"Missing export: {name}"
