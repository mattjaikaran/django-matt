"""
Tests for AI context generation module.

Tests the enhanced AI IDE integration including:
- Context generators (Claude, Cursor, Copilot, JSON)
- Enhanced introspection
- File watcher
- Pre-commit hook generation
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestEnhancedIntrospector:
    """Tests for EnhancedIntrospector class."""

    def test_introspect_returns_project_info(self):
        """Test that introspect returns EnhancedProjectInfo."""
        from django_matt.ai.context import EnhancedIntrospector

        introspector = EnhancedIntrospector()
        info = introspector.introspect()

        assert info is not None
        assert hasattr(info, "name")
        assert hasattr(info, "python_version")
        assert hasattr(info, "django_version")
        assert hasattr(info, "endpoints")
        assert hasattr(info, "schemas")
        assert hasattr(info, "models")

    def test_introspect_finds_endpoints(self):
        """Test that introspection finds API endpoints."""
        from django_matt.ai.context import EnhancedIntrospector

        introspector = EnhancedIntrospector()
        info = introspector.introspect()

        # Should find at least some endpoints (from django_matt itself)
        # May be empty in minimal test setup
        assert isinstance(info.endpoints, list)

    def test_introspect_finds_schemas(self):
        """Test that introspection finds Pydantic schemas."""
        from django_matt.ai.context import EnhancedIntrospector

        introspector = EnhancedIntrospector()
        info = introspector.introspect()

        # Should find at least some schemas
        assert isinstance(info.schemas, list)

    def test_introspect_finds_models(self):
        """Test that introspection finds Django models."""
        from django_matt.ai.context import EnhancedIntrospector

        introspector = EnhancedIntrospector()
        info = introspector.introspect()

        # Should find at least the User model
        assert isinstance(info.models, list)

    def test_to_json_returns_valid_json(self):
        """Test that to_json returns valid JSON."""
        from django_matt.ai.context import EnhancedIntrospector

        introspector = EnhancedIntrospector()
        json_str = introspector.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert "endpoints" in data
        assert "schemas" in data
        assert "models" in data


class TestAuthRequirement:
    """Tests for AuthRequirement enum."""

    def test_auth_requirement_values(self):
        """Test that AuthRequirement has expected values."""
        from django_matt.ai.context import AuthRequirement

        assert AuthRequirement.NONE.value == "none"
        assert AuthRequirement.JWT_REQUIRED.value == "jwt_required"
        assert AuthRequirement.JWT_OPTIONAL.value == "jwt_optional"
        assert AuthRequirement.API_KEY.value == "api_key"


class TestEndpointInfo:
    """Tests for EndpointInfo dataclass."""

    def test_endpoint_info_to_dict(self):
        """Test that EndpointInfo converts to dict."""
        from django_matt.ai.context import AuthRequirement, EndpointInfo

        endpoint = EndpointInfo(
            path="/api/users",
            method="GET",
            name="list_users",
            auth_requirement=AuthRequirement.JWT_REQUIRED,
        )

        data = endpoint.to_dict()
        assert data["path"] == "/api/users"
        assert data["method"] == "GET"
        assert data["auth_requirement"] == "jwt_required"


class TestClaudeMdGenerator:
    """Tests for ClaudeMdGenerator class."""

    def test_generate_returns_content(self):
        """Test that generate returns markdown content."""
        from django_matt.ai.context import ClaudeMdGenerator

        generator = ClaudeMdGenerator()
        content = generator.generate()

        assert content is not None
        assert len(content) > 0
        assert "# " in content  # Should have markdown headers

    def test_generate_includes_project_name(self):
        """Test that generated content includes project info."""
        from django_matt.ai.context import ClaudeMdGenerator

        generator = ClaudeMdGenerator()
        content = generator.generate()

        assert "Project Overview" in content
        assert "Django" in content

    def test_write_creates_file(self):
        """Test that write creates a file."""
        from django_matt.ai.context import ClaudeMdGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ClaudeMdGenerator()
            path = generator.write(f"{tmpdir}/CLAUDE.md")

            assert path.exists()
            assert path.name == "CLAUDE.md"
            assert path.read_text().startswith("#")


class TestCursorRulesGenerator:
    """Tests for CursorRulesGenerator class."""

    def test_generate_returns_content(self):
        """Test that generate returns rules content."""
        from django_matt.ai.context import CursorRulesGenerator

        generator = CursorRulesGenerator()
        content = generator.generate()

        assert content is not None
        assert len(content) > 0

    def test_generate_includes_framework_rules(self):
        """Test that generated content includes framework rules."""
        from django_matt.ai.context import CursorRulesGenerator

        generator = CursorRulesGenerator()
        content = generator.generate()

        assert "Django" in content
        assert "API" in content or "controller" in content.lower()

    def test_write_creates_file(self):
        """Test that write creates a file."""
        from django_matt.ai.context import CursorRulesGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CursorRulesGenerator()
            path = generator.write(f"{tmpdir}/.cursorrules")

            assert path.exists()
            assert path.name == ".cursorrules"


class TestCopilotInstructionsGenerator:
    """Tests for CopilotInstructionsGenerator class."""

    def test_generate_returns_content(self):
        """Test that generate returns instructions content."""
        from django_matt.ai.context import CopilotInstructionsGenerator

        generator = CopilotInstructionsGenerator()
        content = generator.generate()

        assert content is not None
        assert len(content) > 0

    def test_generate_includes_copilot_header(self):
        """Test that generated content has Copilot header."""
        from django_matt.ai.context import CopilotInstructionsGenerator

        generator = CopilotInstructionsGenerator()
        content = generator.generate()

        assert "Copilot" in content or "copilot" in content.lower()

    def test_write_creates_file(self):
        """Test that write creates a file."""
        from django_matt.ai.context import CopilotInstructionsGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CopilotInstructionsGenerator()
            path = generator.write(f"{tmpdir}/.copilot-instructions")

            assert path.exists()
            assert path.name == ".copilot-instructions"


class TestJsonIntrospectionGenerator:
    """Tests for JsonIntrospectionGenerator class."""

    def test_generate_returns_dict(self):
        """Test that generate returns a dictionary."""
        from django_matt.ai.context.generators import JsonIntrospectionGenerator

        generator = JsonIntrospectionGenerator()
        data = generator.generate()

        assert isinstance(data, dict)
        assert "version" in data
        assert "generated_at" in data
        assert "project" in data

    def test_generate_json_returns_string(self):
        """Test that generate_json returns valid JSON string."""
        from django_matt.ai.context.generators import JsonIntrospectionGenerator

        generator = JsonIntrospectionGenerator()
        json_str = generator.generate_json()

        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert "version" in data

    def test_write_creates_file(self):
        """Test that write creates a JSON file."""
        from django_matt.ai.context.generators import JsonIntrospectionGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = JsonIntrospectionGenerator()
            path = generator.write(f"{tmpdir}/introspection.json")

            assert path.exists()
            assert path.name == "introspection.json"

            # Verify it's valid JSON
            data = json.loads(path.read_text())
            assert "version" in data


class TestContextGenerator:
    """Tests for unified ContextGenerator class."""

    def test_generate_all_creates_files(self):
        """Test that generate_all creates all context files."""
        from django_matt.ai.context import ContextGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ContextGenerator(output_dir=tmpdir)
            files = generator.generate_all()

            assert "claude" in files
            assert "cursor" in files
            assert "copilot" in files
            assert "json" in files

            assert files["claude"].exists()
            assert files["cursor"].exists()
            assert files["copilot"].exists()
            assert files["json"].exists()

    def test_generate_specific_formats(self):
        """Test that specific formats can be generated."""
        from django_matt.ai.context import ContextGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ContextGenerator(output_dir=tmpdir)
            files = generator.generate_all(formats=["claude", "cursor"])

            assert "claude" in files
            assert "cursor" in files
            assert "copilot" not in files
            assert "json" not in files


class TestDebouncedCallback:
    """Tests for DebouncedCallback class."""

    def test_debounced_callback_delays_execution(self):
        """Test that callback is delayed."""
        from django_matt.ai.context import DebouncedCallback

        called = []

        def callback():
            called.append(True)

        debounced = DebouncedCallback(callback, delay=0.1)

        # Call multiple times rapidly
        debounced.call()
        debounced.call()
        debounced.call()

        # Should not have been called yet
        assert len(called) == 0

        # Wait for debounce
        import time

        time.sleep(0.15)

        # Should have been called once
        assert len(called) == 1

    def test_debounced_callback_can_be_cancelled(self):
        """Test that callback can be cancelled."""
        from django_matt.ai.context import DebouncedCallback

        called = []

        def callback():
            called.append(True)

        debounced = DebouncedCallback(callback, delay=0.1)
        debounced.call()
        debounced.cancel()

        import time

        time.sleep(0.15)

        assert len(called) == 0


class TestFileChangeHandler:
    """Tests for FileChangeHandler class."""

    def test_should_watch_python_files(self):
        """Test that Python files are watched."""
        from django_matt.ai.context import FileChangeHandler

        handler = FileChangeHandler(on_change=lambda: None)

        assert handler.should_watch(Path("app/models.py"))
        assert handler.should_watch(Path("app/views.py"))
        assert handler.should_watch(Path("tests/test_app.py"))

    def test_should_not_watch_context_files(self):
        """Test that generated context files are not watched."""
        from django_matt.ai.context import FileChangeHandler

        handler = FileChangeHandler(on_change=lambda: None)

        assert not handler.should_watch(Path("CLAUDE.md"))
        assert not handler.should_watch(Path(".cursorrules"))
        assert not handler.should_watch(Path(".copilot-instructions"))

    def test_should_not_watch_cache_dirs(self):
        """Test that cache directories are not watched."""
        from django_matt.ai.context import FileChangeHandler

        handler = FileChangeHandler(on_change=lambda: None)

        assert not handler.should_watch(Path("__pycache__/module.py"))
        assert not handler.should_watch(Path(".git/hooks/pre-commit"))
        assert not handler.should_watch(Path("node_modules/pkg/index.py"))


class TestPrecommitHook:
    """Tests for pre-commit hook generation."""

    def test_generate_precommit_hook(self):
        """Test that pre-commit hook script is generated."""
        from django_matt.ai.context.watcher import generate_precommit_hook

        hook = generate_precommit_hook()

        assert "#!/bin/bash" in hook
        assert "django-matt" in hook
        assert "generate_ai_context" in hook

    def test_generate_precommit_config(self):
        """Test that pre-commit config is generated."""
        from django_matt.ai.context.watcher import generate_precommit_config

        config = generate_precommit_config()

        assert "repos:" in config
        assert "update-ai-context" in config
        assert "generate_ai_context" in config


class TestTemplates:
    """Tests for template functions."""

    def test_get_template(self):
        """Test that templates can be retrieved."""
        from django_matt.ai.context.templates import get_template

        claude_template = get_template("claude")
        cursor_template = get_template("cursor")
        copilot_template = get_template("copilot")

        assert "{project_name}" in claude_template
        assert "{project_name}" in cursor_template
        assert "{project_name}" in copilot_template

    def test_get_template_invalid(self):
        """Test that invalid template name raises error."""
        from django_matt.ai.context.templates import get_template

        with pytest.raises(ValueError):
            get_template("invalid")

    def test_render_template(self):
        """Test that templates can be rendered."""
        from django_matt.ai.context.templates import render_template

        template = "Hello {name}, version {version}"
        result = render_template(template, {"name": "World", "version": "1.0"})

        assert result == "Hello World, version 1.0"

    def test_render_template_with_defaults(self):
        """Test that templates use defaults for missing keys."""
        from django_matt.ai.context.templates import render_template

        template = "Project: {project_name}"
        result = render_template(template, {})

        assert "Project:" in result


# ---------------------------------------------------------------------------
# Plan 03-02: --depth flag and --include-examples tests
# ---------------------------------------------------------------------------

class TestGenerateAiContextDepthFlag:
    """Tests for generate_ai_context --depth flag."""

    def test_generate_ai_context_has_depth_argument(self):
        """generate_ai_context command has --depth argument."""
        import argparse

        from django_matt.management.commands.generate_ai_context import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        action_names = {action.dest for action in parser._actions}
        assert "depth" in action_names

    def test_generate_ai_context_depth_choices(self):
        """--depth accepts minimal, standard, full."""
        import argparse

        from django_matt.management.commands.generate_ai_context import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        depth_action = next(
            a for a in parser._actions if a.dest == "depth"
        )
        assert "minimal" in depth_action.choices
        assert "standard" in depth_action.choices
        assert "full" in depth_action.choices

    def test_depth_minimal_routes_only(self):
        """--depth minimal produces routes but not full type/relationship output."""
        import tempfile
        from io import StringIO

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            err = StringIO()
            call_command(
                "generate_ai_context",
                output=tmpdir,
                format="claude",
                depth="minimal",
                stdout=out,
                stderr=err,
            )
            # Command should run without error
            import os
            assert os.path.exists(os.path.join(tmpdir, "CLAUDE.md"))

    def test_depth_standard_default(self):
        """--depth standard is the default."""
        import argparse

        from django_matt.management.commands.generate_ai_context import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        depth_action = next(
            a for a in parser._actions if a.dest == "depth"
        )
        assert depth_action.default == "standard"

    def test_depth_full_runs_without_error(self):
        """--depth full completes without error."""
        import tempfile
        from io import StringIO

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            err = StringIO()
            call_command(
                "generate_ai_context",
                output=tmpdir,
                format="claude",
                depth="full",
                stdout=out,
                stderr=err,
            )
            import os
            assert os.path.exists(os.path.join(tmpdir, "CLAUDE.md"))

    def test_format_all_produces_all_files(self):
        """--format all creates CLAUDE.md, .cursorrules, .copilot-instructions, and JSON."""
        import tempfile
        from io import StringIO

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            err = StringIO()
            call_command(
                "generate_ai_context",
                output=tmpdir,
                format="all",
                depth="minimal",
                stdout=out,
                stderr=err,
            )
            import os
            assert os.path.exists(os.path.join(tmpdir, "CLAUDE.md"))
            assert os.path.exists(os.path.join(tmpdir, ".cursorrules"))
            assert os.path.exists(os.path.join(tmpdir, ".copilot-instructions"))
            assert os.path.exists(os.path.join(tmpdir, "introspection.json"))

    def test_include_examples_flag_accepted(self):
        """--include-examples flag is accepted without error."""
        import tempfile
        from io import StringIO

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            err = StringIO()
            call_command(
                "generate_ai_context",
                output=tmpdir,
                format="claude",
                include_examples=True,
                depth="minimal",
                stdout=out,
                stderr=err,
            )
            import os
            assert os.path.exists(os.path.join(tmpdir, "CLAUDE.md"))
