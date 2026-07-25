"""
Extended test coverage for the Django Matt experiments module.

Tests cover:
- Experiment model CRUD and lifecycle transitions (draft -> running -> paused -> completed -> archived)
- Variant model properties and edge cases
- Assignment via ExperimentManager (deterministic hashing, anonymous users)
- Multi-armed bandit strategies (epsilon-greedy, UCB, Thompson sampling)
- Conversion and revenue tracking
- Statistical analysis (chi-square, Wilson CI, t-test, power analysis)
- Experiment analysis with winner detection
- Targeting rules and exclusion groups
- Holdout group assignment
- Edge cases: no variants, single variant, 100% allocation, zero conversions
- Audit logging
- Schemas validation
"""

from __future__ import annotations

import math
import random
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from django_matt.experiments.analysis import (
    ComparisonResult,
    ExperimentAnalysis,
    StatisticalAnalyzer,
    VariantStats,
    analyze_experiment,
)
from django_matt.experiments.manager import ExperimentManager
from django_matt.experiments.models import (
    AssignmentStrategy,
    ExperimentStatus,
    MetricType,
)
from django_matt.experiments.schemas import (
    AssignmentContext,
    AssignmentRequest,
    AssignmentResponse,
    BulkAssignmentRequest,
    ConversionEvent,
    ExperimentBase,
    ExperimentCreate,
    ExperimentListResponse,
    ExperimentResponse,
    ExperimentStatsResponse,
    ExperimentUpdate,
    RevenueEvent,
    TargetingRule,
    VariantCreate,
    VariantResponse,
    VariantUpdate,
)

# ===========================================================================
# Model lifecycle (DB-backed)
# ===========================================================================


@pytest.mark.django_db
class TestExperimentLifecycle:
    """Test experiment state machine transitions with real DB."""

    def _make_experiment(self, **kwargs):
        from django_matt.experiments.models import Experiment

        defaults = dict(key="test-exp", name="Test Experiment")
        defaults.update(kwargs)
        return Experiment.objects.create(**defaults)

    def _add_variant(self, experiment, key="control", is_control=True, weight=1):
        from django_matt.experiments.models import Variant

        return Variant.objects.create(
            experiment=experiment,
            key=key,
            name=key.title(),
            is_control=is_control,
            weight=weight,
        )

    def test_draft_to_running(self):
        exp = self._make_experiment()
        self._add_variant(exp)
        assert exp.status == ExperimentStatus.DRAFT.value
        exp.start()
        exp.refresh_from_db()
        assert exp.status == ExperimentStatus.RUNNING.value
        assert exp.start_date is not None
        assert exp.is_running is True

    def test_cannot_start_without_variants(self):
        exp = self._make_experiment()
        with pytest.raises(ValueError, match="at least one variant"):
            exp.start()

    def test_cannot_start_from_non_draft(self):
        exp = self._make_experiment(status=ExperimentStatus.RUNNING.value)
        self._add_variant(exp)
        with pytest.raises(ValueError, match="Cannot start"):
            exp.start()

    def test_running_to_paused(self):
        exp = self._make_experiment()
        self._add_variant(exp)
        exp.start()
        exp.pause()
        exp.refresh_from_db()
        assert exp.status == ExperimentStatus.PAUSED.value
        assert exp.is_running is False

    def test_cannot_pause_from_draft(self):
        exp = self._make_experiment()
        with pytest.raises(ValueError, match="Cannot pause"):
            exp.pause()

    def test_paused_to_resumed(self):
        exp = self._make_experiment()
        self._add_variant(exp)
        exp.start()
        exp.pause()
        exp.resume()
        exp.refresh_from_db()
        assert exp.status == ExperimentStatus.RUNNING.value

    def test_cannot_resume_from_non_paused(self):
        exp = self._make_experiment()
        self._add_variant(exp)
        exp.start()
        with pytest.raises(ValueError, match="Cannot resume"):
            exp.resume()

    def test_complete_with_winner(self):
        exp = self._make_experiment()
        control = self._add_variant(exp, key="control", is_control=True)
        treatment = self._add_variant(exp, key="treatment", is_control=False)
        exp.start()
        exp.complete(winner_variant=treatment, confidence=0.97)
        exp.refresh_from_db()
        assert exp.status == ExperimentStatus.COMPLETED.value
        assert exp.has_winner is True
        assert exp.winner_variant_id == treatment.id
        assert exp.winner_confidence == 0.97
        assert exp.winner_detected_at is not None
        assert exp.end_date is not None

    def test_complete_without_winner(self):
        exp = self._make_experiment()
        self._add_variant(exp)
        exp.start()
        exp.complete()
        exp.refresh_from_db()
        assert exp.status == ExperimentStatus.COMPLETED.value
        assert exp.has_winner is False

    def test_str_representation(self):
        exp = self._make_experiment(key="pricing-test")
        assert "pricing-test" in str(exp)
        assert "draft" in str(exp)

    def test_status_enum_property(self):
        exp = self._make_experiment()
        assert exp.status_enum == ExperimentStatus.DRAFT

    def test_strategy_enum_property(self):
        exp = self._make_experiment(strategy=AssignmentStrategy.UCB.value)
        assert exp.strategy_enum == AssignmentStrategy.UCB

    def test_total_participants(self):
        exp = self._make_experiment()
        assert exp.total_participants == 0

    def test_manager_active(self):
        from django_matt.experiments.models import Experiment

        self._make_experiment(key="active-1", status=ExperimentStatus.RUNNING.value)
        self._make_experiment(key="draft-1", status=ExperimentStatus.DRAFT.value)
        active = Experiment.objects.active()
        assert active.count() == 1
        assert active.first().key == "active-1"

    def test_manager_by_key(self):
        from django_matt.experiments.models import Experiment

        self._make_experiment(key="findme")
        assert Experiment.objects.by_key("findme") is not None
        assert Experiment.objects.by_key("nope") is None


# ===========================================================================
# Variant model
# ===========================================================================


@pytest.mark.django_db
class TestVariantModel:
    def _setup(self):
        from django_matt.experiments.models import Experiment, Variant

        exp = Experiment.objects.create(key="var-test", name="Variant Test")
        control = Variant.objects.create(
            experiment=exp, key="control", name="Control", is_control=True, weight=1
        )
        treatment = Variant.objects.create(
            experiment=exp, key="treatment", name="Treatment", is_control=False, weight=1
        )
        return exp, control, treatment

    def test_str_representation(self):
        _, control, treatment = self._setup()
        assert "(control)" in str(control)
        assert "treatment" in str(treatment)
        assert "(control)" not in str(treatment)

    def test_assignment_count_zero(self):
        _, control, _ = self._setup()
        assert control.assignment_count == 0

    def test_conversion_rate_zero_assignments(self):
        _, control, _ = self._setup()
        assert control.conversion_rate == 0.0

    def test_unique_together_constraint(self):
        from django.db import IntegrityError

        from django_matt.experiments.models import Experiment, Variant

        exp = Experiment.objects.create(key="dup-test", name="Dup Test")
        Variant.objects.create(experiment=exp, key="a", name="A")
        with pytest.raises(IntegrityError):
            Variant.objects.create(experiment=exp, key="a", name="A2")


# ===========================================================================
# Assignment and tracking (DB-backed)
# ===========================================================================


@pytest.mark.django_db
class TestExperimentManagerDB:
    """Test assignment logic against real database."""

    def _setup_running_experiment(self, key="assign-test", strategy="random"):
        from django_matt.experiments.models import Experiment, Variant

        exp = Experiment.objects.create(
            key=key,
            name="Assignment Test",
            status=ExperimentStatus.RUNNING.value,
            strategy=strategy,
        )
        control = Variant.objects.create(
            experiment=exp, key="control", name="Control", is_control=True, weight=1
        )
        treatment = Variant.objects.create(
            experiment=exp, key="treatment", name="Treatment", is_control=False, weight=1
        )
        return exp, control, treatment

    def test_get_assignment_nonexistent_experiment(self):
        mgr = ExperimentManager()
        result = mgr.get_assignment("nonexistent", anonymous_id="anon-1")
        assert result is None

    def test_get_assignment_not_running(self):
        from django_matt.experiments.models import Experiment

        Experiment.objects.create(key="draft-exp", name="Draft", status="draft")
        mgr = ExperimentManager()
        result = mgr.get_assignment("draft-exp", anonymous_id="anon-1")
        assert result is None

    def test_get_assignment_no_identifier(self):
        self._setup_running_experiment(key="no-id-test")
        mgr = ExperimentManager()
        result = mgr.get_assignment("no-id-test")
        assert result is None

    def test_anonymous_assignment_creates(self):
        self._setup_running_experiment(key="anon-test")
        mgr = ExperimentManager()
        assignment = mgr.get_assignment("anon-test", anonymous_id="user-abc-123")
        assert assignment is not None
        assert assignment.anonymous_id == "user-abc-123"
        assert assignment.variant is not None

    def test_anonymous_assignment_idempotent(self):
        self._setup_running_experiment(key="idem-test")
        mgr = ExperimentManager()
        a1 = mgr.get_assignment("idem-test", anonymous_id="same-user")
        a2 = mgr.get_assignment("idem-test", anonymous_id="same-user")
        assert a1.id == a2.id
        assert a1.variant_id == a2.variant_id

    def test_deterministic_random_assignment(self):
        """Same user always gets the same variant for same experiment."""
        self._setup_running_experiment(key="det-test")
        mgr = ExperimentManager()
        a1 = mgr.get_assignment("det-test", anonymous_id="det-user-1")
        variant_key_1 = a1.variant.key
        # Querying again returns the same assignment
        a2 = mgr.get_assignment("det-test", anonymous_id="det-user-1")
        assert a2.variant.key == variant_key_1

    def test_get_variant_key(self):
        self._setup_running_experiment(key="vk-test")
        mgr = ExperimentManager()
        vk = mgr.get_variant_key("vk-test", anonymous_id="vk-user", default="fallback")
        assert vk in ("control", "treatment")

    def test_get_variant_key_default(self):
        mgr = ExperimentManager()
        vk = mgr.get_variant_key("nonexistent", anonymous_id="x", default="fallback")
        assert vk == "fallback"

    def test_track_conversion(self):
        from django_matt.experiments.models import ExperimentResult

        self._setup_running_experiment(key="conv-test")
        mgr = ExperimentManager()
        mgr.get_assignment("conv-test", anonymous_id="conv-user")
        result = mgr.track_conversion("conv-test", anonymous_id="conv-user")
        assert result is True
        assert ExperimentResult.objects.filter(metric_name="conversion").count() == 1

    def test_track_conversion_no_assignment(self):
        mgr = ExperimentManager()
        result = mgr.track_conversion("nonexistent", anonymous_id="no-one")
        assert result is False

    def test_track_revenue(self):
        from django_matt.experiments.models import ExperimentResult

        self._setup_running_experiment(key="rev-test")
        mgr = ExperimentManager()
        mgr.get_assignment("rev-test", anonymous_id="rev-user")
        result = mgr.track_revenue("rev-test", amount=49.99, anonymous_id="rev-user")
        assert result is True
        er = ExperimentResult.objects.filter(metric_name="revenue").first()
        assert er is not None
        assert er.value == Decimal("49.99")

    def test_track_revenue_no_assignment(self):
        mgr = ExperimentManager()
        result = mgr.track_revenue("nonexistent", amount=10.0, anonymous_id="no-one")
        assert result is False

    def test_get_assignment_create_false(self):
        self._setup_running_experiment(key="nocreate-test")
        mgr = ExperimentManager()
        result = mgr.get_assignment("nocreate-test", anonymous_id="new-user", create=False)
        assert result is None


# ===========================================================================
# Holdout group
# ===========================================================================


@pytest.mark.django_db
class TestHoldoutGroup:
    def test_holdout_assignment(self):
        from django_matt.experiments.models import Experiment, Variant

        exp = Experiment.objects.create(
            key="holdout-test",
            name="Holdout Test",
            status=ExperimentStatus.RUNNING.value,
            holdout_percentage=1.0,  # 100% holdout — everyone is holdout
        )
        Variant.objects.create(
            experiment=exp, key="control", name="Control", is_control=True, weight=1
        )
        mgr = ExperimentManager()
        assignment = mgr.get_assignment("holdout-test", anonymous_id="holdout-user")
        assert assignment is not None
        assert assignment.is_holdout is True
        assert assignment.variant is None

    def test_no_holdout_when_zero(self):
        from django_matt.experiments.models import Experiment, Variant

        exp = Experiment.objects.create(
            key="noholdout",
            name="No Holdout",
            status=ExperimentStatus.RUNNING.value,
            holdout_percentage=0.0,
        )
        Variant.objects.create(
            experiment=exp, key="control", name="Control", is_control=True, weight=1
        )
        mgr = ExperimentManager()
        assignment = mgr.get_assignment("noholdout", anonymous_id="normal-user")
        assert assignment is not None
        assert assignment.is_holdout is False

    def test_holdout_returns_none_variant(self):
        """get_variant returns None for holdout users."""
        from django_matt.experiments.models import Experiment, Variant

        exp = Experiment.objects.create(
            key="holdout-var",
            name="Holdout Variant",
            status=ExperimentStatus.RUNNING.value,
            holdout_percentage=1.0,
        )
        Variant.objects.create(
            experiment=exp, key="control", name="Control", is_control=True, weight=1
        )
        mgr = ExperimentManager()
        variant = mgr.get_variant("holdout-var", anonymous_id="holdout-user")
        assert variant is None


# ===========================================================================
# Targeting rules
# ===========================================================================


@pytest.mark.django_db
class TestTargetingRules:
    def test_eligible_with_no_rules(self):
        from django_matt.experiments.models import Experiment, Variant

        exp = Experiment.objects.create(
            key="norule",
            name="No Rules",
            status=ExperimentStatus.RUNNING.value,
            targeting_rules=[],
        )
        Variant.objects.create(experiment=exp, key="a", name="A", weight=1)
        mgr = ExperimentManager()
        assignment = mgr.get_assignment("norule", anonymous_id="anyone")
        assert assignment is not None

    def test_ineligible_user(self):
        from django_matt.experiments.models import Experiment, Variant

        exp = Experiment.objects.create(
            key="targeted",
            name="Targeted",
            status=ExperimentStatus.RUNNING.value,
            targeting_rules=[{"attribute": "is_staff", "operator": "eq", "value": True}],
        )
        Variant.objects.create(experiment=exp, key="a", name="A", weight=1)
        mgr = ExperimentManager()
        # anonymous user without is_staff context
        assignment = mgr.get_assignment(
            "targeted",
            anonymous_id="anon-user",
            context={"is_staff": False},
        )
        assert assignment is None

    def test_eligible_user_with_matching_context(self):
        from django_matt.experiments.models import Experiment, Variant

        exp = Experiment.objects.create(
            key="targeted2",
            name="Targeted2",
            status=ExperimentStatus.RUNNING.value,
            targeting_rules=[{"attribute": "is_staff", "operator": "eq", "value": True}],
        )
        Variant.objects.create(experiment=exp, key="a", name="A", weight=1)
        mgr = ExperimentManager()
        assignment = mgr.get_assignment(
            "targeted2",
            anonymous_id="staff-user",
            context={"is_staff": True},
        )
        assert assignment is not None


# ===========================================================================
# Exclusion groups
# ===========================================================================


@pytest.mark.django_db
class TestExclusionGroups:
    def test_exclusion_blocks_second_experiment(self):
        from django_matt.experiments.models import Experiment, Variant

        exp1 = Experiment.objects.create(
            key="excl-1",
            name="Exclusion 1",
            status=ExperimentStatus.RUNNING.value,
            exclusion_group="checkout",
        )
        Variant.objects.create(experiment=exp1, key="a", name="A", weight=1)

        exp2 = Experiment.objects.create(
            key="excl-2",
            name="Exclusion 2",
            status=ExperimentStatus.RUNNING.value,
            exclusion_group="checkout",
        )
        Variant.objects.create(experiment=exp2, key="b", name="B", weight=1)

        mgr = ExperimentManager()
        # Assign to first experiment
        a1 = mgr.get_assignment("excl-1", anonymous_id="excl-user")
        assert a1 is not None
        # Should be blocked from second experiment in same group
        a2 = mgr.get_assignment("excl-2", anonymous_id="excl-user")
        assert a2 is None

    def test_no_exclusion_group_allows_multiple(self):
        from django_matt.experiments.models import Experiment, Variant

        exp1 = Experiment.objects.create(
            key="noexcl-1",
            name="No Exclusion 1",
            status=ExperimentStatus.RUNNING.value,
        )
        Variant.objects.create(experiment=exp1, key="a", name="A", weight=1)

        exp2 = Experiment.objects.create(
            key="noexcl-2",
            name="No Exclusion 2",
            status=ExperimentStatus.RUNNING.value,
        )
        Variant.objects.create(experiment=exp2, key="b", name="B", weight=1)

        mgr = ExperimentManager()
        a1 = mgr.get_assignment("noexcl-1", anonymous_id="multi-user")
        a2 = mgr.get_assignment("noexcl-2", anonymous_id="multi-user")
        assert a1 is not None
        assert a2 is not None


# ===========================================================================
# Statistical analyzer — extended coverage
# ===========================================================================


class TestStatisticalAnalyzerExtended:
    """Additional coverage for edge cases in StatisticalAnalyzer."""

    def test_chi_square_zero_total(self):
        analyzer = StatisticalAnalyzer()
        p, z = analyzer._chi_square_test(0, 0, 0, 0)
        assert p == 1.0
        assert z == 0.0

    def test_chi_square_no_variation(self):
        """All conversions or zero conversions."""
        analyzer = StatisticalAnalyzer()
        p, z = analyzer._chi_square_test(100, 100, 100, 100)
        assert p == 1.0  # pooled proportion is 1.0

    def test_chi_square_significant_difference(self):
        analyzer = StatisticalAnalyzer()
        # Large sample with clear difference
        p, z = analyzer._chi_square_test(80, 1000, 50, 1000)
        assert p < 0.05
        assert z != 0.0

    def test_wilson_ci_zero_total(self):
        analyzer = StatisticalAnalyzer()
        lower, upper = analyzer._wilson_confidence_interval(0, 0)
        assert lower == 0.0
        assert upper == 0.0

    def test_wilson_ci_all_success(self):
        analyzer = StatisticalAnalyzer()
        lower, upper = analyzer._wilson_confidence_interval(100, 100)
        assert lower > 0.9
        assert upper == pytest.approx(1.0, abs=1e-10)

    def test_wilson_ci_no_success(self):
        analyzer = StatisticalAnalyzer()
        lower, upper = analyzer._wilson_confidence_interval(0, 100)
        assert lower == 0.0
        assert upper < 0.1

    def test_lift_ci_zero_totals(self):
        analyzer = StatisticalAnalyzer()
        lower, upper = analyzer._lift_confidence_interval(0, 0, 0, 0)
        assert lower == 0.0
        assert upper == 0.0

    def test_power_zero_samples(self):
        analyzer = StatisticalAnalyzer()
        power = analyzer._calculate_power(0, 0, 0.5, 0.6)
        assert power == 0.0

    def test_power_equal_rates(self):
        analyzer = StatisticalAnalyzer()
        power = analyzer._calculate_power(1000, 1000, 0.5, 0.5)
        assert power == pytest.approx(0.05, abs=0.01)

    def test_required_sample_size_equal_rates(self):
        analyzer = StatisticalAnalyzer()
        n = analyzer._required_sample_size(0.5, 0.5)
        assert n == float("inf")

    def test_required_sample_size_reasonable(self):
        analyzer = StatisticalAnalyzer()
        n = analyzer._required_sample_size(0.10, 0.12, power=0.8)
        assert isinstance(n, int)
        assert n > 0

    def test_t_test_too_few_samples(self):
        analyzer = StatisticalAnalyzer()
        p, t = analyzer.t_test([1.0], [2.0])
        assert p == 1.0
        assert t == 0.0

    def test_t_test_identical_values(self):
        analyzer = StatisticalAnalyzer()
        p, t = analyzer.t_test([1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
        assert p == 1.0  # se == 0

    def test_t_test_different_means(self):
        analyzer = StatisticalAnalyzer()
        a = [10.0, 11.0, 12.0, 13.0, 14.0] * 20
        b = [20.0, 21.0, 22.0, 23.0, 24.0] * 20
        p, t = analyzer.t_test(a, b)
        assert p < 0.05
        assert t < 0  # mean_a < mean_b

    def test_t_test_small_df(self):
        """Test with small sample sizes to trigger low-df path."""
        analyzer = StatisticalAnalyzer()
        p, t = analyzer.t_test([1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
        assert 0.0 < p < 1.0

    def test_normal_ppf_edge_cases(self):
        analyzer = StatisticalAnalyzer()
        assert analyzer._normal_ppf(0.0) == float("-inf")
        assert analyzer._normal_ppf(1.0) == float("inf")
        assert analyzer._normal_ppf(0.5) == 0.0

    def test_normal_ppf_symmetry(self):
        analyzer = StatisticalAnalyzer()
        v1 = analyzer._normal_ppf(0.025)
        v2 = analyzer._normal_ppf(0.975)
        assert v1 == pytest.approx(-v2, abs=0.001)

    def test_normal_cdf_known_values(self):
        analyzer = StatisticalAnalyzer()
        assert analyzer._normal_cdf(0.0) == pytest.approx(0.5, abs=0.001)
        assert analyzer._normal_cdf(1.96) == pytest.approx(0.975, abs=0.01)

    def test_compare_variants_zero_control_rate(self):
        analyzer = StatisticalAnalyzer()
        treatment = VariantStats(
            variant_id="t", variant_key="treatment", is_control=False,
            sample_size=100, conversions=10, conversion_rate=0.1,
        )
        control = VariantStats(
            variant_id="c", variant_key="control", is_control=True,
            sample_size=100, conversions=0, conversion_rate=0.0,
        )
        result = analyzer._compare_variants(treatment, control)
        assert result.relative_lift == float("inf")


# ===========================================================================
# Full experiment analysis (DB-backed)
# ===========================================================================


@pytest.mark.django_db
class TestExperimentAnalysisDB:
    def _setup_experiment_with_data(self):
        from django_matt.experiments.models import (
            Experiment,
            ExperimentAssignment,
            ExperimentResult,
            Variant,
        )

        exp = Experiment.objects.create(
            key="analysis-test",
            name="Analysis Test",
            status=ExperimentStatus.RUNNING.value,
            min_sample_size=10,
        )
        control = Variant.objects.create(
            experiment=exp, key="control", name="Control", is_control=True, weight=1
        )
        treatment = Variant.objects.create(
            experiment=exp, key="treatment", name="Treatment", is_control=False, weight=1
        )

        # Create assignments and results
        for i in range(50):
            a = ExperimentAssignment.objects.create(
                experiment=exp, variant=control, anonymous_id=f"ctrl-{i}"
            )
            if i < 5:  # 10% conversion rate
                ExperimentResult.objects.create(
                    assignment=a, variant=control,
                    metric_name="conversion", metric_type="conversion",
                    value=Decimal("1.0"),
                )

        for i in range(50):
            a = ExperimentAssignment.objects.create(
                experiment=exp, variant=treatment, anonymous_id=f"treat-{i}"
            )
            if i < 15:  # 30% conversion rate
                ExperimentResult.objects.create(
                    assignment=a, variant=treatment,
                    metric_name="conversion", metric_type="conversion",
                    value=Decimal("1.0"),
                )

        return exp, control, treatment

    def test_analyze_experiment_with_data(self):
        exp, _, _ = self._setup_experiment_with_data()
        result = analyze_experiment(exp)
        assert isinstance(result, ExperimentAnalysis)
        assert result.total_participants == 100
        assert result.total_conversions == 20
        assert len(result.variant_stats) == 2
        assert len(result.comparisons) == 1

    def test_analyze_no_variants(self):
        from django_matt.experiments.models import Experiment

        exp = Experiment.objects.create(
            key="empty-analysis", name="Empty", status="running"
        )
        result = analyze_experiment(exp)
        assert result.total_participants == 0
        assert result.total_conversions == 0
        assert len(result.variant_stats) == 0

    def test_analysis_recommendation(self):
        exp, _, _ = self._setup_experiment_with_data()
        result = analyze_experiment(exp)
        assert result.recommendation != ""


# ===========================================================================
# Audit log
# ===========================================================================


@pytest.mark.django_db
class TestExperimentAuditLog:
    def test_log_creation(self):
        from django_matt.experiments.models import Experiment, ExperimentAuditLog

        exp = Experiment.objects.create(key="audit-test", name="Audit Test")
        log = ExperimentAuditLog.log(
            experiment=exp,
            action="created",
            changes={"status": "draft"},
        )
        assert log.experiment_key == "audit-test"
        assert log.action == "created"
        assert str(log) == "audit-test - created"

    def test_log_with_user_and_ip(self):
        from django_matt.experiments.models import Experiment, ExperimentAuditLog

        exp = Experiment.objects.create(key="audit-ip", name="Audit IP")
        log = ExperimentAuditLog.log(
            experiment=exp,
            action="started",
            ip_address="192.168.1.1",
        )
        assert log.ip_address == "192.168.1.1"


# ===========================================================================
# Targeting rule evaluation (unit tests)
# ===========================================================================


class TestRuleEvaluation:
    def test_eq_operator(self):
        mgr = ExperimentManager()
        assert mgr._evaluate_rule(
            {"attribute": "x", "operator": "eq", "value": 5},
            {"x": 5},
        ) is True
        assert mgr._evaluate_rule(
            {"attribute": "x", "operator": "eq", "value": 5},
            {"x": 6},
        ) is False

    def test_neq_operator(self):
        mgr = ExperimentManager()
        assert mgr._evaluate_rule(
            {"attribute": "x", "operator": "neq", "value": 5},
            {"x": 6},
        ) is True

    def test_gt_gte_lt_lte(self):
        mgr = ExperimentManager()
        assert mgr._evaluate_rule(
            {"attribute": "age", "operator": "gt", "value": 18}, {"age": 21}
        ) is True
        assert mgr._evaluate_rule(
            {"attribute": "age", "operator": "gte", "value": 18}, {"age": 18}
        ) is True
        assert mgr._evaluate_rule(
            {"attribute": "age", "operator": "lt", "value": 18}, {"age": 10}
        ) is True
        assert mgr._evaluate_rule(
            {"attribute": "age", "operator": "lte", "value": 18}, {"age": 18}
        ) is True

    def test_in_operator(self):
        mgr = ExperimentManager()
        assert mgr._evaluate_rule(
            {"attribute": "country", "operator": "in", "value": ["US", "CA"]},
            {"country": "US"},
        ) is True
        assert mgr._evaluate_rule(
            {"attribute": "country", "operator": "not_in", "value": ["US", "CA"]},
            {"country": "UK"},
        ) is True

    def test_contains_operator(self):
        mgr = ExperimentManager()
        assert mgr._evaluate_rule(
            {"attribute": "email", "operator": "contains", "value": "@example.com"},
            {"email": "user@example.com"},
        ) is True

    def test_missing_attribute_passes(self):
        mgr = ExperimentManager()
        assert mgr._evaluate_rule(
            {"attribute": "missing", "operator": "eq", "value": 5},
            {},
        ) is True

    def test_unknown_operator_passes(self):
        mgr = ExperimentManager()
        assert mgr._evaluate_rule(
            {"attribute": "x", "operator": "unknown_op", "value": 5},
            {"x": 5},
        ) is True


# ===========================================================================
# Bandit algorithms (unit tests with mocks)
# ===========================================================================


class TestBanditAlgorithms:
    def _make_mock_variant(self, key, conversion_rate=0.0, assignment_count=0, conversion_count=0, weight=1):
        v = MagicMock()
        v.key = key
        v.id = key
        v.weight = weight
        v.conversion_rate = conversion_rate
        v.assignment_count = assignment_count
        v.conversion_count = conversion_count
        return v

    def test_epsilon_greedy_exploits_best(self):
        mgr = ExperimentManager()
        exp = MagicMock()
        exp.epsilon = 0.0  # Always exploit
        variants = [
            self._make_mock_variant("a", conversion_rate=0.1),
            self._make_mock_variant("b", conversion_rate=0.5),
        ]
        chosen = mgr._epsilon_greedy_assignment(variants, exp)
        assert chosen.key == "b"

    def test_ucb_explores_unvisited(self):
        mgr = ExperimentManager()
        exp = MagicMock()
        exp.exploration_weight = 2.0
        variants = [
            self._make_mock_variant("a", assignment_count=10, conversion_rate=0.5),
            self._make_mock_variant("b", assignment_count=0),
        ]
        chosen = mgr._ucb_assignment(variants, exp)
        assert chosen.key == "b"  # Unvisited gets priority

    def test_ucb_all_zero_assignments(self):
        mgr = ExperimentManager()
        exp = MagicMock()
        exp.exploration_weight = 2.0
        variants = [
            self._make_mock_variant("a", assignment_count=0),
            self._make_mock_variant("b", assignment_count=0),
        ]
        chosen = mgr._ucb_assignment(variants, exp)
        assert chosen is not None

    def test_thompson_sampling_returns_variant(self):
        mgr = ExperimentManager()
        exp = MagicMock()
        variants = [
            self._make_mock_variant("a", conversion_count=5, assignment_count=100),
            self._make_mock_variant("b", conversion_count=50, assignment_count=100),
        ]
        chosen = mgr._thompson_assignment(variants, exp)
        assert chosen is not None
        assert chosen.key in ("a", "b")

    def test_sample_beta(self):
        mgr = ExperimentManager()
        sample = mgr._sample_beta(1, 1)
        assert 0.0 <= sample <= 1.0

    def test_random_assignment_single_variant(self):
        mgr = ExperimentManager()
        exp = MagicMock()
        exp.key = "single"
        v = self._make_mock_variant("only", weight=1)
        chosen = mgr._random_assignment([v], exp, None, "anon-1")
        assert chosen.key == "only"

    def test_random_assignment_zero_weight(self):
        mgr = ExperimentManager()
        exp = MagicMock()
        exp.key = "zero-w"
        v = self._make_mock_variant("a", weight=0)
        chosen = mgr._random_assignment([v], exp, None, "anon-1")
        assert chosen.key == "a"


# ===========================================================================
# Bandit weights
# ===========================================================================


class TestBanditWeights:
    def _make_mock_variant(self, key, **kwargs):
        v = MagicMock()
        v.key = key
        v.id = key
        for k, val in kwargs.items():
            setattr(v, k, val)
        return v

    def _make_experiment(self, strategy, variants, **kwargs):
        exp = MagicMock()
        exp.strategy = strategy
        exp.variants.all.return_value = variants
        for k, val in kwargs.items():
            setattr(exp, k, val)
        return exp

    def test_random_weights(self):
        mgr = ExperimentManager()
        variants = [
            self._make_mock_variant("a", weight=1),
            self._make_mock_variant("b", weight=3),
        ]
        exp = self._make_experiment("random", variants)
        weights = mgr.get_bandit_weights(exp)
        assert weights["a"] == pytest.approx(0.25)
        assert weights["b"] == pytest.approx(0.75)

    def test_random_weights_all_zero(self):
        mgr = ExperimentManager()
        variants = [
            self._make_mock_variant("a", weight=0),
            self._make_mock_variant("b", weight=0),
        ]
        exp = self._make_experiment("random", variants)
        weights = mgr.get_bandit_weights(exp)
        assert weights["a"] == pytest.approx(0.5)

    def test_epsilon_greedy_weights(self):
        mgr = ExperimentManager()
        variants = [
            self._make_mock_variant("a", conversion_rate=0.1),
            self._make_mock_variant("b", conversion_rate=0.5),
        ]
        exp = self._make_experiment("epsilon_greedy", variants, epsilon=0.1)
        weights = mgr.get_bandit_weights(exp)
        assert weights["b"] > weights["a"]

    def test_empty_variants(self):
        mgr = ExperimentManager()
        exp = self._make_experiment("random", [])
        weights = mgr.get_bandit_weights(exp)
        assert weights == {}


# ===========================================================================
# Convenience functions
# ===========================================================================


@pytest.mark.django_db
class TestConvenienceFunctions:
    def test_get_manager_singleton(self):
        from django_matt.experiments.manager import get_manager

        m1 = get_manager()
        m2 = get_manager()
        assert m1 is m2


# ===========================================================================
# Pydantic schemas validation
# ===========================================================================


class TestExperimentSchemas:
    def test_experiment_create_schema(self):
        data = ExperimentCreate(
            key="my-exp",
            name="My Experiment",
            variants=[
                VariantCreate(key="control", name="Control", is_control=True),
                VariantCreate(key="treatment", name="Treatment"),
            ],
        )
        assert data.key == "my-exp"
        assert len(data.variants) == 2

    def test_experiment_update_schema(self):
        data = ExperimentUpdate(name="Updated Name")
        assert data.name == "Updated Name"
        assert data.strategy is None

    def test_variant_update_schema(self):
        data = VariantUpdate(weight=5)
        assert data.weight == 5
        assert data.name is None

    def test_targeting_rule_schema(self):
        rule = TargetingRule(attribute="country", operator="in", value=["US", "CA"])
        assert rule.attribute == "country"

    def test_conversion_event_schema(self):
        event = ConversionEvent(experiment_key="my-exp", value=1.0)
        assert event.metric_name == "conversion"

    def test_revenue_event_schema(self):
        event = RevenueEvent(experiment_key="my-exp", amount=49.99)
        assert event.amount == 49.99

    def test_assignment_request_schema(self):
        req = AssignmentRequest(experiment_key="my-exp")
        assert req.create is True

    def test_experiment_stats_response(self):
        stats = ExperimentStatsResponse(
            total_experiments=10,
            draft_experiments=2,
            running_experiments=5,
            paused_experiments=1,
            completed_experiments=2,
            total_assignments=1000,
            total_conversions=100,
        )
        assert stats.total_experiments == 10

    def test_experiment_list_response(self):
        resp = ExperimentListResponse(items=[], total=0)
        assert resp.page == 1
        assert resp.page_size == 20


# ===========================================================================
# Edge cases: single variant, 100% allocation
# ===========================================================================


@pytest.mark.django_db
class TestEdgeCases:
    def test_single_variant_experiment(self):
        from django_matt.experiments.models import Experiment, Variant

        exp = Experiment.objects.create(
            key="single-var", name="Single", status=ExperimentStatus.RUNNING.value
        )
        only = Variant.objects.create(
            experiment=exp, key="only", name="Only", weight=1
        )
        mgr = ExperimentManager()
        assignment = mgr.get_assignment("single-var", anonymous_id="user-1")
        assert assignment is not None
        assert assignment.variant.key == "only"

    def test_heavily_weighted_variant(self):
        from django_matt.experiments.models import Experiment, Variant

        exp = Experiment.objects.create(
            key="heavy-weight", name="Heavy", status=ExperimentStatus.RUNNING.value
        )
        Variant.objects.create(experiment=exp, key="light", name="Light", weight=1)
        Variant.objects.create(experiment=exp, key="heavy", name="Heavy", weight=999)
        mgr = ExperimentManager()
        # Most users should get the heavy variant
        assignments = []
        for i in range(20):
            a = mgr.get_assignment("heavy-weight", anonymous_id=f"hw-user-{i}")
            assignments.append(a.variant.key)
        heavy_count = assignments.count("heavy")
        assert heavy_count >= 15  # At least 75% should get heavy

    def test_is_running_false_when_past_end_date(self):
        from datetime import timedelta

        from django.utils import timezone

        from django_matt.experiments.models import Experiment

        exp = Experiment.objects.create(
            key="past-end",
            name="Past End",
            status=ExperimentStatus.RUNNING.value,
            end_date=timezone.now() - timedelta(days=1),
        )
        assert exp.is_running is False

    def test_get_variant_weights_empty(self):
        from django_matt.experiments.models import Experiment

        exp = Experiment.objects.create(key="no-vars", name="No Variants")
        assert exp.get_variant_weights() == {}
