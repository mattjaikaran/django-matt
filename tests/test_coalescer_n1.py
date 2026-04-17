"""Tests for query coalescer and N+1 detection."""

from __future__ import annotations

from collections import Counter

import pytest

from django_matt.batch.n_plus_one import NPlusOneWarning, QueryPatternTracker


# ──────────────────────────────────────────────
# QueryPatternTracker
# ──────────────────────────────────────────────


class TestQueryPatternTracker:
    def test_normalize_integers(self):
        tracker = QueryPatternTracker()
        result = tracker._normalize("SELECT * FROM users WHERE id = 42")
        assert "42" not in result
        assert "?" in result

    def test_normalize_strings(self):
        tracker = QueryPatternTracker()
        result = tracker._normalize("SELECT * FROM users WHERE name = 'Matt'")
        assert "Matt" not in result
        assert "?" in result

    def test_same_pattern_different_values(self):
        tracker = QueryPatternTracker()
        # Simulate execute wrapper calls
        tracker._patterns[tracker._normalize("SELECT * FROM users WHERE id = 1")] += 1
        tracker._patterns[tracker._normalize("SELECT * FROM users WHERE id = 2")] += 1
        tracker._patterns[tracker._normalize("SELECT * FROM users WHERE id = 3")] += 1

        # All should normalize to same pattern
        assert len(tracker._patterns) == 1
        pattern = list(tracker._patterns.keys())[0]
        assert tracker._patterns[pattern] == 3

    def test_get_duplicates_above_threshold(self):
        tracker = QueryPatternTracker()
        pattern = "SELECT * FROM products WHERE id = ?"
        tracker._patterns[pattern] = 10

        duplicates = tracker.get_duplicates(threshold=5)
        assert len(duplicates) == 1
        assert duplicates[0] == (pattern, 10)

    def test_get_duplicates_below_threshold(self):
        tracker = QueryPatternTracker()
        pattern = "SELECT * FROM products WHERE id = ?"
        tracker._patterns[pattern] = 3

        duplicates = tracker.get_duplicates(threshold=5)
        assert len(duplicates) == 0

    def test_total_queries(self):
        tracker = QueryPatternTracker()
        tracker._patterns["SELECT ?"] = 5
        tracker._patterns["INSERT ?"] = 3
        assert tracker.total_queries == 8

    def test_unique_patterns(self):
        tracker = QueryPatternTracker()
        tracker._patterns["SELECT ?"] = 5
        tracker._patterns["INSERT ?"] = 3
        assert tracker.unique_patterns == 2

    def test_track_function_records_query(self):
        tracker = QueryPatternTracker()
        executed = []

        def mock_execute(sql, params, many, context):
            executed.append(sql)
            return None

        tracker.track(mock_execute, "SELECT * FROM users WHERE id = 1", None, False, None)
        tracker.track(mock_execute, "SELECT * FROM users WHERE id = 2", None, False, None)

        assert len(executed) == 2
        assert tracker.total_queries == 2
        assert tracker.unique_patterns == 1  # same pattern

    def test_different_queries_stay_separate(self):
        tracker = QueryPatternTracker()

        def mock_execute(sql, params, many, context):
            return None

        tracker.track(mock_execute, "SELECT * FROM users WHERE id = 1", None, False, None)
        tracker.track(mock_execute, "SELECT * FROM orders WHERE user_id = 1", None, False, None)

        assert tracker.unique_patterns == 2

    def test_duplicates_sorted_by_count(self):
        tracker = QueryPatternTracker()
        tracker._patterns["pattern_a"] = 10
        tracker._patterns["pattern_b"] = 20
        tracker._patterns["pattern_c"] = 5

        duplicates = tracker.get_duplicates(threshold=5)
        assert len(duplicates) == 3
        assert duplicates[0][1] == 20  # highest first
        assert duplicates[1][1] == 10
        assert duplicates[2][1] == 5


class TestNPlusOneWarning:
    def test_warning_message(self):
        w = NPlusOneWarning("SELECT * FROM x WHERE id = ?", 47)
        assert "47" in str(w)
        assert w.pattern == "SELECT * FROM x WHERE id = ?"
        assert w.count == 47


# ──────────────────────────────────────────────
# QueryCoalescer (unit tests — no DB)
# ──────────────────────────────────────────────


class TestQueryCoalescerUnit:
    def test_stats_initial(self):
        from django_matt.batch.coalescer import QueryCoalescer

        c = QueryCoalescer()
        assert c.stats == {"coalesced_queries": 0, "total_loads": 0}

    def test_reset_stats(self):
        from django_matt.batch.coalescer import QueryCoalescer

        c = QueryCoalescer()
        c._stats["total_loads"] = 10
        c.reset_stats()
        assert c.stats["total_loads"] == 0
