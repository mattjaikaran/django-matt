"""Tests for django_matt.pages module."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

# =============================================================================
# PAGE DATA TESTS
# =============================================================================


class TestPageData:
    """Tests for PageData dataclass."""

    def test_page_data_creation(self):
        """Test creating PageData."""
        from django_matt.pages.response import PageData

        page = PageData(
            component="UserList",
            props={"users": []},
            url="/users",
        )
        assert page.component == "UserList"
        assert page.props == {"users": []}
        assert page.url == "/users"

    def test_page_data_defaults(self):
        """Test PageData default values."""
        from django_matt.pages.response import PageData

        page = PageData(
            component="Test",
            props={},
            url="/",
        )
        assert page.version == ""
        assert page.shared == {}
        assert page.errors == {}
        assert page.flash == []
        assert page.title is None
        assert page.preserve_scroll is False

    def test_page_data_with_metadata(self):
        """Test PageData with metadata."""
        from django_matt.pages.response import PageData

        page = PageData(
            component="UserDetail",
            props={"user": {"id": 1}},
            url="/users/1",
            title="User Profile",
            meta={"description": "User profile page"},
        )
        assert page.title == "User Profile"
        assert page.meta["description"] == "User profile page"

    def test_page_data_with_errors(self):
        """Test PageData with validation errors."""
        from django_matt.pages.response import PageData

        page = PageData(
            component="UserForm",
            props={},
            url="/users/create",
            errors={"email": ["Invalid email"]},
        )
        assert "email" in page.errors
        assert page.errors["email"] == ["Invalid email"]

    def test_page_data_with_flash(self):
        """Test PageData with flash messages."""
        from django_matt.pages.response import PageData

        page = PageData(
            component="UserList",
            props={},
            url="/users",
            flash=[{"message": "User created", "type": "success"}],
        )
        assert len(page.flash) == 1
        assert page.flash[0]["type"] == "success"

    def test_page_data_to_dict(self):
        """Test PageData serialization to dict."""
        from django_matt.pages.response import PageData

        page = PageData(
            component="UserList",
            props={"users": [{"id": 1}]},
            url="/users",
            version="abc123",
        )
        data = page.to_dict()

        assert data["component"] == "UserList"
        assert data["props"] == {"users": [{"id": 1}]}
        assert data["url"] == "/users"
        assert data["version"] == "abc123"

    def test_page_data_to_dict_excludes_empty(self):
        """Test that to_dict excludes empty optional fields."""
        from django_matt.pages.response import PageData

        page = PageData(
            component="Test",
            props={},
            url="/",
        )
        data = page.to_dict()

        # Empty fields should not be included
        assert "errors" not in data
        assert "flash" not in data
        assert "title" not in data
        assert "preserveScroll" not in data

    def test_page_data_to_dict_includes_navigation_options(self):
        """Test that navigation options are included when set."""
        from django_matt.pages.response import PageData

        page = PageData(
            component="Test",
            props={},
            url="/",
            preserve_scroll=True,
            clear_history=True,
            replace_state=True,
        )
        data = page.to_dict()

        assert data["preserveScroll"] is True
        assert data["clearHistory"] is True
        assert data["replaceState"] is True

    def test_page_data_to_json(self):
        """Test PageData serialization to JSON."""
        from django_matt.pages.response import PageData

        page = PageData(
            component="Test",
            props={"key": "value"},
            url="/test",
        )
        json_str = page.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert data["component"] == "Test"


# =============================================================================
# PAGE RESPONSE TESTS
# =============================================================================


class TestPageResponse:
    """Tests for PageResponse class."""

    def test_page_response_creation(self):
        """Test creating PageResponse."""
        from django_matt.pages.response import PageResponse

        response = PageResponse("UserList", {"users": []})
        assert response.component == "UserList"
        assert response.props == {"users": []}

    def test_page_response_defaults(self):
        """Test PageResponse default values."""
        from django_matt.pages.response import PageResponse

        response = PageResponse("Test")
        assert response.props == {}
        assert response.shared == {}
        assert response.errors == {}
        assert response.status == 200

    def test_page_response_with_errors(self):
        """Test PageResponse with validation errors."""
        from django_matt.pages.response import PageResponse

        response = PageResponse(
            "UserForm",
            props={"values": {}},
            errors={"email": ["Required"]},
            status=422,
        )
        assert response.errors == {"email": ["Required"]}
        assert response.status == 422

    def test_page_response_with_headers(self):
        """Test PageResponse with custom headers."""
        from django_matt.pages.response import PageResponse

        response = PageResponse(
            "Test",
            headers={"X-Custom": "value"},
        )
        assert response.headers == {"X-Custom": "value"}

    def test_page_response_has_get_page_data(self):
        """Test PageResponse has get_page_data method."""
        from django_matt.pages.response import PageResponse

        response = PageResponse("UserList", props={"users": []})
        assert hasattr(response, "get_page_data")
        assert callable(response.get_page_data)


# =============================================================================
# REDIRECT PAGE TESTS
# =============================================================================


class TestRedirectPage:
    """Tests for redirect_page function."""

    def test_redirect_page_exists(self):
        """Test redirect_page function exists."""
        from django_matt.pages.response import redirect_page

        assert callable(redirect_page)


# =============================================================================
# MIDDLEWARE TESTS
# =============================================================================


class TestPageMiddleware:
    """Tests for PageMiddleware."""

    def test_request_mode_enum(self):
        """Test RequestMode enum values."""
        from django_matt.pages.middleware import RequestMode

        # Check enum has expected attributes
        assert hasattr(RequestMode, "FULL_HTML")
        assert hasattr(RequestMode, "PAGE_XHR")
        assert hasattr(RequestMode, "API")

    def test_get_request_mode_exists(self):
        """Test get_request_mode function exists."""
        from django_matt.pages.middleware import get_request_mode

        assert callable(get_request_mode)

    def test_get_request_mode_page_xhr(self):
        """Test detecting page XHR request."""
        from django.test import RequestFactory

        from django_matt.pages.middleware import RequestMode, get_request_mode

        rf = RequestFactory()
        request = rf.get("/users", HTTP_X_PAGE="true")

        mode = get_request_mode(request)
        assert mode == RequestMode.PAGE_XHR

    def test_get_request_mode_api(self):
        """Test detecting API request."""
        from django.test import RequestFactory

        from django_matt.pages.middleware import RequestMode, get_request_mode

        rf = RequestFactory()
        request = rf.get("/users", HTTP_ACCEPT="application/json")

        mode = get_request_mode(request)
        assert mode == RequestMode.API


# =============================================================================
# DECORATOR TESTS
# =============================================================================


class TestPageDecorator:
    """Tests for @page decorator."""

    def test_page_decorator_import(self):
        """Test that page decorator can be imported."""
        from django_matt.pages.decorators import page

        assert callable(page)

    def test_page_decorator_basic(self):
        """Test basic page decorator usage."""
        from django_matt.pages.decorators import page
        from django_matt.pages.response import PageResponse

        @page("UserList")
        def user_list(request):
            return {"users": []}

        # Should return the decorated function
        assert callable(user_list)

    def test_page_decorator_with_title(self):
        """Test page decorator with title."""
        from django_matt.pages.decorators import page

        @page("UserList", title="All Users")
        def user_list(request):
            return {"users": []}

        assert callable(user_list)


# =============================================================================
# CONTEXT TESTS
# =============================================================================


class TestPageContext:
    """Tests for page context utilities."""

    def test_context_module_imports(self):
        """Test context module can be imported."""
        from django_matt.pages import context

        assert context is not None

    def test_set_shared_data_exists(self):
        """Test set_shared_data function exists."""
        from django_matt.pages.context import set_shared_data

        assert callable(set_shared_data)

    def test_get_shared_data_exists(self):
        """Test get_shared_data function exists."""
        from django_matt.pages.context import get_shared_data

        assert callable(get_shared_data)


# =============================================================================
# ASSETS TESTS
# =============================================================================


class TestAssets:
    """Tests for asset management."""

    def test_get_asset_version(self):
        """Test getting asset version."""
        from django_matt.pages.assets import get_asset_version

        version = get_asset_version()
        assert isinstance(version, str)

    def test_get_asset_version_callable(self):
        """Test get_asset_version is callable."""
        from django_matt.pages.assets import get_asset_version

        assert callable(get_asset_version)


# =============================================================================
# FORMS TESTS
# =============================================================================


class TestPageForms:
    """Tests for page form utilities."""

    def test_page_form_import(self):
        """Test PageForm can be imported."""
        from django_matt.pages.forms import PageForm

        assert PageForm is not None

    def test_page_form_schema(self):
        """Test PageForm with Pydantic schema."""
        from pydantic import BaseModel

        from django_matt.pages.forms import PageForm

        class UserSchema(BaseModel):
            email: str
            name: str

        form = PageForm(schema=UserSchema)
        assert form.schema == UserSchema


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestPageErrors:
    """Tests for page error handling."""

    def test_errors_module_imports(self):
        """Test errors module can be imported."""
        from django_matt.pages import errors

        assert errors is not None


# =============================================================================
# RENDERING TESTS
# =============================================================================


class TestPageRendering:
    """Tests for page rendering utilities."""

    def test_render_page_html_import(self):
        """Test render_page_html can be imported."""
        from django_matt.pages.rendering import render_page_html

        assert callable(render_page_html)

    def test_rendering_module_imports(self):
        """Test rendering module can be imported."""
        from django_matt.pages import rendering

        assert rendering is not None


# =============================================================================
# TESTING UTILITIES TESTS
# =============================================================================


class TestPageTestingUtils:
    """Tests for page testing utilities."""

    def test_page_test_client_import(self):
        """Test PageTestClient can be imported."""
        from django_matt.pages.testing import PageTestClient

        assert PageTestClient is not None

    def test_testing_module_imports(self):
        """Test testing module can be imported."""
        from django_matt.pages import testing

        assert testing is not None


# =============================================================================
# ADAPTER TESTS
# =============================================================================


class TestPageAdapters:
    """Tests for frontend adapter configurations."""

    def test_adapters_module_imports(self):
        """Test adapters module can be imported."""
        from django_matt.pages import adapters

        assert adapters is not None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestPagesIntegration:
    """Integration tests for pages system."""

    def test_page_response_render_flow(self):
        """Test full page response render flow."""
        from django.test import RequestFactory

        from django_matt.pages.response import PageResponse

        rf = RequestFactory()
        request = rf.get("/users")

        response = PageResponse(
            "UserList",
            props={"users": [{"id": 1, "name": "Test"}]},
            title="Users",
        )

        # Render the response
        with patch("django_matt.pages.middleware.get_request_mode") as mock_mode:
            from django_matt.pages.middleware import RequestMode
            mock_mode.return_value = RequestMode.PAGE_XHR

            http_response = response.render(request)

        assert http_response.status_code == 200
        assert http_response["X-Page"] == "true"

    def test_page_data_json_roundtrip(self):
        """Test PageData JSON serialization roundtrip."""
        import json

        from django_matt.pages.response import PageData

        original = PageData(
            component="UserDetail",
            props={"user": {"id": 1, "name": "Test"}},
            url="/users/1",
            version="v1",
            title="User Detail",
        )

        # Serialize
        json_str = original.to_json()

        # Deserialize
        data = json.loads(json_str)

        assert data["component"] == "UserDetail"
        assert data["props"]["user"]["id"] == 1
        assert data["title"] == "User Detail"

    def test_error_response(self):
        """Test error page response."""
        from django_matt.pages.response import PageResponse

        response = PageResponse(
            "Error",
            props={"message": "Not found"},
            status=404,
        )

        assert response.status == 404
        assert response.props["message"] == "Not found"
