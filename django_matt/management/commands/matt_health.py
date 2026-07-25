"""
Django Matt code health command.

Calculates per-file and project-level health scores from review findings.

Usage:
    python manage.py matt_health                         # project health
    python manage.py matt_health django_matt/auth/       # specific path
    python manage.py matt_health --trend                 # show trend over commits
    python manage.py matt_health --fail-below 6.0        # CI gate
    python manage.py matt_health --format json           # machine-readable
"""

from __future__ import annotations

import sys
from pathlib import Path

from django_matt.cli import MattCommand
from django_matt.review.config import ReviewConfig
from django_matt.review.engine import ReviewEngine


class Command(MattCommand):
    """Calculate code health scores from review findings."""

    help = "Code health: per-file scores (1-10), trending, CI gates"

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
            "--trend",
            action="store_true",
            help="Show health trend over recent commits",
        )
        parser.add_argument(
            "--trend-count",
            type=int,
            default=10,
            help="Number of commits to show in trend (default: 10)",
        )
        parser.add_argument(
            "--record",
            action="store_true",
            help="Record current health snapshot to trend database",
        )
        parser.add_argument(
            "--fail-below",
            type=float,
            default=None,
            help="Exit non-zero if project health falls below this score",
        )
        parser.add_argument(
            "--format",
            "-f",
            choices=["console", "json"],
            default="console",
            help="Output format (default: console)",
        )
        parser.add_argument(
            "--top",
            type=int,
            default=20,
            help="Number of files to show (default: 20)",
        )
        parser.add_argument(
            "--worst",
            action="store_true",
            help="Sort by worst files first (default)",
        )
        parser.add_argument(
            "--best",
            action="store_true",
            help="Sort by best files first",
        )
        parser.add_argument(
            "--db",
            default=".matthealth.db",
            help="Path to health trend database (default: .matthealth.db)",
        )

    def handle(self, *args, **options) -> None:
        from django_matt.advisor.health import CodeHealthScorer, HealthTrend

        # Show trend only
        if options.get("trend"):
            self._show_trend(options)
            return

        # Build config and run review
        config = self._build_config(options)
        paths = [Path(p).resolve() for p in options["paths"]]

        self.console.header("Code Health")
        engine = ReviewEngine(config)
        summary = engine.review_paths(paths)

        # Compute LOC for each analyzed file
        file_loc: dict[str, int] = {}
        for path in paths:
            for f in engine._collect_files([path]):
                try:
                    loc = len(f.read_text(encoding="utf-8").splitlines())
                    file_loc[str(f)] = loc
                except (OSError, UnicodeDecodeError):
                    continue

        scorer = CodeHealthScorer()
        health = scorer.score_summary(summary, file_loc)

        # Output
        fmt = options.get("format", "console")
        if fmt == "json":
            self._output_json(health)
        else:
            self._output_console(health, options)

        # Record to trend DB
        if options.get("record"):
            trend = HealthTrend(db_path=Path(options["db"]))
            sha = HealthTrend.current_commit_sha()
            trend.record(sha, health)
            self.console.success(f"Recorded health snapshot for {sha[:8]}")

            regressions = trend.regressions(health)
            if regressions:
                self.console.warning(f"{len(regressions)} file(s) regressed:")
                for r in regressions[:5]:
                    self.console.warning(
                        f"  {r.file}: {r.old_score:.1f} -> {r.new_score:.1f} ({r.delta:+.1f})"
                    )
            trend.close()

        # CI gate
        fail_below = options.get("fail_below")
        if fail_below is not None and health.score < fail_below:
            self.console.error(f"Health {health.score_rounded} below threshold {fail_below}")
            sys.exit(1)

    def _build_config(self, options: dict) -> ReviewConfig:
        config = ReviewConfig()
        if options.get("analyzers"):
            config.analyzers = set(options["analyzers"].split(","))
        return config

    def _output_console(self, health, options: dict) -> None:
        from rich.table import Table
        from rich.text import Text

        from django_matt.cli.console import console

        rc = console._console

        # Project summary
        score_color = "green" if health.score >= 7 else "yellow" if health.score >= 5 else "red"
        rc.print(
            Text(
                f"\nProject Health: {health.score_rounded}/10 ({health.grade})",
                style=f"bold {score_color}",
            )
        )
        rc.print(
            Text(
                f"{health.total_files} files, {health.total_loc} LOC, {health.total_findings} findings",
                style="dim",
            )
        )

        # File table
        top = options.get("top", 20)
        sort_best = options.get("best", False)

        if sort_best:
            files = sorted(health.file_scores, key=lambda f: -f.score)[:top]
        else:
            files = sorted(health.file_scores, key=lambda f: f.score)[:top]

        table = Table(show_edge=False, pad_edge=False)
        table.add_column("File", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Grade", justify="center")
        table.add_column("LOC", justify="right", style="dim")
        table.add_column("Findings", justify="right")

        for fs in files:
            sc = "green" if fs.score >= 7 else "yellow" if fs.score >= 5 else "red"
            table.add_row(
                fs.file,
                Text(f"{fs.score_rounded}", style=sc),
                Text(fs.grade, style=sc),
                str(fs.loc),
                str(fs.finding_count),
            )

        rc.print()
        rc.print(table)

    def _output_json(self, health) -> None:
        import orjson

        data = {
            "project": {
                "score": health.score_rounded,
                "grade": health.grade,
                "total_files": health.total_files,
                "total_loc": health.total_loc,
                "total_findings": health.total_findings,
            },
            "files": [
                {
                    "file": fs.file,
                    "score": fs.score_rounded,
                    "grade": fs.grade,
                    "loc": fs.loc,
                    "finding_count": fs.finding_count,
                    "deductions": fs.deductions,
                }
                for fs in sorted(health.file_scores, key=lambda f: f.score)
            ],
        }
        self.stdout.write(orjson.dumps(data, option=orjson.OPT_INDENT_2).decode())

    def _show_trend(self, options: dict) -> None:
        from rich.table import Table
        from rich.text import Text

        from django_matt.advisor.health import HealthTrend
        from django_matt.cli.console import console

        rc = console._console
        trend = HealthTrend(db_path=Path(options["db"]))
        snapshots = trend.trend(limit=options.get("trend_count", 10))
        trend.close()

        if not snapshots:
            self.console.warning("No health snapshots recorded yet. Run with --record first.")
            return

        self.console.header("Health Trend")

        table = Table(show_edge=False, pad_edge=False)
        table.add_column("Commit", style="cyan")
        table.add_column("Score", justify="right")
        table.add_column("Grade", justify="center")
        table.add_column("Findings", justify="right")
        table.add_column("Files", justify="right")
        table.add_column("Date", style="dim")

        for s in snapshots:
            sc = "green" if s.score >= 7 else "yellow" if s.score >= 5 else "red"
            table.add_row(
                s.commit_sha[:8],
                Text(f"{round(s.score, 1)}", style=sc),
                Text(s.grade, style=sc),
                str(s.total_findings),
                str(s.total_files),
                s.timestamp,
            )

        rc.print(table)
