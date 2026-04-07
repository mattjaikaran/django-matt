# Models

django-matt provides abstract base models and mixins for common patterns: soft delete, audit tracking, UUIDs, and timestamps.

## Soft Delete

The `SoftDeleteMixin` replaces `delete()` with a soft delete that sets a `deleted_at` timestamp. Records remain in the database but are hidden from default queries.

### SoftDeleteMixin

```python
from django.db import models
from django_matt.db import SoftDeleteMixin

class Article(SoftDeleteMixin, models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
```

**Fields added:**
- `deleted_at` — `DateTimeField(null=True, db_index=True)`. `None` means active.

**Instance methods:**

| Method | Description |
|--------|-------------|
| `delete()` | Soft delete — sets `deleted_at` to now |
| `adelete()` | Async soft delete |
| `hard_delete()` | Permanent database removal |
| `ahard_delete()` | Async permanent delete |
| `restore()` | Clear `deleted_at`, making the record active again |
| `arestore()` | Async restore |

**Property:**
- `is_deleted` — `True` if `deleted_at` is not None

**Managers:**

```python
# Default manager excludes deleted records
Article.objects.all()           # only active records
Article.objects.count()         # only active

# Include deleted
Article.objects.with_deleted().all()

# Only deleted
Article.objects.deleted_only().all()
```

**QuerySet operations:**

```python
# Soft delete a queryset
Article.objects.filter(author=user).delete()

# Hard delete a queryset
Article.objects.filter(author=user).hard_delete()

# Restore a queryset
Article.objects.deleted_only().filter(author=user).restore()
```

### SoftDeleteWithUserMixin

Extends `SoftDeleteMixin` with a `deleted_by` foreign key to track who deleted the record:

```python
from django_matt.db import SoftDeleteWithUserMixin

class Document(SoftDeleteWithUserMixin, models.Model):
    title = models.CharField(max_length=200)

# Delete with user tracking
document.delete(user=request.user)

# Check who deleted it
print(document.deleted_by)  # User instance

# Restore clears both deleted_at and deleted_by
document.restore()
```

**Additional fields:**
- `deleted_by` — `ForeignKey("auth.User", null=True, on_delete=SET_NULL)`

### Cascade Utilities

Soft delete or restore an instance and all its related soft-deletable objects:

```python
from django_matt.db import soft_delete_cascade, restore_cascade

# Soft delete user and all related posts, comments, etc.
soft_delete_cascade(user)

# Restore user and all related records
restore_cascade(user)
```

## Recommended Base Model Pattern

django-matt does not ship an opinionated `BaseModel` Django model — compose what you need from mixins. A common pattern:

```python
import uuid
from django.db import models
from django_matt.db import SoftDeleteMixin

class BaseModel(SoftDeleteMixin, models.Model):
    """Project-wide abstract base model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
```

### With Audit Fields

Track who created and last modified each record:

```python
from django.conf import settings

class AuditModel(BaseModel):
    """Base model with user audit tracking."""
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated",
    )

    class Meta:
        abstract = True
```

## Common Field Patterns

### UUID Primary Keys

```python
id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
```

### Timestamps

```python
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
```

### Slug with Auto-generation

```python
from django.utils.text import slugify

class Article(BaseModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
```

### Status Fields with Choices

```python
class Order(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
```

When used with `ModelSchema`, choices become `Literal` types and appear as enums in OpenAPI.

## Database Utilities

The `django_matt.db` module provides helpers for database introspection and connection info:

```python
from django_matt.db import get_db_type, is_postgres, get_db_version, get_table_names

get_db_type()       # "postgresql", "mysql", "sqlite"
is_postgres()       # True/False
get_db_version()    # "16.2"
get_table_names()   # ["auth_user", "myapp_article", ...]
```

## QuerySet Managers

The `SoftDeleteManager` and `SoftDeleteQuerySet` are provided as separate classes if you need to compose them with other custom managers:

```python
from django_matt.db import SoftDeleteManager, SoftDeleteQuerySet

class ArticleQuerySet(SoftDeleteQuerySet):
    def published(self):
        return self.filter(status="published")

class ArticleManager(SoftDeleteManager):
    _queryset_class = ArticleQuerySet

class Article(SoftDeleteMixin, models.Model):
    objects = ArticleManager(alive_only=True)
    all_objects = ArticleManager(alive_only=False)
```
