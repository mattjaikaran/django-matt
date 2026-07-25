from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

console = Console()

app = typer.Typer(
    name="schema",
    help="Database schema analysis, visualization, and optimization",
)


def _ensure_django() -> None:
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


@app.command()
def analyze(
    app_label: Optional[str] = typer.Option(None, "--app", "-a", help="Filter by app label"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    _ensure_django()
    from django_matt.schema_designer.analyzer import SchemaAnalyzer, Severity

    app_labels = [app_label] if app_label else None
    analyzer = SchemaAnalyzer(app_labels=app_labels)
    report = analyzer.analyze_all()

    console.print(
        f"\n[bold]Schema Analysis[/] — {len(report.models)} models, {report.total_issues} issues\n"
    )

    severity_colors = {Severity.ERROR: "red", Severity.WARNING: "yellow", Severity.INFO: "blue"}

    for model_report in report.models:
        if not model_report.issues and not verbose:
            continue

        table = Table(title=model_report.full_name, show_header=True)
        table.add_column("Severity", width=8)
        table.add_column("Field")
        table.add_column("Issue")
        table.add_column("Suggestion")

        for issue in model_report.issues:
            color = severity_colors[issue.severity]
            table.add_row(
                f"[{color}]{issue.severity.value.upper()}[/{color}]",
                issue.field_name,
                issue.issue,
                issue.suggestion,
            )

        if model_report.issues:
            console.print(table)
            console.print()

    console.print(
        f"[red]{report.total_errors} errors[/red], "
        f"[yellow]{report.total_warnings} warnings[/yellow], "
        f"[blue]{report.total_info} info[/blue]"
    )


@app.command()
def diagram(
    format: str = typer.Option(
        "mermaid", "--format", "-f", help="Output format: mermaid, dot, dbml, plantuml"
    ),
    app_label: Optional[str] = typer.Option(None, "--app", "-a", help="Filter by app label"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    _ensure_django()
    from django_matt.schema_designer import visualizer

    app_labels = [app_label] if app_label else None
    generators = {
        "mermaid": visualizer.generate_mermaid,
        "dot": visualizer.generate_dot,
        "dbml": visualizer.generate_dbml,
        "plantuml": visualizer.generate_plantuml,
    }

    gen = generators.get(format)
    if not gen:
        console.print(f"[red]Unknown format: {format}[/red]. Use: {', '.join(generators)}")
        raise typer.Exit(1)

    result = gen(app_labels=app_labels)

    if output:
        with open(output, "w") as f:
            f.write(result)
        console.print(f"[green]Written to {output}[/green]")
    else:
        console.print(result)


@app.command()
def optimize(
    app_label: Optional[str] = typer.Option(None, "--app", "-a", help="Filter by app label"),
) -> None:
    _ensure_django()
    from django.apps import apps

    from django_matt.schema_designer.optimizer import SchemaOptimizer

    optimizer = SchemaOptimizer()
    all_models = apps.get_models()
    if app_label:
        all_models = [m for m in all_models if m._meta.app_label == app_label]

    all_suggestions = []
    for model in all_models:
        suggestions = optimizer.suggest_indexes(model)
        all_suggestions.extend(suggestions)

    if not all_suggestions:
        console.print("[green]No index optimizations suggested.[/green]")
        return

    table = Table(title="Index Suggestions", show_header=True)
    table.add_column("Model")
    table.add_column("Field")
    table.add_column("Reason")

    for s in all_suggestions:
        table.add_row(s.model_name, s.field_name, s.reason)

    console.print(table)
    console.print("\n[bold]Migration code:[/bold]\n")
    console.print(optimizer.generate_migration(all_suggestions))


@app.command("export")
def export_schema(
    format: str = typer.Option("json", "--format", "-f", help="Output format: json, yaml"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    _ensure_django()
    from django_matt.schema_designer.analyzer import SchemaAnalyzer

    analyzer = SchemaAnalyzer()
    report = analyzer.analyze_all()
    data = json.loads(report.model_dump_json())

    if format == "yaml":
        try:
            import yaml

            text = yaml.dump(data, default_flow_style=False)
        except ImportError:
            console.print("[red]PyYAML not installed. Use json format or install pyyaml.[/red]")
            raise typer.Exit(1)
    else:
        text = json.dumps(data, indent=2)

    if output:
        with open(output, "w") as f:
            f.write(text)
        console.print(f"[green]Written to {output}[/green]")
    else:
        console.print(text)


@app.command()
def prompt(
    app_label: Optional[str] = typer.Option(None, "--app", "-a", help="Filter by app label"),
    mode: str = typer.Option(
        "schema", "--mode", "-m", help="Prompt mode: schema, review, migration"
    ),
) -> None:
    _ensure_django()
    from django_matt.schema_designer.prompts import (
        generate_review_prompt,
        generate_schema_prompt,
    )

    app_labels = [app_label] if app_label else None

    if mode == "schema":
        result = generate_schema_prompt(app_labels=app_labels)
    elif mode == "review":
        result = generate_review_prompt(app_labels=app_labels)
    else:
        console.print(f"[red]Unknown mode: {mode}[/red]. Use: schema, review")
        raise typer.Exit(1)

    console.print(result)
