"""
Django Matt code review command.

Runs static analysis and optional AI-powered review on your codebase.

Usage:
    python manage.py matt_review                          # full review
    python manage.py matt_review myapp/                   # review specific path
    python manage.py matt_review --analyzers solid,security
    python manage.py matt_review --format json --output review.json
    python manage.py matt_review --min-severity warning
    python manage.py matt_review --ai                     # LLM-enhanced review
    python manage.py matt_review --suggest-refactors      # include refactor suggestions
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from django_matt.cli import MattCommand
from django_matt.review.config import ReviewConfig
from django_matt.review.engine import ReviewEngine
from django_matt.review.findings import Severity

_SEVERITY_CHOICES = ["info", "hint", "warning", "error", "critical"]
_FORMAT_CHOICES = ["console", "markdown", "json", "github"]
_ANALYZER_CHOICES = [
    "complexity",
    "solid",
    "django",
    "ai_friendly",
    "security",
    "modularity",
    "performance",
    "async_safety",
    "n_plus_one",
    "migration_safety",
    "api_design",
]


class Command(MattCommand):
    """Run automated code review on your Django project."""

    help = "Code review: SOLID, complexity, security, Django best practices, AI-friendliness"

    def add_arguments(self, parser) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "paths",
            nargs="*",
            default=["."],
            help="Paths to review (default: current directory)",
        )
        parser.add_argument(
            "--analyzers",
            "-a",
            help=f"Comma-separated analyzers to run (choices: {', '.join(_ANALYZER_CHOICES)})",
        )
        parser.add_argument(
            "--format",
            "-f",
            choices=_FORMAT_CHOICES,
            default="console",
            help="Output format (default: console)",
        )
        parser.add_argument(
            "--output",
            "-o",
            help="Write report to file instead of stdout",
        )
        parser.add_argument(
            "--min-severity",
            choices=_SEVERITY_CHOICES,
            default="info",
            help="Minimum severity to report (default: info)",
        )
        parser.add_argument(
            "--sort",
            choices=["severity", "file", "category"],
            default="severity",
            help="Sort findings by (default: severity)",
        )
        parser.add_argument(
            "--exclude",
            help="Additional glob patterns to exclude (comma-separated)",
        )
        parser.add_argument(
            "--ignore-rules",
            help="Rule IDs to ignore (comma-separated, e.g. CX001,SEC003)",
        )
        parser.add_argument(
            "--ai",
            action="store_true",
            help="Enable AI-powered review (requires configured LLM provider)",
        )
        parser.add_argument(
            "--ai-model",
            default="anthropic/claude-sonnet",
            help="AI model to use for review (default: anthropic/claude-sonnet)",
        )
        parser.add_argument(
            "--suggest-refactors",
            action="store_true",
            help="Include refactoring suggestions in output",
        )
        parser.add_argument(
            "--fail-on-error",
            action="store_true",
            default=True,
            help="Exit with non-zero code if errors found (default: true)",
        )
        parser.add_argument(
            "--no-fail",
            action="store_true",
            help="Always exit with code 0 regardless of findings",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Shorthand for --format json",
        )
        parser.add_argument(
            "--fail-on",
            choices=_SEVERITY_CHOICES,
            default=None,
            help="Fail (exit non-zero) if any finding meets or exceeds this severity",
        )

    def handle(self, *args, **options) -> None:
        # Build config from CLI args
        config = self._build_config(options)

        # Resolve paths
        paths = [Path(p).resolve() for p in options["paths"]]

        # Run review
        self.console.header("Code Review")
        engine = ReviewEngine(config)

        self.console.info(
            f"Analyzers: {', '.join(sorted(config.analyzers))}"
        )
        self.console.info(f"Paths: {', '.join(str(p) for p in paths)}")

        summary = engine.review_paths(paths)

        # Run AI review if enabled
        if config.ai_enabled:
            self.console.info("Running AI-powered review...")
            ai_result = asyncio.run(self._run_ai_review_full(config, paths))
            summary.findings.extend(ai_result.findings)
            summary.refactor_suggestions.extend(ai_result.refactor_suggestions)

        # Output results
        output_format = "json" if options.get("json") else config.output_format
        report_text = self._format_output(summary, config, output_format)

        # Write to file or stdout
        if config.output_file:
            Path(config.output_file).write_text(report_text)
            self.console.success(f"Report written to {config.output_file}")
        elif output_format != "console":
            self.stdout.write(report_text)

        # Summary line
        sev_counts = summary.by_severity
        parts = []
        for sev in reversed(Severity):
            count = sev_counts.get(sev, 0)
            if count:
                parts.append(f"{count} {sev.name.lower()}")

        self.console.info(
            f"\n{summary.files_analyzed} files analyzed in {summary.duration_ms:.0f}ms — "
            f"{summary.total} findings ({', '.join(parts) or 'clean'})"
        )

        # Exit code
        if options.get("no_fail"):
            return

        # --fail-on threshold takes precedence
        fail_on = options.get("fail_on")
        if fail_on:
            threshold = Severity[fail_on.upper()]
            if any(f.severity >= threshold for f in summary.findings):
                sys.exit(1)
            return

        if config.fail_on_error and summary.exit_code:
            sys.exit(summary.exit_code)

    def _build_config(self, options: dict) -> ReviewConfig:
        config = ReviewConfig()

        if options.get("analyzers"):
            config.analyzers = set(options["analyzers"].split(","))

        severity_name = options.get("min_severity", "info").upper()
        config.min_severity = Severity[severity_name]

        config.sort_by = options.get("sort", "severity")

        if options.get("exclude"):
            config.exclude_patterns.extend(options["exclude"].split(","))

        if options.get("ignore_rules"):
            config.ignore_rules = set(options["ignore_rules"].split(","))

        config.ai_enabled = options.get("ai", False)
        config.ai_model = options.get("ai_model", "anthropic/claude-sonnet")
        config.suggest_refactors = options.get("suggest_refactors", False)
        config.fail_on_error = options.get("fail_on_error", True)
        config.output_format = "json" if options.get("json") else options.get("format", "console")
        config.output_file = options.get("output")

        return config

    def _format_output(self, summary, config, output_format: str) -> str:
        if output_format == "console":
            from django_matt.review.reporters.console import report_console

            report_console(summary, config)
            return ""
        if output_format == "markdown":
            from django_matt.review.reporters.markdown import report_markdown

            return report_markdown(summary, config)
        if output_format == "json":
            from django_matt.review.reporters.json_reporter import report_json

            return report_json(summary, config)
        if output_format == "github":
            from django_matt.review.reporters.github import report_github

            return report_github(summary, config)
        return ""

    async def _run_ai_review_full(self, config: ReviewConfig, paths: list[Path]):
        from django_matt.review.ai_reviewer import AIReviewer, AIReviewResult
        from django_matt.review.engine import ReviewEngine

        engine = ReviewEngine(config)
        files_data = []
        for path in paths:
            collected = engine._collect_files([path])
            for f in collected:
                try:
                    source = f.read_text(encoding="utf-8")
                    files_data.append((f, source))
                except (OSError, UnicodeDecodeError):
                    continue

        if not files_data:
            return AIReviewResult()

        reviewer = AIReviewer(config)
        result = await reviewer.review_files(files_data)

        if result.tokens_used:
            self.console.info(f"AI review used {result.tokens_used} tokens")

        return result
