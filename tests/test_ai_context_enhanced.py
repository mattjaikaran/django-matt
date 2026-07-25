"""Tests for enhanced AI context generation — introspection, templates, generators."""

from unittest.mock import MagicMock, patch

import pytest


class TestNewDataclasses:
    """Test the new dataclasses added to introspection."""

    def test_service_info(self):
        """ServiceInfo should serialize correctly."""
        from django_matt.ai.context.introspection import ServiceInfo

        svc = ServiceInfo(
            name="UserService",
            module="myapp.services",
            methods=[
                {
                    "name": "create_user",
                    "is_async": True,
                    "params": [{"name": "data", "type": "dict"}],
                    "return_type": "User",
                },
            ],
            is_async=True,
            docstring="User management service.",
        )
        d = svc.to_dict()
        assert d["name"] == "UserService"
        assert d["module"] == "myapp.services"
        assert d["is_async"] is True
        assert len(d["methods"]) == 1
        assert d["methods"][0]["name"] == "create_user"

    def test_async_warning(self):
        """AsyncWarning should serialize correctly."""
        from django_matt.ai.context.introspection import AsyncWarning

        w = AsyncWarning(
            file="myapp/views.py",
            line=42,
            function="list_users",
            issue="Sync ORM call .get() in async function",
            suggestion="Use .aget() instead",
        )
        d = w.to_dict()
        assert d["file"] == "myapp/views.py"
        assert d["line"] == 42
        assert d["function"] == "list_users"
        assert "Sync ORM" in d["issue"]

    def test_environment_var(self):
        """EnvironmentVar should serialize correctly."""
        from django_matt.ai.context.introspection import EnvironmentVar

        var = EnvironmentVar(
            name="DATABASE_URL",
            default=None,
            required=True,
            source_file="config/settings.py",
        )
        d = var.to_dict()
        assert d["name"] == "DATABASE_URL"
        assert d["required"] is True
        assert d["default"] is None

    def test_environment_var_optional(self):
        """EnvironmentVar with default should be optional."""
        from django_matt.ai.context.introspection import EnvironmentVar

        var = EnvironmentVar(
            name="DEBUG",
            default="False",
            required=False,
            source_file="settings.py",
        )
        d = var.to_dict()
        assert d["required"] is False
        assert d["default"] == "False"

    def test_enhanced_project_info_has_new_fields(self):
        """EnhancedProjectInfo should include services, environment, async_warnings."""
        from django_matt.ai.context.introspection import EnhancedProjectInfo

        info = EnhancedProjectInfo(
            name="test",
            root_path="/tmp/test",
            python_version="3.12.0",
            django_version="5.2",
        )
        d = info.to_dict()
        assert "services" in d
        assert "environment" in d
        assert "async_warnings" in d
        assert isinstance(d["services"], list)
        assert isinstance(d["environment"], list)
        assert isinstance(d["async_warnings"], list)


class TestFormatFunctions:
    """Test the new template format functions."""

    def test_format_async_safety_section_no_warnings(self):
        """Async safety section should render even with no warnings."""
        from django_matt.ai.context.templates import format_async_safety_section

        result = format_async_safety_section([], [])
        assert "Async Safety Guide" in result
        assert "NEVER" in result
        assert ".aget()" in result
        assert "sync_to_async" in result

    def test_format_async_safety_section_with_warnings(self):
        """Async safety section should show warning count."""
        from django_matt.ai.context.templates import format_async_safety_section

        warnings = [
            {
                "file": "views.py",
                "line": 10,
                "function": "list_users",
                "issue": "Sync .get()",
                "suggestion": "Use .aget()",
            },
            {
                "file": "views.py",
                "line": 20,
                "function": "create_user",
                "issue": "Sync .save()",
                "suggestion": "Use .asave()",
            },
        ]
        result = format_async_safety_section(warnings, [])
        assert "2 detected" in result
        assert "views.py:10" in result

    def test_format_error_handling_section(self):
        """Error handling section should include framework error classes."""
        from django_matt.ai.context.templates import format_error_handling_section

        result = format_error_handling_section({})
        assert "Error Handling" in result
        assert "ValidationAPIError" in result
        assert "NotFoundAPIError" in result
        assert "APIError" in result

    def test_format_service_layer_section_empty(self):
        """Service layer section should be empty when no services."""
        from django_matt.ai.context.templates import format_service_layer_section

        result = format_service_layer_section([])
        assert result == ""

    def test_format_service_layer_section_with_services(self):
        """Service layer section should list service methods."""
        from django_matt.ai.context.templates import format_service_layer_section

        services = [
            {
                "name": "UserService",
                "module": "myapp.services",
                "is_async": True,
                "docstring": "Handles user operations.",
                "methods": [
                    {
                        "name": "create_user",
                        "is_async": True,
                        "params": [{"name": "data"}],
                        "return_type": "User",
                    },
                    {
                        "name": "get_user",
                        "is_async": True,
                        "params": [{"name": "pk"}],
                        "return_type": "User",
                    },
                ],
            }
        ]
        result = format_service_layer_section(services)
        assert "Service Layer" in result
        assert "UserService" in result
        assert "async" in result.lower()
        assert "create_user" in result
        assert "get_user" in result

    def test_format_environment_section_empty(self):
        """Environment section should be empty when no vars."""
        from django_matt.ai.context.templates import format_environment_section

        result = format_environment_section([])
        assert result == ""

    def test_format_environment_section_with_vars(self):
        """Environment section should show required and optional vars."""
        from django_matt.ai.context.templates import format_environment_section

        env_vars = [
            {"name": "SECRET_KEY", "default": None, "required": True, "source_file": "settings.py"},
            {"name": "DEBUG", "default": "False", "required": False, "source_file": "settings.py"},
        ]
        result = format_environment_section(env_vars)
        assert "Environment Variables" in result
        assert "SECRET_KEY" in result
        assert "Required" in result
        assert "Optional" in result
        assert "DEBUG" in result

    def test_format_async_safety_rules(self):
        """Async safety rules for Cursor should list ORM mappings."""
        from django_matt.ai.context.templates import format_async_safety_rules

        result = format_async_safety_rules([])
        assert ".get() -> .aget()" in result
        assert ".filter() -> .afilter()" in result
        assert "sync_to_async" in result

    def test_format_async_safety_rules_with_warnings(self):
        """Async safety rules should note detected issues."""
        from django_matt.ai.context.templates import format_async_safety_rules

        warnings = [
            {"file": "views.py", "line": 1, "function": "f", "issue": "x", "suggestion": "y"}
        ]
        result = format_async_safety_rules(warnings)
        assert "1 async safety issue(s)" in result


class TestRenderTemplateDefaults:
    """Test that render_template has defaults for all new keys."""

    def test_new_keys_have_defaults(self):
        """All new template keys should have defaults in render_template."""
        from django_matt.ai.context.templates import render_template

        # A template that uses all new keys
        template = (
            "{async_safety_section}"
            "{error_handling_section}"
            "{service_layer_section}"
            "{environment_section}"
            "{async_safety_rules}"
            "{async_patterns_context}"
            "{error_handling_context}"
        )
        result = render_template(template, {})
        # All should render to empty string (defaults)
        assert result == ""


class TestGeneratorWiring:
    """Test that generators pass new sections to templates."""

    def test_claude_md_generator_has_new_sections(self):
        """ClaudeMdGenerator should populate async_safety and error_handling."""
        from django_matt.ai.context.generators import ClaudeMdGenerator
        from django_matt.ai.context.introspection import EnhancedProjectInfo

        info = EnhancedProjectInfo(
            name="testproject",
            root_path="/tmp/test",
            python_version="3.12.0",
            django_version="5.2",
        )
        generator = ClaudeMdGenerator()
        # Mock the structure generation since it needs Django apps
        with patch.object(generator, "_generate_structure", return_value="## Structure"):
            content = generator.generate(project_info=info)
        assert "Async Safety Guide" in content
        assert "Error Handling" in content

    def test_cursor_rules_generator_has_async_rules(self):
        """CursorRulesGenerator should include async safety rules."""
        from django_matt.ai.context.generators import CursorRulesGenerator
        from django_matt.ai.context.introspection import EnhancedProjectInfo

        info = EnhancedProjectInfo(
            name="testproject",
            root_path="/tmp/test",
            python_version="3.12.0",
            django_version="5.2",
        )
        generator = CursorRulesGenerator()
        content = generator.generate(project_info=info)
        assert ".get() -> .aget()" in content

    def test_copilot_generator_has_async_patterns(self):
        """CopilotInstructionsGenerator should include async patterns and error handling."""
        from django_matt.ai.context.generators import CopilotInstructionsGenerator
        from django_matt.ai.context.introspection import EnhancedProjectInfo

        info = EnhancedProjectInfo(
            name="testproject",
            root_path="/tmp/test",
            python_version="3.12.0",
            django_version="5.2",
        )
        generator = CopilotInstructionsGenerator()
        content = generator.generate(project_info=info)
        assert "Async Safety Patterns" in content
        assert "Error Handling Patterns" in content
        assert "ValidationAPIError" in content
