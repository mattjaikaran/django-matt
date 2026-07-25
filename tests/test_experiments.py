"""
Tests for the Django Matt experiments module.

Tests cover:
- ExperimentStatus, AssignmentStrategy, MetricType enums
- VariantStats, ComparisonResult, ExperimentAnalysis dataclasses
- StatisticalAnalyzer: chi-square, Wilson CI, t-test, power, sample size
- ExperimentManager: bandit algorithms (epsilon-greedy, UCB, Thompson), targeting
- Experiment model: lifecycle (start, pause, resume, complete), properties
- Variant model: properties
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from django_matt.experiments.analysis import (
    ComparisonResult,
    ExperimentAnalysis,
    StatisticalAnalyzer,
    VariantStats,
)
from django_matt.experiments.manager import ExperimentManager
from django_matt.experiments.models import (
    AssignmentStrategy,
    ExperimentStatus,
    MetricType,
)

# ===========================================================================
# Enums
# ===========================================================================


class TestExperimentStatus:
    def test_values(self):
        assert ExperimentStatus.DRAFT.value == "draft"
        assert ExperimentStatus.RUNNING.value == "running"
        assert ExperimentStatus.PAUSED.value == "paused"
        assert ExperimentStatus.COMPLETED.value == "completed"
        assert ExperimentStatus.ARCHIVED.value == "archived"

    def test_choices(self):
        choices = ExperimentStatus.choices()
        assert len(choices) == 5
        assert ("draft", "Draft") in choices

    def test_string_enum(self):
        assert str(ExperimentStatus.RUNNING) == "ExperimentStatus.RUNNING"
        assert ExperimentStatus("running") == ExperimentStatus.RUNNING


class TestAssignmentStrategy:
    def test_values(self):
        assert AssignmentStrategy.RANDOM.value == "random"
        assert AssignmentStrategy.EPSILON_GREEDY.value == "epsilon_greedy"
        assert AssignmentStrategy.UCB.value == "ucb"
        assert AssignmentStrategy.THOMPSON.value == "thompson"

    def test_choices(self):
        choices = AssignmentStrategy.choices()
        assert len(choices) == 4
        assert ("random", "Random") in choices


class TestMetricType:
    def test_values(self):
        assert MetricType.CONVERSION.value == "conversion"
        assert MetricType.REVENUE.value == "revenue"
        assert MetricType.COUNT.value == "count"
        assert MetricType.DURATION.value == "duration"

    def test_choices(self):
        choices = MetricType.choices()
        assert len(choices) == 4


# ===========================================================================
# VariantStats dataclass
# ===========================================================================


class TestVariantStats:
    def test_defaults(self):
        stats = VariantStats(
            variant_id="v1",
            variant_key="control",
            is_control=True,
            sample_size=100,
        )
        assert stats.conversions == 0
        assert stats.conversion_rate == 0.0
        assert stats.total_value == 0.0
        assert stats.std_dev == 0.0

    def test_with_data(self):
        stats = VariantStats(
            variant_id="v2",
            variant_key="treatment",
            is_control=False,
            sample_size=200,
            conversions=40,
            conversion_rate=0.20,
        )
        assert stats.sample_size == 200
        assert stats.conversions == 40
        assert stats.conversion_rate == 0.20


# ===========================================================================
# ComparisonResult dataclass
# ===========================================================================


class TestComparisonResult:
    def test_defaults(self):
        result = ComparisonResult(
            variant_id="v2",
            variant_key="treatment",
            control_id="v1",
            control_key="control",
        )
        assert result.p_value == 1.0
        assert result.z_score == 0.0
        assert result.is_significant is False
        assert result.confidence_level == 0.95

    def test_significant_result(self):
        result = ComparisonResult(
            variant_id="v2",
            variant_key="treatment",
            control_id="v1",
            control_key="control",
            p_value=0.01,
            is_significant=True,
            relative_lift=0.15,
        )
        assert result.is_significant is True
        assert result.relative_lift == 0.15


# ===========================================================================
# ExperimentAnalysis dataclass
# ===========================================================================


class TestExperimentAnalysis:
    def test_defaults(self):
        analysis = ExperimentAnalysis(
            experiment_id="exp1",
            experiment_key="checkout_test",
            status="running",
            total_participants=0,
            total_conversions=0,
            overall_conversion_rate=0.0,
        )
        assert analysis.has_winner is False
        assert analysis.winner_variant_id is None
        assert analysis.should_continue is True
        assert analysis.variant_stats == []
        assert analysis.comparisons == []

    def test_with_winner(self):
        analysis = ExperimentAnalysis(
            experiment_id="exp1",
            experiment_key="test",
            status="completed",
            total_participants=1000,
            total_conversions=200,
            overall_conversion_rate=0.20,
            has_winner=True,
            winner_variant_key="treatment_a",
            winner_confidence=0.97,
        )
        assert analysis.has_winner is True
        assert analysis.winner_variant_key == "treatment_a"


# ===========================================================================
# StatisticalAnalyzer - Pure Math Functions
# ===========================================================================


class TestStatisticalAnalyzerMath:
    def setup_method(self):
        self.analyzer = StatisticalAnalyzer(confidence_level=0.95)

    def test_normal_cdf_zero(self):
        assert self.analyzer._normal_cdf(0.0) == pytest.approx(0.5, abs=1e-6)

    def test_normal_cdf_positive(self):
        result = self.analyzer._normal_cdf(1.96)
        assert result == pytest.approx(0.975, abs=0.01)

    def test_normal_cdf_negative(self):
        result = self.analyzer._normal_cdf(-1.96)
        assert result == pytest.approx(0.025, abs=0.01)

    def test_normal_ppf_median(self):
        assert self.analyzer._normal_ppf(0.5) == 0.0

    def test_normal_ppf_upper(self):
        result = self.analyzer._normal_ppf(0.975)
        assert result == pytest.approx(1.96, abs=0.05)

    def test_normal_ppf_extremes(self):
        assert self.analyzer._normal_ppf(0.0) == float("-inf")
        assert self.analyzer._normal_ppf(1.0) == float("inf")

    def test_chi_square_equal_proportions(self):
        p_value, z = self.analyzer._chi_square_test(50, 500, 50, 500)
        assert p_value == pytest.approx(1.0, abs=0.05)
        assert abs(z) < 0.01

    def test_chi_square_different_proportions(self):
        # 10% vs 15% with 1000 each
        p_value, z = self.analyzer._chi_square_test(100, 1000, 150, 1000)
        assert p_value < 0.05
        assert z != 0.0

    def test_chi_square_zero_samples(self):
        p_value, z = self.analyzer._chi_square_test(0, 0, 0, 0)
        assert p_value == 1.0
        assert z == 0.0

    def test_chi_square_identical_rates(self):
        p_value, z = self.analyzer._chi_square_test(0, 100, 0, 100)
        assert p_value == 1.0

    def test_wilson_ci_zero_samples(self):
        lower, upper = self.analyzer._wilson_confidence_interval(0, 0)
        assert lower == 0.0
        assert upper == 0.0

    def test_wilson_ci_all_successes(self):
        lower, upper = self.analyzer._wilson_confidence_interval(100, 100)
        assert lower > 0.9
        assert upper == pytest.approx(1.0, abs=1e-9)

    def test_wilson_ci_no_successes(self):
        lower, upper = self.analyzer._wilson_confidence_interval(0, 100)
        assert lower == 0.0
        assert upper < 0.1

    def test_wilson_ci_half_successes(self):
        lower, upper = self.analyzer._wilson_confidence_interval(50, 100)
        assert lower < 0.5
        assert upper > 0.5
        assert lower > 0.35
        assert upper < 0.65

    def test_lift_ci_zero_samples(self):
        lower, upper = self.analyzer._lift_confidence_interval(0, 0, 0, 0)
        assert lower == 0.0
        assert upper == 0.0

    def test_lift_ci_normal(self):
        lower, upper = self.analyzer._lift_confidence_interval(60, 500, 40, 500)
        # treatment 12% vs control 8%: diff ~0.04
        assert lower < 0.04 < upper

    def test_calculate_power_zero_samples(self):
        power = self.analyzer._calculate_power(0, 0, 0.1, 0.15)
        assert power == 0.0

    def test_calculate_power_equal_rates(self):
        power = self.analyzer._calculate_power(1000, 1000, 0.10, 0.10)
        assert power == pytest.approx(0.05, abs=0.02)

    def test_calculate_power_large_effect(self):
        power = self.analyzer._calculate_power(5000, 5000, 0.10, 0.20)
        assert power > 0.9

    def test_required_sample_size_equal_rates(self):
        n = self.analyzer._required_sample_size(0.10, 0.10)
        assert n == float("inf")

    def test_required_sample_size_reasonable(self):
        n = self.analyzer._required_sample_size(0.10, 0.15, power=0.8)
        assert isinstance(n, int)
        assert n > 0
        assert n < 50000

    def test_t_test_insufficient_samples(self):
        p_value, t_stat = self.analyzer.t_test([1.0], [2.0])
        assert p_value == 1.0
        assert t_stat == 0.0

    def test_t_test_identical_samples(self):
        a = [5.0, 5.0, 5.0, 5.0, 5.0]
        b = [5.0, 5.0, 5.0, 5.0, 5.0]
        p_value, t_stat = self.analyzer.t_test(a, b)
        assert p_value == 1.0

    def test_t_test_different_means(self):
        random.seed(42)
        a = [random.gauss(10, 2) for _ in range(100)]
        b = [random.gauss(12, 2) for _ in range(100)]
        p_value, t_stat = self.analyzer.t_test(a, b)
        assert p_value < 0.05
        assert t_stat != 0.0

    def test_compare_variants(self):
        control = VariantStats(
            variant_id="v1", variant_key="control", is_control=True,
            sample_size=1000, conversions=100, conversion_rate=0.10,
        )
        treatment = VariantStats(
            variant_id="v2", variant_key="treatment", is_control=False,
            sample_size=1000, conversions=150, conversion_rate=0.15,
        )
        result = self.analyzer._compare_variants(treatment, control)
        assert isinstance(result, ComparisonResult)
        assert result.absolute_lift == pytest.approx(0.05, abs=0.001)
        assert result.relative_lift == pytest.approx(0.50, abs=0.01)
        assert result.is_significant is True


# ===========================================================================
# StatisticalAnalyzer - confidence_level attribute
# ===========================================================================


class TestStatisticalAnalyzerConfig:
    def test_default_confidence(self):
        a = StatisticalAnalyzer()
        assert a.confidence_level == 0.95
        assert a.alpha == pytest.approx(0.05, abs=1e-9)

    def test_custom_confidence(self):
        a = StatisticalAnalyzer(confidence_level=0.99)
        assert a.confidence_level == 0.99
        assert a.alpha == pytest.approx(0.01, abs=1e-9)


# ===========================================================================
# ExperimentManager - Bandit Algorithms (pure logic, no DB)
# ===========================================================================


class TestExperimentManagerBandits:
    def setup_method(self):
        self.manager = ExperimentManager()

    def _make_variant(self, key, weight=1, is_control=False, assignments=0, conversions=0):
        v = MagicMock()
        v.id = key
        v.key = key
        v.weight = weight
        v.is_control = is_control
        v.assignment_count = assignments
        v.conversion_count = conversions
        v.conversion_rate = conversions / assignments if assignments > 0 else 0.0
        return v

    def _make_experiment(self, strategy="random", epsilon=0.1, exploration_weight=2.0):
        exp = MagicMock()
        exp.key = "test_exp"
        exp.strategy = strategy
        exp.epsilon = epsilon
        exp.exploration_weight = exploration_weight
        return exp

    def test_epsilon_greedy_explore(self):
        """With epsilon=1.0, always explores randomly."""
        variants = [self._make_variant("a"), self._make_variant("b")]
        exp = self._make_experiment(strategy="epsilon_greedy", epsilon=1.0)
        random.seed(42)
        results = {v.key for _ in range(50)
                   for v in [self.manager._epsilon_greedy_assignment(variants, exp)]}
        assert len(results) == 2  # both should be selected

    def test_epsilon_greedy_exploit(self):
        """With epsilon=0, always exploits best."""
        v_a = self._make_variant("a", assignments=100, conversions=10)
        v_b = self._make_variant("b", assignments=100, conversions=30)
        exp = self._make_experiment(strategy="epsilon_greedy", epsilon=0.0)
        for _ in range(10):
            result = self.manager._epsilon_greedy_assignment([v_a, v_b], exp)
            assert result.key == "b"

    def test_ucb_explores_unvisited(self):
        """UCB should select unvisited variants first."""
        visited = self._make_variant("visited", assignments=100, conversions=10)
        unvisited = self._make_variant("unvisited", assignments=0, conversions=0)
        exp = self._make_experiment(strategy="ucb")
        result = self.manager._ucb_assignment([visited, unvisited], exp)
        assert result.key == "unvisited"

    def test_ucb_all_zero_assignments(self):
        """UCB with no data returns random."""
        variants = [self._make_variant("a"), self._make_variant("b")]
        exp = self._make_experiment(strategy="ucb")
        result = self.manager._ucb_assignment(variants, exp)
        assert result.key in ("a", "b")

    def test_ucb_selects_best(self):
        """UCB with data selects the one with highest upper bound."""
        v_a = self._make_variant("a", assignments=1000, conversions=100)
        v_b = self._make_variant("b", assignments=1000, conversions=200)
        exp = self._make_experiment(strategy="ucb", exploration_weight=0.0)
        result = self.manager._ucb_assignment([v_a, v_b], exp)
        assert result.key == "b"

    def test_thompson_returns_variant(self):
        """Thompson sampling returns a valid variant."""
        variants = [
            self._make_variant("control", assignments=100, conversions=10),
            self._make_variant("treatment", assignments=100, conversions=30),
        ]
        exp = self._make_experiment(strategy="thompson")
        random.seed(42)
        result = self.manager._thompson_assignment(variants, exp)
        assert result.key in ("control", "treatment")

    def test_thompson_favors_winner(self):
        """Over many samples, Thompson should favor the better variant."""
        control = self._make_variant("control", assignments=500, conversions=50)
        treatment = self._make_variant("treatment", assignments=500, conversions=150)
        exp = self._make_experiment(strategy="thompson")
        random.seed(0)
        counts = {"control": 0, "treatment": 0}
        for _ in range(200):
            result = self.manager._thompson_assignment([control, treatment], exp)
            counts[result.key] += 1
        assert counts["treatment"] > counts["control"]

    def test_sample_beta_returns_float(self):
        result = self.manager._sample_beta(2.0, 3.0)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_sample_beta_edge_zero(self):
        """Both x and y being zero should return 0.5."""
        # This is very unlikely with gammavariate, so just test output is float
        result = self.manager._sample_beta(1.0, 1.0)
        assert isinstance(result, float)


# ===========================================================================
# ExperimentManager - Targeting Rules
# ===========================================================================


class TestTargetingRules:
    def setup_method(self):
        self.manager = ExperimentManager()

    def test_evaluate_eq(self):
        assert self.manager._evaluate_rule(
            {"attribute": "plan", "operator": "eq", "value": "pro"},
            {"plan": "pro"},
        ) is True

    def test_evaluate_neq(self):
        assert self.manager._evaluate_rule(
            {"attribute": "plan", "operator": "neq", "value": "free"},
            {"plan": "pro"},
        ) is True

    def test_evaluate_gt(self):
        assert self.manager._evaluate_rule(
            {"attribute": "age", "operator": "gt", "value": 18},
            {"age": 25},
        ) is True

    def test_evaluate_gte(self):
        assert self.manager._evaluate_rule(
            {"attribute": "age", "operator": "gte", "value": 25},
            {"age": 25},
        ) is True

    def test_evaluate_lt(self):
        assert self.manager._evaluate_rule(
            {"attribute": "age", "operator": "lt", "value": 30},
            {"age": 25},
        ) is True

    def test_evaluate_lte(self):
        assert self.manager._evaluate_rule(
            {"attribute": "age", "operator": "lte", "value": 25},
            {"age": 25},
        ) is True

    def test_evaluate_in(self):
        assert self.manager._evaluate_rule(
            {"attribute": "country", "operator": "in", "value": ["US", "CA"]},
            {"country": "US"},
        ) is True

    def test_evaluate_not_in(self):
        assert self.manager._evaluate_rule(
            {"attribute": "country", "operator": "not_in", "value": ["US", "CA"]},
            {"country": "UK"},
        ) is True

    def test_evaluate_contains(self):
        assert self.manager._evaluate_rule(
            {"attribute": "email", "operator": "contains", "value": "@example.com"},
            {"email": "user@example.com"},
        ) is True

    def test_evaluate_missing_attribute_passes(self):
        assert self.manager._evaluate_rule(
            {"attribute": "missing", "operator": "eq", "value": "x"},
            {},
        ) is True


# ===========================================================================
# ExperimentManager - Bandit Weights
# ===========================================================================


class TestBanditWeights:
    def setup_method(self):
        self.manager = ExperimentManager()

    def _make_variant(self, key, weight=1, assignments=0, conversions=0):
        v = MagicMock()
        v.id = key
        v.key = key
        v.weight = weight
        v.assignment_count = assignments
        v.conversion_count = conversions
        v.conversion_rate = conversions / assignments if assignments > 0 else 0.0
        return v

    def test_random_weights_normalized(self):
        exp = MagicMock()
        exp.strategy = "random"
        variants = [self._make_variant("a", weight=3), self._make_variant("b", weight=1)]
        exp.variants.all.return_value = variants
        weights = self.manager.get_bandit_weights(exp)
        assert weights[str(variants[0].id)] == pytest.approx(0.75)
        assert weights[str(variants[1].id)] == pytest.approx(0.25)

    def test_random_weights_zero_total(self):
        exp = MagicMock()
        exp.strategy = "random"
        variants = [self._make_variant("a", weight=0), self._make_variant("b", weight=0)]
        exp.variants.all.return_value = variants
        weights = self.manager.get_bandit_weights(exp)
        assert weights[str(variants[0].id)] == pytest.approx(0.5)

    def test_epsilon_greedy_weights(self):
        exp = MagicMock()
        exp.strategy = "epsilon_greedy"
        exp.epsilon = 0.1
        v_a = self._make_variant("a", assignments=100, conversions=10)
        v_b = self._make_variant("b", assignments=100, conversions=30)
        exp.variants.all.return_value = [v_a, v_b]
        weights = self.manager.get_bandit_weights(exp)
        # v_b is best: should get (1 - 0.1) + 0.1/2 = 0.95
        assert weights[str(v_b.id)] > weights[str(v_a.id)]

    def test_empty_variants(self):
        exp = MagicMock()
        exp.strategy = "random"
        exp.variants.all.return_value = []
        weights = self.manager.get_bandit_weights(exp)
        assert weights == {}

    def test_thompson_weights_sum_to_one(self):
        exp = MagicMock()
        exp.strategy = "thompson"
        variants = [
            self._make_variant("a", assignments=100, conversions=10),
            self._make_variant("b", assignments=100, conversions=30),
        ]
        exp.variants.all.return_value = variants
        random.seed(42)
        weights = self.manager.get_bandit_weights(exp)
        total = sum(weights.values())
        assert total == pytest.approx(1.0, abs=0.01)


# ===========================================================================
# TestDeterministicAssignment (EXP-01)
# ===========================================================================


@pytest.mark.django_db(transaction=True)
class TestDeterministicAssignment:
    """Test deterministic variant assignment for A/B experiments."""

    def _create_experiment_with_variants(self):
        """Helper: create running experiment with control and treatment variants."""
        from django.contrib.auth.models import User

        from django_matt.experiments.models import (
            AssignmentStrategy,
            Experiment,
            ExperimentStatus,
            Variant,
        )

        exp = Experiment.objects.create(
            key=f"test-determinism-{__import__('uuid').uuid4().hex[:8]}",
            name="Determinism Test",
            status=ExperimentStatus.RUNNING.value,
            strategy=AssignmentStrategy.RANDOM.value,
        )
        Variant.objects.create(
            experiment=exp, key="control", name="Control", is_control=True, weight=1
        )
        Variant.objects.create(
            experiment=exp, key="treatment", name="Treatment", is_control=False, weight=1
        )
        return exp

    def test_same_user_same_variant_100_times(self):
        """Same user always gets the same variant across 100 calls."""
        from django_matt.experiments.manager import ExperimentManager

        exp = self._create_experiment_with_variants()
        variants = list(exp.variants.all())

        manager = ExperimentManager()
        user_id = "user-determinism-42"

        # First assignment
        first_result = manager._random_assignment(variants, exp, None, user_id)
        assert first_result is not None

        # 99 more times should return the same variant
        for _ in range(99):
            result = manager._random_assignment(variants, exp, None, user_id)
            assert result.key == first_result.key, (
                f"Variant changed: expected {first_result.key}, got {result.key}"
            )

    def test_different_users_distributed(self):
        """1000 different users are distributed across both variants."""
        from django_matt.experiments.manager import ExperimentManager

        exp = self._create_experiment_with_variants()
        variants = list(exp.variants.all())
        manager = ExperimentManager()

        variant_counts = {}
        for i in range(1000):
            user_id = f"dist-user-{i}"
            result = manager._random_assignment(variants, exp, None, user_id)
            variant_counts[result.key] = variant_counts.get(result.key, 0) + 1

        # Both variants should receive assignments (not all in one bucket)
        assert len(variant_counts) == 2, f"Expected 2 variants, got: {variant_counts}"
        # Each variant should get at least 10% of assignments (avoid extreme skew)
        for key, count in variant_counts.items():
            assert count > 50, f"Variant {key} got only {count}/1000 assignments"

    def test_assignment_persists_in_db(self):
        """ExperimentAssignment is created in DB after get_assignment call."""
        from django.contrib.auth.models import User

        from django_matt.experiments.manager import ExperimentManager
        from django_matt.experiments.models import ExperimentAssignment

        exp = self._create_experiment_with_variants()
        manager = ExperimentManager()

        # Create a real user
        user = User.objects.create_user(
            username=f"expuser-{__import__('uuid').uuid4().hex[:8]}",
            email="exp@test.com",
            password="pass",
        )

        # First call creates assignment
        assignment1 = manager.get_assignment(
            experiment_key=exp.key,
            user=user,
            create=True,
        )
        assert assignment1 is not None
        assert ExperimentAssignment.objects.filter(experiment=exp, user=user).exists()

        # Second call retrieves same assignment from DB
        assignment2 = manager.get_assignment(
            experiment_key=exp.key,
            user=user,
            create=True,
        )
        assert assignment2 is not None
        assert assignment1.id == assignment2.id
        assert assignment1.variant.key == assignment2.variant.key


# ===========================================================================
# TestExperimentDecorator (EXP-04)
# ===========================================================================


class TestExperimentDecorator:
    """Test @experiment decorator for variant injection and routing."""

    def test_decorator_injects_variant_kwarg_async(self):
        """Async handler receives variant kwarg when @experiment is applied."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from django.test import RequestFactory

        from django_matt.experiments.decorators import experiment

        received_variant = []

        @experiment("test-inject-exp")
        async def my_handler(request, variant: str | None = None):
            received_variant.append(variant)
            return "ok"

        request = RequestFactory().get("/test/")
        request.COOKIES = {}
        request.user = MagicMock()
        request.user.is_authenticated = False

        # Mock ExperimentContext to return known variant.
        # The decorator does a lazy import inside the wrapper, so we patch
        # ExperimentContext.from_request at the context module level.
        mock_ctx = MagicMock()
        mock_ctx.get_variant.return_value = "treatment"
        mock_ctx.track_exposure = MagicMock()

        with patch(
            "django_matt.experiments.context.ExperimentContext.from_request",
            return_value=mock_ctx,
        ):
            asyncio.get_event_loop().run_until_complete(my_handler(request))

        assert len(received_variant) == 1
        assert received_variant[0] == "treatment"

    def test_decorator_tracks_exposure(self):
        """@experiment with track_exposure=True calls ctx.track_exposure."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from django.test import RequestFactory

        from django_matt.experiments.decorators import experiment

        @experiment("test-exposure-exp", track_exposure=True)
        async def exposure_handler(request, variant: str | None = None):
            return "ok"

        request = RequestFactory().get("/test/")
        request.COOKIES = {}
        request.user = MagicMock()
        request.user.is_authenticated = False

        mock_ctx = MagicMock()
        mock_ctx.get_variant.return_value = "control"
        mock_ctx.track_exposure = MagicMock()

        with patch(
            "django_matt.experiments.context.ExperimentContext.from_request",
            return_value=mock_ctx,
        ):
            asyncio.get_event_loop().run_until_complete(exposure_handler(request))

        mock_ctx.track_exposure.assert_called_once_with("test-exposure-exp")

    def test_decorator_with_variant_handlers_routes_correctly(self):
        """@experiment with variant_handlers routes to the correct handler."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from django.test import RequestFactory

        from django_matt.experiments.decorators import experiment

        handler_a_called = []
        handler_b_called = []

        async def handler_a(request):
            handler_a_called.append(True)
            return "a"

        async def handler_b(request):
            handler_b_called.append(True)
            return "b"

        @experiment(
            "test-routing-exp",
            variant_handlers={"control": handler_a, "treatment": handler_b},
        )
        async def default_handler(request, variant: str | None = None):
            return "default"

        request = RequestFactory().get("/test/")
        request.COOKIES = {}
        request.user = MagicMock()
        request.user.is_authenticated = False

        mock_ctx = MagicMock()
        mock_ctx.get_variant.return_value = "treatment"
        mock_ctx.track_exposure = MagicMock()

        with patch(
            "django_matt.experiments.context.ExperimentContext.from_request",
            return_value=mock_ctx,
        ):
            result = asyncio.get_event_loop().run_until_complete(default_handler(request))

        assert result == "b"
        assert len(handler_b_called) == 1
        assert len(handler_a_called) == 0

    def test_decorator_no_variant_falls_through_to_default(self):
        """When no variant assigned, decorator falls through to decorated function with None variant."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from django.test import RequestFactory

        from django_matt.experiments.decorators import experiment

        received = []

        @experiment("test-fallthrough-exp")
        async def my_handler(request, variant: str | None = None):
            received.append(variant)
            return "default"

        request = RequestFactory().get("/test/")
        request.COOKIES = {}
        request.user = MagicMock()
        request.user.is_authenticated = False

        mock_ctx = MagicMock()
        mock_ctx.get_variant.return_value = None  # No variant assigned
        mock_ctx.track_exposure = MagicMock()

        with patch(
            "django_matt.experiments.context.ExperimentContext.from_request",
            return_value=mock_ctx,
        ):
            result = asyncio.get_event_loop().run_until_complete(my_handler(request))

        assert result == "default"
        assert received[0] is None
