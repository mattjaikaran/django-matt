"""
LLM-ready refactoring prompt generator.

For every review finding above a severity threshold, generates a structured
prompt that can be copy-pasted into an LLM or fed to an AI agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django_matt.advisor.health import CodeHealthScorer, FileHealth
from django_matt.review.findings import Category, Finding, Severity

_EFFORT_MAP: dict[Severity, str] = {
    Severity.CRITICAL: "~30-60 minutes",
    Severity.ERROR: "~15-30 minutes",
    Severity.WARNING: "~10-15 minutes",
    Severity.HINT: "~5-10 minutes",
    Severity.INFO: "~5 minutes",
}

_CATEGORY_INSTRUCTIONS: dict[Category, str] = {
    Category.COMPLEXITY: (
        "1. Identify the complex logic block at the flagged location\n"
        "2. Extract each independent concern into a well-named helper function\n"
        "3. Replace nested conditionals with early-return guard clauses\n"
        "4. Ensure the extracted functions have clear type signatures"
    ),
    Category.SECURITY: (
        "1. Identify the security vulnerability at the flagged location\n"
        "2. Apply the principle of least privilege\n"
        "3. Validate/sanitize all external inputs before use\n"
        "4. Verify the fix doesn't introduce new attack vectors"
    ),
    Category.ASYNC_SAFETY: (
        "1. Identify the sync call in async context\n"
        "2. Replace with the async equivalent (e.g., .get() -> .aget())\n"
        "3. If no async equivalent exists, wrap with sync_to_async()\n"
        "4. Verify the calling chain is fully async"
    ),
    Category.N_PLUS_ONE: (
        "1. Identify the query loop causing N+1\n"
        "2. Add select_related() for FK relationships accessed in the loop\n"
        "3. Add prefetch_related() for M2M/reverse FK relationships\n"
        "4. Verify with Django debug toolbar or query logging"
    ),
    Category.SOLID: (
        "1. Identify which SOLID principle is violated\n"
        "2. Extract the violating responsibility into its own class/module\n"
        "3. Define clear interfaces between the separated components\n"
        "4. Update imports and ensure no circular dependencies"
    ),
    Category.PERFORMANCE: (
        "1. Profile the slow path to confirm the bottleneck\n"
        "2. Apply the suggested optimization\n"
        "3. Add a benchmark or timing assertion if appropriate\n"
        "4. Verify correctness is maintained after optimization"
    ),
    Category.DJANGO: (
        "1. Review Django best practices for this pattern\n"
        "2. Apply the idiomatic Django approach\n"
        "3. Ensure migrations are updated if models changed\n"
        "4. Verify admin/API exposure is correct"
    ),
    Category.API_DESIGN: (
        "1. Review the API endpoint design against REST conventions\n"
        "2. Apply consistent naming, auth, and pagination patterns\n"
        "3. Ensure error responses are properly typed\n"
        "4. Update OpenAPI schema if applicable"
    ),
}

_DEFAULT_INSTRUCTIONS = (
    "1. Read the surrounding code to understand the full context\n"
    "2. Apply the suggested fix from the finding\n"
    "3. Run the verification command to confirm the fix\n"
    "4. Check for any side effects in related code"
)


@dataclass(frozen=True, slots=True)
class RefactorPrompt:
    """A structured, LLM-ready refactoring prompt."""

    finding_id: str
    summary: str
    file_path: str
    line_range: tuple[int, int]
    context: str
    instructions: str
    prompt: str
    constraints: list[str]
    verification: str
    estimated_effort: str
    priority: int  # 1-5, derived from health impact
    health_impact: float  # how much the file score improves if fixed


class RefactorPromptGenerator:
    """Generate structured LLM prompts from review findings."""

    def __init__(
        self,
        scorer: CodeHealthScorer | None = None,
        context_lines: int = 10,
    ) -> None:
        self._scorer = scorer or CodeHealthScorer()
        self._context_lines = context_lines

    def generate(
        self,
        finding: Finding,
        source: str,
        file_health: FileHealth | None = None,
    ) -> RefactorPrompt:
        """Generate a refactoring prompt for a single finding."""
        lines = source.splitlines()
        loc = finding.location

        # Extract context snippet
        start = max(0, (loc.line or 1) - 1 - self._context_lines)
        end = min(len(lines), (loc.end_line or loc.line or 1) + self._context_lines)
        context_lines = lines[start:end]
        context = "\n".join(f"{start + i + 1:4d} | {line}" for i, line in enumerate(context_lines))

        # Calculate health impact
        deduction = self._scorer.finding_deduction(finding)
        health_impact = round(deduction, 1)

        # Build constraints
        constraints = self._build_constraints(finding, source)

        # Build verification command
        verification = self._build_verification(finding)

        # Build instructions
        instructions = _CATEGORY_INSTRUCTIONS.get(finding.category, _DEFAULT_INSTRUCTIONS)

        # Priority: 1-5 scale based on severity + category weight
        priority = min(5, max(1, int(deduction)))

        # Build the full prompt text
        prompt = self._build_prompt_text(
            finding, context, instructions, constraints, verification,
            health_impact, file_health,
        )

        return RefactorPrompt(
            finding_id=finding.rule_id,
            summary=f"{finding.message} [{finding.rule_id}]",
            file_path=loc.file,
            line_range=((loc.line or 1), (loc.end_line or loc.line or 1)),
            context=context,
            instructions=instructions,
            prompt=prompt,
            constraints=constraints,
            verification=verification,
            estimated_effort=_EFFORT_MAP.get(finding.severity, "~15 minutes"),
            priority=priority,
            health_impact=health_impact,
        )

    def generate_batch(
        self,
        findings: list[Finding],
        sources: dict[str, str],
        file_healths: dict[str, FileHealth] | None = None,
        min_severity: Severity = Severity.WARNING,
        max_count: int | None = None,
    ) -> list[RefactorPrompt]:
        """Generate prompts for multiple findings, filtered and sorted by priority."""
        file_healths = file_healths or {}
        prompts = []

        for finding in findings:
            if finding.severity < min_severity:
                continue
            source = sources.get(finding.location.file, "")
            if not source:
                continue
            fh = file_healths.get(finding.location.file)
            prompts.append(self.generate(finding, source, fh))

        prompts.sort(key=lambda p: (-p.priority, -p.health_impact))
        if max_count:
            prompts = prompts[:max_count]
        return prompts

    def _build_prompt_text(
        self,
        finding: Finding,
        context: str,
        instructions: str,
        constraints: list[str],
        verification: str,
        health_impact: float,
        file_health: FileHealth | None,
    ) -> str:
        parts = [
            f"## Refactor: {finding.message} [{finding.rule_id}]",
            "",
            f"**File:** {finding.location.file}:{finding.location.line or '?'}",
            f"**Severity:** {finding.severity.name}",
            f"**Category:** {finding.category.value}",
        ]

        if file_health:
            new_score = min(10.0, file_health.score + health_impact)
            parts.append(
                f"**Health impact:** Fixing this improves file score from "
                f"{file_health.score_rounded} -> {round(new_score, 1)}"
            )

        parts.extend([
            "",
            "### Context",
            "```python",
            context,
            "```",
            "",
            "### Instructions",
            instructions,
        ])

        if finding.suggestion:
            parts.extend(["", f"**Suggestion:** {finding.suggestion}"])

        if constraints:
            parts.extend(["", "### Constraints"])
            for c in constraints:
                parts.append(f"- {c}")

        parts.extend([
            "",
            "### Verification",
            "```bash",
            verification,
            "```",
        ])

        return "\n".join(parts)

    def _build_constraints(self, finding: Finding, source: str) -> list[str]:
        """Build constraints based on finding context."""
        constraints = []
        loc = finding.location

        if loc.function:
            constraints.append(
                f"Function `{loc.function}()` signature must not change "
                f"(may be called externally)"
            )
        if loc.class_name:
            constraints.append(
                f"Class `{loc.class_name}` public API must remain backward compatible"
            )

        if finding.category == Category.ASYNC_SAFETY:
            constraints.append("Ensure all callers in the async chain are updated")
        if finding.category == Category.SECURITY:
            constraints.append("Do not weaken existing security checks")
        if finding.category == Category.API_DESIGN:
            constraints.append("Maintain backward compatibility for existing API clients")

        return constraints

    def _build_verification(self, finding: Finding) -> str:
        """Build a verification command string."""
        loc = finding.location
        file_path = loc.file

        # Derive test file path from source file
        parts = Path(file_path).parts
        if "django_matt" in parts:
            idx = parts.index("django_matt")
            rest = parts[idx + 1:]
            test_path = f"tests/test_{'_'.join(rest)}".replace(".py", ".py")
            # Also run the specific module tests
            return f"pytest {test_path} -v\npytest tests/ -k {Path(file_path).stem} -v"

        return "pytest tests/ -v"

    def format_markdown(self, prompts: list[RefactorPrompt]) -> str:
        """Format a list of prompts as a markdown document."""
        if not prompts:
            return "# Refactoring Advisor\n\nNo refactoring suggestions at this time.\n"

        lines = [
            "# Refactoring Advisor",
            "",
            f"**{len(prompts)} suggestions** sorted by priority",
            "",
            "| # | Priority | File | Finding | Effort | Health Impact |",
            "| - | -------- | ---- | ------- | ------ | ------------- |",
        ]
        for i, p in enumerate(prompts, 1):
            lines.append(
                f"| {i} | {'*' * p.priority} | `{p.file_path}` | "
                f"{p.summary} | {p.estimated_effort} | +{p.health_impact} |"
            )
        lines.append("")

        for i, p in enumerate(prompts, 1):
            lines.append("---\n")
            lines.append(f"## {i}. {p.summary}\n")
            lines.append(p.prompt)
            lines.append("")

        return "\n".join(lines)

    def format_json(self, prompts: list[RefactorPrompt]) -> str:
        """Format prompts as JSON for piping to AI agents."""
        import orjson

        data = [
            {
                "finding_id": p.finding_id,
                "summary": p.summary,
                "file_path": p.file_path,
                "line_range": list(p.line_range),
                "instructions": p.instructions,
                "constraints": p.constraints,
                "verification": p.verification,
                "estimated_effort": p.estimated_effort,
                "priority": p.priority,
                "health_impact": p.health_impact,
                "prompt": p.prompt,
            }
            for p in prompts
        ]
        return orjson.dumps(data, option=orjson.OPT_INDENT_2).decode()
