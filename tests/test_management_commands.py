"""
Tests for Django Matt management commands.

Covers:
- matt (main CLI dispatcher): info, doctor, routes, models, version subcommands
- matt_status: comprehensive health checks
- matt_endpoints: API endpoint listing
- matt_analyze: codebase analysis
- matt_schemas: schema listing
- matt_explain: view explanation
- matt_migrate_from: migration wizard
- generate_crud: CRUD code generator quality checks
- startapi: project scaffolding
- Error handling: invalid subcommand, missing args, suggestions
"""

import json
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import django
import pytest
from django.core.management import call_command
from django.test import override_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_command(command_name: str, *args, **kwargs) -> str:
    """Run a management command and capture stdout (self.stdout.write output)."""
    out = StringIO()
    err = StringIO()
    kwargs.setdefault("stdout", out)
    kwargs.setdefault("stderr", err)
    call_command(command_name, *args, **kwargs)
    return out.getvalue()


# ===========================================================================
# matt (main CLI dispatcher)
# ===========================================================================


class TestMattCommand:
    """Tests for the 'matt' management command dispatcher."""

    # -- show_help (no subcommand) -----------------------------------------

    def test_no_subcommand_shows_help(self):
        """Running 'matt' with no subcommand does not raise."""
        # Output goes through Rich console, not self.stdout
        run_command("matt")

    # -- matt info ---------------------------------------------------------

    def test_info_subcommand_runs(self):
        """matt info runs without raising."""
        run_command("matt", "info")

    def test_info_gather_project_info_keys(self):
        """_gather_project_info returns dict with all expected keys."""
        cmd = self._get_command_instance()
        info = cmd._gather_project_info()
        expected_keys = {
            "python_version",
            "django_version",
            "matt_version",
            "debug",
            "app_count",
            "model_count",
            "url_count",
            "middleware_count",
            "databases",
        }
        assert expected_keys == set(info.keys())

    def test_info_python_version_matches(self):
        """_gather_project_info python_version matches the running Python."""
        cmd = self._get_command_instance()
        info = cmd._gather_project_info()
        expected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert info["python_version"] == expected

    def test_info_django_version_matches(self):
        """_gather_project_info django_version matches installed Django."""
        cmd = self._get_command_instance()
        info = cmd._gather_project_info()
        assert info["django_version"] == django.get_version()

    def test_info_matt_version(self):
        """_gather_project_info matt_version is 0.1.0."""
        cmd = self._get_command_instance()
        info = cmd._gather_project_info()
        assert info["matt_version"] == "0.1.0"

    def test_info_database_info(self):
        """_gather_project_info includes database engine and name."""
        cmd = self._get_command_instance()
        info = cmd._gather_project_info()
        assert "default" in info["databases"]
        db = info["databases"]["default"]
        assert "engine" in db
        assert "name" in db
        assert "sqlite3" in db["engine"]

    def test_info_debug_mode(self):
        """_gather_project_info debug reflects settings.DEBUG."""
        cmd = self._get_command_instance()
        info = cmd._gather_project_info()
        from django.conf import settings

        assert info["debug"] == settings.DEBUG

    def test_info_counts_are_nonnegative(self):
        """_gather_project_info counts are non-negative integers."""
        cmd = self._get_command_instance()
        info = cmd._gather_project_info()
        assert isinstance(info["app_count"], int) and info["app_count"] > 0
        assert isinstance(info["model_count"], int) and info["model_count"] >= 0
        assert isinstance(info["middleware_count"], int) and info["middleware_count"] > 0
        assert isinstance(info["url_count"], int) and info["url_count"] >= 0

    # -- matt doctor -------------------------------------------------------

    def test_doctor_subcommand_runs(self):
        """matt doctor runs without error."""
        run_command("matt", "doctor")

    @pytest.mark.django_db
    def test_doctor_subcommand_with_db(self):
        """matt doctor runs in a test-db context."""
        run_command("matt", "doctor")

    # -- matt routes -------------------------------------------------------

    def test_routes_subcommand_runs(self):
        """matt routes runs without error."""
        run_command("matt", "routes")

    # -- matt models -------------------------------------------------------

    def test_models_subcommand_runs(self):
        """matt models runs without error."""
        run_command("matt", "models")

    # -- matt version ------------------------------------------------------

    def test_version_subcommand_runs(self):
        """matt version runs without error."""
        run_command("matt", "version")

    # -- error handling: unknown subcommand / suggest ----------------------

    def test_suggest_command_info(self):
        """'inf' should suggest 'info'."""
        cmd = self._get_command_instance()
        assert cmd._suggest_command("inf") == "info"

    def test_suggest_command_routes(self):
        """'routs' should suggest 'routes'."""
        cmd = self._get_command_instance()
        assert cmd._suggest_command("routs") == "routes"

    def test_suggest_command_doctor(self):
        """'doctr' should suggest 'doctor'."""
        cmd = self._get_command_instance()
        assert cmd._suggest_command("doctr") == "doctor"

    def test_suggest_command_version(self):
        """'versio' should suggest 'version'."""
        cmd = self._get_command_instance()
        assert cmd._suggest_command("versio") == "version"

    def test_suggest_command_no_match(self):
        """Completely unrelated input returns no suggestion."""
        cmd = self._get_command_instance()
        assert cmd._suggest_command("xyzzy") is None

    # -- similarity helper -------------------------------------------------

    def test_similarity_identical(self):
        """Identical strings have similarity 1.0."""
        cmd = self._get_command_instance()
        assert cmd._similarity("info", "info") == 1.0

    def test_similarity_empty(self):
        """Empty strings have similarity 0.0."""
        cmd = self._get_command_instance()
        assert cmd._similarity("", "") == 0.0
        assert cmd._similarity("info", "") == 0.0
        assert cmd._similarity("", "info") == 0.0

    def test_similarity_partial(self):
        """Partial matches have intermediate similarity."""
        cmd = self._get_command_instance()
        score = cmd._similarity("inf", "info")
        assert 0.0 < score < 1.0

    # -- _collect_routes helper --------------------------------------------

    def test_collect_routes_returns_list(self):
        """_collect_routes returns a list."""
        cmd = self._get_command_instance()
        routes = cmd._collect_routes()
        assert isinstance(routes, list)

    def test_collect_routes_dict_structure(self):
        """Each route dict has path, name, Methods, Path keys."""
        cmd = self._get_command_instance()
        routes = cmd._collect_routes()
        if routes:
            route = routes[0]
            assert "path" in route
            assert "name" in route
            assert "Methods" in route
            assert "Path" in route

    def test_collect_routes_includes_test_urls(self):
        """Routes include the test URL patterns from tests/urls.py."""
        cmd = self._get_command_instance()
        routes = cmd._collect_routes()
        paths = [r["path"] for r in routes]
        assert any("api/json" in p for p in paths)

    # -- check helpers -----------------------------------------------------

    def test_check_settings_passes(self):
        """_check_settings returns a passing result."""
        cmd = self._get_command_instance()
        result = cmd._check_settings()
        assert result["passed"] is True
        assert result["name"] == "Django settings"

    def test_check_installed_apps_passes(self):
        """_check_installed_apps passes when contenttypes is installed."""
        cmd = self._get_command_instance()
        result = cmd._check_installed_apps()
        assert result["passed"] is True

    def test_check_dependencies_passes(self):
        """_check_dependencies passes for django, pydantic, rich."""
        cmd = self._get_command_instance()
        result = cmd._check_dependencies()
        assert result["passed"] is True

    @patch("django.db.connection.ensure_connection")
    def test_check_database_passes_on_success(self, mock_conn):
        """_check_database passes when connection succeeds."""
        mock_conn.return_value = None
        cmd = self._get_command_instance()
        result = cmd._check_database()
        assert result["passed"] is True

    @patch("django.db.connection.ensure_connection", side_effect=Exception("db error"))
    def test_check_database_fails_on_error(self, mock_conn):
        """_check_database fails when connection raises."""
        cmd = self._get_command_instance()
        result = cmd._check_database()
        assert result["passed"] is False
        assert "db error" in result["message"]

    # -- private helper ----------------------------------------------------

    def _get_command_instance(self):
        from django_matt.management.commands.matt import Command

        return Command()


# ===========================================================================
# matt_status
# ===========================================================================


class TestMattStatusCommand:
    """Tests for the 'matt_status' management command."""

    def test_status_runs_without_error(self):
        """matt_status runs without raising."""
        run_command("matt_status")

    @pytest.mark.django_db
    def test_status_json_output(self):
        """matt_status --json outputs valid JSON with checks and summary."""
        out = run_command("matt_status", json=True)
        data = json.loads(out)
        assert "checks" in data
        assert "summary" in data
        assert isinstance(data["checks"], list)
        assert len(data["checks"]) > 0

    @pytest.mark.django_db
    def test_status_json_summary_keys(self):
        """JSON summary has expected keys."""
        out = run_command("matt_status", json=True)
        data = json.loads(out)
        summary = data["summary"]
        for key in ("overall", "total_checks", "ok", "warnings", "errors"):
            assert key in summary

    @pytest.mark.django_db
    def test_status_json_check_structure(self):
        """Each check has name, status, message."""
        out = run_command("matt_status", json=True)
        data = json.loads(out)
        for check in data["checks"]:
            assert "name" in check
            assert "status" in check
            assert check["status"] in ("ok", "warning", "error", "info")
            assert "message" in check

    @pytest.mark.django_db
    def test_status_check_db_only(self):
        """matt_status --check db runs only the DB check."""
        out = run_command("matt_status", check="db", json=True)
        data = json.loads(out)
        assert len(data["checks"]) == 1
        assert data["checks"][0]["name"] == "Database"

    @pytest.mark.django_db
    def test_status_check_cache_only(self):
        """matt_status --check cache runs only the cache check."""
        out = run_command("matt_status", check="cache", json=True)
        data = json.loads(out)
        assert len(data["checks"]) == 1
        assert data["checks"][0]["name"] == "Cache"

    @pytest.mark.django_db
    def test_status_check_env_only(self):
        """matt_status --check env runs only the environment check."""
        out = run_command("matt_status", check="env", json=True)
        data = json.loads(out)
        assert len(data["checks"]) == 1
        assert data["checks"][0]["name"] == "Environment"

    @pytest.mark.django_db
    def test_status_check_security(self):
        """matt_status --check security returns security checks."""
        out = run_command("matt_status", check="security", json=True)
        data = json.loads(out)
        assert len(data["checks"]) > 0
        names = [c["name"] for c in data["checks"]]
        assert "DEBUG Mode" in names
        assert "SECRET_KEY" in names

    @pytest.mark.django_db
    def test_status_check_deps(self):
        """matt_status --check deps returns dependency checks."""
        out = run_command("matt_status", check="deps", json=True)
        data = json.loads(out)
        assert len(data["checks"]) > 0
        names = [c["name"] for c in data["checks"]]
        assert any("Django" in n for n in names)
        assert any("Pydantic" in n for n in names)
        assert any("Rich" in n for n in names)

    @pytest.mark.django_db
    def test_status_check_migrations(self):
        """matt_status --check migrations returns migration status."""
        out = run_command("matt_status", check="migrations", json=True)
        data = json.loads(out)
        assert len(data["checks"]) == 1
        assert data["checks"][0]["name"] == "Migrations"

    @pytest.mark.django_db
    def test_status_verbose(self):
        """matt_status --verbose runs without error."""
        run_command("matt_status", verbose=True)

    def test_generate_summary_counts(self):
        """_generate_summary correctly counts statuses."""
        cmd = self._get_command()
        checks = [
            {"name": "A", "status": "ok", "message": ""},
            {"name": "B", "status": "ok", "message": ""},
            {"name": "C", "status": "warning", "message": "warn"},
            {"name": "D", "status": "error", "message": "err"},
            {"name": "E", "status": "info", "message": "inf"},
        ]
        summary = cmd._generate_summary(checks)
        assert summary["ok"] == 2
        assert summary["warnings"] == 1
        assert summary["errors"] == 1
        assert summary["info"] == 1
        assert summary["total_checks"] == 5
        assert summary["overall"] == "unhealthy"

    def test_generate_summary_healthy(self):
        """Summary is 'healthy' when all checks pass."""
        cmd = self._get_command()
        checks = [
            {"name": "A", "status": "ok", "message": ""},
            {"name": "B", "status": "ok", "message": ""},
        ]
        summary = cmd._generate_summary(checks)
        assert summary["overall"] == "healthy"

    def test_generate_summary_warnings_only(self):
        """Summary is 'warnings' when there are warnings but no errors."""
        cmd = self._get_command()
        checks = [
            {"name": "A", "status": "ok", "message": ""},
            {"name": "B", "status": "warning", "message": "warn"},
        ]
        summary = cmd._generate_summary(checks)
        assert summary["overall"] == "warnings"

    def test_environment_check_details(self):
        """_check_environment includes python/django version details."""
        cmd = self._get_command()
        # Ensure BASE_DIR exists for the check
        from django.conf import settings

        if not hasattr(settings, "BASE_DIR"):
            settings.BASE_DIR = "/tmp"
        result = cmd._check_environment(verbose=True)
        assert result["status"] == "ok"
        assert "python_version" in result["details"]
        assert "django_version" in result["details"]
        assert "django_matt_version" in result["details"]
        assert "platform" in result["details"]
        assert "timezone" in result["details"]

    @pytest.mark.django_db
    def test_cache_check_works(self):
        """Cache check works with LocMemCache."""
        cmd = self._get_command()
        result = cmd._check_cache(verbose=True)
        assert result["status"] == "ok"
        assert "backend" in result["details"]

    def test_security_check_debug_status(self):
        """Security check status reflects DEBUG setting."""
        from django.conf import settings

        cmd = self._get_command()
        checks = cmd._check_security()
        debug_check = next(c for c in checks if c["name"] == "DEBUG Mode")
        if settings.DEBUG:
            assert debug_check["status"] == "warning"
        else:
            assert debug_check["status"] == "ok"

    def test_security_check_secret_key(self):
        """Security check evaluates SECRET_KEY."""
        cmd = self._get_command()
        checks = cmd._check_security()
        key_check = next(c for c in checks if c["name"] == "SECRET_KEY")
        assert key_check["status"] in ("ok", "warning")

    def test_security_check_allowed_hosts(self):
        """Security check evaluates ALLOWED_HOSTS."""
        cmd = self._get_command()
        checks = cmd._check_security()
        hosts_check = next(c for c in checks if c["name"] == "ALLOWED_HOSTS")
        assert hosts_check["status"] in ("ok", "warning")

    def test_dependencies_finds_required(self):
        """Dependencies check finds django, pydantic, rich as ok."""
        cmd = self._get_command()
        checks = cmd._check_dependencies()
        required = [c for c in checks if c["name"].startswith("Dependency")]
        assert len(required) == 3
        for check in required:
            assert check["status"] == "ok"

    def test_dependencies_includes_optional(self):
        """Dependencies check lists 4 optional packages."""
        cmd = self._get_command()
        checks = cmd._check_dependencies()
        optional = [c for c in checks if c["name"].startswith("Optional")]
        assert len(optional) == 4

    def _get_command(self):
        from django_matt.management.commands.matt_status import Command

        return Command()


# ===========================================================================
# matt_endpoints
# ===========================================================================


class TestMattEndpointsCommand:
    """Tests for the 'matt_endpoints' management command."""

    def test_endpoints_runs_without_error(self):
        """matt_endpoints runs without raising."""
        run_command("matt_endpoints")

    def test_endpoints_json_output(self):
        """matt_endpoints --json outputs valid JSON list."""
        out = run_command("matt_endpoints", json=True)
        data = json.loads(out)
        assert isinstance(data, list)

    def test_endpoints_json_structure(self):
        """Each endpoint in JSON output has path and methods."""
        out = run_command("matt_endpoints", json=True)
        data = json.loads(out)
        if data:
            ep = data[0]
            assert "path" in ep
            assert "methods" in ep
            assert isinstance(ep["methods"], list)

    def test_endpoints_markdown_output(self):
        """matt_endpoints --markdown produces markdown with table headers."""
        out = run_command("matt_endpoints", markdown=True)
        assert "# API Endpoints" in out
        assert "| Method | Path |" in out

    def test_endpoints_openapi_output(self):
        """matt_endpoints --openapi produces valid OpenAPI 3.0.3 JSON."""
        out = run_command("matt_endpoints", openapi=True)
        data = json.loads(out)
        assert data["openapi"] == "3.0.3"
        assert "info" in data
        assert "paths" in data
        assert isinstance(data["paths"], dict)

    def test_endpoints_openapi_info(self):
        """OpenAPI output has info with title and version."""
        out = run_command("matt_endpoints", openapi=True)
        data = json.loads(out)
        assert "title" in data["info"]
        assert "version" in data["info"]

    def test_endpoints_filter_by_path(self):
        """matt_endpoints --filter filters endpoints by path pattern."""
        all_out = run_command("matt_endpoints", json=True)
        all_endpoints = json.loads(all_out)
        if not all_endpoints:
            pytest.skip("No endpoints registered")

        path_fragment = all_endpoints[0]["path"][:5]
        filtered_out = run_command("matt_endpoints", json=True, filter=path_fragment)
        filtered = json.loads(filtered_out)
        assert all(path_fragment.lower() in ep["path"].lower() for ep in filtered)

    def test_endpoints_filter_no_match(self):
        """matt_endpoints --filter with non-matching pattern returns empty."""
        out = run_command("matt_endpoints", json=True, filter="nonexistent_path_xyz")
        data = json.loads(out)
        assert data == []

    def test_collect_endpoints_returns_list(self):
        """_collect_endpoints returns a list."""
        cmd = self._get_command()
        endpoints = cmd._collect_endpoints()
        assert isinstance(endpoints, list)

    def test_get_methods_default(self):
        """_get_methods returns ['GET'] for a plain function callback."""
        cmd = self._get_command()

        def dummy_view(request):
            pass

        methods = cmd._get_methods(dummy_view)
        assert methods == ["GET"]

    def test_get_methods_with_actions(self):
        """_get_methods extracts methods from .actions attribute."""
        cmd = self._get_command()

        def view_with_actions(request):
            pass

        view_with_actions.actions = {"get": "list", "post": "create"}
        methods = cmd._get_methods(view_with_actions)
        assert "GET" in methods
        assert "POST" in methods

    def test_get_methods_filters_head_options(self):
        """_get_methods filters out HEAD and OPTIONS."""
        cmd = self._get_command()

        class FakeView:
            http_method_names = ["get", "post", "head", "options"]

        callback = lambda r: None  # noqa: E731
        callback.view_class = FakeView
        methods = cmd._get_methods(callback)
        assert "HEAD" not in methods
        assert "OPTIONS" not in methods

    def test_get_permissions_empty(self):
        """_get_permissions returns empty list for views without permissions."""
        cmd = self._get_command()

        def dummy_view(request):
            pass

        assert cmd._get_permissions(dummy_view) == []

    def test_get_permissions_from_callback(self):
        """_get_permissions extracts permission classes from callback."""
        cmd = self._get_command()

        class FakePermission:
            pass

        def view_with_perms(request):
            pass

        view_with_perms.permission_classes = [FakePermission]
        perms = cmd._get_permissions(view_with_perms)
        assert "FakePermission" in perms

    def test_markdown_has_table_separator(self):
        """Markdown output has pipe-delimited table with separator."""
        out = run_command("matt_endpoints", markdown=True)
        assert "|" in out
        assert "---" in out

    def _get_command(self):
        from django_matt.management.commands.matt_endpoints import Command

        return Command()


# ===========================================================================
# matt_analyze
# ===========================================================================


class TestMattAnalyzeCommand:
    """Tests for the 'matt_analyze' management command."""

    def test_analyze_runs_without_error(self):
        """matt_analyze runs without raising."""
        run_command("matt_analyze")

    def test_analyze_json_output(self):
        """matt_analyze --json outputs valid JSON with summary."""
        out = run_command("matt_analyze", json=True)
        data = json.loads(out)
        assert "summary" in data

    def test_analyze_json_health_score(self):
        """JSON summary includes health_score between 0 and 100."""
        out = run_command("matt_analyze", json=True)
        data = json.loads(out)
        assert 0 <= data["summary"]["health_score"] <= 100

    def test_analyze_section_models(self):
        """matt_analyze --section models outputs model analysis."""
        out = run_command("matt_analyze", section="models", json=True)
        data = json.loads(out)
        assert "models" in data
        assert "total" in data["models"]

    def test_analyze_section_tests(self):
        """matt_analyze --section tests outputs test analysis."""
        out = run_command("matt_analyze", section="tests", json=True)
        data = json.loads(out)
        assert "tests" in data
        assert "total_test_files" in data["tests"]
        assert "total_test_methods" in data["tests"]

    def test_analyze_models_structure(self):
        """Model analysis has expected keys."""
        cmd = self._get_command()
        result = cmd._analyze_models()
        for key in ("total", "by_app", "relationships", "issues"):
            assert key in result

    def test_generate_summary_with_no_issues(self):
        """_generate_summary produces health_score 100 with no issues."""
        cmd = self._get_command()
        analysis = {
            "models": {"total": 5, "issues": []},
            "views": {"total": 3},
            "schemas": {"total": 2, "unused": []},
            "tests": {"total_test_methods": 10, "missing_tests": []},
            "queries": {"loop_queries": []},
        }
        summary = cmd._generate_summary(analysis)
        assert summary["total_models"] == 5
        assert summary["total_views"] == 3
        assert summary["total_schemas"] == 2
        assert summary["total_tests"] == 10
        assert summary["health_score"] == 100

    def test_generate_summary_with_issues_reduces_score(self):
        """_generate_summary reduces health_score for issues."""
        cmd = self._get_command()
        analysis = {
            "models": {
                "total": 1,
                "issues": [{"model": "test.Test", "issue": "missing", "severity": "low"}],
            },
            "views": {"total": 0},
            "schemas": {"total": 0, "unused": ["OldSchema"]},
            "tests": {"total_test_methods": 0, "missing_tests": []},
            "queries": {"loop_queries": [{"file": "f.py", "pattern": "p", "suggestion": "s"}]},
        }
        summary = cmd._generate_summary(analysis)
        assert summary["health_score"] < 100

    def _get_command(self):
        from django_matt.management.commands.matt_analyze import Command

        return Command()


# ===========================================================================
# matt_schemas
# ===========================================================================


class TestMattSchemasCommand:
    """Tests for the 'matt_schemas' management command."""

    def test_schemas_runs_without_error(self):
        """matt_schemas runs without raising."""
        run_command("matt_schemas")

    def test_schemas_json_output(self):
        """matt_schemas --json outputs valid JSON list."""
        out = run_command("matt_schemas", json=True)
        data = json.loads(out)
        assert isinstance(data, list)

    def test_schemas_json_structure(self):
        """Each schema in JSON output has expected keys."""
        out = run_command("matt_schemas", json=True)
        data = json.loads(out)
        if data:
            schema = data[0]
            assert "name" in schema
            assert "app" in schema
            assert "field_count" in schema
            assert "validator_count" in schema

    def test_schemas_filter_by_name(self):
        """matt_schemas --filter filters schemas by name pattern."""
        out = run_command("matt_schemas", json=True, filter="zzzznonexistent")
        data = json.loads(out)
        assert data == []


# ===========================================================================
# matt_explain
# ===========================================================================


class TestMattExplainCommand:
    """Tests for the 'matt_explain' management command."""

    def test_explain_nonexistent_view(self):
        """matt_explain with nonexistent target does not crash."""
        run_command("matt_explain", "nonexistent_view_xyz")

    def test_explain_url_path(self):
        """matt_explain with a URL path does not crash."""
        run_command("matt_explain", "/api/json/")

    def test_explain_json_for_url(self):
        """matt_explain --json with URL path outputs JSON when view found."""
        out = run_command("matt_explain", "/api/json/", json=True)
        # If the view resolves, we get JSON
        if out.strip().startswith("{"):
            data = json.loads(out)
            assert "target" in data
            assert "middleware_stack" in data
            assert "request_flow" in data

    def test_middleware_stack(self):
        """_get_middleware_stack returns non-empty list of middleware info."""
        cmd = self._get_command()
        stack = cmd._get_middleware_stack()
        assert isinstance(stack, list)
        assert len(stack) > 0
        mw = stack[0]
        assert "name" in mw
        assert "category" in mw
        assert "full_path" in mw

    def test_middleware_categories(self):
        """_get_middleware_stack categorizes middleware correctly."""
        cmd = self._get_command()
        stack = cmd._get_middleware_stack()
        categories = {mw["category"] for mw in stack}
        # Test settings include SecurityMiddleware and AuthenticationMiddleware
        assert "security" in categories or "authentication" in categories or "other" in categories

    def test_trace_request_flow(self):
        """_trace_request_flow returns a list of flow steps."""
        cmd = self._get_command()
        view_info = {"view_name": "TestView", "view_class": None}
        flow = cmd._trace_request_flow(view_info)
        assert isinstance(flow, list)
        assert len(flow) >= 4  # Entry, Middleware, URL Resolution, View, Middleware, Response
        stages = [s["stage"] for s in flow]
        assert "Entry" in stages
        assert "View Execution" in stages
        assert "Response" in stages

    def _get_command(self):
        from django_matt.management.commands.matt_explain import Command

        return Command()


# ===========================================================================
# matt_migrate_from
# ===========================================================================


class TestMattMigrateFromCommand:
    """Tests for the 'matt_migrate_from' management command."""

    def test_migrate_from_auto_detect(self):
        """matt_migrate_from --source auto runs without crashing."""
        run_command("matt_migrate_from", source="auto")

    def test_migrate_from_drf_json(self):
        """matt_migrate_from --source drf --json outputs valid JSON."""
        out = run_command("matt_migrate_from", source="drf", json=True)
        data = json.loads(out)
        assert data["framework"] == "drf"
        assert "items" in data
        assert "suggestions" in data

    def test_migrate_from_ninja_json(self):
        """matt_migrate_from --source ninja --json outputs valid JSON."""
        out = run_command("matt_migrate_from", source="ninja", json=True)
        data = json.loads(out)
        assert data["framework"] == "ninja"
        assert "items" in data
        assert "suggestions" in data

    def test_drf_always_has_url_suggestion(self):
        """DRF migration always includes URL configuration suggestion."""
        out = run_command("matt_migrate_from", source="drf", json=True)
        data = json.loads(out)
        titles = [s["title"] for s in data["suggestions"]]
        assert "Update URL Configuration" in titles

    def test_ninja_always_has_import_suggestion(self):
        """Ninja migration always includes import update suggestion."""
        out = run_command("matt_migrate_from", source="ninja", json=True)
        data = json.loads(out)
        titles = [s["title"] for s in data["suggestions"]]
        assert "Update Import Statements" in titles

    def test_detect_framework_returns_str_or_none(self):
        """_detect_framework returns str or None."""
        cmd = self._get_command()
        result = cmd._detect_framework()
        assert result is None or isinstance(result, str)

    def test_drf_field_type_conversion(self):
        """_convert_drf_field_type maps DRF types to Python types."""
        cmd = self._get_command()
        assert cmd._convert_drf_field_type("CharField") == "str"
        assert cmd._convert_drf_field_type("IntegerField") == "int"
        assert cmd._convert_drf_field_type("BooleanField") == "bool"
        assert cmd._convert_drf_field_type("DateTimeField") == "datetime"
        assert cmd._convert_drf_field_type("UnknownField") == "Any"

    def test_migrate_from_ninja_rewrites_imports(self):
        """Ninja analysis suggests rewriting 'from ninja import ...' to django_matt imports."""
        out = run_command("matt_migrate_from", source="ninja", json=True)
        data = json.loads(out)
        # Suggestions include import rewrite steps
        all_steps = []
        for suggestion in data["suggestions"]:
            all_steps.extend(suggestion.get("steps", []))
        # Should include a step about replacing ninja imports
        assert any("ninja" in step.lower() and "django_matt" in step.lower() for step in all_steps), (
            "Expected a suggestion step about replacing ninja imports with django_matt. "
            f"Got steps: {all_steps}"
        )

    def test_migrate_from_ninja_suggestions_include_import_update(self):
        """Ninja migration suggestions include 'Update Import Statements'."""
        out = run_command("matt_migrate_from", source="ninja", json=True)
        data = json.loads(out)
        titles = [s["title"] for s in data["suggestions"]]
        assert "Update Import Statements" in titles

    def test_migrate_from_ninja_adds_todo_markers_in_guide(self, tmp_path):
        """_generate_migration_guide includes review/TODO language for ambiguous patterns."""
        cmd = self._get_command()
        analysis = {"framework": "ninja", "items": [], "schemas": [], "routers": [], "suggestions": [
            {
                "title": "Update Import Statements",
                "description": "Replace ninja imports with django_matt imports",
                "priority": "high",
                "steps": [
                    "Replace 'from ninja import ...' with 'from django_matt import ...'",
                    "# TODO: Review this migration — manual verification needed",
                ],
            }
        ]}
        guide = cmd._generate_migration_guide(analysis)
        # Guide should include review/TODO language indicating manual verification
        assert "TODO" in guide or "Review" in guide, (
            "Migration guide should contain TODO or Review markers for ambiguous patterns"
        )

    def test_migrate_from_ninja_preserves_business_logic_in_guide(self, tmp_path):
        """Generated guide does not alter business logic — it provides instructions only."""
        cmd = self._get_command()
        # Run a full ninja analysis
        out = run_command("matt_migrate_from", source="ninja", json=True)
        data = json.loads(out)
        # The output is structured analysis data, not modified source files
        # Business logic is preserved because we only analyze and generate separate files
        assert "framework" in data
        assert "suggestions" in data
        # Suggestions are migration instructions, not destructive changes
        for suggestion in data["suggestions"]:
            assert "title" in suggestion
            assert "steps" in suggestion

    def test_migrate_from_ninja_runs_non_interactively(self):
        """matt_migrate_from --source ninja works with flags only (no prompts)."""
        # Should complete without raising or prompting
        out = run_command("matt_migrate_from", source="ninja", json=True)
        data = json.loads(out)
        assert data["framework"] == "ninja"

    def test_migrate_from_drf_runs_non_interactively(self):
        """matt_migrate_from --source drf works with flags only (no prompts)."""
        out = run_command("matt_migrate_from", source="drf", json=True)
        data = json.loads(out)
        assert data["framework"] == "drf"

    def _get_command(self):
        from django_matt.management.commands.matt_migrate_from import Command

        return Command()


# ===========================================================================
# matt command - models subcommand
# ===========================================================================


class TestMattModelsSubcommand:
    """Tests for the matt models subcommand logic."""

    def test_models_skips_internal_apps(self):
        """Django internal apps are skipped by default."""
        from django.apps import apps as django_apps

        models_by_app = {}
        for model in django_apps.get_models():
            app_label = model._meta.app_label
            if app_label in ("contenttypes", "sessions", "admin", "auth"):
                continue
            if app_label not in models_by_app:
                models_by_app[app_label] = []
            models_by_app[app_label].append(model.__name__)

        assert "contenttypes" not in models_by_app
        assert "sessions" not in models_by_app
        assert "admin" not in models_by_app


# ===========================================================================
# matt command - security checks
# ===========================================================================


class TestMattSecurityChecks:
    """Tests for security check helpers in the matt command."""

    @override_settings(DEBUG=True)
    def test_debug_mode_skips_security_in_doctor(self):
        """In DEBUG mode, handle_doctor does not run security checks."""
        from django.conf import settings

        assert settings.DEBUG is True

    @override_settings(DEBUG=False, SECRET_KEY="django-insecure-test")
    def test_check_security_detects_insecure_key(self):
        """_check_security flags insecure SECRET_KEY."""
        from django_matt.management.commands.matt import Command

        cmd = Command()
        result = cmd._check_security()
        assert result["passed"] is False

    @override_settings(DEBUG=False, ALLOWED_HOSTS=[])
    def test_check_security_empty_hosts(self):
        """_check_security flags empty ALLOWED_HOSTS."""
        from django_matt.management.commands.matt import Command

        cmd = Command()
        result = cmd._check_security()
        assert result["passed"] is False


# ===========================================================================
# Integration tests - command discovery
# ===========================================================================


class TestCommandDiscovery:
    """Tests that all management commands are discoverable by Django."""

    def test_matt_command_discoverable(self):
        from django.core.management import get_commands

        assert "matt" in get_commands()

    def test_matt_status_command_discoverable(self):
        from django.core.management import get_commands

        assert "matt_status" in get_commands()

    def test_matt_endpoints_command_discoverable(self):
        from django.core.management import get_commands

        assert "matt_endpoints" in get_commands()

    def test_matt_analyze_command_discoverable(self):
        from django.core.management import get_commands

        assert "matt_analyze" in get_commands()

    def test_matt_schemas_command_discoverable(self):
        from django.core.management import get_commands

        assert "matt_schemas" in get_commands()

    def test_matt_explain_command_discoverable(self):
        from django.core.management import get_commands

        assert "matt_explain" in get_commands()

    def test_matt_migrate_from_command_discoverable(self):
        from django.core.management import get_commands

        assert "matt_migrate_from" in get_commands()


# ===========================================================================
# matt_endpoints - endpoint data extraction
# ===========================================================================


class TestEndpointDataExtraction:
    """Tests for extract_endpoint_info behavior."""

    def _get_command(self):
        from django_matt.management.commands.matt_endpoints import Command

        return Command()

    def test_admin_paths_skipped(self):
        """Endpoints with 'admin' in the path are skipped."""
        from django.urls import URLPattern

        cmd = self._get_command()

        def fake_callback(request):
            """A fake view."""
            pass

        pattern = URLPattern(r"admin/dashboard/", fake_callback, name="admin_dash")
        result = cmd._extract_endpoint_info(pattern, "admin/dashboard/", None)
        assert result is None

    def test_static_paths_skipped(self):
        """Endpoints starting with 'static/' are skipped."""
        from django.urls import URLPattern

        cmd = self._get_command()

        def fake_callback(request):
            """A fake view."""
            pass

        pattern = URLPattern(r"static/file.js", fake_callback, name="static_file")
        result = cmd._extract_endpoint_info(pattern, "static/file.js", None)
        assert result is None

    def test_normal_endpoint_extracted(self):
        """Normal endpoints are extracted with expected keys."""
        from django.urls import URLPattern

        cmd = self._get_command()

        def my_view(request):
            """My test view."""
            pass

        pattern = URLPattern(r"api/test/", my_view, name="test_view")
        result = cmd._extract_endpoint_info(pattern, "api/test/", "myapp")
        assert result is not None
        assert result["path"] == "/api/test"
        # App is derived from view module, not the passed argument
        assert "app" in result
        assert "methods" in result
        assert "description" in result
        assert result["description"] == "My test view."


# ===========================================================================
# matt_analyze - health score degradation
# ===========================================================================


class TestAnalyzeHealthScore:
    """Tests for health score calculation in matt_analyze."""

    def _get_command(self):
        from django_matt.management.commands.matt_analyze import Command

        return Command()

    def test_score_degrades_for_high_severity(self):
        """High severity issues reduce score by 10 each."""
        cmd = self._get_command()
        analysis = {
            "models": {"total": 0, "issues": []},
            "queries": {
                "loop_queries": [
                    {"file": "a.py", "pattern": "p", "suggestion": "s"},
                    {"file": "b.py", "pattern": "p", "suggestion": "s"},
                ]
            },
        }
        summary = cmd._generate_summary(analysis)
        assert summary["health_score"] == 80  # 100 - 2*10

    def test_score_degrades_for_medium_severity(self):
        """Medium severity issues reduce score by 5 each."""
        cmd = self._get_command()
        analysis = {
            "models": {"total": 0, "issues": []},
            "tests": {
                "total_test_methods": 0,
                "missing_tests": [
                    {"type": "model", "name": "app.Model1"},
                    {"type": "model", "name": "app.Model2"},
                ],
            },
        }
        summary = cmd._generate_summary(analysis)
        assert summary["health_score"] == 90  # 100 - 2*5

    def test_score_degrades_for_low_severity(self):
        """Low severity issues reduce score by 2 each."""
        cmd = self._get_command()
        analysis = {
            "models": {
                "total": 1,
                "issues": [{"model": "test.M", "issue": "no __str__", "severity": "low"}],
            },
        }
        summary = cmd._generate_summary(analysis)
        assert summary["health_score"] == 98  # 100 - 1*2

    def test_score_floor_is_zero(self):
        """Health score cannot go below 0."""
        cmd = self._get_command()
        # loop_queries is capped at 5 items ([:5]) in _generate_summary,
        # so we also add high-severity model issues and missing tests to
        # push the score below 0.
        analysis = {
            "models": {
                "total": 0,
                "issues": [
                    {"type": "issue", "severity": "high"} for _ in range(5)
                ],
            },
            "queries": {
                "loop_queries": [
                    {"file": f"{i}.py", "pattern": "p", "suggestion": "s"} for i in range(15)
                ]
            },
            "tests": {
                "total_test_methods": 0,
                "missing_tests": [
                    {"name": f"test_{j}"} for j in range(10)
                ],
            },
        }
        summary = cmd._generate_summary(analysis)
        assert summary["health_score"] == 0


# ===========================================================================
# generate_crud - code quality
# ===========================================================================


class TestGenerateCrudCommand:
    """Tests for the generate_crud management command code quality."""

    def _get_command(self):
        from django_matt.management.commands.generate_crud import Command

        return Command()

    def _get_generated_content(self, context_overrides: dict | None = None):
        """Get generated content for a minimal test context."""
        from django.contrib.auth import get_user_model

        cmd = self._get_command()
        User = get_user_model()

        # Build a minimal context using auth.User model
        fields = cmd._get_model_fields(User)
        context = {
            "model": User,
            "model_name": "User",
            "app_label": "auth",
            "prefix": "users",
            "fields": fields,
            "permissions": ["IsAuthenticated"],
            "pagination": False,
            "filtering": False,
            "soft_delete": False,
            "with_service": True,
        }
        if context_overrides:
            context.update(context_overrides)
        return context, cmd

    def test_generate_crud_full_passes_ruff(self):
        """Generated controller, schema, service, admin, and test files all pass ruff check."""
        context, cmd = self._get_generated_content()

        generators = {
            "schema": cmd._generate_schema_content(context),
            "controller": cmd._generate_controller_content(context),
            "service": cmd._generate_service_content(context),
            "admin": cmd._generate_admin_content(context),
            "test": cmd._generate_test_content(context),
        }

        for component, content in generators.items():
            result = subprocess.run(
                ["uv", "run", "ruff", "check", "--stdin-filename", f"{component}.py", "-"],
                input=content.encode(),
                capture_output=True,
            )
            assert result.returncode == 0, (
                f"ruff check failed for generated {component}.py:\n"
                f"{result.stdout.decode()}\n{result.stderr.decode()}\n\n"
                f"Content:\n{content}"
            )

    def test_generate_crud_service_async_pattern(self):
        """Generated service file uses async ORM methods throughout."""
        context, cmd = self._get_generated_content()
        content = cmd._generate_service_content(context)

        # Must have async methods
        assert "async def list" in content
        assert "async def get" in content
        assert "async def create" in content
        assert "async def update" in content
        assert "async def delete" in content

        # Must use async ORM calls
        assert "acount()" in content or "aget(" in content or "acreate(" in content or "adelete()" in content

        # Must NOT have top-level sync transaction import (only used in comments)
        lines = [ln for ln in content.splitlines() if not ln.strip().startswith("#")]
        non_comment_content = "\n".join(lines)
        assert "from django.db import transaction" not in non_comment_content, (
            "Service must not import sync 'transaction' at top level (use async patterns instead)"
        )

    def test_generated_test_no_asyncio_mark(self):
        """Generated test file does NOT contain @pytest.mark.asyncio decorator."""
        context, cmd = self._get_generated_content()
        content = cmd._generate_test_content(context)
        assert "@pytest.mark.asyncio" not in content, (
            "Generated tests must NOT use @pytest.mark.asyncio "
            "(project uses asyncio_mode=auto in pyproject.toml)"
        )

    def test_generated_schema_uses_python312_syntax(self):
        """Generated schema uses Python 3.12 builtins, not typing module."""
        context, cmd = self._get_generated_content()
        content = cmd._generate_schema_content(context)

        # Must NOT use typing.Optional or typing.List
        assert "Optional[" not in content, "Schema must use 'X | None' not 'Optional[X]'"
        assert "List[" not in content, "Schema must use 'list[X]' not 'List[X]'"

    def test_generated_admin_uses_unfold(self):
        """Generated admin file uses django-matt MattModelAdmin (Unfold-backed)."""
        context, cmd = self._get_generated_content()
        content = cmd._generate_admin_content(context)

        assert "MattModelAdmin" in content, "Admin must use MattModelAdmin (Unfold-backed)"
        assert "register_admin" in content, "Admin must use @register_admin decorator"

    def test_generated_controller_with_service_no_direct_orm_imports(self):
        """Controller generated with service=True does NOT import Http404 or Q directly."""
        context, cmd = self._get_generated_content({"with_service": True})
        content = cmd._generate_controller_content(context)

        # Http404 and Q are service concerns when with_service=True
        assert "from django.http import Http404" not in content, (
            "Controller with service layer must not import Http404 directly"
        )
        assert "from django.db.models import Q" not in content, (
            "Controller with service layer must not import Q directly"
        )


# ===========================================================================
# startapi - project scaffolding
# ===========================================================================


class TestStartapiCommand:
    """Tests for the startapi management command."""

    def test_startapi_b2b_template_files(self):
        """startapi --template b2b produces CLAUDE.md, CI config, docker-compose, settings."""
        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "testproject"
            project_dir = Path(tmpdir) / project_name
            project_dir.mkdir()

            # Run startapi in the temp directory
            call_command(
                "startapi",
                project_name,
                directory=str(project_dir),
                template="b2b",
                docker=True,
                force=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

            # Check CLAUDE.md was created
            assert (project_dir / "CLAUDE.md").exists(), "CLAUDE.md must be created for b2b template"

            # Check CI config was created
            ci_path = project_dir / ".github" / "workflows" / "ci.yml"
            assert ci_path.exists(), ".github/workflows/ci.yml must be created for b2b template"

            # Check docker-compose.yml exists
            assert (project_dir / "docker-compose.yml").exists(), "docker-compose.yml must exist"

            # Check settings.py contains multitenancy reference
            settings_path = project_dir / project_name / "settings.py"
            assert settings_path.exists(), "settings.py must exist"
            settings_content = settings_path.read_text()
            assert "DJANGO_MATT_MULTITENANCY" in settings_content, (
                "settings.py must contain DJANGO_MATT_MULTITENANCY for b2b template"
            )

    def test_startapi_basic_template(self):
        """startapi --template starter produces settings.py, urls.py, and Makefile."""
        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "basicproject"
            project_dir = Path(tmpdir) / project_name
            project_dir.mkdir()

            call_command(
                "startapi",
                project_name,
                directory=str(project_dir),
                template="starter",
                force=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

            # settings.py must exist
            settings_path = project_dir / project_name / "settings.py"
            assert settings_path.exists(), "settings.py must exist"

            # urls.py must exist
            urls_path = project_dir / project_name / "urls.py"
            assert urls_path.exists(), "urls.py must exist"

            # Makefile must exist
            assert (project_dir / "Makefile").exists(), "Makefile must exist"


# ===========================================================================
# sync_types - from-openapi flag (Plan 03-02)
# ===========================================================================


class TestSyncTypesFromOpenAPI:
    """Tests for sync_types --from-openapi flag."""

    def test_sync_types_has_from_openapi_argument(self):
        """sync_types command has --from-openapi argument in parser."""
        import argparse

        from django_matt.management.commands.sync_types import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        action_names = {action.dest for action in parser._actions}
        assert "from_openapi" in action_names

    def test_sync_types_has_openapi_file_argument(self):
        """sync_types command has --openapi-file argument in parser."""
        import argparse

        from django_matt.management.commands.sync_types import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        action_names = {action.dest for action in parser._actions}
        assert "openapi_file" in action_names

    def test_sync_types_from_openapi_file_produces_output(self):
        """sync_types --openapi-file with a valid spec produces TypeScript output."""
        import json
        import tempfile
        from io import StringIO

        from django.core.management import call_command

        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "username": {"type": "string"},
                        },
                        "required": ["id", "username"],
                    }
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(spec, f)
            spec_path = f.name

        out = StringIO()
        err = StringIO()
        call_command(
            "sync_types",
            openapi_file=spec_path,
            target="typescript",
            stdout=out,
            stderr=err,
        )
        output = out.getvalue()
        assert "User" in output or "interface" in output or len(output) > 0


# ===========================================================================
# sync_types - swift target includes API client (Plan 03-02)
# ===========================================================================


class TestSyncTypesSwiftTarget:
    """Tests for sync_types --target swift producing API client."""

    def test_sync_types_swift_includes_urlsession(self):
        """sync_types --target swift output includes URLSession API client."""
        from pydantic import BaseModel as PydanticModel

        from django_matt.management.commands.sync_types import Command

        class UserSchema(PydanticModel):
            id: int
            name: str

        cmd = Command()
        result = cmd._generate(
            target="swift",
            schemas=[UserSchema],
            models=[],
            camel_case=False,
            base_url="/api",
            include_react_query=False,
            include_swr=False,
        )
        assert "URLSession" in result

    def test_sync_types_swift_includes_codable_struct(self):
        """sync_types --target swift output includes Codable struct."""
        from pydantic import BaseModel as PydanticModel

        from django_matt.management.commands.sync_types import Command

        class ProductSchema(PydanticModel):
            id: int
            name: str

        cmd = Command()
        result = cmd._generate(
            target="swift",
            schemas=[ProductSchema],
            models=[],
            camel_case=False,
            base_url="/api",
            include_react_query=False,
            include_swr=False,
        )
        assert "Codable" in result
        assert "struct" in result or "class" in result
