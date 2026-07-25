"""
Tests for the HTMX integration module.

Tests cover:
- HtmxDetails request detection
- HtmxResponse and response headers
- HTMX decorators (htmx_view, htmx_only, etc.)
- HTMX middleware
- Template helpers
"""

import json
from unittest.mock import Mock, patch

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

import pytest

from django_matt.htmx.decorators import (
    htmx_only,
    htmx_partial,
    htmx_trigger,
    htmx_view,
    require_htmx_target,
    vary_on_htmx,
)
from django_matt.htmx.middleware import (
    HtmxMiddleware,
    HtmxTemplateContextMiddleware,
    htmx_context_processor,
)
from django_matt.htmx.request import (
    HtmxDetails,
    get_htmx_current_url,
    get_htmx_prompt,
    get_htmx_target,
    get_htmx_trigger,
    get_htmx_trigger_name,
    is_htmx_boosted,
    is_htmx_history_restore,
    is_htmx_request,
)
from django_matt.htmx.response import (
    HtmxRedirectResponse,
    HtmxRefreshResponse,
    HtmxResponse,
    StopPolling,
    trigger_client_event,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def rf():
    """Request factory fixture."""
    return RequestFactory()


def make_htmx_request(rf, path="/", **headers):
    """Create a request with HTMX headers."""
    http_headers = {"HTTP_HX_REQUEST": "true"}
    for key, value in headers.items():
        http_headers[f"HTTP_HX_{key.upper().replace('-', '_')}"] = value
    return rf.get(path, **http_headers)


def make_normal_request(rf, path="/"):
    """Create a normal non-HTMX request."""
    return rf.get(path)


# ==============================================================================
# HtmxDetails Tests
# ==============================================================================


class TestHtmxDetails:
    """Tests for HtmxDetails class."""

    def test_from_request_non_htmx(self, rf):
        """Test that from_request returns None for non-HTMX requests."""
        request = make_normal_request(rf)
        details = HtmxDetails.from_request(request)
        assert details is None

    def test_from_request_basic_htmx(self, rf):
        """Test basic HTMX request detection."""
        request = make_htmx_request(rf)
        details = HtmxDetails.from_request(request)

        assert details is not None
        assert details.request is True
        assert details.boosted is False
        assert details.history_restore_request is False

    def test_from_request_with_all_headers(self, rf):
        """Test HTMX request with all headers."""
        request = make_htmx_request(
            rf,
            boosted="true",
            current_url="/current/page/",
            history_restore_request="true",
            prompt="user input",
            target="main-content",
            trigger="submit-btn",
            trigger_name="form_submit",
        )
        details = HtmxDetails.from_request(request)

        assert details is not None
        assert details.request is True
        assert details.boosted is True
        assert details.current_url == "/current/page/"
        assert details.history_restore_request is True
        assert details.prompt == "user input"
        assert details.target == "main-content"
        assert details.trigger == "submit-btn"
        assert details.trigger_name == "form_submit"

    def test_bool_true_for_htmx_request(self, rf):
        """Test that HtmxDetails is truthy for HTMX requests."""
        request = make_htmx_request(rf)
        details = HtmxDetails.from_request(request)
        assert bool(details) is True

    def test_bool_false_for_non_htmx(self, rf):
        """Test that None is returned for non-HTMX."""
        request = make_normal_request(rf)
        details = HtmxDetails.from_request(request)
        assert details is None

    def test_default_values(self):
        """Test HtmxDetails default values."""
        details = HtmxDetails()
        assert details.boosted is False
        assert details.current_url is None
        assert details.history_restore_request is False
        assert details.prompt is None
        assert details.request is False
        assert details.target is None
        assert details.trigger is None
        assert details.trigger_name is None


# ==============================================================================
# Request Helper Function Tests
# ==============================================================================


class TestRequestHelpers:
    """Tests for request helper functions."""

    def test_is_htmx_request_true(self, rf):
        """Test is_htmx_request returns True for HTMX requests."""
        request = make_htmx_request(rf)
        assert is_htmx_request(request) is True

    def test_is_htmx_request_false(self, rf):
        """Test is_htmx_request returns False for non-HTMX requests."""
        request = make_normal_request(rf)
        assert is_htmx_request(request) is False

    def test_is_htmx_boosted(self, rf):
        """Test is_htmx_boosted function."""
        request = make_htmx_request(rf, boosted="true")
        assert is_htmx_boosted(request) is True

        request = make_htmx_request(rf)
        assert is_htmx_boosted(request) is False

    def test_is_htmx_history_restore(self, rf):
        """Test is_htmx_history_restore function."""
        request = make_htmx_request(rf, history_restore_request="true")
        assert is_htmx_history_restore(request) is True

        request = make_htmx_request(rf)
        assert is_htmx_history_restore(request) is False

    def test_get_htmx_target(self, rf):
        """Test get_htmx_target function."""
        request = make_htmx_request(rf, target="content-area")
        assert get_htmx_target(request) == "content-area"

        request = make_htmx_request(rf)
        assert get_htmx_target(request) is None

    def test_get_htmx_trigger(self, rf):
        """Test get_htmx_trigger function."""
        request = make_htmx_request(rf, trigger="btn-123")
        assert get_htmx_trigger(request) == "btn-123"

        request = make_htmx_request(rf)
        assert get_htmx_trigger(request) is None

    def test_get_htmx_trigger_name(self, rf):
        """Test get_htmx_trigger_name function."""
        request = make_htmx_request(rf, trigger_name="my_button")
        assert get_htmx_trigger_name(request) == "my_button"

    def test_get_htmx_prompt(self, rf):
        """Test get_htmx_prompt function."""
        request = make_htmx_request(rf, prompt="user response")
        assert get_htmx_prompt(request) == "user response"

    def test_get_htmx_current_url(self, rf):
        """Test get_htmx_current_url function."""
        request = make_htmx_request(rf, current_url="/dashboard/")
        assert get_htmx_current_url(request) == "/dashboard/"


# ==============================================================================
# HtmxResponse Tests
# ==============================================================================


class TestHtmxResponse:
    """Tests for HtmxResponse class."""

    def test_basic_response(self):
        """Test basic HtmxResponse creation."""
        response = HtmxResponse("<div>Content</div>")
        assert response.content == b"<div>Content</div>"
        assert response.status_code == 200

    def test_trigger_single_event(self):
        """Test triggering a single event."""
        response = HtmxResponse("<div>Content</div>")
        response.trigger("itemAdded")

        assert response["HX-Trigger"] == "itemAdded"

    def test_trigger_multiple_events(self):
        """Test triggering multiple events."""
        response = HtmxResponse("<div>Content</div>")
        response.trigger("event1")
        response.trigger("event2")

        assert "event1" in response["HX-Trigger"]
        assert "event2" in response["HX-Trigger"]

    def test_trigger_with_params(self):
        """Test triggering event with parameters."""
        response = HtmxResponse("<div>Content</div>")
        response.trigger("itemAdded", {"id": 123, "name": "Test"})

        trigger_value = response["HX-Trigger"]
        parsed = json.loads(trigger_value)
        assert parsed["itemAdded"] == {"id": 123, "name": "Test"}

    def test_trigger_after_settle(self):
        """Test trigger_after_settle method."""
        response = HtmxResponse("<div>Content</div>")
        response.trigger_after_settle("animationDone")

        assert response["HX-Trigger-After-Settle"] == "animationDone"

    def test_trigger_after_swap(self):
        """Test trigger_after_swap method."""
        response = HtmxResponse("<div>Content</div>")
        response.trigger_after_swap("swapComplete")

        assert response["HX-Trigger-After-Swap"] == "swapComplete"

    def test_push_url(self):
        """Test push_url method."""
        response = HtmxResponse("<div>Content</div>")
        response.push_url("/new/url/")

        assert response["HX-Push-Url"] == "/new/url/"

    def test_replace_url(self):
        """Test replace_url method."""
        response = HtmxResponse("<div>Content</div>")
        response.replace_url("/replaced/url/")

        assert response["HX-Replace-Url"] == "/replaced/url/"

    def test_redirect(self):
        """Test redirect method."""
        response = HtmxResponse("<div>Content</div>")
        response.redirect("/redirected/")

        assert response["HX-Redirect"] == "/redirected/"

    def test_refresh(self):
        """Test refresh method."""
        response = HtmxResponse("<div>Content</div>")
        response.refresh()

        assert response["HX-Refresh"] == "true"

    def test_retarget(self):
        """Test retarget method."""
        response = HtmxResponse("<div>Content</div>")
        response.retarget("#new-target")

        assert response["HX-Retarget"] == "#new-target"

    def test_reselect(self):
        """Test reselect method."""
        response = HtmxResponse("<div>Content</div>")
        response.reselect(".content")

        assert response["HX-Reselect"] == ".content"

    def test_reswap_simple(self):
        """Test reswap method with simple method."""
        response = HtmxResponse("<div>Content</div>")
        response.reswap("outerHTML")

        assert response["HX-Reswap"] == "outerHTML"

    def test_reswap_with_modifiers(self):
        """Test reswap method with modifiers."""
        response = HtmxResponse("<div>Content</div>")
        response.reswap("innerHTML", transition=True, settle=100, swap=50)

        reswap_value = response["HX-Reswap"]
        assert "innerHTML" in reswap_value
        assert "transition:true" in reswap_value
        assert "settle:100ms" in reswap_value
        assert "swap:50ms" in reswap_value

    def test_location_basic(self):
        """Test location method with basic URL."""
        response = HtmxResponse("<div>Content</div>")
        response.location("/new/location/")

        location_value = json.loads(response["HX-Location"])
        assert location_value["path"] == "/new/location/"

    def test_location_with_options(self):
        """Test location method with all options."""
        response = HtmxResponse("<div>Content</div>")
        response.location(
            "/api/data/",
            target="#main",
            swap="outerHTML",
            values={"key": "value"},
        )

        location_value = json.loads(response["HX-Location"])
        assert location_value["path"] == "/api/data/"
        assert location_value["target"] == "#main"
        assert location_value["swap"] == "outerHTML"
        assert location_value["values"] == {"key": "value"}

    def test_chaining_methods(self):
        """Test that methods can be chained."""
        response = (
            HtmxResponse("<div>Content</div>")
            .trigger("event1")
            .push_url("/new/")
            .retarget("#content")
        )

        assert response["HX-Trigger"] == "event1"
        assert response["HX-Push-Url"] == "/new/"
        assert response["HX-Retarget"] == "#content"


# ==============================================================================
# Special Response Classes Tests
# ==============================================================================


class TestSpecialResponses:
    """Tests for special response classes."""

    def test_stop_polling(self):
        """Test StopPolling response has correct status code."""
        response = StopPolling("<div>Done</div>")
        assert response.status_code == 286

    def test_htmx_redirect_response(self):
        """Test HtmxRedirectResponse sets header."""
        response = HtmxRedirectResponse("/dashboard/")
        assert response["HX-Redirect"] == "/dashboard/"

    def test_htmx_refresh_response(self):
        """Test HtmxRefreshResponse sets header."""
        response = HtmxRefreshResponse()
        assert response["HX-Refresh"] == "true"


# ==============================================================================
# Helper Function Tests
# ==============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_trigger_client_event_basic(self):
        """Test trigger_client_event on plain HttpResponse."""
        response = HttpResponse("OK")
        trigger_client_event(response, "myEvent")

        assert response["HX-Trigger"] == "myEvent"

    def test_trigger_client_event_with_params(self):
        """Test trigger_client_event with parameters."""
        response = HttpResponse("OK")
        trigger_client_event(response, "itemSaved", {"id": 123})

        trigger_value = json.loads(response["HX-Trigger"])
        assert trigger_value["itemSaved"] == {"id": 123}

    def test_trigger_client_event_after_settle(self):
        """Test trigger_client_event with after='settle'."""
        response = HttpResponse("OK")
        trigger_client_event(response, "done", after="settle")

        assert response["HX-Trigger-After-Settle"] == "done"

    def test_trigger_client_event_multiple(self):
        """Test adding multiple triggers."""
        response = HttpResponse("OK")
        trigger_client_event(response, "event1")
        trigger_client_event(response, "event2")

        trigger_value = response["HX-Trigger"]
        assert "event1" in trigger_value
        assert "event2" in trigger_value


# ==============================================================================
# Decorator Tests
# ==============================================================================


class TestHtmxOnlyDecorator:
    """Tests for htmx_only decorator."""

    def test_allows_htmx_request(self, rf):
        """Test that htmx_only allows HTMX requests."""

        @htmx_only
        def view(request):
            return HttpResponse("OK")

        request = make_htmx_request(rf)
        response = view(request)
        assert response.status_code == 200

    def test_blocks_non_htmx_request(self, rf):
        """Test that htmx_only blocks non-HTMX requests."""

        @htmx_only
        def view(request):
            return HttpResponse("OK")

        request = make_normal_request(rf)
        response = view(request)
        assert response.status_code == 405

    def test_allow_boosted_true(self, rf):
        """Test htmx_only with allow_boosted=True (default)."""

        @htmx_only
        def view(request):
            return HttpResponse("OK")

        request = make_htmx_request(rf, boosted="true")
        response = view(request)
        assert response.status_code == 200

    def test_allow_boosted_false(self, rf):
        """Test htmx_only with allow_boosted=False."""

        @htmx_only(allow_boosted=False)
        def view(request):
            return HttpResponse("OK")

        request = make_htmx_request(rf, boosted="true")
        response = view(request)
        assert response.status_code == 405


class TestRequireHtmxTargetDecorator:
    """Tests for require_htmx_target decorator."""

    def test_allows_matching_target(self, rf):
        """Test allows request with matching target."""

        @require_htmx_target("user-list")
        def view(request):
            return HttpResponse("OK")

        request = make_htmx_request(rf, target="user-list")
        response = view(request)
        assert response.status_code == 200

    def test_blocks_non_matching_target(self, rf):
        """Test blocks request with non-matching target."""

        @require_htmx_target("user-list")
        def view(request):
            return HttpResponse("OK")

        request = make_htmx_request(rf, target="other-element")
        response = view(request)
        assert response.status_code == 400

    def test_blocks_non_htmx_request(self, rf):
        """Test blocks non-HTMX request."""

        @require_htmx_target("user-list")
        def view(request):
            return HttpResponse("OK")

        request = make_normal_request(rf)
        response = view(request)
        assert response.status_code == 405


class TestVaryOnHtmxDecorator:
    """Tests for vary_on_htmx decorator."""

    def test_adds_vary_header(self, rf):
        """Test that vary_on_htmx adds Vary header."""

        @vary_on_htmx
        def view(request):
            return HttpResponse("OK")

        request = make_htmx_request(rf)
        response = view(request)
        assert "HX-Request" in response.get("Vary", "")

    def test_appends_to_existing_vary(self, rf):
        """Test that vary_on_htmx appends to existing Vary header."""

        @vary_on_htmx
        def view(request):
            response = HttpResponse("OK")
            response["Vary"] = "Accept-Language"
            return response

        request = make_htmx_request(rf)
        response = view(request)
        assert "Accept-Language" in response["Vary"]
        assert "HX-Request" in response["Vary"]

    def test_doesnt_duplicate_vary(self, rf):
        """Test that vary_on_htmx doesn't duplicate HX-Request."""

        @vary_on_htmx
        def view(request):
            response = HttpResponse("OK")
            response["Vary"] = "HX-Request"
            return response

        request = make_htmx_request(rf)
        response = view(request)
        # Should only have one occurrence
        assert response["Vary"].count("HX-Request") == 1


class TestHtmxTriggerDecorator:
    """Tests for htmx_trigger decorator."""

    def test_adds_trigger_to_response(self, rf):
        """Test htmx_trigger adds trigger to response."""

        @htmx_trigger("itemsUpdated")
        def view(request):
            return HttpResponse("OK")

        request = make_htmx_request(rf)
        response = view(request)
        assert "itemsUpdated" in response.get("HX-Trigger", "")

    def test_adds_multiple_triggers(self, rf):
        """Test htmx_trigger with multiple events."""

        @htmx_trigger("event1", "event2")
        def view(request):
            return HttpResponse("OK")

        request = make_htmx_request(rf)
        response = view(request)
        trigger = response.get("HX-Trigger", "")
        assert "event1" in trigger
        assert "event2" in trigger


# ==============================================================================
# Middleware Tests
# ==============================================================================


class TestHtmxMiddleware:
    """Tests for HtmxMiddleware."""

    def test_adds_htmx_to_request(self, rf):
        """Test that middleware adds htmx to request."""
        request = make_htmx_request(rf)

        def get_response(req):
            # Check that htmx is set
            assert hasattr(req, "htmx")
            assert req.htmx is not None
            assert req.htmx.request is True
            return HttpResponse("OK")

        middleware = HtmxMiddleware(get_response)
        middleware(request)

    def test_htmx_is_none_for_normal_request(self, rf):
        """Test that htmx is None for non-HTMX request."""
        request = make_normal_request(rf)

        def get_response(req):
            assert hasattr(req, "htmx")
            assert req.htmx is None
            return HttpResponse("OK")

        middleware = HtmxMiddleware(get_response)
        middleware(request)

    def test_adds_vary_header_for_htmx(self, rf):
        """Test that Vary header is added for HTMX requests."""
        request = make_htmx_request(rf)

        def get_response(req):
            return HttpResponse("OK")

        middleware = HtmxMiddleware(get_response)
        response = middleware(request)
        assert "HX-Request" in response.get("Vary", "")

    def test_no_vary_for_non_htmx(self, rf):
        """Test that Vary header is not added for non-HTMX requests."""
        request = make_normal_request(rf)

        def get_response(req):
            return HttpResponse("OK")

        middleware = HtmxMiddleware(get_response)
        response = middleware(request)
        assert response.get("Vary") is None or "HX-Request" not in response.get("Vary", "")


class TestHtmxContextProcessor:
    """Tests for htmx_context_processor."""

    def test_returns_htmx_details(self, rf):
        """Test context processor returns htmx details."""
        request = make_htmx_request(rf)
        request.htmx = HtmxDetails.from_request(request)

        context = htmx_context_processor(request)

        assert "htmx" in context
        assert context["htmx"] is not None
        assert context["htmx"].request is True

    def test_returns_none_for_non_htmx(self, rf):
        """Test context processor returns None for non-HTMX."""
        request = make_normal_request(rf)

        context = htmx_context_processor(request)

        assert "htmx" in context
        assert context["htmx"] is None

    def test_creates_htmx_if_not_on_request(self, rf):
        """Test context processor creates htmx if not already set."""
        request = make_htmx_request(rf)
        # Don't set request.htmx

        context = htmx_context_processor(request)

        assert "htmx" in context
        assert context["htmx"] is not None


class TestHtmxTemplateContextMiddleware:
    """Tests for HtmxTemplateContextMiddleware."""

    def test_ensures_htmx_on_request(self, rf):
        """Test middleware ensures htmx is on request."""
        request = make_htmx_request(rf)

        captured_htmx = None

        def get_response(req):
            nonlocal captured_htmx
            captured_htmx = req.htmx
            return HttpResponse("OK")

        middleware = HtmxTemplateContextMiddleware(get_response)
        middleware(request)

        assert captured_htmx is not None
        assert captured_htmx.request is True


# ==============================================================================
# Requirement-aligned tests (07-04)
# ==============================================================================


class TestHtmxResponseHeaders:
    """HTMX-01: Verify HTMX response helpers set correct headers."""

    def test_hx_trigger_header_set_correctly(self):
        """Test HtmxResponse.trigger sets HX-Trigger header."""
        response = HtmxResponse("<div>Content</div>")
        response.trigger("itemAdded")

        assert "HX-Trigger" in response
        assert "itemAdded" in response["HX-Trigger"]

    def test_hx_redirect_header_set_correctly(self):
        """Test HtmxResponse.redirect sets HX-Redirect header."""
        response = HtmxResponse("<div>Content</div>")
        response.redirect("/dashboard/")

        assert response["HX-Redirect"] == "/dashboard/"

    def test_hx_swap_header_set_correctly(self):
        """Test HtmxResponse.reswap sets HX-Reswap header."""
        response = HtmxResponse("<div>Content</div>")
        response.reswap("outerHTML")

        assert response["HX-Reswap"] == "outerHTML"

    def test_hx_push_url_header_set_correctly(self):
        """Test HtmxResponse.push_url sets HX-Push-Url header."""
        response = HtmxResponse("<div>Content</div>")
        response.push_url("/items/42/")

        assert response["HX-Push-Url"] == "/items/42/"

    def test_htmx_redirect_response_class(self):
        """Test HtmxRedirectResponse sets HX-Redirect on construction."""
        response = HtmxRedirectResponse("/login/")
        assert response["HX-Redirect"] == "/login/"

    def test_trigger_client_event_on_plain_response(self):
        """Test trigger_client_event works on plain HttpResponse."""
        response = HttpResponse("OK")
        trigger_client_event(response, "formSaved", {"id": 1})

        header = response["HX-Trigger"]
        parsed = json.loads(header)
        assert parsed["formSaved"] == {"id": 1}


class TestHtmxComponentPatterns:
    """HTMX-02: Verify Livewire-style component patterns work."""

    def test_oob_builder_produces_response(self):
        """Test OobBuilder produces HtmxResponse with OOB swaps."""
        from django_matt.htmx.components import OobBuilder

        response = (
            OobBuilder()
            .main("<div>Main content</div>")
            .swap("sidebar", "<ul>Updated</ul>")
            .delete("old-element")
            .build()
        )

        assert isinstance(response, HtmxResponse)
        content = response.content.decode()
        assert "Main content" in content
        assert 'hx-swap-oob="innerHTML"' in content
        assert 'hx-swap-oob="delete"' in content

    def test_infinite_scroll_config_generates_trigger(self):
        """Test InfiniteScrollConfig generates trigger HTML."""
        from django_matt.htmx.components import InfiniteScrollConfig

        config = InfiniteScrollConfig()
        html = config.get_trigger_html("/items/", page=1, has_more=True)

        assert "hx-get" in html
        assert "page=2" in html
        assert "intersect" in html

    def test_infinite_scroll_no_trigger_when_no_more(self):
        """Test InfiniteScrollConfig returns empty when no more pages."""
        from django_matt.htmx.components import InfiniteScrollConfig

        config = InfiniteScrollConfig()
        html = config.get_trigger_html("/items/", page=5, has_more=False)

        assert html == ""

    def test_modal_open_and_close(self):
        """Test modal open/close return HtmxResponse with correct headers."""
        from django_matt.htmx.components import close_modal, open_modal

        response = open_modal("<p>Modal content</p>", title="My Modal")
        assert isinstance(response, HtmxResponse)
        assert response["HX-Retarget"] == "#modal"
        assert response["HX-Reswap"] == "innerHTML"
        content = response.content.decode()
        assert "My Modal" in content

        close_response = close_modal()
        assert isinstance(close_response, HtmxResponse)

    def test_toast_show_returns_response(self):
        """Test show_toast returns HtmxResponse with toast HTML."""
        from django_matt.htmx.components import show_toast

        response = show_toast("Item saved!", type="success")
        assert isinstance(response, HtmxResponse)
        content = response.content.decode()
        assert "Item saved!" in content
        assert "toast-success" in content
