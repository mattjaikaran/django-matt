"""
Per-rule auto-fix generators for audit findings.

Each fixer takes an AuditFinding and returns structured fix data:
- patch_lines: unified diff hunks to apply
- message: description of what was changed

Add new fixers by decorating with @register_fixer(rule_id).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .framework import AuditFinding

# Registry: rule_id -> callable
_FIXER_REGISTRY: dict[str, FixerFunc] = {}

type FixerFunc = callable  # (finding, project_path) -> FixResult | None


class FixResult:
    """Result of applying a fix."""

    def __init__(
        self,
        patch_lines: list[str],
        message: str,
        applied: bool = True,
    ):
        self.patch_lines = patch_lines
        self.message = message
        self.applied = applied

    @classmethod
    def skipped(cls, reason: str) -> FixResult:
        return cls([], reason, applied=False)


def register_fixer(rule_id: str):
    """Decorator to register a fixer for a rule ID."""

    def decorator(func):
        _FIXER_REGISTRY[rule_id] = func
        return func

    return decorator


def get_fixer(rule_id: str) -> FixerFunc | None:
    """Get a fixer function for a rule ID, or None."""
    return _FIXER_REGISTRY.get(rule_id)


def has_fixer(rule_id: str) -> bool:
    """Check if a fixer exists for a rule ID."""
    return rule_id in _FIXER_REGISTRY


# ─── Fixer implementations ──────────────────────────────────────


@register_fixer("SCAL001")
def fix_scal001(finding: AuditFinding, project_path: Path) -> FixResult | None:
    """Add pagination to an unbounded list endpoint."""
    file_path = _resolve_path(finding, project_path)
    if not file_path:
        return FixResult.skipped("file not found")

    content = file_path.read_text(encoding="utf-8")
    line_no = finding.line or 1

    # Find the function and add a pagination decorator
    has_pagination_import = "PageNumberPagination" in content
    has_limit_offset_import = "LimitOffsetPagination" in content

    patch_lines = ["@@ pagination fix @@"]
    import_lines = []

    if not has_pagination_import and not has_limit_offset_import:
        import_lines.append("+from django_matt.pagination import PageNumberPagination")

    # Suggest adding @paginate decorator before the function
    func_line = line_no - 1  # 0-indexed
    patch_lines.extend(import_lines)
    patch_lines.append(
        f"  Add @paginate(PageNumberPagination, page_size=25) above function at line {line_no}"
    )

    return FixResult(
        patch_lines=patch_lines,
        message=(
            "Add @paginate(PageNumberPagination, page_size=25) decorator. "
            "Auto-import added if needed."
        ),
    )


@register_fixer("SCAL002")
def fix_scal002(finding: AuditFinding, project_path: Path) -> FixResult | None:
    """Replace single operation with bulk in loop."""
    file_path = _resolve_path(finding, project_path)
    if not file_path:
        return FixResult.skipped("file not found")

    code = finding.code or ""
    method = ""
    if "create()" in (finding.message or ""):
        method = "bulk_create"
    elif "save()" in (finding.message or ""):
        method = "bulk_update"
    elif "delete()" in (finding.message or ""):
        method = "bulk_delete"
    elif "update()" in (finding.message or ""):
        method = "bulk_update"
    else:
        method = "bulk_create"

    patch_lines = [
        "@@ bulk operation fix @@",
        f"  Replace loop with {method}() call. Pattern:",
        f"  - Accumulate objects in a list, then call {method}(objects) after the loop.",
    ]

    return FixResult(
        patch_lines=patch_lines,
        message=f"Replace looped single operation with {method}(). "
        "Accumulate items in a list and call {method}(items) once after the loop.",
    )


@register_fixer("SCAL004")
def fix_scal004(finding: AuditFinding, project_path: Path) -> FixResult | None:
    """Add @throttle decorator to an endpoint."""
    file_path = _resolve_path(finding, project_path)
    if not file_path:
        return FixResult.skipped("file not found")

    content = file_path.read_text(encoding="utf-8")
    has_throttle_import = "from django_matt.throttling" in content

    patch_lines = ["@@ rate limiting fix @@"]
    if not has_throttle_import:
        patch_lines.append("+from django_matt.throttling import throttle")
    patch_lines.append(f"  +@throttle(rate='100/hour')  # before function at line {finding.line}")

    return FixResult(
        patch_lines=patch_lines,
        message="Add @throttle(rate='100/hour') decorator. "
        "Import added if needed. Adjust rate to match your traffic patterns.",
    )


@register_fixer("SCAL010")
def fix_scal010(finding: AuditFinding, project_path: Path) -> FixResult | None:
    """Add CONN_MAX_AGE to DATABASES config."""
    file_path = _resolve_path(finding, project_path)
    if not file_path:
        return FixResult.skipped("file not found")

    patch_lines = [
        "@@ connection pooling fix @@",
        "  Add to your DATABASES['default'] configuration:",
        "  +    'CONN_MAX_AGE': 600,",
        "  +    'CONN_HEALTH_CHECKS': True,  # Django 5.1+",
    ]

    return FixResult(
        patch_lines=patch_lines,
        message="Set CONN_MAX_AGE=600 in DATABASES['default'] for persistent connections. "
        "Use CONN_HEALTH_CHECKS=True for Django 5.1+.",
    )


@register_fixer("SCAL012")
def fix_scal012(finding: AuditFinding, project_path: Path) -> FixResult | None:
    """Switch from DB sessions to cached_db."""
    file_path = _resolve_path(finding, project_path)
    if not file_path:
        return FixResult.skipped("file not found")

    content = file_path.read_text(encoding="utf-8")
    patch_lines = ["@@ session storage fix @@"]

    if "django.contrib.sessions.backends.db" in content:
        patch_lines.extend(
            [
                "-SESSION_ENGINE = 'django.contrib.sessions.backends.db'",
                "+SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'",
            ]
        )

    return FixResult(
        patch_lines=patch_lines,
        message="Switch SESSION_ENGINE to 'django.contrib.sessions.backends.cached_db'. "
        "Requires CACHES to be configured (see SCAL013).",
    )


@register_fixer("SCAL013")
def fix_scal013(finding: AuditFinding, project_path: Path) -> FixResult | None:
    """Add Redis CACHES configuration."""
    file_path = _resolve_path(finding, project_path)
    if not file_path:
        return FixResult.skipped("file not found")

    patch_lines = [
        "@@ cache configuration fix @@",
        "  Add to your settings:",
        "+CACHES = {",
        "+    'default': {",
        "+        'BACKEND': 'django.core.cache.backends.redis.RedisCache',",
        "+        'LOCATION': env('REDIS_URL', default='redis://127.0.0.1:6379/1'),",
        "+        'OPTIONS': {",
        "+            'CLIENT_CLASS': 'django.core.cache.backends.redis.RedisClient',",
        "+        },",
        "+    },",
        "+}",
    ]

    return FixResult(
        patch_lines=patch_lines,
        message="Add Redis CACHES configuration. "
        "For production, use Redis URL from environment variable."
        "See django_matt.utils.cache_invalidation for helpers.",
    )


@register_fixer("SCAL015")
def fix_scal015(finding: AuditFinding, project_path: Path) -> FixResult | None:
    """Add ThrottleMiddleware to MIDDLEWARE."""
    file_path = _resolve_path(finding, project_path)
    if not file_path:
        return FixResult.skipped("file not found")

    patch_lines = [
        "@@ throttle middleware fix @@",
        "  Add to MIDDLEWARE list (before any auth middleware):",
        "  +    'django_matt.throttling.middleware.ThrottleMiddleware',",
    ]

    return FixResult(
        patch_lines=patch_lines,
        message="Add 'django_matt.throttling.middleware.ThrottleMiddleware' to MIDDLEWARE. "
        "Place before authentication middleware for accurate user identification.",
    )


@register_fixer("BUND001")
def fix_bund001(finding: AuditFinding, project_path: Path) -> FixResult | None:
    """Suggest adding MATT_DISABLED_MODULES to settings."""
    patch_lines = [
        "@@ bundle size fix @@",
        "  Add to your settings:",
        "+MATT_DISABLED_MODULES = [",
        "+    # Add unused modules listed in audit findings",
        "+]",
        "",
        "  Or use slim mode:",
        "+# MattAPI(mode='slim')",
    ]

    return FixResult(
        patch_lines=patch_lines,
        message="Add MATT_DISABLED_MODULES to settings with unused modules. "
        "Alternatively, use MattAPI(mode='slim') for automatic trimming.",
    )


@register_fixer("BUND002")
def fix_bund002(finding: AuditFinding, project_path: Path) -> FixResult | None:
    """Add a specific module to MATT_DISABLED_MODULES."""
    module_match = re.search(r"'(\w+)'", finding.message or "")
    module_name = module_match.group(1) if module_match else "unknown_module"

    patch_lines = [
        f"@@ bundle prune: {module_name} @@",
        "  Add to MATT_DISABLED_MODULES:",
        f"+    '{module_name}',",
    ]

    return FixResult(
        patch_lines=patch_lines,
        message=f"Add '{module_name}' to MATT_DISABLED_MODULES to trim bundle.",
    )


# ─── Helpers ────────────────────────────────────────────────────


def _resolve_path(finding: AuditFinding, project_path: Path) -> Path | None:
    """Resolve the file path for a finding."""
    if not finding.file:
        return None
    fp = project_path / finding.file
    return fp if fp.exists() else None


# ─── Bulk fix runner ────────────────────────────────────────────


def generate_all_patches(
    findings: list[AuditFinding],
    project_path: Path,
) -> dict[str, list[str]]:
    """
    Generate unified diff patches for all fixable findings.

    Returns:
        Dict mapping file path -> list of diff lines.
    """
    patches: dict[str, list[str]] = {}

    for finding in findings:
        if not finding.file:
            continue

        fixer = get_fixer(finding.id)
        if not fixer:
            continue

        result = fixer(finding, project_path)
        if not result or not result.applied:
            continue

        key = finding.file
        if key not in patches:
            patches[key] = [
                f"--- a/{finding.file}",
                f"+++ b/{finding.file}",
            ]
        patches[key].extend(result.patch_lines)

    return patches
