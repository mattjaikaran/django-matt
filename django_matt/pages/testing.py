"""
Testing utilities for pages.

Provides test client extensions and assertions for testing
page views and responses.
"""

import json
from typing import Any

from django.http import HttpResponse
from django.test import Client


class PageTestClient(Client):
    """
    Test client with page-specific methods.

    Usage:
        from django_matt.pages.testing import PageTestClient

        class TestUserPages(TestCase):
            def setUp(self):
                self.client = PageTestClient()

            def test_user_list(self):
                response = self.client.get_page("/users/")
                self.assertEqual(response.page_component, "UserList")
                self.assertIn("users", response.page_props)

            def test_spa_navigation(self):
                response = self.client.navigate("/users/")
                self.assertTrue(response.is_page_response)
                self.assertEqual(response.json()["component"], "UserList")
    """

    def get_page(self, path: str, **kwargs) -> "PageResponse":
        """
        Make a GET request expecting a full HTML page response.

        Returns a PageResponse with convenient accessors.
        """
        response = self.get(path, **kwargs)
        return PageResponse(response)

    def post_page(self, path: str, data: dict[str, Any] = None, **kwargs) -> "PageResponse":
        """
        Make a POST request expecting a page response.
        """
        response = self.post(path, data=data, **kwargs)
        return PageResponse(response)

    def navigate(self, path: str, **kwargs) -> "PageResponse":
        """
        Simulate SPA navigation (XHR with X-Page header).

        Returns the page JSON response.
        """
        kwargs.setdefault("HTTP_X_PAGE", "true")
        kwargs.setdefault("HTTP_ACCEPT", "application/json")
        response = self.get(path, **kwargs)
        return PageResponse(response)

    def submit_form(
        self,
        path: str,
        data: dict[str, Any],
        **kwargs,
    ) -> "PageResponse":
        """
        Submit a form via SPA navigation.
        """
        kwargs.setdefault("HTTP_X_PAGE", "true")
        kwargs.setdefault("HTTP_ACCEPT", "application/json")
        kwargs.setdefault("content_type", "application/json")
        response = self.post(path, data=json.dumps(data), **kwargs)
        return PageResponse(response)

    def api_get(self, path: str, **kwargs) -> HttpResponse:
        """
        Make an API request (Accept: application/json).
        """
        kwargs.setdefault("HTTP_ACCEPT", "application/json")
        return self.get(path, **kwargs)

    def api_post(self, path: str, data: dict[str, Any] = None, **kwargs) -> HttpResponse:
        """
        Make an API POST request.
        """
        kwargs.setdefault("HTTP_ACCEPT", "application/json")
        kwargs.setdefault("content_type", "application/json")
        return self.post(path, data=json.dumps(data) if data else None, **kwargs)


class PageResponse:
    """
    Wrapper around Django HttpResponse for page testing.

    Provides convenient accessors for page data.
    """

    def __init__(self, response: HttpResponse):
        self.response = response
        self._page_data: dict[str, Any] | None = None

    @property
    def status_code(self) -> int:
        return self.response.status_code

    @property
    def is_page_response(self) -> bool:
        """Check if this is a page JSON response."""
        return self.response.get("X-Page") == "true"

    @property
    def is_redirect(self) -> bool:
        """Check if this is a redirect."""
        return self.status_code in (301, 302, 303, 307, 308)

    @property
    def redirect_url(self) -> str | None:
        """Get redirect URL if this is a redirect."""
        if self.is_redirect:
            return self.response.get("Location") or self.response.get("X-Page-Location")
        return None

    @property
    def page_data(self) -> dict[str, Any]:
        """
        Get the page data from the response.

        For JSON responses, parses the JSON body.
        For HTML responses, extracts from the script tag.
        """
        if self._page_data is not None:
            return self._page_data

        content_type = self.response.get("Content-Type", "")

        # JSON response
        if "application/json" in content_type:
            try:
                self._page_data = json.loads(self.response.content)
                return self._page_data
            except json.JSONDecodeError:
                return {}

        # HTML response - extract from script tag
        try:
            content = self.response.content.decode("utf-8")
            # Find the page-data script tag
            import re

            match = re.search(
                r'<script[^>]*id="page-data"[^>]*>(.*?)</script>',
                content,
                re.DOTALL,
            )
            if match:
                self._page_data = json.loads(match.group(1))
                return self._page_data
        except Exception:
            pass

        return {}

    @property
    def page_component(self) -> str | None:
        """Get the component name from page data."""
        return self.page_data.get("component")

    @property
    def page_props(self) -> dict[str, Any]:
        """Get props from page data."""
        return self.page_data.get("props", {})

    @property
    def page_shared(self) -> dict[str, Any]:
        """Get shared data from page data."""
        return self.page_data.get("shared", {})

    @property
    def page_errors(self) -> dict[str, list[str]]:
        """Get validation errors from page data."""
        return self.page_data.get("errors", {})

    @property
    def page_flash(self) -> list[dict[str, str]]:
        """Get flash messages from page data."""
        return self.page_data.get("flash", [])

    @property
    def page_title(self) -> str | None:
        """Get page title from page data."""
        return self.page_data.get("title")

    def json(self) -> dict[str, Any]:
        """Get the response as JSON."""
        return json.loads(self.response.content)

    def __getattr__(self, name: str) -> Any:
        """Delegate to underlying response."""
        return getattr(self.response, name)


class PageTestMixin:
    """
    Mixin for TestCase classes with page testing utilities.

    Usage:
        class TestUserPages(PageTestMixin, TestCase):
            def test_user_list(self):
                response = self.get_page("/users/")
                self.assertPageComponent(response, "UserList")
                self.assertPageHasProp(response, "users")
    """

    def setUp(self):
        super().setUp()
        self.page_client = PageTestClient()

    def get_page(self, path: str, **kwargs) -> PageResponse:
        """Make a page GET request."""
        return self.page_client.get_page(path, **kwargs)

    def post_page(self, path: str, data: dict[str, Any] = None, **kwargs) -> PageResponse:
        """Make a page POST request."""
        return self.page_client.post_page(path, data, **kwargs)

    def navigate(self, path: str, **kwargs) -> PageResponse:
        """Simulate SPA navigation."""
        return self.page_client.navigate(path, **kwargs)

    def assertPageComponent(self, response: PageResponse, component: str) -> None:
        """Assert the page renders the expected component."""
        self.assertEqual(
            response.page_component,
            component,
            f"Expected component '{component}', got '{response.page_component}'",
        )

    def assertPageHasProp(self, response: PageResponse, prop: str) -> None:
        """Assert the page has a specific prop."""
        self.assertIn(
            prop,
            response.page_props,
            f"Expected prop '{prop}' not found in page props",
        )

    def assertPagePropEquals(
        self,
        response: PageResponse,
        prop: str,
        value: Any,
    ) -> None:
        """Assert a page prop equals a specific value."""
        self.assertEqual(
            response.page_props.get(prop),
            value,
            f"Prop '{prop}' does not equal expected value",
        )

    def assertPageHasError(self, response: PageResponse, field: str) -> None:
        """Assert the page has a validation error for a field."""
        self.assertIn(
            field,
            response.page_errors,
            f"Expected error for field '{field}' not found",
        )

    def assertPageNoErrors(self, response: PageResponse) -> None:
        """Assert the page has no validation errors."""
        self.assertEqual(
            response.page_errors,
            {},
            f"Expected no errors, got: {response.page_errors}",
        )

    def assertPageRedirect(self, response: PageResponse, url: str) -> None:
        """Assert the response is a redirect to a specific URL."""
        self.assertTrue(
            response.is_redirect,
            f"Expected redirect, got status {response.status_code}",
        )
        self.assertEqual(
            response.redirect_url,
            url,
            f"Expected redirect to '{url}', got '{response.redirect_url}'",
        )


__all__ = [
    "PageResponse",
    "PageTestClient",
    "PageTestMixin",
]
