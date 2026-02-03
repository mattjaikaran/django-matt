# Feature Flag Best Practices

Guidelines for effectively managing feature flags in your application.

## Naming Conventions

### Use Descriptive, Consistent Names

```python
# Good - clear and descriptive
"new_checkout_flow"
"enable_ai_recommendations"
"show_pricing_v2"
"use_optimized_search"

# Avoid - vague or inconsistent
"flag1"
"test_thing"
"NEW_FEATURE"  # Inconsistent casing
```

### Naming Patterns

| Pattern | Example | Use Case |
|---------|---------|----------|
| `enable_*` | `enable_dark_mode` | On/off features |
| `show_*` | `show_beta_banner` | UI visibility |
| `use_*` | `use_new_api` | Implementation choice |
| `allow_*` | `allow_bulk_export` | Permission-like features |
| `*_experiment` | `checkout_experiment` | A/B tests |
| `*_rollout` | `search_v2_rollout` | Gradual releases |

### Namespace by Domain

```python
# Prefix with domain/module
"billing_stripe_checkout"
"auth_passwordless_login"
"dashboard_new_charts"
"api_v2_endpoints"

# Or use dots (if your system supports)
"billing.stripe_checkout"
"auth.passwordless"
```

---

## Flag Lifecycle

### 1. Planning

Before creating a flag:

- [ ] Define clear success criteria
- [ ] Determine flag type (boolean/percentage/variant)
- [ ] Plan targeting rules
- [ ] Set expected lifetime
- [ ] Document the flag

### 2. Implementation

```python
# Create with documentation
FeatureFlag.objects.create(
    key="new_search_algorithm",
    name="New Search Algorithm",
    description="""
    Uses ML-based search ranking instead of keyword matching.

    Success criteria:
    - CTR improvement > 5%
    - Search latency < 200ms p95

    Owner: search-team@company.com
    Ticket: JIRA-1234
    Expected removal: 2024-Q2
    """,
    flag_type=FlagType.PERCENTAGE.value,
    status=FlagStatus.INACTIVE.value,
    metadata={
        "owner": "search-team",
        "ticket": "JIRA-1234",
        "created_date": "2024-01-15",
        "expected_removal": "2024-04-01",
    },
)
```

### 3. Testing

```python
# Test both paths
def test_feature_enabled(self):
    backend = MemoryBackend()
    backend.set_flag("new_search", enabled=True)

    result = search_view(self.request)
    assert "new_results" in result

def test_feature_disabled(self):
    backend = MemoryBackend()
    backend.set_flag("new_search", enabled=False)

    result = search_view(self.request)
    assert "legacy_results" in result
```

### 4. Rollout

```python
# Gradual rollout schedule
# Day 1: 1% (internal testing)
flag.rollout_percentage = 1
flag.save()

# Day 3: 10% (early adopters)
flag.rollout_percentage = 10
flag.save()

# Day 7: 50% (half users)
flag.rollout_percentage = 50
flag.save()

# Day 14: 100% (full rollout)
flag.rollout_percentage = 100
flag.save()

# Day 21: Remove flag (cleanup)
```

### 5. Cleanup

```python
# After successful rollout, remove the flag
# 1. Update code to remove flag checks
# 2. Archive the flag
flag.status = FlagStatus.ARCHIVED.value
flag.save()

# 3. Later, delete the flag
# flag.delete()  # Or keep for audit history
```

---

## Code Organization

### Centralize Flag Keys

```python
# flags/keys.py
class FeatureFlags:
    """Central registry of feature flag keys."""

    # Checkout features
    NEW_CHECKOUT = "new_checkout_flow"
    EXPRESS_CHECKOUT = "express_checkout"

    # Search features
    ML_SEARCH = "ml_search_ranking"
    SEMANTIC_SEARCH = "semantic_search"

    # UI features
    DARK_MODE = "enable_dark_mode"
    NEW_DASHBOARD = "new_dashboard_v2"

# Usage
from myapp.flags.keys import FeatureFlags

if feature_enabled(FeatureFlags.NEW_CHECKOUT, user=user):
    ...
```

### Create Helper Functions

```python
# flags/helpers.py
from django_matt.flags import feature_enabled, get_variant

def is_premium_feature_enabled(user, feature_key):
    """Check if a premium feature is enabled for user."""
    if not user.subscription.is_premium:
        return False
    return feature_enabled(feature_key, user=user)

def get_experiment_variant(user, experiment_key, default="control"):
    """Get variant with tracking."""
    variant = get_variant(experiment_key, user=user, default=default)
    track_experiment_exposure(user, experiment_key, variant)
    return variant
```

### Keep Flag Checks Simple

```python
# Good - simple, clear check
if feature_enabled("new_checkout", user=request.user):
    return new_checkout()
return legacy_checkout()

# Avoid - complex nested logic
if feature_enabled("new_checkout", user=request.user):
    if feature_enabled("express_option", user=request.user):
        if get_variant("express_experiment") == "fast":
            return fast_express_checkout()
        return express_checkout()
    return new_checkout()
return legacy_checkout()

# Better - extract to functions
def get_checkout_handler(user):
    if not feature_enabled("new_checkout", user=user):
        return legacy_checkout

    if feature_enabled("express_option", user=user):
        variant = get_variant("express_experiment", user=user)
        if variant == "fast":
            return fast_express_checkout
        return express_checkout

    return new_checkout
```

---

## Testing Strategies

### Unit Tests with Memory Backend

```python
import pytest
from django_matt.flags.backends import MemoryBackend

@pytest.fixture
def flags():
    backend = MemoryBackend()
    yield backend
    backend.clear()

def test_with_flag_enabled(flags, mocker):
    flags.set_flag("feature_x", enabled=True)
    mocker.patch("django_matt.flags.backends.get_backend", return_value=flags)

    result = my_function()
    assert result == "new_behavior"

def test_with_flag_disabled(flags, mocker):
    flags.set_flag("feature_x", enabled=False)
    mocker.patch("django_matt.flags.backends.get_backend", return_value=flags)

    result = my_function()
    assert result == "old_behavior"
```

### Integration Tests

```python
from django.test import TestCase
from django_matt.flags.models import FeatureFlag, FlagType, FlagStatus

class FeatureFlagIntegrationTest(TestCase):
    def setUp(self):
        self.flag = FeatureFlag.objects.create(
            key="test_feature",
            name="Test Feature",
            flag_type=FlagType.BOOLEAN.value,
            status=FlagStatus.ACTIVE.value,
            enabled_by_default=True,
        )

    def test_feature_enabled_in_view(self):
        response = self.client.get("/api/feature/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("new_behavior", response.json())

    def test_feature_disabled_in_view(self):
        self.flag.enabled_by_default = False
        self.flag.save()

        response = self.client.get("/api/feature/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("old_behavior", response.json())
```

### Test All Variants

```python
@pytest.mark.parametrize("variant,expected", [
    ("control", "control_result"),
    ("treatment_a", "treatment_a_result"),
    ("treatment_b", "treatment_b_result"),
])
def test_all_variants(flags, mocker, variant, expected):
    flags.set_flag("experiment", flag_type="variant", variants=["control", "treatment_a", "treatment_b"])
    flags.set_override("experiment", user_id="123", variant=variant)
    mocker.patch("django_matt.flags.backends.get_backend", return_value=flags)

    result = experiment_function(user_id="123")
    assert result == expected
```

---

## Performance Tips

### Cache Flag Evaluations

```python
# Use request-level caching
def get_flags_for_request(request):
    if not hasattr(request, "_flags_cache"):
        request._flags_cache = {}
    return request._flags_cache

def cached_feature_check(request, flag_key):
    cache = get_flags_for_request(request)
    if flag_key not in cache:
        cache[flag_key] = feature_enabled(flag_key, user=request.user)
    return cache[flag_key]
```

### Bulk Evaluation

```python
# Instead of multiple individual checks
if feature_enabled("feature_a", user=user):
    ...
if feature_enabled("feature_b", user=user):
    ...
if feature_enabled("feature_c", user=user):
    ...

# Use bulk evaluation
flags = get_all_flags(user=user)
if flags.get("feature_a"):
    ...
if flags.get("feature_b"):
    ...
```

### Use Redis for High Traffic

```python
# settings.py
FEATURE_FLAG_BACKEND = "redis"
FEATURE_FLAG_BACKEND_SETTINGS = {
    "redis": {
        "redis_url": os.environ["REDIS_URL"],
        "cache_timeout": 60,  # Short TTL for freshness
    },
}
```

---

## Security Considerations

### Protect Management Endpoints

```python
from django_matt.permissions import IsAdmin

class SecureFlagController(FlagController):
    permission_classes = [IsAdmin]
```

### Disable Debug Overrides in Production

```python
# settings.py
FEATURE_FLAG_MIDDLEWARE = {
    "header_overrides": DEBUG,  # Only in development
    "cookie_overrides": False,
    "query_overrides": False,
}
```

### Audit Sensitive Changes

```python
# All changes are automatically logged
# Review logs regularly
from django_matt.flags.models import FlagAuditLog

# Recent changes to critical flags
critical_changes = FlagAuditLog.objects.filter(
    flag_key__startswith="billing_",
    created_at__gte=timezone.now() - timedelta(days=7),
)
```

---

## Common Patterns

### Kill Switch

```python
# Create enabled-by-default flag
FeatureFlag.objects.create(
    key="external_api_enabled",
    name="External API Calls",
    enabled_by_default=True,
    status=FlagStatus.ACTIVE.value,
)

# In code
if feature_enabled("external_api_enabled"):
    return await external_api.call()
else:
    logger.warning("External API disabled, using fallback")
    return get_fallback_data()

# To disable: flip enabled_by_default to False
```

### Beta Access

```python
# Create flag with overrides for beta users
flag = FeatureFlag.objects.create(
    key="beta_feature",
    name="Beta Feature",
    enabled_by_default=False,  # Off for everyone
)

# Add beta users
for user in beta_users:
    flag.add_override(
        override_type=OverrideType.USER,
        target_id=str(user.pk),
        enabled=True,
    )
```

### Staged Rollout

```python
# Day 1: Internal only
flag = FeatureFlag.objects.create(
    key="new_feature",
    flag_type=FlagType.BOOLEAN.value,
    enabled_by_default=False,
    targeting_rules=[
        {"attribute": "email", "operator": "ends_with", "value": "@company.com"}
    ],
)

# Day 3: Add percentage rollout
flag.flag_type = FlagType.PERCENTAGE.value
flag.rollout_percentage = 10
flag.targeting_rules = []  # Remove internal-only rule
flag.save()

# Day 7: Increase rollout
flag.rollout_percentage = 50
flag.save()

# Day 14: Full rollout
flag.flag_type = FlagType.BOOLEAN.value
flag.enabled_by_default = True
flag.save()
```

---

## Cleanup Checklist

When removing a flag:

- [ ] Flag has been at 100% for sufficient time
- [ ] No errors or regressions observed
- [ ] Remove flag checks from code
- [ ] Deploy code changes
- [ ] Archive the flag in admin
- [ ] Update documentation
- [ ] (Optional) Delete flag after retention period

```python
# Cleanup script
from django.utils import timezone
from datetime import timedelta
from django_matt.flags.models import FeatureFlag, FlagStatus

# Find flags ready for cleanup
old_threshold = timezone.now() - timedelta(days=90)

archived_flags = FeatureFlag.objects.filter(
    status=FlagStatus.ARCHIVED.value,
    updated_at__lt=old_threshold,
)

for flag in archived_flags:
    print(f"Ready for deletion: {flag.key}")
    # flag.delete()  # Uncomment to actually delete
```

## See Also

- [Types](types.md) - Choosing the right flag type
- [Targeting](targeting.md) - Targeting strategies
- [Admin](admin.md) - Managing flags
