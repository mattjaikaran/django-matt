# Feature Flags

Control feature rollouts, A/B testing, and kill switches with django-matt's built-in feature flag system.

## Overview

Feature flags (also called feature toggles) allow you to dynamically enable or disable features without deploying new code. django-matt provides a comprehensive feature flag system with:

- **Multiple flag types**: Boolean, percentage rollout, and A/B test variants
- **Flexible targeting**: User, organization, email, and attribute-based rules
- **Multiple backends**: Database, Redis, LaunchDarkly, and Unleash
- **Scheduled activation**: Time-based flag enable/disable
- **Audit logging**: Track all flag changes
- **Admin interface**: Full Django admin integration
- **REST API**: Complete API for flag management

## Quick Start

```python
from django_matt.flags import feature_enabled, get_variant

# Simple boolean check
if feature_enabled("new_checkout", user=request.user):
    return new_checkout_flow()
else:
    return legacy_checkout_flow()

# A/B test variants
variant = get_variant("checkout_experiment", user=request.user)
if variant == "control":
    return checkout_v1()
elif variant == "treatment_a":
    return checkout_v2()
```

## Installation

Add the middleware to your Django settings:

```python
# settings.py
MIDDLEWARE = [
    ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_matt.flags.FlagMiddleware',  # After auth middleware
    ...
]
```

## Use Cases

### Gradual Feature Rollout

Roll out new features to a percentage of users:

```python
# settings.py or admin panel
# Set rollout_percentage = 10 for "new_dashboard"

if feature_enabled("new_dashboard", user=request.user):
    return render_new_dashboard()
```

### A/B Testing

Test multiple variations of a feature:

```python
variant = get_variant("pricing_page", user=request.user)
template = f"pricing/{variant}.html"
return render(request, template)
```

### Beta Access

Enable features for specific users or organizations:

```python
# Via admin: Add override for beta users
if feature_enabled("ai_assistant", user=request.user):
    context["show_ai_assistant"] = True
```

### Kill Switches

Quickly disable problematic features:

```python
if feature_enabled("external_api_calls"):
    data = await fetch_from_external_api()
else:
    data = get_cached_fallback()
```

### Environment-Specific Features

Enable features only in specific environments:

```python
# Create flag with targeting rules
rules = [
    {"attribute": "environment", "operator": "eq", "value": "staging"}
]
```

## Configuration

```python
# settings.py

# Choose backend (default: database)
FEATURE_FLAG_BACKEND = "database"  # or "redis", "launchdarkly", "unleash"

# Backend-specific settings
FEATURE_FLAG_BACKEND_SETTINGS = {
    "database": {
        "cache_timeout": 60,
        "use_cache": True,
    },
    "redis": {
        "redis_url": "redis://localhost:6379/0",
        "cache_timeout": 300,
    },
}

# Middleware configuration
FEATURE_FLAG_MIDDLEWARE = {
    "header_overrides": True,    # Allow X-Feature-Flag-* headers
    "cookie_overrides": False,   # Allow ff_* cookies
    "query_overrides": False,    # Allow ?ff_* query params
    "expose_flags_header": True, # Add X-Feature-Flags response header
}
```

## Key Benefits

| Benefit | Description |
|---------|-------------|
| **Safer Deployments** | Deploy code with features off, then enable gradually |
| **Instant Rollback** | Disable broken features without redeploying |
| **Data-Driven Decisions** | A/B test to find what works best |
| **Targeted Releases** | Beta test with specific users or orgs |
| **Reduced Risk** | Limit blast radius of new feature issues |

## Architecture

```
Request Flow:
                                    +------------------+
    Request --> FlagMiddleware --> | FlagContext      |
                     |             | - user           |
                     v             | - organization   |
              FlagBackend         | - attributes     |
              (DB/Redis/LD)        +------------------+
                     |
                     v
              FeatureFlag Model
              - type (boolean/percentage/variant)
              - targeting_rules
              - overrides
```

## Documentation

- [Quickstart](quickstart.md) - Get started in 5 minutes
- [Models](models.md) - FeatureFlag, FlagOverride, FlagAuditLog
- [Flag Types](types.md) - Boolean, percentage rollout, A/B variants
- [Targeting](targeting.md) - User, org, and attribute targeting
- [Decorators](decorators.md) - @feature_flag, @requires_flag, @variant_flag
- [REST API](api.md) - Flag management endpoints
- [Backends](backends.md) - Database, Redis, LaunchDarkly, Unleash
- [Admin](admin.md) - Django admin integration
- [Best Practices](best-practices.md) - Lifecycle, cleanup, naming conventions
