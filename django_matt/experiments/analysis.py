"""
Statistical analysis for experiments.

Provides chi-square tests, t-tests, confidence intervals, and significance testing
for A/B test experiments.
"""

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger("django_matt.experiments")


@dataclass
class VariantStats:
    """Statistics for a single variant."""

    variant_id: str
    variant_key: str
    is_control: bool
    sample_size: int
    conversions: int = 0
    conversion_rate: float = 0.0
    total_value: float = 0.0
    mean_value: float = 0.0
    std_dev: float = 0.0
    variance: float = 0.0
    confidence_interval_lower: float = 0.0
    confidence_interval_upper: float = 0.0


@dataclass
class ComparisonResult:
    """Result of comparing a variant against control."""

    variant_id: str
    variant_key: str
    control_id: str
    control_key: str

    # Effect sizes
    absolute_lift: float = 0.0  # Absolute difference
    relative_lift: float = 0.0  # Percentage improvement
    lift_confidence_interval: tuple[float, float] = (0.0, 0.0)

    # Statistical significance
    p_value: float = 1.0
    z_score: float = 0.0
    is_significant: bool = False
    confidence_level: float = 0.95

    # Power analysis
    statistical_power: float = 0.0
    required_sample_size: int = 0


@dataclass
class ExperimentAnalysis:
    """Complete analysis of an experiment."""

    experiment_id: str
    experiment_key: str
    status: str
    total_participants: int
    total_conversions: int
    overall_conversion_rate: float

    # Per-variant statistics
    variant_stats: list[VariantStats] = field(default_factory=list)

    # Comparisons against control
    comparisons: list[ComparisonResult] = field(default_factory=list)

    # Winner detection
    has_winner: bool = False
    winner_variant_id: str | None = None
    winner_variant_key: str | None = None
    winner_confidence: float = 0.0
    winner_reason: str = ""

    # Recommendations
    should_continue: bool = True
    recommendation: str = ""
    days_to_significance: int | None = None

    # Metadata
    analysis_timestamp: str = ""
    confidence_level: float = 0.95
    minimum_sample_size: int = 100


class StatisticalAnalyzer:
    """
    Statistical analyzer for A/B test experiments.

    Provides methods for:
    - Chi-square tests for conversion rate comparisons
    - T-tests for continuous metrics
    - Confidence interval calculations
    - Automatic winner detection
    - Power analysis and sample size calculations
    """

    def __init__(self, confidence_level: float = 0.95):
        """
        Initialize the analyzer.

        Args:
            confidence_level: Required confidence level (default 0.95)
        """
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level

    def analyze_experiment(
        self,
        experiment,
        metric_name: str = "conversion",
    ) -> ExperimentAnalysis:
        """
        Perform complete analysis of an experiment.

        Args:
            experiment: Experiment model instance
            metric_name: Name of metric to analyze

        Returns:
            ExperimentAnalysis with all results
        """
        from django.utils import timezone

        from django_matt.experiments.models import ExperimentResult, MetricType

        variants = list(experiment.variants.all())
        if not variants:
            return ExperimentAnalysis(
                experiment_id=str(experiment.id),
                experiment_key=experiment.key,
                status=experiment.status,
                total_participants=0,
                total_conversions=0,
                overall_conversion_rate=0.0,
                analysis_timestamp=timezone.now().isoformat(),
            )

        # Gather variant statistics
        variant_stats_list = []
        control_stats = None
        total_participants = 0
        total_conversions = 0

        for variant in variants:
            assignments = variant.assignments.count()
            conversions = ExperimentResult.objects.filter(
                variant=variant,
                metric_name=metric_name,
                metric_type=MetricType.CONVERSION.value,
                value__gt=0,
            ).count()

            # Calculate statistics
            conversion_rate = conversions / assignments if assignments > 0 else 0.0

            # Calculate confidence interval using Wilson score interval
            ci_lower, ci_upper = self._wilson_confidence_interval(
                conversions, assignments, self.confidence_level
            )

            stats = VariantStats(
                variant_id=str(variant.id),
                variant_key=variant.key,
                is_control=variant.is_control,
                sample_size=assignments,
                conversions=conversions,
                conversion_rate=conversion_rate,
                confidence_interval_lower=ci_lower,
                confidence_interval_upper=ci_upper,
            )

            variant_stats_list.append(stats)
            total_participants += assignments
            total_conversions += conversions

            if variant.is_control:
                control_stats = stats

        # If no control, use first variant as baseline
        if control_stats is None and variant_stats_list:
            control_stats = variant_stats_list[0]

        # Compare variants against control
        comparisons = []
        if control_stats:
            for stats in variant_stats_list:
                if stats.variant_id != control_stats.variant_id:
                    comparison = self._compare_variants(stats, control_stats)
                    comparisons.append(comparison)

        # Determine winner
        has_winner = False
        winner_variant_id = None
        winner_variant_key = None
        winner_confidence = 0.0
        winner_reason = ""

        best_variant = None
        best_lift = 0.0

        for comparison in comparisons:
            if comparison.is_significant and comparison.relative_lift > best_lift:
                best_lift = comparison.relative_lift
                best_variant = comparison

        if best_variant and best_lift > 0:
            has_winner = True
            winner_variant_id = best_variant.variant_id
            winner_variant_key = best_variant.variant_key
            winner_confidence = 1 - best_variant.p_value
            winner_reason = (
                f"Variant '{best_variant.variant_key}' shows {best_lift:.1%} improvement "
                f"with {winner_confidence:.1%} confidence (p={best_variant.p_value:.4f})"
            )

        # Generate recommendation
        should_continue = True
        recommendation = ""

        min_sample = experiment.min_sample_size
        samples_needed = min_sample - min(s.sample_size for s in variant_stats_list)

        if samples_needed > 0:
            should_continue = True
            recommendation = (
                f"Continue collecting data. Need ~{samples_needed} more samples per variant."
            )
        elif has_winner:
            should_continue = False
            recommendation = f"Winner found: {winner_variant_key}. Consider stopping experiment."
        # Check if we should continue based on power
        elif any(c.statistical_power < 0.8 for c in comparisons):
            should_continue = True
            recommendation = "Low statistical power. Continue to increase sample size."
        else:
            should_continue = False
            recommendation = "No significant difference detected. Consider stopping or redesigning."

        return ExperimentAnalysis(
            experiment_id=str(experiment.id),
            experiment_key=experiment.key,
            status=experiment.status,
            total_participants=total_participants,
            total_conversions=total_conversions,
            overall_conversion_rate=total_conversions / total_participants
            if total_participants > 0
            else 0.0,
            variant_stats=variant_stats_list,
            comparisons=comparisons,
            has_winner=has_winner,
            winner_variant_id=winner_variant_id,
            winner_variant_key=winner_variant_key,
            winner_confidence=winner_confidence,
            winner_reason=winner_reason,
            should_continue=should_continue,
            recommendation=recommendation,
            analysis_timestamp=timezone.now().isoformat(),
            confidence_level=self.confidence_level,
            minimum_sample_size=min_sample,
        )

    def _compare_variants(
        self,
        treatment: VariantStats,
        control: VariantStats,
    ) -> ComparisonResult:
        """
        Compare a treatment variant against control.

        Uses chi-square test for conversion rates.
        """
        # Calculate lifts
        if control.conversion_rate > 0:
            relative_lift = (
                treatment.conversion_rate - control.conversion_rate
            ) / control.conversion_rate
        else:
            relative_lift = 0.0 if treatment.conversion_rate == 0 else float("inf")

        absolute_lift = treatment.conversion_rate - control.conversion_rate

        # Chi-square test
        p_value, z_score = self._chi_square_test(
            treatment.conversions,
            treatment.sample_size,
            control.conversions,
            control.sample_size,
        )

        is_significant = p_value < self.alpha

        # Calculate lift confidence interval
        lift_ci = self._lift_confidence_interval(
            treatment.conversions,
            treatment.sample_size,
            control.conversions,
            control.sample_size,
        )

        # Calculate statistical power
        power = self._calculate_power(
            treatment.sample_size,
            control.sample_size,
            control.conversion_rate,
            treatment.conversion_rate,
        )

        # Calculate required sample size for 80% power
        required_n = self._required_sample_size(
            control.conversion_rate,
            treatment.conversion_rate
            if treatment.conversion_rate != control.conversion_rate
            else control.conversion_rate * 1.1,
            power=0.8,
        )

        return ComparisonResult(
            variant_id=treatment.variant_id,
            variant_key=treatment.variant_key,
            control_id=control.variant_id,
            control_key=control.variant_key,
            absolute_lift=absolute_lift,
            relative_lift=relative_lift,
            lift_confidence_interval=lift_ci,
            p_value=p_value,
            z_score=z_score,
            is_significant=is_significant,
            confidence_level=self.confidence_level,
            statistical_power=power,
            required_sample_size=required_n,
        )

    def _chi_square_test(
        self,
        conversions_a: int,
        total_a: int,
        conversions_b: int,
        total_b: int,
    ) -> tuple[float, float]:
        """
        Perform chi-square test for two proportions.

        Returns (p_value, z_score).
        """
        if total_a == 0 or total_b == 0:
            return 1.0, 0.0

        # Pooled proportion
        p_pool = (conversions_a + conversions_b) / (total_a + total_b)

        if p_pool == 0 or p_pool == 1:
            return 1.0, 0.0

        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / total_a + 1 / total_b))

        if se == 0:
            return 1.0, 0.0

        # Z-score
        p_a = conversions_a / total_a
        p_b = conversions_b / total_b
        z = (p_a - p_b) / se

        # Two-tailed p-value using normal approximation
        p_value = 2 * (1 - self._normal_cdf(abs(z)))

        return p_value, z

    def _wilson_confidence_interval(
        self,
        successes: int,
        total: int,
        confidence: float = 0.95,
    ) -> tuple[float, float]:
        """
        Calculate Wilson score confidence interval for a proportion.

        More accurate than normal approximation for small samples or extreme proportions.
        """
        if total == 0:
            return 0.0, 0.0

        z = self._normal_ppf(1 - (1 - confidence) / 2)
        p = successes / total
        n = total

        denominator = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denominator
        margin = (z / denominator) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))

        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)

        return lower, upper

    def _lift_confidence_interval(
        self,
        conversions_a: int,
        total_a: int,
        conversions_b: int,
        total_b: int,
        confidence: float = 0.95,
    ) -> tuple[float, float]:
        """
        Calculate confidence interval for the difference in proportions.
        """
        if total_a == 0 or total_b == 0:
            return 0.0, 0.0

        p_a = conversions_a / total_a
        p_b = conversions_b / total_b
        diff = p_a - p_b

        # Standard error of difference
        se = math.sqrt((p_a * (1 - p_a) / total_a) + (p_b * (1 - p_b) / total_b))

        z = self._normal_ppf(1 - (1 - confidence) / 2)
        margin = z * se

        return diff - margin, diff + margin

    def _calculate_power(
        self,
        n_treatment: int,
        n_control: int,
        p_control: float,
        p_treatment: float,
        alpha: float = 0.05,
    ) -> float:
        """
        Calculate statistical power of the test.
        """
        if n_treatment == 0 or n_control == 0:
            return 0.0

        if p_control == p_treatment:
            return alpha  # Power equals alpha under null

        # Effect size (Cohen's h)
        h = 2 * math.asin(math.sqrt(p_treatment)) - 2 * math.asin(math.sqrt(p_control))

        # Harmonic mean of sample sizes
        n_harmonic = 2 * n_treatment * n_control / (n_treatment + n_control)

        # Non-centrality parameter
        ncp = abs(h) * math.sqrt(n_harmonic / 2)

        # Critical value
        z_alpha = self._normal_ppf(1 - alpha / 2)

        # Power (approximate)
        power = 1 - self._normal_cdf(z_alpha - ncp) + self._normal_cdf(-z_alpha - ncp)

        return min(1.0, max(0.0, power))

    def _required_sample_size(
        self,
        p_control: float,
        p_treatment: float,
        power: float = 0.8,
        alpha: float = 0.05,
    ) -> int:
        """
        Calculate required sample size per group for desired power.
        """
        if p_control == p_treatment:
            return float("inf")

        z_alpha = self._normal_ppf(1 - alpha / 2)
        z_beta = self._normal_ppf(power)

        p_avg = (p_control + p_treatment) / 2
        effect = abs(p_treatment - p_control)

        numerator = (
            z_alpha * math.sqrt(2 * p_avg * (1 - p_avg))
            + z_beta * math.sqrt(p_control * (1 - p_control) + p_treatment * (1 - p_treatment))
        ) ** 2
        denominator = effect**2

        return int(math.ceil(numerator / denominator))

    def _normal_cdf(self, x: float) -> float:
        """
        Standard normal cumulative distribution function.
        """
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _normal_ppf(self, p: float) -> float:
        """
        Percent point function (inverse CDF) of standard normal.

        Uses rational approximation from Abramowitz and Stegun.
        """
        if p <= 0:
            return float("-inf")
        if p >= 1:
            return float("inf")
        if p == 0.5:
            return 0.0

        # Use symmetry
        if p > 0.5:
            return -self._normal_ppf(1 - p)

        t = math.sqrt(-2 * math.log(p))

        # Rational approximation coefficients
        c0 = 2.515517
        c1 = 0.802853
        c2 = 0.010328
        d1 = 1.432788
        d2 = 0.189269
        d3 = 0.001308

        return -(t - (c0 + c1 * t + c2 * t**2) / (1 + d1 * t + d2 * t**2 + d3 * t**3))

    def t_test(
        self,
        values_a: list[float],
        values_b: list[float],
    ) -> tuple[float, float]:
        """
        Perform independent samples t-test.

        Returns (p_value, t_statistic).
        """
        n_a = len(values_a)
        n_b = len(values_b)

        if n_a < 2 or n_b < 2:
            return 1.0, 0.0

        mean_a = sum(values_a) / n_a
        mean_b = sum(values_b) / n_b

        var_a = sum((x - mean_a) ** 2 for x in values_a) / (n_a - 1)
        var_b = sum((x - mean_b) ** 2 for x in values_b) / (n_b - 1)

        # Pooled standard error (Welch's t-test)
        se = math.sqrt(var_a / n_a + var_b / n_b)

        if se == 0:
            return 1.0, 0.0

        t = (mean_a - mean_b) / se

        # Degrees of freedom (Welch-Satterthwaite)
        df_num = (var_a / n_a + var_b / n_b) ** 2
        df_den = (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
        df = df_num / df_den if df_den > 0 else 1

        # Approximate p-value using normal distribution for large df
        if df > 30:
            p_value = 2 * (1 - self._normal_cdf(abs(t)))
        else:
            # Use beta function approximation for t-distribution
            p_value = self._t_distribution_pvalue(t, df)

        return p_value, t

    def _t_distribution_pvalue(self, t: float, df: float) -> float:
        """
        Approximate two-tailed p-value from t-distribution.
        """
        # Use normal approximation for simplicity
        # For more accuracy, use scipy.stats.t
        x = df / (df + t**2)
        # Beta regularized incomplete function approximation
        if df > 30:
            return 2 * (1 - self._normal_cdf(abs(t)))
        # Rough approximation
        return 2 * (1 - self._normal_cdf(abs(t) * math.sqrt(df / (df + 2))))


def analyze_experiment(
    experiment,
    metric_name: str = "conversion",
    confidence_level: float = 0.95,
) -> ExperimentAnalysis:
    """
    Convenience function to analyze an experiment.

    Args:
        experiment: Experiment model instance
        metric_name: Name of metric to analyze
        confidence_level: Required confidence level

    Returns:
        ExperimentAnalysis with results
    """
    analyzer = StatisticalAnalyzer(confidence_level=confidence_level)
    return analyzer.analyze_experiment(experiment, metric_name)


__all__ = [
    "VariantStats",
    "ComparisonResult",
    "ExperimentAnalysis",
    "StatisticalAnalyzer",
    "analyze_experiment",
]
