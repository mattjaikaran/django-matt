# file-length-max: 600
"""
matt audit — Run AI-assisted codebase audits with diff-mode auto-fixes.

Commands:
    matt audit run          Run audits against the project
    matt audit fix          Apply auto-fix suggestions (with --diff mode)
    matt audit diff         Generate fix diffs without applying
    matt audit list         List available auditors

Examples:
    matt audit run --category scalability --level strict
    matt audit fix --diff --rule SCAL001
    matt audit diff --output-dir patches/
    matt audit run --all --format sarif
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

app = typer.Typer(help="AI-assisted codebase audits with auto-fix")
console = Console()


@app.callback(invoke_without_command=True)
def audit(ctx: typer.Context):
    """Run AI-assisted codebase audits and auto-fixes."""
    if ctx.invoked_subcommand is None:
        console.print(
            Panel.fit(
                "[bold blue]matt audit[/] — Codebase quality and scalability audits\n"
                "Run [bold]matt audit --help[/] for available commands.",
                title="Audit",
            )
        )


@app.command()
def run(
    category: str = typer.Option(
        "all",
        "--category",
        "-c",
        help="Audit category: security, performance, scalability, bundle_size, best_practices, maintainability, all",
    ),
    level: str = typer.Option(
        "standard",
        "--level",
        "-L",
        help="Strictness: relaxed, standard, strict, paranoid",
    ),
    fmt: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, json, markdown, sarif",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write report to file",
    ),
    max_findings: int = typer.Option(
        0,
        "--max-findings",
        help="Maximum findings per auditor (0 = unlimited)",
    ),
    path: Optional[str] = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
):
    """Run audits against the project."""
    try:
        from django_matt.audits import AuditCategory, AuditLevel, run_audit
    except ImportError as e:
        console.print(f"[red]Error: Could not import audit framework: {e}[/]")
        console.print("[dim]Ensure django-matt is installed with audit support.[/]")
        raise typer.Exit(code=1) from e

    valid_categories = {c.value for c in AuditCategory}
    if category not in valid_categories:
        console.print(f"[red]Invalid category: {category}[/]")
        console.print(f"[dim]Valid: {', '.join(sorted(valid_categories))}[/]")
        raise typer.Exit(code=1)

    valid_levels = {lv.value for lv in AuditLevel}
    if level not in valid_levels:
        console.print(f"[red]Invalid level: {level}[/]")
        console.print(f"[dim]Valid: {', '.join(sorted(valid_levels))}[/]")
        raise typer.Exit(code=1)

    cat = AuditCategory(category)
    lvl = AuditLevel(level)

    with console.status("[bold blue]Running audits...[/]"):
        report = run_audit(
            category=cat,
            level=lvl,
            project_path=Path(path) if path else None,
        )

    if fmt == "json":
        _render_json(report, output)
    elif fmt == "markdown":
        _render_markdown(report, output)
    elif fmt == "sarif":
        _render_sarif(report, output)
    else:
        _render_table(report)

    total = len(report.all_findings)
    critical = len(report.critical_findings)
    high = sum(1 for f in report.all_findings if f.severity.value == "high")

    if total == 0:
        console.print("\n[bold green]No issues found![/]")
    else:
        color = "red" if critical > 0 else "yellow"
        console.print(
            f"\n[bold {color}]{total} finding(s)[/] "
            f"([red]{critical} critical[/], [yellow]{high} high[/])"
        )
        if not report.passed:
            console.print("[bold red]Audit FAILED[/] — fix critical issues before deploy.")
            raise typer.Exit(code=report.exit_code)
        console.print("[bold green]Audit PASSED[/]")


@app.command()
def fix(
    rule: Optional[str] = typer.Option(
        None,
        "--rule",
        "-r",
        help="Fix specific rule ID (e.g., SCAL001) or comma-separated list",
    ),
    category: str = typer.Option(
        "all",
        "--category",
        "-c",
        help="Fix findings from a specific category",
    ),
    level: str = typer.Option(
        "standard",
        "--level",
        "-L",
        help="Strictness: relaxed, standard, strict, paranoid",
    ),
    diff: bool = typer.Option(
        False,
        "--diff",
        "-d",
        help="Show diffs without applying changes",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview what would be fixed without changing files",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Confirm each fix before applying",
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output-dir",
        help="Write patch files to directory (implies --diff)",
    ),
    path: Optional[str] = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
):
    """Apply auto-fix suggestions or generate diffs."""
    try:
        from django_matt.audits import AuditCategory, AuditLevel, run_audit
        from django_matt.audits.auditors import ScalabilityAuditor  # noqa: F401
    except ImportError as e:
        console.print(f"[red]Error: Could not import audit framework: {e}[/]")
        raise typer.Exit(code=1) from e

    is_diff_mode = diff or output_dir is not None or dry_run

    rule_filter: set[str] | None = None
    if rule:
        rule_filter = {r.strip().upper() for r in rule.split(",") if r.strip()}

    cat = AuditCategory(category)
    lvl = AuditLevel(level)
    project_path = Path(path) if path else Path.cwd()

    with console.status("[bold blue]Collecting audit findings...[/]"):
        report = run_audit(
            category=cat,
            level=lvl,
            project_path=project_path,
        )

    fixable = [
        f
        for f in report.all_findings
        if f.suggestion and (rule_filter is None or f.id in rule_filter)
    ]

    if not fixable:
        console.print("[yellow]No fixable findings found.[/]")
        return

    console.print(f"\n[bold]Found {len(fixable)} fixable finding(s)[/]\n")

    if is_diff_mode:
        _generate_diffs(fixable, output_dir, project_path)
    else:
        _apply_fixes(fixable, interactive, project_path)

    if not dry_run and not diff:
        console.print("\n[bold green]Fixes applied![/] Review changes with [bold]git diff[/].")


@app.command()
def diff(
    rule: Optional[str] = typer.Option(
        None,
        "--rule",
        "-r",
        help="Show diff for specific rule ID",
    ),
    category: str = typer.Option(
        "all",
        "--category",
        "-c",
        help="Audit category",
    ),
    level: str = typer.Option(
        "standard",
        "--level",
        "-L",
        help="Strictness level",
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Write patch files to directory",
    ),
    path: Optional[str] = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path",
    ),
):
    """Generate fix diffs without applying changes."""
    fix(
        rule=rule,
        category=category,
        level=level,
        diff=True,
        output_dir=output_dir,
        dry_run=False,
        interactive=False,
        path=path,
    )


@app.command(name="list")
def list_command(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List available auditors."""
    try:
        from django_matt.audits.framework import _load_builtin_auditors, list_auditors
    except ImportError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(code=1) from e

    _load_builtin_auditors()
    auditors = list_auditors()

    if json_output:
        data = [
            {
                "name": a.name,
                "category": a.category.value,
                "description": a.description,
            }
            for a in auditors
        ]
        console.print_json(data=data)
        return

    table = Table(title="Available Auditors")
    table.add_column("Name", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("Description")

    for a in auditors:
        table.add_row(a.name, a.category.value, a.description)

    console.print(table)


# ─── Rendering helpers ──────────────────────────────────────────


def _render_table(report) -> None:
    """Render audit report as a Rich table."""
    from django_matt.audits.framework import AuditSeverity

    findings = report.all_findings
    if not findings:
        console.print("[green]No findings.[/]")
        return

    severity_styles = {
        AuditSeverity.CRITICAL: "bold red",
        AuditSeverity.HIGH: "red",
        AuditSeverity.MEDIUM: "yellow",
        AuditSeverity.LOW: "dim",
        AuditSeverity.INFO: "dim cyan",
    }

    table = Table(title="Audit Findings", expand=True)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Severity", width=10)
    table.add_column("Category", width=14)
    table.add_column("File:Line", width=30)
    table.add_column("Message")

    for f in findings:
        style = severity_styles.get(f.severity, "")
        location = f"{f.file or '-'}:{f.line or '-'}"
        table.add_row(
            f.id,
            f"[{style}]{f.severity.value}[/]",
            f.category.value,
            location,
            f.message[:120],
        )

    console.print(table)


def _render_json(report, output: str | None) -> None:
    """Render audit report as JSON."""
    data = report.model_dump(mode="json")
    json_str = json.dumps(data, indent=2, default=str)

    if output:
        Path(output).write_text(json_str)
        console.print(f"[green]Report written to {output}[/]")
    else:
        console.print_json(data=data)


def _render_markdown(report, output: str | None) -> None:
    """Render audit report as Markdown."""
    lines = [
        f"# Audit Report — Level: {report.level.value}",
        "",
        f"**Started:** {report.started_at}",
        f"**Completed:** {report.completed_at}",
        f"**Files Scanned:** {report.total_files}",
        f"**Status:** {'PASSED' if report.passed else 'FAILED'}",
        "",
        "## Findings",
        "",
    ]

    severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪", "info": "🔵"}
    for f in report.all_findings:
        emoji = severity_emoji.get(f.severity.value, "")
        lines.append(f"- **{emoji} [{f.id}]** ({f.severity.value}) — {f.file}:{f.line}")
        lines.append(f"  - {f.message}")
        if f.suggestion:
            lines.append(f"  - *Fix:* {f.suggestion}")
        lines.append("")

    md_str = "\n".join(lines)

    if output:
        Path(output).write_text(md_str)
        console.print(f"[green]Report written to {output}[/]")
    else:
        console.print(md_str)


def _render_sarif(report, output: str | None) -> None:
    """Render audit report as SARIF."""
    sarif = report.to_sarif()
    json_str = json.dumps(sarif, indent=2)

    if output:
        Path(output).write_text(json_str)
        console.print(f"[green]SARIF report written to {output}[/]")
    else:
        console.print(json_str)


# ─── Fix / diff engine ──────────────────────────────────────────


def _generate_diffs(
    findings: list,
    output_dir: str | None,
    project_path: Path,
) -> None:
    """Generate unified diffs for fixable findings using fixer registry."""
    try:
        from django_matt.audits.fixers import generate_all_patches, has_fixer
    except ImportError:
        console.print("[yellow]Fixer engine not available.[/]")
        return

    fixer_findings = [f for f in findings if has_fixer(f.id)]
    fallback_findings = [f for f in findings if not has_fixer(f.id)]

    patches = generate_all_patches(fixer_findings, project_path)

    for finding in fallback_findings:
        if not finding.file or not finding.line:
            continue
        file_path = project_path / finding.file
        if not file_path.exists():
            continue
        patch_lines = _generate_fallback_patch(finding, file_path)
        if patch_lines:
            key = str(file_path)
            if key not in patches:
                patches[key] = [f"--- a/{finding.file}", f"+++ b/{finding.file}"]
            patches[key].extend(patch_lines)

    if not patches:
        console.print("[yellow]No patches could be generated.[/]")
        return

    for file_key, patch_lines in patches.items():
        rel_path = Path(file_key).relative_to(project_path)
        console.print(f"\n[bold cyan]--- {rel_path}[/]")

        patch_text = "\n".join(patch_lines)
        syntax = Syntax(patch_text, "diff", theme="monokai", line_numbers=False)
        console.print(syntax)

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            safe_name = rel_path.name.replace("/", "_")
            patch_file = out_path / f"{safe_name}.patch"
            patch_file.write_text(patch_text)
            console.print(f"[dim]Patch written to {patch_file}[/]")

    fixed_count = len(fixer_findings)
    todo_count = len(fallback_findings)
    parts = []
    if fixed_count:
        parts.append(f"{fixed_count} rule-specific fix(es)")
    if todo_count:
        parts.append(f"{todo_count} TODO annotation(s)")

    console.print(
        f"\n[bold]{len(patches)} file(s) would be changed.[/] "
        f"({', '.join(parts)}) "
        "Apply with [bold]matt audit fix[/] (without --diff)."
    )


def _generate_fallback_patch(finding, file_path: Path) -> list[str] | None:
    """Generate unified diff for findings without specific fixers (TODO annotation)."""
    original_lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
    line_idx = (finding.line or 1) - 1

    if line_idx >= len(original_lines):
        return None

    context_start = max(0, line_idx - 3)
    context_end = min(len(original_lines), line_idx + 4)

    hunk_header = (
        f"@@ -{context_start + 1},{context_end - context_start} "
        f"+{context_start + 1},{context_end - context_start} @@"
    )
    lines = [hunk_header]

    for i in range(context_start, context_end):
        line = original_lines[i].rstrip("\n")
        if i == line_idx:
            lines.append(f"-{line}")
            lines.append(f"+{line}  # TODO: auto-fix {finding.id}")
        else:
            lines.append(f" {line}")

    return lines


def _apply_fixes(
    findings: list,
    interactive: bool,
    project_path: Path,
) -> None:
    """Apply auto-fix suggestions using fixer registry."""
    try:
        from django_matt.audits.fixers import get_fixer, has_fixer
    except ImportError:
        console.print("[yellow]Fixer engine not available.[/]")
        return

    applied = 0
    skipped = 0

    for finding in findings:
        if not finding.file:
            continue

        file_path = project_path / finding.file
        if not file_path.exists():
            console.print(f"[dim]Skipping missing file: {finding.file}[/]")
            skipped += 1
            continue

        if interactive:
            console.print(f"\n[bold]{finding.id}[/] — {finding.message}")
            console.print(f"  File: {finding.file}:{finding.line}")
            console.print(f"  Suggestion: {finding.suggestion}")
            if not typer.confirm("  Apply this fix?", default=True):
                skipped += 1
                continue

        if has_fixer(finding.id):
            fixer = get_fixer(finding.id)
            result = fixer(finding, project_path)
            if result and result.applied:
                console.print(f"  [green]{result.message}[/]")
                applied += 1
            else:
                reason = result.message if result else "no fix generated"
                console.print(f"  [yellow]Skipped: {reason}[/]")
                skipped += 1
        else:
            # Fallback: annotate with TODO
            original = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
            line_idx = (finding.line or 1) - 1
            if line_idx < len(original):
                line = original[line_idx].rstrip("\n")
                if f"TODO: auto-fix {finding.id}" not in line:
                    comment = f"  # TODO: auto-fix {finding.id}"
                    original[line_idx] = f"{line}{comment}\n"
                    file_path.write_text("".join(original), encoding="utf-8")
                    applied += 1
                    tid = finding.id
                    loc = finding.file or "?"
                    line_no = finding.line or 0
                    console.print(f"  [green]Annotated {loc}:{line_no} — TODO: auto-fix {tid}[/]")

    console.print(f"\n[bold]{applied} fix(es) applied, {skipped} skipped.[/]")
