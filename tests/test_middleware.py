"""
Tests for django_matt/middleware/ — CORS, RequestID, SecurityHeaders, Timing,
RequestLogging, chaining (DjangoMattMiddleware, APIExceptionMiddleware,
JSONResponseMiddleware).
"""

from __future__ import annotations

import re
import uuid
from unittest.mock import patch

from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, override_settings

import pytest

from django_matt.middleware import DEVELOPMENT_STACK, PRODUCTION_STACK
from django_matt.middleware.chaining import (
    APIExceptionMiddleware,
    DjangoMattMiddleware,
    JSONResponseMiddleware,
)
from django_matt.middleware.cors import CORSMiddleware
from django_matt.middleware.logging import RequestLoggingMiddleware
from django_matt.middleware.request_id import (
    RequestIDMiddleware,
    get_request_id,
    request_id_var,
)
from django_matt.middleware.security import SecurityHeadersMiddleware
from django_matt.middleware.timing import TimingMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_response(request):
    """Simple 200 OK response callable for middleware get_response."""
    return HttpResponse("OK", status=200)


def _json_response(request):
    return JsonResponse({"status": "ok"})


def _slow_response(request):
    """Response that takes a tiny bit of time."""
    import time

    time.sleep(0.005)
    return HttpResponse("slow", status=200)


def _error_response(request):
    raise ValueError("something broke")


def _dict_response(request):
    """Return a plain dict (for JSONResponseMiddleware)."""
    return {"message": "hello"}


@pytest.fixture
def rf():
    return RequestFactory()


# ---------------------------------------------------------------------------
# CORSMiddleware
# ---------------------------------------------------------------------------


class TestCORSMiddleware:
    """Test CORS header injection and preflight handling."""

    @override_settings(DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://app.example.com"]}})
    def test_allowed_origin_gets_header(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://app.example.com")
        response = mw(request)
        assert response["Access-Control-Allow-Origin"] == "https://app.example.com"

    @override_settings(DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://app.example.com"]}})
    def test_disallowed_origin_no_header(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://evil.com")
        response = mw(request)
        assert "Access-Control-Allow-Origin" not in response

    @override_settings(DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["*"]}})
    def test_wildcard_origin(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://anything.com")
        response = mw(request)
        assert response["Access-Control-Allow-Origin"] == "*"

    @override_settings(DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": True}})
    def test_allow_all_with_true(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://anywhere.com")
        response = mw(request)
        assert response["Access-Control-Allow-Origin"] == "*"

    @override_settings(DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://app.example.com"]}})
    def test_no_origin_header_no_cors(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/")
        response = mw(request)
        assert "Access-Control-Allow-Origin" not in response

    @override_settings(DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://app.example.com"]}})
    def test_vary_header_set_for_specific_origin(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://app.example.com")
        response = mw(request)
        assert response.get("Vary") == "Origin"

    @override_settings(DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["*"]}})
    def test_no_vary_header_for_wildcard(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://x.com")
        response = mw(request)
        assert response.get("Vary") is None

    # -- Preflight (OPTIONS) -----------------------------------------------

    @override_settings(DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://app.example.com"]}})
    def test_preflight_returns_204(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.options("/api/", HTTP_ORIGIN="https://app.example.com")
        response = mw(request)
        assert response.status_code == 204

    @override_settings(
        DJANGO_MATT={
            "CORS": {
                "ALLOWED_ORIGINS": ["https://app.example.com"],
                "ALLOW_METHODS": ["GET", "POST"],
            }
        }
    )
    def test_preflight_allow_methods(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.options("/api/", HTTP_ORIGIN="https://app.example.com")
        response = mw(request)
        assert "GET" in response["Access-Control-Allow-Methods"]
        assert "POST" in response["Access-Control-Allow-Methods"]

    @override_settings(
        DJANGO_MATT={
            "CORS": {
                "ALLOWED_ORIGINS": ["https://app.example.com"],
                "ALLOW_HEADERS": ["Authorization", "Content-Type"],
            }
        }
    )
    def test_preflight_allow_headers(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.options("/api/", HTTP_ORIGIN="https://app.example.com")
        response = mw(request)
        assert "Authorization" in response["Access-Control-Allow-Headers"]
        assert "Content-Type" in response["Access-Control-Allow-Headers"]

    @override_settings(
        DJANGO_MATT={
            "CORS": {
                "ALLOWED_ORIGINS": ["https://app.example.com"],
                "MAX_AGE": 3600,
            }
        }
    )
    def test_preflight_max_age(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.options("/api/", HTTP_ORIGIN="https://app.example.com")
        response = mw(request)
        assert response["Access-Control-Max-Age"] == "3600"

    @override_settings(DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://app.example.com"]}})
    def test_non_preflight_no_allow_methods(self, rf):
        """Regular GET should NOT have Allow-Methods header."""
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://app.example.com")
        response = mw(request)
        assert "Access-Control-Allow-Methods" not in response

    # -- Credentials --------------------------------------------------------

    @override_settings(
        DJANGO_MATT={
            "CORS": {
                "ALLOWED_ORIGINS": ["https://app.example.com"],
                "ALLOW_CREDENTIALS": True,
            }
        }
    )
    def test_credentials_header(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://app.example.com")
        response = mw(request)
        assert response["Access-Control-Allow-Credentials"] == "true"

    @override_settings(
        DJANGO_MATT={
            "CORS": {
                "ALLOWED_ORIGINS": ["https://app.example.com"],
                "ALLOW_CREDENTIALS": False,
            }
        }
    )
    def test_no_credentials_header_when_disabled(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://app.example.com")
        response = mw(request)
        assert "Access-Control-Allow-Credentials" not in response

    # -- Expose headers -----------------------------------------------------

    @override_settings(
        DJANGO_MATT={
            "CORS": {
                "ALLOWED_ORIGINS": ["https://app.example.com"],
                "EXPOSE_HEADERS": ["X-Custom", "X-Request-ID"],
            }
        }
    )
    def test_expose_headers(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://app.example.com")
        response = mw(request)
        exposed = response["Access-Control-Expose-Headers"]
        assert "X-Custom" in exposed
        assert "X-Request-ID" in exposed

    # -- Disabled -----------------------------------------------------------

    @override_settings(DJANGO_MATT={"CORS": {"ENABLED": False}})
    def test_disabled_cors_passthrough(self, rf):
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://x.com")
        response = mw(request)
        assert "Access-Control-Allow-Origin" not in response
        assert response.status_code == 200

    # -- Default config -----------------------------------------------------

    @override_settings(DJANGO_MATT={})
    def test_default_config_no_origins(self, rf):
        """No CORS section means empty allowed origins — no CORS headers."""
        mw = CORSMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_ORIGIN="https://x.com")
        response = mw(request)
        assert "Access-Control-Allow-Origin" not in response


# ---------------------------------------------------------------------------
# RequestIDMiddleware
# ---------------------------------------------------------------------------


class TestRequestIDMiddleware:
    """Test unique request ID generation and propagation."""

    @override_settings(DJANGO_MATT={})
    def test_generates_uuid(self, rf):
        mw = RequestIDMiddleware(_ok_response)
        request = rf.get("/api/")
        response = mw(request)
        rid = response["X-Request-ID"]
        # uuid4 hex is 32 chars
        assert len(rid) == 32
        # Verify it parses as valid hex
        int(rid, 16)

    @override_settings(DJANGO_MATT={})
    def test_unique_per_request(self, rf):
        mw = RequestIDMiddleware(_ok_response)
        r1 = mw(rf.get("/a/"))
        r2 = mw(rf.get("/b/"))
        assert r1["X-Request-ID"] != r2["X-Request-ID"]

    @override_settings(DJANGO_MATT={})
    def test_sets_request_attribute(self, rf):
        captured = {}

        def capture(request):
            captured["rid"] = request.request_id
            return HttpResponse("OK")

        mw = RequestIDMiddleware(capture)
        request = rf.get("/api/")
        response = mw(request)
        assert captured["rid"] == response["X-Request-ID"]

    @override_settings(DJANGO_MATT={"TRUST_PROXY_REQUEST_ID": True})
    def test_trusts_upstream_header(self, rf):
        mw = RequestIDMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_X_REQUEST_ID="upstream-id-123")
        response = mw(request)
        assert response["X-Request-ID"] == "upstream-id-123"

    @override_settings(DJANGO_MATT={"TRUST_PROXY_REQUEST_ID": False})
    def test_ignores_upstream_when_not_trusted(self, rf):
        mw = RequestIDMiddleware(_ok_response)
        request = rf.get("/api/", HTTP_X_REQUEST_ID="upstream-id-123")
        response = mw(request)
        assert response["X-Request-ID"] != "upstream-id-123"

    @override_settings(DJANGO_MATT={"REQUEST_ID_HEADER": "X-Trace-ID"})
    def test_custom_header_name(self, rf):
        mw = RequestIDMiddleware(_ok_response)
        request = rf.get("/api/")
        response = mw(request)
        assert "X-Trace-ID" in response

    @override_settings(DJANGO_MATT={})
    def test_contextvar_set_during_request(self, rf):
        captured = {}

        def capture(request):
            captured["ctx_rid"] = get_request_id()
            return HttpResponse("OK")

        mw = RequestIDMiddleware(capture)
        request = rf.get("/api/")
        response = mw(request)
        assert captured["ctx_rid"] == response["X-Request-ID"]

    @override_settings(DJANGO_MATT={})
    def test_contextvar_reset_after_request(self, rf):
        mw = RequestIDMiddleware(_ok_response)
        mw(rf.get("/api/"))
        # After middleware completes, contextvar should be reset to default
        assert get_request_id() == ""


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware
# ---------------------------------------------------------------------------


class TestSecurityHeadersMiddleware:
    """Test security header injection."""

    @override_settings(DJANGO_MATT={})
    def test_default_headers_present(self, rf):
        mw = SecurityHeadersMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in response
        assert "Strict-Transport-Security" in response
        assert "Referrer-Policy" in response
        assert "Permissions-Policy" in response

    @override_settings(DJANGO_MATT={})
    def test_hsts_default_max_age(self, rf):
        mw = SecurityHeadersMiddleware(_ok_response)
        response = mw(rf.get("/"))
        hsts = response["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    @override_settings(
        DJANGO_MATT={
            "SECURITY_HEADERS": {
                "HSTS_MAX_AGE": 7200,
                "HSTS_INCLUDE_SUBDOMAINS": False,
                "HSTS_PRELOAD": True,
            }
        }
    )
    def test_hsts_custom_config(self, rf):
        mw = SecurityHeadersMiddleware(_ok_response)
        response = mw(rf.get("/"))
        hsts = response["Strict-Transport-Security"]
        assert "max-age=7200" in hsts
        assert "includeSubDomains" not in hsts
        assert "preload" in hsts

    @override_settings(
        DJANGO_MATT={
            "SECURITY_HEADERS": {
                "CONTENT_SECURITY_POLICY": "default-src 'none'",
            }
        }
    )
    def test_custom_csp(self, rf):
        mw = SecurityHeadersMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert response["Content-Security-Policy"] == "default-src 'none'"

    @override_settings(DJANGO_MATT={"SECURITY_HEADERS": {"X_FRAME_OPTIONS": "SAMEORIGIN"}})
    def test_custom_x_frame_options(self, rf):
        mw = SecurityHeadersMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert response["X-Frame-Options"] == "SAMEORIGIN"

    @override_settings(DJANGO_MATT={"SECURITY_HEADERS": {"REFERRER_POLICY": "no-referrer"}})
    def test_custom_referrer_policy(self, rf):
        mw = SecurityHeadersMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert response["Referrer-Policy"] == "no-referrer"

    @override_settings(DJANGO_MATT={"SECURITY_HEADERS": {"PERMISSIONS_POLICY": "camera=()"}})
    def test_custom_permissions_policy(self, rf):
        mw = SecurityHeadersMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert response["Permissions-Policy"] == "camera=()"

    @override_settings(DJANGO_MATT={"SECURITY_HEADERS": {"ENABLED": False}})
    def test_disabled_no_headers(self, rf):
        mw = SecurityHeadersMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert "X-Content-Type-Options" not in response
        assert "X-Frame-Options" not in response
        assert "Content-Security-Policy" not in response
        assert "Strict-Transport-Security" not in response

    @override_settings(DJANGO_MATT={"SECURITY_HEADERS": {"CONTENT_SECURITY_POLICY": ""}})
    def test_empty_csp_not_set(self, rf):
        mw = SecurityHeadersMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert "Content-Security-Policy" not in response

    @override_settings(DJANGO_MATT={"SECURITY_HEADERS": {"HSTS_MAX_AGE": 0}})
    def test_hsts_disabled_with_zero(self, rf):
        mw = SecurityHeadersMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert "Strict-Transport-Security" not in response

    @override_settings(DJANGO_MATT={})
    def test_does_not_modify_status_code(self, rf):
        mw = SecurityHeadersMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# TimingMiddleware
# ---------------------------------------------------------------------------


class TestTimingMiddleware:
    """Test response timing header."""

    @override_settings(DJANGO_MATT={})
    def test_adds_timing_header(self, rf):
        mw = TimingMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert "X-Response-Time" in response

    @override_settings(DJANGO_MATT={})
    def test_timing_format(self, rf):
        mw = TimingMiddleware(_ok_response)
        response = mw(rf.get("/"))
        value = response["X-Response-Time"]
        # Should end with "ms" and be a valid float prefix
        assert value.endswith("ms")
        float(value.replace("ms", ""))

    @override_settings(DJANGO_MATT={})
    def test_timing_is_nonnegative(self, rf):
        mw = TimingMiddleware(_ok_response)
        response = mw(rf.get("/"))
        ms = float(response["X-Response-Time"].replace("ms", ""))
        assert ms >= 0

    @override_settings(DJANGO_MATT={})
    def test_slow_request_measurable(self, rf):
        mw = TimingMiddleware(_slow_response)
        response = mw(rf.get("/"))
        ms = float(response["X-Response-Time"].replace("ms", ""))
        # At least 4ms for a 5ms sleep
        assert ms >= 4

    @override_settings(DJANGO_MATT={"TIMING": {"HEADER_NAME": "X-Duration"}})
    def test_custom_header_name(self, rf):
        mw = TimingMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert "X-Duration" in response

    @override_settings(DJANGO_MATT={"TIMING": {"ENABLED": False}})
    def test_disabled_no_header(self, rf):
        mw = TimingMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert "X-Response-Time" not in response

    @override_settings(DJANGO_MATT={"TIMING": {"ENABLED": False}})
    def test_disabled_passthrough(self, rf):
        mw = TimingMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert response.status_code == 200
        assert response.content == b"OK"


# ---------------------------------------------------------------------------
# RequestLoggingMiddleware
# ---------------------------------------------------------------------------


class TestRequestLoggingMiddleware:
    """Test structured request logging."""

    @override_settings(DJANGO_MATT={})
    def test_logs_request(self, rf):
        mw = RequestLoggingMiddleware(_ok_response)
        with patch("django_matt.middleware.logging.logger") as mock_logger:
            mw(rf.get("/api/test/"))
            mock_logger.log.assert_called_once()
            call_args = mock_logger.log.call_args
            extra = call_args.kwargs.get("extra", {})
            assert extra["method"] == "GET"
            assert extra["path"] == "/api/test/"
            assert extra["status"] == 200
            assert "duration_ms" in extra

    @override_settings(DJANGO_MATT={"REQUEST_LOGGING": {"EXCLUDE_PATHS": ["/health/", "/ready/"]}})
    def test_excluded_paths_not_logged(self, rf):
        mw = RequestLoggingMiddleware(_ok_response)
        with patch("django_matt.middleware.logging.logger") as mock_logger:
            mw(rf.get("/health/"))
            mock_logger.log.assert_not_called()

    @override_settings(DJANGO_MATT={"REQUEST_LOGGING": {"ENABLED": False}})
    def test_disabled_no_logging(self, rf):
        mw = RequestLoggingMiddleware(_ok_response)
        with patch("django_matt.middleware.logging.logger") as mock_logger:
            mw(rf.get("/api/"))
            mock_logger.log.assert_not_called()

    @override_settings(DJANGO_MATT={})
    def test_passthrough_response(self, rf):
        mw = RequestLoggingMiddleware(_ok_response)
        response = mw(rf.get("/api/"))
        assert response.status_code == 200

    @override_settings(DJANGO_MATT={})
    def test_includes_request_id_if_present(self, rf):
        def capture_with_rid(request):
            request.request_id = "test-rid-123"
            return HttpResponse("OK", status=200)

        mw = RequestLoggingMiddleware(capture_with_rid)
        with patch("django_matt.middleware.logging.logger") as mock_logger:
            mw(rf.get("/api/"))
            extra = mock_logger.log.call_args.kwargs.get("extra", {})
            assert extra.get("request_id") == "test-rid-123"


# ---------------------------------------------------------------------------
# JSONResponseMiddleware
# ---------------------------------------------------------------------------


class TestJSONResponseMiddleware:
    """Test dict-to-JsonResponse conversion."""

    @override_settings(DJANGO_MATT={})
    def test_dict_converted_to_json_response(self, rf):
        mw = JSONResponseMiddleware(_dict_response)
        response = mw(rf.get("/api/"))
        assert isinstance(response, JsonResponse)

    @override_settings(DJANGO_MATT={})
    def test_http_response_passthrough(self, rf):
        mw = JSONResponseMiddleware(_ok_response)
        response = mw(rf.get("/api/"))
        assert not isinstance(response, JsonResponse)
        assert response.content == b"OK"


# ---------------------------------------------------------------------------
# APIExceptionMiddleware
# ---------------------------------------------------------------------------


class TestAPIExceptionMiddleware:
    """Test API exception handling middleware."""

    @override_settings(DJANGO_MATT={})
    def test_normal_request_passthrough(self, rf):
        mw = APIExceptionMiddleware(_ok_response)
        response = mw(rf.get("/api/test/"))
        assert response.status_code == 200

    @override_settings(DJANGO_MATT={})
    def test_non_api_path_reraises(self, rf):
        mw = APIExceptionMiddleware(_error_response)
        request = rf.get("/admin/test/")
        with pytest.raises(ValueError, match="something broke"):
            mw(request)

    @override_settings(DJANGO_MATT={})
    def test_api_path_catches_exception(self, rf):
        mw = APIExceptionMiddleware(_error_response)
        request = rf.get("/api/test/")
        response = mw(request)
        # Should return a structured error response, not raise
        assert response.status_code >= 400


# ---------------------------------------------------------------------------
# Middleware stacks (module-level constants)
# ---------------------------------------------------------------------------


class TestMiddlewareStacks:
    """Test the predefined middleware stack constants."""

    def test_production_stack_includes_security(self):
        assert SecurityHeadersMiddleware in PRODUCTION_STACK

    def test_production_stack_includes_request_id(self):
        assert RequestIDMiddleware in PRODUCTION_STACK

    def test_production_stack_includes_cors(self):
        assert CORSMiddleware in PRODUCTION_STACK

    def test_production_stack_includes_timing(self):
        assert TimingMiddleware in PRODUCTION_STACK

    def test_production_stack_includes_logging(self):
        assert RequestLoggingMiddleware in PRODUCTION_STACK

    def test_development_stack_no_security(self):
        assert SecurityHeadersMiddleware not in DEVELOPMENT_STACK

    def test_development_stack_includes_request_id(self):
        assert RequestIDMiddleware in DEVELOPMENT_STACK

    def test_development_stack_includes_cors(self):
        assert CORSMiddleware in DEVELOPMENT_STACK

    def test_development_stack_includes_timing(self):
        assert TimingMiddleware in DEVELOPMENT_STACK


# ---------------------------------------------------------------------------
# Middleware chaining integration
# ---------------------------------------------------------------------------


class TestMiddlewareChaining:
    """Test that multiple middleware chain correctly."""

    @override_settings(
        DJANGO_MATT={
            "CORS": {"ALLOWED_ORIGINS": ["https://app.example.com"]},
        }
    )
    def test_request_id_then_cors(self, rf):
        """Chain RequestID -> CORS and verify both headers appear."""
        inner = CORSMiddleware(_ok_response)
        outer = RequestIDMiddleware(inner)
        request = rf.get("/api/", HTTP_ORIGIN="https://app.example.com")
        response = outer(request)
        assert "X-Request-ID" in response
        assert response["Access-Control-Allow-Origin"] == "https://app.example.com"

    @override_settings(DJANGO_MATT={})
    def test_timing_wraps_request_id(self, rf):
        """Chain Timing -> RequestID and verify both headers appear."""
        inner = RequestIDMiddleware(_ok_response)
        outer = TimingMiddleware(inner)
        response = outer(rf.get("/"))
        assert "X-Request-ID" in response
        assert "X-Response-Time" in response

    @override_settings(DJANGO_MATT={})
    def test_security_plus_timing(self, rf):
        """Chain Security -> Timing and verify all headers."""
        inner = TimingMiddleware(_ok_response)
        outer = SecurityHeadersMiddleware(inner)
        response = outer(rf.get("/"))
        assert "X-Content-Type-Options" in response
        assert "X-Response-Time" in response

    @override_settings(
        DJANGO_MATT={
            "CORS": {"ALLOWED_ORIGINS": True},
        }
    )
    def test_full_production_chain(self, rf):
        """Chain Security -> RequestID -> CORS -> Timing (minimal production)."""
        chain = _ok_response
        for mw_cls in reversed(
            [SecurityHeadersMiddleware, RequestIDMiddleware, CORSMiddleware, TimingMiddleware]
        ):
            chain = mw_cls(chain)

        request = rf.get("/api/", HTTP_ORIGIN="https://test.com")
        response = chain(request)

        assert "X-Content-Type-Options" in response
        assert "X-Request-ID" in response
        assert response["Access-Control-Allow-Origin"] == "*"
        assert "X-Response-Time" in response
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# DjangoMattMiddleware (chaining.py)
# ---------------------------------------------------------------------------


class TestDjangoMattMiddleware:
    """Test the main DjangoMattMiddleware with auto-chaining."""

    @override_settings(DJANGO_MATT={})
    def test_passthrough_without_stack(self, rf):
        """No MIDDLEWARE_STACK configured — simple passthrough."""
        mw = DjangoMattMiddleware(_ok_response)
        response = mw(rf.get("/"))
        assert response.status_code == 200

    @override_settings(DJANGO_MATT={"MIDDLEWARE_STACK": "development"})
    def test_development_stack_chains(self, rf):
        mw = DjangoMattMiddleware(_ok_response)
        response = mw(rf.get("/", HTTP_ORIGIN="https://x.com"))
        # Development stack includes RequestID and Timing
        assert "X-Request-ID" in response
        assert "X-Response-Time" in response

    @override_settings(DJANGO_MATT={"MIDDLEWARE_STACK": "production"})
    def test_production_stack_chains(self, rf):
        mw = DjangoMattMiddleware(_ok_response)
        response = mw(rf.get("/"))
        # Production stack adds security headers
        assert "X-Content-Type-Options" in response
        assert "X-Request-ID" in response
        assert "X-Response-Time" in response

    @override_settings(
        DJANGO_MATT={
            "MIDDLEWARE_STACK": [
                "django_matt.middleware.timing.TimingMiddleware",
            ]
        }
    )
    def test_custom_stack_with_class_list(self, rf):
        """Custom stack using actual class references."""
        # Build with actual classes instead of strings
        with override_settings(DJANGO_MATT={"MIDDLEWARE_STACK": [TimingMiddleware]}):
            mw = DjangoMattMiddleware(_ok_response)
            response = mw(rf.get("/"))
            assert "X-Response-Time" in response
