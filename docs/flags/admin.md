# Feature Flags Admin

django-matt provides a full Django admin interface for managing feature flags.

## Setup

The admin is automatically registered when you import from `django_matt.flags.admin`:

```python
# admin.py
from django_matt.flags.admin import FeatureFlagAdmin, FlagOverrideAdmin, FlagAuditLogAdmin
```

Or register manually:

```python
from django_matt.flags.admin import register_flag_admin

# Register with default admin site
register_flag_admin()

# Or with custom admin site
register_flag_admin(site=my_custom_admin_site)
```

## Admin Classes

### FeatureFlagAdmin

Full-featured admin for managing feature flags.

![Feature Flag Admin List](../assets/placeholder-flag-list.png)

**List View Features:**

- **Columns**: Key, Name, Type (badge), Status (badge), Default, Rollout %, Overrides, Updated
- **Filters**: Status, Type, Enabled by Default, Created At
- **Search**: Key, Name, Description
- **Actions**: Enable, Disable, Archive selected flags

**Detail View Fieldsets:**

1. **Basic Info**: Key, Name, Description
2. **Configuration**: Type, Status, Default, Rollout %
3. **Variants & Targeting**: Variants JSON, Targeting Rules JSON
4. **Scheduling**: Enable At, Disable At
5. **Metadata**: Metadata JSON, ID, Timestamps, Created By

**Inline**: Overrides can be edited directly on the flag detail page.

### FlagOverrideAdmin

Admin for managing individual overrides.

**List View Features:**

- **Columns**: Flag, Type (badge), Target, Enabled (badge), Variant, Status, Created
- **Filters**: Type, Enabled, Flag Key
- **Search**: Flag Key, Target ID, Target Value

### FlagAuditLogAdmin

Read-only admin for viewing audit logs.

**List View Features:**

- **Columns**: Flag Key, Action (badge), User, IP Address, Created
- **Filters**: Action, Created At
- **Search**: Flag Key, User Email, IP Address
- **Date Hierarchy**: Created At

**Permissions:**

- Cannot add logs manually
- Cannot modify logs
- Only superusers can delete logs

---

## Admin Actions

### Enable Flags

Select flags and use "Enable selected flags" action:

```python
# What it does:
flag.status = FlagStatus.ACTIVE.value
flag.save()

# Creates audit log:
FlagAuditLog.log(flag=flag, action="enable", ...)
```

### Disable Flags

Select flags and use "Disable selected flags" action.

### Archive Flags

Select flags and use "Archive selected flags" action.

---

## Customization

### Custom Admin Class

```python
from django_matt.flags.admin import FeatureFlagAdmin

class MyFeatureFlagAdmin(FeatureFlagAdmin):
    # Add custom fields
    list_display = FeatureFlagAdmin.list_display + ["custom_field"]

    # Custom actions
    actions = FeatureFlagAdmin.actions + ["my_custom_action"]

    def custom_field(self, obj):
        return obj.metadata.get("custom_value", "-")
    custom_field.short_description = "Custom"

    def my_custom_action(self, request, queryset):
        for flag in queryset:
            # Custom logic
            pass
        self.message_user(request, "Action completed")
    my_custom_action.short_description = "My Custom Action"
```

### Filter by Environment

```python
class EnvironmentFilteredFlagAdmin(FeatureFlagAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Filter by environment metadata
        env = getattr(settings, "ENVIRONMENT", "production")
        return qs.filter(
            models.Q(metadata__environment=env) |
            models.Q(metadata__environment__isnull=True)
        )
```

### Restrict Access

```python
class RestrictedFlagAdmin(FeatureFlagAdmin):
    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        if obj and obj.key.startswith("critical_"):
            return request.user.is_superuser
        return super().has_change_permission(request, obj)
```

---

## Django Unfold Integration

If [Django Unfold](https://github.com/unfoldadmin/django-unfold) is installed, the admin automatically uses Unfold styling:

```python
# The admin classes extend UnfoldModelAdmin when available
try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    HAS_UNFOLD = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin
    HAS_UNFOLD = False
```

### Visual Features with Unfold

- Colored badges for status, type, and actions
- Progress bar for rollout percentage
- Modern form styling
- Collapsible fieldsets

---

## Inline Overrides

Edit overrides directly on the flag detail page:

```python
class FlagOverrideInline(TabularInline):
    model = FlagOverride
    extra = 0
    readonly_fields = ["created_at", "created_by"]
    fields = [
        "override_type",
        "target_id",
        "target_value",
        "enabled",
        "variant",
        "expires_at"
    ]
```

---

## Dashboard Integration

Add feature flags to your admin dashboard:

```python
from django_matt.admin import Dashboard, model_stat_widget
from django_matt.flags.models import FeatureFlag

dashboard = Dashboard(title="Admin Dashboard")

# Add flag statistics
dashboard.add_stat(
    model_stat_widget(
        FeatureFlag,
        icon="flag",
        color="primary",
        label="Feature Flags",
    )
)

# Add active flags count
from django_matt.admin import StatWidget
from django_matt.flags.models import FlagStatus

dashboard.add_stat(
    StatWidget(
        title="Active Flags",
        value=FeatureFlag.objects.filter(status=FlagStatus.ACTIVE.value).count(),
        icon="check-circle",
        color="success",
    )
)
```

---

## Audit Log Viewing

The audit log provides complete history of flag changes:

```python
# In admin, view audit logs for any flag:
# /admin/django_matt/flagauditlog/?flag_key=new_feature

# Actions logged:
# - create: Flag created
# - update: Flag updated
# - delete: Flag deleted
# - enable: Flag enabled
# - disable: Flag disabled
# - archive: Flag archived
# - add_override: Override added
# - remove_override: Override removed
```

### Example Audit Entry

```json
{
  "flag_key": "new_checkout",
  "action": "enable",
  "old_values": {
    "status": "inactive"
  },
  "new_values": {
    "status": "active"
  },
  "user": "admin@example.com",
  "ip_address": "192.168.1.100",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## Screenshots

### Flag List View

```
+-------------------------------------------------------------------------+
| FEATURE FLAGS                                          [+ Add] [Actions]|
+-------------------------------------------------------------------------+
| [x] | Key            | Name          | Type    | Status  | Default | % |
+-----+----------------+---------------+---------+---------+---------+---+
| [ ] | new_checkout   | New Checkout  | BOOLEAN | ACTIVE  |   Yes   | - |
| [ ] | gradual_deploy | Gradual Deploy| PERCENT | ACTIVE  |   No    |25%|
| [ ] | ab_experiment  | A/B Test      | VARIANT | ACTIVE  |   Yes   | - |
| [ ] | old_feature    | Legacy        | BOOLEAN | ARCHIVED|   No    | - |
+-------------------------------------------------------------------------+
```

### Override Inline

```
+-------------------------------------------------------------------------+
| OVERRIDES                                                    [+ Add]    |
+-------------------------------------------------------------------------+
| Type         | Target ID      | Target Value | Enabled | Variant | Exp |
+--------------+----------------+--------------+---------+---------+-----+
| USER         | abc-123-def    |              | Yes     |         |     |
| ORGANIZATION | org-456-xyz    |              | Yes     |         |     |
| EMAIL        |                | beta@ex.com  | Yes     | treat_a | 3/1 |
+-------------------------------------------------------------------------+
```

---

## Quick Actions from Admin

### Enable a Flag

1. Go to flag list
2. Check the flag(s)
3. Select "Enable selected flags" from actions
4. Click "Go"

### Add Beta Tester

1. Go to flag detail page
2. Scroll to Overrides section
3. Click "Add another override"
4. Set type to "email", enter email, check "enabled"
5. Save

### Schedule Feature Launch

1. Go to flag detail page
2. Set status to "active"
3. Set "Scheduled enable at" to launch date
4. Save

The flag will only evaluate as active after the scheduled time.

## See Also

- [Models](models.md) - Model reference
- [API](api.md) - REST API alternative
- [Best Practices](best-practices.md) - Management workflows
