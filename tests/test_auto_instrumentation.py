from __future__ import annotations

import asyncio
import io
import time

import pytest

from django_matt.observability.auto import AutoInstrumentor, reset_instrumentation
from django_matt.observability.collectors import (
    CacheMetricsCollector,
    DatabaseMetricsCollector,
    MetricsRegistry,
    RequestMetricsCollector,
    metrics_registry,
)
from django_matt.observability.exporters import (
    ConsoleExporter,
    JSONExporter,
    MultiExporter,
)
from django_matt.observability.setup import (
    get_metrics_snapshot,
    setup_observability,
    shutdown_observability,
)
from django_matt.observability.spans import (
    Span,
    SpanStatus,
    add_span_listener,
    aspan,
    get_current_span,
    remove_span_listener,
    span,
    traced,
)

# -- Span tests --


class TestSpan:
    def test_span_creation(self):
        s = Span(name="test")
        assert s.name == "test"
        assert s.status == SpanStatus.UNSET
        assert s.end_time is None
        assert s.tags == {}
        assert s.children == []

    def test_span_finish(self):
        s = Span(name="test")
        s.finish()
        assert s.end_time is not None
        assert s.status == SpanStatus.OK
        assert s.duration_ms >= 0

    def test_span_set_error(self):
        s = Span(name="test")
        exc = ValueError("bad value")
        s.set_error(exc)
        assert s.status == SpanStatus.ERROR
        assert s.error is exc
        assert s.tags["error"] is True
        assert s.tags["error.type"] == "ValueError"
        assert s.tags["error.message"] == "bad value"

    def test_span_set_tags(self):
        s = Span(name="test")
        s.set_tag("key1", "val1")
        s.set_tags({"key2": "val2", "key3": 3})
        assert s.tags == {"key1": "val1", "key2": "val2", "key3": 3}

    def test_span_to_dict(self):
        s = Span(name="test")
        s.set_tag("foo", "bar")
        s.finish()
        d = s.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "ok"
        assert d["tags"] == {"foo": "bar"}
        assert "duration_ms" in d
        assert "children" not in d

    def test_span_to_dict_with_children(self):
        parent = Span(name="parent")
        child = Span(name="child", _parent=parent)
        parent.children.append(child)
        child.finish()
        parent.finish()
        d = parent.to_dict()
        assert len(d["children"]) == 1
        assert d["children"][0]["name"] == "child"

    def test_span_to_dict_with_error(self):
        s = Span(name="test")
        s.set_error(RuntimeError("boom"))
        s.finish()
        d = s.to_dict()
        assert d["error"]["type"] == "RuntimeError"
        assert d["error"]["message"] == "boom"

    def test_span_duration_while_running(self):
        s = Span(name="test")
        time.sleep(0.01)
        assert s.duration_ms > 0
        assert s.end_time is None


class TestSpanContextManager:
    def test_sync_span(self):
        with span("test-op") as s:
            assert get_current_span() is s
            assert s.name == "test-op"
        assert get_current_span() is None
        assert s.status == SpanStatus.OK
        assert s.end_time is not None

    def test_sync_span_with_tags(self):
        with span("test-op", tags={"key": "val"}) as s:
            assert s.tags["key"] == "val"

    def test_sync_span_error(self):
        with pytest.raises(ValueError, match="oops"), span("test-op") as s:
            raise ValueError("oops")
        assert s.status == SpanStatus.ERROR
        assert s.error is not None

    def test_nested_spans(self):
        with span("parent") as parent_span:
            assert get_current_span() is parent_span
            with span("child") as child_span:
                assert get_current_span() is child_span
            assert get_current_span() is parent_span
        assert get_current_span() is None
        assert len(parent_span.children) == 1
        assert parent_span.children[0] is child_span

    @pytest.mark.asyncio
    async def test_async_span(self):
        async with aspan("async-op") as s:
            assert get_current_span() is s
        assert get_current_span() is None
        assert s.status == SpanStatus.OK

    @pytest.mark.asyncio
    async def test_async_span_error(self):
        with pytest.raises(RuntimeError, match="async boom"):
            async with aspan("async-op") as s:
                raise RuntimeError("async boom")
        assert s.status == SpanStatus.ERROR

    def test_span_listener(self):
        collected: list[Span] = []
        add_span_listener(collected.append)
        try:
            with span("listened"):
                pass
            assert len(collected) == 1
            assert collected[0].name == "listened"
        finally:
            remove_span_listener(collected.append)

    def test_nested_span_listener_fires_once(self):
        collected: list[Span] = []
        add_span_listener(collected.append)
        try:
            with span("parent"), span("child"):
                pass
            assert len(collected) == 1
            assert collected[0].name == "parent"
            assert len(collected[0].children) == 1
        finally:
            remove_span_listener(collected.append)


class TestTracedDecorator:
    def test_sync_traced(self):
        @traced("my-func")
        def my_func(x: int) -> int:
            return x * 2

        collected: list[Span] = []
        add_span_listener(collected.append)
        try:
            result = my_func(5)
            assert result == 10
            assert len(collected) == 1
            assert collected[0].name == "my-func"
        finally:
            remove_span_listener(collected.append)

    @pytest.mark.asyncio
    async def test_async_traced(self):
        @traced("async-func")
        async def my_func(x: int) -> int:
            return x * 3

        collected: list[Span] = []
        add_span_listener(collected.append)
        try:
            result = await my_func(4)
            assert result == 12
            assert len(collected) == 1
            assert collected[0].name == "async-func"
        finally:
            remove_span_listener(collected.append)

    def test_traced_preserves_exception(self):
        @traced("failing")
        def failing():
            raise ValueError("fail")

        with pytest.raises(ValueError, match="fail"):
            failing()

    def test_traced_default_name(self):
        @traced()
        def some_function():
            return 42

        collected: list[Span] = []
        add_span_listener(collected.append)
        try:
            some_function()
            assert collected[0].name.endswith("some_function")
        finally:
            remove_span_listener(collected.append)


# -- Collector tests --


class TestRequestMetricsCollector:
    def test_record_and_collect(self):
        c = RequestMetricsCollector()
        c.record("GET", "/api/users", 200, 0.05)
        c.record("POST", "/api/users", 201, 0.1)
        c.record("GET", "/api/users", 500, 0.5)

        data = c.collect()
        assert data["total_requests"] == 3
        assert data["error_count"] == 1
        assert data["by_method"]["GET"] == 2
        assert data["by_method"]["POST"] == 1
        assert data["by_status"][200] == 1
        assert data["by_status"][500] == 1
        assert data["duration"]["count"] == 3
        assert data["duration"]["avg_ms"] > 0

    def test_error_rate(self):
        c = RequestMetricsCollector()
        c.record("GET", "/", 200, 0.01)
        c.record("GET", "/", 500, 0.01)
        data = c.collect()
        assert data["error_rate"] == pytest.approx(0.5)

    def test_reset(self):
        c = RequestMetricsCollector()
        c.record("GET", "/", 200, 0.01)
        c.reset()
        data = c.collect()
        assert data["total_requests"] == 0


class TestDatabaseMetricsCollector:
    def test_record_and_collect(self):
        c = DatabaseMetricsCollector(slow_query_threshold_ms=50.0)
        c.record("SELECT", "users", 0.01, "SELECT * FROM users")
        c.record("INSERT", "users", 0.02, "INSERT INTO users ...")
        c.record("SELECT", "orders", 0.1, "SELECT * FROM orders")  # slow

        data = c.collect()
        assert data["total_queries"] == 3
        assert data["by_operation"]["SELECT"] == 2
        assert data["by_operation"]["INSERT"] == 1
        assert len(data["slow_queries"]) == 1
        assert data["slow_queries"][0]["table"] == "orders"

    def test_reset(self):
        c = DatabaseMetricsCollector()
        c.record("SELECT", "t", 0.01)
        c.reset()
        assert c.collect()["total_queries"] == 0


class TestCacheMetricsCollector:
    def test_hit_miss_tracking(self):
        c = CacheMetricsCollector()
        c.record_hit(0.001)
        c.record_hit(0.001)
        c.record_miss(0.002)
        c.record_set(0.003)
        c.record_delete(0.001)

        data = c.collect()
        assert data["hits"] == 2
        assert data["misses"] == 1
        assert data["sets"] == 1
        assert data["deletes"] == 1
        assert data["hit_rate"] == pytest.approx(2 / 3)
        assert data["total_operations"] == 5

    def test_reset(self):
        c = CacheMetricsCollector()
        c.record_hit()
        c.reset()
        assert c.collect()["hits"] == 0


class TestMetricsRegistry:
    def test_register_and_collect(self):
        reg = MetricsRegistry()
        req = RequestMetricsCollector()
        db = DatabaseMetricsCollector()
        reg.register(req)
        reg.register(db)

        req.record("GET", "/", 200, 0.01)
        db.record("SELECT", "t", 0.01)

        data = reg.collect_all()
        assert "requests" in data
        assert "database" in data
        assert data["requests"]["total_requests"] == 1
        assert data["database"]["total_queries"] == 1

    def test_unregister(self):
        reg = MetricsRegistry()
        req = RequestMetricsCollector()
        reg.register(req)
        reg.unregister("requests")
        assert reg.get("requests") is None

    def test_reset_all(self):
        reg = MetricsRegistry()
        req = RequestMetricsCollector()
        reg.register(req)
        req.record("GET", "/", 200, 0.01)
        reg.reset_all()
        assert req.collect()["total_requests"] == 0


# -- Exporter tests --


class TestConsoleExporter:
    def test_export_basic(self):
        stream = io.StringIO()
        exporter = ConsoleExporter(stream=stream, color=False)
        s = Span(name="test-span")
        s.finish()
        exporter.export(s)
        output = stream.getvalue()
        assert "test-span" in output
        assert "[+]" in output

    def test_export_error_span(self):
        stream = io.StringIO()
        exporter = ConsoleExporter(stream=stream, color=False)
        s = Span(name="error-span")
        s.set_error(ValueError("bad"))
        s.finish()
        exporter.export(s)
        output = stream.getvalue()
        assert "[!]" in output
        assert "ValueError" in output

    def test_export_with_children(self):
        stream = io.StringIO()
        exporter = ConsoleExporter(stream=stream, color=False)
        parent = Span(name="parent")
        child = Span(name="child", _parent=parent)
        parent.children.append(child)
        child.finish()
        parent.finish()
        exporter.export(parent)
        output = stream.getvalue()
        assert "parent" in output
        assert "child" in output

    def test_export_with_tags(self):
        stream = io.StringIO()
        exporter = ConsoleExporter(stream=stream, color=False)
        s = Span(name="tagged")
        s.set_tag("method", "GET")
        s.finish()
        exporter.export(s)
        output = stream.getvalue()
        assert "method=GET" in output


class TestJSONExporter:
    def test_export_to_stream(self):
        stream = io.StringIO()
        exporter = JSONExporter(stream=stream)
        s = Span(name="json-test")
        s.finish()
        exporter.export(s)
        output = stream.getvalue()
        assert "json-test" in output
        assert "exported_at" in output

    def test_export_to_file(self, tmp_path):
        file_path = str(tmp_path / "spans.jsonl")
        exporter = JSONExporter(file_path=file_path)
        s = Span(name="file-test")
        s.finish()
        exporter.export(s)
        exporter.shutdown()
        with open(file_path) as f:
            content = f.read()
        assert "file-test" in content


class TestMultiExporter:
    def test_multi_export(self):
        s1 = io.StringIO()
        s2 = io.StringIO()
        multi = MultiExporter([
            ConsoleExporter(stream=s1, color=False),
            ConsoleExporter(stream=s2, color=False),
        ])
        s = Span(name="multi")
        s.finish()
        multi.export(s)
        assert "multi" in s1.getvalue()
        assert "multi" in s2.getvalue()

    def test_multi_handles_exporter_error(self):
        class BadExporter:
            def export(self, s):
                raise RuntimeError("export failed")
            def shutdown(self):
                pass

        stream = io.StringIO()
        multi = MultiExporter([BadExporter(), ConsoleExporter(stream=stream, color=False)])
        s = Span(name="resilient")
        s.finish()
        multi.export(s)
        assert "resilient" in stream.getvalue()


# -- Auto-instrumentor tests --


class TestAutoInstrumentor:
    def setup_method(self):
        reset_instrumentation()

    def test_instrumentor_creation(self):
        inst = AutoInstrumentor()
        assert inst.request_collector is not None
        assert inst.db_collector is not None
        assert inst.cache_collector is not None

    def test_instrument_controllers_idempotent(self):
        inst = AutoInstrumentor()
        inst.instrument_controllers()
        inst.instrument_controllers()  # should not raise

    def test_instrument_db_idempotent(self):
        inst = AutoInstrumentor()
        inst.instrument_db()
        inst.instrument_db()

    def test_instrument_cache_idempotent(self):
        inst = AutoInstrumentor()
        inst.instrument_cache()
        inst.instrument_cache()

    def test_instrument_http_idempotent(self):
        inst = AutoInstrumentor()
        inst.instrument_http()
        inst.instrument_http()


# -- Setup tests --


class TestSetupObservability:
    def setup_method(self):
        reset_instrumentation()

    def teardown_method(self):
        shutdown_observability()
        reset_instrumentation()

    def test_setup_with_custom_exporters(self):
        stream = io.StringIO()
        exporter = ConsoleExporter(stream=stream, color=False)
        inst = setup_observability(auto=False, exporters=[exporter])
        assert inst is not None

    def test_setup_auto_false_skips_instrumentation(self):
        inst = setup_observability(auto=False, exporters=[ConsoleExporter(color=False)])
        assert inst is not None

    def test_get_metrics_snapshot(self):
        setup_observability(auto=False, exporters=[ConsoleExporter(color=False)])
        snapshot = get_metrics_snapshot()
        assert isinstance(snapshot, dict)


# -- Integration tests --


class TestSpanExporterIntegration:
    def test_span_triggers_exporter(self):
        stream = io.StringIO()
        exporter = ConsoleExporter(stream=stream, color=False)
        add_span_listener(exporter.export)
        try:
            with span("integrated"):
                pass
            assert "integrated" in stream.getvalue()
        finally:
            remove_span_listener(exporter.export)

    @pytest.mark.asyncio
    async def test_async_span_triggers_exporter(self):
        stream = io.StringIO()
        exporter = ConsoleExporter(stream=stream, color=False)
        add_span_listener(exporter.export)
        try:
            async with aspan("async-integrated"):
                await asyncio.sleep(0.001)
            assert "async-integrated" in stream.getvalue()
        finally:
            remove_span_listener(exporter.export)

    def test_traced_decorator_triggers_exporter(self):
        stream = io.StringIO()
        exporter = ConsoleExporter(stream=stream, color=False)
        add_span_listener(exporter.export)
        try:
            @traced("decorated-op")
            def do_work():
                return 42

            result = do_work()
            assert result == 42
            assert "decorated-op" in stream.getvalue()
        finally:
            remove_span_listener(exporter.export)

    def test_json_exporter_with_nested_spans(self):
        stream = io.StringIO()
        exporter = JSONExporter(stream=stream)
        add_span_listener(exporter.export)
        try:
            with span("root"):
                with span("child-1"):
                    pass
                with span("child-2"), span("grandchild"):
                    pass
            output = stream.getvalue()
            assert "root" in output
            assert "child-1" in output
            assert "child-2" in output
            assert "grandchild" in output
        finally:
            remove_span_listener(exporter.export)

    def test_collector_records_during_span(self):
        req_collector = RequestMetricsCollector()
        req_collector.record("GET", "/test", 200, 0.05)
        req_collector.record("GET", "/test", 500, 0.1)

        data = req_collector.collect()
        assert data["total_requests"] == 2
        assert data["error_count"] == 1
        assert data["duration"]["p50_ms"] > 0
