"""
Tests for the native task engine loading module.
"""

import pytest

from django_matt.tasks_native.loading import (
    LazyBackendLoader,
    ModuleLoader,
    estimate_import_cost,
    get_enabled_features,
    get_import_impact,
    get_loader,
    is_admin_available,
    is_unfold_available,
)


class TestAvailabilityChecks:
    """Tests for availability check functions."""

    def test_is_admin_available(self):
        """Test admin availability check."""
        result = is_admin_available()
        assert isinstance(result, bool)

    def test_is_unfold_available(self):
        """Test Unfold availability check."""
        result = is_unfold_available()
        assert isinstance(result, bool)


class TestLazyBackendLoader:
    """Tests for LazyBackendLoader."""

    def test_reset(self):
        """Test reset clears cached backend."""
        LazyBackendLoader.reset()
        assert LazyBackendLoader._backend is None
        assert LazyBackendLoader._backend_type is None


class TestModuleLoader:
    """Tests for ModuleLoader."""

    def test_should_load_core(self):
        """Test core module should load."""
        loader = ModuleLoader()
        assert loader.should_load("core") is True

    def test_mark_loaded(self):
        """Test marking module as loaded."""
        loader = ModuleLoader()
        loader.mark_loaded("test_module")
        assert loader.is_loaded("test_module") is True

    def test_loaded_modules_empty(self):
        """Test loaded modules starts empty."""
        loader = ModuleLoader()
        assert len(loader.loaded_modules) == 0

    def test_loaded_modules_returns_copy(self):
        """Test loaded_modules returns a copy."""
        loader = ModuleLoader()
        loader.mark_loaded("test")
        modules = loader.loaded_modules
        modules.add("modified")
        assert "modified" not in loader.loaded_modules


class TestGetLoader:
    """Tests for get_loader."""

    def test_returns_module_loader(self):
        """Test get_loader returns ModuleLoader."""
        loader = get_loader()
        assert isinstance(loader, ModuleLoader)


class TestEnabledFeatures:
    """Tests for get_enabled_features."""

    def test_returns_set(self):
        """Test returns a set."""
        features = get_enabled_features()
        assert isinstance(features, set)

    def test_includes_core(self):
        """Test core is always included."""
        features = get_enabled_features()
        assert "core" in features

    def test_includes_registry(self):
        """Test registry is always included."""
        features = get_enabled_features()
        assert "registry" in features

    def test_includes_scheduling(self):
        """Test scheduling is always included."""
        features = get_enabled_features()
        assert "scheduling" in features

    def test_includes_retry(self):
        """Test retry is always included."""
        features = get_enabled_features()
        assert "retry" in features


class TestImportCostEstimates:
    """Tests for import cost estimation."""

    def test_estimate_import_cost_returns_dict(self):
        """Test returns a dictionary."""
        costs = estimate_import_cost()
        assert isinstance(costs, dict)

    def test_estimate_import_cost_has_core(self):
        """Test includes core module."""
        costs = estimate_import_cost()
        assert "core" in costs

    def test_estimate_import_cost_values_are_strings(self):
        """Test values are cost categories."""
        costs = estimate_import_cost()
        valid_categories = {"minimal", "moderate", "heavy"}
        for value in costs.values():
            assert value in valid_categories

    def test_get_import_impact_returns_dict(self):
        """Test returns a dictionary."""
        impact = get_import_impact()
        assert isinstance(impact, dict)

    def test_get_import_impact_values_are_ints(self):
        """Test values are KB estimates."""
        impact = get_import_impact()
        for value in impact.values():
            assert isinstance(value, int)
            assert value > 0
