# Feature Flag Models

django-matt provides three core models for feature flag management.

## FeatureFlag

The main model for storing feature flag configuration.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `key` | CharField | Unique identifier (e.g., `new_checkout`) |
| `name` | CharField | Human-readable name |
| `description` | TextField | Optional description |
| `flag_type` | CharField | Type: `boolean`, `percentage`, `variant` |
| `status` | CharField | Status: `active`, `inactive`, `archived` |
| `enabled_by_default` | BooleanField | Default state when no rules match |
| `rollout_percentage` | IntegerField | Percentage for rollout (0-100) |
| `variants` | JSONField | Variant configuration for A/B tests |
| `targeting_rules` | JSONField | Targeting rules for conditional logic |
| `scheduled_enable_at` | DateTimeField | Auto-enable time |
| `scheduled_disable_at` | DateTimeField | Auto-disable time |
| `metadata` | JSONField | Additional metadata |
| `created_at` | DateTimeField | Creation timestamp |
| `updated_at` | DateTimeField | Last update timestamp |
| `created_by` | ForeignKey | User who created the flag |

### Enums

```python
from django_matt.flags.models import FlagType, FlagStatus

class FlagType(str, Enum):
    BOOLEAN = "boolean"      # Simple on/off
    PERCENTAGE = "percentage" # Gradual rollout
    VARIANT = "variant"      # A/B testing

class FlagStatus(str, Enum):
    ACTIVE = "active"        # Flag is evaluating
    INACTIVE = "inactive"    # Flag returns default
    ARCHIVED = "archived"    # Flag is retired
```

### Creating Flags

```python
from django_matt.flags.models import FeatureFlag, FlagType, FlagStatus

# Boolean flag
flag = FeatureFlag.objects.create(
    key="new_feature",
    name="New Feature",
    description="Enables the new feature experience",
    flag_type=FlagType.BOOLEAN.value,
    status=FlagStatus.ACTIVE.value,
    enabled_by_default=False,
)

# Percentage rollout flag
flag = FeatureFlag.objects.create(
    key="gradual_rollout",
    name="Gradual Rollout",
    flag_type=FlagType.PERCENTAGE.value,
    status=FlagStatus.ACTIVE.value,
    rollout_percentage=25,  # 25% of users
)

# Variant flag for A/B testing
flag = FeatureFlag.objects.create(
    key="checkout_experiment",
    name="Checkout Experiment",
    flag_type=FlagType.VARIANT.value,
    status=FlagStatus.ACTIVE.value,
    variants={
        "variants": [
            {"key": "control", "name": "Control", "weight": 50},
            {"key": "treatment", "name": "Treatment", "weight": 50},
        ],
        "default_variant": "control",
    },
)
```

### Checking Flags

```python
# Check if flag is active (respects scheduling)
if flag.is_active:
    print("Flag is currently active")

# Check for specific user
enabled = flag.is_enabled_for_user(
    user=user,
    organization=org,
    attributes={"plan": "premium"},
)

# Get variant assignment
variant = flag.get_variant(user=user)
```

### Manager Methods

```python
from django_matt.flags.models import FeatureFlag

# Get active flags only
active_flags = FeatureFlag.objects.active()

# Get flag by key
flag = FeatureFlag.objects.by_key("new_feature")

# Get flags enabled for a user
user_flags = FeatureFlag.objects.enabled_for_user(user)
```

### Scheduled Activation

```python
from django.utils import timezone
from datetime import timedelta

# Enable in 1 hour
flag = FeatureFlag.objects.create(
    key="holiday_theme",
    name="Holiday Theme",
    status=FlagStatus.ACTIVE.value,
    scheduled_enable_at=timezone.now() + timedelta(hours=1),
    scheduled_disable_at=timezone.now() + timedelta(days=7),
)

# Flag won't be active until scheduled_enable_at
# Flag will automatically deactivate after scheduled_disable_at
```

---

## FlagOverride

Overrides allow enabling/disabling flags for specific targets.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `flag` | ForeignKey | Reference to FeatureFlag |
| `override_type` | CharField | Type: `user`, `organization`, `email`, `attribute` |
| `target_id` | CharField | Target ID (user ID, org ID) |
| `target_value` | CharField | Target value (email address) |
| `enabled` | BooleanField | Override state |
| `variant` | CharField | Override variant (for variant flags) |
| `expires_at` | DateTimeField | Optional expiry time |
| `created_at` | DateTimeField | Creation timestamp |
| `created_by` | ForeignKey | User who created override |

### Override Types

```python
from django_matt.flags.models import OverrideType

class OverrideType(str, Enum):
    USER = "user"              # Override by user ID
    ORGANIZATION = "organization"  # Override by org ID
    EMAIL = "email"            # Override by email address
    ATTRIBUTE = "attribute"    # Override by attribute value
```

### Creating Overrides

```python
from django_matt.flags.models import FlagOverride, OverrideType

# Enable for specific user
FlagOverride.objects.create(
    flag=flag,
    override_type=OverrideType.USER.value,
    target_id=str(user.pk),
    enabled=True,
)

# Enable for organization
FlagOverride.objects.create(
    flag=flag,
    override_type=OverrideType.ORGANIZATION.value,
    target_id=str(org.pk),
    enabled=True,
)

# Enable for email address (beta testers)
FlagOverride.objects.create(
    flag=flag,
    override_type=OverrideType.EMAIL.value,
    target_value="beta@example.com",
    enabled=True,
)

# Force specific variant
FlagOverride.objects.create(
    flag=flag,
    override_type=OverrideType.USER.value,
    target_id=str(user.pk),
    enabled=True,
    variant="treatment_a",
)
```

### Using the Helper Method

```python
# Add override via flag model
flag.add_override(
    override_type=OverrideType.USER,
    target_id=str(user.pk),
    enabled=True,
    expires_at=timezone.now() + timedelta(days=30),
)
```

### Temporary Overrides

```python
from datetime import timedelta
from django.utils import timezone

# Beta access for 30 days
FlagOverride.objects.create(
    flag=flag,
    override_type=OverrideType.EMAIL.value,
    target_value="tester@example.com",
    enabled=True,
    expires_at=timezone.now() + timedelta(days=30),
)

# Check if expired
override = FlagOverride.objects.get(...)
if override.is_expired:
    print("Override has expired")

if override.is_active:
    print("Override is still active")
```

---

## FlagAuditLog

Tracks all changes to flags and overrides for compliance and debugging.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `flag` | ForeignKey | Reference to FeatureFlag (nullable) |
| `flag_key` | CharField | Flag key (preserved if flag deleted) |
| `action` | CharField | Action: `create`, `update`, `delete`, `enable`, etc. |
| `changes` | JSONField | Detailed changes |
| `old_values` | JSONField | Previous values |
| `new_values` | JSONField | New values |
| `user` | ForeignKey | User who made change |
| `ip_address` | GenericIPAddressField | Request IP |
| `user_agent` | TextField | Browser user agent |
| `created_at` | DateTimeField | Timestamp |

### Actions Logged

- `create` - Flag created
- `update` - Flag updated
- `delete` - Flag deleted
- `enable` - Flag enabled
- `disable` - Flag disabled
- `archive` - Flag archived
- `add_override` - Override added
- `remove_override` - Override removed

### Creating Audit Logs

Audit logs are automatically created by the API and admin. For manual logging:

```python
from django_matt.flags.models import FlagAuditLog

FlagAuditLog.log(
    flag=flag,
    action="custom_action",
    old_values={"status": "inactive"},
    new_values={"status": "active"},
    user=request.user,
    ip_address=request.META.get("REMOTE_ADDR"),
    user_agent=request.META.get("HTTP_USER_AGENT", ""),
)
```

### Querying Audit Logs

```python
# Get logs for a specific flag
logs = FlagAuditLog.objects.filter(flag_key="new_feature")

# Get recent changes
from django.utils import timezone
from datetime import timedelta

yesterday = timezone.now() - timedelta(days=1)
recent = FlagAuditLog.objects.filter(created_at__gte=yesterday)

# Get changes by user
user_changes = FlagAuditLog.objects.filter(user=user)

# Get specific action
enables = FlagAuditLog.objects.filter(action="enable")
```

---

## Database Indexes

The models include indexes for common queries:

```python
class FeatureFlag:
    class Meta:
        indexes = [
            models.Index(fields=["key"]),
            models.Index(fields=["status"]),
            models.Index(fields=["flag_type"]),
            models.Index(fields=["scheduled_enable_at"]),
            models.Index(fields=["scheduled_disable_at"]),
        ]

class FlagOverride:
    class Meta:
        indexes = [
            models.Index(fields=["flag", "override_type"]),
            models.Index(fields=["override_type", "target_id"]),
            models.Index(fields=["override_type", "target_value"]),
            models.Index(fields=["expires_at"]),
        ]
        unique_together = [["flag", "override_type", "target_id", "target_value"]]
```

## See Also

- [Flag Types](types.md) - Understanding different flag types
- [Targeting](targeting.md) - Targeting rules and overrides
- [Admin](admin.md) - Managing flags in Django admin
