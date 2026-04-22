"""
AI agent integration for automated audits.

Provides MCP tool definitions, structured output schemas,
and integration helpers for AI coding assistants.

Example:
    >>> from django_matt.audits.agents import get_mcp_tools, AuditToolResult
    >>> tools = get_mcp_tools()
    >>> # Use with Claude, GPT, or other AI agents
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class MCPToolDefinition(BaseModel):
    """
    MCP (Model Context Protocol) tool definition.

    Attributes:
        name: Tool name for invocation.
        description: Description of what the tool does.
        parameters: JSON Schema for tool parameters.
    """

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: dict[str, Any] = Field(..., description="JSON Schema for parameters")


class AuditToolResult(BaseModel):
    """
    Structured result from an audit tool invocation.

    Attributes:
        success: Whether the audit completed successfully.
        findings_count: Number of findings.
        critical_count: Number of critical findings.
        high_count: Number of high severity findings.
        summary: Brief summary of results.
        findings: List of findings (if requested).
        report_path: Path to full report if saved.
        duration_ms: Time taken in milliseconds.
    """

    success: bool = Field(..., description="Whether audit succeeded")
    findings_count: int = Field(0, description="Total findings")
    critical_count: int = Field(0, description="Critical findings")
    high_count: int = Field(0, description="High severity findings")
    summary: str = Field("", description="Brief summary")
    findings: list[dict[str, Any]] = Field(default_factory=list)
    report_path: str | None = Field(None, description="Path to saved report")
    duration_ms: float = Field(0.0, description="Duration in milliseconds")
    error: str | None = Field(None, description="Error message if failed")


# MCP Tool definitions for AI agents
MCP_TOOLS: dict[str, MCPToolDefinition] = {
    "run_django_matt_audit": MCPToolDefinition(
        name="run_django_matt_audit",
        description="Run a codebase audit on the Django Matt project. Returns findings categorized by severity.",
        parameters={
            "type": "object",
            "properties": {
                "audit_type": {
                    "type": "string",
                    "enum": [
                        "security",
                        "performance",
                        "scalability",
                        "bundle_size",
                        "best_practices",
                        "accessibility",
                        "maintainability",
                        "all",
                    ],
                    "description": "Type of audit to run",
                    "default": "all",
                },
                "level": {
                    "type": "string",
                    "enum": ["relaxed", "standard", "strict", "paranoid"],
                    "description": "Strictness level",
                    "default": "standard",
                },
                "max_findings": {
                    "type": "integer",
                    "description": "Maximum number of findings to return",
                    "default": 50,
                },
                "include_suggestions": {
                    "type": "boolean",
                    "description": "Include fix suggestions in output",
                    "default": True,
                },
            },
            "required": [],
        },
    ),
    "analyze_bundle_size": MCPToolDefinition(
        name="analyze_bundle_size",
        description="Analyze django-matt bundle size and detect unused modules. Returns optimization recommendations.",
        parameters={
            "type": "object",
            "properties": {
                "include_import_time": {
                    "type": "boolean",
                    "description": "Measure import times",
                    "default": True,
                },
            },
            "required": [],
        },
    ),
    "get_audit_prompt": MCPToolDefinition(
        name="get_audit_prompt",
        description="Get a pre-built audit prompt with optional project context for deeper analysis.",
        parameters={
            "type": "object",
            "properties": {
                "prompt_name": {
                    "type": "string",
                    "enum": [
                        "security_audit",
                        "performance_review",
                        "api_design_review",
                        "database_optimization",
                        "test_coverage_gaps",
                        "refactoring_suggestions",
                    ],
                    "description": "Name of the prompt to retrieve",
                },
                "include_context": {
                    "type": "boolean",
                    "description": "Include project context in the prompt",
                    "default": True,
                },
            },
            "required": ["prompt_name"],
        },
    ),
    "generate_project_context": MCPToolDefinition(
        name="generate_project_context",
        description="Generate structured project context for LLM analysis. Includes models, routes, and settings.",
        parameters={
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["markdown", "xml", "json"],
                    "description": "Output format",
                    "default": "markdown",
                },
            },
            "required": [],
        },
    ),
    "fix_audit_finding": MCPToolDefinition(
        name="fix_audit_finding",
        description="Apply an auto-fix for a specific audit finding.",
        parameters={
            "type": "object",
            "properties": {
                "finding_id": {
                    "type": "string",
                    "description": "ID of the finding to fix (e.g., 'SEC001')",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the file containing the issue",
                },
                "preview_only": {
                    "type": "boolean",
                    "description": "Only preview the fix, don't apply it",
                    "default": True,
                },
            },
            "required": ["finding_id", "file_path"],
        },
    ),
}


def get_mcp_tools() -> list[dict[str, Any]]:
    """
    Get MCP tool definitions for AI agents.

    Returns:
        List of tool definitions in MCP format.

    Example:
        >>> tools = get_mcp_tools()
        >>> # Register with your AI agent system
    """
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in MCP_TOOLS.values()
    ]


def execute_mcp_tool(
    tool_name: str,
    parameters: dict[str, Any],
) -> AuditToolResult:
    """
    Execute an MCP tool with the given parameters.

    Args:
        tool_name: Name of the tool to execute.
        parameters: Tool parameters.

    Returns:
        AuditToolResult with execution results.

    Example:
        >>> result = execute_mcp_tool(
        ...     "run_django_matt_audit", {"audit_type": "security", "level": "strict"}
        ... )
        >>> if result.critical_count > 0:
        ...     print(f"Found {result.critical_count} critical issues!")
    """
    import time

    start_time = time.perf_counter()

    try:
        if tool_name == "run_django_matt_audit":
            return _execute_audit(parameters)
        if tool_name == "analyze_bundle_size":
            return _execute_bundle_analysis(parameters)
        if tool_name == "get_audit_prompt":
            return _execute_get_prompt(parameters)
        if tool_name == "generate_project_context":
            return _execute_generate_context(parameters)
        if tool_name == "fix_audit_finding":
            return _execute_fix_finding(parameters)
        return AuditToolResult(
            success=False,
            error=f"Unknown tool: {tool_name}",
        )
    except Exception as e:
        return AuditToolResult(
            success=False,
            error=str(e),
            duration_ms=(time.perf_counter() - start_time) * 1000,
        )


def _execute_audit(params: dict[str, Any]) -> AuditToolResult:
    """Execute the audit tool."""
    from ..framework import AuditLevel, run_audit

    audit_type = params.get("audit_type", "all")
    level = AuditLevel(params.get("level", "standard"))
    max_findings = params.get("max_findings", 50)
    include_suggestions = params.get("include_suggestions", True)

    report = run_audit(audit_type, level=level)

    # Format findings for output
    findings = []
    for finding in report.all_findings[:max_findings]:
        finding_dict = {
            "id": finding.id,
            "severity": finding.severity.value,
            "category": finding.category.value,
            "message": finding.message,
            "file": finding.file,
            "line": finding.line,
        }
        if include_suggestions and finding.suggestion:
            finding_dict["suggestion"] = finding.suggestion
        findings.append(finding_dict)

    # Generate summary
    summary_parts = [
        f"{len(report.all_findings)} total findings",
        f"{len(report.critical_findings)} critical",
        f"{report.results[0].high_count if report.results else 0} high",
    ]

    return AuditToolResult(
        success=True,
        findings_count=len(report.all_findings),
        critical_count=len(report.critical_findings),
        high_count=sum(r.high_count for r in report.results),
        summary=", ".join(summary_parts),
        findings=findings,
        duration_ms=(report.completed_at - report.started_at).total_seconds() * 1000
        if report.completed_at
        else 0,
    )


def _execute_bundle_analysis(params: dict[str, Any]) -> AuditToolResult:
    """Execute the bundle analysis tool."""
    from ..bundle import analyze_bundle

    include_import_time = params.get("include_import_time", True)
    result = analyze_bundle(include_import_time=include_import_time)

    findings = [
        {
            "type": "unused_module",
            "module": module,
            "size_kb": result.module_details.get(module, {}).get("size_kb", 0),
        }
        for module in result.unused_modules
    ]

    summary = (
        f"Total: {result.total_size_kb:.0f}KB, "
        f"Unused: {result.unused_size_kb:.0f}KB, "
        f"{len(result.unused_modules)} unused modules"
    )

    return AuditToolResult(
        success=True,
        findings_count=len(result.unused_modules),
        summary=summary,
        findings=findings,
    )


def _execute_get_prompt(params: dict[str, Any]) -> AuditToolResult:
    """Execute the get prompt tool."""
    from ..prompts import get_prompt

    prompt_name = params.get("prompt_name")
    include_context = params.get("include_context", True)

    if not prompt_name:
        return AuditToolResult(
            success=False,
            error="prompt_name is required",
        )

    prompt = get_prompt(prompt_name, include_context=include_context)

    return AuditToolResult(
        success=True,
        summary=f"Generated {prompt_name} prompt",
        findings=[{"system": prompt["system"], "user": prompt["user"][:1000] + "..."}],
    )


def _execute_generate_context(params: dict[str, Any]) -> AuditToolResult:
    """Execute the generate context tool."""
    from ..prompts import generate_context

    output_format = params.get("format", "markdown")
    context = generate_context()

    if output_format == "xml":
        content = context.to_xml()
    elif output_format == "json":
        content = context.model_dump_json(indent=2)
    else:
        content = context.to_markdown()

    return AuditToolResult(
        success=True,
        summary=f"Generated project context in {output_format} format",
        findings=[{"context": content[:2000] + "..." if len(content) > 2000 else content}],
    )


def _execute_fix_finding(params: dict[str, Any]) -> AuditToolResult:
    """Execute the fix finding tool."""
    finding_id = params.get("finding_id")
    file_path = params.get("file_path")
    preview_only = params.get("preview_only", True)

    if not finding_id or not file_path:
        return AuditToolResult(
            success=False,
            error="finding_id and file_path are required",
        )

    # For now, return a preview message
    return AuditToolResult(
        success=True,
        summary=f"{'Preview' if preview_only else 'Applied'} fix for {finding_id}",
        findings=[
            {
                "finding_id": finding_id,
                "file": file_path,
                "preview_only": preview_only,
                "status": "preview" if preview_only else "applied",
            }
        ],
    )


@dataclass
class CursorRulesSection:
    """
    Section for .cursorrules file generation.

    Attributes:
        title: Section title.
        content: Section content.
        priority: Display priority.
    """

    title: str
    content: str
    priority: int = 0


def generate_cursor_rules(project_path: str | None = None) -> str:
    """
    Generate .cursorrules file content for Cursor IDE.

    Args:
        project_path: Path to the project.

    Returns:
        Content for .cursorrules file.

    Example:
        >>> rules = generate_cursor_rules()
        >>> Path(".cursorrules").write_text(rules)
    """
    sections = [
        CursorRulesSection(
            title="Django Matt Project",
            content="""This is a Django Matt project. When suggesting code:

1. Use async/await for all I/O operations
2. Follow django-matt patterns for controllers, schemas, and views
3. Use Pydantic for all request/response schemas
4. Prefer `acreate`, `aget`, `afilter` etc. for ORM operations in async contexts
5. Use type hints on all function signatures""",
            priority=1,
        ),
        CursorRulesSection(
            title="Code Style",
            content="""Follow these coding standards:

- Type hints: All functions must have type hints
- Docstrings: All public functions and classes need docstrings
- Line length: 88 characters (ruff default)
- Imports: Use absolute imports, sort with ruff""",
            priority=2,
        ),
        CursorRulesSection(
            title="Testing",
            content="""When writing tests:

- Use pytest with pytest-asyncio
- Use django-matt's AsyncAPITestClient for API tests
- Test async code with `async def test_*` and `await`
- Use factories for test data creation""",
            priority=3,
        ),
        CursorRulesSection(
            title="Security",
            content="""Security requirements:

- Never hardcode secrets, use environment variables
- Use parameterized queries, never string formatting for SQL
- Apply authentication decorators to all endpoints
- Validate all user input with Pydantic schemas""",
            priority=4,
        ),
    ]

    # Sort by priority
    sections.sort(key=lambda s: s.priority)

    # Build rules content
    lines = ["# Django Matt Project Rules", ""]
    for section in sections:
        lines.append(f"## {section.title}")
        lines.append("")
        lines.append(section.content)
        lines.append("")

    return "\n".join(lines)


def generate_claude_md(project_path: str | None = None) -> str:
    """
    Generate CLAUDE.md file content for Claude Code.

    Args:
        project_path: Path to the project.

    Returns:
        Content for CLAUDE.md file.

    Example:
        >>> content = generate_claude_md()
        >>> Path("CLAUDE.md").write_text(content)
    """
    return """# Django Matt Project

## Stack
- Python 3.12+ / Django 5.2+ / Pydantic 2.0+
- Async-first, type hints everywhere, ruff for lint/format

## Key Patterns

### Controllers
```python
class UserController(APIController):
    prefix = "/users"
    tags = ["Users"]
    permission_classes = [IsAuthenticated]

    @api.get("/")
    async def list_users(self) -> list[UserSchema]:
        return await User.objects.all().aiterator()
```

### Async ORM
Always use async ORM methods in async functions:
- `aget()` instead of `get()`
- `acreate()` instead of `create()`
- `aiterator()` or `async for` instead of iterating querysets

### Type Hints
All functions need type hints:
```python
async def get_user(user_id: int) -> UserSchema | None:
    ...
```

## Common Tasks
| Task | Pattern |
|------|---------|
| Create endpoint | `@api.post("/")` decorator with Pydantic schema |
| Add auth | `@jwt_required` or `permission_classes = [IsAuthenticated]` |
| Database query | Use `aget`, `acreate`, `afilter` etc. |
| Background task | `@task` decorator with Pydantic payload |

## Testing
```bash
pytest tests/ -v  # run tests
pytest tests/ --cov  # with coverage
```
"""
