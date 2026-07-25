"""
Tests for django_matt.testing.smart — affected test detection and failed-only re-runs.

Covers:
- ASTBlockDiffer: block extraction, change detection, comment immunity
- TestDependencyTracker: recording, querying, failure tracking
- DB schema: creation, reset, migrations
- Plugin: flag registration, test filtering
"""

from __future__ import annotations

import textwrap

import pytest

# =====================================================================
# ASTBlockDiffer tests
# =====================================================================


class TestASTBlockDiffer:
    """Test AST-level block extraction and diffing."""

    def setup_method(self):
        from django_matt.testing.smart.differ import ASTBlockDiffer

        self.differ = ASTBlockDiffer()

    def test_extract_function(self):
        source = textwrap.dedent("""\
            def hello():
                return "world"
        """)
        blocks = self.differ.extract_blocks(source)
        funcs = [b for b in blocks if b.block_type == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "hello"
        assert funcs[0].start_line == 1
        assert funcs[0].end_line == 2

    def test_extract_class_and_methods(self):
        source = textwrap.dedent("""\
            class MyClass:
                def method_a(self):
                    pass

                def method_b(self):
                    return 42
        """)
        blocks = self.differ.extract_blocks(source)
        classes = [b for b in blocks if b.block_type == "class"]
        methods = [b for b in blocks if b.block_type == "method"]
        assert len(classes) == 1
        assert classes[0].name == "MyClass"
        assert len(methods) == 2
        assert {m.name for m in methods} == {"MyClass.method_a", "MyClass.method_b"}

    def test_extract_async_function(self):
        source = textwrap.dedent("""\
            async def fetch_data():
                return await get()
        """)
        blocks = self.differ.extract_blocks(source)
        funcs = [b for b in blocks if b.block_type == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "fetch_data"

    def test_extract_imports_as_statements(self):
        source = textwrap.dedent("""\
            import os
            from pathlib import Path

            x = 42
        """)
        blocks = self.differ.extract_blocks(source)
        stmts = [b for b in blocks if b.block_type == "statement"]
        assert len(stmts) == 3
        names = {s.name for s in stmts}
        assert "import:os" in names
        assert "from:pathlib" in names
        assert "assign:x" in names

    def test_comment_change_no_diff(self):
        """A comment-only change should NOT produce a diff."""
        old = textwrap.dedent("""\
            def greet(name):
                # say hello
                return f"hi {name}"
        """)
        new = textwrap.dedent("""\
            def greet(name):
                # say goodbye  (changed comment)
                return f"hi {name}"
        """)
        changes = self.differ.changed_blocks(old, new)
        assert len(changes) == 0

    def test_whitespace_change_no_diff(self):
        """Pure whitespace changes should NOT produce a diff."""
        old = textwrap.dedent("""\
            def greet(name):
                return f"hi {name}"
        """)
        new = textwrap.dedent("""\
            def greet(name):

                return f"hi {name}"
        """)
        changes = self.differ.changed_blocks(old, new)
        assert len(changes) == 0

    def test_body_change_detected(self):
        old = textwrap.dedent("""\
            def calc(x):
                return x + 1
        """)
        new = textwrap.dedent("""\
            def calc(x):
                return x + 2
        """)
        changes = self.differ.changed_blocks(old, new)
        assert len(changes) == 1
        assert changes[0].change_type == "modified"
        assert changes[0].name == "calc"

    def test_added_function_detected(self):
        old = textwrap.dedent("""\
            def existing():
                pass
        """)
        new = textwrap.dedent("""\
            def existing():
                pass

            def new_func():
                return True
        """)
        changes = self.differ.changed_blocks(old, new)
        added = [c for c in changes if c.change_type == "added"]
        assert len(added) == 1
        assert added[0].name == "new_func"

    def test_removed_function_detected(self):
        old = textwrap.dedent("""\
            def keep():
                pass

            def remove_me():
                return False
        """)
        new = textwrap.dedent("""\
            def keep():
                pass
        """)
        changes = self.differ.changed_blocks(old, new)
        removed = [c for c in changes if c.change_type == "removed"]
        assert len(removed) == 1
        assert removed[0].name == "remove_me"

    def test_function_moved_no_diff(self):
        """If a function moves lines but content stays the same, no diff."""
        old = textwrap.dedent("""\
            def a():
                return 1

            def b():
                return 2
        """)
        new = textwrap.dedent("""\
            def b():
                return 2

            def a():
                return 1
        """)
        changes = self.differ.changed_blocks(old, new)
        assert len(changes) == 0

    def test_syntax_error_falls_back(self):
        """Unparseable source is treated as a single block."""
        source = "def broken(:\n    pass"
        blocks = self.differ.extract_blocks(source)
        assert len(blocks) == 1
        assert blocks[0].block_type == "unparseable"

    def test_file_has_changes(self):
        old = "x = 1"
        new = "x = 2"
        assert self.differ.file_has_changes(old, new) is True
        assert self.differ.file_has_changes(old, old) is False

    def test_method_change_detected(self):
        old = textwrap.dedent("""\
            class Service:
                def process(self):
                    return "v1"

                def validate(self):
                    return True
        """)
        new = textwrap.dedent("""\
            class Service:
                def process(self):
                    return "v2"

                def validate(self):
                    return True
        """)
        changes = self.differ.changed_blocks(old, new)
        # Both the class (whole content changed) and the method should appear
        modified = [c for c in changes if c.change_type == "modified"]
        names = {c.name for c in modified}
        assert "Service.process" in names

    def test_augmented_assign_named(self):
        source = "counter += 1"
        blocks = self.differ.extract_blocks(source)
        stmts = [b for b in blocks if b.block_type == "statement"]
        assert any("counter" in s.name for s in stmts)

    def test_annotated_assign_named(self):
        source = "value: int = 42"
        blocks = self.differ.extract_blocks(source)
        stmts = [b for b in blocks if b.block_type == "statement"]
        assert any("value" in s.name for s in stmts)


# =====================================================================
# DB module tests
# =====================================================================


class TestDB:
    """Test SQLite schema and connection management."""

    def test_connect_and_schema(self, tmp_path):
        from django_matt.testing.smart.db import connect, ensure_schema

        db = connect(tmp_path / "test.db")
        ensure_schema(db)

        # Verify tables exist
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "source_blocks" in tables
        assert "test_deps" in tables
        assert "failures" in tables
        assert "run_meta" in tables
        assert "meta" in tables

        # Verify schema version
        row = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        assert row is not None
        assert int(row["value"]) == 1
        db.close()

    def test_reset_clears_all_data(self, tmp_path):
        from django_matt.testing.smart.db import connect, ensure_schema, reset

        db = connect(tmp_path / "test.db")
        ensure_schema(db)

        # Insert some data
        db.execute("INSERT INTO failures (test_id, exc_repr) VALUES ('test_a', 'err')")
        db.commit()
        assert db.execute("SELECT COUNT(*) FROM failures").fetchone()[0] == 1

        reset(db)
        assert db.execute("SELECT COUNT(*) FROM failures").fetchone()[0] == 0
        db.close()

    def test_wal_mode(self, tmp_path):
        from django_matt.testing.smart.db import connect

        db = connect(tmp_path / "test.db")
        mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        db.close()

    def test_foreign_keys_enabled(self, tmp_path):
        from django_matt.testing.smart.db import connect

        db = connect(tmp_path / "test.db")
        fk = db.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        db.close()

    def test_idempotent_schema_creation(self, tmp_path):
        from django_matt.testing.smart.db import connect, ensure_schema

        db = connect(tmp_path / "test.db")
        ensure_schema(db)
        ensure_schema(db)  # should not raise
        db.close()


# =====================================================================
# TestDependencyTracker tests
# =====================================================================


class TestDependencyTracker:
    """Test the dependency tracker recording and querying."""

    def setup_method(self, tmp_path=None):
        pass

    def _make_tracker(self, tmp_path):
        from django_matt.testing.smart.tracker import TestDependencyTracker

        return TestDependencyTracker(tmp_path / "test.db")

    def test_record_and_query_coverage(self, tmp_path):
        """Record coverage for a test, then query affected tests."""
        tracker = self._make_tracker(tmp_path)

        # Create a source file to track
        src = tmp_path / "module.py"
        src.write_text(
            textwrap.dedent("""\
            def func_a():
                return 1

            def func_b():
                return 2
        """)
        )

        # Record that test_x covers func_a (lines 1-2)
        tracker.record_test_coverage(
            "tests/test_mod.py::test_x",
            {str(src): {1, 2}},
        )

        assert tracker.has_data()

        # Modify func_a
        src.write_text(
            textwrap.dedent("""\
            def func_a():
                return 99

            def func_b():
                return 2
        """)
        )

        affected = tracker.get_affected_tests(changed_files=[src])
        assert "tests/test_mod.py::test_x" in affected
        tracker.close()

    def test_no_data_returns_empty(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        assert not tracker.has_data()
        assert tracker.get_affected_tests(changed_files=[]) == []
        tracker.close()

    def test_failure_tracking(self, tmp_path):
        tracker = self._make_tracker(tmp_path)

        tracker.record_failure("test_a", "AssertionError: 1 != 2")
        tracker.record_failure("test_b", "TypeError: ...")

        failed = tracker.get_failed_tests()
        assert len(failed) == 2
        assert "test_a" in failed
        assert "test_b" in failed

        # Pass clears failure
        tracker.record_pass("test_a")
        failed = tracker.get_failed_tests()
        assert failed == ["test_b"]

        tracker.close()

    def test_clear_failures(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.record_failure("test_a", "err")
        tracker.clear_failures()
        assert tracker.get_failed_tests() == []
        tracker.close()

    def test_failure_details(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.record_failure("test_a", "AssertionError")
        details = tracker.get_failure_details()
        assert len(details) == 1
        assert details[0]["test_id"] == "test_a"
        assert details[0]["exc_repr"] == "AssertionError"
        assert "timestamp" in details[0]
        tracker.close()

    def test_rebuild_clears_all(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.record_failure("test_a", "err")
        tracker.rebuild()
        assert tracker.get_failed_tests() == []
        assert not tracker.has_data()
        tracker.close()

    def test_record_run_metadata(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.record_run("run1", "abc123", 100, 95, 5)

        row = tracker.conn.execute("SELECT * FROM run_meta WHERE run_id = 'run1'").fetchone()
        assert row is not None
        assert row["total_tests"] == 100
        assert row["passed"] == 95
        assert row["failed"] == 5
        assert row["commit_sha"] == "abc123"
        tracker.close()

    def test_invalidate_file(self, tmp_path):
        tracker = self._make_tracker(tmp_path)

        src = tmp_path / "module.py"
        src.write_text("def f(): pass")
        tracker.record_test_coverage("test_x", {str(src): {1}})

        # Verify data exists
        count = tracker.conn.execute(
            "SELECT COUNT(*) FROM source_blocks WHERE file = ?",
            (str(src),),
        ).fetchone()[0]
        assert count > 0

        tracker.invalidate_file(src)

        count = tracker.conn.execute(
            "SELECT COUNT(*) FROM source_blocks WHERE file = ?",
            (str(src),),
        ).fetchone()[0]
        assert count == 0
        tracker.close()

    def test_settings_file_invalidates_all(self, tmp_path):
        """Changes to settings.py should mark all tests as affected."""
        tracker = self._make_tracker(tmp_path)

        src = tmp_path / "module.py"
        src.write_text("def f(): return 1")
        tracker.record_test_coverage("test_x", {str(src): {1}})

        settings = tmp_path / "settings.py"
        settings.write_text("DEBUG = True")

        affected = tracker.get_affected_tests(changed_files=[settings])
        assert "test_x" in affected
        tracker.close()

    def test_deleted_file_affects_dependents(self, tmp_path):
        """If a tracked file is deleted, all its dependents are affected."""
        tracker = self._make_tracker(tmp_path)

        src = tmp_path / "module.py"
        src.write_text("def f(): return 1")
        tracker.record_test_coverage("test_x", {str(src): {1}})

        # Delete the file
        src.unlink()

        affected = tracker.get_affected_tests(changed_files=[src])
        assert "test_x" in affected
        tracker.close()

    def test_conftest_invalidates_all(self, tmp_path):
        tracker = self._make_tracker(tmp_path)

        src = tmp_path / "module.py"
        src.write_text("def f(): return 1")
        tracker.record_test_coverage("test_x", {str(src): {1}})

        conftest = tmp_path / "conftest.py"
        conftest.write_text("# config")

        affected = tracker.get_affected_tests(changed_files=[conftest])
        assert "test_x" in affected
        tracker.close()


# =====================================================================
# Plugin tests (unit-level, no pytest subprocess)
# =====================================================================


class TestPluginOptions:
    """Test that plugin CLI options are defined correctly."""

    def test_options_defined(self):
        from django_matt.testing.smart.plugin import pytest_addoption

        class FakeGroup:
            def addoption(self, *args, **kwargs):
                self.options = getattr(self, "options", [])
                self.options.append(args[0])

        class FakeParser:
            def __init__(self):
                self._group = FakeGroup()

            def getgroup(self, name, desc=""):
                return self._group

        parser = FakeParser()
        pytest_addoption(parser)

        opts = parser._group.options
        assert "--matt-affected" in opts
        assert "--matt-failed" in opts
        assert "--matt-rebuild-deps" in opts
        assert "--matt-clear-failures" in opts
        assert "--matt-changed" in opts
        assert "--matt-db" in opts

    def test_configure_noop_without_flags(self):
        """Plugin should not register when no matt flags are set."""
        from django_matt.testing.smart.plugin import pytest_configure

        class FakeConfig:
            def getoption(self, name, default=None):
                return default

            class pluginmanager:
                registered = []

                @classmethod
                def register(cls, plugin, name):
                    cls.registered.append(name)

        config = FakeConfig()
        FakeConfig.pluginmanager.registered.clear()
        pytest_configure(config)
        assert "matt-smart" not in FakeConfig.pluginmanager.registered


# =====================================================================
# Integration-level: differ + tracker working together
# =====================================================================


class TestIntegration:
    """End-to-end tests combining differ and tracker."""

    def test_comment_change_no_affected_tests(self, tmp_path):
        """Adding a comment should not trigger any test re-runs."""
        from django_matt.testing.smart.tracker import TestDependencyTracker

        tracker = TestDependencyTracker(tmp_path / "test.db")

        src = tmp_path / "service.py"
        src.write_text(
            textwrap.dedent("""\
            def process(data):
                result = transform(data)
                return result
        """)
        )

        tracker.record_test_coverage("test_process", {str(src): {1, 2, 3}})

        # Add a comment — should NOT invalidate
        src.write_text(
            textwrap.dedent("""\
            def process(data):
                # important transformation step
                result = transform(data)
                return result
        """)
        )

        affected = tracker.get_affected_tests(changed_files=[src])
        assert affected == []
        tracker.close()

    def test_multiple_files_multiple_tests(self, tmp_path):
        """Track dependencies across multiple files and tests."""
        from django_matt.testing.smart.tracker import TestDependencyTracker

        tracker = TestDependencyTracker(tmp_path / "test.db")

        src_a = tmp_path / "module_a.py"
        src_a.write_text(
            textwrap.dedent("""\
            def func_a():
                return 1
        """)
        )

        src_b = tmp_path / "module_b.py"
        src_b.write_text(
            textwrap.dedent("""\
            def func_b():
                return 2
        """)
        )

        # test_1 uses module_a, test_2 uses module_b, test_3 uses both
        tracker.record_test_coverage("test_1", {str(src_a): {1, 2}})
        tracker.record_test_coverage("test_2", {str(src_b): {1, 2}})
        tracker.record_test_coverage("test_3", {str(src_a): {1, 2}, str(src_b): {1, 2}})

        # Change module_a only
        src_a.write_text(
            textwrap.dedent("""\
            def func_a():
                return 99
        """)
        )

        affected = tracker.get_affected_tests(changed_files=[src_a])
        assert "test_1" in affected
        assert "test_3" in affected
        assert "test_2" not in affected
        tracker.close()

    def test_new_function_affects_file_tests(self, tmp_path):
        """Adding a new function conservatively marks all file-level tests."""
        from django_matt.testing.smart.tracker import TestDependencyTracker

        tracker = TestDependencyTracker(tmp_path / "test.db")

        src = tmp_path / "module.py"
        src.write_text(
            textwrap.dedent("""\
            def existing():
                return 1
        """)
        )

        tracker.record_test_coverage("test_existing", {str(src): {1, 2}})

        # Add a brand new function
        src.write_text(
            textwrap.dedent("""\
            def existing():
                return 1

            def brand_new():
                return 2
        """)
        )

        affected = tracker.get_affected_tests(changed_files=[src])
        # Conservative: existing tests for this file should be marked
        assert "test_existing" in affected
        tracker.close()
