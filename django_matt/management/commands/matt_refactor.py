# file-length-max: 1500
"""
Django Matt CLI - Model refactoring management commands.

Safely move, rename, split, and merge Django models and apps with proper
migration generation, reference updates, and AST-based code rewriting.

Usage:
    python manage.py matt_refactor move-model myapp.Product newapp
    python manage.py matt_refactor move-model myapp.Product newapp --dry-run
    python manage.py matt_refactor rename-model myapp.Product myapp.Item
    python manage.py matt_refactor split-app myapp --models Product,Category --new-app catalog
    python manage.py matt_refactor merge-apps app1 app2 --into combined
"""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings
from django.db import models

from django_matt.cli import MattCommand

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class FieldReference:
    """A FK / O2O / M2M reference to or from a model."""

    app_label: str
    model_name: str
    field_name: str
    field_type: str  # ForeignKey, OneToOneField, ManyToManyField
    target_app: str
    target_model: str
    file_path: Path | None = None


@dataclass
class ImportReference:
    """An import of a model found via AST analysis."""

    file_path: Path
    line_number: int
    original_line: str
    module_path: str
    name: str


@dataclass
class AdminReference:
    """An admin registration for a model."""

    file_path: Path
    line_number: int
    model_name: str


@dataclass
class RefactorPlan:
    """Complete plan for a refactoring operation."""

    description: str
    field_refs: list[FieldReference] = field(default_factory=list)
    import_refs: list[ImportReference] = field(default_factory=list)
    admin_refs: list[AdminReference] = field(default_factory=list)
    migrations: list[dict[str, Any]] = field(default_factory=list)
    file_changes: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AST visitor for finding model references
# ---------------------------------------------------------------------------


class ModelReferenceVisitor(ast.NodeVisitor):
    """Find imports and string references to a specific model."""

    def __init__(self, app_label: str, model_name: str) -> None:
        self.app_label = app_label
        self.model_name = model_name
        self.imports: list[dict[str, Any]] = []
        self.string_refs: list[dict[str, Any]] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and node.names:
            for alias in node.names:
                if alias.name == self.model_name:
                    # Check if the import path looks related to our app
                    if self.app_label in (node.module or ""):
                        self.imports.append(
                            {
                                "module": node.module,
                                "name": alias.name,
                                "alias": alias.asname,
                                "line": node.lineno,
                            }
                        )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            ref = f"{self.app_label}.{self.model_name}"
            if node.value == ref or node.value == self.model_name:
                self.string_refs.append({"value": node.value, "line": node.lineno})
        self.generic_visit(node)


class AdminRegistrationVisitor(ast.NodeVisitor):
    """Find admin.site.register() calls for a specific model."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.registrations: list[dict[str, Any]] = []

    def visit_Call(self, node: ast.Call) -> None:
        # Match admin.site.register(ModelName, ...)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "register":
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id == self.model_name:
                    self.registrations.append({"line": node.lineno})
        # Match @admin.register(ModelName)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_decorators(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._check_decorators(node)
        self.generic_visit(node)

    def _check_decorators(self, node: ast.FunctionDef | ast.ClassDef) -> None:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr == "register":
                        for arg in decorator.args:
                            if isinstance(arg, ast.Name) and arg.id == self.model_name:
                                self.registrations.append({"line": decorator.lineno})


# ---------------------------------------------------------------------------
# Core analysis engine
# ---------------------------------------------------------------------------


class RefactorAnalyzer:
    """Analyze a Django project for model references."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(settings.BASE_DIR)

    def get_model_class(self, app_label: str, model_name: str) -> type[models.Model]:
        """Resolve a model class from app_label.ModelName."""
        return apps.get_model(app_label, model_name)

    def find_field_references(self, app_label: str, model_name: str) -> list[FieldReference]:
        """Find all FK/O2O/M2M fields pointing to this model."""
        refs: list[FieldReference] = []
        target_model = self.get_model_class(app_label, model_name)

        for model in apps.get_models():
            for f in model._meta.get_fields():
                related_model = None
                field_type = ""

                if isinstance(f, models.ForeignKey):
                    related_model = f.related_model
                    field_type = "ForeignKey"
                elif isinstance(f, models.OneToOneField):
                    related_model = f.related_model
                    field_type = "OneToOneField"
                elif isinstance(f, models.ManyToManyField):
                    related_model = f.related_model
                    field_type = "ManyToManyField"
                elif hasattr(f, "related_model") and hasattr(f, "field"):
                    # Reverse relations
                    continue

                if related_model is target_model and model is not target_model:
                    refs.append(
                        FieldReference(
                            app_label=model._meta.app_label,
                            model_name=model.__name__,
                            field_name=f.name,
                            field_type=field_type,
                            target_app=app_label,
                            target_model=model_name,
                        )
                    )

        return refs

    def find_import_references(self, app_label: str, model_name: str) -> list[ImportReference]:
        """Find all import statements referencing this model via AST."""
        refs: list[ImportReference] = []

        for py_file in self._python_files():
            try:
                source = py_file.read_text()
                tree = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError):
                continue

            visitor = ModelReferenceVisitor(app_label, model_name)
            visitor.visit(tree)

            for imp in visitor.imports:
                refs.append(
                    ImportReference(
                        file_path=py_file,
                        line_number=imp["line"],
                        original_line=source.splitlines()[imp["line"] - 1]
                        if imp["line"] <= len(source.splitlines())
                        else "",
                        module_path=imp["module"],
                        name=imp["name"],
                    )
                )

        return refs

    def find_admin_references(self, app_label: str, model_name: str) -> list[AdminReference]:
        """Find admin.site.register() calls for this model."""
        refs: list[AdminReference] = []

        # Check admin.py in the app
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            return refs

        admin_file = Path(app_config.path) / "admin.py"
        if not admin_file.exists():
            return refs

        try:
            source = admin_file.read_text()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return refs

        visitor = AdminRegistrationVisitor(model_name)
        visitor.visit(tree)

        for reg in visitor.registrations:
            refs.append(
                AdminReference(
                    file_path=admin_file,
                    line_number=reg["line"],
                    model_name=model_name,
                )
            )

        return refs

    def get_model_source(self, app_label: str, model_name: str) -> str | None:
        """Extract the source code for a model class via AST."""
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            return None

        models_file = Path(app_config.path) / "models.py"
        if not models_file.exists():
            return None

        try:
            source = models_file.read_text()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return None

        lines = source.splitlines(keepends=True)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == model_name:
                start = node.lineno - 1
                end = node.end_lineno if node.end_lineno else start + 1
                return "".join(lines[start:end])

        return None

    def get_model_fields_repr(self, app_label: str, model_name: str) -> list[dict[str, str]]:
        """Get a representation of model fields for migration generation."""
        model = self.get_model_class(app_label, model_name)
        fields_info: list[dict[str, str]] = []

        for f in model._meta.local_fields:
            fields_info.append(
                {
                    "name": f.name,
                    "type": type(f).__name__,
                    "column": f.column,
                }
            )

        for f in model._meta.local_many_to_many:
            fields_info.append(
                {
                    "name": f.name,
                    "type": "ManyToManyField",
                    "column": "",
                }
            )

        return fields_info

    def _python_files(self) -> list[Path]:
        """Collect all .py files under the project root, skipping venvs."""
        skip = {".venv", "venv", "node_modules", "__pycache__", ".git", "migrations"}
        result: list[Path] = []

        for py_file in self.project_root.rglob("*.py"):
            if any(part in skip for part in py_file.parts):
                continue
            result.append(py_file)

        return result


# ---------------------------------------------------------------------------
# Migration generator
# ---------------------------------------------------------------------------


class MigrationGenerator:
    """Generate Django migration files for model refactoring."""

    @staticmethod
    def move_model_source_migration(
        source_app: str,
        model_name: str,
        target_app: str,
        db_table: str,
    ) -> str:
        """Generate the source-app migration (state: delete, db: no-op)."""
        return textwrap.dedent(f"""\
            from django.db import migrations


            class Migration(migrations.Migration):

                dependencies = [
                    ("{source_app}", "__latest__"),
                    ("{target_app}", "__latest__"),
                ]

                # Remove the model from this app's state without touching the DB table.
                # The target app's migration creates the model in state and keeps the
                # same table (via db_table = "{db_table}").
                operations = [
                    migrations.SeparateDatabaseAndState(
                        state_operations=[
                            migrations.DeleteModel(
                                name="{model_name}",
                            ),
                        ],
                        database_operations=[],
                    ),
                ]
        """)

    @staticmethod
    def move_model_target_migration(
        source_app: str,
        target_app: str,
        model_name: str,
        db_table: str,
        model_source: str,
    ) -> str:
        """Generate the target-app migration (state: create, db: no-op)."""
        return textwrap.dedent(f"""\
            from django.db import migrations


            class Migration(migrations.Migration):

                dependencies = [
                    ("{source_app}", "__latest__"),
                    ("{target_app}", "__latest__"),
                ]

                # Create the model in this app's state. The table already exists as
                # "{db_table}" from the source app, so no DB operations needed.
                #
                # IMPORTANT: Replace the CreateModel below with the actual model
                # definition from makemigrations after copying the model class.
                # This placeholder shows the intent.
                operations = [
                    migrations.SeparateDatabaseAndState(
                        state_operations=[
                            migrations.CreateModel(
                                name="{model_name}",
                                fields=[],  # TODO: run makemigrations to populate
                                options={{
                                    "db_table": "{db_table}",
                                }},
                            ),
                        ],
                        database_operations=[],
                    ),
                ]
        """)

    @staticmethod
    def rename_model_migration(app_label: str, old_name: str, new_name: str) -> str:
        """Generate a RenameModel migration."""
        return textwrap.dedent(f"""\
            from django.db import migrations


            class Migration(migrations.Migration):

                dependencies = [
                    ("{app_label}", "__latest__"),
                ]

                operations = [
                    migrations.RenameModel(
                        old_name="{old_name}",
                        new_name="{new_name}",
                    ),
                    migrations.AlterModelOptions(
                        name="{new_name.lower()}",
                        options={{"db_table": "{app_label}_{old_name.lower()}"}},
                    ),
                ]
        """)

    @staticmethod
    def fk_update_migration(
        app_label: str,
        model_name: str,
        field_name: str,
        new_target: str,
    ) -> str:
        """Generate a state-only migration to update FK target."""
        return textwrap.dedent(f"""\
            from django.db import migrations, models
            import django.db.models.deletion


            class Migration(migrations.Migration):

                dependencies = [
                    ("{app_label}", "__latest__"),
                ]

                # State-only: update the FK reference from old app to new app.
                # The underlying column/constraint is unchanged.
                operations = [
                    migrations.SeparateDatabaseAndState(
                        state_operations=[
                            migrations.AlterField(
                                model_name="{model_name.lower()}",
                                name="{field_name}",
                                field=models.ForeignKey(
                                    to="{new_target}",
                                    on_delete=django.db.models.deletion.CASCADE,
                                ),
                            ),
                        ],
                        database_operations=[],
                    ),
                ]
        """)


# ---------------------------------------------------------------------------
# Command implementation
# ---------------------------------------------------------------------------


class Command(MattCommand):
    """Model refactoring utilities: move, rename, split, merge."""

    help = "Safely refactor Django models — move between apps, rename, split/merge apps"

    def add_arguments(self, parser: Any) -> None:
        super().add_arguments(parser)
        subparsers = parser.add_subparsers(dest="subcommand", help="Refactoring operations")

        # move-model
        move_parser = subparsers.add_parser(
            "move-model", help="Move a model from one app to another"
        )
        move_parser.add_argument("model", help="Source model (app_label.ModelName)")
        move_parser.add_argument("target_app", help="Target app label")
        move_parser.add_argument(
            "--dry-run", action="store_true", help="Show plan without applying"
        )
        move_parser.add_argument(
            "--yes", "-y", action="store_true", help="Skip confirmation prompt"
        )

        # rename-model
        rename_parser = subparsers.add_parser("rename-model", help="Rename a model within its app")
        rename_parser.add_argument("model", help="Current model (app_label.ModelName)")
        rename_parser.add_argument("new_name", help="New model path (app_label.NewName)")
        rename_parser.add_argument(
            "--dry-run", action="store_true", help="Show plan without applying"
        )
        rename_parser.add_argument(
            "--yes", "-y", action="store_true", help="Skip confirmation prompt"
        )

        # split-app
        split_parser = subparsers.add_parser("split-app", help="Extract models into a new app")
        split_parser.add_argument("source_app", help="Source app label")
        split_parser.add_argument(
            "--models", required=True, help="Comma-separated model names to extract"
        )
        split_parser.add_argument("--new-app", required=True, help="New app label")
        split_parser.add_argument(
            "--dry-run", action="store_true", help="Show plan without applying"
        )
        split_parser.add_argument(
            "--yes", "-y", action="store_true", help="Skip confirmation prompt"
        )

        # merge-apps
        merge_parser = subparsers.add_parser("merge-apps", help="Merge two apps into one")
        merge_parser.add_argument("apps", nargs="+", help="Apps to merge")
        merge_parser.add_argument("--into", required=True, help="Target app to merge into")
        merge_parser.add_argument(
            "--dry-run", action="store_true", help="Show plan without applying"
        )
        merge_parser.add_argument(
            "--yes", "-y", action="store_true", help="Skip confirmation prompt"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        subcommand = options.get("subcommand")

        if not subcommand:
            self.console.header("Model Refactoring")
            self.console.print("[bold]Usage:[/] python manage.py matt_refactor <command>")
            self.console.newline()
            self.console.command_group(
                "Commands",
                [
                    ("move-model", "Move a model from one app to another"),
                    ("rename-model", "Rename a model within its app"),
                    ("split-app", "Extract models into a new app"),
                    ("merge-apps", "Merge multiple apps into one"),
                ],
            )
            self.console.newline()
            self.console.muted("All commands support --dry-run to preview changes safely.")
            return

        handler_name = f"handle_{subcommand.replace('-', '_')}"
        handler = getattr(self, handler_name, None)
        if handler:
            handler(options)
        else:
            self.error(f"Unknown subcommand: {subcommand}")

    # =========================================================================
    # move-model
    # =========================================================================

    def handle_move_model(self, options: dict[str, Any]) -> None:
        model_path = options["model"]
        target_app = options["target_app"]
        dry_run = options.get("dry_run", False)
        skip_confirm = options.get("yes", False)

        # Parse model path
        app_label, model_name = self._parse_model_path(model_path)

        self.console.header(
            "Move Model",
            f"{app_label}.{model_name} -> {target_app}.{model_name}",
        )

        # Validate
        self._validate_model_exists(app_label, model_name)
        self._validate_app_exists(target_app)

        analyzer = RefactorAnalyzer()

        # Build plan
        self.console.section("Analyzing references")
        plan = RefactorPlan(description=f"Move {app_label}.{model_name} to {target_app}")

        plan.field_refs = analyzer.find_field_references(app_label, model_name)
        plan.import_refs = analyzer.find_import_references(app_label, model_name)
        plan.admin_refs = analyzer.find_admin_references(app_label, model_name)

        # Show analysis
        self._show_references(plan)

        # Get model info
        model_class = analyzer.get_model_class(app_label, model_name)
        db_table = model_class._meta.db_table
        model_source = analyzer.get_model_source(app_label, model_name)

        if not model_source:
            self.console.error(f"Could not extract model source from {app_label}/models.py")
            return

        # Plan file changes
        self.console.section("Planned changes")

        # 1. Migrations
        plan.migrations.append(
            {
                "app": app_label,
                "type": "source_delete_state",
                "description": f"Remove {model_name} from {app_label} state (keep table)",
            }
        )
        plan.migrations.append(
            {
                "app": target_app,
                "type": "target_create_state",
                "description": f"Create {model_name} in {target_app} state (no table change)",
            }
        )

        # 2. Code changes
        plan.file_changes.append(
            {
                "action": "copy",
                "description": f"Copy model class to {target_app}/models.py",
                "target": f"{target_app}/models.py",
            }
        )
        plan.file_changes.append(
            {
                "action": "remove",
                "description": f"Remove model class from {app_label}/models.py",
                "target": f"{app_label}/models.py",
            }
        )
        plan.file_changes.append(
            {
                "action": "modify",
                "description": f"Set db_table = '{db_table}' on moved model",
                "target": f"{target_app}/models.py",
            }
        )

        # 3. FK updates
        for ref in plan.field_refs:
            plan.file_changes.append(
                {
                    "action": "migration",
                    "description": (
                        f"Update {ref.app_label}.{ref.model_name}.{ref.field_name} "
                        f"to point to {target_app}.{model_name}"
                    ),
                    "target": f"{ref.app_label}/migrations/",
                }
            )

        # 4. Import updates
        for ref in plan.import_refs:
            plan.file_changes.append(
                {
                    "action": "rewrite_import",
                    "description": f"Update import in {ref.file_path.name}:{ref.line_number}",
                    "target": str(ref.file_path),
                }
            )

        self._show_plan(plan)

        # Warnings
        if plan.admin_refs:
            plan.warnings.append(
                f"Found {len(plan.admin_refs)} admin registration(s) that need manual update"
            )
        if plan.field_refs:
            plan.warnings.append(
                f"Found {len(plan.field_refs)} FK/M2M references — migrations will be generated"
            )

        self._show_warnings(plan)

        if dry_run:
            self.console.newline()
            self.console.box_warning(
                "Dry run complete. No changes were made.\nRun without --dry-run to apply changes.",
                title="Dry Run",
            )
            self._show_migration_preview(app_label, target_app, model_name, db_table, model_source)
            return

        # Confirm
        if not skip_confirm:
            self.console.newline()
            self.console.warning("Back up your project before proceeding (git commit recommended).")
            try:
                from django_matt.cli.prompts import confirm

                if not confirm("Apply changes?", default=False):
                    self.console.info("Aborted.")
                    return
            except (ImportError, EOFError, KeyboardInterrupt):
                self.console.info("Aborted.")
                return

        # Execute
        self._execute_move_model(
            analyzer, app_label, model_name, target_app, db_table, model_source, plan
        )

    def _execute_move_model(
        self,
        analyzer: RefactorAnalyzer,
        app_label: str,
        model_name: str,
        target_app: str,
        db_table: str,
        model_source: str,
        plan: RefactorPlan,
    ) -> None:
        self.console.section("Applying changes")

        target_config = apps.get_app_config(target_app)
        source_config = apps.get_app_config(app_label)

        # 1. Copy model to target app
        target_models = Path(target_config.path) / "models.py"

        # Add db_table to model's Meta if not present
        patched_source = self._add_db_table_to_model(model_source, db_table)

        if target_models.exists():
            existing = target_models.read_text()
            target_models.write_text(existing.rstrip() + "\n\n\n" + patched_source + "\n")
        else:
            target_models.write_text("from django.db import models\n\n\n" + patched_source + "\n")
        self.console.success(f"Copied {model_name} to {target_models}")

        # 2. Remove model from source app
        source_models = Path(source_config.path) / "models.py"
        if source_models.exists():
            self._remove_class_from_file(source_models, model_name)
            self.console.success(f"Removed {model_name} from {source_models}")

        # 3. Write migration files
        source_mig_dir = Path(source_config.path) / "migrations"
        target_mig_dir = Path(target_config.path) / "migrations"

        source_mig_dir.mkdir(parents=True, exist_ok=True)
        target_mig_dir.mkdir(parents=True, exist_ok=True)

        # Ensure __init__.py exists
        (source_mig_dir / "__init__.py").touch(exist_ok=True)
        (target_mig_dir / "__init__.py").touch(exist_ok=True)

        source_mig_name = self._next_migration_name(
            source_mig_dir, f"move_{model_name.lower()}_to_{target_app}"
        )
        target_mig_name = self._next_migration_name(
            target_mig_dir, f"receive_{model_name.lower()}_from_{app_label}"
        )

        source_mig_content = MigrationGenerator.move_model_source_migration(
            app_label, model_name, target_app, db_table
        )
        target_mig_content = MigrationGenerator.move_model_target_migration(
            app_label, target_app, model_name, db_table, model_source
        )

        (source_mig_dir / f"{source_mig_name}.py").write_text(source_mig_content)
        self.console.success(f"Created migration {source_mig_name} in {app_label}")

        (target_mig_dir / f"{target_mig_name}.py").write_text(target_mig_content)
        self.console.success(f"Created migration {target_mig_name} in {target_app}")

        # 4. Update imports
        for ref in plan.import_refs:
            self._rewrite_import(ref, app_label, target_app, model_name)

        # 5. Generate FK update migrations
        for ref in plan.field_refs:
            fk_mig_dir = Path(apps.get_app_config(ref.app_label).path) / "migrations"
            fk_mig_dir.mkdir(parents=True, exist_ok=True)
            (fk_mig_dir / "__init__.py").touch(exist_ok=True)

            fk_mig_name = self._next_migration_name(
                fk_mig_dir,
                f"update_{ref.field_name}_to_{target_app}_{model_name.lower()}",
            )
            fk_content = MigrationGenerator.fk_update_migration(
                ref.app_label,
                ref.model_name,
                ref.field_name,
                f"{target_app}.{model_name}",
            )
            (fk_mig_dir / f"{fk_mig_name}.py").write_text(fk_content)
            self.console.success(f"Created FK migration {fk_mig_name} in {ref.app_label}")

        self.console.newline()
        self.console.box_success(
            f"Moved {app_label}.{model_name} to {target_app}.{model_name}\n\n"
            f"Next steps:\n"
            f"  1. Review generated migrations (replace __latest__ with actual deps)\n"
            f"  2. Run: python manage.py makemigrations --check\n"
            f"  3. Run: python manage.py migrate\n"
            f"  4. Update any admin.py registrations manually\n"
            f"  5. Run your test suite"
        )

    # =========================================================================
    # rename-model
    # =========================================================================

    def handle_rename_model(self, options: dict[str, Any]) -> None:
        model_path = options["model"]
        new_path = options["new_name"]
        dry_run = options.get("dry_run", False)
        skip_confirm = options.get("yes", False)

        app_label, old_name = self._parse_model_path(model_path)
        new_app, new_name = self._parse_model_path(new_path)

        if app_label != new_app:
            self.console.error(
                f"App labels must match for rename. Got {app_label} and {new_app}.\n"
                "Use 'move-model' to move between apps."
            )
            return

        self.console.header("Rename Model", f"{app_label}.{old_name} -> {app_label}.{new_name}")

        self._validate_model_exists(app_label, old_name)

        analyzer = RefactorAnalyzer()

        self.console.section("Analyzing references")
        plan = RefactorPlan(description=f"Rename {app_label}.{old_name} to {app_label}.{new_name}")
        plan.field_refs = analyzer.find_field_references(app_label, old_name)
        plan.import_refs = analyzer.find_import_references(app_label, old_name)
        plan.admin_refs = analyzer.find_admin_references(app_label, old_name)

        self._show_references(plan)

        model_class = analyzer.get_model_class(app_label, old_name)
        db_table = model_class._meta.db_table

        # Plan
        plan.migrations.append(
            {
                "app": app_label,
                "type": "rename",
                "description": f"RenameModel {old_name} -> {new_name} (preserve db_table)",
            }
        )
        plan.file_changes.append(
            {
                "action": "rename_class",
                "description": f"Rename class {old_name} -> {new_name} in models.py",
                "target": f"{app_label}/models.py",
            }
        )
        plan.file_changes.append(
            {
                "action": "set_db_table",
                "description": f"Set db_table = '{db_table}' to preserve table name",
                "target": f"{app_label}/models.py",
            }
        )

        for ref in plan.import_refs:
            plan.file_changes.append(
                {
                    "action": "rewrite_import",
                    "description": f"Update import {old_name} -> {new_name} in {ref.file_path.name}",
                    "target": str(ref.file_path),
                }
            )

        self._show_plan(plan)
        self._show_warnings(plan)

        if dry_run:
            self.console.newline()
            self.console.box_warning("Dry run complete. No changes were made.", title="Dry Run")
            # Show migration preview
            self.console.section("Migration preview")
            self.console.code(
                MigrationGenerator.rename_model_migration(app_label, old_name, new_name),
                title=f"{app_label}/migrations/XXXX_rename_{old_name.lower()}.py",
            )
            return

        if not skip_confirm:
            self.console.newline()
            self.console.warning("Back up your project before proceeding.")
            try:
                from django_matt.cli.prompts import confirm

                if not confirm("Apply changes?", default=False):
                    self.console.info("Aborted.")
                    return
            except (ImportError, EOFError, KeyboardInterrupt):
                self.console.info("Aborted.")
                return

        self._execute_rename_model(analyzer, app_label, old_name, new_name, db_table, plan)

    def _execute_rename_model(
        self,
        analyzer: RefactorAnalyzer,
        app_label: str,
        old_name: str,
        new_name: str,
        db_table: str,
        plan: RefactorPlan,
    ) -> None:
        self.console.section("Applying changes")

        app_config = apps.get_app_config(app_label)

        # 1. Rename class in models.py
        models_file = Path(app_config.path) / "models.py"
        if models_file.exists():
            self._rename_class_in_file(models_file, old_name, new_name)
            # Add db_table
            source = models_file.read_text()
            if f'db_table = "{db_table}"' not in source:
                source = self._inject_db_table_into_class(source, new_name, db_table)
                models_file.write_text(source)
            self.console.success(f"Renamed {old_name} -> {new_name} in {models_file}")

        # 2. Write migration
        mig_dir = Path(app_config.path) / "migrations"
        mig_dir.mkdir(parents=True, exist_ok=True)
        (mig_dir / "__init__.py").touch(exist_ok=True)

        mig_name = self._next_migration_name(
            mig_dir, f"rename_{old_name.lower()}_to_{new_name.lower()}"
        )
        mig_content = MigrationGenerator.rename_model_migration(app_label, old_name, new_name)
        (mig_dir / f"{mig_name}.py").write_text(mig_content)
        self.console.success(f"Created migration {mig_name}")

        # 3. Update imports
        for ref in plan.import_refs:
            self._rewrite_import_name(ref, old_name, new_name)

        self.console.newline()
        self.console.box_success(
            f"Renamed {app_label}.{old_name} to {app_label}.{new_name}\n\n"
            f"Next steps:\n"
            f"  1. Review the migration (replace __latest__)\n"
            f"  2. Update admin registrations manually\n"
            f"  3. Run: python manage.py migrate\n"
            f"  4. Run your test suite"
        )

    # =========================================================================
    # split-app
    # =========================================================================

    def handle_split_app(self, options: dict[str, Any]) -> None:
        source_app = options["source_app"]
        model_names = [m.strip() for m in options["models"].split(",")]
        new_app = options["new_app"]
        dry_run = options.get("dry_run", False)
        skip_confirm = options.get("yes", False)

        self.console.header(
            "Split App",
            f"Extract {', '.join(model_names)} from {source_app} into {new_app}",
        )

        self._validate_app_exists(source_app)
        for name in model_names:
            self._validate_model_exists(source_app, name)

        # Check if target app already exists
        try:
            apps.get_app_config(new_app)
            app_exists = True
        except LookupError:
            app_exists = False

        self.console.section("Plan")
        plan_items: list[dict[str, str]] = []

        if not app_exists:
            plan_items.append({"Action": "create", "Description": f"Create new app '{new_app}'"})

        for name in model_names:
            plan_items.append(
                {
                    "Action": "move-model",
                    "Description": f"Move {source_app}.{name} -> {new_app}.{name}",
                }
            )

        plan_items.append(
            {
                "Action": "note",
                "Description": f"Add '{new_app}' to INSTALLED_APPS",
            }
        )

        self.console.table(plan_items)

        if dry_run:
            self.console.newline()
            self.console.box_warning(
                "Dry run complete. No changes were made.\n"
                "Each model move would generate SeparateDatabaseAndState migrations.",
                title="Dry Run",
            )
            return

        if not skip_confirm:
            self.console.newline()
            self.console.warning("Back up your project before proceeding.")
            try:
                from django_matt.cli.prompts import confirm

                if not confirm("Apply changes?", default=False):
                    self.console.info("Aborted.")
                    return
            except (ImportError, EOFError, KeyboardInterrupt):
                self.console.info("Aborted.")
                return

        # Execute
        self.console.section("Applying changes")

        # Create app if needed
        if not app_exists:
            self._create_app_skeleton(new_app)

        # Move each model
        analyzer = RefactorAnalyzer()
        for name in model_names:
            self.console.info(f"Moving {source_app}.{name} to {new_app}...")
            model_class = analyzer.get_model_class(source_app, name)
            db_table = model_class._meta.db_table
            model_source = analyzer.get_model_source(source_app, name)

            if not model_source:
                self.console.warning(f"Could not extract source for {name}, skipping")
                continue

            sub_plan = RefactorPlan(description=f"Move {name}")
            sub_plan.field_refs = analyzer.find_field_references(source_app, name)
            sub_plan.import_refs = analyzer.find_import_references(source_app, name)

            self._execute_move_model(
                analyzer, source_app, name, new_app, db_table, model_source, sub_plan
            )

        self.console.newline()
        self.console.box_success(
            f"Split {len(model_names)} model(s) from {source_app} into {new_app}\n\n"
            f"Next steps:\n"
            f"  1. Add '{new_app}' to INSTALLED_APPS in settings.py\n"
            f"  2. Review all generated migrations\n"
            f"  3. Run: python manage.py makemigrations --check\n"
            f"  4. Run: python manage.py migrate\n"
            f"  5. Run your test suite"
        )

    # =========================================================================
    # merge-apps
    # =========================================================================

    def handle_merge_apps(self, options: dict[str, Any]) -> None:
        source_apps = options["apps"]
        target_app = options["into"]
        dry_run = options.get("dry_run", False)
        skip_confirm = options.get("yes", False)

        self.console.header(
            "Merge Apps",
            f"Merge {', '.join(source_apps)} into {target_app}",
        )

        self._validate_app_exists(target_app)
        for app in source_apps:
            self._validate_app_exists(app)

        if target_app in source_apps:
            self.console.error("Target app cannot be one of the source apps.")
            return

        # Gather all models to move
        all_models: list[tuple[str, str]] = []
        for app in source_apps:
            app_config = apps.get_app_config(app)
            for model in app_config.get_models():
                all_models.append((app, model.__name__))

        self.console.section("Models to merge")
        model_table = [{"Source App": app, "Model": name} for app, name in all_models]
        self.console.table(model_table)
        self.console.info(f"Total: {len(all_models)} model(s) to move")

        if not all_models:
            self.console.warning("No models found in source apps.")
            return

        if dry_run:
            self.console.newline()
            self.console.box_warning(
                "Dry run complete. No changes were made.\n"
                "Each model would be moved with SeparateDatabaseAndState migrations.",
                title="Dry Run",
            )
            return

        if not skip_confirm:
            self.console.newline()
            self.console.warning("Back up your project before proceeding.")
            try:
                from django_matt.cli.prompts import confirm

                if not confirm("Apply changes?", default=False):
                    self.console.info("Aborted.")
                    return
            except (ImportError, EOFError, KeyboardInterrupt):
                self.console.info("Aborted.")
                return

        # Execute
        self.console.section("Applying changes")
        analyzer = RefactorAnalyzer()

        for app, name in all_models:
            self.console.info(f"Moving {app}.{name} to {target_app}...")
            model_class = analyzer.get_model_class(app, name)
            db_table = model_class._meta.db_table
            model_source = analyzer.get_model_source(app, name)

            if not model_source:
                self.console.warning(f"Could not extract source for {app}.{name}, skipping")
                continue

            sub_plan = RefactorPlan(description=f"Move {name}")
            sub_plan.field_refs = analyzer.find_field_references(app, name)
            sub_plan.import_refs = analyzer.find_import_references(app, name)

            self._execute_move_model(
                analyzer, app, name, target_app, db_table, model_source, sub_plan
            )

        self.console.newline()
        self.console.box_success(
            f"Merged {len(all_models)} model(s) into {target_app}\n\n"
            f"Next steps:\n"
            f"  1. Review all generated migrations\n"
            f"  2. Consolidate admin registrations in {target_app}/admin.py\n"
            f"  3. Run: python manage.py makemigrations --check\n"
            f"  4. Run: python manage.py migrate\n"
            f"  5. Remove source apps from INSTALLED_APPS after verifying\n"
            f"  6. Run your test suite"
        )

    # =========================================================================
    # Display helpers
    # =========================================================================

    def _show_references(self, plan: RefactorPlan) -> None:
        if plan.field_refs:
            self.console.section("Field references (FK/O2O/M2M)")
            field_table = [
                {
                    "Model": f"{r.app_label}.{r.model_name}",
                    "Field": r.field_name,
                    "Type": r.field_type,
                }
                for r in plan.field_refs
            ]
            self.console.table(field_table)
        else:
            self.console.info("No FK/O2O/M2M references found")

        if plan.import_refs:
            self.console.section("Import references")
            import_table = [
                {
                    "File": str(r.file_path.name),
                    "Line": str(r.line_number),
                    "Import": r.original_line.strip(),
                }
                for r in plan.import_refs
            ]
            self.console.table(import_table)
        else:
            self.console.info("No import references found")

        if plan.admin_refs:
            self.console.section("Admin registrations")
            admin_table = [
                {
                    "File": str(r.file_path.name),
                    "Line": str(r.line_number),
                }
                for r in plan.admin_refs
            ]
            self.console.table(admin_table)

    def _show_plan(self, plan: RefactorPlan) -> None:
        self.console.section("Changes to apply")

        if plan.migrations:
            mig_table = [
                {"App": m["app"], "Type": m["type"], "Description": m["description"]}
                for m in plan.migrations
            ]
            self.console.table(mig_table, title="Migrations")

        if plan.file_changes:
            change_table = [
                {"Action": c["action"], "Description": c["description"]} for c in plan.file_changes
            ]
            self.console.table(change_table, title="File changes")

    def _show_warnings(self, plan: RefactorPlan) -> None:
        if plan.warnings:
            self.console.newline()
            for w in plan.warnings:
                self.console.warning(w)

    def _show_migration_preview(
        self,
        source_app: str,
        target_app: str,
        model_name: str,
        db_table: str,
        model_source: str,
    ) -> None:
        self.console.section("Migration preview (source app)")
        self.console.code(
            MigrationGenerator.move_model_source_migration(
                source_app, model_name, target_app, db_table
            ),
            title=f"{source_app}/migrations/XXXX_move_{model_name.lower()}.py",
        )

        self.console.section("Migration preview (target app)")
        self.console.code(
            MigrationGenerator.move_model_target_migration(
                source_app, target_app, model_name, db_table, model_source
            ),
            title=f"{target_app}/migrations/XXXX_receive_{model_name.lower()}.py",
        )

    # =========================================================================
    # Validation helpers
    # =========================================================================

    def _parse_model_path(self, path: str) -> tuple[str, str]:
        parts = path.split(".")
        if len(parts) != 2:
            self.console.error(f"Invalid model path '{path}'. Expected format: app_label.ModelName")
            raise SystemExit(1)
        return parts[0], parts[1]

    def _validate_model_exists(self, app_label: str, model_name: str) -> None:
        try:
            apps.get_model(app_label, model_name)
        except LookupError:
            available = [f"{m._meta.app_label}.{m.__name__}" for m in apps.get_models()]
            self.fail_model_not_found(f"{app_label}.{model_name}", available)

    def _validate_app_exists(self, app_label: str) -> None:
        try:
            apps.get_app_config(app_label)
        except LookupError:
            available = [c.label for c in apps.get_app_configs()]
            self.fail_invalid_argument("app", f"App '{app_label}' not found", available)

    # =========================================================================
    # File manipulation helpers
    # =========================================================================

    def _add_db_table_to_model(self, source: str, db_table: str) -> str:
        """Add db_table to a model's Meta class, or create Meta if missing."""
        if f'db_table = "{db_table}"' in source:
            return source

        lines = source.splitlines(keepends=True)

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Meta":
                # Insert db_table at start of Meta body
                insert_line = node.body[0].lineno - 1
                indent = "        "
                lines.insert(insert_line, f'{indent}db_table = "{db_table}"\n')
                return "".join(lines)

        # No Meta class found — add one
        # Find the class body end and add Meta before it
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Add Meta after the class definition line
                body_start = node.body[0].lineno - 1
                indent = "    "
                meta_block = f'\n{indent}class Meta:\n{indent}    db_table = "{db_table}"\n\n'
                lines.insert(body_start, meta_block)
                return "".join(lines)

        return source

    def _remove_class_from_file(self, file_path: Path, class_name: str) -> None:
        """Remove a class definition from a Python file using AST."""
        source = file_path.read_text()

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        lines = source.splitlines(keepends=True)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                start = node.lineno - 1
                end = node.end_lineno if node.end_lineno else start + 1

                # Also remove any decorators above the class
                if node.decorator_list:
                    start = node.decorator_list[0].lineno - 1

                # Remove blank lines before the class (up to 2)
                while start > 0 and lines[start - 1].strip() == "":
                    start -= 1

                del lines[start:end]
                break

        file_path.write_text("".join(lines))

    def _rename_class_in_file(self, file_path: Path, old_name: str, new_name: str) -> None:
        """Rename a class and all references to it within a single file."""
        source = file_path.read_text()
        # Simple text replacement — class name as whole word
        import re

        new_source = re.sub(rf"\b{old_name}\b", new_name, source)
        file_path.write_text(new_source)

    def _inject_db_table_into_class(self, source: str, class_name: str, db_table: str) -> str:
        """Inject db_table into a class's Meta after renaming."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        lines = source.splitlines(keepends=True)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # Look for Meta inside this class
                for child in node.body:
                    if isinstance(child, ast.ClassDef) and child.name == "Meta":
                        insert_line = child.body[0].lineno - 1
                        indent = "        "
                        lines.insert(insert_line, f'{indent}db_table = "{db_table}"\n')
                        return "".join(lines)

                # No Meta — add one after class definition
                body_start = node.body[0].lineno - 1
                indent = "    "
                meta_block = f'\n{indent}class Meta:\n{indent}    db_table = "{db_table}"\n\n'
                lines.insert(body_start, meta_block)
                return "".join(lines)

        return source

    def _rewrite_import(
        self,
        ref: ImportReference,
        old_app: str,
        new_app: str,
        model_name: str,
    ) -> None:
        """Rewrite an import statement to point to the new app."""
        if not ref.file_path.exists():
            return

        source = ref.file_path.read_text()
        old_import = ref.original_line.strip()

        # Replace the app portion in the module path
        new_module = ref.module_path.replace(old_app, new_app, 1)
        new_import = old_import.replace(ref.module_path, new_module)

        if old_import != new_import:
            source = source.replace(old_import, new_import, 1)
            ref.file_path.write_text(source)
            self.console.success(f"Updated import in {ref.file_path.name}:{ref.line_number}")

    def _rewrite_import_name(self, ref: ImportReference, old_name: str, new_name: str) -> None:
        """Rewrite an import to use a new model name."""
        if not ref.file_path.exists():
            return

        source = ref.file_path.read_text()
        import re

        new_source = re.sub(rf"\b{old_name}\b", new_name, source)
        if source != new_source:
            ref.file_path.write_text(new_source)
            self.console.success(f"Updated references in {ref.file_path.name}")

    def _next_migration_name(self, mig_dir: Path, description: str) -> str:
        """Generate the next migration filename like 0003_description."""
        existing = sorted(
            f.stem for f in mig_dir.glob("*.py") if f.stem != "__init__" and f.stem[0].isdigit()
        )

        if existing:
            last = existing[-1]
            try:
                num = int(last.split("_")[0]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1

        return f"{num:04d}_{description}"

    def _create_app_skeleton(self, app_label: str) -> None:
        """Create a minimal Django app directory."""
        base_dir = Path(settings.BASE_DIR)
        app_dir = base_dir / app_label

        app_dir.mkdir(parents=True, exist_ok=True)

        # __init__.py
        (app_dir / "__init__.py").touch(exist_ok=True)

        # apps.py
        class_name = app_label.replace("_", " ").title().replace(" ", "")
        (app_dir / "apps.py").write_text(
            f"from django.apps import AppConfig\n\n\n"
            f"class {class_name}Config(AppConfig):\n"
            f'    default_auto_field = "django.db.models.BigAutoField"\n'
            f'    name = "{app_label}"\n'
        )

        # models.py
        (app_dir / "models.py").write_text("from django.db import models\n")

        # admin.py
        (app_dir / "admin.py").write_text("from django.contrib import admin\n")

        # migrations/
        mig_dir = app_dir / "migrations"
        mig_dir.mkdir(parents=True, exist_ok=True)
        (mig_dir / "__init__.py").touch(exist_ok=True)

        self.console.success(f"Created app skeleton: {app_dir}")
