# Flag Types

django-matt supports three types of feature flags, each suited for different use cases.

## Boolean Flags

Simple on/off switches for features.

### Use Cases

- Feature gates (show/hide features)
- Kill switches for emergency disabling
- Environment-specific features
- Beta access control

### Creating Boolean Flags

```python
from django_matt.flags.models import FeatureFlag, FlagType, FlagStatus

flag = FeatureFlag.objects.create(
    key="new_dashboard",
    name="New Dashboard",
    flag_type=FlagType.BOOLEAN.value,
    status=FlagStatus.ACTIVE.value,
    enabled_by_default=True,  # On for everyone
)
```

### Checking Boolean Flags

```python
from django_matt.flags import feature_enabled

if feature_enabled("new_dashboard", user=request.user):
    return render_new_dashboard()
else:
    return render_legacy_dashboard()
```

### Kill Switch Pattern

```python
# Create a normally-enabled flag
FeatureFlag.objects.create(
    key="external_api_enabled",
    name="External API Calls",
    flag_type=FlagType.BOOLEAN.value,
    status=FlagStatus.ACTIVE.value,
    enabled_by_default=True,
)

# In code
if feature_enabled("external_api_enabled"):
    data = await call_external_api()
else:
    # Fallback when API is disabled
    data = get_cached_data()

# To disable: Just flip enabled_by_default to False in admin
```

---

## Percentage Rollout Flags

Gradually roll out features to a percentage of users.

### Use Cases

- Staged rollouts (1% -> 10% -> 50% -> 100%)
- Canary deployments
- Reducing blast radius of new features
- Load testing with real traffic

### Creating Percentage Flags

```python
flag = FeatureFlag.objects.create(
    key="new_checkout_flow",
    name="New Checkout Flow",
    flag_type=FlagType.PERCENTAGE.value,
    status=FlagStatus.ACTIVE.value,
    rollout_percentage=10,  # Enable for 10% of users
)
```

### How Percentage Rollout Works

The rollout uses consistent hashing based on user ID and flag key:

```python
# Pseudo-code of rollout logic
hash_input = f"{flag_key}:{user_id}"
hash_value = md5(hash_input).hexdigest()
bucket = int(hash_value, 16) % 100

# User is enabled if their bucket is less than rollout percentage
enabled = bucket < rollout_percentage
```

This ensures:

- **Consistency**: Same user always gets same result for a flag
- **Distribution**: Users are evenly distributed across buckets
- **Stickiness**: User assignment doesn't change when percentage increases

### Gradual Rollout Example

```python
# Week 1: 5% rollout
flag.rollout_percentage = 5
flag.save()

# Week 2: Looking good, increase to 25%
flag.rollout_percentage = 25
flag.save()

# Week 3: No issues, increase to 50%
flag.rollout_percentage = 50
flag.save()

# Week 4: Full rollout
flag.rollout_percentage = 100
flag.save()

# Or convert to boolean when fully rolled out
flag.flag_type = FlagType.BOOLEAN.value
flag.enabled_by_default = True
flag.save()
```

### Checking Percentage Flags

```python
from django_matt.flags import feature_enabled

# Works the same as boolean flags
if feature_enabled("new_checkout_flow", user=request.user):
    return new_checkout()
else:
    return legacy_checkout()

# Note: Without a user, percentage flags return False
# The user is required for consistent bucketing
```

---

## Variant Flags (A/B Testing)

Assign users to different variants for experimentation.

### Use Cases

- A/B testing UI changes
- Multivariate testing (A/B/C/D)
- Price testing
- Algorithm comparison

### Creating Variant Flags

```python
flag = FeatureFlag.objects.create(
    key="pricing_experiment",
    name="Pricing Page A/B Test",
    flag_type=FlagType.VARIANT.value,
    status=FlagStatus.ACTIVE.value,
    enabled_by_default=True,
    variants={
        "variants": [
            {
                "key": "control",
                "name": "Original Pricing",
                "weight": 50,
                "payload": {"theme": "classic"}
            },
            {
                "key": "treatment_a",
                "name": "New Pricing Layout",
                "weight": 30,
                "payload": {"theme": "modern", "show_annual": True}
            },
            {
                "key": "treatment_b",
                "name": "Simplified Pricing",
                "weight": 20,
                "payload": {"theme": "minimal", "tiers": 2}
            }
        ],
        "default_variant": "control"
    },
)
```

### Variant Configuration

| Field | Type | Description |
|-------|------|-------------|
| `key` | string | Unique variant identifier |
| `name` | string | Human-readable name |
| `weight` | integer | Relative weight for assignment (higher = more likely) |
| `payload` | object | Variant-specific configuration data |

### Getting Variant Assignment

```python
from django_matt.flags import get_variant

variant = get_variant("pricing_experiment", user=request.user)

if variant == "control":
    template = "pricing/original.html"
elif variant == "treatment_a":
    template = "pricing/new_layout.html"
elif variant == "treatment_b":
    template = "pricing/simplified.html"

return render(request, template)
```

### Using Variant Payloads

```python
from django_matt.flags.models import FeatureFlag

flag = FeatureFlag.objects.get(key="pricing_experiment")
variant_key = flag.get_variant(user=request.user)

# Get variant configuration
variants = flag.variants.get("variants", [])
variant_config = next(
    (v for v in variants if v["key"] == variant_key),
    None
)

if variant_config:
    payload = variant_config.get("payload", {})
    theme = payload.get("theme", "classic")
    show_annual = payload.get("show_annual", False)
```

### Variant Decorator

```python
from django_matt.flags import variant_flag

def pricing_control(request):
    return render(request, "pricing/control.html")

def pricing_treatment_a(request):
    return render(request, "pricing/treatment_a.html")

def pricing_treatment_b(request):
    return render(request, "pricing/treatment_b.html")

@variant_flag(
    "pricing_experiment",
    variant_handlers={
        "control": pricing_control,
        "treatment_a": pricing_treatment_a,
        "treatment_b": pricing_treatment_b,
    },
    default_variant="control",
)
async def pricing_page(request):
    # Fallback if no variant matches
    return render(request, "pricing/default.html")
```

### Weight Distribution

Weights determine the probability of assignment:

```python
variants = [
    {"key": "control", "weight": 50},      # 50%
    {"key": "treatment_a", "weight": 30},  # 30%
    {"key": "treatment_b", "weight": 20},  # 20%
]

# Weights don't need to sum to 100
# They're proportional:
variants = [
    {"key": "control", "weight": 1},       # 33.3%
    {"key": "treatment_a", "weight": 1},   # 33.3%
    {"key": "treatment_b", "weight": 1},   # 33.3%
]
```

### Forcing Variants via Overrides

```python
from django_matt.flags.models import FlagOverride, OverrideType

# Force specific user to see treatment_a
FlagOverride.objects.create(
    flag=flag,
    override_type=OverrideType.USER.value,
    target_id=str(user.pk),
    enabled=True,
    variant="treatment_a",
)
```

---

## Type Comparison

| Feature | Boolean | Percentage | Variant |
|---------|---------|------------|---------|
| Simple on/off | Yes | No | No |
| Gradual rollout | No | Yes | Yes (via weights) |
| Multiple variations | No | No | Yes |
| Requires user | No | Yes | Recommended |
| A/B testing | No | No | Yes |
| Kill switch | Yes | Yes | Yes |

## Choosing the Right Type

```
Need to show/hide a feature?
├── For everyone → Boolean (enabled_by_default)
├── For some users → Boolean + Overrides
└── Gradually → Percentage

Need to test variations?
├── 2 variations → Variant (50/50 weights)
├── 3+ variations → Variant (custom weights)
└── Need metrics → Variant + analytics integration

Need emergency control?
└── Boolean (kill switch pattern)
```

## See Also

- [Targeting](targeting.md) - Target specific users with overrides
- [Decorators](decorators.md) - Use flags with decorators
- [Best Practices](best-practices.md) - Naming and lifecycle
