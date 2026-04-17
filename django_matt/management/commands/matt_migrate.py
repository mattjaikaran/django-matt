"""Management command for migration safety analysis and visualization."""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Analyze migrations for safety issues and visualize dependency graphs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Analyze pending migrations for unsafe DDL patterns.",
        )
        parser.add_argument(
            "--rewrite",
            action="store_true",
            help="Show safe rewrite steps for unsafe migrations.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview only — don't write files.",
        )
        parser.add_argument(
            "--graph",
            action="store_true",
            help="Show migration dependency graph.",
        )
        parser.add_argument(
            "--format",
            choices=["ascii", "dot", "mermaid"],
            default="ascii",
            help="Graph output format (default: ascii).",
        )
        parser.add_argument(
            "--app",
            type=str,
            default=None,
            help="Filter to a specific app.",
        )
        parser.add_argument(
            "--check-cycles",
            action="store_true",
            help="Detect circular dependencies in migration graph.",
        )
        parser.add_argument(
            "--check-conflicts",
            action="store_true",
            help="Detect branch conflicts (multiple leaf migrations per app).",
        )

    def handle(self, **options):
        if options["check"] or options["rewrite"]:
            self._handle_check(options)
        elif options["graph"]:
            self._handle_graph(options)
        elif options["check_cycles"]:
            self._handle_cycles()
        elif options["check_conflicts"]:
            self._handle_conflicts()
        else:
            self.stderr.write(
                "Specify --check, --rewrite, --graph, --check-cycles, or --check-conflicts\n"
            )
            sys.exit(1)

    def _handle_check(self, options):
        from django_matt.migrations.advisor import MigrationAdvisor

        advisor = MigrationAdvisor()

        if options.get("app"):
            issues = advisor.analyze_app(options["app"])
        else:
            issues = advisor.analyze_pending()

        if not issues:
            self.stdout.write(self.style.SUCCESS("No unsafe migration patterns detected."))
            return

        for issue in issues:
            icon = "\u26a0" if issue.severity.value == "warning" else "\u2717"
            self.stdout.write(
                f"\n{icon} {issue.app_label}/{issue.migration_name}"
            )
            self.stdout.write(f"  {issue.operation_description}")
            self.stdout.write(f"  {issue.message}")

            if options["rewrite"] and issue.rewrite:
                self.stdout.write("")
                self.stdout.write(
                    self.style.SUCCESS("  Safe rewrite steps:")
                )
                for i, step in enumerate(issue.rewrite.steps, 1):
                    self.stdout.write(f"    Step {i}: {step.description}")
                    if step.sql and not options.get("dry_run"):
                        for line in step.sql.strip().split("\n"):
                            self.stdout.write(f"      {line}")

        self.stdout.write(f"\n{len(issues)} issue(s) found.")
        if not options["rewrite"]:
            self.stdout.write("Run with --rewrite to see safe alternatives.")

    def _handle_graph(self, options):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        from django_matt.migrations.graph import MigrationGraphRenderer

        loader = MigrationLoader(connection)
        renderer = MigrationGraphRenderer()
        app_label = options.get("app")
        fmt = options["format"]

        if fmt == "dot":
            self.stdout.write(renderer.render_dot(loader.graph, app_label=app_label))
        elif fmt == "mermaid":
            self.stdout.write(renderer.render_mermaid(loader.graph, app_label=app_label))
        else:
            self.stdout.write(renderer.render_ascii(loader.graph, app_label=app_label))

    def _handle_cycles(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        from django_matt.migrations.graph import MigrationGraphRenderer

        loader = MigrationLoader(connection)
        renderer = MigrationGraphRenderer()
        cycles = renderer.detect_cycles(loader.graph)

        if not cycles:
            self.stdout.write(self.style.SUCCESS("No circular dependencies detected."))
        else:
            for cycle in cycles:
                path = " \u2192 ".join(f"{al}.{mn}" for al, mn in cycle)
                self.stdout.write(self.style.ERROR(f"Cycle: {path}"))

    def _handle_conflicts(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        from django_matt.migrations.graph import MigrationGraphRenderer

        loader = MigrationLoader(connection)
        renderer = MigrationGraphRenderer()
        conflicts = renderer.find_conflicts(loader.graph)

        if not conflicts:
            self.stdout.write(self.style.SUCCESS("No branch conflicts detected."))
        else:
            for conflict in conflicts:
                self.stdout.write(
                    self.style.WARNING(
                        f"{conflict.app_label}: {len(conflict.leaves)} leaf migrations "
                        f"({', '.join(conflict.leaves)})"
                    )
                )
