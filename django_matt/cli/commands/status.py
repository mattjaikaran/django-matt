import json
import os
import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Literal

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from django_matt.cli.utils import setup_django

app = typer.Typer(help="Check project health and status")
console = Console()

Tier = Literal["error", "warning", "info"]


@dataclass
class CheckResult:
    """Structured result from a health check."""

    tier: Tier
    name: str
    message: str
    fix: str = ""


def _collect_errors() -> list[CheckResult]:
    """Error tier: must fix. Returns list of CheckResult with tier='error'."""
    results: list[CheckResult] = []

    try:
        from django.conf import settings

        # Access SECRET_KEY via _wrapped to bypass Django's validation guard,
        # so we can report a missing/bad key rather than raising.
        try:
            wrapped = getattr(settings, "_wrapped", settings)
            secret_key = getattr(wrapped, "SECRET_KEY", "")
        except Exception:
            secret_key = ""

        if not secret_key:
            results.append(
                CheckResult(
                    tier="error",
                    name="SECRET_KEY missing",
                    message="SECRET_KEY is not configured",
                    fix="Set SECRET_KEY in your settings file",
                )
            )
        elif secret_key in ("change-me", "changeme", "your-secret-key"):
            results.append(
                CheckResult(
                    tier="error",
                    name="SECRET_KEY insecure",
                    message="SECRET_KEY is set to a known-insecure placeholder",
                    fix=(
                        "Generate a new secret key: "
                        'python -c "from django.core.management.utils import '
                        'get_random_secret_key; print(get_random_secret_key())"'
                    ),
                )
            )

        # django_matt not in INSTALLED_APPS
        try:
            installed_apps = getattr(settings, "INSTALLED_APPS", [])
        except Exception:
            installed_apps = []

        if "django_matt" not in installed_apps:
            results.append(
                CheckResult(
                    tier="error",
                    name="django_matt not installed",
                    message="'django_matt' is not in INSTALLED_APPS",
                    fix="Add 'django_matt' to INSTALLED_APPS in your settings",
                )
            )

        # DATABASES not configured
        try:
            databases = getattr(settings, "DATABASES", {})
        except Exception:
            databases = {}

        if not databases:
            results.append(
                CheckResult(
                    tier="error",
                    name="DATABASES not configured",
                    message="No database configuration found",
                    fix="Add a DATABASES setting to your settings file",
                )
            )

    except Exception as e:
        results.append(
            CheckResult(
                tier="error",
                name="Django settings failed to load",
                message=str(e),
                fix="Ensure DJANGO_SETTINGS_MODULE is set and settings file is valid",
            )
        )

    # Check required imports
    required_modules = ["django", "pydantic", "rich"]
    for module in required_modules:
        try:
            import_module(module)
        except ImportError:
            results.append(
                CheckResult(
                    tier="error",
                    name=f"Required module missing: {module}",
                    message=f"Could not import '{module}'",
                    fix=f"Install the missing dependency: uv add {module}",
                )
            )

    return results


def _collect_warnings() -> list[CheckResult]:
    """Warning tier: should fix. Returns list of CheckResult with tier='warning'."""
    results: list[CheckResult] = []

    try:
        from django.conf import settings

        # DEBUG=True in apparent production
        if getattr(settings, "DEBUG", False):
            dsm = os.environ.get("DJANGO_SETTINGS_MODULE", "")
            if "prod" in dsm or "production" in dsm:
                results.append(
                    CheckResult(
                        tier="warning",
                        name="DEBUG=True in production",
                        message=f"DJANGO_SETTINGS_MODULE='{dsm}' looks like production, but DEBUG=True",
                        fix="Set DEBUG=False in your production settings",
                    )
                )

        # No cache backend configured (using default LocMemCache)
        caches = getattr(settings, "CACHES", {})
        default_cache = caches.get("default", {})
        backend = default_cache.get("BACKEND", "")
        if not backend or "LocMemCache" in backend:
            results.append(
                CheckResult(
                    tier="warning",
                    name="No persistent cache configured",
                    message="Using Django's LocMemCache (in-memory, not shared between processes)",
                    fix="Configure Redis or Memcached: CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': 'redis://127.0.0.1:6379/1'}}",
                )
            )

        # ALLOWED_HOSTS is empty
        allowed_hosts = getattr(settings, "ALLOWED_HOSTS", [])
        if not allowed_hosts:
            results.append(
                CheckResult(
                    tier="warning",
                    name="ALLOWED_HOSTS is empty",
                    message="ALLOWED_HOSTS is not configured",
                    fix="Set ALLOWED_HOSTS to your domain(s) in production",
                )
            )

        # No CORS headers configured
        cors_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", None)
        cors_all = getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False)
        cors_middleware = any("CorsMiddleware" in m for m in getattr(settings, "MIDDLEWARE", []))
        if not cors_middleware and cors_origins is None and not cors_all:
            results.append(
                CheckResult(
                    tier="warning",
                    name="No CORS configuration",
                    message="django-cors-headers is not configured",
                    fix="Install django-cors-headers and add CorsMiddleware + CORS_ALLOWED_ORIGINS",
                )
            )

    except Exception:
        pass

    return results


def _collect_info() -> list[CheckResult]:
    """Info tier: suggestions. Returns list of CheckResult with tier='info'."""
    results: list[CheckResult] = []

    try:
        from django.conf import settings

        # Recommend MATT_API_MODE for API-only projects
        if not getattr(settings, "MATT_API_MODE", False):
            results.append(
                CheckResult(
                    tier="info",
                    name="Consider MATT_API_MODE",
                    message="For API-only projects, enable MATT_API_MODE to strip unused middleware",
                    fix="Add MATT_API_MODE = True to your settings",
                )
            )

        # DI container not configured
        if not getattr(settings, "MATT_DI_CONTAINER", None):
            results.append(
                CheckResult(
                    tier="info",
                    name="DI container not configured",
                    message="Dependency injection container is available but not configured",
                    fix="Set MATT_DI_CONTAINER in settings to enable automatic dependency injection",
                )
            )

        # Suggest caching configuration if not already warned
        caches = getattr(settings, "CACHES", {})
        default_cache = caches.get("default", {})
        backend = default_cache.get("BACKEND", "")
        if backend and "LocMemCache" not in backend:
            results.append(
                CheckResult(
                    tier="info",
                    name="Cache configured",
                    message=f"Cache backend: {backend.split('.')[-1]}",
                )
            )

    except Exception:
        pass

    return results



# ── AI-powered suggestion engine ─────────────────────────────────────────

_DOCTOR_SYSTEM_PROMPT = """\
You are a senior Django infrastructure engineer.
Your task: analyze project health check failures and provide concrete,
actionable fixes. Return structured JSON with fix suggestions.

For each issue, provide:
- "check_name": the name of the failing check
- "tier": "error" or "warning"
- "analysis": 1-2 sentence root cause explanation
- "fix_type": one of "config_patch", "file_edit", "cli_command", "manual"
- "fix_target": the file path (for config_patch or file_edit), or command (for cli_command)
- "fix_diff": unified diff or config snippet to apply
- "rationale": brief explanation of why this fix helps
- "risk": "low", "medium", or "high" — how risky is applying this automatically

Return ONLY valid JSON: {"suggestions": [...]}"""


_DOCTOR_USER_TEMPLATE = """\
Project health check found the following issues.

Project root: {project_root}
Settings module: {settings_module}

{issues_text}

Provide fix suggestions for each issue. Focus on config changes that can
be safely applied. For settings issues, provide exact lines to add or modify.
For missing modules, suggest the exact CLI command.
"""


def _run_ai_suggestions(
    errors: list[CheckResult],
    warnings: list[CheckResult],
    *,
    apply: bool = False,
) -> None:
    """Feed doctor failures to an LLM and display AI-suggested fixes."""
    from django_matt.ai import Message, get_provider

    # ── Resolve AI provider ──────────────────────────────────────────
    try:
        from django.conf import settings

        ai_config = getattr(settings, "DJANGO_MATT_AI", {})
    except Exception:
        ai_config = {}

    provider_name = ai_config.get("DEFAULT_PROVIDER", os.environ.get("MATT_AI_PROVIDER", ""))
    if not provider_name:
        # Try common env vars to detect which provider is configured
        for candidate in ("openai", "anthropic", "gemini", "groq", "deepseek", "ollama"):
            env_key = f"{candidate.upper()}_API_KEY"
            if os.environ.get(env_key) or ai_config.get(env_key):
                provider_name = candidate
                break

    if not provider_name:
        console.print(
            Panel(
                "[yellow]No AI provider configured.[/]\n"
                "Set DJANGO_MATT_AI['DEFAULT_PROVIDER'] in settings or "
                "set MATT_AI_PROVIDER env var.\n"
                "Supported providers: openai, anthropic, gemini, groq, deepseek, ollama",
                title="AI Unavailable",
                border_style="yellow",
            )
        )
        return

    try:
        llm = get_provider(provider_name)
    except Exception as e:
        console.print(
            Panel(
                f"[red]Failed to initialize AI provider '{provider_name}': {e}[/]",
                title="AI Error",
                border_style="red",
            )
        )
        return

    # ── Build prompt ─────────────────────────────────────────────────
    project_root = Path.cwd()
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "unknown")

    issues_lines: list[str] = []
    for tier_name, results in [("ERROR", errors), ("WARNING", warnings)]:
        for r in results:
            issues_lines.append(f"## [{tier_name}] {r.name}")
            issues_lines.append(f"  Issue: {r.message}")
            if r.fix:
                issues_lines.append(f"  Current suggestion: {r.fix}")
            issues_lines.append("")

    issues_text = "\n".join(issues_lines)

    messages = [
        Message.system(_DOCTOR_SYSTEM_PROMPT),
        Message.user(
            _DOCTOR_USER_TEMPLATE.format(
                project_root=project_root,
                settings_module=settings_module,
                issues_text=issues_text,
            )
        ),
    ]

    console.print("[bold cyan]🤖 Asking AI for fix suggestions...[/]\n")

    # ── Call LLM ─────────────────────────────────────────────────────
    try:
        response = llm.complete_sync(
            messages,
            temperature=0.3,
            max_tokens=4096,
        )
    except Exception as e:
        console.print(f"[red]AI call failed: {e}[/]")
        return

    # ── Parse response ───────────────────────────────────────────────
    suggestions = _parse_ai_response(response.content)
    if not suggestions:
        console.print("[yellow]AI returned no structured suggestions.[/]")
        console.print(Panel(response.content[:2000], title="Raw AI Response"))
        return

    # ── Display suggestions ──────────────────────────────────────────
    _display_ai_suggestions(suggestions)

    # ── Apply if requested ───────────────────────────────────────────
    if apply:
        _apply_ai_suggestions(suggestions)


def _parse_ai_response(content: str) -> list[dict[str, Any]]:
    """Extract JSON suggestions from LLM response."""
    # Try to find a JSON block
    import re

    json_match = re.search(r"\{[\s\S]*\"suggestions\"[\s\S]*\}", content)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            return data.get("suggestions", [])
        except json.JSONDecodeError:
            pass

    # Fallback: try parsing the entire response
    try:
        data = json.loads(content)
        return data.get("suggestions", [])
    except json.JSONDecodeError:
        pass

    return []


def _display_ai_suggestions(suggestions: list[dict[str, Any]]) -> None:
    """Render AI fix suggestions as rich panels."""
    if not suggestions:
        return

    console.print(
        Panel(
            f"AI analyzed {len(suggestions)} issue(s) and generated fix suggestions.",
            title="[bold green]AI Fix Suggestions[/]",
            border_style="green",
        )
    )

    for i, s in enumerate(suggestions, 1):
        check_name = s.get("check_name", f"Issue {i}")
        tier = s.get("tier", "unknown")
        analysis = s.get("analysis", "")
        fix_type = s.get("fix_type", "manual")
        fix_target = s.get("fix_target", "")
        fix_diff = s.get("fix_diff", "")
        rationale = s.get("rationale", "")
        risk = s.get("risk", "medium")

        tier_color = "red" if tier == "error" else "yellow"
        risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(risk, "yellow")

        content_parts: list[str] = []

        if analysis:
            content_parts.append(f"[bold]Analysis:[/] {analysis}")
        if rationale:
            content_parts.append(f"[bold]Rationale:[/] {rationale}")
        if fix_target:
            content_parts.append(f"[bold]Target:[/] [cyan]{fix_target}[/]")

        content_parts.append(f"[bold]Risk:[/] [{risk_color}]{risk.upper()}[/]")
        content_parts.append(f"[bold]Type:[/] [dim]{fix_type}[/]")

        if fix_diff:
            lexer = "python" if fix_target and fix_target.endswith(".py") else "text"
            try:
                syntax = Syntax(fix_diff, lexer, theme="monokai", line_numbers=False)
                content_parts.append("[bold]Fix:[/]")
                content_parts.append("")  # spacer before syntax block
            except Exception:
                syntax = None
                content_parts.append(f"[bold]Fix:[/]\n[dim]{fix_diff}[/]")
        else:
            syntax = None

        title = f"[{tier_color}]#{i} {check_name}[/]"

        # Build body without the diff first, then append syntax separately
        body = "\n".join(p for p in content_parts if p and p != "[bold]Fix:[/]")
        if syntax:
            body += "\n"

        console.print(Panel(body, title=title, border_style=tier_color))
        if syntax:
            console.print(syntax)
            console.print()


def _apply_ai_suggestions(suggestions: list[dict[str, Any]]) -> None:
    """Apply AI fix suggestions that are safe to auto-apply."""
    applied_count = 0
    skipped_count = 0
    errors_list: list[str] = []

    for s in suggestions:
        fix_type = s.get("fix_type", "manual")
        risk = s.get("risk", "medium")

        if risk == "high":
            skipped_count += 1
            continue

        if fix_type in ("config_patch", "file_edit"):
            fix_target = s.get("fix_target", "")
            fix_diff = s.get("fix_diff", "")
            check_name = s.get("check_name", "unknown")

            if not fix_target or not fix_diff:
                skipped_count += 1
                continue

            target_path = Path(fix_target)
            if not target_path.is_absolute():
                target_path = Path.cwd() / target_path

            if not target_path.exists():
                skipped_count += 1
                errors_list.append(f"  [{check_name}] Target file not found: {fix_target}")
                continue

            try:
                if _apply_patch(target_path, fix_diff):
                    applied_count += 1
                    console.print(f"  [green]✓[/] Applied: {check_name} → {fix_target}")
                else:
                    skipped_count += 1
                    errors_list.append(f"  [{check_name}] Could not apply patch to {fix_target}")
            except Exception as e:
                skipped_count += 1
                errors_list.append(f"  [{check_name}] Error applying: {e}")

        elif fix_type == "cli_command":
            fix_diff = s.get("fix_diff", "")
            if fix_diff:
                console.print(
                    Panel(
                        f"[cyan]{fix_diff}[/]",
                        title=f"Suggested command for: {s.get('check_name', '?')}",
                        border_style="cyan",
                    )
                )
            skipped_count += 1  # CLI commands are not auto-run

        else:
            skipped_count += 1

    # Summary
    status_color = "green" if applied_count > 0 else "yellow"
    console.print(
        Panel(
            f"Applied: [green]{applied_count}[/]  |  "
            f"Skipped: [yellow]{skipped_count}[/]",
            title="[bold]Apply Summary[/]",
            border_style=status_color,
        )
    )
    if errors_list:
        for err in errors_list:
            console.print(f"[yellow]  ⚠ {err}[/]")
        console.print()


def _apply_patch(target_path: Path, diff_text: str) -> bool:
    """Attempt to apply a unified diff or config snippet to a file.

    Returns True if the patch was successfully applied.
    """
    content = target_path.read_text(encoding="utf-8")

    # Try as unified diff first
    if diff_text.strip().startswith("@@") or diff_text.strip().startswith("---"):
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".diff", delete=False, encoding="utf-8"
        ) as f:
            f.write(diff_text)
            diff_path = f.name

        try:
            result = subprocess.run(
                ["patch", "--dry-run", "-p0", str(target_path), diff_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                # Try with -p1
                result = subprocess.run(
                    ["patch", "--dry-run", "-p1", str(target_path), diff_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

            if result.returncode != 0:
                return False

            # Apply for real
            strip_level = "-p0" if "-p0" in str(result) else "-p1"
            result = subprocess.run(
                ["patch", strip_level, str(target_path), diff_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        finally:
            Path(diff_path).unlink(missing_ok=True)

    # Try as config snippet (add to file)
    if diff_text.strip() not in content:
        new_content = content.rstrip("\n") + "\n\n# Added by matt doctor --ai\n"
        new_content += diff_text.strip() + "\n"
        target_path.write_text(new_content, encoding="utf-8")
        return True

    return False

@app.callback(invoke_without_command=True)
def status(ctx: typer.Context):
    """
    Show project status and health information.
    """
    if ctx.invoked_subcommand is not None:
        return

    doctor()


@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix issues"),
    ai: bool = typer.Option(
        False, "--ai", help="Use LLM to analyze failures and suggest fixes"
    ),
    apply: bool = typer.Option(
        False, "--apply", help="Auto-apply AI-suggested fixes (implies --ai)"
    ),
):
    """
    Run comprehensive project diagnostics with tiered output.

    Reports:
    - Errors (must fix): broken settings, missing modules
    - Warnings (should fix): suboptimal config, missing security
    - Info (suggestions): available but unused features

    Use --ai to get LLM-powered fix suggestions for errors and warnings.
    Use --apply to automatically apply those suggestions.
    """
    if apply:
        ai = True

    setup_django()

    console.print("\n[bold magenta]Project Health Check[/]\n")

    errors = _collect_errors()
    warnings = _collect_warnings()
    infos = _collect_info()

    # Display errors
    if errors:
        error_table = Table(title="[bold red]Errors (Must Fix)[/]", border_style="red")
        error_table.add_column("Check", style="red")
        error_table.add_column("Issue")
        error_table.add_column("Fix", style="dim")
        for r in errors:
            error_table.add_row(r.name, r.message, r.fix)
        console.print(error_table)
        console.print()

    # Display warnings
    if warnings:
        warn_table = Table(title="[bold yellow]Warnings (Should Fix)[/]", border_style="yellow")
        warn_table.add_column("Check", style="yellow")
        warn_table.add_column("Issue")
        warn_table.add_column("Fix", style="dim")
        for r in warnings:
            warn_table.add_row(r.name, r.message, r.fix)
        console.print(warn_table)
        console.print()

    # Display info
    if infos:
        info_table = Table(title="[bold blue]Info (Suggestions)[/]", border_style="blue")
        info_table.add_column("Feature", style="blue")
        info_table.add_column("Message")
        info_table.add_column("Action", style="dim")
        for r in infos:
            info_table.add_row(r.name, r.message, r.fix)
        console.print(info_table)
        console.print()

    # Summary line
    error_count = len(errors)
    warning_count = len(warnings)
    info_count = len(infos)

    summary_color = "red" if error_count else ("yellow" if warning_count else "green")
    summary = (
        f"[{summary_color}]{error_count} errors[/], "
        f"[yellow]{warning_count} warnings[/], "
        f"[blue]{info_count} info[/]"
    )
    console.print(
        Panel(
            summary,
            title="Health Check Complete",
            border_style=summary_color,
        )
    )

    # ── AI-powered fix suggestions ──────────────────────────────────────
    if ai and (errors or warnings):
        _run_ai_suggestions(errors, warnings, apply=apply)

    if error_count:
        raise typer.Exit(1)


@app.command()
def info(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show detailed project information."""
    if not setup_django():
        console.print("[red]Could not set up Django[/]")
        raise typer.Exit(1)

    import django
    from django.apps import apps
    from django.conf import settings

    try:
        from django_matt import __version__ as matt_version
    except (ImportError, AttributeError):
        matt_version = "0.1.0"

    console.print("\n[bold magenta]Project Information[/]\n")

    # Environment info
    console.print("[bold cyan]Environment[/]")
    console.print("─" * 11)

    env_table = Table(show_header=False)
    env_table.add_column("Key", style="dim")
    env_table.add_column("Value", style="green")

    env_table.add_row(
        "Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    env_table.add_row("Django", django.get_version())
    env_table.add_row("django-matt", matt_version)
    env_table.add_row("Debug Mode", "Yes" if settings.DEBUG else "No")

    console.print(env_table)
    console.print()

    # Project stats
    console.print("[bold cyan]Project Stats[/]")
    console.print("─" * 13)

    stats_table = Table(show_header=False)
    stats_table.add_column("Metric", style="dim")
    stats_table.add_column("Count", style="green")

    stats_table.add_row("Installed Apps", str(len(settings.INSTALLED_APPS)))
    stats_table.add_row("Models", str(len(list(apps.get_models()))))
    stats_table.add_row("Middleware", str(len(settings.MIDDLEWARE)))

    console.print(stats_table)
    console.print()

    # Database info
    console.print("[bold cyan]Database[/]")
    console.print("─" * 8)

    for alias in settings.DATABASES:
        db = settings.DATABASES[alias]
        engine = db.get("ENGINE", "").split(".")[-1]
        name = db.get("NAME", "")
        console.print(f"  [cyan]{alias}:[/] {engine} - {name}")

    console.print()


@app.command()
def version():
    """Show django-matt version."""
    try:
        from django_matt import __version__

        version_str = __version__
    except (ImportError, AttributeError):
        version_str = "0.1.0"

    console.print(f"\n[bold magenta]Django Matt[/] v{version_str}\n")
