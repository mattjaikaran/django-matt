# Scaffolding Workflow

Django Matt provides a Rails-like scaffolding workflow: generate app structure first, then fill in models and regenerate everything around them.

## Design Principles

### Small Files, Always

Django Matt enforces a **modular, small-file architecture** by default:

- **No file should exceed 500 lines.** If it does, split it.
- **One model per file.** `models/post.py`, not a 1500-line `models.py`.
- **One controller per file.** `controllers/post_controller.py`, not `views.py`.
- **One schema set per file.** `schemas/post_schema.py` with Create/Update/Read variants.
- **One admin config per file.** `admin/post_admin.py`.
- **One service per file.** `services/post_service.py`.
- **One factory per file.** `tests/factories/post_factory.py`.
- **One test module per model.** `tests/test_post.py`.

This is non-negotiable. The scaffolding commands enforce this structure. The framework encourages it at every level.

### Why Package-Based

Django's default flat structure (`models.py`, `views.py`, `admin.py`) works for tiny apps. It collapses when you have 10+ models. You end up with:

- `models.py` at 3000 lines
- `views.py` at 2000 lines
- Merge conflicts on every PR
- No way to find anything

Package-based means:

```
# Bad: flat
myapp/
├── models.py      # 3000 lines, 15 models
├── views.py       # 2000 lines
├── admin.py       # 800 lines
└── tests.py       # 1500 lines

# Good: packages
myapp/
├── models/
│   ├── __init__.py
│   ├── user.py          # ~50 lines
│   ├── post.py          # ~40 lines
│   └── comment.py       # ~35 lines
├── controllers/
│   ├── __init__.py
│   ├── user_controller.py
│   ├── post_controller.py
│   └── comment_controller.py
├── schemas/
│   └── ...
└── tests/
    ├── test_user.py
    ├── test_post.py
    └── test_comment.py
```

Every file is small. Every file has one job. Git diffs are clean. New developers can navigate immediately.

## The Two-Step Workflow

### Step 1: Create the App

```bash
python manage.py startapp blog --models Post Comment Tag
```

This creates the full package structure with starter files for each model. The generated models have basic fields (UUID pk, title, description, timestamps) — they're starting points.

### Step 2: Customize Your Models

Edit the generated model files to add your actual fields:

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
    slug = models.SlugField(max_length=255, unique=True)
    body = models.TextField()
    excerpt = models.CharField(max_length=500, blank=True)
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField("Tag", blank=True, related_name="posts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-published_at", "-created_at"]
```

### Step 3: Migrate

```bash
python manage.py makemigrations blog
python manage.py migrate
```

### Step 4: Regenerate Scaffolding

Now regenerate the schema, controller, admin, service, and tests from your real model:

```bash
python manage.py generate_crud blog.Post --full
python manage.py generate_crud blog.Comment --full
python manage.py generate_crud blog.Tag --full
```

This reads your model's actual fields and generates code that matches — proper field types in schemas, correct `select_related`/`prefetch_related` in controllers, appropriate `list_display` in admin.

## Complete Example

Build a blog app from scratch:

```bash
# 1. Scaffold the app
python manage.py startapp blog --models Post Comment Tag

# 2. Add to INSTALLED_APPS
# settings.py: INSTALLED_APPS += ["blog"]

# 3. Edit models to add real fields
# (edit blog/models/post.py, comment.py, tag.py)

# 4. Create and run migrations
python manage.py makemigrations blog && python manage.py migrate

# 5. Regenerate everything from the real models
python manage.py generate_crud blog.Post --full
python manage.py generate_crud blog.Comment --full
python manage.py generate_crud blog.Tag --full

# 6. Run tests to verify
pytest blog/tests/ -v
```

## Adding a New Model to an Existing App

You don't need to re-run `startapp`. Just:

```bash
# 1. Create the model file
touch blog/models/category.py

# 2. Write your model

# 3. Add it to blog/models/__init__.py:
#    from blog.models.category import Category

# 4. Migrate
python manage.py makemigrations blog && python manage.py migrate

# 5. Generate everything
python manage.py generate_crud blog.Category --full
```

## Makefile Shortcuts

```bash
# Create a new app
make startapp NAME=blog MODELS="Post Comment Tag"

# Generate CRUD for a model
make crud MODEL=blog.Post

# Generate full CRUD (with admin, tests, service)
make crud-full MODEL=blog.Post
```

## What Each Command Generates

| Component | `startapp` generates | `generate_crud --full` generates |
|-----------|---------------------|----------------------------------|
| Model | Starter with UUID/timestamps | *Doesn't modify models* |
| Schema | Basic title/description schema | Schema matching real model fields |
| Controller | Generic CRUD controller | Controller with proper field handling |
| Service | Generic async CRUD | Service with relationship handling |
| Admin | Basic list_display | Admin matching real fields |
| Tests | Stubs with TODO | Tests with proper fixtures |
| Factory | Basic Faker factory | Factory matching real fields |
| `__init__.py` | Auto-imports | *Doesn't modify* |
| `urls.py` | Router setup | *Doesn't modify* |

Use `startapp` for the initial skeleton. Use `generate_crud` to regenerate scaffolding after model changes.

## Fast Tooling

Django Matt leverages the fastest tools in the Python ecosystem:

| Tool | Purpose | Why it's fast |
|------|---------|---------------|
| **uv** | Package management | Rust-based, 10-100x faster than pip |
| **ruff** | Linting + formatting | Rust-based, replaces flake8/black/isort |
| **orjson** | JSON serialization | Rust-based, 3-10x faster than stdlib json |
| **Pydantic v2** | Schema validation | Rust core (pydantic-core) |
| **uvicorn** | ASGI server | uvloop-powered async |

Every code path in django-matt uses these tools by default. Generated code imports `orjson` directly, schemas use Pydantic v2, and the dev server runs through uvicorn.

## See Also

- [startapp — App Scaffolding](startapp.md)
- [generate_crud — CRUD Generator](crud-generator.md)
- [Architecture](architecture.md)
