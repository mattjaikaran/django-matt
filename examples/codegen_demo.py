#!/usr/bin/env python
"""
Example demonstrating Django Matt's frontend code generation features.

This example shows how to use the code generation utilities to create:
- TypeScript interfaces from Django models
- Zod validation schemas
- React Query (TanStack Query) hooks
- React form and list components

To run this example:
1. Install Django and Django Matt
2. Run this script with Python: uv run python examples/codegen_demo.py

"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

# Add the parent directory to the path so we can import django_matt
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure Django settings (minimal setup for codegen - no database required)
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="django-matt-codegen-demo",
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
    )
    django.setup()


def create_mock_model(name: str, app_label: str, fields: list[dict]) -> Mock:
    """
    Create a mock Django model for testing code generation.

    Args:
        name: Model name (e.g., "User")
        app_label: App label (e.g., "users")
        fields: List of field dictionaries with configuration

    Returns:
        Mock model object
    """
    mock_model = Mock()
    mock_model._meta = Mock()
    mock_model._meta.object_name = name
    mock_model._meta.app_label = app_label
    mock_model._meta.verbose_name = name.lower()
    mock_model._meta.verbose_name_plural = name.lower() + "s"
    mock_model._meta.db_table = f"{app_label}_{name.lower()}"
    mock_model._meta.ordering = []
    mock_model._meta.unique_together = []
    mock_model._meta.indexes = []

    mock_fields = []
    for field_config in fields:
        mock_field = Mock()
        mock_field.name = field_config["name"]
        mock_field.__class__.__name__ = field_config["type"]
        mock_field.is_relation = field_config.get("is_relation", False)
        mock_field.column = field_config["name"]
        mock_field.null = field_config.get("null", False)
        mock_field.blank = field_config.get("blank", False)
        mock_field.has_default = Mock(return_value=field_config.get("has_default", False))
        mock_field.default = field_config.get("default", None)
        mock_field.max_length = field_config.get("max_length", None)
        mock_field.choices = field_config.get("choices", None)
        mock_field.help_text = field_config.get("help_text", "")
        mock_field.verbose_name = field_config.get("verbose_name", field_config["name"])
        mock_field.validators = []
        mock_field.primary_key = field_config.get("primary_key", False)
        mock_field.unique = field_config.get("unique", False)
        mock_field.editable = field_config.get("editable", True)
        mock_fields.append(mock_field)

    mock_model._meta.get_fields = Mock(return_value=mock_fields)
    return mock_model


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_subheader(title: str):
    """Print a formatted subheader."""
    print(f"\n--- {title} ---\n")


def print_code(code: str, language: str = "typescript"):
    """Print code with formatting."""
    print(f"```{language}")
    print(code)
    print("```\n")


def demo_typescript_interface():
    """Demonstrate TypeScript interface generation."""
    from django_matt.codegen import generate_typescript_interface

    print_header("1. TypeScript Interface Generation")

    # Create a mock User model
    user_model = create_mock_model("User", "users", [
        {"name": "id", "type": "AutoField", "primary_key": True, "editable": False},
        {"name": "email", "type": "EmailField", "unique": True, "max_length": 255},
        {"name": "first_name", "type": "CharField", "max_length": 100, "verbose_name": "first name"},
        {"name": "last_name", "type": "CharField", "max_length": 100, "verbose_name": "last name"},
        {"name": "is_active", "type": "BooleanField", "has_default": True, "default": True},
        {"name": "bio", "type": "TextField", "null": True, "blank": True, "verbose_name": "biography"},
        {"name": "created_at", "type": "DateTimeField", "editable": False},
    ])

    print_subheader("Generated TypeScript Interface for User model")
    ts_code = generate_typescript_interface(user_model)
    print_code(ts_code)

    return user_model


def demo_zod_schema():
    """Demonstrate Zod schema generation."""
    from django_matt.codegen import generate_zod_schema

    print_header("2. Zod Schema Generation")

    # Create a mock Product model
    product_model = create_mock_model("Product", "catalog", [
        {"name": "id", "type": "AutoField", "primary_key": True, "editable": False},
        {"name": "name", "type": "CharField", "max_length": 200},
        {"name": "description", "type": "TextField", "blank": True},
        {"name": "price", "type": "DecimalField"},
        {"name": "stock", "type": "IntegerField", "has_default": True, "default": 0},
        {"name": "is_available", "type": "BooleanField", "has_default": True, "default": True},
        {"name": "category", "type": "CharField", "max_length": 50,
         "choices": [("electronics", "Electronics"), ("clothing", "Clothing"), ("books", "Books")]},
        {"name": "sku", "type": "CharField", "max_length": 50, "unique": True},
    ])

    print_subheader("Generated Zod Schema for Product model")
    zod_code = generate_zod_schema(product_model, "ProductSchema")
    print_code(zod_code)

    # Also show Create and Update schemas
    from django_matt.codegen.typescript import generate_create_schema, generate_update_schema

    print_subheader("Generated Create Schema")
    create_code = generate_create_schema(product_model)
    print_code(create_code)

    print_subheader("Generated Update Schema")
    update_code = generate_update_schema(product_model)
    print_code(update_code)

    return product_model


def demo_react_hooks():
    """Demonstrate React Query hooks generation."""
    from django_matt.codegen import generate_react_hooks

    print_header("3. React Query (TanStack Query) Hooks Generation")

    # Create a mock Order model
    order_model = create_mock_model("Order", "orders", [
        {"name": "id", "type": "AutoField", "primary_key": True, "editable": False},
        {"name": "customer_email", "type": "EmailField"},
        {"name": "status", "type": "CharField", "max_length": 20,
         "choices": [("pending", "Pending"), ("processing", "Processing"),
                    ("shipped", "Shipped"), ("delivered", "Delivered")]},
        {"name": "total", "type": "DecimalField"},
        {"name": "created_at", "type": "DateTimeField", "editable": False},
    ])

    print_subheader("Generated TanStack Query Hooks for Order model")
    hooks_code = generate_react_hooks(order_model, api_base="/api/v1")
    print_code(hooks_code)

    # Show hooks without mutations
    print_subheader("Read-only Hooks (without mutations)")
    readonly_hooks = generate_react_hooks(order_model, api_base="/api/v1", include_mutations=False)
    print_code(readonly_hooks)

    return order_model


def demo_react_components():
    """Demonstrate React component generation."""
    from django_matt.codegen import generate_react_form, generate_react_list, generate_react_detail

    print_header("4. React Component Generation")

    # Create a mock Task model
    task_model = create_mock_model("Task", "tasks", [
        {"name": "id", "type": "AutoField", "primary_key": True, "editable": False},
        {"name": "title", "type": "CharField", "max_length": 200, "verbose_name": "title"},
        {"name": "description", "type": "TextField", "blank": True, "verbose_name": "description"},
        {"name": "priority", "type": "CharField", "max_length": 20,
         "choices": [("low", "Low"), ("medium", "Medium"), ("high", "High")]},
        {"name": "completed", "type": "BooleanField", "has_default": True, "default": False,
         "verbose_name": "completed"},
        {"name": "due_date", "type": "DateField", "null": True, "blank": True, "verbose_name": "due date"},
    ])

    print_subheader("Generated Form Component (with shadcn/ui)")
    form_code = generate_react_form(task_model, ui_library="shadcn")
    print_code(form_code, "tsx")

    print_subheader("Generated List Component")
    list_code = generate_react_list(task_model, ui_library="shadcn")
    print_code(list_code, "tsx")

    print_subheader("Generated Detail Component")
    detail_code = generate_react_detail(task_model, ui_library="shadcn")
    print_code(detail_code, "tsx")

    return task_model


def demo_full_generation():
    """Demonstrate full code generation with ReactGenerator."""
    from django_matt.codegen import ReactGenerator

    print_header("5. Full React Generation (ReactGenerator)")

    # Create mock models
    user_model = create_mock_model("User", "users", [
        {"name": "id", "type": "AutoField", "primary_key": True, "editable": False},
        {"name": "email", "type": "EmailField", "unique": True},
        {"name": "name", "type": "CharField", "max_length": 100},
        {"name": "is_active", "type": "BooleanField", "has_default": True, "default": True},
    ])

    post_model = create_mock_model("Post", "blog", [
        {"name": "id", "type": "AutoField", "primary_key": True, "editable": False},
        {"name": "title", "type": "CharField", "max_length": 200},
        {"name": "content", "type": "TextField"},
        {"name": "published", "type": "BooleanField", "has_default": True, "default": False},
        {"name": "created_at", "type": "DateTimeField", "editable": False},
    ])

    print_subheader("Generating full React codebase for User and Post models...")

    generator = ReactGenerator(
        models=[user_model, post_model],
        output_dir="./generated",
        api_base="/api",
        ui_library="shadcn",
    )

    files = generator.generate_all()

    print(f"Generated {len(files)} files:\n")
    for filename in sorted(files.keys()):
        print(f"  - {filename}")

    # Show sample generated files
    print_subheader("Sample: types.ts")
    if "types.ts" in files:
        print_code(files["types.ts"])

    print_subheader("Sample: schemas.ts")
    if "schemas.ts" in files:
        # Just show first part since it can be long
        schema_content = files["schemas.ts"]
        if len(schema_content) > 2000:
            schema_content = schema_content[:2000] + "\n// ... (truncated)"
        print_code(schema_content)

    print_subheader("Sample: hooks.ts")
    if "hooks.ts" in files:
        hooks_content = files["hooks.ts"]
        if len(hooks_content) > 3000:
            hooks_content = hooks_content[:3000] + "\n// ... (truncated)"
        print_code(hooks_content)

    return files


def demo_typescript_generator_class():
    """Demonstrate TypeScriptGenerator class usage."""
    from django_matt.codegen import TypeScriptGenerator

    print_header("6. TypeScriptGenerator Class")

    # Create mock models
    article_model = create_mock_model("Article", "news", [
        {"name": "id", "type": "AutoField", "primary_key": True, "editable": False},
        {"name": "title", "type": "CharField", "max_length": 300},
        {"name": "slug", "type": "SlugField", "max_length": 300, "unique": True},
        {"name": "content", "type": "TextField"},
        {"name": "author_name", "type": "CharField", "max_length": 100},
        {"name": "view_count", "type": "IntegerField", "has_default": True, "default": 0},
        {"name": "is_featured", "type": "BooleanField", "has_default": True, "default": False},
        {"name": "published_at", "type": "DateTimeField", "null": True, "blank": True},
    ])

    print_subheader("Using TypeScriptGenerator for types and schemas")

    generator = TypeScriptGenerator([article_model], output_dir="./generated")
    all_files = generator.generate_all()

    print("Generated files:")
    for filename, content in all_files.items():
        print(f"\n--- {filename} ---")
        print_code(content)


def demo_write_to_disk():
    """Demonstrate writing generated files to disk."""
    from django_matt.codegen import ReactGenerator

    print_header("7. Writing Generated Files to Disk")

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "generated"

        # Create mock models
        user_model = create_mock_model("User", "users", [
            {"name": "id", "type": "AutoField", "primary_key": True, "editable": False},
            {"name": "email", "type": "EmailField", "unique": True},
            {"name": "name", "type": "CharField", "max_length": 100},
        ])

        print(f"Output directory: {output_dir}")
        print_subheader("Generating and writing files...")

        generator = ReactGenerator(
            models=[user_model],
            output_dir=str(output_dir),
            api_base="/api",
        )

        # Generate files (returns dict)
        files = generator.generate_all()

        # Write files to disk
        os.makedirs(output_dir, exist_ok=True)
        written = []
        for filepath, content in files.items():
            full_path = output_dir / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            written.append(full_path)

        print(f"\nSuccessfully wrote {len(written)} files:")
        for path in sorted(written):
            rel_path = path.relative_to(output_dir)
            print(f"  - {rel_path}")

        # Verify files exist
        print("\nFile contents verification:")
        for path in written:
            content = path.read_text()
            print(f"  - {path.name}: {len(content)} bytes")


def demo_core_primitives():
    """Demonstrate core code generation primitives."""
    from django_matt.codegen import (
        Interface, Property, Function, Parameter,
        ImportFrom, CodeFile, Return, Statement
    )

    print_header("8. Core Code Generation Primitives")

    print_subheader("Building custom TypeScript code with AST-like nodes")

    # Create a custom interface
    custom_interface = Interface(
        name="ApiResponse",
        generic="T",
        properties=[
            Property("data", "T"),
            Property("success", "boolean"),
            Property("message", "string", optional=True),
            Property("timestamp", "string", readonly=True),
        ],
        comment="Generic API response wrapper",
    )

    print("Custom Interface:")
    print_code(custom_interface.to_typescript())

    # Create a custom function
    fetch_function = Function(
        name="fetchData",
        generic="T",
        parameters=[
            Parameter("url", "string"),
            Parameter("options", "RequestInit", optional=True),
        ],
        return_type="Promise<ApiResponse<T>>",
        async_=True,
        export=True,
        body=[
            Statement("const response = await fetch(url, options)"),
            Statement("const data = await response.json()"),
            Return("data as ApiResponse<T>"),
        ],
        comment="Fetch data from API with typed response",
    )

    print("Custom Function:")
    print_code(fetch_function.to_typescript())

    # Create a complete file
    file = CodeFile()
    file.header_comment = "Custom API utilities\nGenerated by django-matt"
    file.add_import(ImportFrom("zod", ["z"]))
    file.add_node(custom_interface)
    file.add_node(fetch_function)

    print("Complete File:")
    print_code(file.to_typescript())


def main():
    """Run all code generation demos."""
    print("\n" + "=" * 70)
    print(" Django Matt Frontend Code Generation Demo")
    print("=" * 70)
    print("""
This demo showcases the frontend code generation capabilities of django-matt.
You'll see how to generate:

  1. TypeScript interfaces from Django models
  2. Zod validation schemas
  3. React Query (TanStack Query) hooks
  4. React form, list, and detail components
  5. Full React codebases with a single generator
  6. TypeScriptGenerator for types-only generation
  7. Writing generated files to disk
  8. Core primitives for custom code generation

Let's get started!
""")

    try:
        # Run demos
        demo_typescript_interface()
        demo_zod_schema()
        demo_react_hooks()
        demo_react_components()
        demo_full_generation()
        demo_typescript_generator_class()
        demo_write_to_disk()
        demo_core_primitives()

        print_header("Demo Complete!")
        print("""
The code generation features demonstrated above can be used in your project:

1. Management command:
   python manage.py sync_types --target react --output frontend/src/generated

2. Programmatic usage:
   from django_matt.codegen import ReactGenerator
   generator = ReactGenerator(models=[User, Post])
   files = generator.generate_all()

3. Configuration file:
   Create django_matt_codegen.py with your settings

For more details, see the documentation at:
  docs/codegen/overview.md
""")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
