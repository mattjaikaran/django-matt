"""
AI IDE Integration.

Tools for generating context files that help AI assistants
understand Django projects.

Generates:
- CLAUDE.md - Project context for Claude Code
- .cursorrules - Rules for Cursor IDE
- API documentation for AI consumption

Usage:
    from django_matt.ai.ide import AIContextGenerator

    # Generate all context files
    generator = AIContextGenerator()
    files = generator.generate_all()
    print(f"Generated: {files}")

    # Or generate specific files
    generator.generate_claude_md()
    generator.generate_cursorrules()

    # Use introspection directly
    from django_matt.ai.ide import ProjectIntrospector

    introspector = ProjectIntrospector()
    info = introspector.introspect()
    print(f"Found {len(info.apps)} apps")

Management Command:
    python manage.py generate_ai_context
    python manage.py generate_ai_context --output ./docs
    python manage.py generate_ai_context --format claude
"""

from django_matt.ai.ide.generators import (
    AIContextGenerator,
    ClaudeMdGenerator,
    CursorRulesGenerator,
)
from django_matt.ai.ide.introspection import (
    AppInfo,
    FieldInfo,
    ModelInfo,
    ProjectInfo,
    ProjectIntrospector,
    URLInfo,
    ViewInfo,
    get_project_structure,
)

__all__ = [
    # Introspection
    "FieldInfo",
    "ModelInfo",
    "ViewInfo",
    "URLInfo",
    "AppInfo",
    "ProjectInfo",
    "ProjectIntrospector",
    "get_project_structure",
    # Generators
    "ClaudeMdGenerator",
    "CursorRulesGenerator",
    "AIContextGenerator",
]
