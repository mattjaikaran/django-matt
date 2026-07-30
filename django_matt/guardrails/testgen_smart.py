"""
Smart test generation — integrates ``SchemaTestGenerator`` with the
``testing/smart`` dependency tracker for affected-test re-run capability.

``SmartTestGenerator`` extends ``SchemaTestGenerator`` and registers
every generated test with the ``TestDependencyTracker`` so that subsequent
``pytest --matt-affected`` runs can automatically discover and re-run
only the tests whose source schema has changed.

Usage::

    from django_matt.guardrails.testgen_smart import SmartTestGenerator
    from myapp.schemas import UserCreateSchema

    gen = SmartTestGenerator(UserCreateSchema)
    gen.generate_test_file(Path("tests/test_user_create_schema.py"))

    # Committed generated test files are tracked automatically.
    # When UserCreateSchema changes, pytest --matt-affected re-runs them.
"""

from __future__ import annotations

import ast
from pathlib import Path

from pydantic import BaseModel

from django_matt.guardrails.testgen import SchemaTestGenerator
from django_matt.testing.smart.tracker import TestDependencyTracker
from django_matt.testing.smart.db import DEFAULT_DB_PATH


class SmartTestGenerator(SchemaTestGenerator):
    """Same as ``SchemaTestGenerator``, but registers output with the
    smart-testing dependency tracker.

    Each generated test file is recorded so that ``pytest --matt-affected``
    re-runs it when the source schema changes.
    """

    def __init__(
        self,
        schema_class: type[BaseModel],
        tracker: TestDependencyTracker | None = None,
        db_path: Path | None = None,
    ) -> None:
        super().__init__(schema_class)
        if tracker is not None:
            self._tracker = tracker
        else:
            self._tracker = TestDependencyTracker(
                db_path=db_path if db_path is not None else DEFAULT_DB_PATH
            )

    @property
    def tracker(self) -> TestDependencyTracker:
        """The ``TestDependencyTracker`` used for smart re-run."""
        return self._tracker

    def generate_test_file(
        self,
        output_path: Path,
        *,
        register: bool = True,
    ) -> Path:
        """Write tests and optionally register with the tracker.

        Args:
            output_path: Where to write the pytest module.
            register: If ``True`` (default), register generated tests with
                      the ``TestDependencyTracker``.
        """
        path = super().generate_test_file(output_path)

        if register:
            self.register_with_tracker(output_path)

        return path

    def register_with_tracker(self, test_file: Path) -> None:
        """Register the generated test file's test IDs with the tracker.

        Parses the generated file to discover test function names and
        records coverage stubs so the tracker knows these tests depend
        on the schema's source module.
        """
        schema_module_path = self._resolve_schema_source_path()
        test_ids = self._discover_test_ids(test_file)

        if not test_ids or schema_module_path is None:
            return

        # Build synthetic coverage: every test touches the schema source
        # We approximate by marking the entire schema file as covered.
        try:
            lines = schema_module_path.read_text(encoding="utf-8").splitlines()
            line_set = set(range(1, len(lines) + 1))
        except (OSError, UnicodeDecodeError):
            return

        coverage_data: dict[str, set[int]] = {
            str(schema_module_path): line_set
        }

        for test_id in test_ids:
            self._tracker.record_test_coverage(test_id, coverage_data)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_schema_source_path(self) -> Path | None:
        """Try to resolve the schema class's source file to a Path."""
        module_name = self.schema_class.__module__
        if not module_name or module_name == "builtins":
            return None

        # Best effort: use __file__ from the module
        import importlib

        try:
            mod = importlib.import_module(module_name)
            file_attr = getattr(mod, "__file__", None)
            if file_attr:
                return Path(file_attr)
        except (ImportError, ValueError):
            pass

        return None

    def _discover_test_ids(self, test_file: Path) -> list[str]:
        """Parse *test_file* and extract pytest node IDs.

        Returns IDs like ``tests/test_user_schema.py::TestUserSchemaValidation::test_name_empty``.
        """
        try:
            source = test_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        test_ids: list[str] = []
        rel_path = str(test_file)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and (
                node.name.startswith("Test") or "Test" in node.name
            ):
                class_name = node.name
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith(
                        "test_"
                    ):
                        test_ids.append(
                            f"{rel_path}::{class_name}::{item.name}"
                        )

        return test_ids


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------


def generate_smart_tests(
    schema_class: type[BaseModel],
    output_path: Path,
    *,
    db_path: Path | None = None,
) -> Path:
    """Generate tests and register them with the smart-tracking DB.

    Args:
        schema_class: The Pydantic schema to generate tests for.
        output_path: Where to write the generated pytest module.
        db_path: Path to the smart-tracking DB (default: ``.matttest.db``).

    Returns:
        The *output_path*.
    """
    gen = SmartTestGenerator(schema_class, db_path=db_path)
    return gen.generate_test_file(output_path)
