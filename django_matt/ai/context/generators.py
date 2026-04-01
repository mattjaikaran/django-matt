"""
Enhanced AI context file generators.

Generates CLAUDE.md, .cursorrules, .copilot-instructions, and JSON
introspection endpoints from Django project introspection data.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import orjson

from django_matt.ai.context.introspection import EnhancedIntrospector, EnhancedProjectInfo
from django_matt.ai.context.templates import (
    CLAUDE_MD_TEMPLATE,
    COPILOT_INSTRUCTIONS_TEMPLATE,
    CURSOR_RULES_TEMPLATE,
    format_async_safety_rules,
    format_async_safety_section,
    format_auth_section,
    format_code_examples_section,
    format_endpoints_rules,
    format_endpoints_section,
    format_environment_section,
    format_error_handling_section,
    format_llm_prompt,
    format_models_rules,
    format_models_section,
    format_schema_rules,
    format_schemas_section,
    format_service_layer_section,
    format_tech_stack,
    format_test_patterns_section,
    render_template,
)


class ClaudeMdGenerator:
    """
    Generates enhanced CLAUDE.md files for Claude Code.

    Creates comprehensive project context including:
    - Project overview and tech stack
    - All API endpoints with auth requirements
    - All Pydantic schemas with field types
    - Django models with relationships
    - Code examples from the codebase
    - Test patterns

    Usage:
        generator = ClaudeMdGenerator()
        content = generator.generate()
        generator.write("CLAUDE.md")
    """

    def __init__(
        self,
        introspector: EnhancedIntrospector | None = None,
        include_examples: bool = True,
        max_endpoints: int = 50,
        max_models: int = 30,
        max_schemas: int = 30,
    ):
        """
        Initialize generator.

        Args:
            introspector: Enhanced introspector instance
            include_examples: Include code examples from codebase
            max_endpoints: Maximum endpoints to include
            max_models: Maximum models to include
            max_schemas: Maximum schemas to include
        """
        self.introspector = introspector or EnhancedIntrospector(include_examples=include_examples)
        self.include_examples = include_examples
        self.max_endpoints = max_endpoints
        self.max_models = max_models
        self.max_schemas = max_schemas

    def generate(self, project_info: EnhancedProjectInfo | None = None) -> str:
        """Generate CLAUDE.md content."""
        if project_info is None:
            project_info = self.introspector.introspect()

        info_dict = project_info.to_dict()

        # Prepare serialized data
        endpoint_dicts = [e.to_dict() for e in project_info.endpoints]
        async_warning_dicts = [w.to_dict() for w in project_info.async_warnings]
        service_dicts = [s.to_dict() for s in project_info.services]
        env_dicts = [e.to_dict() for e in project_info.environment]

        # Build context for template
        context = {
            "project_name": project_info.name,
            "generated_date": datetime.now().strftime("%Y-%m-%d"),
            "python_version": project_info.python_version,
            "django_version": project_info.django_version,
            "settings_module": project_info.settings_module,
            "tech_stack_section": format_tech_stack(info_dict),
            "structure_section": self._generate_structure(project_info),
            "models_section": format_models_section(info_dict["models"], self.max_models),
            "endpoints_section": format_endpoints_section(endpoint_dicts, self.max_endpoints),
            "schemas_section": format_schemas_section(
                [s.to_dict() for s in project_info.schemas], self.max_schemas
            ),
            "auth_section": format_auth_section(endpoint_dicts),
            "async_safety_section": format_async_safety_section(
                async_warning_dicts, endpoint_dicts
            ),
            "error_handling_section": format_error_handling_section(info_dict),
            "service_layer_section": format_service_layer_section(service_dicts),
            "environment_section": format_environment_section(env_dicts),
            "test_patterns_section": format_test_patterns_section(
                project_info.test_patterns.to_dict() if project_info.test_patterns else None
            ),
            "code_examples_section": (
                format_code_examples_section(project_info.code_examples)
                if self.include_examples
                else ""
            ),
            "important_files": self._generate_important_files(project_info),
        }

        return render_template(CLAUDE_MD_TEMPLATE, context)

    def _generate_structure(self, info: EnhancedProjectInfo) -> str:
        """Generate project structure section."""
        from django_matt.ai.ide.introspection import get_project_structure

        structure = get_project_structure(info.root_path)

        def format_tree(tree: dict[str, Any], prefix: str = "") -> list[str]:
            lines = []
            items = list(tree.items())

            for i, (name, children) in enumerate(items):
                is_last = i == len(items) - 1
                connector = "-> " if is_last else "|-- "
                lines.append(f"{prefix}{connector}{name}")

                if children:
                    extension = "    " if is_last else "|   "
                    lines.extend(format_tree(children, prefix + extension))

            return lines

        tree_lines = format_tree(structure)

        if len(tree_lines) > 60:
            tree_lines = tree_lines[:60] + ["    ... (truncated)"]

        return "## Project Structure\n\n```\n" + "\n".join(tree_lines) + "\n```"

    def _generate_important_files(self, info: EnhancedProjectInfo) -> str:
        """Generate important files section."""
        files = [
            "- `manage.py` - Django management script",
            f"- `{info.settings_module.replace('.', '/')}.py` - Django settings"
            if info.settings_module
            else "",
            "- `pyproject.toml` - Project configuration",
        ]

        # Add app files
        for app in info.installed_apps[:5]:
            if not app.startswith("django."):
                files.append(f"- `{app.replace('.', '/')}/` - App module")

        return "\n".join(f for f in files if f)

    def write(self, path: str = "CLAUDE.md") -> Path:
        """Generate and write to file."""
        content = self.generate()
        file_path = Path(path)
        file_path.write_text(content)
        return file_path


class CursorRulesGenerator:
    """
    Generates enhanced .cursorrules files for Cursor IDE.

    Creates project-specific rules including:
    - Framework conventions
    - Available models and endpoints
    - Schema information
    - Import preferences

    Usage:
        generator = CursorRulesGenerator()
        content = generator.generate()
        generator.write(".cursorrules")
    """

    def __init__(
        self,
        introspector: EnhancedIntrospector | None = None,
    ):
        """
        Initialize generator.

        Args:
            introspector: Enhanced introspector instance
        """
        self.introspector = introspector or EnhancedIntrospector()

    def generate(self, project_info: EnhancedProjectInfo | None = None) -> str:
        """Generate .cursorrules content."""
        if project_info is None:
            project_info = self.introspector.introspect()

        context = {
            "project_name": project_info.name,
            "generated_date": datetime.now().strftime("%Y-%m-%d"),
            "python_version": project_info.python_version,
            "django_version": project_info.django_version,
            "models_rules": format_models_rules(project_info.models),
            "endpoints_rules": format_endpoints_rules(
                [e.to_dict() for e in project_info.endpoints]
            ),
            "schema_rules": format_schema_rules([s.to_dict() for s in project_info.schemas]),
            "async_safety_rules": format_async_safety_rules(
                [w.to_dict() for w in project_info.async_warnings]
            ),
        }

        return render_template(CURSOR_RULES_TEMPLATE, context)

    def write(self, path: str = ".cursorrules") -> Path:
        """Generate and write to file."""
        content = self.generate()
        file_path = Path(path)
        file_path.write_text(content)
        return file_path


class CopilotInstructionsGenerator:
    """
    Generates .copilot-instructions files for GitHub Copilot.

    Creates Copilot-specific instructions including:
    - Project context and guidelines
    - Code style examples
    - Model and endpoint context
    - Common patterns

    Usage:
        generator = CopilotInstructionsGenerator()
        content = generator.generate()
        generator.write(".copilot-instructions")
    """

    def __init__(
        self,
        introspector: EnhancedIntrospector | None = None,
    ):
        """
        Initialize generator.

        Args:
            introspector: Enhanced introspector instance
        """
        self.introspector = introspector or EnhancedIntrospector()

    def generate(self, project_info: EnhancedProjectInfo | None = None) -> str:
        """Generate .copilot-instructions content."""
        if project_info is None:
            project_info = self.introspector.introspect()

        context = {
            "project_name": project_info.name,
            "generated_date": datetime.now().strftime("%Y-%m-%d"),
            "python_version": project_info.python_version,
            "django_version": project_info.django_version,
            "models_context": self._format_models_context(project_info.models),
            "endpoints_context": self._format_endpoints_context(project_info.endpoints),
            "schemas_context": self._format_schemas_context(project_info.schemas),
            "async_patterns_context": self._format_async_patterns_context(
                project_info.async_warnings
            ),
            "error_handling_context": self._format_error_handling_context(),
        }

        return render_template(COPILOT_INSTRUCTIONS_TEMPLATE, context)

    def _format_models_context(self, models: list[dict[str, Any]]) -> str:
        """Format models context for Copilot."""
        if not models:
            return ""

        lines = ["## Available Models", ""]
        for model in models[:15]:
            lines.append(f"### {model['app_label']}.{model['name']}")
            lines.append("Fields:")
            for field in model.get("fields", [])[:8]:
                lines.append(f"  - {field['name']}: {field['type']}")
            lines.append("")

        return "\n".join(lines)

    def _format_endpoints_context(self, endpoints: list) -> str:
        """Format endpoints context for Copilot."""
        if not endpoints:
            return ""

        lines = ["## Available Endpoints", ""]
        for ep in endpoints[:20]:
            auth = (
                f" (requires: {ep.auth_requirement.value})"
                if ep.auth_requirement.value != "none"
                else ""
            )
            lines.append(f"- `{ep.method} {ep.path}`{auth}")

        return "\n".join(lines)

    def _format_schemas_context(self, schemas: list) -> str:
        """Format schemas context for Copilot."""
        if not schemas:
            return ""

        lines = ["## Available Schemas", ""]
        for schema in schemas[:15]:
            lines.append(f"### {schema.name}")
            lines.append("Fields:")
            for field in schema.fields[:6]:
                req = "(required)" if field.required else "(optional)"
                lines.append(f"  - {field.name}: {field.field_type} {req}")
            lines.append("")

        return "\n".join(lines)

    def _format_async_patterns_context(self, async_warnings: list) -> str:
        """Format async safety patterns for Copilot."""
        lines = ["## Async Safety Patterns", ""]
        lines.append("When writing async views, ALWAYS use async ORM methods:")
        lines.append("```python")
        lines.append("# CORRECT")
        lines.append("async def my_view(request):")
        lines.append("    items = await MyModel.objects.afilter(active=True)")
        lines.append("    item = await MyModel.objects.aget(pk=pk)")
        lines.append("    await item.asave()")
        lines.append("")
        lines.append("# WRONG - will block the event loop")
        lines.append("async def my_view(request):")
        lines.append("    items = MyModel.objects.filter(active=True)  # sync!")
        lines.append("```")

        if async_warnings:
            lines.append("")
            lines.append(f"Note: {len(async_warnings)} async safety issue(s) detected in this project")

        return "\n".join(lines)

    def _format_error_handling_context(self) -> str:
        """Format error handling patterns for Copilot."""
        lines = ["## Error Handling Patterns", ""]
        lines.append("Use framework error classes for consistent API responses:")
        lines.append("```python")
        lines.append("from django_matt.core.errors import (")
        lines.append("    ValidationAPIError,  # 400")
        lines.append("    NotFoundAPIError,    # 404")
        lines.append("    APIError,            # Custom status")
        lines.append(")")
        lines.append("")
        lines.append("# Framework auto-wraps these into JSON responses")
        lines.append("raise NotFoundAPIError(f'User {pk} not found')")
        lines.append("raise ValidationAPIError('Invalid email', field='email')")
        lines.append("```")

        return "\n".join(lines)

    def write(self, path: str = ".copilot-instructions") -> Path:
        """Generate and write to file."""
        content = self.generate()
        file_path = Path(path)
        file_path.write_text(content)
        return file_path


class JsonIntrospectionGenerator:
    """
    Generates machine-readable JSON introspection data.

    Creates comprehensive JSON output suitable for:
    - API endpoints (/_matt/introspection)
    - Build tools and CI/CD
    - Custom tooling integration

    Usage:
        generator = JsonIntrospectionGenerator()
        data = generator.generate()
        generator.write("introspection.json")
    """

    def __init__(
        self,
        introspector: EnhancedIntrospector | None = None,
    ):
        """
        Initialize generator.

        Args:
            introspector: Enhanced introspector instance
        """
        self.introspector = introspector or EnhancedIntrospector()

    def generate(self, project_info: EnhancedProjectInfo | None = None) -> dict[str, Any]:
        """Generate introspection data as dictionary."""
        if project_info is None:
            project_info = self.introspector.introspect()

        return {
            "version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "project": project_info.to_dict(),
        }

    def generate_json(self, project_info: EnhancedProjectInfo | None = None) -> str:
        """Generate introspection data as JSON string."""
        data = self.generate(project_info)
        return orjson.dumps(data, default=str, option=orjson.OPT_INDENT_2).decode()

    def write(self, path: str = "introspection.json") -> Path:
        """Generate and write to file."""
        content = self.generate_json()
        file_path = Path(path)
        file_path.write_text(content)
        return file_path


class LlmPromptGenerator:
    """
    Generates a self-contained LLM system prompt for code generation.

    Creates a project-specific system prompt that any LLM can consume
    to generate correct django-matt code. Includes models, endpoints,
    schemas, auth patterns, async safety rules, and anti-patterns.

    Usage:
        generator = LlmPromptGenerator()
        prompt = generator.generate()
        generator.write("LLM-PROMPT.md")
    """

    def __init__(
        self,
        introspector: EnhancedIntrospector | None = None,
    ):
        self.introspector = introspector or EnhancedIntrospector()

    def generate(self, project_info: EnhancedProjectInfo | None = None) -> str:
        """Generate LLM system prompt content."""
        if project_info is None:
            project_info = self.introspector.introspect()

        info_dict = project_info.to_dict()
        endpoint_dicts = [e.to_dict() for e in project_info.endpoints]
        async_warning_dicts = [w.to_dict() for w in project_info.async_warnings]
        service_dicts = [s.to_dict() for s in project_info.services]
        env_dicts = [e.to_dict() for e in project_info.environment]

        return format_llm_prompt(
            project_info=info_dict,
            models=info_dict["models"],
            endpoints=endpoint_dicts,
            schemas=[s.to_dict() for s in project_info.schemas],
            async_warnings=async_warning_dicts,
            services=service_dicts,
            environment=env_dicts,
            test_patterns=(
                project_info.test_patterns.to_dict() if project_info.test_patterns else None
            ),
        )

    def write(self, path: str = "LLM-PROMPT.md") -> Path:
        """Generate and write to file."""
        content = self.generate()
        file_path = Path(path)
        file_path.write_text(content)
        return file_path


class ContextGenerator:
    """
    Unified generator for all AI context files.

    Generates multiple context files in one operation:
    - CLAUDE.md for Claude Code
    - .cursorrules for Cursor IDE
    - .copilot-instructions for GitHub Copilot
    - introspection.json for machine consumption

    Usage:
        generator = ContextGenerator()
        files = generator.generate_all()

        # Or generate specific files
        generator.generate_claude_md()
        generator.generate_cursorrules()
        generator.generate_copilot_instructions()
        generator.generate_json()
    """

    def __init__(
        self,
        output_dir: str | Path | None = None,
        include_third_party: bool = False,
        include_examples: bool = True,
    ):
        """
        Initialize generator.

        Args:
            output_dir: Directory for output files (default: project root)
            include_third_party: Include third-party apps in analysis
            include_examples: Include code examples from codebase
        """
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.introspector = EnhancedIntrospector(
            include_third_party=include_third_party,
            include_examples=include_examples,
        )
        self._project_info: EnhancedProjectInfo | None = None

    @property
    def project_info(self) -> EnhancedProjectInfo:
        """Get cached project info."""
        if self._project_info is None:
            self._project_info = self.introspector.introspect()
        return self._project_info

    def generate_claude_md(self, filename: str = "CLAUDE.md") -> Path:
        """Generate CLAUDE.md file."""
        generator = ClaudeMdGenerator(introspector=self.introspector)
        content = generator.generate(self.project_info)

        path = self.output_dir / filename
        path.write_text(content)
        return path

    def generate_cursorrules(self, filename: str = ".cursorrules") -> Path:
        """Generate .cursorrules file."""
        generator = CursorRulesGenerator(introspector=self.introspector)
        content = generator.generate(self.project_info)

        path = self.output_dir / filename
        path.write_text(content)
        return path

    def generate_copilot_instructions(self, filename: str = ".copilot-instructions") -> Path:
        """Generate .copilot-instructions file."""
        generator = CopilotInstructionsGenerator(introspector=self.introspector)
        content = generator.generate(self.project_info)

        path = self.output_dir / filename
        path.write_text(content)
        return path

    def generate_json(self, filename: str = "introspection.json") -> Path:
        """Generate introspection.json file."""
        generator = JsonIntrospectionGenerator(introspector=self.introspector)
        content = generator.generate_json(self.project_info)

        path = self.output_dir / filename
        path.write_text(content)
        return path

    def generate_llm_prompt(self, filename: str = "LLM-PROMPT.md") -> Path:
        """Generate LLM system prompt file."""
        generator = LlmPromptGenerator(introspector=self.introspector)
        content = generator.generate(self.project_info)

        path = self.output_dir / filename
        path.write_text(content)
        return path

    def generate_all(self, formats: list[str] | None = None) -> dict[str, Path]:
        """
        Generate all or selected context files.

        Args:
            formats: List of formats to generate.
                    Options: claude, cursor, copilot, json, llm
                    If None, generates all formats.

        Returns:
            Dictionary mapping format names to file paths
        """
        if formats is None:
            formats = ["claude", "cursor", "copilot", "json", "llm"]

        generated = {}

        if "claude" in formats:
            generated["claude"] = self.generate_claude_md()

        if "cursor" in formats:
            generated["cursor"] = self.generate_cursorrules()

        if "copilot" in formats:
            generated["copilot"] = self.generate_copilot_instructions()

        if "json" in formats:
            generated["json"] = self.generate_json()

        if "llm" in formats:
            generated["llm"] = self.generate_llm_prompt()

        return generated


__all__ = [
    "ClaudeMdGenerator",
    "ContextGenerator",
    "CopilotInstructionsGenerator",
    "CursorRulesGenerator",
    "JsonIntrospectionGenerator",
    "LlmPromptGenerator",
]
