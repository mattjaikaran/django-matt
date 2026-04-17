# Experiments

A/B testing with multi-armed bandit algorithms (epsilon-greedy, UCB, Thompson sampling), statistical analysis, variant-based routing, and conversion tracking.

## Quick Start

```python
from django_matt.experiments.decorators import experiment

@experiment(
    "checkout_test",
    variant_handlers={
        "control": checkout_v1,
        "treatment": checkout_v2,
    },
    default_variant="control",
)
async def checkout(request):
    # Fallback if no variant matches
    return checkout_v1(request)
```

## Configuration

Experiments are managed through the database. Create them via the admin or programmatically:

```python
from django_matt.experiments.models import Experiment, Variant, ExperimentStatus, AssignmentStrategy

# Create an experiment
exp = await Experiment.objects.acreate(
    key="checkout_test",
    name="Checkout Flow Test",
    description="Test new checkout flow vs. current",
    status=ExperimentStatus.RUNNING.value,
    strategy=AssignmentStrategy.RANDOM.value,
    target_confidence=0.95,
    min_sample_size=1000,
    primary_metric="conversion",
)

# Add variants
await Variant.objects.acreate(experiment=exp, key="control", name="Current Checkout", weight=50, is_control=True)
await Variant.objects.acreate(experiment=exp, key="treatment", name="New Checkout", weight=50)
```

## Key Features

### Assignment Strategies

| Strategy | Key | Description |
|----------|-----|-------------|
| Random | `random` | Random assignment based on variant weights |
| Epsilon-Greedy | `epsilon_greedy` | Exploit the best variant, explore with probability epsilon |
| UCB | `ucb` | Upper Confidence Bound -- balances exploration/exploitation |
| Thompson Sampling | `thompson` | Bayesian approach using posterior distributions |

### ExperimentManager

Handles user assignment with bandit algorithms and exclusion groups:

```python
from django_matt.experiments.manager import ExperimentManager

manager = ExperimentManager()

# Get or create assignment
assignment = manager.get_assignment(
    experiment_key="checkout_test",
    user=request.user,
    anonymous_id="anon-abc",
    create=True,
    context={"country": "US"},
)

if assignment:
    print(assignment.variant.key)  # "control" or "treatment"
```

### Decorators

**@experiment** -- Route to different handlers based on variant:

```python
from django_matt.experiments.decorators import experiment

@experiment(
    "pricing_test",
    variant_handlers={
        "control": show_old_pricing,
        "new_layout": show_new_pricing,
    },
    track_exposure=True,
)
async def pricing(request, variant=None):
    # variant is injected if no handler matches
    return render(request, "pricing.html", {"variant": variant})
```

**@requires_experiment** -- Gate access to experiment participants:

```python
from django_matt.experiments.decorators import requires_experiment

@requires_experiment("beta_feature")
async def beta_endpoint(request):
    return JsonResponse({"feature": "enabled"})

@requires_experiment("checkout_test", allowed_variants=["treatment_a", "treatment_b"])
async def new_checkout(request):
    ...
```

**@track_conversion** -- Track conversion after successful response:

```python
from django_matt.experiments.decorators import track_conversion

@track_conversion("checkout_test", metric_name="purchase", value=1.0)
async def complete_checkout(request):
    # Process checkout...
    return JsonResponse({"success": True})
# Conversion tracked only if response is 2xx
```

**@with_experiment_context** -- Ensure ExperimentContext is available:

```python
from django_matt.experiments.decorators import with_experiment_context

@with_experiment_context
async def my_view(request):
    from django_matt.experiments.context import ExperimentContext
    ctx = ExperimentContext.from_request(request)
    variant = ctx.get_variant("my_experiment")
    ...
```

### ExperimentMixin

For class-based views:

```python
from django_matt.experiments.decorators import ExperimentMixin

class CheckoutView(ExperimentMixin, APIController):
    experiment_key = "checkout_test"
    track_exposure = True

    async def get(self, request):
        variant = self.get_variant()
        payload = self.get_variant_payload()

        if self.is_in_variant("treatment"):
            return self.new_checkout(request)
        return self.old_checkout(request)

    async def post(self, request):
        # Track conversion on successful purchase
        self.track_conversion(metric_name="purchase", value=99.99)
        return JsonResponse({"status": "ok"})
```

### Statistical Analysis

```python
from django_matt.experiments.analysis import ExperimentAnalysis, VariantStats, ComparisonResult

# ExperimentAnalysis contains:
# - variant_stats: list[VariantStats] -- per-variant sample size, conversion rate, CI
# - comparisons: list[ComparisonResult] -- vs. control with p-value, z-score, lift
# - has_winner: bool
# - winner_variant_key: str | None
# - winner_confidence: float

# VariantStats fields:
# sample_size, conversions, conversion_rate, mean_value, std_dev,
# confidence_interval_lower, confidence_interval_upper

# ComparisonResult fields:
# absolute_lift, relative_lift, lift_confidence_interval,
# p_value, z_score, is_significant, confidence_level,
# statistical_power, required_sample_size
```

### Experiment Lifecycle

```python
from django_matt.experiments.models import ExperimentStatus

# Status flow: DRAFT -> RUNNING -> PAUSED -> RUNNING -> COMPLETED -> ARCHIVED
# Experiments only accept assignments when status is RUNNING.

# Query helpers
running = Experiment.objects.active()           # Running experiments
exp = Experiment.objects.by_key("checkout_test")  # By key
eligible = Experiment.objects.for_user(user)     # User-eligible experiments
```

## Practical Example

```python
from django_matt.experiments.decorators import experiment, track_conversion

# Step 1: Route users to different checkout flows
@experiment(
    "checkout_v2_test",
    variant_handlers={
        "control": lambda r: render(r, "checkout/v1.html"),
        "treatment": lambda r: render(r, "checkout/v2.html"),
    },
)
async def checkout(request, variant=None):
    return render(request, "checkout/v1.html")

# Step 2: Track purchases as conversions
@track_conversion("checkout_v2_test", metric_name="purchase")
async def complete_purchase(request):
    order = await create_order(request)
    return JsonResponse({"order_id": order.id})

# Step 3: Analyze results (management command or admin action)
from django_matt.experiments.models import Experiment

exp = await Experiment.objects.aget(key="checkout_v2_test")
# Use the analysis module to compute significance and declare winner
```
