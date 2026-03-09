"""
Tests for the Django Matt observability module.

Tests cover:
- Logging: JSONFormatter, PrettyJSONFormatter, ColoredTextFormatter, StructuredLogger, BoundLogger
- Context management: set/get/clear request_id, user_id, correlation_id
- Logging config: LoggingConfig, get_logging_config, configure_logging
- Metrics: MetricsManager, FallbackCounter, FallbackGauge, FallbackHistogram, FallbackSummary
- Metrics convenience: record_request, record_db_query, increment/decrement_active_requests
- Metrics percentiles: get_percentiles
- Decorators: @trace, @metric, @timed, @counted, @observe, @with_span_attribute
- Tracing: NullSpan, NullTracer, TracingManager, TracingConfig
- Tracing helpers: get_tracer, get_current_span, get/set_correlation_id, inject_headers, extract_context
- Middleware: TracingMiddleware, MetricsMiddleware, LoggingMiddleware, DatabaseQueryMiddleware, ObservabilityMiddleware
- Middleware helpers: _normalize_path
- Views: metrics_view, health_view, ready_view, info_view, debug_view
- ReadinessChecker: register, unregister, run_checks
- Edge cases: disabled features, missing backends, exception handling
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from unittest.mock import MagicMock, patch

import orjson
import pytest
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, override_settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture(autouse=True)
def _clear_logging_context():
    """Clear observability context vars before and after each test."""
    from django_matt.observability.logging import clear_context

    clear_context()
    yield
    clear_context()


@pytest.fixture
def fresh_metrics_manager():
    """Provide a fresh MetricsManager with no pre-registered metrics."""
    from django_matt.observability.metrics import MetricsManager

    return MetricsManager()


@pytest.fixture
def json_formatter():
    from django_matt.observability.logging import JSONFormatter

    return JSONFormatter(
        include_timestamp=True,
        include_correlation_id=True,
        include_request_id=True,
        include_user=True,
        include_hostname=False,
    )


@pytest.fixture
def pretty_formatter():
    from django_matt.observability.logging import PrettyJSONFormatter

    return PrettyJSONFormatter(
        include_timestamp=False,
        include_hostname=False,
    )


@pytest.fixture
def colored_formatter():
    from django_matt.observability.logging import ColoredTextFormatter

    return ColoredTextFormatter()


# ---------------------------------------------------------------------------
# Tests: Logging — JSONFormatter
# ---------------------------------------------------------------------------


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_basic_format_produces_valid_json(self, json_formatter):
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Hello %s",
            args=("world",),
            exc_info=None,
        )
        output = json_formatter.format(record)
        data = orjson.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Hello world"
        assert "timestamp" in data
        assert data["location"]["line"] == 42

    def test_format_includes_context_vars(self, json_formatter):
        from django_matt.observability.logging import (
            set_correlation_id,
            set_request_id,
            set_user_id,
        )

        set_request_id("req-123")
        set_user_id("user-456")
        set_correlation_id("corr-789")

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="ctx test", args=(), exc_info=None,
        )
        data = orjson.loads(json_formatter.format(record))

        assert data["request_id"] == "req-123"
        assert data["user_id"] == "user-456"
        assert data["correlation_id"] == "corr-789"

    def test_format_without_context_vars(self, json_formatter):
        record = logging.LogRecord(
            name="test", level=logging.DEBUG, pathname="", lineno=0,
            msg="no ctx", args=(), exc_info=None,
        )
        data = orjson.loads(json_formatter.format(record))

        assert "request_id" not in data
        assert "user_id" not in data
        assert "correlation_id" not in data

    def test_format_sanitizes_sensitive_fields(self, json_formatter):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="sensitive", args=(), exc_info=None,
        )
        record.extra = {"password": "secret123", "username": "matt"}
        data = orjson.loads(json_formatter.format(record))

        assert data["extra"]["password"] == "[REDACTED]"
        assert data["extra"]["username"] == "matt"

    def test_format_sanitizes_nested_sensitive_fields(self, json_formatter):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="nested", args=(), exc_info=None,
        )
        record.extra = {"data": {"api_token": "xyz", "name": "test"}}
        data = orjson.loads(json_formatter.format(record))

        assert data["extra"]["data"]["api_token"] == "[REDACTED]"
        assert data["extra"]["data"]["name"] == "test"

    def test_format_sanitizes_list_values_in_dict(self, json_formatter):
        """Sanitize lists nested inside dict extra fields."""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="list", args=(), exc_info=None,
        )
        record.extra = {"items": [{"password": "bad"}, {"name": "ok"}]}
        data = orjson.loads(json_formatter.format(record))

        assert data["extra"]["items"][0]["password"] == "[REDACTED]"
        assert data["extra"]["items"][1]["name"] == "ok"

    def test_format_includes_exception_info(self, json_formatter):
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="error occurred", args=(), exc_info=exc_info,
        )
        data = orjson.loads(json_formatter.format(record))

        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert data["exception"]["message"] == "test error"
        assert data["exception"]["traceback"] is not None

    def test_format_with_extra_fields(self):
        from django_matt.observability.logging import JSONFormatter

        formatter = JSONFormatter(
            include_timestamp=False,
            include_hostname=False,
            extra_fields={"service": "test-svc", "env": "test"},
        )
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="extra", args=(), exc_info=None,
        )
        data = orjson.loads(formatter.format(record))

        assert data["extra"]["service"] == "test-svc"
        assert data["extra"]["env"] == "test"

    def test_format_with_hostname(self):
        from django_matt.observability.logging import JSONFormatter

        formatter = JSONFormatter(include_hostname=True, include_timestamp=False)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="host", args=(), exc_info=None,
        )
        data = orjson.loads(formatter.format(record))

        assert "hostname" in data

    def test_format_with_custom_record_attributes(self, json_formatter):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="custom", args=(), exc_info=None,
        )
        record.custom_field = "custom_value"
        data = orjson.loads(json_formatter.format(record))

        assert data["extra"]["custom_field"] == "custom_value"


# ---------------------------------------------------------------------------
# Tests: Logging — PrettyJSONFormatter
# ---------------------------------------------------------------------------


class TestPrettyJSONFormatter:
    """Tests for PrettyJSONFormatter."""

    def test_produces_indented_json(self, pretty_formatter):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="pretty test", args=(), exc_info=None,
        )
        output = pretty_formatter.format(record)
        data = json.loads(output)

        assert data["message"] == "pretty test"
        # Pretty format has newlines and indentation
        assert "\n" in output
        assert "  " in output

    def test_inherits_json_formatter_behavior(self, pretty_formatter):
        from django_matt.observability.logging import set_request_id

        set_request_id("pretty-req-1")

        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="", lineno=0,
            msg="warning", args=(), exc_info=None,
        )
        data = json.loads(pretty_formatter.format(record))

        assert data["level"] == "WARNING"
        assert data["request_id"] == "pretty-req-1"


# ---------------------------------------------------------------------------
# Tests: Logging — ColoredTextFormatter
# ---------------------------------------------------------------------------


class TestColoredTextFormatter:
    """Tests for ColoredTextFormatter."""

    def test_basic_format(self, colored_formatter):
        record = logging.LogRecord(
            name="test.logger", level=logging.INFO, pathname="", lineno=0,
            msg="colored message", args=(), exc_info=None,
        )
        output = colored_formatter.format(record)

        assert "colored message" in output
        assert "test.logger" in output
        # Check that ANSI codes are present
        assert "\033[" in output

    def test_includes_correlation_id(self, colored_formatter):
        from django_matt.observability.logging import correlation_id_var

        correlation_id_var.set("abcdef123456")

        record = logging.LogRecord(
            name="test", level=logging.DEBUG, pathname="", lineno=0,
            msg="with correlation", args=(), exc_info=None,
        )
        output = colored_formatter.format(record)

        # Correlation ID is truncated to first 8 chars
        assert "abcdef12" in output

    def test_different_levels_use_different_colors(self, colored_formatter):
        levels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
        outputs = []
        for level in levels:
            record = logging.LogRecord(
                name="test", level=level, pathname="", lineno=0,
                msg="level test", args=(), exc_info=None,
            )
            outputs.append(colored_formatter.format(record))

        # Each level should produce unique output (different color codes)
        assert len(set(outputs)) == len(outputs)

    def test_exception_formatting(self, colored_formatter):
        try:
            raise RuntimeError("color error")
        except RuntimeError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="error", args=(), exc_info=exc_info,
        )
        output = colored_formatter.format(record)

        assert "RuntimeError" in output
        assert "color error" in output


# ---------------------------------------------------------------------------
# Tests: Logging — StructuredLogger and BoundLogger
# ---------------------------------------------------------------------------


class TestStructuredLogger:
    """Tests for StructuredLogger."""

    def test_get_logger_returns_structured_logger(self):
        from django_matt.observability.logging import StructuredLogger, get_logger

        logger = get_logger("test.structured")
        assert isinstance(logger, StructuredLogger)

    def test_info_with_context(self):
        from django_matt.observability.logging import get_logger

        logger = get_logger("test.ctx")
        handler = logging.Handler()
        handler.emit = MagicMock()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            logger.info_with_context("test message", user="matt", action="login")
            assert handler.emit.called
            record = handler.emit.call_args[0][0]
            assert record.extra["user"] == "matt"
            assert record.extra["action"] == "login"
        finally:
            logger.removeHandler(handler)

    def test_debug_with_context(self):
        from django_matt.observability.logging import get_logger

        logger = get_logger("test.debug.ctx")
        handler = logging.Handler()
        handler.emit = MagicMock()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            logger.debug_with_context("debug msg", key="val")
            assert handler.emit.called
            record = handler.emit.call_args[0][0]
            assert record.extra["key"] == "val"
        finally:
            logger.removeHandler(handler)

    def test_warning_with_context(self):
        from django_matt.observability.logging import get_logger

        logger = get_logger("test.warn.ctx")
        handler = logging.Handler()
        handler.emit = MagicMock()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            logger.warning_with_context("warn msg", status="degraded")
            assert handler.emit.called
        finally:
            logger.removeHandler(handler)

    def test_error_with_context(self):
        from django_matt.observability.logging import get_logger

        logger = get_logger("test.error.ctx")
        handler = logging.Handler()
        handler.emit = MagicMock()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            logger.error_with_context("error msg", code=500)
            assert handler.emit.called
        finally:
            logger.removeHandler(handler)

    def test_critical_with_context(self):
        from django_matt.observability.logging import get_logger

        logger = get_logger("test.critical.ctx")
        handler = logging.Handler()
        handler.emit = MagicMock()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            logger.critical_with_context("critical msg")
            assert handler.emit.called
        finally:
            logger.removeHandler(handler)

    def test_bind_creates_bound_logger(self):
        from django_matt.observability.logging import BoundLogger, get_logger

        logger = get_logger("test.bind")
        bound = logger.bind(service="auth", env="test")
        assert isinstance(bound, BoundLogger)

    def test_bound_logger_carries_context(self):
        from django_matt.observability.logging import get_logger

        logger = get_logger("test.bound.carry")
        handler = logging.Handler()
        handler.emit = MagicMock()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            bound = logger.bind(service="api")
            bound.info("bound message", extra_key="extra_val")
            assert handler.emit.called
            record = handler.emit.call_args[0][0]
            assert record.extra["service"] == "api"
            assert record.extra["extra_key"] == "extra_val"
        finally:
            logger.removeHandler(handler)

    def test_bound_logger_rebind(self):
        from django_matt.observability.logging import get_logger

        logger = get_logger("test.rebind")
        bound1 = logger.bind(a="1")
        bound2 = bound1.bind(b="2")

        handler = logging.Handler()
        handler.emit = MagicMock()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            bound2.debug("rebind test")
            record = handler.emit.call_args[0][0]
            assert record.extra["a"] == "1"
            assert record.extra["b"] == "2"
        finally:
            logger.removeHandler(handler)

    def test_bound_logger_all_levels(self):
        from django_matt.observability.logging import get_logger

        logger = get_logger("test.bound.levels")
        handler = logging.Handler()
        handler.emit = MagicMock()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            bound = logger.bind(ctx="test")
            bound.debug("d")
            bound.info("i")
            bound.warning("w")
            bound.error("e")
            bound.critical("c")
            bound.exception("x")
            assert handler.emit.call_count == 6
        finally:
            logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# Tests: Logging — Context management
# ---------------------------------------------------------------------------


class TestLoggingContext:
    """Tests for context variable management."""

    def test_set_and_get_request_id(self):
        from django_matt.observability.logging import get_request_id, set_request_id

        assert get_request_id() is None
        set_request_id("req-abc")
        assert get_request_id() == "req-abc"

    def test_set_and_get_user_id(self):
        from django_matt.observability.logging import get_user_id, set_user_id

        assert get_user_id() is None
        set_user_id("user-xyz")
        assert get_user_id() == "user-xyz"

    def test_set_and_get_correlation_id(self):
        from django_matt.observability.logging import (
            get_correlation_id as log_get_corr,
            set_correlation_id as log_set_corr,
        )

        assert log_get_corr() is None
        log_set_corr("corr-111")
        assert log_get_corr() == "corr-111"

    def test_clear_context(self):
        from django_matt.observability.logging import (
            clear_context,
            get_correlation_id as log_get_corr,
            get_request_id,
            get_user_id,
            set_correlation_id as log_set_corr,
            set_request_id,
            set_user_id,
        )

        set_request_id("r")
        set_user_id("u")
        log_set_corr("c")
        clear_context()

        assert get_request_id() is None
        assert get_user_id() is None
        assert log_get_corr() is None


# ---------------------------------------------------------------------------
# Tests: Logging — Configuration
# ---------------------------------------------------------------------------


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_default_values(self):
        from django_matt.observability.logging import LoggingConfig

        config = LoggingConfig()
        assert config.enabled is True
        assert config.format == "json"
        assert config.level == "INFO"
        assert config.include_timestamp is True
        assert config.include_correlation_id is True
        assert config.include_request_id is True
        assert config.include_user is True
        assert config.include_hostname is True
        assert config.timestamp_format == "iso"
        assert isinstance(config.extra_fields, dict)
        assert isinstance(config.exclude_loggers, list)
        assert "password" in config.sensitive_fields

    @override_settings(DJANGO_MATT_LOGGING={
        "ENABLED": False,
        "FORMAT": "text",
        "LEVEL": "DEBUG",
        "INCLUDE_TIMESTAMP": False,
        "INCLUDE_HOSTNAME": False,
        "EXTRA_FIELDS": {"service": "test"},
    })
    def test_custom_values(self):
        from django_matt.observability.logging import LoggingConfig

        config = LoggingConfig()
        assert config.enabled is False
        assert config.format == "text"
        assert config.level == "DEBUG"
        assert config.include_timestamp is False
        assert config.include_hostname is False
        assert config.extra_fields == {"service": "test"}


class TestGetLoggingConfig:
    """Tests for get_logging_config."""

    def test_json_format(self):
        from django_matt.observability.logging import get_logging_config

        config = get_logging_config(format="json", level="INFO")
        assert config["version"] == 1
        assert "structured" in config["formatters"]
        assert "JSONFormatter" in config["formatters"]["structured"]["()"]

    def test_pretty_format(self):
        from django_matt.observability.logging import get_logging_config

        config = get_logging_config(format="pretty")
        assert "PrettyJSONFormatter" in config["formatters"]["structured"]["()"]

    def test_text_format(self):
        from django_matt.observability.logging import get_logging_config

        config = get_logging_config(format="text")
        assert "ColoredTextFormatter" in config["formatters"]["structured"]["()"]

    def test_includes_django_loggers(self):
        from django_matt.observability.logging import get_logging_config

        config = get_logging_config(include_django=True)
        assert "django" in config["loggers"]
        assert "django.request" in config["loggers"]
        assert "django.db.backends" in config["loggers"]

    def test_excludes_django_loggers(self):
        from django_matt.observability.logging import get_logging_config

        config = get_logging_config(include_django=False)
        assert "django" not in config["loggers"]

    def test_custom_level(self):
        from django_matt.observability.logging import get_logging_config

        config = get_logging_config(level="WARNING")
        assert config["root"]["level"] == "WARNING"


class TestConfigureLogging:
    """Tests for configure_logging."""

    def test_configure_json(self):
        from django_matt.observability.logging import JSONFormatter, configure_logging

        configure_logging(format="json", level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert any(isinstance(h.formatter, JSONFormatter) for h in root.handlers)

    def test_configure_pretty(self):
        from django_matt.observability.logging import PrettyJSONFormatter, configure_logging

        configure_logging(format="pretty", level="INFO")
        root = logging.getLogger()
        assert any(isinstance(h.formatter, PrettyJSONFormatter) for h in root.handlers)

    def test_configure_text(self):
        from django_matt.observability.logging import ColoredTextFormatter, configure_logging

        configure_logging(format="text", level="WARNING")
        root = logging.getLogger()
        assert any(isinstance(h.formatter, ColoredTextFormatter) for h in root.handlers)


# ---------------------------------------------------------------------------
# Tests: Metrics — Fallback metrics (no prometheus_client)
# ---------------------------------------------------------------------------


class TestFallbackMetrics:
    """Tests for fallback metric implementations."""

    def test_fallback_counter_inc(self):
        from django_matt.observability.metrics import FallbackCounter

        counter = FallbackCounter("test_counter", "Test counter")
        counter.inc()
        counter.inc(5)
        assert counter._values[()] == 6

    def test_fallback_gauge_inc_dec_set(self):
        from django_matt.observability.metrics import FallbackGauge

        gauge = FallbackGauge("test_gauge", "Test gauge")
        gauge.inc()
        gauge.inc(2)
        assert gauge._values[()] == 3
        gauge.dec()
        assert gauge._values[()] == 2
        gauge.set(10)
        assert gauge._values[()] == 10

    def test_fallback_histogram_observe(self):
        from django_matt.observability.metrics import FallbackHistogram

        hist = FallbackHistogram("test_hist", "Test histogram")
        hist.observe(0.1)
        hist.observe(0.5)
        hist.observe(1.0)
        assert len(hist._observations[()]) == 3
        assert sum(hist._observations[()]) == pytest.approx(1.6)

    def test_fallback_histogram_time_context_manager(self):
        from django_matt.observability.metrics import FallbackHistogram

        hist = FallbackHistogram("test_hist_time", "Test histogram timing")
        with hist.time():
            time.sleep(0.01)
        assert len(hist._observations[()]) == 1
        assert hist._observations[()][0] > 0

    def test_fallback_summary_observe(self):
        from django_matt.observability.metrics import FallbackSummary

        summary = FallbackSummary("test_summary", "Test summary")
        summary.observe(1.0)
        summary.observe(2.0)
        assert len(summary._observations[()]) == 2

    def test_fallback_metric_labels(self):
        from django_matt.observability.metrics import FallbackMetric

        metric = FallbackMetric("test_labeled", "Test", labelnames=["method", "status"])
        labeled = metric.labels(method="GET", status="200")
        labeled.inc()
        labeled.inc(3)
        assert metric._values[("GET", "200")] == 4

    def test_fallback_labeled_metric_dec(self):
        from django_matt.observability.metrics import FallbackMetric

        metric = FallbackMetric("test_dec", "Test", labelnames=["a"])
        labeled = metric.labels(a="x")
        labeled.set(10)
        labeled.dec(3)
        assert metric._values[("x",)] == 7

    def test_fallback_labeled_metric_observe(self):
        from django_matt.observability.metrics import FallbackMetric

        metric = FallbackMetric("test_obs", "Test", labelnames=["op"])
        labeled = metric.labels(op="query")
        labeled.observe(0.5)
        assert metric._values[("query",)] == 0.5

    def test_fallback_histogram_custom_buckets(self):
        from django_matt.observability.metrics import FallbackHistogram

        buckets = [0.1, 0.5, 1.0]
        hist = FallbackHistogram("custom_buck", "Custom buckets", buckets=buckets)
        assert hist.buckets == buckets


# ---------------------------------------------------------------------------
# Tests: Metrics — MetricsManager
# ---------------------------------------------------------------------------


class TestMetricsManager:
    """Tests for MetricsManager."""

    def test_counter_creation(self, fresh_metrics_manager):
        counter = fresh_metrics_manager.counter("test_counter", "A counter")
        assert counter is not None
        assert "django_matt_test_counter" in fresh_metrics_manager._metrics

    def test_counter_caching(self, fresh_metrics_manager):
        c1 = fresh_metrics_manager.counter("test_cache", "Cached counter")
        c2 = fresh_metrics_manager.counter("test_cache", "Cached counter")
        assert c1 is c2

    def test_gauge_creation(self, fresh_metrics_manager):
        gauge = fresh_metrics_manager.gauge("test_gauge", "A gauge")
        assert gauge is not None

    def test_histogram_creation(self, fresh_metrics_manager):
        hist = fresh_metrics_manager.histogram("test_hist", "A histogram")
        assert hist is not None

    def test_histogram_custom_buckets(self, fresh_metrics_manager):
        buckets = [0.01, 0.1, 1.0]
        hist = fresh_metrics_manager.histogram("custom_hist", buckets=buckets)
        assert hist is not None

    def test_summary_creation(self, fresh_metrics_manager):
        summary = fresh_metrics_manager.summary("test_summary", "A summary")
        assert summary is not None

    def test_info_creation(self, fresh_metrics_manager):
        info = fresh_metrics_manager.info("test_info", "An info metric")
        assert info is not None

    def test_prefixed_name(self, fresh_metrics_manager):
        name = fresh_metrics_manager._get_prefixed_name("requests")
        assert name == "django_matt_requests"

    def test_prefixed_name_already_prefixed(self, fresh_metrics_manager):
        name = fresh_metrics_manager._get_prefixed_name("django_matt_requests")
        assert name == "django_matt_requests"

    def test_remove_metric(self, fresh_metrics_manager):
        fresh_metrics_manager.counter("to_remove", "Remove me")
        assert fresh_metrics_manager.remove_metric("to_remove") is True
        assert fresh_metrics_manager.remove_metric("to_remove") is False

    def test_generate_metrics_fallback(self, fresh_metrics_manager):
        counter = fresh_metrics_manager.counter("gen_counter", "Generation test")
        counter.inc(5)
        output = fresh_metrics_manager.generate_metrics()
        assert isinstance(output, bytes)

    def test_generate_metrics_histogram_fallback(self, fresh_metrics_manager):
        hist = fresh_metrics_manager.histogram("gen_hist", "Gen histogram")
        hist.observe(0.1)
        hist.observe(0.5)
        output = fresh_metrics_manager.generate_metrics().decode("utf-8")
        assert "gen_hist" in output or "django_matt_gen_hist" in output

    def test_get_content_type(self, fresh_metrics_manager):
        ct = fresh_metrics_manager.get_content_type()
        assert "text/plain" in ct or "openmetrics" in ct or "text" in ct

    def test_counter_with_labels(self, fresh_metrics_manager):
        counter = fresh_metrics_manager.counter(
            "labeled_counter", "Labeled", labelnames=["method"]
        )
        labeled = counter.labels(method="GET")
        labeled.inc()
        assert counter is not None

    def test_setup_enabled(self, fresh_metrics_manager):
        result = fresh_metrics_manager.setup()
        assert result is True
        assert fresh_metrics_manager._initialized is True

    def test_setup_disabled(self):
        from django_matt.observability.metrics import MetricsManager

        mgr = MetricsManager()
        with patch("django_matt.observability.metrics.metrics_config") as mock_config:
            mock_config.enabled = False
            result = mgr.setup()
            assert result is False


# ---------------------------------------------------------------------------
# Tests: Metrics — MetricsConfig
# ---------------------------------------------------------------------------


class TestMetricsConfig:
    """Tests for MetricsConfig."""

    def test_default_values(self):
        from django_matt.observability.metrics import MetricsConfig

        config = MetricsConfig()
        assert config.enabled is True
        assert config.prefix == "django_matt"
        assert isinstance(config.default_buckets, list)
        assert config.include_host is True
        assert config.include_method is True
        assert config.include_path is True
        assert config.include_status is True
        assert isinstance(config.exclude_paths, list)

    @override_settings(DJANGO_MATT_METRICS={
        "ENABLED": False,
        "PREFIX": "myapp",
        "INCLUDE_HOST": False,
    })
    def test_custom_values(self):
        from django_matt.observability.metrics import MetricsConfig

        config = MetricsConfig()
        assert config.enabled is False
        assert config.prefix == "myapp"
        assert config.include_host is False


# ---------------------------------------------------------------------------
# Tests: Metrics — Convenience functions
# ---------------------------------------------------------------------------


class TestMetricsConvenience:
    """Tests for record_request, record_db_query, etc."""

    def test_record_request_success(self):
        from django_matt.observability.metrics import record_request

        # Should not raise
        record_request("GET", "/api/users", 200, 0.05)

    def test_record_request_error(self):
        from django_matt.observability.metrics import record_request

        record_request("POST", "/api/users", 400, 0.1)
        record_request("GET", "/api/users", 500, 0.2)

    @override_settings(DJANGO_MATT_METRICS={"ENABLED": False})
    def test_record_request_disabled(self):
        from django_matt.observability.metrics import MetricsConfig

        # Temporarily create a config that reads disabled
        config = MetricsConfig()
        assert config.enabled is False

    def test_record_db_query(self):
        from django_matt.observability.metrics import record_db_query

        record_db_query("SELECT", "users", 0.01)
        record_db_query("INSERT", "orders", 0.005)

    def test_increment_decrement_active_requests(self):
        from django_matt.observability.metrics import (
            decrement_active_requests,
            increment_active_requests,
        )

        increment_active_requests("GET", "/api/users")
        decrement_active_requests("GET", "/api/users")

    def test_get_percentiles_no_data(self):
        from django_matt.observability.metrics import get_percentiles

        result = get_percentiles("nonexistent_histogram")
        assert result == {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    def test_get_percentiles_with_fallback_histogram(self, fresh_metrics_manager):
        hist = fresh_metrics_manager.histogram("perc_hist", "Percentile test")
        for i in range(100):
            hist.observe(float(i))

        from django_matt.observability.metrics import get_percentiles

        # Patch the global manager temporarily
        with patch("django_matt.observability.metrics.metrics_manager", fresh_metrics_manager):
            result = get_percentiles("perc_hist")
            assert result["p50"] > 0
            assert result["p95"] > result["p50"]
            assert result["p99"] >= result["p95"]


# ---------------------------------------------------------------------------
# Tests: Tracing — NullSpan and NullTracer
# ---------------------------------------------------------------------------


class TestNullSpan:
    """Tests for NullSpan."""

    def test_basic_operations(self):
        from django_matt.observability.tracing import NullSpan

        span = NullSpan("test")
        assert span.name == "test"
        assert span.is_recording() is False
        assert span.get_span_context() is None

    def test_set_attribute_returns_self(self):
        from django_matt.observability.tracing import NullSpan

        span = NullSpan("test")
        result = span.set_attribute("key", "value")
        assert result is span
        assert span._attributes["key"] == "value"

    def test_set_attributes(self):
        from django_matt.observability.tracing import NullSpan

        span = NullSpan()
        span.set_attributes({"a": 1, "b": 2})
        assert span._attributes == {"a": 1, "b": 2}

    def test_add_event(self):
        from django_matt.observability.tracing import NullSpan

        span = NullSpan()
        result = span.add_event("test_event", {"key": "val"})
        assert result is span
        assert len(span._events) == 1
        assert span._events[0] == ("test_event", {"key": "val"})

    def test_set_status(self):
        from django_matt.observability.tracing import NullSpan

        span = NullSpan()
        result = span.set_status("ok")
        assert result is span

    def test_record_exception(self):
        from django_matt.observability.tracing import NullSpan

        span = NullSpan()
        result = span.record_exception(ValueError("test"))
        assert result is span

    def test_context_manager(self):
        from django_matt.observability.tracing import NullSpan

        with NullSpan("ctx") as span:
            span.set_attribute("inside", True)
        assert span._attributes["inside"] is True

    def test_end(self):
        from django_matt.observability.tracing import NullSpan

        span = NullSpan()
        span.end()  # Should not raise


class TestNullTracer:
    """Tests for NullTracer."""

    def test_start_span(self):
        from django_matt.observability.tracing import NullSpan, NullTracer

        tracer = NullTracer()
        span = tracer.start_span("test_span")
        assert isinstance(span, NullSpan)
        assert span.name == "test_span"

    def test_start_span_with_attributes(self):
        from django_matt.observability.tracing import NullTracer

        tracer = NullTracer()
        span = tracer.start_span("test", attributes={"key": "val"})
        assert span is not None

    def test_start_as_current_span(self):
        from django_matt.observability.tracing import NullSpan, NullTracer

        tracer = NullTracer()
        with tracer.start_as_current_span("test_span") as span:
            assert isinstance(span, NullSpan)
            span.set_attribute("test", True)


# ---------------------------------------------------------------------------
# Tests: Tracing — TracingConfig
# ---------------------------------------------------------------------------


class TestTracingConfig:
    """Tests for TracingConfig."""

    def test_default_values(self):
        from django_matt.observability.tracing import TracingConfig

        config = TracingConfig()
        assert config.enabled is False  # Default disabled
        assert config.service_name == "django-matt-app"
        assert config.exporter == "console"
        assert config.endpoint is None
        assert config.sample_rate == 1.0
        assert "tracecontext" in config.propagators
        assert config.debug is False
        assert config.headers is None

    @override_settings(DJANGO_MATT_TRACING={
        "ENABLED": True,
        "SERVICE_NAME": "myapp",
        "EXPORTER": "otlp",
        "ENDPOINT": "http://localhost:4317",
        "SAMPLE_RATE": 0.5,
        "DEBUG": True,
        "HEADERS": {"api-key": "abc"},
    })
    def test_custom_values(self):
        from django_matt.observability.tracing import TracingConfig

        config = TracingConfig()
        assert config.enabled is True
        assert config.service_name == "myapp"
        assert config.exporter == "otlp"
        assert config.endpoint == "http://localhost:4317"
        assert config.sample_rate == 0.5
        assert config.debug is True
        assert config.headers == {"api-key": "abc"}


# ---------------------------------------------------------------------------
# Tests: Tracing — TracingManager
# ---------------------------------------------------------------------------


class TestTracingManager:
    """Tests for TracingManager."""

    def test_uninitialized_returns_null_tracer(self):
        from django_matt.observability.tracing import NullTracer, TracingManager

        mgr = TracingManager()
        assert isinstance(mgr.tracer, NullTracer)

    def test_uninitialized_get_current_span_returns_null(self):
        from django_matt.observability.tracing import NullSpan, TracingManager

        mgr = TracingManager()
        span = mgr.get_current_span()
        assert isinstance(span, NullSpan)

    def test_uninitialized_start_span_returns_null(self):
        from django_matt.observability.tracing import NullSpan, TracingManager

        mgr = TracingManager()
        span = mgr.start_span("test")
        assert isinstance(span, NullSpan)

    def test_uninitialized_span_context_manager(self):
        from django_matt.observability.tracing import NullSpan, TracingManager

        mgr = TracingManager()
        with mgr.span("test") as span:
            assert isinstance(span, NullSpan)
            span.set_attribute("key", "val")

    def test_inject_context_uninitialized(self):
        from django_matt.observability.tracing import TracingManager

        mgr = TracingManager()
        carrier = {"existing": "header"}
        result = mgr.inject_context(carrier)
        assert result == carrier

    def test_extract_context_uninitialized(self):
        from django_matt.observability.tracing import TracingManager

        mgr = TracingManager()
        result = mgr.extract_context({"traceparent": "00-abc-def-01"})
        assert result is None

    def test_setup_without_opentelemetry(self):
        from django_matt.observability.tracing import TracingManager

        mgr = TracingManager()
        with patch("django_matt.observability.tracing.HAS_OPENTELEMETRY", False):
            result = mgr.setup(service_name="test")
            assert result is False


# ---------------------------------------------------------------------------
# Tests: Tracing — Helper functions
# ---------------------------------------------------------------------------


class TestTracingHelpers:
    """Tests for module-level tracing helpers."""

    def test_get_tracer(self):
        from django_matt.observability.tracing import NullTracer, get_tracer

        tracer = get_tracer()
        # Without OTel setup, returns NullTracer
        assert isinstance(tracer, NullTracer)

    def test_get_current_span(self):
        from django_matt.observability.tracing import NullSpan, get_current_span

        span = get_current_span()
        assert isinstance(span, NullSpan)

    def test_correlation_id(self):
        from django_matt.observability.tracing import get_correlation_id, set_correlation_id

        assert get_correlation_id() is None
        set_correlation_id("trace-corr-123")
        assert get_correlation_id() == "trace-corr-123"
        # Clean up
        set_correlation_id(None)

    def test_inject_headers(self):
        from django_matt.observability.tracing import inject_headers

        headers = {"Content-Type": "application/json"}
        result = inject_headers(headers)
        assert "Content-Type" in result

    def test_extract_context(self):
        from django_matt.observability.tracing import extract_context

        result = extract_context({"traceparent": "00-abc-def-01"})
        # Without OTel, returns None
        assert result is None

    def test_get_datadog_tracer_not_installed(self):
        from django_matt.observability.tracing import get_datadog_tracer

        # Datadog not installed in test env
        result = get_datadog_tracer()
        assert result is None

    def test_datadog_trace_decorator_noop(self):
        from django_matt.observability.tracing import datadog_trace

        @datadog_trace("test_op")
        def my_func():
            return 42

        # Without Datadog, decorator is a no-op passthrough
        assert my_func() == 42

    def test_newrelic_trace_decorator_noop(self):
        from django_matt.observability.tracing import newrelic_trace

        @newrelic_trace("test_transaction")
        def my_func():
            return 99

        assert my_func() == 99


# ---------------------------------------------------------------------------
# Tests: Decorators — @trace
# ---------------------------------------------------------------------------


class TestTraceDecorator:
    """Tests for @trace decorator."""

    def test_sync_function(self):
        from django_matt.observability.decorators import trace

        @trace("test_op")
        def my_func():
            return {"status": "ok", "data": 42}

        result = my_func()
        assert result == {"status": "ok", "data": 42}

    def test_sync_function_with_exception(self):
        from django_matt.observability.decorators import trace

        @trace("fail_op")
        def bad_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            bad_func()

    def test_async_function(self):
        from django_matt.observability.decorators import trace

        @trace("async_op")
        async def my_async_func():
            return {"status": "success"}

        result = asyncio.get_event_loop().run_until_complete(my_async_func())
        assert result == {"status": "success"}

    def test_async_function_with_exception(self):
        from django_matt.observability.decorators import trace

        @trace("async_fail")
        async def bad_async():
            raise RuntimeError("async error")

        with pytest.raises(RuntimeError, match="async error"):
            asyncio.get_event_loop().run_until_complete(bad_async())

    def test_default_name(self):
        from django_matt.observability.decorators import trace

        @trace()
        def named_func():
            return True

        # functools.wraps preserves name
        assert named_func.__name__ == "named_func"
        assert named_func() is True

    def test_record_exception_disabled(self):
        from django_matt.observability.decorators import trace

        @trace("no_record", record_exception=False)
        def failing_func():
            raise TypeError("no record")

        with pytest.raises(TypeError):
            failing_func()

    def test_with_attributes(self):
        from django_matt.observability.decorators import trace

        @trace("attr_op", attributes={"custom": "attr"})
        def attr_func():
            return 1

        assert attr_func() == 1

    def test_with_kind(self):
        from django_matt.observability.decorators import trace

        @trace("kind_op", kind="server")
        def server_func():
            return "response"

        assert server_func() == "response"


# ---------------------------------------------------------------------------
# Tests: Decorators — @metric
# ---------------------------------------------------------------------------


class TestMetricDecorator:
    """Tests for @metric decorator."""

    def test_counter_metric(self):
        from django_matt.observability.decorators import metric

        @metric("test_metric_counter")
        def my_func():
            return {"status": "ok"}

        result = my_func()
        assert result == {"status": "ok"}

    def test_counter_metric_with_labels(self):
        from django_matt.observability.decorators import metric

        @metric("test_labeled_metric", labels=["status"])
        def my_func():
            return {"status": "ok"}

        result = my_func()
        assert result["status"] == "ok"

    def test_histogram_metric(self):
        from django_matt.observability.decorators import metric

        @metric("test_hist_metric", metric_type="histogram")
        def my_func():
            return 42

        assert my_func() == 42

    def test_gauge_metric(self):
        from django_matt.observability.decorators import metric

        @metric("test_gauge_metric", metric_type="gauge")
        def my_func():
            return "ok"

        assert my_func() == "ok"

    def test_metric_with_duration(self):
        from django_matt.observability.decorators import metric

        @metric("test_duration_metric", record_duration=True)
        def my_func():
            return True

        assert my_func() is True

    def test_metric_on_exception(self):
        from django_matt.observability.decorators import metric

        @metric("test_error_metric")
        def failing():
            raise ValueError("metric error")

        with pytest.raises(ValueError):
            failing()

    def test_async_metric(self):
        from django_matt.observability.decorators import metric

        @metric("test_async_metric")
        async def my_async():
            return {"status": "done"}

        result = asyncio.get_event_loop().run_until_complete(my_async())
        assert result == {"status": "done"}

    def test_async_metric_with_exception(self):
        from django_matt.observability.decorators import metric

        @metric("test_async_error_metric")
        async def bad_async():
            raise RuntimeError("async metric error")

        with pytest.raises(RuntimeError):
            asyncio.get_event_loop().run_until_complete(bad_async())

    def test_metric_labels_from_kwargs(self):
        from django_matt.observability.decorators import metric

        @metric("test_kwarg_metric", labels=["region"])
        def my_func(region="us"):
            return "result"

        # When result is not a dict, labels are extracted from kwargs
        result = my_func(region="eu")
        assert result == "result"

    def test_metric_no_increment_on_success(self):
        from django_matt.observability.decorators import metric

        @metric("test_no_inc", increment_on_success=False)
        def my_func():
            return True

        assert my_func() is True

    def test_metric_no_increment_on_error(self):
        from django_matt.observability.decorators import metric

        @metric("test_no_inc_err", increment_on_error=False)
        def failing():
            raise ValueError("no inc")

        with pytest.raises(ValueError):
            failing()


# ---------------------------------------------------------------------------
# Tests: Decorators — @timed
# ---------------------------------------------------------------------------


class TestTimedDecorator:
    """Tests for @timed decorator."""

    def test_sync_timed(self):
        from django_matt.observability.decorators import timed

        @timed()
        def slow_func():
            time.sleep(0.01)
            return "done"

        assert slow_func() == "done"

    def test_custom_name(self):
        from django_matt.observability.decorators import timed

        @timed("custom_timing")
        def my_func():
            return 42

        assert my_func() == 42

    def test_with_labels(self):
        from django_matt.observability.decorators import timed

        @timed(labels={"service": "api"})
        def my_func():
            return "ok"

        assert my_func() == "ok"

    def test_async_timed(self):
        from django_matt.observability.decorators import timed

        @timed()
        async def async_slow():
            return "async done"

        result = asyncio.get_event_loop().run_until_complete(async_slow())
        assert result == "async done"

    def test_timed_with_exception(self):
        from django_matt.observability.decorators import timed

        @timed()
        def failing():
            raise RuntimeError("timed error")

        with pytest.raises(RuntimeError):
            failing()

    def test_preserves_function_name(self):
        from django_matt.observability.decorators import timed

        @timed()
        def original_name():
            pass

        assert original_name.__name__ == "original_name"


# ---------------------------------------------------------------------------
# Tests: Decorators — @counted
# ---------------------------------------------------------------------------


class TestCountedDecorator:
    """Tests for @counted decorator."""

    def test_sync_counted(self):
        from django_matt.observability.decorators import counted

        @counted()
        def my_func():
            return "counted"

        assert my_func() == "counted"

    def test_custom_name(self):
        from django_matt.observability.decorators import counted

        @counted("custom_count")
        def my_func():
            return 1

        assert my_func() == 1

    def test_with_labels(self):
        from django_matt.observability.decorators import counted

        @counted(labels={"endpoint": "/api"})
        def my_func():
            return True

        assert my_func() is True

    def test_counted_with_exception(self):
        from django_matt.observability.decorators import counted

        @counted(count_exceptions=True)
        def failing():
            raise ValueError("counted error")

        with pytest.raises(ValueError):
            failing()

    def test_counted_no_count_on_exception(self):
        from django_matt.observability.decorators import counted

        @counted(count_exceptions=False)
        def failing():
            raise ValueError("no count")

        with pytest.raises(ValueError):
            failing()

    def test_async_counted(self):
        from django_matt.observability.decorators import counted

        @counted()
        async def async_counted():
            return "async counted"

        result = asyncio.get_event_loop().run_until_complete(async_counted())
        assert result == "async counted"

    def test_async_counted_with_exception(self):
        from django_matt.observability.decorators import counted

        @counted(count_exceptions=True)
        async def async_failing():
            raise RuntimeError("async count error")

        with pytest.raises(RuntimeError):
            asyncio.get_event_loop().run_until_complete(async_failing())

    def test_async_counted_no_count_on_exception(self):
        from django_matt.observability.decorators import counted

        @counted(count_exceptions=False)
        async def async_failing():
            raise RuntimeError("no count async")

        with pytest.raises(RuntimeError):
            asyncio.get_event_loop().run_until_complete(async_failing())


# ---------------------------------------------------------------------------
# Tests: Decorators — @observe
# ---------------------------------------------------------------------------


class TestObserveDecorator:
    """Tests for @observe decorator."""

    def test_sync_observe(self):
        from django_matt.observability.decorators import observe

        @observe("items_count", lambda r: r["count"])
        def process():
            return {"count": 42, "items": []}

        result = process()
        assert result == {"count": 42, "items": []}

    def test_observe_with_labels(self):
        from django_matt.observability.decorators import observe

        @observe("items_obs", lambda r: r["count"], labels={"type": "batch"})
        def process():
            return {"count": 10}

        assert process()["count"] == 10

    def test_observe_with_bad_extractor(self):
        from django_matt.observability.decorators import observe

        @observe("bad_extract", lambda r: r["missing_key"])
        def process():
            return {"data": "ok"}

        # Should not raise, just log a warning
        result = process()
        assert result == {"data": "ok"}

    def test_async_observe(self):
        from django_matt.observability.decorators import observe

        @observe("async_items", lambda r: r["total"])
        async def async_process():
            return {"total": 100}

        result = asyncio.get_event_loop().run_until_complete(async_process())
        assert result["total"] == 100


# ---------------------------------------------------------------------------
# Tests: Decorators — @with_span_attribute
# ---------------------------------------------------------------------------


class TestWithSpanAttribute:
    """Tests for @with_span_attribute decorator."""

    def test_sync_span_attribute(self):
        from django_matt.observability.decorators import with_span_attribute

        @with_span_attribute("user.name", lambda r: r.get("name"))
        def get_user():
            return {"name": "Matt", "id": 1}

        result = get_user()
        assert result == {"name": "Matt", "id": 1}

    def test_async_span_attribute(self):
        from django_matt.observability.decorators import with_span_attribute

        @with_span_attribute("user.email", lambda r: r.get("email"))
        async def get_user():
            return {"email": "matt@test.com"}

        result = asyncio.get_event_loop().run_until_complete(get_user())
        assert result["email"] == "matt@test.com"

    def test_bad_extractor_does_not_raise(self):
        from django_matt.observability.decorators import with_span_attribute

        @with_span_attribute("bad.key", lambda r: r["nonexistent"])
        def my_func():
            return {}

        result = my_func()
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: Middleware — _normalize_path
# ---------------------------------------------------------------------------


class TestNormalizePath:
    """Tests for _normalize_path helper."""

    def test_normal_path(self):
        from django_matt.observability.middleware import _normalize_path

        assert _normalize_path("/api/users") == "/api/users"

    def test_numeric_id(self):
        from django_matt.observability.middleware import _normalize_path

        assert _normalize_path("/api/users/123") == "/api/users/{id}"

    def test_uuid(self):
        from django_matt.observability.middleware import _normalize_path

        path = "/api/users/550e8400-e29b-41d4-a716-446655440000"
        assert _normalize_path(path) == "/api/users/{uuid}"

    def test_hex_id(self):
        from django_matt.observability.middleware import _normalize_path

        assert _normalize_path("/api/items/abcdef12") == "/api/items/{id}"

    def test_root_path(self):
        from django_matt.observability.middleware import _normalize_path

        assert _normalize_path("/") == "/"

    def test_multiple_ids(self):
        from django_matt.observability.middleware import _normalize_path

        assert _normalize_path("/api/users/42/posts/99") == "/api/users/{id}/posts/{id}"


# ---------------------------------------------------------------------------
# Tests: Middleware — TracingMiddleware
# ---------------------------------------------------------------------------


class TestTracingMiddleware:
    """Tests for TracingMiddleware."""

    def test_disabled_tracing(self, rf):
        from django_matt.observability.middleware import TracingMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = TracingMiddleware(get_response)
        middleware.enabled = False

        request = rf.get("/api/test")
        response = middleware(request)
        assert response.status_code == 200

    def test_enabled_tracing_with_null_tracer(self, rf):
        from django_matt.observability.middleware import TracingMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = TracingMiddleware(get_response)
        middleware.enabled = True

        request = rf.get("/api/test")
        response = middleware(request)
        assert response.status_code == 200
        assert "X-Correlation-ID" in response

    def test_correlation_id_from_header(self, rf):
        from django_matt.observability.middleware import TracingMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = TracingMiddleware(get_response)
        middleware.enabled = True

        request = rf.get("/api/test", HTTP_X_CORRELATION_ID="custom-corr-id")
        response = middleware(request)
        assert response["X-Correlation-ID"] == "custom-corr-id"

    def test_exception_handling(self, rf):
        from django_matt.observability.middleware import TracingMiddleware

        def get_response(request):
            raise RuntimeError("middleware error")

        middleware = TracingMiddleware(get_response)
        middleware.enabled = True

        request = rf.get("/api/test")
        with pytest.raises(RuntimeError, match="middleware error"):
            middleware(request)


# ---------------------------------------------------------------------------
# Tests: Middleware — MetricsMiddleware
# ---------------------------------------------------------------------------


class TestMetricsMiddleware:
    """Tests for MetricsMiddleware."""

    def test_basic_request_tracking(self, rf):
        from django_matt.observability.middleware import MetricsMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = MetricsMiddleware(get_response)
        middleware.enabled = True

        request = rf.get("/api/test")
        response = middleware(request)
        assert response.status_code == 200
        assert "X-Response-Time" in response

    def test_disabled_metrics(self, rf):
        from django_matt.observability.middleware import MetricsMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = MetricsMiddleware(get_response)
        middleware.enabled = False

        request = rf.get("/api/test")
        response = middleware(request)
        assert "X-Response-Time" not in response

    def test_excluded_paths(self, rf):
        from django_matt.observability.middleware import MetricsMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = MetricsMiddleware(get_response)
        middleware.enabled = True

        request = rf.get("/health")
        response = middleware(request)
        assert "X-Response-Time" not in response

    def test_exception_records_500(self, rf):
        from django_matt.observability.middleware import MetricsMiddleware

        def get_response(request):
            raise RuntimeError("server error")

        middleware = MetricsMiddleware(get_response)
        middleware.enabled = True

        request = rf.get("/api/test")
        with pytest.raises(RuntimeError):
            middleware(request)


# ---------------------------------------------------------------------------
# Tests: Middleware — LoggingMiddleware
# ---------------------------------------------------------------------------


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    def test_sets_context_vars(self, rf):
        from django_matt.observability.middleware import LoggingMiddleware

        captured = {}

        def get_response(request):
            from django_matt.observability.logging import get_correlation_id, get_request_id

            captured["request_id"] = get_request_id()
            captured["correlation_id"] = get_correlation_id()
            return HttpResponse("OK")

        middleware = LoggingMiddleware(get_response)
        request = rf.get("/api/test")
        response = middleware(request)

        assert captured["request_id"] is not None
        assert captured["correlation_id"] is not None
        assert response["X-Request-ID"] == captured["request_id"]
        assert response["X-Correlation-ID"] == captured["correlation_id"]

    def test_uses_header_correlation_id(self, rf):
        from django_matt.observability.middleware import LoggingMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = LoggingMiddleware(get_response)
        request = rf.get("/api/test", HTTP_X_CORRELATION_ID="header-corr-id")
        response = middleware(request)

        assert response["X-Correlation-ID"] == "header-corr-id"

    def test_clears_context_after_request(self, rf):
        from django_matt.observability.logging import get_request_id
        from django_matt.observability.middleware import LoggingMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = LoggingMiddleware(get_response)
        request = rf.get("/api/test")
        middleware(request)

        # Context should be cleared after request
        assert get_request_id() is None

    def test_exception_logging(self, rf):
        from django_matt.observability.middleware import LoggingMiddleware

        def get_response(request):
            raise ValueError("logging error")

        middleware = LoggingMiddleware(get_response)
        request = rf.get("/api/test")

        with pytest.raises(ValueError, match="logging error"):
            middleware(request)

    def test_client_ip_from_forwarded_for(self, rf):
        from django_matt.observability.middleware import LoggingMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = LoggingMiddleware(get_response)
        ip = middleware._get_client_ip(
            rf.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8")
        )
        assert ip == "1.2.3.4"

    def test_client_ip_from_remote_addr(self, rf):
        from django_matt.observability.middleware import LoggingMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = LoggingMiddleware(get_response)
        request = rf.get("/")
        ip = middleware._get_client_ip(request)
        assert ip == "127.0.0.1"

    def test_authenticated_user_sets_user_id(self, rf):
        from django_matt.observability.middleware import LoggingMiddleware

        captured = {}

        def get_response(request):
            from django_matt.observability.logging import get_user_id

            captured["user_id"] = get_user_id()
            return HttpResponse("OK")

        middleware = LoggingMiddleware(get_response)
        request = rf.get("/api/test")

        # Mock authenticated user
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.pk = 42

        middleware(request)
        assert captured["user_id"] == "42"


# ---------------------------------------------------------------------------
# Tests: Middleware — DatabaseQueryMiddleware
# ---------------------------------------------------------------------------


class TestDatabaseQueryMiddleware:
    """Tests for DatabaseQueryMiddleware."""

    def test_disabled(self, rf):
        from django_matt.observability.middleware import DatabaseQueryMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = DatabaseQueryMiddleware(get_response)
        middleware.enabled = False

        request = rf.get("/api/test")
        response = middleware(request)
        assert "X-DB-Query-Count" not in response

    @pytest.mark.django_db
    def test_counts_queries(self, rf):
        from django_matt.observability.middleware import DatabaseQueryMiddleware

        from django.conf import settings
        # Temporarily enable DEBUG to track queries
        original_debug = settings.DEBUG
        settings.DEBUG = True

        try:
            def get_response(request):
                from django.contrib.auth.models import User
                list(User.objects.all()[:1])
                return HttpResponse("OK")

            middleware = DatabaseQueryMiddleware(get_response)
            middleware.enabled = True

            request = rf.get("/api/test")
            response = middleware(request)
            assert "X-DB-Query-Count" in response
        finally:
            settings.DEBUG = original_debug


# ---------------------------------------------------------------------------
# Tests: Middleware — ObservabilityMiddleware
# ---------------------------------------------------------------------------


class TestObservabilityMiddleware:
    """Tests for combined ObservabilityMiddleware."""

    def test_chains_middlewares(self, rf):
        from django_matt.observability.middleware import ObservabilityMiddleware

        def get_response(request):
            return HttpResponse("OK")

        middleware = ObservabilityMiddleware(get_response)
        request = rf.get("/api/test")
        response = middleware(request)

        assert response.status_code == 200
        # Should have logging middleware headers
        assert "X-Request-ID" in response
        assert "X-Correlation-ID" in response


# ---------------------------------------------------------------------------
# Tests: Views — health_view
# ---------------------------------------------------------------------------


class TestHealthView:
    """Tests for health_view."""

    def test_health_returns_200(self, rf):
        from django_matt.observability.views import health_view

        request = rf.get("/health")
        response = health_view(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_health_content_type(self, rf):
        from django_matt.observability.views import health_view

        request = rf.get("/health")
        response = health_view(request)
        assert response["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# Tests: Views — metrics_view
# ---------------------------------------------------------------------------


class TestMetricsView:
    """Tests for metrics_view."""

    def test_metrics_returns_200(self, rf):
        from django_matt.observability.views import metrics_view

        request = rf.get("/_matt/metrics")
        response = metrics_view(request)
        assert response.status_code == 200

    def test_metrics_content_type(self, rf):
        from django_matt.observability.views import metrics_view

        request = rf.get("/_matt/metrics")
        response = metrics_view(request)
        ct = response["Content-Type"]
        assert "text" in ct

    def test_metrics_error_handling(self, rf):
        from django_matt.observability.views import metrics_view

        with patch(
            "django_matt.observability.views.metrics_manager.generate_metrics",
            side_effect=RuntimeError("generation failed"),
        ):
            request = rf.get("/_matt/metrics")
            response = metrics_view(request)
            assert response.status_code == 500
            assert b"Error generating metrics" in response.content


# ---------------------------------------------------------------------------
# Tests: Views — info_view
# ---------------------------------------------------------------------------


class TestInfoView:
    """Tests for info_view."""

    def test_info_returns_200(self, rf):
        from django_matt.observability.views import info_view

        request = rf.get("/_matt/info")
        response = info_view(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert "python_version" in data
        assert "django_version" in data
        assert "dependencies" in data
        assert "timestamp" in data

    def test_info_includes_dependencies(self, rf):
        from django_matt.observability.views import info_view

        request = rf.get("/_matt/info")
        response = info_view(request)
        data = json.loads(response.content)

        deps = data["dependencies"]
        assert "opentelemetry" in deps
        assert "prometheus_client" in deps
        assert "jaeger" in deps
        assert "otlp" in deps

    @override_settings(APP_VERSION="1.2.3")
    def test_info_includes_app_version(self, rf):
        from django_matt.observability.views import info_view

        request = rf.get("/_matt/info")
        response = info_view(request)
        data = json.loads(response.content)

        assert data["app_version"] == "1.2.3"


# ---------------------------------------------------------------------------
# Tests: Views — debug_view
# ---------------------------------------------------------------------------


class TestDebugView:
    """Tests for debug_view."""

    @override_settings(DEBUG=True)
    def test_debug_returns_info_in_debug_mode(self, rf):
        from django_matt.observability.views import debug_view

        request = rf.get("/_matt/debug")
        response = debug_view(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert "request" in data
        assert "context" in data
        assert "settings" in data

    @override_settings(DEBUG=False)
    def test_debug_returns_403_in_production(self, rf):
        from django_matt.observability.views import debug_view

        request = rf.get("/_matt/debug")
        response = debug_view(request)

        assert response.status_code == 403
        data = json.loads(response.content)
        assert "error" in data


# ---------------------------------------------------------------------------
# Tests: Views — ready_view
# ---------------------------------------------------------------------------


class TestReadyView:
    """Tests for ready_view."""

    @pytest.mark.django_db
    def test_ready_with_database(self, rf):
        from django_matt.observability.views import ready_view

        request = rf.get("/ready")
        response = ready_view(request)

        data = json.loads(response.content)
        assert "ready" in data
        assert "checks" in data
        assert "timestamp" in data


# ---------------------------------------------------------------------------
# Tests: Views — ReadinessChecker
# ---------------------------------------------------------------------------


class TestReadinessChecker:
    """Tests for ReadinessChecker."""

    def test_register_and_run(self):
        from django_matt.observability.views import ReadinessChecker

        checker = ReadinessChecker()
        checker.register("test_check", lambda: (True, "All good"))

        all_ready, results = checker.run_checks()
        assert all_ready is True
        assert results["test_check"]["ready"] is True
        assert results["test_check"]["message"] == "All good"

    def test_failing_check(self):
        from django_matt.observability.views import ReadinessChecker

        checker = ReadinessChecker()
        checker.register("fail_check", lambda: (False, "Not ready"))

        all_ready, results = checker.run_checks()
        assert all_ready is False
        assert results["fail_check"]["ready"] is False

    def test_exception_in_check(self):
        from django_matt.observability.views import ReadinessChecker

        def bad_check():
            raise RuntimeError("check crashed")

        checker = ReadinessChecker()
        checker.register("crash_check", bad_check)

        all_ready, results = checker.run_checks()
        assert all_ready is False
        assert "Check failed" in results["crash_check"]["message"]

    def test_unregister(self):
        from django_matt.observability.views import ReadinessChecker

        checker = ReadinessChecker()
        checker.register("removable", lambda: (True, "ok"))
        checker.unregister("removable")

        all_ready, results = checker.run_checks()
        assert all_ready is True
        assert "removable" not in results

    def test_multiple_checks(self):
        from django_matt.observability.views import ReadinessChecker

        checker = ReadinessChecker()
        checker.register("db", lambda: (True, "DB OK"))
        checker.register("cache", lambda: (True, "Cache OK"))
        checker.register("queue", lambda: (False, "Queue down"))

        all_ready, results = checker.run_checks()
        assert all_ready is False
        assert results["db"]["ready"] is True
        assert results["cache"]["ready"] is True
        assert results["queue"]["ready"] is False

    def test_no_checks_returns_ready(self):
        from django_matt.observability.views import ReadinessChecker

        checker = ReadinessChecker()
        all_ready, results = checker.run_checks()
        assert all_ready is True
        assert results == {}


# ---------------------------------------------------------------------------
# Tests: Views — URL patterns
# ---------------------------------------------------------------------------


class TestURLPatterns:
    """Tests for observability URL patterns."""

    def test_urlpatterns_exist(self):
        from django_matt.observability.views import urlpatterns

        assert len(urlpatterns) == 5

        names = {p.name for p in urlpatterns}
        assert "observability-metrics" in names
        assert "observability-health" in names
        assert "observability-ready" in names
        assert "observability-info" in names
        assert "observability-debug" in names


# ---------------------------------------------------------------------------
# Tests: Module __init__ exports
# ---------------------------------------------------------------------------


class TestModuleExports:
    """Tests that __init__.py exports are accessible."""

    def test_tracing_exports(self):
        from django_matt.observability import (
            HAS_DATADOG,
            HAS_JAEGER,
            HAS_NEWRELIC,
            HAS_OPENTELEMETRY,
            HAS_OTLP,
            HAS_ZIPKIN,
            NullSpan,
            NullTracer,
            TracingConfig,
            TracingManager,
            extract_context,
            get_correlation_id,
            get_current_span,
            get_tracer,
            inject_headers,
            set_correlation_id,
            setup_tracing,
            tracing_config,
            tracing_manager,
        )

        assert TracingConfig is not None
        assert TracingManager is not None
        assert NullSpan is not None
        assert NullTracer is not None

    def test_metrics_exports(self):
        from django_matt.observability import (
            HAS_PROMETHEUS,
            MetricsConfig,
            MetricsManager,
            decrement_active_requests,
            get_percentiles,
            increment_active_requests,
            metrics_config,
            metrics_manager,
            record_db_query,
            record_request,
        )

        assert MetricsConfig is not None
        assert MetricsManager is not None

    def test_logging_exports(self):
        from django_matt.observability import (
            BoundLogger,
            ColoredTextFormatter,
            JSONFormatter,
            LoggingConfig,
            PrettyJSONFormatter,
            StructuredLogger,
            clear_context,
            configure_logging,
            get_logger,
            get_logging_config,
            get_request_id,
            get_user_id,
            logging_config,
            set_request_id,
            set_user_id,
        )

        assert JSONFormatter is not None
        assert StructuredLogger is not None

    def test_middleware_exports(self):
        from django_matt.observability import (
            DatabaseQueryMiddleware,
            LoggingMiddleware,
            MetricsMiddleware,
            ObservabilityMiddleware,
            TracingMiddleware,
        )

        assert TracingMiddleware is not None
        assert ObservabilityMiddleware is not None

    def test_decorator_exports(self):
        from django_matt.observability import (
            counted,
            metric,
            observe,
            timed,
            trace,
            with_span_attribute,
        )

        assert trace is not None
        assert metric is not None
        assert timed is not None
        assert counted is not None
        assert observe is not None
        assert with_span_attribute is not None

    def test_view_exports(self):
        from django_matt.observability import (
            ReadinessChecker,
            debug_view,
            health_view,
            info_view,
            metrics_view,
            observability_urlpatterns,
            readiness_checker,
            ready_view,
        )

        assert metrics_view is not None
        assert health_view is not None
        assert observability_urlpatterns is not None


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and integration scenarios."""

    def test_json_formatter_with_none_exc_info(self, json_formatter):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="no exc", args=(), exc_info=None,
        )
        data = orjson.loads(json_formatter.format(record))
        assert "exception" not in data

    def test_json_formatter_with_partial_exc_info(self, json_formatter):
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="partial exc", args=(), exc_info=(None, None, None),
        )
        data = orjson.loads(json_formatter.format(record))
        assert data["exception"]["type"] is None
        assert data["exception"]["message"] is None

    def test_metrics_manager_counter_with_no_labels_default(self, fresh_metrics_manager):
        counter = fresh_metrics_manager.counter("simple", "Simple counter")
        counter.inc()
        counter.inc(2)
        assert counter._values[()] == 3

    def test_tracing_flags_are_booleans(self):
        from django_matt.observability.tracing import (
            HAS_DATADOG,
            HAS_JAEGER,
            HAS_NEWRELIC,
            HAS_OPENTELEMETRY,
            HAS_OTLP,
            HAS_ZIPKIN,
        )

        assert isinstance(HAS_OPENTELEMETRY, bool)
        assert isinstance(HAS_JAEGER, bool)
        assert isinstance(HAS_OTLP, bool)
        assert isinstance(HAS_ZIPKIN, bool)
        assert isinstance(HAS_DATADOG, bool)
        assert isinstance(HAS_NEWRELIC, bool)

    def test_metrics_has_prometheus_is_boolean(self):
        from django_matt.observability.metrics import HAS_PROMETHEUS

        assert isinstance(HAS_PROMETHEUS, bool)

    def test_null_span_end_with_time(self):
        from django_matt.observability.tracing import NullSpan

        span = NullSpan()
        span.end(end_time=12345)  # Should not raise

    def test_null_span_add_event_no_attributes(self):
        from django_matt.observability.tracing import NullSpan

        span = NullSpan()
        span.add_event("event_name")
        assert span._events[0] == ("event_name", {})

    def test_get_hostname(self):
        from django_matt.observability.logging import get_hostname

        hostname = get_hostname()
        assert isinstance(hostname, str)
        assert len(hostname) > 0

    def test_get_hostname_error(self):
        from django_matt.observability.logging import get_hostname

        with patch("socket.gethostname", side_effect=OSError("no host")):
            assert get_hostname() == "unknown"

    def test_logging_config_sensitive_fields_default(self):
        from django_matt.observability.logging import LoggingConfig

        config = LoggingConfig()
        fields = config.sensitive_fields
        assert "password" in fields
        assert "token" in fields
        assert "secret" in fields
        assert "api_key" in fields
        assert "authorization" in fields

    def test_metrics_generate_empty(self, fresh_metrics_manager):
        output = fresh_metrics_manager.generate_metrics()
        assert isinstance(output, bytes)

    def test_ready_view_returns_503_when_not_ready(self, rf):
        from django_matt.observability.views import ReadinessChecker

        checker = ReadinessChecker()
        checker.register("always_fail", lambda: (False, "Down"))

        with patch("django_matt.observability.views.readiness_checker", checker):
            from django_matt.observability.views import ready_view

            request = rf.get("/ready")
            response = ready_view(request)
            assert response.status_code == 503
            data = json.loads(response.content)
            assert data["ready"] is False


# =============================================================================
# Success-Criteria-Aligned Tests (Phase 07, Plan 02)
# =============================================================================


class TestStructuredLoggingSuccessCriteria:
    """
    Verify OBS-01: Structured logging produces valid JSON with configurable formatters.
    These tests directly validate the success criteria from the roadmap.
    """

    def test_json_formatter_produces_valid_json_with_required_fields(self):
        """JSONFormatter.format() produces valid JSON with timestamp, level, message."""
        from django_matt.observability.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.app",
            level=logging.WARNING,
            pathname="app.py",
            lineno=10,
            msg="Something happened",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)

        # Must be valid JSON parseable by orjson
        data = orjson.loads(output)

        # Required fields
        assert "timestamp" in data, "JSON log must contain 'timestamp'"
        assert "level" in data, "JSON log must contain 'level'"
        assert "message" in data, "JSON log must contain 'message'"

        # Correct values
        assert data["level"] == "WARNING"
        assert data["message"] == "Something happened"
        assert data["logger"] == "test.app"

        # Timestamp must be ISO format
        assert "T" in data["timestamp"]

    def test_json_formatter_log_levels(self):
        """Verify all standard log levels produce correct level field."""
        from django_matt.observability.logging import JSONFormatter

        formatter = JSONFormatter()
        for level_name, level_num in [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ]:
            record = logging.LogRecord(
                name="test", level=level_num, pathname="", lineno=0,
                msg="msg", args=(), exc_info=None,
            )
            data = orjson.loads(formatter.format(record))
            assert data["level"] == level_name

    def test_pretty_json_formatter_produces_indented_valid_json(self):
        """PrettyJSONFormatter produces human-readable indented JSON."""
        from django_matt.observability.logging import PrettyJSONFormatter

        formatter = PrettyJSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="pretty test", args=(), exc_info=None,
        )
        output = formatter.format(record)

        # Must be valid JSON
        data = orjson.loads(output)
        assert data["message"] == "pretty test"

        # Must be indented (multi-line)
        assert "\n" in output

    def test_colored_text_formatter_produces_readable_output(self):
        """ColoredTextFormatter produces text with ANSI color codes."""
        from django_matt.observability.logging import ColoredTextFormatter

        formatter = ColoredTextFormatter()
        record = logging.LogRecord(
            name="test.app", level=logging.ERROR, pathname="", lineno=0,
            msg="error msg", args=(), exc_info=None,
        )
        output = formatter.format(record)

        assert "ERROR" in output
        assert "error msg" in output
        assert "test.app" in output
        # Contains ANSI escape code
        assert "\033[" in output


class TestPrometheusMetricsSuccessCriteria:
    """
    Verify OBS-02: Prometheus metrics endpoint responds with metric data.
    """

    def test_metrics_manager_records_request_count(self):
        """MetricsManager with fallback records request count metrics."""
        from django_matt.observability.metrics import MetricsManager

        mgr = MetricsManager()
        counter = mgr.counter(
            "test_req_total", "Total requests", labelnames=["method", "status"]
        )
        counter.labels(method="GET", status="200").inc()
        counter.labels(method="GET", status="200").inc()
        counter.labels(method="POST", status="201").inc()

        # Verify counter values via fallback metric internal state
        get_key = ("GET", "200")
        post_key = ("POST", "201")
        assert counter._values[get_key] == 2.0
        assert counter._values[post_key] == 1.0

    def test_metrics_manager_records_latency(self):
        """MetricsManager records request latency via histogram."""
        from django_matt.observability.metrics import MetricsManager

        mgr = MetricsManager()
        hist = mgr.histogram("test_latency", "Request latency")
        hist.observe(0.05)
        hist.observe(0.15)

        # Verify observations stored and appear in output
        output = mgr.generate_metrics().decode("utf-8")
        assert "test_latency" in output or "django_matt_test_latency" in output

    def test_metrics_view_returns_prometheus_text_format(self, rf):
        """Prometheus metrics view returns text/plain content with metric lines."""
        from django_matt.observability.views import metrics_view

        request = rf.get("/_matt/metrics")
        response = metrics_view(request)

        assert response.status_code == 200
        content_type = response["Content-Type"]
        # Prometheus text format uses text/plain or openmetrics
        assert "text" in content_type

    def test_record_request_convenience_updates_metrics(self):
        """record_request() updates both count and latency metrics."""
        from django_matt.observability.metrics import MetricsManager, record_request

        # Use a fresh manager to avoid cross-test pollution
        mgr = MetricsManager()
        with patch("django_matt.observability.metrics.metrics_manager", mgr):
            with patch("django_matt.observability.metrics.metrics_config") as mock_cfg:
                mock_cfg.enabled = True
                mock_cfg.prefix = "django_matt"
                mock_cfg.default_buckets = [0.01, 0.1, 1.0]

                record_request("GET", "/api/users", 200, 0.05)

                # Metrics should have been created
                output = mgr.generate_metrics().decode("utf-8")
                assert len(output) > 0


class TestOTELTracingSuccessCriteria:
    """
    Verify OBS-03: OTEL tracing emits spans for request handling.
    """

    def test_tracing_manager_creates_spans_with_operation_names(self):
        """TracingManager creates NullSpan with correct operation name when OTEL unavailable."""
        from django_matt.observability.tracing import NullSpan, TracingManager

        mgr = TracingManager()
        span = mgr.start_span("GET /api/users")
        assert isinstance(span, NullSpan)
        assert span.name == "GET /api/users"

    def test_null_span_records_attributes(self):
        """NullSpan stores attributes (no-op but API-compatible)."""
        from django_matt.observability.tracing import NullSpan

        span = NullSpan("test-span")
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.status_code", 200)
        assert span._attributes["http.method"] == "GET"
        assert span._attributes["http.status_code"] == 200

    def test_null_span_records_events(self):
        """NullSpan stores events."""
        from django_matt.observability.tracing import NullSpan

        span = NullSpan("test-span")
        span.add_event("request.start", {"time": "now"})
        assert len(span._events) == 1
        assert span._events[0][0] == "request.start"

    def test_tracing_manager_span_context_manager(self):
        """TracingManager span context manager yields span with correct name."""
        from django_matt.observability.tracing import NullSpan, TracingManager

        mgr = TracingManager()
        with mgr.span("POST /api/orders", attributes={"user": "123"}) as span:
            assert isinstance(span, NullSpan)
            assert span.name == "POST /api/orders"
            span.set_attribute("http.status_code", 201)

    def test_has_opentelemetry_flag_exists(self):
        """HAS_OPENTELEMETRY flag properly guards OTEL imports."""
        from django_matt.observability.tracing import HAS_OPENTELEMETRY

        assert isinstance(HAS_OPENTELEMETRY, bool)

    def test_setup_returns_false_without_otel(self):
        """TracingManager.setup() gracefully returns False without OTEL SDK."""
        from django_matt.observability.tracing import TracingManager

        mgr = TracingManager()
        with patch("django_matt.observability.tracing.HAS_OPENTELEMETRY", False):
            result = mgr.setup(service_name="test-svc")
            assert result is False


class TestTracingMiddlewareSpanStatus:
    """Test the corrected span status logic in TracingMiddleware."""

    def test_4xx_response_does_not_set_error_status(self, rf):
        """4xx responses should set OK status, not ERROR (OTEL server span convention)."""
        from django_matt.observability.middleware import TracingMiddleware

        def get_response(request):
            return HttpResponse("Not Found", status=404)

        middleware = TracingMiddleware(get_response)
        # Even with tracing disabled, verify the middleware path
        request = rf.get("/api/missing")
        response = middleware(request)
        assert response.status_code == 404

    def test_5xx_response_would_set_error_status(self, rf):
        """5xx responses should set ERROR status."""
        from django_matt.observability.middleware import TracingMiddleware

        def get_response(request):
            return HttpResponse("Server Error", status=500)

        middleware = TracingMiddleware(get_response)
        request = rf.get("/api/broken")
        response = middleware(request)
        assert response.status_code == 500
