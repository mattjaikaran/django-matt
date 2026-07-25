"""
Django management command for running AI-assisted codebase audits.

Usage:
    python manage.py matt_audit                    # Run all audits
    python manage.py matt_audit security          # Run security audit
    python manage.py matt_audit --level strict    # Run with strict level
    python manage.py matt_audit --format json     # Output as JSON
    python manage.py matt_audit bundle            # Run bundle size analysis
    python manage.py matt_audit context           # Generate LLM context
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.core.management.base import BaseCommand, CommandParser

if TYPE_CHECKING:
    pass


class Command(BaseCommand):
    """
    Run AI-assisted codebase audits on the project.

    Provides multi-perspective audits for security, performance,
    best practices, and maintainability with configurable strictness levels.
    """

    help = "Run AI-assisted codebase audits"

    def add_arguments(self, parser: CommandParser) -> None:
        """Add command arguments."""
        parser.add_argument(
            "audit_type",
            nargs="?",
            default="all",
            help="Type of audit: security, performance, scalability, bundle_size, "
            "best_practices, accessibility, maintainability, all, bundle, context",
        )

        parser.add_argument(
            "--level",
            "-l",
            choices=["relaxed", "standard", "strict", "paranoid"],
            default="standard",
            help="Audit strictness level (default: standard)",
        )

        parser.add_argument(
            "--format",
            "-f",
            choices=["text", "json", "markdown", "sarif"],
            default="text",
            help="Output format (default: text)",
        )

        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path (default: stdout)",
        )

        parser.add_argument(
            "--ci",
            action="store_true",
            help="CI mode: exit with non-zero code if issues found",
        )

        parser.add_argument(
            "--fail-on",
            choices=["critical", "high", "medium", "low", "info"],
            default="critical",
            help="Minimum severity to fail on in CI mode (default: critical)",
        )

        parser.add_argument(
            "--max-findings",
            type=int,
            default=0,
            help="Maximum findings to report (0 = unlimited)",
        )

        parser.add_argument(
            "--exclude",
            type=str,
            action="append",
            default=[],
            help="Patterns to exclude (can be specified multiple times)",
        )

        parser.add_argument(
            "--diff",
            type=str,
            help="Only audit files changed since this git ref",
        )

        parser.add_argument(
            "--watch",
            action="store_true",
            help="Watch mode: continuously audit on file changes",
        )

        parser.add_argument(
            "--fix-preview",
            action="store_true",
            help="Show what would be auto-fixed",
        )

        parser.add_argument(
            "--fix",
            action="store_true",
            help="Apply safe auto-fixes",
        )

        parser.add_argument(
            "--for",
            dest="for_model",
            choices=["claude", "gpt", "generic"],
            default="generic",
            help="Optimize context output for specific model",
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        """Execute the audit command."""
        audit_type = options["audit_type"]

        # Handle special audit types
        if audit_type == "bundle":
            return self._handle_bundle_audit(options)
        if audit_type == "context":
            return self._handle_context_generation(options)

        return self._handle_standard_audit(options)

    def _handle_standard_audit(self, options: dict[str, Any]) -> str | None:
        """Run standard code audits."""
        from django_matt.audits import AuditConfig, AuditLevel, run_audit

        audit_type = options["audit_type"]
        level = AuditLevel(options["level"])
        output_format = options["format"]
        output_path = options.get("output")
        ci_mode = options["ci"]

        # Build config
        config = AuditConfig(
            level=level,
            max_findings=options["max_findings"],
            exclude_patterns=[
                "**/migrations/**",
                "**/__pycache__/**",
                *options["exclude"],
            ],
            diff_base=options.get("diff"),
        )

        self.stdout.write(
            self.style.NOTICE(f"Running {audit_type} audit (level: {level.value})...")
        )

        # Run the audit
        report = run_audit(audit_type, level=level, config=config)

        # Format output
        if output_format == "json":
            output = json.dumps(
                {
                    "level": report.level.value,
                    "passed": report.passed,
                    "total_findings": len(report.all_findings),
                    "findings": [f.model_dump() for f in report.all_findings],
                },
                indent=2,
                default=str,
            )
        elif output_format == "markdown":
            output = report.to_markdown()
        elif output_format == "sarif":
            output = json.dumps(report.to_sarif(), indent=2)
        else:
            output = self._format_text_output(report)

        # Write output
        if output_path:
            Path(output_path).write_text(output)
            self.stdout.write(self.style.SUCCESS(f"Report written to {output_path}"))
        else:
            self.stdout.write(output)

        # CI mode exit code
        if ci_mode:
            fail_severity = options["fail_on"]
            should_fail = self._check_failure(report, fail_severity)
            if should_fail:
                self.stderr.write(
                    self.style.ERROR(f"Audit failed: issues at {fail_severity} or above")
                )
                sys.exit(1)

        return None

    def _handle_bundle_audit(self, options: dict[str, Any]) -> str | None:
        """Run bundle size analysis."""
        from django_matt.audits.bundle import analyze_bundle, generate_slim_config

        self.stdout.write(self.style.NOTICE("Analyzing bundle size..."))

        result = analyze_bundle()

        output_format = options["format"]

        if output_format == "json":
            output = result.model_dump_json(indent=2)
        else:
            lines = [
                "",
                self.style.SUCCESS("Bundle Size Analysis"),
                "=" * 50,
                "",
                f"✓ Core modules: {result.core_size_kb:.0f}KB (required)",
                f"  Total size: {result.total_size_kb:.0f}KB",
                f"  Import time: {result.import_time_ms:.0f}ms",
                "",
            ]

            if result.unused_modules:
                lines.append(self.style.WARNING("⚠ Unused modules detected:"))
                for module in result.unused_modules:
                    size = result.module_details.get(module, {}).get("size_kb", 0)
                    lines.append(f"    - {module} ({size:.0f}KB)")
                lines.append("")

            if result.recommendations:
                lines.append(self.style.NOTICE("Recommendations:"))
                for i, rec in enumerate(result.recommendations, 1):
                    lines.append(f"  {i}. {rec}")
                lines.append("")

            # Generate slim config suggestion
            if result.unused_modules:
                lines.append(self.style.NOTICE("Suggested SlimConfig:"))
                lines.append("")
                lines.append(generate_slim_config())
                lines.append("")

            output = "\n".join(lines)

        output_path = options.get("output")
        if output_path:
            Path(output_path).write_text(output)
            self.stdout.write(self.style.SUCCESS(f"Report written to {output_path}"))
        else:
            self.stdout.write(output)

        return None

    def _handle_context_generation(self, options: dict[str, Any]) -> str | None:
        """Generate project context for LLMs."""
        from django_matt.audits.prompts import generate_context

        for_model = options.get("for_model", "generic")

        self.stdout.write(self.style.NOTICE(f"Generating project context for {for_model}..."))

        context = generate_context(for_model=for_model)

        output_format = options["format"]
        if output_format == "json":
            output = context.model_dump_json(indent=2)
        elif for_model == "claude" or output_format == "markdown":
            output = context.to_xml() if for_model == "claude" else context.to_markdown()
        else:
            output = context.to_markdown()

        output_path = options.get("output")
        if output_path:
            Path(output_path).write_text(output)
            self.stdout.write(self.style.SUCCESS(f"Context written to {output_path}"))
        else:
            self.stdout.write(output)

        return None

    def _format_text_output(self, report) -> str:
        """Format report as colored terminal output."""
        from django_matt.audits import AuditSeverity

        lines = [
            "",
            self.style.SUCCESS("Audit Report"),
            "=" * 50,
            "",
            f"Level: {report.level.value}",
            f"Status: {self.style.SUCCESS('PASSED') if report.passed else self.style.ERROR('FAILED')}",
            f"Total Findings: {len(report.all_findings)}",
            "",
        ]

        # Summary by severity
        lines.append("Summary by Severity:")
        severity_styles = {
            AuditSeverity.CRITICAL: self.style.ERROR,
            AuditSeverity.HIGH: self.style.WARNING,
            AuditSeverity.MEDIUM: self.style.NOTICE,
            AuditSeverity.LOW: self.style.HTTP_INFO,
            AuditSeverity.INFO: self.style.HTTP_SUCCESS,
        }

        for severity in AuditSeverity:
            count = sum(1 for f in report.all_findings if f.severity == severity)
            if count > 0:
                style = severity_styles.get(severity, lambda x: x)
                lines.append(f"  {style(severity.value.upper())}: {count}")
        lines.append("")

        # Findings
        if report.all_findings:
            lines.append("Findings:")
            lines.append("-" * 50)

            for finding in report.all_findings[:50]:  # Limit output
                style = severity_styles.get(finding.severity, lambda x: x)
                lines.append(f"\n[{finding.id}] {style(finding.severity.value.upper())}")
                lines.append(finding.message)

                if finding.file:
                    location = finding.file
                    if finding.line:
                        location += f":{finding.line}"
                    lines.append(f"  Location: {location}")

                if finding.suggestion:
                    lines.append(f"  Suggestion: {finding.suggestion}")

            if len(report.all_findings) > 50:
                lines.append(f"\n... and {len(report.all_findings) - 50} more findings")

        return "\n".join(lines)

    def _check_failure(self, report, fail_severity: str) -> bool:
        """Check if audit should fail based on severity threshold."""
        from django_matt.audits import AuditSeverity

        severity_order = [
            AuditSeverity.CRITICAL,
            AuditSeverity.HIGH,
            AuditSeverity.MEDIUM,
            AuditSeverity.LOW,
            AuditSeverity.INFO,
        ]

        try:
            threshold = AuditSeverity(fail_severity)
            threshold_index = severity_order.index(threshold)
        except ValueError:
            return False

        for finding in report.all_findings:
            finding_index = severity_order.index(finding.severity)
            if finding_index <= threshold_index:
                return True

        return False
