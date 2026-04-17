"""
Optional LLM-powered code review using django_matt.ai providers.

Provides architectural review, refactor suggestions, and pattern recognition
that goes beyond what static analysis can detect.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("django_matt.review")

from django_matt.review.config import ReviewConfig
from django_matt.review.findings import (
    Category,
    Finding,
    Location,
    Severity,
)


@dataclass
class AIReviewRequest:
    """A batch of files to send for AI review."""

    files: list[tuple[Path, str]]  # (path, source)
    focus_areas: list[str] = field(default_factory=list)
    context: str = ""


@dataclass
class AIReviewResult:
    """Result from an AI review pass."""

    findings: list[Finding] = field(default_factory=list)
    summary: str = ""
    refactor_suggestions: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0


_REVIEW_SYSTEM_PROMPT = """\
You are a senior Django engineer performing a code review. Analyze the provided code for:

1. **Architectural issues** — poor separation of concerns, missing abstractions, tight coupling
2. **Django anti-patterns** — misuse of ORM, incorrect async patterns, security gaps
3. **Refactoring opportunities** — duplicated logic, overly complex flows, missing design patterns
4. **AI/LLM friendliness** — code that would be hard for AI agents to understand or modify

For each finding, respond in this exact JSON format:
{
  "findings": [
    {
      "rule_id": "AIR-XXX",
      "file": "path/to/file.py",
      "line": 42,
      "severity": "warning",
      "message": "Brief description of the issue",
      "suggestion": "How to fix it",
      "category": "architecture|django|refactoring|ai_friendly"
    }
  ],
  "summary": "Brief overall assessment",
  "refactor_suggestions": [
    {
      "title": "Extract payment service",
      "description": "The PaymentView handles Stripe API calls directly...",
      "files": ["payments/views.py"],
      "effort": "medium"
    }
  ]
}

Be specific and actionable. Don't flag minor style issues — focus on things that matter.
"""

_SEVERITY_MAP = {
    "info": Severity.INFO,
    "hint": Severity.HINT,
    "warning": Severity.WARNING,
    "error": Severity.ERROR,
    "critical": Severity.CRITICAL,
}

_CATEGORY_MAP = {
    "architecture": Category.SOLID,
    "django": Category.DJANGO,
    "refactoring": Category.COMPLEXITY,
    "ai_friendly": Category.AI_FRIENDLY,
    "security": Category.SECURITY,
    "performance": Category.PERFORMANCE,
    "async_safety": Category.ASYNC_SAFETY,
    "n_plus_one": Category.N_PLUS_ONE,
    "modularity": Category.MODULARITY,
    "style": Category.STYLE,
    "testing": Category.TESTING,
    "migration": Category.MIGRATION,
    "api_design": Category.API_DESIGN,
}


class AIReviewer:
    """LLM-powered code reviewer using django_matt.ai providers."""

    def __init__(self, config: ReviewConfig) -> None:
        self.config = config

    async def review_files(self, files: list[tuple[Path, str]]) -> AIReviewResult:
        """Review a batch of files using the configured LLM provider."""
        try:
            import django_matt.ai.providers  # noqa: F401
        except ImportError:
            return AIReviewResult(
                summary="AI review unavailable: django_matt.ai not configured"
            )

        result = AIReviewResult()

        # Batch files to stay within context limits
        batch_size = self.config.ai_max_files_per_request
        for i in range(0, len(files), batch_size):
            batch = files[i : i + batch_size]
            batch_result = await self._review_batch(batch)
            result.findings.extend(batch_result.findings)
            result.refactor_suggestions.extend(batch_result.refactor_suggestions)
            result.tokens_used += batch_result.tokens_used

        if result.findings:
            result.summary = f"AI review found {len(result.findings)} issues across {len(files)} files"
        else:
            result.summary = f"AI review: no significant issues found in {len(files)} files"

        return result

    async def _review_batch(self, files: list[tuple[Path, str]]) -> AIReviewResult:
        """Review a single batch of files."""
        from django_matt.ai.providers import get_provider

        provider = get_provider(self.config.ai_model)

        # Build the user message with file contents
        parts = []
        for path, source in files:
            parts.append(f"### {path}\n```python\n{source}\n```")

        user_message = "Review the following files:\n\n" + "\n\n".join(parts)

        if self.config.suggest_refactors:
            user_message += "\n\nAlso suggest specific refactoring opportunities."

        response = await provider.acomplete(
            messages=[
                {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=4096,
        )

        return self._parse_response(response.content, response.usage.total_tokens if response.usage else 0)

    def _parse_response(self, content: str, tokens: int) -> AIReviewResult:
        """Parse LLM response into structured findings."""
        import orjson

        result = AIReviewResult(tokens_used=tokens)

        # Extract JSON from response (may be wrapped in markdown code block)
        json_str = content.strip()
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            json_str = "\n".join(lines[1:-1])

        try:
            data = orjson.loads(json_str)
        except (orjson.JSONDecodeError, ValueError):
            result.summary = "AI review returned unparseable response"
            return result

        for f in data.get("findings", []):
            severity = _SEVERITY_MAP.get(f.get("severity", "hint"), Severity.HINT)
            raw_category = f.get("category", "")
            category = _CATEGORY_MAP.get(raw_category)
            if category is None:
                logger.warning(
                    "AI reviewer returned unknown category %r, skipping finding", raw_category
                )
                continue

            finding = Finding(
                rule_id=f.get("rule_id", "AIR-000"),
                message=f.get("message", ""),
                severity=severity,
                category=category,
                location=Location(
                    file=f.get("file", "unknown"),
                    line=f.get("line"),
                ),
                suggestion=f.get("suggestion"),
            )
            result.findings.append(finding)

        result.summary = data.get("summary", "")
        result.refactor_suggestions = data.get("refactor_suggestions", [])

        return result
