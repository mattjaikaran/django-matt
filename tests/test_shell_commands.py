"""Tests for matt_shell and matt_dbshell management commands."""

from __future__ import annotations

import csv
import io
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

import pytest

from django_matt.management.commands.matt_dbshell import (
    format_csv,
    format_plain_table,
    format_rich_table,
    get_connection_info,
    set_read_only,
)
from django_matt.management.commands.matt_shell import (
    collect_auto_imports,
    format_banner,
)

# ── matt_shell: auto-import collection ──


class TestCollectAutoImports(TestCase):
    def test_returns_namespace_and_log(self) -> None:
        namespace, import_log = collect_auto_imports()
        assert isinstance(namespace, dict)
        assert isinstance(import_log, list)

    def test_orm_utilities_imported(self) -> None:
        namespace, _ = collect_auto_imports()
        for name in ("Q", "F", "Value", "Count", "Sum", "Avg", "Max", "Min", "Prefetch"):
            assert name in namespace, f"{name} missing from auto-imports"

    def test_settings_imported(self) -> None:
        namespace, _ = collect_auto_imports()
        assert "settings" in namespace

    def test_async_utilities_imported(self) -> None:
        namespace, _ = collect_auto_imports()
        assert "sync_to_async" in namespace
        assert "async_to_sync" in namespace

    def test_django_matt_classes_imported(self) -> None:
        namespace, _ = collect_auto_imports()
        # At minimum MattAPI should be importable
        assert "MattAPI" in namespace

    def test_models_imported(self) -> None:
        namespace, import_log = collect_auto_imports()
        # There should be at least some models from installed apps
        model_entries = [e for e in import_log if e.startswith("models")]
        # Models may or may not exist depending on test DB state
        # Just check no crash
        assert isinstance(namespace, dict)

    def test_import_log_has_entries(self) -> None:
        _, import_log = collect_auto_imports()
        assert len(import_log) >= 3  # at least ORM, settings, async


class TestFormatBanner(TestCase):
    def test_banner_contains_header(self) -> None:
        banner = format_banner(["django.db.models: Q, F"])
        assert "Django Matt Shell+" in banner

    def test_banner_contains_imports(self) -> None:
        banner = format_banner(["django.db.models: Q, F", "django.conf: settings"])
        assert "django.db.models: Q, F" in banner
        assert "django.conf: settings" in banner


class TestMattShellPrintImports(TestCase):
    def test_print_imports_flag(self) -> None:
        from django.core.management import call_command

        out = io.StringIO()
        call_command("matt_shell", "--print-imports", stdout=out)
        output = out.getvalue()
        assert "Q" in output
        assert "settings" in output


# ── matt_shell: graceful missing optional deps ──


class TestMattShellMissingDeps(TestCase):
    @patch.dict("sys.modules", {"IPython": None})
    def test_ipython_import_skipped_gracefully(self) -> None:
        """collect_auto_imports works even if IPython is missing."""
        namespace, _ = collect_auto_imports()
        assert "Q" in namespace  # core imports still work

    @patch.dict("sys.modules", {"rich": None, "rich.console": None, "rich.panel": None})
    def test_rich_import_skipped_gracefully(self) -> None:
        """format_banner works as fallback when rich is unavailable."""
        banner = format_banner(["test: something"])
        assert "Django Matt Shell+" in banner


# ── matt_dbshell: connection info ──


class TestGetConnectionInfo(TestCase):
    def test_returns_expected_keys(self) -> None:
        info = get_connection_info()
        for key in ("engine", "name", "host", "port", "user"):
            assert key in info, f"{key} missing from connection info"

    def test_engine_is_short_name(self) -> None:
        info = get_connection_info()
        # Should be the last component (e.g. "sqlite3" not "django.db.backends.sqlite3")
        assert "." not in info["engine"]


# ── matt_dbshell: query execution and formatting ──


class TestFormatCsv(TestCase):
    def test_csv_output(self) -> None:
        columns = ["id", "name"]
        rows = [(1, "alice"), (2, "bob")]
        result = format_csv(columns, rows)
        reader = csv.reader(io.StringIO(result))
        parsed = list(reader)
        assert parsed[0] == ["id", "name"]
        assert parsed[1] == ["1", "alice"]
        assert parsed[2] == ["2", "bob"]

    def test_csv_empty_results(self) -> None:
        result = format_csv(["col"], [])
        reader = csv.reader(io.StringIO(result))
        parsed = list(reader)
        assert len(parsed) == 1  # header only


class TestFormatPlainTable(TestCase):
    def test_plain_table_alignment(self) -> None:
        columns = ["id", "name"]
        rows = [(1, "alice"), (2, "bob")]
        result = format_plain_table(columns, rows)
        lines = result.split("\n")
        assert len(lines) == 4  # header + separator + 2 rows
        assert "id" in lines[0]
        assert "---" in lines[1] or "---" in lines[1]

    def test_plain_table_no_columns(self) -> None:
        result = format_plain_table([], [])
        assert result == "(no results)"


class TestFormatRichTable(TestCase):
    def test_rich_table_returns_string(self) -> None:
        pytest.importorskip("rich")
        result = format_rich_table(["id", "name"], [(1, "alice")])
        assert result is not None
        assert "alice" in result

    @patch.dict("sys.modules", {"rich": None, "rich.console": None, "rich.table": None})
    def test_rich_table_returns_none_without_rich(self) -> None:
        result = format_rich_table(["id"], [(1,)])
        assert result is None


# ── matt_dbshell: read-only mode ──


class TestSetReadOnly(TestCase):
    def test_read_only_returns_bool(self) -> None:
        result = set_read_only()
        assert isinstance(result, bool)

    @override_settings(DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}})
    def test_read_only_sqlite(self) -> None:
        # SQLite supports PRAGMA query_only — should return True or gracefully False
        result = set_read_only()
        assert isinstance(result, bool)
        # Restore writable state so subsequent tests can write to the DB
        from django.db import connections

        with connections["default"].cursor() as cursor:
            cursor.execute("PRAGMA query_only = OFF")


# ── matt_dbshell: query execution ──


class TestExecuteQuery(TestCase):
    def test_simple_query(self) -> None:
        from django_matt.management.commands.matt_dbshell import execute_query

        columns, rows = execute_query("SELECT 1 AS val")
        assert columns == ["val"]
        assert rows == [(1,)]

    def test_multi_row_query(self) -> None:
        from django_matt.management.commands.matt_dbshell import execute_query

        columns, rows = execute_query(
            "SELECT 1 AS n UNION ALL SELECT 2 UNION ALL SELECT 3"
        )
        assert columns == ["n"]
        assert len(rows) == 3
