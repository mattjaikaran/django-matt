"""Tests for flaky detection and test replay archives."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from django_matt.testing.smart.flaky import FlakyDetector, FlakyRecord
from django_matt.testing.smart.recorder import TestRecorder, TestReplayer

# ──────────────────────────────────────────────
# FlakyDetector
# ──────────────────────────────────────────────


class TestFlakyDetector:
    @pytest.fixture
    def detector(self, tmp_path):
        db_path = tmp_path / "test_flaky.db"
        d = FlakyDetector(db_path)
        yield d
        d.close()

    def test_record_pass(self, detector):
        detector.record_outcome("test::foo", passed=True)
        flaky = detector.get_flaky_tests()
        assert len(flaky) == 0  # only passes — not flaky

    def test_record_fail(self, detector):
        detector.record_outcome("test::foo", passed=False, traceback="Error!")
        flaky = detector.get_flaky_tests()
        assert len(flaky) == 0  # only fails — not flaky (just broken)

    def test_mixed_outcomes_is_flaky(self, detector):
        detector.record_outcome("test::foo", passed=True)
        detector.record_outcome("test::foo", passed=False, traceback="Sometimes fails")
        flaky = detector.get_flaky_tests()
        assert len(flaky) == 1
        assert flaky[0].test_id == "test::foo"
        assert flaky[0].is_flaky is True
        assert flaky[0].failure_rate == 0.5

    def test_failure_rate_calculation(self, detector):
        for _ in range(7):
            detector.record_outcome("test::bar", passed=True)
        for _ in range(3):
            detector.record_outcome("test::bar", passed=False, traceback="Flaky!")
        flaky = detector.get_flaky_tests()
        assert len(flaky) == 1
        assert flaky[0].total_runs == 10
        assert flaky[0].failure_rate == pytest.approx(0.3)

    def test_quarantined_ids(self, detector):
        detector.record_outcome("test::a", passed=True)
        detector.record_outcome("test::a", passed=False)
        detector.record_outcome("test::b", passed=True)
        ids = detector.get_quarantined_ids()
        assert "test::a" in ids
        assert "test::b" not in ids

    def test_stress_results(self, detector):
        for i in range(10):
            detector.record_stress_result(
                "test::stress", run_index=i, passed=(i % 3 != 0), duration_ms=50.0 + i
            )
        summary = detector.get_stress_summary("test::stress")
        assert summary["total_runs"] == 10
        assert summary["failed"] == 4  # indices 0, 3, 6, 9
        assert summary["is_flaky"] is True
        assert summary["avg_duration_ms"] > 0

    def test_stress_summary_empty(self, detector):
        summary = detector.get_stress_summary("nonexistent")
        assert summary["total_runs"] == 0

    def test_clear(self, detector):
        detector.record_outcome("test::x", passed=True)
        detector.record_outcome("test::x", passed=False)
        detector.clear()
        assert len(detector.get_flaky_tests()) == 0


# ──────────────────────────────────────────────
# TestRecorder + TestReplayer
# ──────────────────────────────────────────────


class TestRecorder_:
    def test_record_and_save(self, tmp_path):
        archive = tmp_path / "run.zip"
        recorder = TestRecorder(archive)
        recorder.record_start("test::a")
        recorder.record_pass("test::a", duration_ms=42.0, stdout="output")
        recorder.record_start("test::b")
        recorder.record_fail("test::b", duration_ms=100.0, traceback="AssertionError")
        recorder.record_start("test::c")
        recorder.record_skip("test::c", reason="skip reason")

        saved = recorder.save()
        assert saved.exists()
        assert zipfile.is_zipfile(saved)

    def test_archive_contains_meta(self, tmp_path):
        archive = tmp_path / "run.zip"
        recorder = TestRecorder(archive)
        recorder.record_pass("test::a", duration_ms=10.0)
        recorder.save()

        with zipfile.ZipFile(archive) as zf:
            meta = json.loads(zf.read("meta.json"))
            assert "python_version" in meta
            assert meta["total_tests"] == 1
            assert meta["passed"] == 1

    def test_archive_contains_events(self, tmp_path):
        archive = tmp_path / "run.zip"
        recorder = TestRecorder(archive)
        recorder.record_pass("test::a", duration_ms=10.0)
        recorder.record_fail("test::b", duration_ms=20.0, traceback="Error")
        recorder.save()

        with zipfile.ZipFile(archive) as zf:
            events_raw = zf.read("events.ndjson").decode()
            events = [json.loads(line) for line in events_raw.strip().split("\n")]
            assert len(events) == 2
            assert events[0]["event"] == "test_pass"
            assert events[1]["event"] == "test_fail"


class TestReplayer_:
    @pytest.fixture
    def archive(self, tmp_path):
        path = tmp_path / "replay.zip"
        recorder = TestRecorder(path)
        recorder.record_pass("test::ok", duration_ms=10.0, stdout="all good")
        recorder.record_fail(
            "test::broken", duration_ms=50.0, traceback="AssertionError: bad", stderr="err"
        )
        recorder.record_skip("test::skipped")
        recorder.save()
        return path

    def test_metadata(self, archive):
        replayer = TestReplayer(archive)
        meta = replayer.metadata
        assert meta.total_tests == 3
        assert meta.passed == 1
        assert meta.failed == 1
        assert meta.skipped == 1

    def test_get_failed_test_ids(self, archive):
        replayer = TestReplayer(archive)
        failed = replayer.get_failed_test_ids()
        assert failed == ["test::broken"]

    def test_get_test_output(self, archive):
        replayer = TestReplayer(archive)
        output = replayer.get_test_output("test::broken")
        assert "AssertionError" in output.get("traceback", "")
        assert "err" in output.get("stderr", "")

    def test_summary(self, archive):
        replayer = TestReplayer(archive)
        summary = replayer.summary()
        assert summary["total_tests"] == 3
        assert summary["failed"] == 1
        assert "python_version" in summary

    def test_events(self, archive):
        replayer = TestReplayer(archive)
        events = replayer.events
        assert len(events) == 3
        event_types = [e.event for e in events]
        assert "test_pass" in event_types
        assert "test_fail" in event_types
        assert "test_skip" in event_types
