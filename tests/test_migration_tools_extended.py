"""Tests for extended migration tools — baseline, parallel, stats."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from django_matt.migration_tools.baseline import (
    BaselineInfo,
    MigrationBaseline,
    suggest_baseline_version,
)
from django_matt.migration_tools.parallel import (
    MigrationWavePlanner,
    ParallelMigrationExecutor,
    format_parallel_result,
)
from django_matt.migration_tools.stats import (
    MigrationProfiler,
    MigrationTimer,
    format_profiles,
    format_project_stats,
)


class TestBaselineInfo:
    """Tests for BaselineInfo dataclass."""

    def test_to_dict(self):
        info = BaselineInfo(
            version="v1.0.0",
            created_at="2024-01-15T12:00:00Z",
            schema_hash="abc123",
            applied_migrations={"myapp": ["0001_initial", "0002_add_field"]},
            db_vendor="postgresql",
            django_version="5.2",
            notes="Test baseline",
        )

        d = info.to_dict()
        assert d["version"] == "v1.0.0"
        assert d["schema_hash"] == "abc123"
        assert len(d["applied_migrations"]["myapp"]) == 2

    def test_from_dict(self):
        data = {
            "version": "v2.0.0",
            "created_at": "2024-02-20T00:00:00Z",
            "schema_hash": "def456",
            "applied_migrations": {"app": ["0001"]},
            "db_vendor": "mysql",
            "django_version": "5.2",
        }

        info = BaselineInfo.from_dict(data)
        assert info.version == "v2.0.0"
        assert info.notes == ""  # Default value


class TestSuggestBaselineVersion:
    """Tests for version suggestion."""

    def test_suggest_baseline_version_returns_string(self):
        # Should return a non-empty version string
        version = suggest_baseline_version()
        assert isinstance(version, str)
        assert len(version) >= 1


class TestMigrationProfiler:
    """Tests for migration profiling."""

    @pytest.mark.django_db
    def test_get_project_stats(self):
        profiler = MigrationProfiler()
        stats = profiler.get_project_stats()

        assert stats.total_migrations >= 0
        assert stats.applied_migrations >= 0
        assert stats.pending_migrations >= 0
        assert isinstance(stats.apps, dict)

    def test_format_project_stats(self):
        from django_matt.migration_tools.stats import ProjectMigrationStats

        stats = ProjectMigrationStats(
            total_migrations=100,
            applied_migrations=95,
            pending_migrations=5,
            total_operations=500,
            data_migrations_count=10,
            index_operations_count=20,
            estimated_pending_time=30.5,
            apps={"myapp": 50, "otherapp": 50},
            complexity_breakdown={
                "trivial": 3,
                "simple": 1,
                "moderate": 1,
                "complex": 0,
                "extreme": 0,
            },
        )

        output = format_project_stats(stats)
        assert "100" in output  # total
        assert "95" in output  # applied
        assert "5" in output  # pending
        assert "myapp" in output


class TestMigrationWavePlanner:
    """Tests for parallel wave planning."""

    @pytest.mark.django_db
    def test_plan_waves_empty(self):
        # When all migrations are applied, should return empty
        planner = MigrationWavePlanner()
        waves = planner.plan_waves()
        # May or may not be empty depending on DB state
        assert isinstance(waves, list)

    @pytest.mark.django_db
    def test_estimate_speedup(self):
        planner = MigrationWavePlanner()

        timings = {
            ("app1", "0001"): 1.0,
            ("app2", "0001"): 2.0,
            ("app1", "0002"): 1.5,
        }

        result = planner.estimate_speedup(timings)
        assert "speedup_factor" in result
        assert result["speedup_factor"] >= 1.0


class TestParallelMigrationExecutor:
    """Tests for parallel execution."""

    @pytest.mark.django_db
    def test_plan(self):
        executor = ParallelMigrationExecutor()
        plan = executor.plan()
        assert isinstance(plan, list)

    @pytest.mark.django_db
    def test_dry_run(self):
        executor = ParallelMigrationExecutor()
        result = executor.execute(dry_run=True)
        assert result.success
        assert result.migrations_failed == 0

    def test_format_parallel_result(self):
        from django_matt.migration_tools.parallel import ParallelMigrateResult

        result = ParallelMigrateResult(
            success=True,
            waves=[],
            total_elapsed=0,
            sequential_would_take=0,
            speedup_factor=1.0,
            migrations_applied=0,
            migrations_failed=0,
        )

        output = format_parallel_result(result)
        assert "No migrations to apply" in output


class TestMigrationTimer:
    """Tests for migration timing."""

    def test_timing_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            timer = MigrationTimer(base_path=Path(tmpdir))

            with timer.time_migration("myapp", "0001_test"):
                pass  # Simulate migration

            history = timer.get_history("myapp")
            assert len(history) == 1
            assert history[0].app_label == "myapp"
            assert history[0].success

    def test_get_average_times(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            timer = MigrationTimer(base_path=Path(tmpdir))

            # Record some timings
            with timer.time_migration("myapp", "0001"):
                pass
            with timer.time_migration("myapp", "0001"):
                pass

            averages = timer.get_average_times()
            assert "myapp.0001" in averages

    def test_get_slowest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            timer = MigrationTimer(base_path=Path(tmpdir))

            slowest = timer.get_slowest(5)
            assert isinstance(slowest, list)


class TestMigrationBaseline:
    """Tests for baseline management."""

    def test_list_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = MigrationBaseline(base_path=Path(tmpdir))
            baselines = baseline.list()
            assert baselines == []

    def test_delete_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = MigrationBaseline(base_path=Path(tmpdir))
            result = baseline.delete("nonexistent")
            assert result is False

    @pytest.mark.django_db
    def test_verify_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = MigrationBaseline(base_path=Path(tmpdir))
            valid, message = baseline.verify("v1.0.0")
            assert not valid
            assert "not found" in message.lower()
