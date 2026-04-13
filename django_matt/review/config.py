"""
Review configuration — thresholds, rulesets, and ignore patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from django_matt.review.findings import Category, Severity


@dataclass
class ComplexityThresholds:
    """Thresholds for complexity analyzer."""

    max_cyclomatic: int = 10
    max_cognitive: int = 15
    max_function_lines: int = 50
    max_class_lines: int = 300
    max_nesting_depth: int = 4
    max_parameters: int = 5
    max_returns: int = 4


@dataclass
class SolidThresholds:
    """Thresholds for SOLID analyzer."""

    max_class_methods: int = 15
    max_class_responsibilities: int = 3
    max_type_checks: int = 3
    max_interface_methods: int = 10
    max_dependencies: int = 8


@dataclass
class AIFriendlyThresholds:
    """Thresholds for AI-friendliness analyzer."""

    max_file_lines: int = 500
    max_function_lines: int = 40
    min_type_hint_coverage: float = 0.7
    min_naming_clarity: float = 0.6
    max_nesting_depth: int = 3


@dataclass
class SecurityPatterns:
    """Patterns for security analyzer."""

    secret_patterns: list[str] = field(default_factory=lambda: [
        r"(?i)(password|secret|api_key|token|private_key)\s*=\s*['\"][^'\"]+['\"]",
        r"(?i)(AWS_SECRET|STRIPE_SECRET|DATABASE_URL)\s*=\s*['\"][^'\"]+['\"]",
    ])
    sql_injection_patterns: list[str] = field(default_factory=lambda: [
        r"\.raw\s*\(",
        r"\.extra\s*\(",
        r"cursor\.execute\s*\(\s*f['\"]",
        r"cursor\.execute\s*\(\s*['\"].*%s",
    ])


@dataclass
class ReviewConfig:
    """Configuration for a code review run."""

    # Which analyzers to run
    analyzers: set[str] = field(default_factory=lambda: {
        "complexity",
        "solid",
        "django",
        "ai_friendly",
        "security",
        "modularity",
        "performance",
    })

    # Minimum severity to report
    min_severity: Severity = Severity.INFO

    # Categories to include (None = all)
    categories: set[Category] | None = None

    # File patterns to include/exclude
    include_patterns: list[str] = field(default_factory=lambda: ["**/*.py"])
    exclude_patterns: list[str] = field(default_factory=lambda: [
        "**/migrations/**",
        "**/__pycache__/**",
        "**/node_modules/**",
        "**/.venv/**",
        "**/venv/**",
        "**/dist/**",
        "**/build/**",
        "**/.git/**",
        "**/manage.py",
    ])

    # Per-analyzer thresholds
    complexity: ComplexityThresholds = field(default_factory=ComplexityThresholds)
    solid: SolidThresholds = field(default_factory=SolidThresholds)
    ai_friendly: AIFriendlyThresholds = field(default_factory=AIFriendlyThresholds)
    security: SecurityPatterns = field(default_factory=SecurityPatterns)

    # Rule IDs to ignore
    ignore_rules: set[str] = field(default_factory=set)

    # Files to ignore (exact paths)
    ignore_files: set[str] = field(default_factory=set)

    # AI reviewer config
    ai_enabled: bool = False
    ai_model: str = "anthropic/claude-sonnet"
    ai_max_files_per_request: int = 5

    # Output
    output_format: str = "console"
    output_file: str | None = None

    # Behavior
    fail_on_error: bool = True
    suggest_refactors: bool = False
    sort_by: str = "severity"  # severity, file, category

    def should_analyze_file(self, file_path: str | Path) -> bool:
        """Check if a file should be analyzed based on include/exclude patterns."""
        from fnmatch import fnmatch

        path_str = str(file_path)

        for pattern in self.exclude_patterns:
            if fnmatch(path_str, pattern):
                return False

        for pattern in self.include_patterns:
            if fnmatch(path_str, pattern):
                return True

        return False

    def should_report_finding(self, rule_id: str, severity: Severity) -> bool:
        """Check if a finding should be reported."""
        if rule_id in self.ignore_rules:
            return False
        if severity < self.min_severity:
            return False
        return True
