# Mixins

django-matt provides reusable mixins for admin classes and views. Mixins follow Django's cooperative inheritance pattern and compose cleanly with each other.

## Admin Mixins

All admin mixins live in `django_matt.admin.mixins` and are designed to be used with `admin.ModelAdmin` (or django-unfold's `ModelAdmin`).

### AuditAdminMixin

For models with audit fields (`created_at`, `updated_at`, `created_by`, `updated_by`). Automatically makes audit fields read-only, shows them in the list view, and sets `created_by`/`updated_by` on save.

```python
from django.contrib import admin
from django_matt.admin.mixins import AuditAdminMixin

@admin.register(Article)
class ArticleAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ["title", "status"]
    # created_at is auto-appended to list_display
    # audit fields are auto-added to readonly_fields
    # created_by/updated_by are auto-set on save
```

**Configuration:**

| Attribute | Default | Description |
|-----------|---------|-------------|
| `created_at_field` | `"created_at"` | Field name for creation timestamp |
| `updated_at_field` | `"updated_at"` | Field name for last update timestamp |
| `created_by_field` | `"created_by"` | Field name for creator user FK |
| `updated_by_field` | `"updated_by"` | Field name for last updater FK |
| `show_audit_in_list` | `True` | Auto-add `created_at` to list_display |

### SoftDeleteAdminMixin

For models using `SoftDeleteMixin`. Provides filtering, restore/hard-delete actions, and overrides `delete_model` to soft delete from the admin.

```python
from django_matt.admin.mixins import SoftDeleteAdminMixin

@admin.register(Document)
class DocumentAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ["title", "created_at"]
```

**What it provides:**
- A "deleted status" list filter with options: Active only, Include deleted, Deleted only
- "Restore selected items" bulk action
- "Permanently delete selected items" bulk action
- Admin delete overridden to soft delete

**Configuration:**

| Attribute | Default | Description |
|-----------|---------|-------------|
| `deleted_at_field` | `"deleted_at"` | Soft delete timestamp field |
| `deleted_by_field` | `"deleted_by"` | User who deleted (optional) |
| `show_deleted_by_default` | `False` | Show deleted items by default |
| `include_restore_action` | `True` | Add restore bulk action |
| `include_hard_delete_action` | `True` | Add permanent delete bulk action |

### ReadOnlyAdminMixin

Makes an admin completely read-only. Useful for audit logs, event history, or analytics tables.

```python
from django_matt.admin.mixins import ReadOnlyAdminMixin

@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["action", "user", "timestamp", "details"]
```

Disables add, change, and delete permissions.

### ExportAdminMixin

Adds CSV and JSON export actions to any admin.

```python
from django_matt.admin.mixins import ExportAdminMixin

@admin.register(Order)
class OrderAdmin(ExportAdminMixin, admin.ModelAdmin):
    list_display = ["id", "customer", "total", "status"]
    export_fields = ["id", "customer", "total", "status", "created_at"]
    export_exclude = ["password", "internal_notes"]
```

**What it provides:**
- "Export selected as CSV" bulk action
- "Export selected as JSON" bulk action (uses orjson)

**Configuration:**

| Attribute | Default | Description |
|-----------|---------|-------------|
| `export_fields` | `None` (all) | Fields to include in export |
| `export_exclude` | `["password"]` | Fields to exclude from export |

### MultiTenantAdminMixin

Auto-filters querysets by the current user's organization. Hides the tenant field from forms and auto-sets it on create.

```python
from django_matt.admin.mixins import MultiTenantAdminMixin

@admin.register(Project)
class ProjectAdmin(MultiTenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "status"]
    tenant_field = "organization"
```

**Configuration:**

| Attribute | Default | Description |
|-----------|---------|-------------|
| `tenant_field` | `"organization"` | FK field referencing the tenant |
| `hide_tenant_in_form` | `True` | Exclude tenant from edit forms |
| `auto_set_tenant` | `True` | Auto-set tenant on create |

Tenant detection checks (in order): `request.user.organization`, `request.user.current_organization`, `request.organization`, `request.tenant`.

## Composing Admin Mixins

Combine multiple mixins for a complete admin:

```python
@admin.register(Invoice)
class InvoiceAdmin(
    AuditAdminMixin,
    SoftDeleteAdminMixin,
    ExportAdminMixin,
    MultiTenantAdminMixin,
    admin.ModelAdmin,
):
    list_display = ["number", "customer", "total", "status"]
    export_fields = ["number", "customer", "total", "status", "created_at"]
```

The mixins use `super()` calls throughout, so cooperative inheritance works correctly. Place `admin.ModelAdmin` (or your base admin class) last.

## View Mixins

### SoftDeleteMixin (Views)

Adds `RestoreView` and `PermanentDeleteView` endpoints to a ViewSet:

```python
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView
from django_matt.views.soft_delete import SoftDeleteMixin, RestoreView, PermanentDeleteView

class ArticleViewSet(SoftDeleteMixin, APIViewSet):
    api = api
    model = Article
    default_response_schema = ArticleSchema

    list = ListView()
    create = CreateView()
    read = ReadView()
    update = UpdateView()
    # delete is replaced by soft delete from the mixin
    restore = RestoreView()
    permanent_delete = PermanentDeleteView()
```

### HooksMixin

Enables lifecycle hooks on a ViewSet (enabled by default on `APIViewSet`):

```python
from django_matt.views import APIViewSet
from django_matt.views.hooks import HooksMixin

class UserViewSet(HooksMixin, APIViewSet):
    async def before_create(self, request, data):
        data["created_by_id"] = request.user.id
        return data

    async def after_create(self, request, instance):
        await send_welcome_email(instance)
        return instance
```

## Creating Custom Mixins

Follow these patterns when creating your own mixins:

1. Inherit from `object` (or nothing) for admin/view mixins
2. Always call `super()` in overridden methods
3. Use `class Meta: abstract = True` for model mixins
4. Prefix configuration attributes to avoid collisions

```python
class SlugAdminMixin:
    """Auto-populate slug field from a source field in admin."""
    slug_field = "slug"
    slug_source = "title"

    def get_prepopulated_fields(self, request, obj=None):
        fields = dict(super().get_prepopulated_fields(request, obj) or {})
        fields[self.slug_field] = (self.slug_source,)
        return fields

class TimestampModelMixin(models.Model):
    """Add created_at and updated_at to any model."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```
