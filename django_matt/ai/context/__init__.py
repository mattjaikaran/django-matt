"""
AI Context Generation Module.

Enhanced context generation for AI IDE integrations including
Claude Code, Cursor IDE, and GitHub Copilot.

Features:
- Generate context files for multiple AI assistants
- Deep project introspection with endpoint detection
- Pydantic schema extraction with field types
- Django model relationship mapping
- Authentication requirement detection per endpoint
- Example request/response generation
- Machine-readable JSON introspection endpoint
- File watching with debounced auto-updates
- Pre-commit hook support
- MCP server generation from introspection

Usage:
    from django_matt.ai.context import (
        ContextGenerator,
        EnhancedIntrospector,
        ContextWatcher,
    )

    # Generate all context files
    generator = ContextGenerator()
    files = generator.generate_all()

    # Start file watcher for auto-updates
    watcher = ContextWatcher()
    watcher.start()

Management Commands:
    python manage.py generate_ai_context --format all
    python manage.py generate_ai_context --watch
    python manage.py generate_ai_context --include-examples
    python manage.py generate_ai_context --output-json
    python manage.py generate_mcp_server
    python manage.py generate_mcp_server --base-url https://api.example.com
"""

from django_matt.ai.context.generators import (
    ClaudeMdGenerator,
    ContextGenerator,
    CopilotInstructionsGenerator,
    CursorRulesGenerator,
    JsonIntrospectionGenerator,
    LlmPromptGenerator,
)
from django_matt.ai.context.introspection import (
    AuthRequirement,
    EndpointInfo,
    EnhancedIntrospector,
    ExamplePayload,
    PydanticSchemaInfo,
    SchemaFieldInfo,
    TestPatternInfo,
)
from django_matt.ai.context.mcp import (
    generate_mcp_server,
    write_mcp_server,
)
from django_matt.ai.context.templates import (
    CLAUDE_MD_TEMPLATE,
    COPILOT_INSTRUCTIONS_TEMPLATE,
    CURSOR_RULES_TEMPLATE,
    LLM_SYSTEM_PROMPT_TEMPLATE,
    format_llm_prompt,
    get_template,
    render_template,
)
from django_matt.ai.context.watcher import (
    ContextWatcher,
    DebouncedCallback,
    FileChangeHandler,
    generate_precommit_config,
    generate_precommit_hook,
    install_precommit_hook,
)

# Views are imported lazily to avoid Django import issues
# Use: from django_matt.ai.context.views import urlpatterns

__all__ = [
    # Generators
    "ClaudeMdGenerator",
    "CursorRulesGenerator",
    "CopilotInstructionsGenerator",
    "JsonIntrospectionGenerator",
    "LlmPromptGenerator",
    "ContextGenerator",
    # Introspection
    "EnhancedIntrospector",
    "EndpointInfo",
    "AuthRequirement",
    "ExamplePayload",
    "PydanticSchemaInfo",
    "SchemaFieldInfo",
    "TestPatternInfo",
    # Templates
    "CLAUDE_MD_TEMPLATE",
    "CURSOR_RULES_TEMPLATE",
    "COPILOT_INSTRUCTIONS_TEMPLATE",
    "LLM_SYSTEM_PROMPT_TEMPLATE",
    "format_llm_prompt",
    "get_template",
    "render_template",
    # Watcher
    "ContextWatcher",
    "FileChangeHandler",
    "DebouncedCallback",
    "generate_precommit_hook",
    "generate_precommit_config",
    "install_precommit_hook",
    # MCP
    "generate_mcp_server",
    "write_mcp_server",
]
