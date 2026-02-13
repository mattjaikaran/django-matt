# generate_crud — CRUD Code Generator

The `generate_crud` command generates complete CRUD scaffolding from an existing Django model. It reads your model's fields, relationships, and metadata to produce production-ready code.

## Philosophy

> **Define the model once. Generate everything else.**

Your Django model is the source of truth. The generator introspects its fields (CharField, ForeignKey, ManyToMany, etc.) and produces schemas, controllers, services, admin, and tests that match exactly.

## Quick Start

```bash
# Generate a controller + schema for an existing model
python manage.py generate_crud blog.Post

# Generate everything: controller, schema, service, admin, tests
python manage.py generate_crud blog.Post --full

# Preview what would be generated
python manage.py generate_crud blog.Post --full --dry-run

# Interactive wizard mode
python manage.py generate_crud
```

Or via Make:

```bash
make crud MODEL=blog.Post
make crud-full MODEL=blog.Post
```

## Command Options

| Option | Description |
|--------|-------------|
| `model` | Model path as `app.Model` (positional) |
| `--full` | Generate all components (controller, schema, service, admin, tests) |
| `--with-admin` | Include Django Unfold admin config |
| `--with-tests` | Include pytest test file |
| `--no-service` | Skip the service layer |
| `--soft-delete` | Use soft delete instead of hard delete |
| `--permissions` | Permission classes to apply (e.g. `IsAuthenticated`) |
| `--pagination` | Include pagination (default: true) |
| `--filtering` | Include filtering support |
| `--prefix` | Custom URL prefix |
| `--output-dir` | Custom output directory |
| `--dry-run` | Preview without writing files |

## What Gets Generated

Given this model:

```python
# blog/models/post.py
import uuid
from django.db import models
from django.conf import settings


class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    published = models.BooleanField(default=False)
    tags = models.ManyToManyField("Tag", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

Running `python manage.py generate_crud blog.Post --full` produces:

### Schema

- Reads all fields from the model
- Detects FK/M2M relationships and generates nested or ID-based fields
- Creates `PostSchema` (response), `PostCreateSchema`, `PostUpdateSchema` (partial), `PostListSchema`

```python
class PostSchema(Schema):
    id: uuid.UUID
    author_id: int
    title: str
    body: str
    published: bool
    tags: list[int]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class PostCreateSchema(Schema):
    title: str = Field(..., max_length=255)
    body: str
    published: bool = False
    tag_ids: list[int] = []


class PostUpdateSchema(Schema):
    title: Optional[str] = Field(None, max_length=255)
    body: Optional[str] = None
    published: Optional[bool] = None
    tag_ids: Optional[list[int]] = None
```

### Controller

- Async CRUD endpoints
- Uses `CRUDController` base class
- Injects permission classes if specified

### Service Layer

- Business logic separated from the controller
- All async ORM operations (`.aget()`, `.acreate()`, `.asave()`, `.adelete()`)
- Handles related field updates (M2M `.aset()`)

### Admin

- `@admin.register` with Unfold `ModelAdmin`
- `list_display` from model fields
- `list_filter` for booleans and dates
- `search_fields` for text fields
- `readonly_fields` for auto-generated fields

### Tests

- pytest fixtures with Factory Boy
- Model CRUD tests
- API endpoint tests (list, create, read, update, delete)

## Interactive Wizard

Running `generate_crud` with no arguments starts the interactive wizard:

```bash
$ python manage.py generate_crud

Welcome to the CRUD Generator!

Enter model (app.Model): blog.Post
Generate service layer? [Y/n]: y
Generate admin? [Y/n]: y
Generate tests? [Y/n]: y
Use soft delete? [y/N]: n
Permission classes (comma-separated, or blank): IsAuthenticated
URL prefix (blank for auto):

Generating...
  Created blog/schemas/post_schema.py
  Created blog/controllers/post_controller.py
  Created blog/services/post_service.py
  Created blog/admin/post_admin.py
  Created blog/tests/test_post.py
Done!
```

## Common Workflows

### New App from Scratch

```bash
# 1. Create the app skeleton
python manage.py startapp blog --models Post Comment Tag

# 2. Customize the generated models (add fields, relationships)
# edit blog/models/post.py, comment.py, tag.py

# 3. Create and run migrations
python manage.py makemigrations blog && python manage.py migrate

# 4. Regenerate scaffolding from your final models
python manage.py generate_crud blog.Post --full
python manage.py generate_crud blog.Comment --full
python manage.py generate_crud blog.Tag --full
```

### Add CRUD to an Existing Model

```bash
# Model already exists and has migrations
python manage.py generate_crud myapp.Product --full
```

### Schema-Only Generation

```bash
# Just need schemas, no controller/admin/tests
python manage.py generate_crud blog.Post
```

### With Permissions and Soft Delete

```bash
python manage.py generate_crud blog.Post \
    --full \
    --permissions IsAuthenticated \
    --soft-delete
```

## Output Locations

Generated files go into the app's package structure:

| Component | Path |
|-----------|------|
| Schema | `{app}/schemas/{model}_schema.py` |
| Controller | `{app}/controllers/{model}_controller.py` |
| Service | `{app}/services/{model}_service.py` |
| Admin | `{app}/admin/{model}_admin.py` |
| Tests | `{app}/tests/test_{model}.py` |

## Relationship Handling

The generator detects and handles:

- **ForeignKey**: Generates `{field}_id` in schemas, uses `select_related` in queries
- **ManyToManyField**: Generates `{field}_ids` list in create/update schemas, handles `.set()` in service
- **OneToOneField**: Treated like FK with `select_related`

## See Also

- [startapp — App Scaffolding](startapp.md)
- [Scaffolding Workflow](scaffolding.md)
- [Controllers](controllers.md)
- [Schemas](core/schemas.md)
