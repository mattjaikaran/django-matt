# Feature Flag Decorators

django-matt provides decorators for easy feature flag integration in views.

## @feature_flag

Gate a view based on a feature flag with optional fallback.

### Basic Usage

```python
from django_matt.flags import feature_flag

@feature_flag("new_checkout")
async def new_checkout_view(request):
    return render(request, "checkout/new.html")
```

If the flag is disabled, returns a 404 response:

```json
{"detail": "Feature not available", "code": "feature_disabled"}
```

### With Fallback Function

```python
async def legacy_checkout(request):
    return render(request, "checkout/legacy.html")

@feature_flag("new_checkout", fallback=legacy_checkout)
async def new_checkout(request):
    return render(request, "checkout/new.html")
```

When disabled, the fallback function is called instead of returning 404.

### With Fallback Response

```python
@feature_flag(
    "premium_feature",
    fallback_response={"error": "Upgrade to premium", "code": "premium_required"}
)
async def premium_view(request):
    return render(request, "premium/dashboard.html")
```

### With Default Value

```python
# If flag doesn't exist, treat as enabled
@feature_flag("maybe_exists", default=True)
async def maybe_view(request):
    return render(request, "view.html")

# If flag doesn't exist, treat as disabled
@feature_flag("maybe_exists", default=False)
async def maybe_view(request):
    return render(request, "view.html")
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `flag_key` | str | required | Feature flag key to check |
| `default` | bool | `False` | Default if flag doesn't exist |
| `fallback` | Callable | `None` | Function to call if disabled |
| `fallback_response` | Response/dict | `None` | Response to return if disabled |

### Sync and Async Support

The decorator works with both sync and async views:

```python
# Async view
@feature_flag("new_feature")
async def async_view(request):
    return await render_async(request, "template.html")

# Sync view
@feature_flag("new_feature")
def sync_view(request):
    return render(request, "template.html")
```

---

## @requires_flag

Require a flag to be enabled, returning an error if not.

### Basic Usage

```python
from django_matt.flags import requires_flag

@requires_flag("beta_feature")
async def beta_only_view(request):
    return render(request, "beta/feature.html")
```

Returns a 404 if the flag is disabled:

```json
{"detail": "Feature not available", "code": "feature_disabled"}
```

### Custom Error Response

```python
@requires_flag(
    "admin_tools",
    status_code=403,
    error_message="Admin access required",
    error_code="admin_required"
)
async def admin_tools(request):
    return render(request, "admin/tools.html")
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `flag_key` | str | required | Feature flag key to require |
| `status_code` | int | `404` | HTTP status for error response |
| `error_message` | str | `"Feature not available"` | Error message |
| `error_code` | str | `"feature_disabled"` | Error code |

---

## @variant_flag

Route to different handlers based on variant assignment.

### Basic Usage

```python
from django_matt.flags import variant_flag

def checkout_control(request):
    return render(request, "checkout/v1.html")

def checkout_streamlined(request):
    return render(request, "checkout/v2.html")

def checkout_express(request):
    return render(request, "checkout/v3.html")

@variant_flag(
    "checkout_experiment",
    variant_handlers={
        "control": checkout_control,
        "streamlined": checkout_streamlined,
        "express": checkout_express,
    },
    default_variant="control",
)
async def checkout(request):
    # Fallback if no variant matches
    return render(request, "checkout/default.html")
```

### How It Works

1. Gets the user's variant assignment for the flag
2. If variant matches a handler, calls that handler
3. If no match, calls the decorated function as fallback

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `flag_key` | str | required | Variant flag key |
| `variant_handlers` | dict | `None` | Map of variant key to handler function |
| `default_variant` | str | `None` | Default variant if none assigned |

### Mixed Sync/Async Handlers

```python
def sync_handler(request):
    return render(request, "sync.html")

async def async_handler(request):
    data = await fetch_data()
    return render(request, "async.html", {"data": data})

@variant_flag(
    "experiment",
    variant_handlers={
        "control": sync_handler,
        "treatment": async_handler,
    },
)
async def view(request):
    return render(request, "default.html")
```

---

## @with_flag_context

Ensure FlagContext is available in the view.

```python
from django_matt.flags import with_flag_context, feature_enabled

@with_flag_context
async def my_view(request):
    # FlagContext is set for this request
    if feature_enabled("feature_a"):
        ...
    if feature_enabled("feature_b"):
        ...
    return render(request, "template.html")
```

This decorator:

1. Creates a `FlagContext` from the request
2. Sets it as the current context
3. Restores the previous context when done

### When to Use

Use `@with_flag_context` when you need to check multiple flags in helper functions:

```python
from django_matt.flags import feature_enabled

def get_dashboard_config():
    # These checks use the current FlagContext
    return {
        "show_analytics": feature_enabled("dashboard_analytics"),
        "show_reports": feature_enabled("dashboard_reports"),
        "show_widgets": feature_enabled("dashboard_widgets"),
    }

@with_flag_context
async def dashboard(request):
    config = get_dashboard_config()
    return render(request, "dashboard.html", {"config": config})
```

---

## FlagEnabledMixin

A mixin for class-based controllers that adds feature flag checking.

### Basic Usage

```python
from django_matt.flags import FlagEnabledMixin
from django_matt.core import APIController

class BetaFeatureController(FlagEnabledMixin, APIController):
    # Required flags - view returns 404 if any are disabled
    required_flags = ["beta_feature", "new_api"]

    # Optional flags with defaults
    optional_flags = {
        "enhanced_responses": False,
        "caching": True,
    }

    async def get(self, request):
        # Check if required flags pass
        error = self.check_flags()
        if error:
            return error

        # Check optional flags
        if self.is_flag_enabled("enhanced_responses"):
            return self.enhanced_response()

        return self.standard_response()
```

### Properties and Methods

| Member | Type | Description |
|--------|------|-------------|
| `required_flags` | list[str] | Flags that must be enabled |
| `optional_flags` | dict[str, bool] | Optional flags with defaults |
| `flag_error_status` | int | Error status code (default: 404) |
| `flag_error_message` | str | Error message |
| `flag_context` | FlagContext | Current flag context |
| `check_flags()` | method | Check required flags, return error or None |
| `is_flag_enabled(key)` | method | Check if a flag is enabled |
| `get_variant(key)` | method | Get variant assignment |

### With Variants

```python
class ExperimentController(FlagEnabledMixin, APIController):
    required_flags = []

    async def get(self, request):
        variant = self.get_variant("experiment")

        if variant == "treatment_a":
            return self.treatment_a_response()
        elif variant == "treatment_b":
            return self.treatment_b_response()

        return self.control_response()
```

### Custom Error Handling

```python
class PremiumController(FlagEnabledMixin, APIController):
    required_flags = ["premium_features"]
    flag_error_status = 403
    flag_error_message = "Premium subscription required"

    async def get(self, request):
        error = self.check_flags()
        if error:
            return error
        ...
```

---

## Combining Decorators

Decorators work with other django-matt decorators:

```python
from django_matt.auth import jwt_required
from django_matt.flags import requires_flag
from django_matt.permissions import requires_permission

@jwt_required
@requires_flag("new_api")
@requires_permission("api.access")
async def protected_feature(request):
    return JsonResponse({"data": "secret"})
```

Order matters - decorators are applied bottom-up:

1. `requires_permission` checks permission
2. `requires_flag` checks flag
3. `jwt_required` checks authentication

---

## Real-World Examples

### Gradual UI Rollout

```python
def legacy_dashboard(request):
    return render(request, "dashboard/legacy.html")

@feature_flag("new_dashboard", fallback=legacy_dashboard)
async def dashboard(request):
    return render(request, "dashboard/new.html")
```

### A/B Test with Analytics

```python
def track_variant(request, variant, experiment):
    analytics.track(
        user_id=request.user.id,
        event="experiment_viewed",
        properties={
            "experiment": experiment,
            "variant": variant,
        }
    )

@variant_flag(
    "onboarding_experiment",
    variant_handlers={
        "control": lambda r: render(r, "onboarding/control.html"),
        "simplified": lambda r: render(r, "onboarding/simplified.html"),
        "gamified": lambda r: render(r, "onboarding/gamified.html"),
    },
)
async def onboarding(request):
    ctx = FlagContext.from_request(request)
    variant = ctx.get_variant("onboarding_experiment")
    track_variant(request, variant, "onboarding_experiment")
    return render(request, "onboarding/default.html")
```

### Kill Switch with Graceful Degradation

```python
async def get_recommendations_fallback(request):
    # Return cached/static recommendations
    return JsonResponse({"recommendations": get_cached_recommendations()})

@feature_flag(
    "ml_recommendations",
    fallback=get_recommendations_fallback,
    default=True  # On by default
)
async def get_recommendations(request):
    # Call ML service
    recommendations = await ml_service.get_recommendations(request.user)
    return JsonResponse({"recommendations": recommendations})
```

## See Also

- [Types](types.md) - Understanding flag types
- [Targeting](targeting.md) - Targeting specific users
- [API](api.md) - Managing flags via REST API
