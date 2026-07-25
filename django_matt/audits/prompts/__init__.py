# file-length-max: 750
"""
LLM prompt helpers for AI-assisted audits.

Provides structured context generation and pre-built audit prompts
optimized for various LLM providers.

Example:
    >>> from django_matt.audits.prompts import get_prompt, generate_context
    >>> context = generate_context(for_model="claude")
    >>> prompt = get_prompt("security_audit", include_context=True)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


class ProjectContext(BaseModel):
    """
    Structured project context for LLM consumption.

    Attributes:
        project_name: Name of the project.
        django_matt_version: Version of django-matt.
        python_version: Python version.
        django_version: Django version.
        models: List of model definitions.
        routes: List of API routes.
        settings: Relevant settings summary.
        dependencies: Key dependencies.
        file_structure: Project structure summary.
        generated_at: When the context was generated.
    """

    project_name: str = Field("", description="Project name")
    django_matt_version: str = Field("", description="django-matt version")
    python_version: str = Field("", description="Python version")
    django_version: str = Field("", description="Django version")
    models: list[dict[str, Any]] = Field(default_factory=list)
    routes: list[dict[str, Any]] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    file_structure: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_markdown(self) -> str:
        """Convert context to markdown format for LLMs."""
        sections = [
            f"# Project Context: {self.project_name}",
            "",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            "## Environment",
            f"- Python: {self.python_version}",
            f"- Django: {self.django_version}",
            f"- django-matt: {self.django_matt_version}",
            "",
        ]

        if self.models:
            sections.append("## Models")
            for model in self.models:
                sections.append(f"### {model.get('name', 'Unknown')}")
                if "fields" in model:
                    for f in model["fields"]:
                        sections.append(f"- {f['name']}: {f['type']}")
            sections.append("")

        if self.routes:
            sections.append("## API Routes")
            for route in self.routes:
                method = route.get("method", "GET")
                path = route.get("path", "/")
                name = route.get("name", "")
                sections.append(f"- `{method} {path}` ({name})")
            sections.append("")

        if self.dependencies:
            sections.append("## Dependencies")
            for dep in self.dependencies:
                sections.append(f"- {dep}")
            sections.append("")

        if self.file_structure:
            sections.append("## Project Structure")
            sections.append("```")
            sections.extend(self.file_structure)
            sections.append("```")
            sections.append("")

        return "\n".join(sections)

    def to_xml(self) -> str:
        """Convert context to XML format (optimized for Claude)."""
        sections = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            "<project_context>",
            f"  <name>{self.project_name}</name>",
            f"  <generated_at>{self.generated_at.isoformat()}</generated_at>",
            "  <environment>",
            f"    <python>{self.python_version}</python>",
            f"    <django>{self.django_version}</django>",
            f"    <django_matt>{self.django_matt_version}</django_matt>",
            "  </environment>",
        ]

        if self.models:
            sections.append("  <models>")
            for model in self.models:
                sections.append(f'    <model name="{model.get("name", "")}">')
                for f in model.get("fields", []):
                    sections.append(f'      <field name="{f["name"]}" type="{f["type"]}" />')
                sections.append("    </model>")
            sections.append("  </models>")

        if self.routes:
            sections.append("  <routes>")
            for route in self.routes:
                sections.append(
                    f'    <route method="{route.get("method", "GET")}" '
                    f'path="{route.get("path", "/")}" '
                    f'name="{route.get("name", "")}" />'
                )
            sections.append("  </routes>")

        sections.append("</project_context>")
        return "\n".join(sections)


@dataclass
class AuditPrompt:
    """
    A pre-built audit prompt template.

    Attributes:
        name: Prompt identifier.
        description: What this prompt audits.
        system_prompt: System-level instructions.
        user_prompt_template: User prompt with placeholders.
        response_format: Expected response format.
        tags: Tags for categorization.
    """

    name: str
    description: str
    system_prompt: str
    user_prompt_template: str
    response_format: str = "markdown"
    tags: list[str] = field(default_factory=list)

    def render(
        self,
        context: ProjectContext | None = None,
        **kwargs: Any,
    ) -> dict[str, str]:
        """
        Render the prompt with context and variables.

        Args:
            context: Optional project context.
            **kwargs: Additional template variables.

        Returns:
            Dict with "system" and "user" prompt strings.
        """
        user_prompt = self.user_prompt_template

        if context:
            user_prompt = f"{context.to_markdown()}\n\n{user_prompt}"

        for key, value in kwargs.items():
            user_prompt = user_prompt.replace(f"{{{key}}}", str(value))

        return {
            "system": self.system_prompt,
            "user": user_prompt,
        }


# Pre-built audit prompts
AUDIT_PROMPTS: dict[str, AuditPrompt] = {
    "security_audit": AuditPrompt(
        name="security_audit",
        description="Comprehensive security review of a Django project",
        system_prompt="""You are a senior security engineer specializing in Django applications.
Your task is to review the provided project context and code for security vulnerabilities.
Be thorough but practical - focus on issues that could be exploited in production.
Categorize findings by severity: CRITICAL, HIGH, MEDIUM, LOW, INFO.
For each finding, provide:
1. The vulnerability type (e.g., SQL Injection, XSS, CSRF)
2. The affected code location
3. The potential impact
4. A specific remediation recommendation
5. OWASP category if applicable""",
        user_prompt_template="""Review this Django project for security vulnerabilities.

Focus on:
- Authentication and authorization weaknesses
- Input validation and SQL injection
- Cross-site scripting (XSS)
- Cross-site request forgery (CSRF)
- Sensitive data exposure
- Security misconfigurations
- Insecure deserialization
- Using components with known vulnerabilities

Provide findings in this format:

## Finding: [Title]
- **Severity:** [CRITICAL/HIGH/MEDIUM/LOW/INFO]
- **Type:** [Vulnerability Type]
- **Location:** [File:Line]
- **Description:** [What the vulnerability is]
- **Impact:** [What could happen if exploited]
- **Remediation:** [How to fix it]
- **OWASP:** [OWASP Top 10 category if applicable]
""",
        tags=["security", "owasp"],
    ),
    "performance_review": AuditPrompt(
        name="performance_review",
        description="Performance analysis and optimization suggestions",
        system_prompt="""You are a performance engineer specializing in Django and database optimization.
Analyze the provided project for performance issues and optimization opportunities.
Focus on practical improvements that will have measurable impact.
Consider: database queries, caching, async operations, memory usage, and algorithmic efficiency.""",
        user_prompt_template="""Analyze this Django project for performance issues.

Focus on:
- N+1 query patterns
- Missing database indexes
- Inefficient queryset operations
- Caching opportunities
- Async/await usage for I/O operations
- Memory-intensive operations
- Algorithmic inefficiencies

For each issue found, provide:
1. What the performance problem is
2. Where it occurs in the code
3. Estimated impact (latency, memory, CPU)
4. Specific optimization recommendation
5. Expected improvement

Format findings as:

## Issue: [Title]
- **Impact:** [HIGH/MEDIUM/LOW]
- **Type:** [Query/Cache/Memory/Algorithm/I/O]
- **Location:** [File or component]
- **Problem:** [Description]
- **Recommendation:** [How to fix]
- **Expected Improvement:** [Estimated gain]
""",
        tags=["performance", "optimization"],
    ),
    "api_design_review": AuditPrompt(
        name="api_design_review",
        description="RESTful API design review",
        system_prompt="""You are an API design expert specializing in RESTful best practices.
Review the API endpoints for consistency, usability, and adherence to REST principles.
Consider: naming conventions, HTTP methods, status codes, error handling, versioning, and documentation.""",
        user_prompt_template="""Review this API design for best practices.

Evaluate:
- Resource naming and URL structure
- HTTP method usage
- Status code appropriateness
- Error response format
- Pagination implementation
- Filtering and sorting
- Authentication/authorization patterns
- API versioning
- Documentation completeness

For each issue, provide:
1. What the design problem is
2. Which endpoint is affected
3. Why it matters for API consumers
4. Recommended improvement

Format as:

## Issue: [Title]
- **Severity:** [HIGH/MEDIUM/LOW]
- **Endpoint:** [METHOD /path]
- **Problem:** [Description]
- **Best Practice:** [What it should be]
- **Recommendation:** [How to fix]
""",
        tags=["api", "rest", "design"],
    ),
    "database_optimization": AuditPrompt(
        name="database_optimization",
        description="Database schema and query optimization",
        system_prompt="""You are a database optimization expert specializing in Django ORM and PostgreSQL.
Analyze models, queries, and database patterns for optimization opportunities.
Consider: indexing strategy, query efficiency, schema design, and data integrity.""",
        user_prompt_template="""Analyze the database design and query patterns.

Evaluate:
- Index usage and missing indexes
- Query efficiency (select_related, prefetch_related)
- Schema normalization
- Field type choices
- Constraint usage
- Migration efficiency
- Connection pooling
- Read/write splitting opportunities

For each finding:
1. What the issue is
2. Affected model or query
3. Performance impact
4. Specific SQL or ORM recommendation

Format as:

## Finding: [Title]
- **Type:** [Index/Query/Schema/Connection]
- **Impact:** [HIGH/MEDIUM/LOW]
- **Location:** [Model or query]
- **Issue:** [Description]
- **Recommendation:** [How to fix]
- **SQL/ORM:** [Specific code if applicable]
""",
        tags=["database", "postgresql", "optimization"],
    ),
    "test_coverage_gaps": AuditPrompt(
        name="test_coverage_gaps",
        description="Identify areas lacking test coverage",
        system_prompt="""You are a quality assurance engineer specializing in Django testing.
Analyze the codebase to identify areas that need more test coverage.
Focus on critical paths, edge cases, and error handling that should be tested.""",
        user_prompt_template="""Identify test coverage gaps in this project.

Analyze:
- Critical business logic without tests
- API endpoints without integration tests
- Error handling paths
- Edge cases in validation
- Authentication/authorization scenarios
- Database operations
- External service integrations
- Async code paths

For each gap:
1. What needs testing
2. Why it's important
3. Suggested test approach
4. Example test case outline

Format as:

## Gap: [Component/Function]
- **Priority:** [HIGH/MEDIUM/LOW]
- **Type:** [Unit/Integration/E2E]
- **Risk:** [What could go wrong untested]
- **Suggested Tests:**
  - [Test case 1]
  - [Test case 2]
""",
        tags=["testing", "coverage", "quality"],
    ),
    "refactoring_suggestions": AuditPrompt(
        name="refactoring_suggestions",
        description="Code quality and refactoring opportunities",
        system_prompt="""You are a senior software architect specializing in Django applications.
Identify code that would benefit from refactoring to improve maintainability,
readability, and adherence to SOLID principles.""",
        user_prompt_template="""Suggest refactoring opportunities in this codebase.

Look for:
- Code duplication
- Long methods/functions
- Large classes
- Complex conditionals
- Poor separation of concerns
- Tight coupling
- Missing abstractions
- Inconsistent patterns

For each suggestion:
1. What to refactor
2. Why it would help
3. Proposed approach
4. Estimated effort

Format as:

## Refactoring: [Title]
- **Priority:** [HIGH/MEDIUM/LOW]
- **Location:** [File/Class/Function]
- **Problem:** [Current issue]
- **Approach:** [How to refactor]
- **Benefits:** [What improves]
- **Effort:** [Small/Medium/Large]
""",
        tags=["refactoring", "architecture", "clean-code"],
    ),
}


def get_prompt(
    prompt_name: str,
    include_context: bool = False,
    project_path: Path | str | None = None,
    **kwargs: Any,
) -> dict[str, str]:
    """
    Get a pre-built audit prompt.

    Args:
        prompt_name: Name of the prompt (e.g., "security_audit").
        include_context: Whether to include project context.
        project_path: Path to the project for context generation.
        **kwargs: Additional template variables.

    Returns:
        Dict with "system" and "user" prompt strings.

    Example:
        >>> prompt = get_prompt("security_audit", include_context=True)
        >>> print(prompt["system"])
        >>> print(prompt["user"])
    """
    if prompt_name not in AUDIT_PROMPTS:
        available = ", ".join(AUDIT_PROMPTS.keys())
        raise ValueError(f"Unknown prompt: {prompt_name}. Available: {available}")

    prompt = AUDIT_PROMPTS[prompt_name]
    context = None

    if include_context:
        context = generate_context(project_path=project_path)

    return prompt.render(context=context, **kwargs)


def list_prompts() -> list[dict[str, str]]:
    """
    List all available audit prompts.

    Returns:
        List of prompt info dicts with name, description, and tags.
    """
    return [
        {
            "name": p.name,
            "description": p.description,
            "tags": p.tags,
        }
        for p in AUDIT_PROMPTS.values()
    ]


def generate_context(
    project_path: Path | str | None = None,
    for_model: Literal["claude", "gpt", "generic"] = "generic",
) -> ProjectContext:
    """
    Generate project context for LLM consumption.

    Args:
        project_path: Path to the project.
        for_model: Target model (affects format optimization).

    Returns:
        ProjectContext with project information.
    """
    import sys

    project_path = Path(project_path) if project_path else Path.cwd()

    context = ProjectContext(
        project_name=project_path.name,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )

    # Get django-matt version
    try:
        from django_matt import __version__

        context.django_matt_version = __version__
    except ImportError:
        pass

    # Get Django version
    try:
        import django

        context.django_version = django.__version__
    except ImportError:
        pass

    # Scan for models (simplified - real impl would use Django introspection)
    models_dir = project_path / "models"
    if models_dir.exists():
        context.models = _scan_models(models_dir)

    # Generate file structure
    context.file_structure = _generate_structure(project_path)

    # Scan dependencies
    context.dependencies = _scan_dependencies(project_path)

    return context


def _scan_models(models_dir: Path) -> list[dict[str, Any]]:
    """Scan for Django models."""
    models = []
    # This is a placeholder - real implementation would use Django's model introspection
    return models


def _generate_structure(project_path: Path, max_depth: int = 3) -> list[str]:
    """Generate project directory structure."""
    lines = []
    _add_tree(project_path, lines, "", max_depth)
    return lines[:50]  # Limit output


def _add_tree(path: Path, lines: list[str], prefix: str, max_depth: int) -> None:
    """Recursively add directory tree."""
    if max_depth <= 0:
        return

    items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
    for i, item in enumerate(items):
        # Skip hidden and common ignore patterns
        if item.name.startswith(".") or item.name in {
            "__pycache__",
            "node_modules",
            ".git",
            "venv",
            ".venv",
        }:
            continue

        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{item.name}")

        if item.is_dir():
            extension = "    " if is_last else "│   "
            _add_tree(item, lines, prefix + extension, max_depth - 1)


def _scan_dependencies(project_path: Path) -> list[str]:
    """Scan for project dependencies."""
    deps = []

    # Check pyproject.toml
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib

            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            deps_section = data.get("project", {}).get("dependencies", []) or data.get(
                "tool", {}
            ).get("poetry", {}).get("dependencies", {})
            if isinstance(deps_section, list):
                deps.extend(deps_section[:20])
            elif isinstance(deps_section, dict):
                deps.extend(list(deps_section.keys())[:20])
        except Exception:
            pass

    # Check requirements.txt
    req_file = project_path / "requirements.txt"
    if req_file.exists() and not deps:
        try:
            content = req_file.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    deps.append(line.split("==")[0].split(">=")[0].split("<")[0])
                if len(deps) >= 20:
                    break
        except Exception:
            pass

    return deps


@dataclass
class ParsedFinding:
    """
    A parsed finding from LLM output.

    Attributes:
        severity: Finding severity.
        title: Finding title.
        file: Affected file.
        line: Line number.
        message: Description.
        recommendation: Suggested fix.
    """

    severity: str
    title: str
    file: str | None = None
    line: int | None = None
    message: str = ""
    recommendation: str = ""


def parse_audit_response(
    response: str,
    audit_type: str = "generic",
) -> list[ParsedFinding]:
    """
    Parse structured LLM audit response into findings.

    Args:
        response: Raw LLM response text.
        audit_type: Type of audit (affects parsing).

    Returns:
        List of parsed findings.

    Example:
        >>> findings = parse_audit_response(llm_output, audit_type="security")
        >>> for f in findings:
        ...     print(f"[{f.severity}] {f.title}")
    """
    import re

    findings = []

    # Pattern for markdown-formatted findings
    finding_pattern = re.compile(
        r"##\s*(Finding|Issue|Gap|Refactoring):\s*(.+?)(?=\n##|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    severity_pattern = re.compile(r"\*\*Severity:\*\*\s*(\w+)", re.IGNORECASE)
    location_pattern = re.compile(r"\*\*Location:\*\*\s*([^\n]+)", re.IGNORECASE)
    description_pattern = re.compile(
        r"\*\*(Description|Problem|Issue):\*\*\s*([^\n]+)", re.IGNORECASE
    )
    recommendation_pattern = re.compile(r"\*\*Recommendation:\*\*\s*([^\n]+)", re.IGNORECASE)

    for match in finding_pattern.finditer(response):
        _finding_type, content = match.groups()
        title_end = content.find("\n")
        title = content[:title_end].strip() if title_end > 0 else content.strip()

        severity_match = severity_pattern.search(content)
        severity = severity_match.group(1) if severity_match else "MEDIUM"

        location_match = location_pattern.search(content)
        file_loc = None
        line = None
        if location_match:
            loc = location_match.group(1).strip()
            if ":" in loc:
                parts = loc.split(":")
                file_loc = parts[0]
                try:
                    line = int(parts[1])
                except (ValueError, IndexError):
                    pass
            else:
                file_loc = loc

        desc_match = description_pattern.search(content)
        description = desc_match.group(2).strip() if desc_match else ""

        rec_match = recommendation_pattern.search(content)
        recommendation = rec_match.group(1).strip() if rec_match else ""

        findings.append(
            ParsedFinding(
                severity=severity.upper(),
                title=title,
                file=file_loc,
                line=line,
                message=description,
                recommendation=recommendation,
            )
        )

    return findings
