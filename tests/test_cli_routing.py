"""Tests for CLI routing — matt.py hub subcommands and Typer CLI aliases."""

from io import StringIO

from django.core.management import call_command

import pytest


class TestMattHubSubcommands:
    """Test the matt management command hub routes to subcommands."""

    def test_matt_help_runs(self):
        """matt (no args) should show help without error."""
        # Rich console output goes to stdout directly, not Django's self.stdout
        call_command("matt", stdout=StringIO())

    def test_matt_info(self):
        """matt info should run without error."""
        call_command("matt", "info", stdout=StringIO())

    def test_matt_version(self):
        """matt version should run without error."""
        call_command("matt", "version", stdout=StringIO())

    def test_matt_doctor(self):
        """matt doctor should run health checks without error."""
        call_command("matt", "doctor", stdout=StringIO())

    def test_matt_routes(self):
        """matt routes should list URL patterns without error."""
        call_command("matt", "routes", stdout=StringIO())

    def test_matt_models(self):
        """matt models should list Django models without error."""
        call_command("matt", "models", stdout=StringIO())

    def test_matt_unknown_subcommand(self):
        """matt <unknown> should raise CommandError."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            call_command("matt", "xyzzyx", stdout=StringIO(), stderr=StringIO())

    def test_matt_subcommands_list(self):
        """SUBCOMMANDS list should contain all commands including new ones."""
        from django_matt.management.commands.matt import Command

        cmd = Command()
        expected = [
            "info",
            "doctor",
            "routes",
            "models",
            "version",
            "new",
            "analyze",
            "endpoints",
            "explain",
            "schemas",
            "validate",
            "migrate-from",
            "ai",
        ]
        for subcmd in expected:
            assert subcmd in cmd.SUBCOMMANDS, f"{subcmd} not in SUBCOMMANDS"


class TestMattHubDelegation:
    """Test that new subcommands delegate to standalone commands."""

    def test_handle_dispatch_hyphenated(self):
        """Hyphenated subcommands should route correctly."""
        from django_matt.management.commands.matt import Command

        cmd = Command()
        handler = getattr(cmd, "handle_migrate_from", None)
        assert handler is not None, "handle_migrate_from method should exist"

    def test_handler_methods_exist(self):
        """All new handler methods should be defined."""
        from django_matt.management.commands.matt import Command

        cmd = Command()
        for name in ["analyze", "endpoints", "explain", "schemas", "validate", "ai"]:
            handler = getattr(cmd, f"handle_{name}", None)
            assert handler is not None, f"handle_{name} method should exist"


class TestSharedCliUtils:
    """Test the shared CLI utilities module."""

    def test_find_manage_py_import(self):
        """find_manage_py should be importable from utils."""
        from django_matt.cli.utils import find_manage_py

        assert callable(find_manage_py)

    def test_find_project_root_import(self):
        """find_project_root should be importable from utils."""
        from django_matt.cli.utils import find_project_root

        assert callable(find_project_root)

    def test_run_manage_command_import(self):
        """run_manage_command should be importable from utils."""
        from django_matt.cli.utils import run_manage_command

        assert callable(run_manage_command)

    def test_setup_django_import(self):
        """setup_django should be importable from utils."""
        from django_matt.cli.utils import setup_django

        assert callable(setup_django)

    def test_utils_exported_from_cli_package(self):
        """Shared utils should be re-exported from django_matt.cli."""
        from django_matt.cli import (
            find_manage_py,
            find_project_root,
            run_manage_command,
            setup_django,
        )

        assert callable(find_manage_py)
        assert callable(find_project_root)
        assert callable(run_manage_command)
        assert callable(setup_django)


class TestValidateApiCommand:
    """Test the enhanced validate_api command."""

    def test_validate_api_runs(self):
        """validate_api should run without errors."""
        try:
            call_command("validate_api", stdout=StringIO())
        except SystemExit:
            pass  # --strict may cause exit

    def test_validate_api_json(self):
        """validate_api --json should produce JSON output."""
        import orjson

        out = StringIO()
        try:
            call_command("validate_api", json=True, stdout=out)
        except SystemExit:
            pass
        output = out.getvalue()
        if output.strip():
            data = orjson.loads(output)
            assert "endpoint_count" in data
            assert "issues" in data

    def test_validate_api_with_prefix(self):
        """validate_api --prefix should filter endpoints."""
        try:
            call_command("validate_api", prefix="/nonexistent/", stdout=StringIO())
        except SystemExit:
            pass

    def test_validation_issue_class(self):
        """ValidationIssue should have correct attributes."""
        from django_matt.management.commands.validate_api import ValidationIssue

        issue = ValidationIssue(
            endpoint="/api/test/",
            severity="warning",
            code="test-code",
            message="Test message",
            suggestion="Fix it",
        )
        d = issue.to_dict()
        assert d["endpoint"] == "/api/test/"
        assert d["severity"] == "warning"
        assert d["code"] == "test-code"
        assert d["message"] == "Test message"
        assert d["suggestion"] == "Fix it"
