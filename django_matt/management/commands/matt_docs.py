"""
Django management command for documentation analysis and generation.

Usage:
    python manage.py matt_docs coverage              # Show coverage stats
    python manage.py matt_docs stubs                 # Generate docstring stubs
    python manage.py matt_docs stubs --module core   # Generate for specific module
    python manage.py matt_docs hints                 # Show missing type hints
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser


class Command(BaseCommand):
    """
    Analyze and improve code documentation.

    Provides tools for measuring documentation coverage and generating
    docstring stubs for undocumented functions and classes.
    """

    help = "Analyze and improve code documentation"

    def add_arguments(self, parser: CommandParser) -> None:
        """Add command arguments."""
        parser.add_argument(
            "action",
            choices=["coverage", "stubs", "hints"],
            help="Action to perform: coverage, stubs, or hints",
        )

        parser.add_argument(
            "--module",
            "-m",
            type=str,
            help="Specific module to analyze (e.g., 'core', 'auth')",
        )

        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file for stubs",
        )

        parser.add_argument(
            "--style",
            choices=["google", "numpy", "sphinx"],
            default="google",
            help="Docstring style (default: google)",
        )

        parser.add_argument(
            "--threshold",
            type=float,
            default=80.0,
            help="Minimum coverage threshold for CI (default: 80.0)",
        )

        parser.add_argument(
            "--ci",
            action="store_true",
            help="CI mode: exit non-zero if below threshold",
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        """Execute the docs command."""
        action = options["action"]

        if action == "coverage":
            return self._handle_coverage(options)
        if action == "stubs":
            return self._handle_stubs(options)
        if action == "hints":
            return self._handle_hints(options)

        return None

    def _handle_coverage(self, options: dict[str, Any]) -> str | None:
        """Show documentation coverage statistics."""
        from django_matt.audits.docs_helper import calculate_doc_coverage

        module = options.get("module")
        threshold = options.get("threshold", 80.0)
        ci_mode = options.get("ci", False)

        if module:
            path = Path("django_matt") / module
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"Module not found: {module}"))
                return None
        else:
            path = Path("django_matt")

        self.stdout.write(self.style.NOTICE(f"Analyzing documentation coverage for {path}..."))

        stats = calculate_doc_coverage(path)

        # Display results
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Documentation Coverage Report"))
        self.stdout.write("=" * 50)
        self.stdout.write("")

        # Docstring coverage
        doc_pct = stats["coverage_pct"]
        doc_style = self.style.SUCCESS if doc_pct >= threshold else self.style.WARNING
        self.stdout.write(f"Docstring Coverage: {doc_style(f'{doc_pct:.1f}%')}")
        self.stdout.write(f"  Documented: {stats['documented_items']}/{stats['total_items']}")
        self.stdout.write("")

        # Parameter type coverage
        param_pct = stats["param_coverage_pct"]
        param_style = self.style.SUCCESS if param_pct >= threshold else self.style.WARNING
        self.stdout.write(f"Parameter Type Coverage: {param_style(f'{param_pct:.1f}%')}")
        self.stdout.write(f"  Typed: {stats['typed_params']}/{stats['total_params']}")
        self.stdout.write("")

        # Return type coverage
        return_pct = stats["return_coverage_pct"]
        return_style = self.style.SUCCESS if return_pct >= threshold else self.style.WARNING
        self.stdout.write(f"Return Type Coverage: {return_style(f'{return_pct:.1f}%')}")
        self.stdout.write(f"  Typed: {stats['typed_returns']}/{stats['total_returns']}")
        self.stdout.write("")

        # Overall assessment
        overall = (doc_pct + param_pct + return_pct) / 3
        if overall >= 90:
            self.stdout.write(self.style.SUCCESS("✓ Excellent documentation!"))
        elif overall >= 80:
            self.stdout.write(self.style.SUCCESS("✓ Good documentation coverage"))
        elif overall >= 60:
            self.stdout.write(self.style.WARNING("⚠ Documentation needs improvement"))
        else:
            self.stdout.write(self.style.ERROR("✗ Poor documentation coverage"))

        # CI mode
        if ci_mode:
            if doc_pct < threshold:
                self.stderr.write(
                    self.style.ERROR(
                        f"Docstring coverage {doc_pct:.1f}% below threshold {threshold}%"
                    )
                )
                return "1"
            if param_pct < threshold:
                self.stderr.write(
                    self.style.ERROR(
                        f"Parameter type coverage {param_pct:.1f}% below threshold {threshold}%"
                    )
                )
                return "1"

        return None

    def _handle_stubs(self, options: dict[str, Any]) -> str | None:
        """Generate docstring stubs for undocumented items."""
        from django_matt.audits.docs_helper import batch_generate_stubs

        module = options.get("module")
        output_file = options.get("output")
        style = options.get("style", "google")

        if module:
            path = Path("django_matt") / module
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"Module not found: {module}"))
                return None
        else:
            path = Path("django_matt")

        self.stdout.write(self.style.NOTICE(f"Generating docstring stubs for {path}..."))

        if not output_file:
            output_file = "DOCS_TODO.md"

        stubs = batch_generate_stubs(path, output_file=output_file, style=style)

        total_stubs = sum(len(s) for s in stubs.values())
        self.stdout.write(self.style.SUCCESS(f"Generated {total_stubs} stubs in {output_file}"))

        # Show summary
        if stubs:
            self.stdout.write("")
            self.stdout.write("Files needing documentation:")
            for file_path, file_stubs in sorted(stubs.items())[:20]:
                self.stdout.write(f"  {file_path}: {len(file_stubs)} items")

            if len(stubs) > 20:
                self.stdout.write(f"  ... and {len(stubs) - 20} more files")

        return None

    def _handle_hints(self, options: dict[str, Any]) -> str | None:
        """Show missing type hints."""
        from django_matt.audits.docs_helper import generate_type_hints_stub

        module = options.get("module")
        output_file = options.get("output")

        if module:
            path = Path("django_matt") / module
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"Module not found: {module}"))
                return None
        else:
            path = Path("django_matt")

        self.stdout.write(self.style.NOTICE(f"Finding missing type hints in {path}..."))

        all_hints = []
        for py_file in path.rglob("*.py"):
            if any(
                part in py_file.parts
                for part in ("__pycache__", "migrations", ".git", "venv", ".venv")
            ):
                continue

            hints = generate_type_hints_stub(py_file)
            if hints:
                all_hints.append(f"\n## {py_file}\n{hints}")

        if output_file:
            Path(output_file).write_text("# Missing Type Hints\n" + "\n".join(all_hints))
            self.stdout.write(self.style.SUCCESS(f"Wrote hints to {output_file}"))
        else:
            for section in all_hints[:10]:
                self.stdout.write(section)

            if len(all_hints) > 10:
                self.stdout.write(self.style.WARNING(f"\n... and {len(all_hints) - 10} more files"))

        return None
