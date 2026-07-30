"""
Tests for the native task engine admin module.

Note: Database-dependent tests are skipped when tables don't exist.
Run with migrations applied for full test coverage.
"""

import pytest

from django_matt.tasks_native.admin.dashboard import (
    TaskDashboard,
    get_task_dashboard_callback,
    get_task_widgets,
)
from django_matt.tasks_native.admin.filters import (
    StateFilter,
)


class TestFilters:
    """Tests for admin filters."""

    def test_state_filter_lookups(self):
        """Test StateFilter provides all states."""
        filter_instance = StateFilter(None, {}, None, None)
        lookups = filter_instance.lookups(None, None)

        # Should have all task states
        assert len(lookups) == 8
        lookup_values = [lookup[0] for lookup in lookups]
        assert "pending" in lookup_values
        assert "completed" in lookup_values
        assert "failed" in lookup_values


class TestTaskDashboard:
    """Tests for TaskDashboard class structure."""

    def test_has_get_task_stats_method(self):
        """Test TaskDashboard has get_task_stats method."""
        assert hasattr(TaskDashboard, "get_task_stats")
        assert callable(TaskDashboard.get_task_stats)

    def test_has_get_queue_metrics_method(self):
        """Test TaskDashboard has get_queue_metrics method."""
        assert hasattr(TaskDashboard, "get_queue_metrics")
        assert callable(TaskDashboard.get_queue_metrics)

    def test_has_get_recent_failures_method(self):
        """Test TaskDashboard has get_recent_failures method."""
        assert hasattr(TaskDashboard, "get_recent_failures")
        assert callable(TaskDashboard.get_recent_failures)

    def test_has_get_upcoming_schedules_method(self):
        """Test TaskDashboard has get_upcoming_schedules method."""
        assert hasattr(TaskDashboard, "get_upcoming_schedules")
        assert callable(TaskDashboard.get_upcoming_schedules)


class TestDashboardCallback:
    """Tests for dashboard callback."""

    def test_callback_creation(self):
        """Test callback can be created."""
        callback = get_task_dashboard_callback()
        assert callable(callback)

    def test_callback_accepts_request_and_context(self):
        """Test callback signature accepts request and context."""
        import inspect

        callback = get_task_dashboard_callback()
        sig = inspect.signature(callback)
        params = list(sig.parameters.keys())

        assert len(params) == 2
        assert "request" in params
        assert "context" in params


class TestDashboardWidgets:
    """Tests for dashboard widgets function."""

    def test_get_task_widgets_callable(self):
        """Test get_task_widgets is callable."""
        assert callable(get_task_widgets)

    def test_get_task_widgets_returns_list(self):
        """Test get_task_widgets returns a list (may be empty without DB)."""
        # May return empty list if DB tables don't exist
        widgets = get_task_widgets()
        assert isinstance(widgets, list)
