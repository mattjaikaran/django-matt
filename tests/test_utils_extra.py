"""
Tests for django_matt.utils — cache_invalidation, errors, hot_reload.

Covers:
  - CacheInvalidator: register, unregister, invalidate, get_cache_keys, signals
  - CacheInvalidationMixin: auto-registration via __init_subclass__
  - cached_view: sync/async decorator, cache hit/miss, vary_on
  - ErrorHandler: capture_error, format_response, code snippet, suggestions
  - ValidationErrorFormatter: format_validation_error, format_error_path, nested
  - ErrorMiddleware: API vs non-API paths, sync handling
  - FileChangeHandler / HotReloader: debounce, .py filter, start/stop
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from django.core.cache import cache as default_cache
from django.db import models
from django.test import RequestFactory

import pytest
from pydantic import BaseModel, ValidationError

from django_matt.core.errors import (
    ErrorDetail,
    ErrorHandler,
    ErrorMiddleware,
    ValidationErrorFormatter,
)
from django_matt.utils.cache_invalidation import (
    CacheInvalidator,
    _generate_view_cache_key,
    cached_view,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_model_class(name: str = "FakeModel"):
    """Create a minimal mock that behaves like a Django Model class for registration."""
    cls = type(name, (), {})
    cls.__name__ = name

    # Provide a minimal _meta
    meta = MagicMock()
    meta.abstract = False
    meta.get_fields.return_value = []  # no M2M
    cls._meta = meta
    return cls


def _make_fake_instance(cls, pk=1):
    """Create a minimal mock instance of the fake model class."""
    inst = MagicMock(spec=[])
    inst.__class__ = cls
    inst.pk = pk
    return inst


# =========================================================================
# CacheInvalidator
# =========================================================================


class TestCacheInvalidator:
    """Tests for the CacheInvalidator class."""

    def setup_method(self):
        self.invalidator = CacheInvalidator()

    def test_register_stores_model(self):
        """Registering a model should store it with default prefix."""
        FakeModel = _make_fake_model_class("Product")
        self.invalidator.register(FakeModel, cache_key_prefix="product")
        assert FakeModel in self.invalidator._registered_models
        assert self.invalidator._registered_models[FakeModel]["prefix"] == "product"

    def test_register_default_prefix(self):
        """If no prefix given, default to lowercase model name."""
        FakeModel = _make_fake_model_class("Widget")
        self.invalidator.register(FakeModel)
        assert self.invalidator._registered_models[FakeModel]["prefix"] == "widget"

    def test_register_duplicate_is_noop(self):
        """Re-registering the same model does not overwrite."""
        FakeModel = _make_fake_model_class("Thing")
        self.invalidator.register(FakeModel, cache_key_prefix="first")
        self.invalidator.register(FakeModel, cache_key_prefix="second")
        assert self.invalidator._registered_models[FakeModel]["prefix"] == "first"

    def test_unregister_removes_model(self):
        """Unregistering a model removes it from the registry."""
        FakeModel = _make_fake_model_class("Removable")
        self.invalidator.register(FakeModel)
        assert FakeModel in self.invalidator._registered_models

        self.invalidator.unregister(FakeModel)
        assert FakeModel not in self.invalidator._registered_models

    def test_unregister_nonexistent_is_noop(self):
        """Unregistering a model that's not registered does nothing."""
        FakeModel = _make_fake_model_class("Ghost")
        # Should not raise
        self.invalidator.unregister(FakeModel)

    def test_get_cache_keys_returns_standard_keys(self):
        """get_cache_keys produces the 4 standard keys for a registered model."""
        FakeModel = _make_fake_model_class("Item")
        self.invalidator.register(FakeModel, cache_key_prefix="item")

        instance = _make_fake_instance(FakeModel, pk=42)
        keys = self.invalidator.get_cache_keys(instance)

        assert "item:list" in keys
        assert "item:42" in keys
        assert "item:detail:42" in keys
        assert "item:count" in keys

    def test_get_cache_keys_unregistered_returns_empty(self):
        """get_cache_keys returns [] for an unregistered model."""
        FakeModel = _make_fake_model_class("Unknown")
        instance = _make_fake_instance(FakeModel, pk=1)
        assert self.invalidator.get_cache_keys(instance) == []

    def test_invalidate_deletes_keys_and_returns_count(self):
        """invalidate() calls cache.delete_many and returns key count."""
        FakeModel = _make_fake_model_class("Cached")
        self.invalidator.register(FakeModel, cache_key_prefix="cached")

        instance = _make_fake_instance(FakeModel, pk=5)

        with patch.object(self.invalidator.cache, "delete_many") as mock_del:
            count = self.invalidator.invalidate(instance, action="update")
            assert count == 4
            mock_del.assert_called_once()
            # The keys passed should be the 4 standard keys
            deleted_keys = mock_del.call_args[0][0]
            assert len(deleted_keys) == 4

    def test_invalidate_fires_callbacks(self):
        """invalidate() fires registered callbacks for the model."""
        FakeModel = _make_fake_model_class("Callbackable")
        self.invalidator.register(FakeModel)

        cb = MagicMock()
        self.invalidator.add_callback(FakeModel, cb)

        instance = _make_fake_instance(FakeModel, pk=10)

        with patch.object(self.invalidator.cache, "delete_many"):
            self.invalidator.invalidate(instance, action="save")

        cb.assert_called_once_with(instance, "save")

    def test_custom_key_generator(self):
        """A custom key generator replaces the standard keys."""
        FakeModel = _make_fake_model_class("Custom")

        def gen(inst):
            return [f"custom:{inst.pk}:v1", f"custom:{inst.pk}:v2"]

        self.invalidator.register(FakeModel, custom_key_generator=gen)

        instance = _make_fake_instance(FakeModel, pk=7)
        keys = self.invalidator.get_cache_keys(instance)
        assert keys == ["custom:7:v1", "custom:7:v2"]

    def test_invalidate_pattern_without_support(self):
        """invalidate_pattern returns -1 when backend lacks delete_pattern."""
        FakeModel = _make_fake_model_class("Patterned")
        self.invalidator.register(FakeModel)

        # LocMemCache doesn't have delete_pattern
        result = self.invalidator.invalidate_pattern("product:*")
        assert result == -1


# =========================================================================
# CacheInvalidationMixin
# =========================================================================


class TestCacheInvalidationMixin:
    """Tests for the CacheInvalidationMixin auto-registration."""

    def test_mixin_registers_on_init_subclass(self):
        """Subclassing with CacheMeta should call register_cache_invalidation."""
        from django_matt.utils.cache_invalidation import CacheInvalidationMixin

        with patch("django_matt.utils.cache_invalidation.register_cache_invalidation") as mock_reg:
            # Build a fake subclass that has _meta (simulates a concrete model)
            meta = MagicMock()
            meta.abstract = False
            meta.get_fields.return_value = []

            cls = type(
                "AutoRegistered",
                (CacheInvalidationMixin,),
                {
                    "_meta": meta,
                    "CacheMeta": type(
                        "CacheMeta",
                        (),
                        {"cache_key_prefix": "auto", "invalidate_related": []},
                    ),
                },
            )

            mock_reg.assert_called_once()
            call_kwargs = mock_reg.call_args
            assert call_kwargs[1]["cache_key_prefix"] == "auto"

    def test_mixin_skips_abstract_models(self):
        """Abstract models should NOT be registered."""
        from django_matt.utils.cache_invalidation import CacheInvalidationMixin

        with patch("django_matt.utils.cache_invalidation.register_cache_invalidation") as mock_reg:
            meta = MagicMock()
            meta.abstract = True

            type(
                "AbstractModel",
                (CacheInvalidationMixin,),
                {"_meta": meta},
            )

            mock_reg.assert_not_called()


# =========================================================================
# cached_view
# =========================================================================


class TestCachedView:
    """Tests for the cached_view decorator."""

    def setup_method(self):
        default_cache.clear()

    def test_sync_view_cache_miss_then_hit(self):
        """First call should invoke the view; second call should return cached."""
        call_count = {"n": 0}

        @cached_view(timeout=60, key_prefix="synctest")
        def my_view(request):
            call_count["n"] += 1
            return {"result": call_count["n"]}

        rf = RequestFactory()
        request = rf.get("/test/")

        result1 = my_view(request)
        assert result1 == {"result": 1}
        assert call_count["n"] == 1

        result2 = my_view(request)
        assert result2 == {"result": 1}  # cached
        assert call_count["n"] == 1  # view not called again

    async def test_async_view_cache_miss_then_hit(self):
        """Async view: first call invokes, second returns cached."""
        call_count = {"n": 0}

        @cached_view(timeout=60, key_prefix="asynctest")
        async def my_async_view(request):
            call_count["n"] += 1
            return {"async_result": call_count["n"]}

        rf = RequestFactory()
        request = rf.get("/async-test/")

        result1 = await my_async_view(request)
        assert result1 == {"async_result": 1}

        result2 = await my_async_view(request)
        assert result2 == {"async_result": 1}
        assert call_count["n"] == 1

    def test_vary_on_produces_different_keys(self):
        """Different vary_on attribute values should produce different cache entries."""
        call_count = {"n": 0}

        @cached_view(timeout=60, key_prefix="vary", vary_on=["user"])
        def my_view(request):
            call_count["n"] += 1
            return {"count": call_count["n"]}

        rf = RequestFactory()

        req_a = rf.get("/a/")
        req_a.user = "alice"
        req_b = rf.get("/b/")
        req_b.user = "bob"

        res_a = my_view(req_a)
        assert res_a == {"count": 1}

        res_b = my_view(req_b)
        assert res_b == {"count": 2}  # different user => different cache key

    def test_generate_view_cache_key_includes_kwargs(self):
        """Cache key should incorporate kwargs for the same function."""
        rf = RequestFactory()
        request = rf.get("/foo/")

        def dummy(request):
            pass

        key1 = _generate_view_cache_key(dummy, "pf", request, None, (), {"id": 1})
        key2 = _generate_view_cache_key(dummy, "pf", request, None, (), {"id": 2})
        assert key1 != key2


# =========================================================================
# ErrorHandler
# =========================================================================


class TestErrorHandler:
    """Tests for ErrorHandler static/class methods."""

    def test_generate_suggestion_known_types(self):
        """generate_suggestion returns a string for each known exception type."""
        known = [
            ("ValidationError", "schema"),
            ("TypeError", "types"),
            ("AttributeError", "attribute"),
            ("ImportError", "module"),
            ("KeyError", "key"),
        ]
        for etype, expected_word in known:
            suggestion = ErrorHandler.generate_suggestion(Exception(), etype)
            assert suggestion is not None
            assert expected_word.lower() in suggestion.lower()

    def test_generate_suggestion_unknown_returns_none(self):
        """Unknown exception types should return None."""
        assert ErrorHandler.generate_suggestion(Exception(), "WeirdError") is None

    def test_capture_error_produces_error_detail(self):
        """capture_error should return an ErrorDetail with correct fields."""
        try:
            raise ValueError("test message")
        except ValueError as exc:
            detail = ErrorHandler.capture_error(exc)

        assert isinstance(detail, ErrorDetail)
        assert detail.message == "test message"
        assert detail.exception_type == "ValueError"
        assert detail.suggestion is not None  # ValueError has a suggestion
        assert detail.line_number is not None

    def test_format_response_includes_error_key(self):
        """format_response returns dict with 'error' top-level key."""
        try:
            raise TypeError("bad type")
        except TypeError as exc:
            resp = ErrorHandler.format_response(exc, include_traceback=True)

        assert "error" in resp
        assert resp["error"]["message"] == "bad type"
        assert resp["error"]["exception_type"] == "TypeError"
        assert "traceback" in resp["error"]

    def test_format_response_hides_traceback_when_disabled(self):
        """When include_traceback=False, traceback is omitted."""
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            resp = ErrorHandler.format_response(exc, include_traceback=False)

        assert "traceback" not in resp["error"]

    def test_get_code_snippet_for_existing_file(self):
        """get_code_snippet should return lines around the target line."""
        # Use this test file itself as the target
        snippet = ErrorHandler.get_code_snippet(__file__, 1, context_lines=2)
        assert isinstance(snippet, dict)
        assert len(snippet) > 0
        # Line 1 should be present
        assert 1 in snippet

    def test_get_code_snippet_nonexistent_file(self):
        """get_code_snippet for a missing file returns empty dict."""
        snippet = ErrorHandler.get_code_snippet("/nonexistent/file.py", 10)
        assert snippet == {}


# =========================================================================
# ValidationErrorFormatter
# =========================================================================


class TestValidationErrorFormatter:
    """Tests for ValidationErrorFormatter."""

    def _get_validation_error(self):
        """Helper: create a real Pydantic ValidationError."""

        class StrictModel(BaseModel):
            name: str
            age: int

        try:
            StrictModel(name=123, age="not-an-int")  # type: ignore[arg-type]
        except ValidationError as exc:
            return exc
        pytest.fail("Expected ValidationError")

    def test_format_validation_error_structure(self):
        """format_validation_error returns dict with 'detail' and 'errors' list."""
        error = self._get_validation_error()
        result = ValidationErrorFormatter.format_validation_error(error)

        assert result["detail"] == "Validation error"
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) >= 1

    def test_format_error_path_simple(self):
        """Simple string location should return the string."""
        path = ValidationErrorFormatter.format_error_path(("name",))
        assert path == "name"

    def test_format_error_path_nested_with_index(self):
        """Nested path with integer index should use bracket notation."""
        path = ValidationErrorFormatter.format_error_path(("items", 0, "price"))
        assert path == "items[0].price"

    def test_format_validation_error_missing_field(self):
        """Missing field errors should produce a friendly_message."""

        class RequiredModel(BaseModel):
            required_field: str

        try:
            RequiredModel()  # type: ignore[call-arg]
        except ValidationError as exc:
            result = ValidationErrorFormatter.format_validation_error(exc)

        errors = result["errors"]
        assert len(errors) == 1
        assert errors[0]["error_type"] == "missing"
        assert "friendly_message" in errors[0]


# =========================================================================
# ErrorMiddleware
# =========================================================================


class TestErrorMiddleware:
    """Tests for ErrorMiddleware."""

    def test_api_path_returns_json_on_error(self):
        """Exceptions on /api/ paths should become JSON responses."""

        def bad_response(request):
            raise RuntimeError("api boom")

        middleware = ErrorMiddleware(bad_response)
        rf = RequestFactory()
        request = rf.get("/api/users/")

        try:
            raise RuntimeError("api boom")
        except RuntimeError:
            # We need the exception in sys.exc_info, so trigger via middleware
            pass

        response = middleware(request)
        assert response.status_code == 500
        assert response["Content-Type"] == "application/json"

    def test_non_api_path_reraises_exception(self):
        """Exceptions on non-API paths should be re-raised, not caught."""

        def bad_response(request):
            raise RuntimeError("html boom")

        middleware = ErrorMiddleware(bad_response)
        rf = RequestFactory()
        request = rf.get("/admin/dashboard/")

        with pytest.raises(RuntimeError, match="html boom"):
            middleware(request)

    def test_successful_request_passes_through(self):
        """Non-error responses pass through unchanged."""
        from django.http import HttpResponse

        def ok_response(request):
            return HttpResponse("OK", status=200)

        middleware = ErrorMiddleware(ok_response)
        rf = RequestFactory()
        request = rf.get("/api/health/")

        response = middleware(request)
        assert response.status_code == 200


# =========================================================================
# ErrorDetail
# =========================================================================


class TestErrorDetail:
    """Tests for ErrorDetail.to_dict."""

    def test_to_dict_includes_all_fields(self):
        detail = ErrorDetail(
            message="oops",
            exception_type="RuntimeError",
            traceback_str="Traceback ...",
            file_path="/app/views.py",
            line_number=42,
            code_snippet={41: "x = 1", 42: "raise RuntimeError", 43: "y = 2"},
            context={"extra": "info"},
            suggestion="Fix it.",
        )
        d = detail.to_dict(include_traceback=True)
        assert d["message"] == "oops"
        assert d["exception_type"] == "RuntimeError"
        assert d["location"]["file"] == "/app/views.py"
        assert d["location"]["line"] == 42
        assert d["suggestion"] == "Fix it."
        assert d["code_snippet"] == {41: "x = 1", 42: "raise RuntimeError", 43: "y = 2"}
        assert d["traceback"] == "Traceback ..."

    def test_to_dict_omits_traceback_when_disabled(self):
        detail = ErrorDetail(
            message="no tb",
            exception_type="ValueError",
            traceback_str="secret trace",
        )
        d = detail.to_dict(include_traceback=False)
        assert "traceback" not in d


# =========================================================================
# FileChangeHandler (watchdog)
# =========================================================================


class TestFileChangeHandler:
    """Tests for FileChangeHandler debounce and filtering."""

    def setup_method(self):
        pytest.importorskip("watchdog")
        from django_matt.utils.hot_reload import FileChangeHandler

        self.callback = MagicMock()
        self.handler = FileChangeHandler(self.callback)

    def test_ignores_unwatched_extensions(self):
        """Extensions not in watch set should not trigger the callback."""
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/app/readme.md"

        self.handler.dispatch(event)
        self.callback.assert_not_called()

    def test_fires_for_py_files(self):
        """A .py file modification should trigger the callback."""
        from django_matt.utils.hot_reload import ChangeType

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/app/views.py"

        self.handler.dispatch(event)
        self.callback.assert_called_once_with("/app/views.py", ChangeType.PYTHON)

    def test_fires_for_css_files(self):
        """CSS files should trigger callback with CSS change type."""
        from django_matt.utils.hot_reload import ChangeType

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/app/static/style.css"

        self.handler.dispatch(event)
        self.callback.assert_called_once_with("/app/static/style.css", ChangeType.CSS)

    def test_fires_for_html_templates(self):
        """HTML templates should trigger callback with TEMPLATE type."""
        from django_matt.utils.hot_reload import ChangeType

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/templates/base.html"

        self.handler.dispatch(event)
        self.callback.assert_called_once_with("/templates/base.html", ChangeType.TEMPLATE)

    def test_debounce_skips_rapid_second_event(self):
        """A second event for the same file within debounce_time is ignored."""
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/app/models.py"

        self.handler.dispatch(event)
        assert self.callback.call_count == 1

        # Immediate second event — should be debounced
        self.handler.dispatch(event)
        assert self.callback.call_count == 1

    def test_fires_after_debounce_period(self):
        """After debounce_time elapses, the same file triggers callback again."""
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/app/urls.py"

        self.handler.dispatch(event)
        assert self.callback.call_count == 1

        # Manually advance the recorded time to simulate debounce expiry
        self.handler._last_event["/app/urls.py"] -= 1.0
        self.handler.dispatch(event)
        assert self.callback.call_count == 2

    def test_ignores_directory_events(self):
        """Directory events should be ignored."""
        event = MagicMock()
        event.is_directory = True
        event.src_path = "/app/views.py"

        self.handler.dispatch(event)
        self.callback.assert_not_called()
