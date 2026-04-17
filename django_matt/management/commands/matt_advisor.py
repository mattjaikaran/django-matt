"""
Django Matt code advisor command.

Generates LLM-ready refactoring prompts from review findings.

Usage:
    python manage.py matt_advisor                           # all suggestions
    python manage.py matt_advisor django_matt/auth/jwt.py   # specific file
    python manage.py matt_advisor --min-priority 3          # high priority only
    python manage.py matt_advisor --format json             # for AI agents
    python manage.py matt_advisor --format markdown -o report.md
"""

from __future__ import annotations

from pathlib import Path

from django_matt.cli import MattCommand
from django_matt.review.config import ReviewConfig
from django_matt.review.engine import ReviewEngine
from django_matt.review.findings import Severity

_MIN_SEV_CHOICES = ["info", "hint", "warning", "error", "critical"]


class Command(MattCommand):
    """Generate LLM-ready refactoring prompts from code review findings."""

    help = "Code advisor: structured refactoring prompts for LLMs and AI agents"

    def add_arguments(self, parser) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "paths",
            nargs="*",
            default=["."],
            help="Paths to analyze (default: current directory)",
        )
        parser.add_argument(
            "--analyzers",
            "-a",
            help="Comma-separated analyzers to run",
        )
        parser.add_argument(
            "--min-severity",
            choices=_MIN_SEV_CHOICES,
            default="warning",
            help="Minimum finding severity to generate prompts for (default: warning)",
        )
        parser.add_argument(
            "--min-priority",
            type=int,
            default=1,
            choices=[1, 2, 3, 4, 5],
            help="Minimum priority level (1-5, default: 1)",
        )
        parser.add_argument(
            "--max-count",
            type=int,
            default=None,
            help="Maximum number of prompts to generate",
        )
        parser.add_argument(
            "--format",
            "-f",
            choices=["console", "markdown", "json"],
            default="console",
            help="Output format (default: console)",
        )
        parser.add_argument(
            "--output",
            "-o",
            help="Write report to file instead of stdout",
        )
        parser.add_argument(
            "--context-lines",
            type=int,
            default=10,
            help="Number of context lines around each finding (default: 10)",
        )

    def handle(self, *args, **options) -> None:
        from django_matt.advisor.health import CodeHealthScorer
        from django_matt.advisor.prompts import RefactorPromptGenerator

        # Build config and run review
        config = self._build_config(options)
        paths = [Path(p).resolve() for p in options["paths"]]

        self.console.header("Code Advisor")
        engine = ReviewEngine(config)
        summary = engine.review_paths(paths)

        if not summary.findings:
            self.console.success("No findings to generate prompts for.")
            return

        # Collect source files and LOC
        sources: dict[str, str] = {}
        file_loc: dict[str, int] = {}
        for path in paths:
            for f in engine._collect_files([path]):
                try:
                    source = f.read_text(encoding="utf-8")
                    sources[str(f)] = source
                    file_loc[str(f)] = len(source.splitlines())
                except (OSError, UnicodeDecodeError):
                    continue

        # Score files for health impact context
        scorer = CodeHealthScorer()
        project_health = scorer.score_summary(summary, file_loc)
        file_healths = {fs.file: fs for fs in project_health.file_scores}

        # Generate prompts
        min_sev = Severity[options.get("min_severity", "warning").upper()]
        generator = RefactorPromptGenerator(
            scorer=scorer,
            context_lines=options.get("context_lines", 10),
        )
        prompts = generator.generate_batch(
            findings=summary.findings,
            sources=sources,
            file_healths=file_healths,
            min_severity=min_sev,
            max_count=options.get("max_count"),
        )

        # Filter by priority
        min_priority = options.get("min_priority", 1)
        if min_priority > 1:
            prompts = [p for p in prompts if p.priority >= min_priority]

        if not prompts:
            self.console.success("No refactoring suggestions at the current thresholds.")
            return

        self.console.info(f"{len(prompts)} refactoring suggestion(s)")

        # Output
        fmt = options.get("format", "console")
        output_file = options.get("output")

        if fmt == "json":
            text = generator.format_json(prompts)
        elif fmt == "markdown":
            text = generator.format_markdown(prompts)
        else:
            text = self._format_console(prompts)

        if output_file:
            Path(output_file).write_text(text)
            self.console.success(f"Report written to {output_file}")
        else:
            self.stdout.write(text)

    def _build_config(self, options: dict) -> ReviewConfig:
        config = ReviewConfig()
        if options.get("analyzers"):
            config.analyzers = set(options["analyzers"].split(","))
        return config

    def _format_console(self, prompts) -> str:
        lines = []
        for i, p in enumerate(prompts, 1):
            lines.append(f"\n{'='*60}")
            lines.append(f"  [{i}/{len(prompts)}] {p.summary}")
            lines.append(f"  File: {p.file_path}:{p.line_range[0]}")
            lines.append(f"  Priority: {'*' * p.priority} ({p.priority}/5)")
            lines.append(f"  Effort: {p.estimated_effort}")
            lines.append(f"  Health impact: +{p.health_impact}")
            lines.append(f"{'='*60}")
            lines.append("")
            lines.append(p.prompt)
            lines.append("")
        return "\n".join(lines)
