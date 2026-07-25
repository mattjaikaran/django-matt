"""Tests for django_matt.middleware package."""

import logging

from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, override_settings

from django_matt.errors import ErrorEnhancementMiddleware
from django_matt.middleware import (
    DEVELOPMENT_STACK,
    PRODUCTION_STACK,
    CORSMiddleware,
    QueryStringParserMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    TimingMiddleware,
)
from django_matt.middleware.request_id import get_request_id, request_id_var


def _get_response(request):
    """Simple view that returns 200 OK."""
    return HttpResponse("OK")


def _json_response(request):
    """Simple view that returns JSON."""
    return JsonResponse({"status": "ok"})


# ---------------------------------------------------------------
# SecurityHeadersMiddleware
# ---------------------------------------------------------------


class TestSecurityHeaders:
    def test_default_headers(self):
        mw = SecurityHeadersMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))

        assert response["Content-Security-Policy"]
        assert response["Strict-Transport-Security"]
        assert response["X-Frame-Options"] == "DENY"
        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Permissions-Policy" in response

    def test_default_csp_value(self):
        mw = SecurityHeadersMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert response["Content-Security-Policy"] == (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
        )

    def test_hsts_includes_subdomains(self):
        mw = SecurityHeadersMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        hsts = response["Strict-Transport-Security"]
        assert "includeSubDomains" in hsts
        assert "max-age=31536000" in hsts

    def test_hsts_no_preload_by_default(self):
        mw = SecurityHeadersMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert "preload" not in response["Strict-Transport-Security"]

    @override_settings(DJANGO_MATT={"SECURITY_HEADERS": {"HSTS_PRELOAD": True}})
    def test_hsts_preload_when_configured(self):
        mw = SecurityHeadersMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert "preload" in response["Strict-Transport-Security"]

    def test_default_permissions_policy(self):
        mw = SecurityHeadersMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert response["Permissions-Policy"] == "geolocation=(), camera=(), microphone=()"

    @override_settings(DJANGO_MATT={"SECURITY_HEADERS": {"ENABLED": False}})
    def test_disabled(self):
        mw = SecurityHeadersMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert "Content-Security-Policy" not in response
        assert "Strict-Transport-Security" not in response
        assert "Permissions-Policy" not in response

    @override_settings(DJANGO_MATT={"SECURITY_HEADERS": {"X_FRAME_OPTIONS": "SAMEORIGIN"}})
    def test_custom_frame_options(self):
        mw = SecurityHeadersMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert response["X-Frame-Options"] == "SAMEORIGIN"

    @override_settings(
        DJANGO_MATT={
            "SECURITY_HEADERS": {
                "CONTENT_SECURITY_POLICY": "default-src 'none'",
                "REFERRER_POLICY": "no-referrer",
            }
        }
    )
    def test_custom_csp_and_referrer(self):
        mw = SecurityHeadersMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert response["Content-Security-Policy"] == "default-src 'none'"
        assert response["Referrer-Policy"] == "no-referrer"

    def test_passes_through_response_body(self):
        mw = SecurityHeadersMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert response.content == b"OK"


# ---------------------------------------------------------------
# RequestIDMiddleware
# ---------------------------------------------------------------


class TestRequestID:
    def test_generates_id(self):
        mw = RequestIDMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        rid = response.get("X-Request-ID")
        assert rid is not None
        # uuid4().hex is 32 hex characters
        assert len(rid) == 32

    def test_generated_id_is_valid_hex(self):
        mw = RequestIDMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        rid = response["X-Request-ID"]
        # Should be parseable as a UUID hex
        int(rid, 16)

    def test_propagates_incoming_header(self):
        mw = RequestIDMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.get("/", HTTP_X_REQUEST_ID="my-custom-id")
        response = mw(request)
        assert response["X-Request-ID"] == "my-custom-id"

    def test_sets_on_request_object(self):
        captured = {}

        def capture_view(request):
            captured["rid"] = request.request_id
            return HttpResponse("OK")

        mw = RequestIDMiddleware(capture_view)
        factory = RequestFactory()
        mw(factory.get("/"))
        assert captured["rid"]

    def test_contextvar_set_during_request(self):
        captured = {}

        def capture_view(request):
            captured["rid"] = get_request_id()
            return HttpResponse("OK")

        mw = RequestIDMiddleware(capture_view)
        factory = RequestFactory()
        mw(factory.get("/"))
        assert captured["rid"]
        assert len(captured["rid"]) == 32

    def test_contextvar_matches_header(self):
        captured = {}

        def capture_view(request):
            captured["contextvar_rid"] = get_request_id()
            captured["attr_rid"] = request.request_id
            return HttpResponse("OK")

        mw = RequestIDMiddleware(capture_view)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        header_rid = response["X-Request-ID"]
        assert captured["contextvar_rid"] == header_rid
        assert captured["attr_rid"] == header_rid

    def test_contextvar_reset_after_request(self):
        mw = RequestIDMiddleware(_get_response)
        factory = RequestFactory()
        mw(factory.get("/"))
        # After request completes, contextvar should be reset to default ""
        assert request_id_var.get() == ""

    @override_settings(DJANGO_MATT={"TRUST_PROXY_REQUEST_ID": False})
    def test_ignores_proxy_when_untrusted(self):
        mw = RequestIDMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.get("/", HTTP_X_REQUEST_ID="proxy-id")
        response = mw(request)
        # Should generate a new ID, not use the proxy one
        assert response["X-Request-ID"] != "proxy-id"
        assert len(response["X-Request-ID"]) == 32

    def test_unique_ids_per_request(self):
        mw = RequestIDMiddleware(_get_response)
        factory = RequestFactory()
        ids = set()
        for _ in range(10):
            response = mw(factory.get("/"))
            ids.add(response["X-Request-ID"])
        assert len(ids) == 10


# ---------------------------------------------------------------
# CORSMiddleware
# ---------------------------------------------------------------


class TestCORS:
    @override_settings(
        DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://example.com"], "ENABLED": True}}
    )
    def test_allows_matching_origin(self):
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.get("/", HTTP_ORIGIN="https://example.com")
        response = mw(request)
        assert response["Access-Control-Allow-Origin"] == "https://example.com"

    @override_settings(
        DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://example.com"], "ENABLED": True}}
    )
    def test_blocks_non_matching_origin(self):
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.get("/", HTTP_ORIGIN="https://evil.com")
        response = mw(request)
        assert "Access-Control-Allow-Origin" not in response

    @override_settings(DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": True, "ENABLED": True}})
    def test_wildcard_allows_all_with_true(self):
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.get("/", HTTP_ORIGIN="https://anything.com")
        response = mw(request)
        assert response["Access-Control-Allow-Origin"] == "*"

    @override_settings(DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["*"], "ENABLED": True}})
    def test_wildcard_allows_all_with_star_list(self):
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.get("/", HTTP_ORIGIN="https://anything.com")
        response = mw(request)
        assert response["Access-Control-Allow-Origin"] == "*"

    @override_settings(
        DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://example.com"], "ENABLED": True}}
    )
    def test_preflight_returns_204(self):
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.options("/", HTTP_ORIGIN="https://example.com")
        response = mw(request)
        assert response.status_code == 204
        assert "Access-Control-Allow-Methods" in response
        assert "Access-Control-Allow-Headers" in response

    @override_settings(
        DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://example.com"], "ENABLED": True}}
    )
    def test_preflight_includes_max_age(self):
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.options("/", HTTP_ORIGIN="https://example.com")
        response = mw(request)
        assert response["Access-Control-Max-Age"] == "86400"

    @override_settings(DJANGO_MATT={"CORS": {"ENABLED": False}})
    def test_disabled(self):
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.get("/", HTTP_ORIGIN="https://example.com")
        response = mw(request)
        assert "Access-Control-Allow-Origin" not in response

    @override_settings(
        DJANGO_MATT={
            "CORS": {
                "ALLOWED_ORIGINS": ["https://example.com"],
                "ALLOW_CREDENTIALS": True,
                "ENABLED": True,
            }
        }
    )
    def test_credentials(self):
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.get("/", HTTP_ORIGIN="https://example.com")
        response = mw(request)
        assert response["Access-Control-Allow-Credentials"] == "true"

    @override_settings(
        DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://example.com"], "ENABLED": True}}
    )
    def test_no_credentials_by_default(self):
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.get("/", HTTP_ORIGIN="https://example.com")
        response = mw(request)
        assert "Access-Control-Allow-Credentials" not in response

    def test_no_origin_header_no_cors(self):
        """When no Origin header is present, no CORS headers should be added."""
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert "Access-Control-Allow-Origin" not in response

    @override_settings(
        DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://example.com"], "ENABLED": True}}
    )
    def test_vary_header_set_for_specific_origin(self):
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.get("/", HTTP_ORIGIN="https://example.com")
        response = mw(request)
        assert response.get("Vary") == "Origin"

    @override_settings(
        DJANGO_MATT={"CORS": {"ALLOWED_ORIGINS": ["https://example.com"], "ENABLED": True}}
    )
    def test_expose_headers_default(self):
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.get("/", HTTP_ORIGIN="https://example.com")
        response = mw(request)
        expose = response.get("Access-Control-Expose-Headers", "")
        assert "X-Request-ID" in expose
        assert "X-Response-Time" in expose

    @override_settings(
        DJANGO_MATT={
            "CORS": {
                "ALLOWED_ORIGINS": ["https://evil.com"],
                "ENABLED": True,
            }
        }
    )
    def test_preflight_blocked_origin_no_cors_headers(self):
        """Preflight with non-matching origin should not set CORS headers."""
        mw = CORSMiddleware(_get_response)
        factory = RequestFactory()
        request = factory.options("/", HTTP_ORIGIN="https://other.com")
        response = mw(request)
        assert response.status_code == 204
        assert "Access-Control-Allow-Origin" not in response


# ---------------------------------------------------------------
# RequestLoggingMiddleware
# ---------------------------------------------------------------


class TestRequestLogging:
    def test_logs_request(self, caplog):
        with caplog.at_level(logging.INFO, logger="django_matt.requests"):
            mw = RequestLoggingMiddleware(_get_response)
            factory = RequestFactory()
            mw(factory.get("/test/"))

        assert any("/test/" in r.message for r in caplog.records)

    def test_logs_method_and_status(self, caplog):
        with caplog.at_level(logging.INFO, logger="django_matt.requests"):
            mw = RequestLoggingMiddleware(_get_response)
            factory = RequestFactory()
            mw(factory.get("/api/data/"))

        assert any("GET" in r.message and "200" in r.message for r in caplog.records)

    @override_settings(DJANGO_MATT={"REQUEST_LOGGING": {"ENABLED": False}})
    def test_disabled(self, caplog):
        with caplog.at_level(logging.INFO, logger="django_matt.requests"):
            mw = RequestLoggingMiddleware(_get_response)
            factory = RequestFactory()
            mw(factory.get("/test/"))

        assert not any("/test/" in r.message for r in caplog.records)

    @override_settings(DJANGO_MATT={"REQUEST_LOGGING": {"EXCLUDE_PATHS": ["/health/"]}})
    def test_exclude_paths(self, caplog):
        with caplog.at_level(logging.INFO, logger="django_matt.requests"):
            mw = RequestLoggingMiddleware(_get_response)
            factory = RequestFactory()
            mw(factory.get("/health/"))

        assert not any("/health/" in r.message for r in caplog.records)

    def test_default_excludes_health(self, caplog):
        """Default config excludes /health/, /ready/, and /favicon.ico."""
        with caplog.at_level(logging.INFO, logger="django_matt.requests"):
            mw = RequestLoggingMiddleware(_get_response)
            factory = RequestFactory()
            mw(factory.get("/health/"))
            mw(factory.get("/ready/"))
            mw(factory.get("/favicon.ico"))

        assert not any(
            path in r.message
            for r in caplog.records
            for path in ("/health/", "/ready/", "/favicon.ico")
        )

    def test_non_excluded_paths_logged(self, caplog):
        """Paths not in the exclude list should be logged."""
        with caplog.at_level(logging.INFO, logger="django_matt.requests"):
            mw = RequestLoggingMiddleware(_get_response)
            factory = RequestFactory()
            mw(factory.get("/api/users/"))

        assert any("/api/users/" in r.message for r in caplog.records)

    def test_passes_through_response(self):
        mw = RequestLoggingMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert response.content == b"OK"
        assert response.status_code == 200


# ---------------------------------------------------------------
# TimingMiddleware
# ---------------------------------------------------------------


class TestTiming:
    def test_adds_timing_header(self):
        mw = TimingMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert "X-Response-Time" in response
        assert response["X-Response-Time"].endswith("ms")

    def test_timing_value_is_numeric(self):
        mw = TimingMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        value = response["X-Response-Time"]
        # Should be like "0.1ms" — parse the numeric part
        numeric = value.replace("ms", "")
        float(numeric)  # Should not raise

    @override_settings(DJANGO_MATT={"TIMING": {"HEADER_NAME": "X-Duration"}})
    def test_custom_header_name(self):
        mw = TimingMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert "X-Duration" in response
        assert response["X-Duration"].endswith("ms")

    @override_settings(DJANGO_MATT={"TIMING": {"ENABLED": False}})
    def test_disabled(self):
        mw = TimingMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert "X-Response-Time" not in response

    def test_passes_through_response(self):
        mw = TimingMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert response.content == b"OK"
        assert response.status_code == 200


# ---------------------------------------------------------------
# Stack constants
# ---------------------------------------------------------------


class TestStacks:
    def test_production_stack_has_all(self):
        assert ErrorEnhancementMiddleware in PRODUCTION_STACK
        assert SecurityHeadersMiddleware in PRODUCTION_STACK
        assert RequestIDMiddleware in PRODUCTION_STACK
        assert CORSMiddleware in PRODUCTION_STACK
        assert QueryStringParserMiddleware in PRODUCTION_STACK
        assert RequestLoggingMiddleware in PRODUCTION_STACK
        assert TimingMiddleware in PRODUCTION_STACK

    def test_production_stack_length(self):
        assert len(PRODUCTION_STACK) == 7

    def test_development_stack_no_security(self):
        assert SecurityHeadersMiddleware not in DEVELOPMENT_STACK
        assert ErrorEnhancementMiddleware in DEVELOPMENT_STACK
        assert RequestIDMiddleware in DEVELOPMENT_STACK
        assert CORSMiddleware in DEVELOPMENT_STACK
        assert QueryStringParserMiddleware in DEVELOPMENT_STACK
        assert RequestLoggingMiddleware in DEVELOPMENT_STACK
        assert TimingMiddleware in DEVELOPMENT_STACK

    def test_development_stack_length(self):
        assert len(DEVELOPMENT_STACK) == 6

    def test_production_stack_order(self):
        # ErrorEnhancement must be first (outermost) so it catches everything.
        assert PRODUCTION_STACK[0] is ErrorEnhancementMiddleware
        assert PRODUCTION_STACK[1] is SecurityHeadersMiddleware
        assert PRODUCTION_STACK[2] is RequestIDMiddleware
        assert PRODUCTION_STACK[3] is CORSMiddleware
        assert PRODUCTION_STACK[4] is QueryStringParserMiddleware
        assert PRODUCTION_STACK[5] is RequestLoggingMiddleware
        assert PRODUCTION_STACK[6] is TimingMiddleware

    def test_development_stack_order(self):
        assert DEVELOPMENT_STACK[0] is ErrorEnhancementMiddleware
        assert DEVELOPMENT_STACK[1] is RequestIDMiddleware
        assert DEVELOPMENT_STACK[2] is CORSMiddleware
        assert DEVELOPMENT_STACK[3] is QueryStringParserMiddleware
        assert DEVELOPMENT_STACK[4] is RequestLoggingMiddleware
        assert DEVELOPMENT_STACK[5] is TimingMiddleware


# ---------------------------------------------------------------
# DjangoMattMiddleware auto-chaining
# ---------------------------------------------------------------


class TestDjangoMattMiddlewareChaining:
    """Test DjangoMattMiddleware with MIDDLEWARE_STACK configuration."""

    @override_settings(DJANGO_MATT={"MIDDLEWARE_STACK": "production"})
    def test_production_string_chains_all(self):
        from django_matt.middleware import DjangoMattMiddleware

        mw = DjangoMattMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))

        # Production stack includes SecurityHeaders + Timing at minimum
        assert "Content-Security-Policy" in response
        assert "X-Response-Time" in response
        assert "X-Request-ID" in response

    @override_settings(DJANGO_MATT={"MIDDLEWARE_STACK": "development"})
    def test_development_string_no_security(self):
        from django_matt.middleware import DjangoMattMiddleware

        mw = DjangoMattMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))

        # Development stack does NOT include SecurityHeaders
        assert "Content-Security-Policy" not in response
        # But does include Timing and RequestID
        assert "X-Response-Time" in response
        assert "X-Request-ID" in response

    def test_no_stack_config_passes_through(self):
        """When MIDDLEWARE_STACK is not set, no internal chain is built."""
        from django_matt.middleware import DjangoMattMiddleware

        mw = DjangoMattMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))

        # No internal middleware, so no extra headers
        assert "Content-Security-Policy" not in response
        assert "X-Response-Time" not in response
        assert "X-Request-ID" not in response
        assert response.content == b"OK"

    def test_custom_list_of_classes(self):
        """Custom list of actual middleware classes in MIDDLEWARE_STACK."""
        from django.test import override_settings as _override

        with _override(DJANGO_MATT={"MIDDLEWARE_STACK": [TimingMiddleware]}):
            from django_matt.middleware import DjangoMattMiddleware

            mw = DjangoMattMiddleware(_get_response)
            factory = RequestFactory()
            response = mw(factory.get("/"))
            assert "X-Response-Time" in response
            # Only Timing is in the stack, no security headers
            assert "Content-Security-Policy" not in response

    @override_settings(
        DJANGO_MATT={
            "MIDDLEWARE_STACK": None,
        }
    )
    def test_explicit_none_no_chain(self):
        from django_matt.middleware import DjangoMattMiddleware

        mw = DjangoMattMiddleware(_get_response)
        assert mw._inner_chain is None

    @override_settings(DJANGO_MATT={"MIDDLEWARE_STACK": "invalid_name"})
    def test_unknown_stack_name_no_chain(self):
        """An unrecognized stack name results in no chain (empty list)."""
        from django_matt.middleware import DjangoMattMiddleware

        mw = DjangoMattMiddleware(_get_response)
        assert mw._inner_chain is None

    @override_settings(DJANGO_MATT={"MIDDLEWARE_STACK": "production"})
    def test_production_chain_response_body_intact(self):
        from django_matt.middleware import DjangoMattMiddleware

        mw = DjangoMattMiddleware(_get_response)
        factory = RequestFactory()
        response = mw(factory.get("/"))
        assert response.content == b"OK"


class TestDjangoMattMiddlewareCustomStack:
    """Test DjangoMattMiddleware with a list of actual middleware classes."""

    def test_custom_class_list(self):
        """Pass actual classes in MIDDLEWARE_STACK."""
        from django.test import override_settings as _override

        with _override(DJANGO_MATT={"MIDDLEWARE_STACK": [TimingMiddleware]}):
            from django_matt.middleware import DjangoMattMiddleware

            mw = DjangoMattMiddleware(_get_response)
            factory = RequestFactory()
            response = mw(factory.get("/"))

            assert "X-Response-Time" in response
            # No security headers since only Timing is in stack
            assert "Content-Security-Policy" not in response

    def test_custom_two_class_stack(self):
        """Pass two classes — both should apply."""
        from django.test import override_settings as _override

        with _override(
            DJANGO_MATT={
                "MIDDLEWARE_STACK": [SecurityHeadersMiddleware, TimingMiddleware],
            }
        ):
            from django_matt.middleware import DjangoMattMiddleware

            mw = DjangoMattMiddleware(_get_response)
            factory = RequestFactory()
            response = mw(factory.get("/"))

            assert "Content-Security-Policy" in response
            assert "X-Response-Time" in response


# ---------------------------------------------------------------
# Integration: multiple middleware together
# ---------------------------------------------------------------


class TestMiddlewareIntegration:
    """Test middleware composed together manually (not via DjangoMattMiddleware)."""

    def test_request_id_visible_in_logging(self, caplog):
        """RequestID middleware sets request.request_id which logging can pick up."""

        def view(request):
            return HttpResponse("OK")

        # Chain: RequestID -> Logging -> view
        logging_mw = RequestLoggingMiddleware(view)
        rid_mw = RequestIDMiddleware(logging_mw)

        factory = RequestFactory()
        with caplog.at_level(logging.INFO, logger="django_matt.requests"):
            response = rid_mw(factory.get("/integrated/"))

        assert "X-Request-ID" in response
        assert any("/integrated/" in r.message for r in caplog.records)

    def test_timing_and_security_compose(self):
        """Timing + Security headers both appear on the response."""
        timing_mw = TimingMiddleware(_get_response)
        security_mw = SecurityHeadersMiddleware(timing_mw)

        factory = RequestFactory()
        response = security_mw(factory.get("/"))

        assert "X-Response-Time" in response
        assert "Content-Security-Policy" in response
        assert "X-Frame-Options" in response

    @override_settings(
        DJANGO_MATT={
            "CORS": {
                "ALLOWED_ORIGINS": ["https://app.example.com"],
                "ENABLED": True,
            }
        }
    )
    def test_full_stack_manual_chain(self):
        """Manually chain all 5 middleware and verify all headers appear."""
        timing = TimingMiddleware(_get_response)
        logging_mw = RequestLoggingMiddleware(timing)
        cors = CORSMiddleware(logging_mw)
        rid = RequestIDMiddleware(cors)
        security = SecurityHeadersMiddleware(rid)

        factory = RequestFactory()
        request = factory.get("/", HTTP_ORIGIN="https://app.example.com")
        response = security(request)

        assert response["Content-Security-Policy"]
        assert response["X-Request-ID"]
        assert response["Access-Control-Allow-Origin"] == "https://app.example.com"
        assert response["X-Response-Time"].endswith("ms")
        assert response.content == b"OK"
