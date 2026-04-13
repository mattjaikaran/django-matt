"""Tests for the LLM-optimized error messages system."""

from __future__ import annotations

import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

import django

django.setup()

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.test import RequestFactory

import pytest

from django_matt.errors import (
    ErrorEnhancementMiddleware,
    StructuredError,
    SuggestionEngine,
    format_for_api,
    format_for_human,
    format_for_llm,
    format_for_log,
)

# ---------------------------------------------------------------------------
# StructuredError creation and serialization
# ---------------------------------------------------------------------------


class TestStructuredError:
    def test_create_basic(self) -> None:
        err = StructuredError(code="TEST_ERROR", message="Something broke")
        assert err.code == "TEST_ERROR"
        assert err.message == "Something broke"
        assert err.status_code == 500
        assert err.fix_suggestions == []
        assert err.context == {}
        assert err.timestamp  # auto-generated

    def test_create_full(self) -> None:
        err = StructuredError(
            code="AUTH_TOKEN_EXPIRED",
            message="JWT token has expired",
            status_code=401,
            detail="The token was issued 2 hours ago and has a 1-hour TTL.",
            fix_suggestions=["Refresh the token", "Re-authenticate"],
            docs_url="https://django-matt.dev/docs/auth/jwt",
            context={"token_age_seconds": 7200, "ttl_seconds": 3600},
            related_settings=["MATT_AUTH"],
            search_terms=["JWT expired", "token refresh"],
        )
        assert err.status_code == 401
        assert len(err.fix_suggestions) == 2
        assert err.context["token_age_seconds"] == 7200

    def test_to_dict_production(self) -> None:
        err = StructuredError(
            code="DB_ERROR",
            message="Connection refused",
            traceback_str="Traceback ...",
            exception_type="OperationalError",
        )
        d = err.to_dict(include_debug=False)
        assert d["code"] == "DB_ERROR"
        assert "traceback" not in d
        assert "exception_type" not in d

    def test_to_dict_debug(self) -> None:
        err = StructuredError(
            code="DB_ERROR",
            message="Connection refused",
            traceback_str="Traceback ...",
            exception_type="OperationalError",
        )
        d = err.to_dict(include_debug=True)
        assert d["traceback"] == "Traceback ..."
        assert d["exception_type"] == "OperationalError"

    def test_to_json(self) -> None:
        err = StructuredError(code="TEST", message="test")
        raw = err.to_json()
        assert isinstance(raw, bytes)
        parsed = json.loads(raw)
        assert parsed["code"] == "TEST"

    def test_to_json_str(self) -> None:
        err = StructuredError(code="TEST", message="test")
        s = err.to_json_str()
        assert isinstance(s, str)
        assert '"code": "TEST"' in s


# ---------------------------------------------------------------------------
# SuggestionEngine
# ---------------------------------------------------------------------------


class TestSuggestionEngine:
    def test_improperly_configured(self) -> None:
        engine = SuggestionEngine()
        exc = ImproperlyConfigured("INSTALLED_APPS is missing 'myapp'")
        result = engine.get_suggestions(exc)
        assert result.code == "IMPROPERLY_CONFIGURED"
        assert len(result.fix_suggestions) >= 1
        assert "INSTALLED_APPS" in result.related_settings

    def test_permission_denied(self) -> None:
        engine = SuggestionEngine()
        exc = PermissionDenied("You do not have permission")
        result = engine.get_suggestions(exc)
        assert result.code == "PERMISSION_DENIED"
        assert any("permission" in s.lower() for s in result.fix_suggestions)

    def test_module_not_found(self) -> None:
        engine = SuggestionEngine()
        exc = ModuleNotFoundError("No module named 'nonexistent'")
        result = engine.get_suggestions(exc)
        assert result.code == "MODULE_NOT_FOUND"
        assert any("uv add" in s for s in result.fix_suggestions)

    def test_key_error(self) -> None:
        engine = SuggestionEngine()
        exc = KeyError("missing_key")
        result = engine.get_suggestions(exc)
        assert result.code == "KEY_ERROR"
        assert any(".get(" in s for s in result.fix_suggestions)

    def test_attribute_error_fuzzy(self) -> None:
        engine = SuggestionEngine()
        exc = AttributeError("'str' object has no attribute 'uppr'")
        result = engine.get_suggestions(exc)
        assert result.code == "ATTRIBUTE_ERROR"
        # should suggest 'upper' via fuzzy match
        assert any("upper" in s for s in result.fix_suggestions)

    def test_attribute_error_no_match(self) -> None:
        engine = SuggestionEngine()
        exc = AttributeError("something went wrong")
        result = engine.get_suggestions(exc)
        assert result.code == "ATTRIBUTE_ERROR"
        assert len(result.fix_suggestions) >= 1

    def test_timeout_error(self) -> None:
        engine = SuggestionEngine()
        exc = TimeoutError("timed out")
        result = engine.get_suggestions(exc)
        assert result.code == "TIMEOUT_ERROR"

    def test_connection_error(self) -> None:
        engine = SuggestionEngine()
        exc = ConnectionError("refused")
        result = engine.get_suggestions(exc)
        assert result.code == "CONNECTION_ERROR"

    def test_type_error(self) -> None:
        engine = SuggestionEngine()
        exc = TypeError("expected str got int")
        result = engine.get_suggestions(exc)
        assert result.code == "TYPE_ERROR"

    def test_not_implemented_error(self) -> None:
        engine = SuggestionEngine()
        exc = NotImplementedError("not yet")
        result = engine.get_suggestions(exc)
        assert result.code == "NOT_IMPLEMENTED"

    def test_fallback_unknown_exception(self) -> None:
        engine = SuggestionEngine()

        class WeirdError(Exception):
            pass

        exc = WeirdError("something")
        result = engine.get_suggestions(exc)
        assert result.message == "something"
        assert result.exception_type.endswith("WeirdError")

    def test_custom_registration(self) -> None:
        engine = SuggestionEngine()
        engine.register(
            RuntimeError,
            message_pattern=r"celery.*not running",
            suggestions=["Start Celery with: celery -A config worker -l info"],
            code="CELERY_DOWN",
            priority=100,
        )
        exc = RuntimeError("celery broker not running")
        result = engine.get_suggestions(exc)
        assert result.code == "CELERY_DOWN"
        assert "Start Celery" in result.fix_suggestions[0]

    def test_custom_matcher(self) -> None:
        engine = SuggestionEngine()

        def my_matcher(exc: Exception) -> StructuredError | None:
            if isinstance(exc, ValueError) and "custom" in str(exc):
                return StructuredError(
                    code="CUSTOM_VALUE",
                    message=str(exc),
                    fix_suggestions=["Custom fix"],
                )
            return None

        engine.register_matcher(my_matcher)
        exc = ValueError("custom value issue")
        result = engine.get_suggestions(exc)
        assert result.code == "CUSTOM_VALUE"

    def test_custom_matcher_passthrough(self) -> None:
        engine = SuggestionEngine()

        def my_matcher(exc: Exception) -> StructuredError | None:
            return None  # always pass

        engine.register_matcher(my_matcher)
        exc = KeyError("x")
        result = engine.get_suggestions(exc)
        # falls through to built-in patterns
        assert result.code == "KEY_ERROR"

    def test_validation_error(self) -> None:
        from pydantic import BaseModel, ValidationError

        class MyModel(BaseModel):
            name: str
            age: int

        engine = SuggestionEngine()
        try:
            MyModel(name=123, age="not_a_number")  # type: ignore[arg-type]
        except ValidationError as exc:
            result = engine.get_suggestions(exc)
            assert result.code == "VALIDATION_ERROR"
            assert any("schema" in s.lower() for s in result.fix_suggestions)

    def test_priority_ordering(self) -> None:
        engine = SuggestionEngine()
        # register low-priority generic match
        engine.register(
            RuntimeError,
            suggestions=["Generic fix"],
            code="GENERIC",
            priority=0,
        )
        # register high-priority specific match
        engine.register(
            RuntimeError,
            message_pattern=r"specific",
            suggestions=["Specific fix"],
            code="SPECIFIC",
            priority=100,
        )
        exc = RuntimeError("a specific error")
        result = engine.get_suggestions(exc)
        assert result.code == "SPECIFIC"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class TestFormatters:
    @pytest.fixture()
    def sample_error(self) -> StructuredError:
        return StructuredError(
            code="AUTH_TOKEN_EXPIRED",
            message="JWT token has expired",
            status_code=401,
            detail="Token TTL exceeded.",
            fix_suggestions=["Refresh the token", "Re-authenticate"],
            docs_url="https://django-matt.dev/docs/auth/jwt",
            context={"token_age": 7200},
            related_settings=["MATT_AUTH", "SECRET_KEY"],
            search_terms=["JWT expired"],
            exception_type="AuthenticationAPIError",
            traceback_str="Traceback (most recent call last):\n  File ...\nError",
        )

    def test_format_for_llm(self, sample_error: StructuredError) -> None:
        output = format_for_llm(sample_error)
        assert "# Error: AUTH_TOKEN_EXPIRED" in output
        assert "## Fix Suggestions" in output
        assert "Refresh the token" in output
        assert "## Context" in output
        assert "## Related Settings" in output
        assert "`MATT_AUTH`" in output
        assert "## Search Terms" in output
        assert "## Traceback" in output
        assert "## Documentation" in output

    def test_format_for_llm_minimal(self) -> None:
        err = StructuredError(code="BARE", message="bare error")
        output = format_for_llm(err)
        assert "# Error: BARE" in output
        assert "## Fix Suggestions" not in output

    def test_format_for_human_color(self, sample_error: StructuredError) -> None:
        output = format_for_human(sample_error, color=True)
        assert "\033[91m" in output  # red
        assert "AUTH_TOKEN_EXPIRED" in output
        assert "Suggestions:" in output

    def test_format_for_human_no_color(self, sample_error: StructuredError) -> None:
        output = format_for_human(sample_error, color=False)
        assert "\033[" not in output
        assert "AUTH_TOKEN_EXPIRED" in output

    def test_format_for_api_production(self, sample_error: StructuredError) -> None:
        result = format_for_api(sample_error, include_debug=False)
        assert result["status"] == 401
        assert result["code"] == "AUTH_TOKEN_EXPIRED"
        assert result["hint"] == "Refresh the token"
        assert "traceback" not in result
        assert "exception_type" not in result
        assert result["extra"] is None

    def test_format_for_api_debug(self, sample_error: StructuredError) -> None:
        result = format_for_api(sample_error, include_debug=True)
        assert result["traceback"] is not None
        assert result["exception_type"] == "AuthenticationAPIError"
        assert result["related_settings"] == ["MATT_AUTH", "SECRET_KEY"]
        assert result["fix_suggestions"] == ["Refresh the token", "Re-authenticate"]

    def test_format_for_log(self, sample_error: StructuredError) -> None:
        result = format_for_log(sample_error)
        assert result["level"] == "error"
        assert result["code"] == "AUTH_TOKEN_EXPIRED"
        assert result["status_code"] == 401
        assert result["timestamp"] is not None
        assert result["exception_type"] == "AuthenticationAPIError"
        assert result["traceback"] is not None


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class TestErrorEnhancementMiddleware:
    def _make_request(self) -> object:
        factory = RequestFactory()
        return factory.get("/api/users/")

    def test_middleware_passes_normal_response(self) -> None:
        from django.http import HttpResponse

        def get_response(request: object) -> HttpResponse:
            return HttpResponse("OK")

        mw = ErrorEnhancementMiddleware(get_response)
        request = self._make_request()
        response = mw(request)
        assert response.status_code == 200

    def test_middleware_catches_exception_debug(self, settings: object) -> None:
        settings.DEBUG = True  # type: ignore[attr-defined]

        def get_response(request: object) -> None:
            raise ValueError("bad value")

        mw = ErrorEnhancementMiddleware(get_response)
        request = self._make_request()
        response = mw(request)
        assert response.status_code == 500
        assert response["Content-Type"] == "application/json"
        import orjson

        body = orjson.loads(response.content)
        assert body["code"] is not None
        # debug mode includes traceback
        assert "traceback" in body

    def test_middleware_catches_exception_production(self, settings: object) -> None:
        settings.DEBUG = False  # type: ignore[attr-defined]

        def get_response(request: object) -> None:
            raise KeyError("missing")

        mw = ErrorEnhancementMiddleware(get_response)
        request = self._make_request()
        response = mw(request)
        assert response.status_code == 400
        import orjson

        body = orjson.loads(response.content)
        assert "traceback" not in body
        assert "related_settings" not in body

    def test_middleware_max_suggestions(self, settings: object) -> None:
        settings.DEBUG = True  # type: ignore[attr-defined]
        settings.MATT_ERRORS = {"enhanced": True, "max_suggestions": 1}  # type: ignore[attr-defined]

        def get_response(request: object) -> None:
            raise ImproperlyConfigured("bad config")

        mw = ErrorEnhancementMiddleware(get_response)
        request = self._make_request()
        response = mw(request)
        import orjson

        body = orjson.loads(response.content)
        # hint is always a single string in API format
        assert isinstance(body.get("hint"), str)

    @pytest.mark.asyncio
    async def test_middleware_async(self, settings: object) -> None:
        settings.DEBUG = True  # type: ignore[attr-defined]

        async def get_response(request: object) -> None:
            raise TypeError("async error")

        mw = ErrorEnhancementMiddleware(get_response)
        request = self._make_request()
        response = await mw.__acall__(request)
        assert response.status_code == 500
        import orjson

        body = orjson.loads(response.content)
        assert body["code"] is not None

    def test_middleware_disabled(self, settings: object) -> None:
        settings.MATT_ERRORS = {"enhanced": False}  # type: ignore[attr-defined]

        def get_response(request: object) -> None:
            raise RuntimeError("should re-raise")

        mw = ErrorEnhancementMiddleware(get_response)
        request = self._make_request()
        with pytest.raises(RuntimeError, match="should re-raise"):
            mw(request)


# ---------------------------------------------------------------------------
# Dev overlay (basic smoke test)
# ---------------------------------------------------------------------------


class TestDevOverlay:
    def test_render_plain(self) -> None:
        from django_matt.errors.dev_overlay import render_dev_error

        err = StructuredError(
            code="TEST",
            message="test error",
            fix_suggestions=["Fix it"],
        )
        output = render_dev_error(err, use_rich=False)
        assert "TEST" in output
        assert "Fix it" in output

    def test_print_dev_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        from django_matt.errors.dev_overlay import print_dev_error

        err = StructuredError(code="PRINT_TEST", message="printed error")
        print_dev_error(err)
        captured = capsys.readouterr()
        assert "PRINT_TEST" in captured.err
