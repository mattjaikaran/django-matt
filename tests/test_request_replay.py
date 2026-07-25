"""Tests for request replay debugging."""

from __future__ import annotations

import json

import pytest

from django_matt.inspector.replay.player import (
    QueryDiff,
    ReplayResult,
    RequestReplayer,
    ResponseDiff,
)
from django_matt.inspector.replay.recorder import (
    QueryRecord,
    RequestRecorder,
    RequestTrace,
    TimingRecord,
    _QueryTracker,
)

# ──────────────────────────────────────────────
# RequestTrace serialization
# ──────────────────────────────────────────────


class TestRequestTrace:
    def test_roundtrip_json(self):
        trace = RequestTrace(
            trace_id="abc123",
            method="POST",
            path="/api/users",
            body=b'{"name": "Matt"}',
            status_code=201,
            response_body=b'{"id": 1}',
            queries=[QueryRecord(sql="SELECT 1", params=[], duration_ms=0.5)],
            timing=TimingRecord(total_ms=42.0, db_ms=0.5),
        )
        data = trace.to_json()
        restored = RequestTrace.from_json(data)

        assert restored.trace_id == "abc123"
        assert restored.method == "POST"
        assert restored.body == b'{"name": "Matt"}'
        assert restored.response_body == b'{"id": 1}'
        assert len(restored.queries) == 1
        assert restored.queries[0].sql == "SELECT 1"
        assert restored.timing.total_ms == 42.0

    def test_empty_body_roundtrip(self):
        trace = RequestTrace(trace_id="empty", method="GET", path="/")
        data = trace.to_json()
        restored = RequestTrace.from_json(data)
        assert restored.body == b""
        assert restored.response_body == b""

    def test_defaults(self):
        trace = RequestTrace()
        assert trace.trace_id == ""
        assert trace.queries == []
        assert trace.timing.total_ms == 0.0


# ──────────────────────────────────────────────
# QueryTracker
# ──────────────────────────────────────────────


class TestQueryTracker:
    def test_captures_queries(self):
        tracker = _QueryTracker()
        executed = []

        def mock_execute(sql, params, many, context):
            executed.append(sql)

        tracker(mock_execute, "SELECT 1", None, False, None)
        tracker(mock_execute, "SELECT 2", None, False, None)

        assert len(tracker.queries) == 2
        assert tracker.queries[0].sql == "SELECT 1"
        assert tracker.queries[1].sql == "SELECT 2"
        assert tracker._total_ms > 0

    def test_captures_duration(self):
        tracker = _QueryTracker()

        def slow_execute(sql, params, many, context):
            import time

            time.sleep(0.01)

        tracker(slow_execute, "SELECT 1", None, False, None)
        assert tracker.queries[0].duration_ms >= 5  # at least 5ms


# ──────────────────────────────────────────────
# QueryDiff
# ──────────────────────────────────────────────


class TestQueryDiff:
    def test_identical_queries(self):
        original = [QueryRecord(sql="SELECT * FROM users WHERE id = 1")]
        replayed = [QueryRecord(sql="SELECT * FROM users WHERE id = 2")]

        replayer = RequestReplayer()
        diff = replayer._diff_queries(original, replayed)

        assert diff.original_count == 1
        assert diff.replayed_count == 1
        assert diff.new_queries == []  # same pattern after normalization
        assert diff.missing_queries == []

    def test_new_query_detected(self):
        original = [QueryRecord(sql="SELECT * FROM users WHERE id = 1")]
        replayed = [
            QueryRecord(sql="SELECT * FROM users WHERE id = 1"),
            QueryRecord(sql="SELECT * FROM orders WHERE user_id = 1"),
        ]

        replayer = RequestReplayer()
        diff = replayer._diff_queries(original, replayed)

        assert len(diff.new_queries) == 1
        assert "orders" in diff.new_queries[0]

    def test_missing_query_detected(self):
        original = [
            QueryRecord(sql="SELECT * FROM users"),
            QueryRecord(sql="SELECT * FROM orders"),
        ]
        replayed = [QueryRecord(sql="SELECT * FROM users")]

        replayer = RequestReplayer()
        diff = replayer._diff_queries(original, replayed)

        assert len(diff.missing_queries) == 1


# ──────────────────────────────────────────────
# ResponseDiff
# ──────────────────────────────────────────────


class TestResponseDiff:
    def test_defaults(self):
        diff = ResponseDiff()
        assert diff.status_changed is False
        assert diff.body_changed is False
        assert diff.headers_changed == []


# ──────────────────────────────────────────────
# ReplayResult
# ──────────────────────────────────────────────


class TestReplayResult:
    def test_defaults(self):
        result = ReplayResult(trace_id="test")
        assert result.success is True
        assert result.error == ""

    def test_with_error(self):
        result = ReplayResult(trace_id="test", success=False, error="boom")
        assert result.success is False


# ──────────────────────────────────────────────
# RequestReplayer._build_request
# ──────────────────────────────────────────────


class TestRequestReplayerBuild:
    def test_build_get_request(self):
        replayer = RequestReplayer()
        trace = RequestTrace(
            method="GET",
            path="/api/users",
            query_string="page=1",
            headers={"accept": "application/json"},
        )
        request = replayer._build_request(trace)
        assert request.method == "GET"
        assert "page=1" in request.META.get("QUERY_STRING", "")

    def test_build_post_request(self):
        replayer = RequestReplayer()
        trace = RequestTrace(
            method="POST",
            path="/api/users",
            body=b'{"name": "Matt"}',
            headers={"content-type": "application/json"},
        )
        request = replayer._build_request(trace)
        assert request.method == "POST"
        assert request.body == b'{"name": "Matt"}'

    def test_build_preserves_headers(self):
        replayer = RequestReplayer()
        trace = RequestTrace(
            method="GET",
            path="/",
            headers={"x-custom": "value", "authorization": "Bearer token"},
        )
        request = replayer._build_request(trace)
        assert request.META.get("HTTP_X_CUSTOM") == "value"
        assert request.META.get("HTTP_AUTHORIZATION") == "Bearer token"
