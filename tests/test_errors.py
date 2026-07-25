"""
Tests for django_matt/core/errors.py — Error handling classes.

Covers:
- ErrorDetail: serialization, to_dict, to_json, to_response
- APIError: status codes, messages, detail serialization
- ValidationAPIError: field errors, multiple errors
- AuthenticationAPIError: 401 responses
- PermissionDeniedAPIError / PermissionAPIError: 403 responses
- NotFoundAPIError: 404 responses
- RateLimitAPIError: 429 responses, retry_after context
- ErrorHandler: capture_exception, status code mapping, suggestions, debug mode
- ErrorMiddleware: process_exception, debug vs production
- handle_exceptions: sync/async decorator
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory

import pytest

from django_matt.core.errors import (
    APIError,
    AuthenticationAPIError,
    ErrorDetail,
    ErrorHandler,
    ErrorMiddleware,
    NotFoundAPIError,
    PermissionAPIError,
    PermissionDeniedAPIError,
    RateLimitAPIError,
    ValidationAPIError,
    handle_exceptions,
)

# ---------------------------------------------------------------------------
# ErrorDetail
# ---------------------------------------------------------------------------


class TestErrorDetail:
    """Tests for the ErrorDetail class."""

    def test_basic_construction(self):
        """ErrorDetail stores all fields correctly."""
        detail = ErrorDetail(
            message="Something broke",
            error_type="ValueError",
            code="value_error",
            status_code=400,
        )
        assert detail.message == "Something broke"
        assert detail.error_type == "ValueError"
        assert detail.code == "value_error"
        assert detail.status_code == 400
        assert detail.path is None
        assert detail.line_number is None
        assert detail.context == {}
        assert detail.suggestion is None
        assert detail.traceback_str is None
        assert detail.code_snippet is None
        assert detail.timestamp  # nonempty ISO string

    def test_construction_with_all_fields(self):
        """ErrorDetail accepts optional fields."""
        detail = ErrorDetail(
            message="err",
            error_type="RuntimeError",
            path="/app/views.py",
            line_number=42,
            context={"key": "val"},
            suggestion="Try again",
            traceback_str="Traceback...",
            code_snippet=["41: pass", "42: raise", "43: pass"],
        )
        assert detail.path == "/app/views.py"
        assert detail.line_number == 42
        assert detail.context == {"key": "val"}
        assert detail.suggestion == "Try again"
        assert detail.traceback_str == "Traceback..."
        assert detail.code_snippet == ["41: pass", "42: raise", "43: pass"]

    def test_to_dict_minimal(self):
        """to_dict returns required keys without optional data."""
        detail = ErrorDetail(message="err", error_type="Err", code="e", status_code=500)
        d = detail.to_dict()
        assert d["message"] == "err"
        assert d["error_type"] == "Err"
        assert d["code"] == "e"
        assert d["status_code"] == 500
        assert "timestamp" in d
        # Optional keys should not be present
        assert "location" not in d
        assert "context" not in d
        assert "suggestion" not in d
        assert "traceback" not in d
        assert "code_snippet" not in d

    def test_to_dict_with_location(self):
        """to_dict includes location when path is set."""
        detail = ErrorDetail(
            message="err",
            error_type="E",
            path="/a.py",
            line_number=10,
        )
        d = detail.to_dict()
        assert d["location"] == {"path": "/a.py", "line": 10}

    def test_to_dict_with_context(self):
        """to_dict includes context when non-empty."""
        detail = ErrorDetail(
            message="err",
            error_type="E",
            context={"request_id": "abc123"},
        )
        d = detail.to_dict()
        assert d["context"]["request_id"] == "abc123"

    def test_to_dict_with_suggestion(self):
        """to_dict includes suggestion when set."""
        detail = ErrorDetail(message="err", error_type="E", suggestion="Fix it")
        d = detail.to_dict()
        assert d["suggestion"] == "Fix it"

    def test_to_dict_traceback_excluded_by_default(self):
        """to_dict excludes traceback unless include_traceback=True."""
        detail = ErrorDetail(
            message="err", error_type="E", traceback_str="Traceback (most recent)..."
        )
        d_no = detail.to_dict(include_traceback=False)
        assert "traceback" not in d_no

        d_yes = detail.to_dict(include_traceback=True)
        assert d_yes["traceback"] == "Traceback (most recent)..."

    def test_to_dict_snippet_excluded_by_default(self):
        """to_dict excludes code_snippet unless include_snippet=True."""
        detail = ErrorDetail(
            message="err", error_type="E", code_snippet=["1: x = 1"]
        )
        d_no = detail.to_dict(include_snippet=False)
        assert "code_snippet" not in d_no

        d_yes = detail.to_dict(include_snippet=True)
        assert d_yes["code_snippet"] == ["1: x = 1"]

    def test_to_json(self):
        """to_json returns valid JSON."""
        detail = ErrorDetail(message="err", error_type="E", code="e", status_code=500)
        raw = detail.to_json()
        parsed = json.loads(raw)
        assert parsed["message"] == "err"

    def test_to_json_with_debug_flags(self):
        """to_json passes through include_traceback and include_snippet."""
        detail = ErrorDetail(
            message="err",
            error_type="E",
            traceback_str="TB",
            code_snippet=["line"],
        )
        parsed_debug = json.loads(
            detail.to_json(include_traceback=True, include_snippet=True)
        )
        assert "traceback" in parsed_debug
        assert "code_snippet" in parsed_debug

    def test_to_response_returns_json_response(self):
        """to_response returns a Django JsonResponse with correct status."""
        detail = ErrorDetail(message="err", error_type="E", status_code=422)
        resp = detail.to_response()
        assert isinstance(resp, JsonResponse)
        assert resp.status_code == 422
        body = json.loads(resp.content)
        assert body["message"] == "err"

    def test_to_response_debug_mode(self):
        """to_response includes traceback/snippet in debug mode."""
        detail = ErrorDetail(
            message="err",
            error_type="E",
            status_code=500,
            traceback_str="TB-content",
            code_snippet=["42: boom"],
        )
        resp = detail.to_response(include_traceback=True, include_snippet=True)
        body = json.loads(resp.content)
        assert body["traceback"] == "TB-content"
        assert body["code_snippet"] == ["42: boom"]


# ---------------------------------------------------------------------------
# APIError base class
# ---------------------------------------------------------------------------


class TestAPIError:
    """Tests for the APIError exception class."""

    def test_default_values(self):
        """APIError defaults to 500, code='api_error'."""
        err = APIError("Something went wrong")
        assert err.message == "Something went wrong"
        assert err.status_code == 500
        assert err.code == "api_error"
        assert err.context == {}
        assert err.suggestion is None
        assert str(err) == "Something went wrong"

    def test_custom_status_code(self):
        """APIError accepts custom status codes."""
        err = APIError("Bad", status_code=418, code="teapot")
        assert err.status_code == 418
        assert err.code == "teapot"

    def test_context_and_suggestion(self):
        """APIError stores context dict and suggestion string."""
        err = APIError(
            "err",
            context={"field": "name"},
            suggestion="Check the field",
        )
        assert err.context == {"field": "name"}
        assert err.suggestion == "Check the field"

    def test_is_exception(self):
        """APIError is a proper Exception subclass."""
        err = APIError("test")
        assert isinstance(err, Exception)
        with pytest.raises(APIError, match="test"):
            raise err


# ---------------------------------------------------------------------------
# ValidationAPIError
# ---------------------------------------------------------------------------


class TestValidationAPIError:
    """Tests for the ValidationAPIError exception class."""

    def test_defaults(self):
        """ValidationAPIError defaults to 422 and 'validation_error' code."""
        err = ValidationAPIError()
        assert err.status_code == 422
        assert err.code == "validation_error"
        assert err.message == "Validation error"
        assert err.errors == []
        assert err.suggestion == "Check the request data against the schema requirements."

    def test_single_field_error(self):
        """ValidationAPIError stores single field errors."""
        errors = [{"field": "email", "message": "Invalid email"}]
        err = ValidationAPIError(errors=errors)
        assert err.errors == errors
        assert err.context["validation_errors"] == errors

    def test_multiple_field_errors(self):
        """ValidationAPIError stores multiple field errors."""
        errors = [
            {"field": "name", "message": "Required"},
            {"field": "age", "message": "Must be positive"},
            {"field": "email", "message": "Invalid format"},
        ]
        err = ValidationAPIError(message="3 errors", errors=errors)
        assert len(err.errors) == 3
        assert err.message == "3 errors"

    def test_custom_message_and_suggestion(self):
        """ValidationAPIError accepts custom message and suggestion."""
        err = ValidationAPIError(
            message="Custom validation failure",
            suggestion="Check the docs",
        )
        assert err.message == "Custom validation failure"
        assert err.suggestion == "Check the docs"

    def test_context_merges_with_errors(self):
        """Extra context is merged alongside validation_errors."""
        err = ValidationAPIError(
            errors=[{"field": "x", "message": "bad"}],
            context={"request_id": "abc"},
        )
        assert err.context["request_id"] == "abc"
        assert "validation_errors" in err.context

    def test_is_api_error_subclass(self):
        """ValidationAPIError is a subclass of APIError."""
        err = ValidationAPIError()
        assert isinstance(err, APIError)


# ---------------------------------------------------------------------------
# AuthenticationAPIError
# ---------------------------------------------------------------------------


class TestAuthenticationAPIError:
    """Tests for the AuthenticationAPIError exception class."""

    def test_defaults(self):
        """AuthenticationAPIError defaults to 401 and 'authentication_required'."""
        err = AuthenticationAPIError()
        assert err.status_code == 401
        assert err.code == "authentication_required"
        assert err.message == "Authentication required"
        assert err.suggestion == "Provide valid authentication credentials."

    def test_custom_auth_type(self):
        """AuthenticationAPIError stores auth_type in context."""
        err = AuthenticationAPIError(auth_type="bearer")
        assert err.context["auth_type"] == "bearer"

    def test_custom_message(self):
        """AuthenticationAPIError accepts custom message."""
        err = AuthenticationAPIError(message="Token expired")
        assert err.message == "Token expired"

    def test_is_api_error_subclass(self):
        """AuthenticationAPIError is a subclass of APIError."""
        assert isinstance(AuthenticationAPIError(), APIError)


# ---------------------------------------------------------------------------
# PermissionAPIError / PermissionDeniedAPIError
# ---------------------------------------------------------------------------


class TestPermissionAPIError:
    """Tests for the PermissionAPIError exception class."""

    def test_defaults(self):
        """PermissionAPIError defaults to 403 and 'permission_denied'."""
        err = PermissionAPIError()
        assert err.status_code == 403
        assert err.code == "permission_denied"
        assert err.message == "Permission denied"

    def test_required_permission_context(self):
        """PermissionAPIError stores required_permission and builds message."""
        err = PermissionAPIError(required_permission="admin.delete_user")
        assert err.context["required_permission"] == "admin.delete_user"
        assert "admin.delete_user" in err.message

    def test_custom_message_overrides(self):
        """Custom message wins when no required_permission is given."""
        err = PermissionAPIError(message="You cannot do this")
        assert err.message == "You cannot do this"

    def test_alias_backward_compat(self):
        """PermissionDeniedAPIError is an alias for PermissionAPIError."""
        assert PermissionDeniedAPIError is PermissionAPIError
        err = PermissionDeniedAPIError()
        assert isinstance(err, PermissionAPIError)
        assert err.status_code == 403


# ---------------------------------------------------------------------------
# NotFoundAPIError
# ---------------------------------------------------------------------------


class TestNotFoundAPIError:
    """Tests for the NotFoundAPIError exception class."""

    def test_defaults(self):
        """NotFoundAPIError defaults to 404 and 'not_found'."""
        err = NotFoundAPIError()
        assert err.status_code == 404
        assert err.code == "not_found"
        assert err.message == "Resource not found"

    def test_resource_type_and_id(self):
        """NotFoundAPIError builds a descriptive message from resource_type + resource_id."""
        err = NotFoundAPIError(resource_type="User", resource_id="42")
        assert err.context["resource_type"] == "User"
        assert err.context["resource_id"] == "42"
        assert "User" in err.message
        assert "42" in err.message

    def test_resource_type_only(self):
        """NotFoundAPIError stores resource_type even without resource_id."""
        err = NotFoundAPIError(resource_type="Product")
        assert err.context["resource_type"] == "Product"
        # Without resource_id, the default message is used
        assert err.message == "Resource not found"

    def test_custom_suggestion(self):
        """NotFoundAPIError accepts custom suggestion."""
        err = NotFoundAPIError(suggestion="Check the URL")
        assert err.suggestion == "Check the URL"


# ---------------------------------------------------------------------------
# RateLimitAPIError
# ---------------------------------------------------------------------------


class TestRateLimitAPIError:
    """Tests for the RateLimitAPIError exception class."""

    def test_defaults(self):
        """RateLimitAPIError defaults to 429 and 'rate_limit_exceeded'."""
        err = RateLimitAPIError()
        assert err.status_code == 429
        assert err.code == "rate_limit_exceeded"
        assert err.message == "Rate limit exceeded"

    def test_retry_after(self):
        """RateLimitAPIError stores retry_after in context."""
        err = RateLimitAPIError(retry_after=60)
        assert err.context["retry_after"] == 60
        assert "60" in err.suggestion

    def test_limit_and_remaining(self):
        """RateLimitAPIError stores limit and remaining in context."""
        err = RateLimitAPIError(limit=100, remaining=0)
        assert err.context["limit"] == 100
        assert err.context["remaining"] == 0

    def test_remaining_zero_vs_none(self):
        """remaining=0 should be stored; remaining=None should not."""
        err_zero = RateLimitAPIError(remaining=0)
        assert err_zero.context["remaining"] == 0

        err_none = RateLimitAPIError(remaining=None)
        assert "remaining" not in err_none.context

    def test_all_rate_limit_fields(self):
        """RateLimitAPIError stores all fields together."""
        err = RateLimitAPIError(retry_after=30, limit=1000, remaining=0)
        assert err.context["retry_after"] == 30
        assert err.context["limit"] == 1000
        assert err.context["remaining"] == 0


# ---------------------------------------------------------------------------
# ErrorHandler
# ---------------------------------------------------------------------------


class TestErrorHandler:
    """Tests for the ErrorHandler class."""

    def test_debug_flag(self):
        """ErrorHandler stores debug flag."""
        h = ErrorHandler(debug=True)
        assert h.debug is True

        h2 = ErrorHandler(debug=False)
        assert h2.debug is False

    def test_status_code_for_api_error(self):
        """ErrorHandler uses status_code from APIError."""
        handler = ErrorHandler(debug=False)
        err = APIError("test", status_code=418)
        assert handler._get_status_code(err) == 418

    def test_status_code_for_validation_error(self):
        """Pydantic ValidationError maps to 422."""
        handler = ErrorHandler()
        from pydantic import BaseModel, ValidationError

        class M(BaseModel):
            x: int

        try:
            M(x="not_int")  # type: ignore
        except ValidationError as e:
            assert handler._get_status_code(e) == 422

    def test_status_code_for_permission_error(self):
        """Python PermissionError maps to 403."""
        handler = ErrorHandler()
        assert handler._get_status_code(PermissionError("denied")) == 403

    def test_status_code_for_file_not_found(self):
        """FileNotFoundError maps to 404."""
        handler = ErrorHandler()
        assert handler._get_status_code(FileNotFoundError("missing")) == 404

    def test_status_code_for_key_error(self):
        """KeyError maps to 400."""
        handler = ErrorHandler()
        assert handler._get_status_code(KeyError("field")) == 400

    def test_status_code_for_attribute_error(self):
        """AttributeError maps to 400."""
        handler = ErrorHandler()
        assert handler._get_status_code(AttributeError("attr")) == 400

    def test_status_code_for_json_decode_error(self):
        """JSONDecodeError maps to 400."""
        handler = ErrorHandler()
        import json

        try:
            json.loads("{bad")
        except json.JSONDecodeError as e:
            assert handler._get_status_code(e) == 400

    def test_status_code_for_not_implemented(self):
        """NotImplementedError maps to 501."""
        handler = ErrorHandler()
        assert handler._get_status_code(NotImplementedError("todo")) == 501

    def test_status_code_default_500(self):
        """Unknown exceptions default to 500."""
        handler = ErrorHandler()
        assert handler._get_status_code(RuntimeError("boom")) == 500

    def test_get_error_code_from_exc_attribute(self):
        """ErrorHandler reads .code from exception when present."""
        handler = ErrorHandler()
        err = APIError("test", code="custom_code")
        assert handler._get_error_code(err) == "custom_code"

    def test_get_error_code_fallback(self):
        """ErrorHandler falls back to lowercased class name."""
        handler = ErrorHandler()
        assert handler._get_error_code(ValueError("x")) == "valueerror"
        assert handler._get_error_code(RuntimeError("x")) == "runtimeerror"

    def test_generate_suggestion_permission_error(self):
        """Suggestion for PermissionError."""
        handler = ErrorHandler()
        sugg = handler._generate_suggestion(PermissionError(), "PermissionError")
        assert "permissions" in sugg.lower()

    def test_generate_suggestion_key_error(self):
        """Suggestion for KeyError includes the missing key."""
        handler = ErrorHandler()
        sugg = handler._generate_suggestion(KeyError("username"), "KeyError")
        assert "username" in sugg

    def test_generate_suggestion_not_implemented(self):
        """Suggestion for NotImplementedError."""
        handler = ErrorHandler()
        sugg = handler._generate_suggestion(NotImplementedError(), "NotImplementedError")
        assert "not yet implemented" in sugg.lower()

    def test_generate_suggestion_default(self):
        """Default suggestion for unknown exceptions."""
        handler = ErrorHandler()
        sugg = handler._generate_suggestion(RuntimeError("boom"), "RuntimeError")
        assert "review" in sugg.lower() or "error message" in sugg.lower()

    def test_capture_exception_returns_error_detail(self):
        """capture_exception returns an ErrorDetail object."""
        handler = ErrorHandler(debug=False)
        try:
            raise ValueError("test capture")
        except ValueError as e:
            detail = handler.capture_exception(e)
            assert isinstance(detail, ErrorDetail)
            assert detail.message == "test capture"
            assert detail.error_type == "ValueError"
            assert detail.status_code == 500  # default for ValueError

    def test_capture_exception_with_request(self):
        """capture_exception includes request context."""
        handler = ErrorHandler(debug=False)
        rf = RequestFactory()
        request = rf.get("/api/test/?foo=bar")
        try:
            raise KeyError("field")
        except KeyError as e:
            detail = handler.capture_exception(e, request)
            assert "request" in detail.context
            assert detail.context["request"]["method"] == "GET"
            assert detail.context["request"]["path"] == "/api/test/"
            assert detail.context["request"]["query_params"]["foo"] == "bar"

    def test_capture_exception_with_json_body(self):
        """capture_exception parses JSON body from request."""
        handler = ErrorHandler(debug=False)
        rf = RequestFactory()
        request = rf.post(
            "/api/test/",
            data=json.dumps({"name": "test"}),
            content_type="application/json",
        )
        try:
            raise RuntimeError("parse")
        except RuntimeError as e:
            detail = handler.capture_exception(e, request)
            assert detail.context["request"]["body"] == {"name": "test"}

    def test_capture_exception_with_invalid_json_body(self):
        """capture_exception handles invalid JSON body gracefully."""
        handler = ErrorHandler(debug=False)
        rf = RequestFactory()
        request = rf.post(
            "/api/test/",
            data=b"not json",
            content_type="application/json",
        )
        try:
            raise RuntimeError("parse")
        except RuntimeError as e:
            detail = handler.capture_exception(e, request)
            assert detail.context["request"]["body"] == "Invalid JSON"

    def test_capture_exception_debug_includes_traceback(self):
        """In debug mode, capture_exception includes traceback."""
        handler = ErrorHandler(debug=True)
        try:
            raise RuntimeError("debug test")
        except RuntimeError as e:
            detail = handler.capture_exception(e)
            assert detail.traceback_str is not None
            assert "RuntimeError" in detail.traceback_str

    def test_capture_exception_production_excludes_traceback(self):
        """In production mode, capture_exception excludes traceback."""
        handler = ErrorHandler(debug=False)
        try:
            raise RuntimeError("prod test")
        except RuntimeError as e:
            detail = handler.capture_exception(e)
            assert detail.traceback_str is None

    def test_capture_exception_api_error_preserves_status(self):
        """capture_exception preserves APIError status_code."""
        handler = ErrorHandler(debug=False)
        try:
            raise APIError("test", status_code=409, code="conflict")
        except APIError as e:
            detail = handler.capture_exception(e)
            assert detail.status_code == 409
            assert detail.code == "conflict"


# ---------------------------------------------------------------------------
# ErrorMiddleware
# ---------------------------------------------------------------------------


class TestErrorMiddleware:
    """Tests for the ErrorMiddleware class."""

    def _make_middleware(self, debug: bool = False):
        """Create an ErrorMiddleware with a mock get_response."""
        get_response = MagicMock(return_value=JsonResponse({"ok": True}))
        env_val = "true" if debug else "false"
        with patch.dict(os.environ, {"DJANGO_DEBUG": env_val}):
            mw = ErrorMiddleware(get_response)
        return mw

    def test_normal_call_passes_through(self):
        """ErrorMiddleware passes through normal requests."""
        mw = self._make_middleware()
        rf = RequestFactory()
        request = rf.get("/test/")
        resp = mw(request)
        assert resp.status_code == 200

    def test_process_exception_returns_json(self):
        """process_exception returns a JsonResponse."""
        mw = self._make_middleware(debug=False)
        rf = RequestFactory()
        request = rf.get("/test/")
        try:
            raise ValueError("middleware test")
        except ValueError as e:
            resp = mw.process_exception(request, e)
            assert isinstance(resp, JsonResponse)
            body = json.loads(resp.content)
            assert body["message"] == "middleware test"
            assert body["error_type"] == "ValueError"

    def test_process_exception_production_no_traceback(self):
        """In production, process_exception excludes traceback."""
        mw = self._make_middleware(debug=False)
        rf = RequestFactory()
        request = rf.get("/test/")
        try:
            raise RuntimeError("prod")
        except RuntimeError as e:
            resp = mw.process_exception(request, e)
            body = json.loads(resp.content)
            assert "traceback" not in body

    def test_process_exception_debug_includes_traceback(self):
        """In debug mode, process_exception includes traceback."""
        mw = self._make_middleware(debug=True)
        rf = RequestFactory()
        request = rf.get("/test/")
        try:
            raise RuntimeError("debug")
        except RuntimeError as e:
            resp = mw.process_exception(request, e)
            body = json.loads(resp.content)
            assert "traceback" in body

    def test_process_exception_api_error_status(self):
        """process_exception uses APIError's status code."""
        mw = self._make_middleware()
        rf = RequestFactory()
        request = rf.get("/test/")
        try:
            raise NotFoundAPIError(resource_type="Item", resource_id="99")
        except NotFoundAPIError as e:
            resp = mw.process_exception(request, e)
            assert resp.status_code == 404

    def test_sync_and_async_capable(self):
        """ErrorMiddleware declares both sync and async support."""
        assert ErrorMiddleware.sync_capable is True
        assert ErrorMiddleware.async_capable is True


# ---------------------------------------------------------------------------
# handle_exceptions decorator
# ---------------------------------------------------------------------------


class TestHandleExceptionsDecorator:
    """Tests for the handle_exceptions decorator."""

    @pytest.mark.asyncio
    async def test_async_function_success(self):
        """handle_exceptions passes through successful async functions."""

        @handle_exceptions
        async def my_view(request):
            return JsonResponse({"ok": True})

        rf = RequestFactory()
        request = rf.get("/test/")
        resp = await my_view(request)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_async_function_catches_error(self):
        """handle_exceptions catches errors from async functions."""

        @handle_exceptions
        async def my_view(request):
            raise ValueError("async boom")

        rf = RequestFactory()
        request = rf.get("/test/")
        resp = await my_view(request)
        assert isinstance(resp, JsonResponse)
        body = json.loads(resp.content)
        assert body["message"] == "async boom"

    @pytest.mark.asyncio
    async def test_sync_function_through_async_wrapper(self):
        """handle_exceptions wraps sync functions in async wrapper."""

        @handle_exceptions
        def my_view(request):
            return JsonResponse({"ok": True})

        rf = RequestFactory()
        request = rf.get("/test/")
        resp = await my_view(request)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sync_function_error(self):
        """handle_exceptions catches errors from sync functions."""

        @handle_exceptions
        def my_view(request):
            raise RuntimeError("sync boom")

        rf = RequestFactory()
        request = rf.get("/test/")
        resp = await my_view(request)
        body = json.loads(resp.content)
        assert body["message"] == "sync boom"

    @pytest.mark.asyncio
    async def test_api_error_status_preserved(self):
        """handle_exceptions preserves APIError status code."""

        @handle_exceptions
        async def my_view(request):
            raise AuthenticationAPIError()

        rf = RequestFactory()
        request = rf.get("/test/")
        resp = await my_view(request)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestErrorEdgeCases:
    """Edge case tests for the error module."""

    def test_api_error_empty_context_default(self):
        """APIError with context=None defaults to empty dict."""
        err = APIError("test", context=None)
        assert err.context == {}

    def test_validation_error_empty_errors_default(self):
        """ValidationAPIError with errors=None defaults to empty list."""
        err = ValidationAPIError(errors=None)
        assert err.errors == []

    def test_rate_limit_suggestion_without_retry_after(self):
        """RateLimitAPIError suggestion says 'some time' when no retry_after."""
        err = RateLimitAPIError()
        assert "some time" in err.suggestion

    def test_rate_limit_suggestion_with_retry_after(self):
        """RateLimitAPIError suggestion includes the retry_after value."""
        err = RateLimitAPIError(retry_after=120)
        assert "120" in err.suggestion

    def test_not_found_resource_id_without_type(self):
        """NotFoundAPIError with resource_id but no resource_type uses 'Resource'."""
        err = NotFoundAPIError(resource_id="123")
        assert "Resource" in err.message
        assert "123" in err.message

    def test_error_detail_context_defaults_to_empty_dict(self):
        """ErrorDetail context=None becomes empty dict."""
        detail = ErrorDetail(message="err", error_type="E", context=None)
        assert detail.context == {}

    def test_error_handler_get_code_snippet_nonexistent_file(self):
        """_get_code_snippet returns None for non-existent files."""
        handler = ErrorHandler(debug=True)
        result = handler._get_code_snippet("/nonexistent/file.py", 1)
        assert result is None
