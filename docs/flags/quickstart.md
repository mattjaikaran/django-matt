# Feature Flags Quickstart

Get started with feature flags in 5 minutes.

## Step 1: Add Middleware

Add the feature flag middleware to your Django settings:

```python
# settings.py
MIDDLEWARE = [
    ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_matt.flags.FlagMiddleware',  # Must be after auth
    ...
]
```

## Step 2: Run Migrations

The feature flag models are included in django-matt:

```bash
python manage.py migrate
```

## Step 3: Create Your First Flag

### Via Admin Panel

1. Navigate to `/admin/django_matt/featureflag/`
2. Click "Add Feature Flag"
3. Fill in:
   - **Key**: `new_dashboard` (unique identifier)
   - **Name**: "New Dashboard"
   - **Type**: Boolean
   - **Status**: Active
   - **Enabled by Default**: True
4. Save

### Via Python Shell

```python
from django_matt.flags.models import FeatureFlag, FlagType, FlagStatus

flag = FeatureFlag.objects.create(
    key="new_dashboard",
    name="New Dashboard",
    flag_type=FlagType.BOOLEAN.value,
    status=FlagStatus.ACTIVE.value,
    enabled_by_default=True,
)
```

### Via REST API

```bash
curl -X POST http://localhost:8000/api/flags \
  -H "Content-Type: application/json" \
  -d '{
    "key": "new_dashboard",
    "name": "New Dashboard",
    "flag_type": "boolean",
    "status": "active",
    "enabled_by_default": true
  }'
```

## Step 4: Check the Flag in Code

### Using the Helper Function

```python
from django_matt.flags import feature_enabled

def dashboard_view(request):
    if feature_enabled("new_dashboard", user=request.user):
        return render(request, "dashboard/new.html")
    return render(request, "dashboard/legacy.html")
```

### Using the Decorator

```python
from django_matt.flags import feature_flag

@feature_flag("new_dashboard", fallback=legacy_dashboard)
async def new_dashboard(request):
    return render(request, "dashboard/new.html")
```

### Using FlagContext

```python
from django_matt.flags import FlagContext

def my_view(request):
    ctx = FlagContext.from_request(request)

    if ctx.is_enabled("new_dashboard"):
        # New feature code
        pass
```

## Step 5: Test with Overrides

### Enable for Specific User

```python
from django_matt.flags.models import FeatureFlag, OverrideType

flag = FeatureFlag.objects.get(key="new_dashboard")
flag.add_override(
    override_type=OverrideType.USER,
    target_id=str(user.pk),
    enabled=True,
)
```

### Override via Header (Debug Mode)

```bash
# Enable in settings
FEATURE_FLAG_MIDDLEWARE = {
    "header_overrides": True,
}

# Then use header in requests
curl -H "X-Feature-Flag-New-Dashboard: true" http://localhost:8000/dashboard
```

## Complete Example

Here's a full example implementing a gradual rollout:

```python
# views.py
from django_matt.flags import feature_enabled, get_variant

class CheckoutView(APIController):
    async def post(self, request):
        # Check if new checkout is enabled
        if feature_enabled("new_checkout", user=request.user):
            # Get which variant to show
            variant = get_variant("checkout_experiment", user=request.user)

            if variant == "streamlined":
                return await self.streamlined_checkout(request)
            elif variant == "express":
                return await self.express_checkout(request)

        # Default checkout
        return await self.standard_checkout(request)
```

```python
# Create flags in management command or admin
from django_matt.flags.models import FeatureFlag, FlagType, FlagStatus

# Boolean flag for feature gate
FeatureFlag.objects.create(
    key="new_checkout",
    name="New Checkout Flow",
    flag_type=FlagType.BOOLEAN.value,
    status=FlagStatus.ACTIVE.value,
    enabled_by_default=True,
)

# Variant flag for A/B test
FeatureFlag.objects.create(
    key="checkout_experiment",
    name="Checkout A/B Test",
    flag_type=FlagType.VARIANT.value,
    status=FlagStatus.ACTIVE.value,
    variants={
        "variants": [
            {"key": "streamlined", "name": "Streamlined", "weight": 50},
            {"key": "express", "name": "Express", "weight": 50},
        ]
    },
)
```

## Next Steps

- [Learn about flag types](types.md) - Boolean, percentage, and variants
- [Set up targeting rules](targeting.md) - Target specific users or segments
- [Configure backends](backends.md) - Use Redis or external services
- [Review best practices](best-practices.md) - Naming conventions and lifecycle
