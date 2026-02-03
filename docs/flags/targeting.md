# Flag Targeting

Target specific users, organizations, or segments with feature flags.

## Targeting Overview

django-matt supports multiple targeting strategies:

1. **User Targeting** - Enable/disable for specific users
2. **Organization Targeting** - Target entire organizations
3. **Email Targeting** - Target by email address
4. **Attribute Rules** - Complex targeting logic

## User Targeting

Enable or disable flags for specific users.

### Via Python

```python
from django_matt.flags.models import FeatureFlag, FlagOverride, OverrideType

flag = FeatureFlag.objects.get(key="beta_feature")

# Enable for specific user
FlagOverride.objects.create(
    flag=flag,
    override_type=OverrideType.USER.value,
    target_id=str(user.pk),
    enabled=True,
)

# Disable for specific user (even if flag is on by default)
FlagOverride.objects.create(
    flag=flag,
    override_type=OverrideType.USER.value,
    target_id=str(problem_user.pk),
    enabled=False,
)
```

### Using Helper Method

```python
# Add override via flag model
flag.add_override(
    override_type=OverrideType.USER,
    target_id=str(user.pk),
    enabled=True,
)
```

### Via REST API

```bash
# Enable for user
curl -X POST http://localhost:8000/api/flags/beta_feature/overrides \
  -H "Content-Type: application/json" \
  -d '{
    "override_type": "user",
    "target_id": "123e4567-e89b-12d3-a456-426614174000",
    "enabled": true
  }'
```

---

## Organization Targeting

Enable flags for entire organizations (B2B scenarios).

### Creating Organization Overrides

```python
# Enable for entire organization
FlagOverride.objects.create(
    flag=flag,
    override_type=OverrideType.ORGANIZATION.value,
    target_id=str(organization.pk),
    enabled=True,
)
```

### Checking with Organization Context

```python
from django_matt.flags import feature_enabled

# Pass organization explicitly
enabled = feature_enabled(
    "enterprise_feature",
    user=request.user,
    organization=request.user.organization,
)

# Or use FlagContext (auto-detects from request)
from django_matt.flags import FlagContext

ctx = FlagContext.from_request(request)  # Extracts org from request
if ctx.is_enabled("enterprise_feature"):
    ...
```

### Multi-Tenant Example

```python
# Enable premium features for paying orgs
def enable_premium_for_org(organization):
    for feature in ["advanced_analytics", "custom_branding", "api_access"]:
        flag = FeatureFlag.objects.get(key=feature)
        flag.add_override(
            override_type=OverrideType.ORGANIZATION,
            target_id=str(organization.pk),
            enabled=True,
        )
```

---

## Email Targeting

Target users by email address. Useful for:

- Beta tester access before user accounts exist
- External stakeholder access
- Domain-based targeting

### Creating Email Overrides

```python
# Enable for specific email
FlagOverride.objects.create(
    flag=flag,
    override_type=OverrideType.EMAIL.value,
    target_value="beta@example.com",
    enabled=True,
)

# Enable for all emails in a domain (via targeting rules - see below)
```

### Beta Tester Pattern

```python
# Add beta testers by email
beta_emails = [
    "alice@example.com",
    "bob@example.com",
    "charlie@example.com",
]

flag = FeatureFlag.objects.get(key="new_feature")
for email in beta_emails:
    flag.add_override(
        override_type=OverrideType.EMAIL,
        target_value=email,
        enabled=True,
    )
```

---

## Attribute-Based Targeting

Target users based on custom attributes using targeting rules.

### Targeting Rule Structure

```python
{
    "attribute": "plan",        # Attribute to check
    "operator": "eq",           # Comparison operator
    "value": "premium"          # Value to compare against
}
```

### Available Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equals | `{"attribute": "plan", "operator": "eq", "value": "premium"}` |
| `neq` | Not equals | `{"attribute": "status", "operator": "neq", "value": "banned"}` |
| `gt` | Greater than | `{"attribute": "age", "operator": "gt", "value": 18}` |
| `gte` | Greater than or equal | `{"attribute": "credits", "operator": "gte", "value": 100}` |
| `lt` | Less than | `{"attribute": "risk_score", "operator": "lt", "value": 50}` |
| `lte` | Less than or equal | `{"attribute": "days_active", "operator": "lte", "value": 30}` |
| `in` | In list | `{"attribute": "country", "operator": "in", "value": ["US", "CA"]}` |
| `not_in` | Not in list | `{"attribute": "role", "operator": "not_in", "value": ["guest"]}` |
| `contains` | Contains substring | `{"attribute": "email", "operator": "contains", "value": "@company.com"}` |
| `starts_with` | Starts with | `{"attribute": "email", "operator": "starts_with", "value": "admin"}` |
| `ends_with` | Ends with | `{"attribute": "domain", "operator": "ends_with", "value": ".edu"}` |
| `regex` | Regex match | `{"attribute": "email", "operator": "regex", "value": ".*@(example\|test)\\.com$"}` |

### Creating Targeting Rules

```python
flag = FeatureFlag.objects.create(
    key="premium_feature",
    name="Premium Feature",
    flag_type=FlagType.BOOLEAN.value,
    status=FlagStatus.ACTIVE.value,
    enabled_by_default=False,  # Off by default
    targeting_rules=[
        # Enable for premium plan users
        {"attribute": "plan", "operator": "eq", "value": "premium"},
        # OR enable for enterprise plan
        {"attribute": "plan", "operator": "eq", "value": "enterprise"},
    ],
)
```

### Passing Custom Attributes

```python
from django_matt.flags import feature_enabled

# Pass custom attributes
enabled = feature_enabled(
    "premium_feature",
    user=request.user,
    attributes={
        "plan": user.subscription.plan,
        "country": user.profile.country,
        "days_active": (timezone.now() - user.date_joined).days,
    }
)
```

### Using FlagContext with Attributes

```python
from django_matt.flags import FlagContext

# Create context with custom attributes
ctx = FlagContext(
    user=request.user,
    organization=request.organization,
    attributes={
        "plan": "premium",
        "beta_tester": True,
        "internal": user.email.endswith("@mycompany.com"),
    }
)

if ctx.is_enabled("advanced_feature"):
    ...
```

### Complex Targeting Examples

```python
# Enable for internal users only
targeting_rules = [
    {"attribute": "email", "operator": "ends_with", "value": "@mycompany.com"}
]

# Enable for US/CA users on premium plans
targeting_rules = [
    {"attribute": "country", "operator": "in", "value": ["US", "CA"]},
    {"attribute": "plan", "operator": "eq", "value": "premium"},
]
# Note: Multiple rules use OR logic. For AND, combine in application code.

# Enable for new users (signed up in last 30 days)
targeting_rules = [
    {"attribute": "days_since_signup", "operator": "lte", "value": 30}
]

# Enable for mobile users
targeting_rules = [
    {"attribute": "is_mobile", "operator": "eq", "value": True}
]
```

### FlagContext Auto-Detected Attributes

`FlagContext.from_request()` automatically detects these attributes:

| Attribute | Source | Example Value |
|-----------|--------|---------------|
| `email` | `user.email` | `"user@example.com"` |
| `is_staff` | `user.is_staff` | `True` |
| `is_superuser` | `user.is_superuser` | `False` |
| `days_since_signup` | `user.date_joined` | `45` |
| `path` | `request.path` | `"/api/users/"` |
| `method` | `request.method` | `"GET"` |
| `user_agent` | `request.META` | `"Mozilla/5.0..."` |
| `is_mobile` | User agent detection | `True` |

---

## Temporary Overrides

Create overrides that automatically expire.

```python
from datetime import timedelta
from django.utils import timezone

# Grant beta access for 30 days
FlagOverride.objects.create(
    flag=flag,
    override_type=OverrideType.USER.value,
    target_id=str(user.pk),
    enabled=True,
    expires_at=timezone.now() + timedelta(days=30),
)

# Check if override is still active
override = FlagOverride.objects.get(...)
if override.is_active:
    print("Override is still valid")
if override.is_expired:
    print("Override has expired")
```

---

## Override Priority

When multiple targeting rules apply, this is the evaluation order:

1. **User override** (highest priority)
2. **Email override**
3. **Organization override**
4. **Targeting rules** (attributes)
5. **Percentage rollout** (if applicable)
6. **Default value** (lowest priority)

```python
# Example: User override takes precedence
flag.enabled_by_default = False  # Default off

# Org has access
flag.add_override(
    override_type=OverrideType.ORGANIZATION,
    target_id=str(org.pk),
    enabled=True,
)

# But this user is disabled
flag.add_override(
    override_type=OverrideType.USER,
    target_id=str(user.pk),
    enabled=False,  # User override wins
)

# Result: User does NOT have access even though org does
```

---

## Debug Mode Overrides

Enable temporary overrides for testing via HTTP headers, cookies, or query params.

### Configuration

```python
# settings.py
FEATURE_FLAG_MIDDLEWARE = {
    "header_overrides": True,    # X-Feature-Flag-* headers
    "cookie_overrides": True,    # ff_* cookies
    "query_overrides": True,     # ?ff_* query params
}
```

### Using Header Overrides

```bash
# Enable a flag for this request only
curl -H "X-Feature-Flag-New-Dashboard: true" http://localhost:8000/

# Disable a flag
curl -H "X-Feature-Flag-New-Dashboard: false" http://localhost:8000/
```

### Using Query Param Overrides

```
http://localhost:8000/?ff_new_dashboard=true
http://localhost:8000/?ff_beta_feature=1
```

!!! warning "Security Note"
    Debug overrides are only active when `debug_mode` is True (defaults to `settings.DEBUG`). Never enable in production!

## See Also

- [Models](models.md) - FlagOverride model reference
- [API](api.md) - REST API for managing overrides
- [Best Practices](best-practices.md) - Targeting best practices
