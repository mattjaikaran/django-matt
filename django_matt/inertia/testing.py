"""
Inertia.js testing utilities.

Provides helpers for asserting Inertia responses in test suites.
"""

from __future__ import annotations

from typing import Any

from django.http import HttpResponse

import orjson


def inertia_headers() -> dict[str, str]:
    """Return headers that mark a request as an Inertia request.

    Usage::

        response = client.get("/dashboard/", **inertia_headers())
    """
    return {
        "HTTP_X_INERTIA": "true",
    }


def get_inertia_page(response: HttpResponse) -> dict[str, Any]:
    """Extract the Inertia page object from a response.

    Works with both JSON Inertia responses (``X-Inertia: true``) and
    full-page HTML responses (parses the ``data-page`` attribute).
    """
    if response.get("X-Inertia") == "true":
        return orjson.loads(response.content)

    # Fall back to parsing HTML for the data-page attribute
    content = response.content.decode()
    marker = 'data-page="'
    start = content.find(marker)
    if start == -1:
        # Try single-quote variant
        marker = "data-page='"
        start = content.find(marker)
    if start == -1:
        raise ValueError("Response does not contain Inertia page data")

    start += len(marker)
    end_char = marker[-1]
    end = content.find(end_char, start)
    if end == -1:
        raise ValueError("Malformed Inertia page data attribute")

    raw = content[start:end]
    # Unescape HTML entities
    raw = raw.replace("&quot;", '"').replace("&amp;", "&").replace("&#x27;", "'")
    return orjson.loads(raw)


class InertiaTestMixin:
    """Mixin for Django test cases that adds Inertia assertion helpers.

    Usage::

        from django.test import TestCase
        from django_matt.inertia.testing import InertiaTestMixin


        class DashboardTests(InertiaTestMixin, TestCase):
            def test_dashboard(self):
                response = self.client.get("/dashboard/", **inertia_headers())
                self.assert_inertia_component(response, "Dashboard/Index")
                self.assert_inertia_props(response, {"title": "Home"})
    """

    def assert_inertia_component(self, response: HttpResponse, component_name: str) -> None:
        """Assert the Inertia response renders the expected component."""
        page = get_inertia_page(response)
        actual = page.get("component")
        assert actual == component_name, (
            f"Expected Inertia component '{component_name}', got '{actual}'"
        )

    def assert_inertia_props(self, response: HttpResponse, expected_props: dict[str, Any]) -> None:
        """Assert the Inertia response props contain the expected key/value pairs."""
        page = get_inertia_page(response)
        actual_props = page.get("props", {})
        for key, value in expected_props.items():
            assert key in actual_props, (
                f"Expected prop '{key}' not found in Inertia props. "
                f"Available: {list(actual_props.keys())}"
            )
            assert actual_props[key] == value, (
                f"Prop '{key}': expected {value!r}, got {actual_props[key]!r}"
            )

    def get_inertia_page(self, response: HttpResponse) -> dict[str, Any]:
        """Extract the Inertia page object from a response."""
        return get_inertia_page(response)

    @staticmethod
    def inertia_headers() -> dict[str, str]:
        """Return headers for Inertia requests in tests."""
        return inertia_headers()


__all__ = [
    "InertiaTestMixin",
    "get_inertia_page",
    "inertia_headers",
]
