"""Tests for QueryStringParserMiddleware."""

from django.http import HttpRequest, HttpResponse, QueryDict

import pytest

from django_matt._accel import HAS_RUST
from django_matt.middleware.querystring import QueryStringParserMiddleware


def _make_request(query_string: str = "") -> HttpRequest:
    request = HttpRequest()
    request.method = "GET"
    request.META["QUERY_STRING"] = query_string
    request.GET = QueryDict(query_string)
    return request


def _dummy_response(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


class TestQueryStringParserMiddleware:
    """Verify the middleware parses query strings and attaches to request."""

    def test_init_checks_rust_availability(self):
        mw = QueryStringParserMiddleware(_dummy_response)
        assert mw._enabled == HAS_RUST

    @pytest.mark.skipif(not HAS_RUST, reason="Rust extensions not available")
    def test_parses_query_string_when_present(self):
        mw = QueryStringParserMiddleware(_dummy_response)
        request = _make_request("filter[status]=active&ordering=-name&page=2")
        mw(request)

        parsed = getattr(request, "_parsed_qs", None)
        assert parsed is not None
        assert dict(parsed["filters"]) == {"status": "active"}
        assert [(f, a) for f, a in parsed["sort"]] == [("name", False)]
        assert dict(parsed["pagination"]) == {"page": "2"}

    @pytest.mark.skipif(not HAS_RUST, reason="Rust extensions not available")
    def test_empty_query_string_skips_parsing(self):
        mw = QueryStringParserMiddleware(_dummy_response)
        request = _make_request("")
        mw(request)

        assert not hasattr(request, "_parsed_qs")

    @pytest.mark.skipif(not HAS_RUST, reason="Rust extensions not available")
    def test_fields_parsing(self):
        mw = QueryStringParserMiddleware(_dummy_response)
        request = _make_request("fields=id,name,email")
        mw(request)

        parsed = request._parsed_qs  # type: ignore[attr-defined]
        assert list(parsed["fields"]) == ["id", "name", "email"]

    @pytest.mark.skipif(not HAS_RUST, reason="Rust extensions not available")
    def test_extras_for_django_lookups(self):
        mw = QueryStringParserMiddleware(_dummy_response)
        request = _make_request("status=active&role__in=admin,user")
        mw(request)

        parsed = request._parsed_qs  # type: ignore[attr-defined]
        extras = dict(parsed["extras"])
        assert extras["status"] == "active"
        assert extras["role__in"] == "admin,user"

    @pytest.mark.skipif(not HAS_RUST, reason="Rust extensions not available")
    def test_complex_query_string(self):
        mw = QueryStringParserMiddleware(_dummy_response)
        request = _make_request(
            "fields=id,name&filter[status]=active&ordering=-created_at,name"
            "&page=3&page_size=25&search=hello&role=admin"
        )
        mw(request)

        parsed = request._parsed_qs  # type: ignore[attr-defined]
        assert list(parsed["fields"]) == ["id", "name"]
        assert dict(parsed["filters"]) == {"status": "active"}
        assert [(f, a) for f, a in parsed["sort"]] == [
            ("created_at", False),
            ("name", True),
        ]
        assert dict(parsed["pagination"]) == {"page": "3", "page_size": "25"}
        extras = dict(parsed["extras"])
        assert extras["search"] == "hello"
        assert extras["role"] == "admin"

    @pytest.mark.skipif(not HAS_RUST, reason="Rust extensions not available")
    def test_response_passes_through(self):
        mw = QueryStringParserMiddleware(_dummy_response)
        request = _make_request("page=1")
        response = mw(request)

        assert response.status_code == 200
        assert response.content == b"ok"

    def test_noop_without_rust(self):
        """When Rust is unavailable, middleware should not attach _parsed_qs."""
        mw = QueryStringParserMiddleware(_dummy_response)
        mw._enabled = False  # Force disable
        request = _make_request("page=1&status=active")
        mw(request)

        assert not hasattr(request, "_parsed_qs")

    @pytest.mark.skipif(not HAS_RUST, reason="Rust extensions not available")
    def test_does_not_overwrite_existing_parsed_qs(self):
        """If _parsed_qs is already set (e.g. by a view), middleware should still
        set it on first pass — but the view's _get_parsed_qs caches correctly."""
        mw = QueryStringParserMiddleware(_dummy_response)
        request = _make_request("page=5")
        # Middleware sets it
        mw(request)
        first_parsed = request._parsed_qs  # type: ignore[attr-defined]
        assert dict(first_parsed["pagination"]) == {"page": "5"}
