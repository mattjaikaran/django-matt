#!/usr/bin/env python3
"""Architecture enforcement for django-matt.

Validates:
  L0 foundation ← L1 infrastructure ← L2 domain ← L3 interface
  (lower layers MUST NOT import from higher layers)

  Domain cross-feature ban
  No imports from tests/
  Tooling modules exempt

Usage:
    python scripts/check_architecture.py [files...]
    python scripts/check_architecture.py --all
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Layer definitions ────────────────────────────────────────────────────────

FOUNDATION = {  # L0
    "_accel",
    "api",
    "compat",
    "conf",
    "core",
    "slim",
}

INFRASTRUCTURE = {  # L1
    "audit",
    "batch",
    "config",
    "cqrs",
    "db",
    "di",
    "errors",
    "events",
    "exceptions",
    "files",
    "filtering",
    "interceptors",
    "introspection",
    "loader",
    "middleware",
    "modules",
    "negotiation",
    "observability",
    "pagination",
    "permissions",
    "plugins",
    "prefetch",
    "rpc",
    "rules",
    "secrets",
    "serialization",
    "servers",
    "startup",
    "streaming",
    "tasks",
    "tasks_native",
    "testing",
    "throttling",
    "utils",
    "versioning",
    "wasm",
    "websockets",
}

DOMAIN = {  # L2
    "ai",
    "analytics",
    "auth",
    "billing",
    "email",
    "experiments",
    "flags",
    "messaging",
    "ml",
    "multitenancy",
    "notifications",
}

INTERFACE = {  # L3
    "admin",
    "components",
    "dashboard",
    "docs",
    "forms",
    "graphql",
    "htmx",
    "inertia",
    "livewire",
    "openapi",
    "pages",
    "resources",
    "templates",
    "tailwind",
    "unpoly",
    "views",
    "vite",
}

TOOLING = {  # exempt
    "advisor",
    "benchmarks",
    "changelog_gen",
    "cli",
    "codegen",
    "codemods",
    "deploy",
    "deployment",
    "dev",
    "inspector",
    "management",
    "migration_tools",
    "review",
    "schema_designer",
    "sdkgen",
    "typegen",
    "versioning_tool",
}

_MODULE_LAYER: dict[str, int] = {}
_MODULE_LAYER.update(dict.fromkeys(FOUNDATION, 0))
_MODULE_LAYER.update(dict.fromkeys(INFRASTRUCTURE, 1))
_MODULE_LAYER.update(dict.fromkeys(DOMAIN, 2))
_MODULE_LAYER.update(dict.fromkeys(INTERFACE, 3))

_LAYER_NAME = {0: "foundation", 1: "infrastructure", 2: "domain", 3: "interface"}
_ALL_MODULES = FOUNDATION | INFRASTRUCTURE | DOMAIN | INTERFACE | TOOLING

# ── Exemptions ───────────────────────────────────────────────────────────────

# Modules entirely exempt from all checks (imports from anywhere allowed).
TESTING_EXEMPT = {"testing"}

# API facade file (foundation/api.py) — the top-level surface, imports from anywhere.
API_FACADE_FILE = "django_matt/api.py"

# (source_module, target_module) exempt from LAYER-DEP violations.
ALLOWED_CROSS_LAYER: set[tuple[str, str]] = {
    ("core", "di"),  # core/router.py DI integration
    ("permissions", "multitenancy"),  # org-scoped permissions need tenant models
    ("websockets", "auth"),  # WebSocket auth needs JWT tokens
    ("tasks_native", "admin"),  # intra-module: tasks_native/apps.py → tasks_native/admin/
}

# (source_module, target_module) exempt from CROSS-DOMAIN violations.
ALLOWED_CROSS_DOMAIN: set[tuple[str, str]] = {
    ("ml", "ai"),  # ML models use AI base classes
    ("notifications", "email"),  # notifications deliver via email
    ("experiments", "flags"),  # flags_integration is THE flags bridge
    ("experiments", "analytics"),  # manager analytics bridge
}

# External package prefixes — imports from these are never django-matt modules.
_EXTERNAL_PREFIXES = frozenset(
    {"django.", "rest_framework.", "celery.", "pydantic.", "sqlalchemy."}
)


SKIP_DIRS = {
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "site-packages",
    "dist",
    "build",
    ".tox",
    "eggs",
}
SKIP_MODULES = TOOLING | {"__pycache__", "tests", "test", "migrations"}


@dataclass
class Violation:
    filepath: str
    line: int
    rule: str
    message: str


# ── Resolution helpers ───────────────────────────────────────────────────────


def _top_module(path: str) -> str | None:
    """django_matt/core/router.py → 'core'; django_matt/conf.py → 'conf'."""
    parts = Path(path).parts
    for i, p in enumerate(parts):
        if p == "django_matt" and i + 1 < len(parts):
            cand = parts[i + 1]
            return cand[:-3] if cand.endswith(".py") else (cand if cand in _ALL_MODULES else cand)
    return None


def _eff_layer(path: str, module: str) -> int | None:
    """Effective layer: controller/view files promoted to interface (L3)."""
    base = _MODULE_LAYER.get(module)
    if base is None:
        return None
    fname = Path(path).name
    if "controller" in fname.lower() or "view" in fname.lower():
        return 3
    return base


def _resolve_abs(import_path: str) -> str | None:
    """django_matt.core.router → 'core'; core.schema → 'core'."""
    # Skip known external packages (e.g. django.contrib.admin is not django_matt.admin).
    for prefix in _EXTERNAL_PREFIXES:
        if import_path == prefix.rstrip(".") or import_path.startswith(prefix):
            return None
    parts = import_path.split(".")
    if parts[0] == "django_matt" and len(parts) >= 2:
        return parts[1] if parts[1] in _ALL_MODULES else None
    if parts[0] in _ALL_MODULES:
        return parts[0]
    return None


def _resolve_rel(path: str, node: ast.ImportFrom) -> str | None:
    """Resolve 'from ..core import X' to top-level module using file path."""
    if node.level == 0:
        return None
    parts = Path(path).parts
    pkg: list[str] = []
    in_pkg = False
    for p in parts:
        if p == "django_matt":
            in_pkg = True
            continue
        if in_pkg:
            if p.endswith(".py"):
                break
            pkg.append(p)
    if not in_pkg or node.level > len(pkg):
        return None
    base = pkg[: len(pkg) - node.level] if node.level < len(pkg) else []
    if node.module:
        base.extend(node.module.split("."))
    if base and base[0] in _ALL_MODULES:
        return base[0]
    return pkg[0] if pkg and pkg[0] in _ALL_MODULES else None


# ── Checker ──────────────────────────────────────────────────────────────────


@dataclass
class ArchChecker:
    violations: list[Violation] = field(default_factory=list)
    checked: int = 0

    def check_file(self, fp: Path) -> None:
        rel = str(fp)
        if not rel.endswith(".py"):
            return
        # API facade imports from everywhere — exempt.
        if rel == API_FACADE_FILE:
            return
        mod = _top_module(rel)
        if mod is None or mod in SKIP_MODULES:
            return
        # Testing infrastructure imports from everywhere — exempt.
        if mod in TESTING_EXEMPT:
            return
        layer = _eff_layer(rel, mod)
        if layer is None:
            return
        self.checked += 1

        try:
            src = fp.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src, filename=str(fp))
        except (SyntaxError, UnicodeDecodeError):
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._check(rel, node.lineno, mod, layer, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0 and node.module:
                    res = _resolve_rel(rel, node)
                    if res:
                        self._check(rel, node.lineno, mod, layer, res)
                elif node.module:
                    self._check(rel, node.lineno, mod, layer, node.module)

    def _check(
        self,
        fp: str,
        line: int,
        fmod: str,
        flayer: int,
        ipath: str,
    ) -> None:
        tmod = _resolve_abs(ipath)
        if tmod is None:
            return

        # Intra-module imports (e.g. tasks_native.apps → tasks_native.admin) are always allowed.
        if fmod == tmod:
            return

        if tmod in ("tests", "test"):
            self.violations.append(
                Violation(
                    fp,
                    line,
                    "NO-TEST-IMPORT",
                    f"Import from tests/: '{ipath}' is forbidden.",
                )
            )
            return

        tlayer = _MODULE_LAYER.get(tmod)
        if tlayer is None:
            return

        if flayer < tlayer:
            if (fmod, tmod) not in ALLOWED_CROSS_LAYER:
                self.violations.append(
                    Violation(
                        fp,
                        line,
                        "LAYER-DEP",
                        f"Layer violation: {_LAYER_NAME[flayer]}({fmod}) "
                        f"→ {_LAYER_NAME[tlayer]}({tmod}) via '{ipath}'. "
                        f"Lower layers must not depend on higher layers.",
                    )
                )

        if flayer == 2 and tlayer == 2 and fmod != tmod:
            if (fmod, tmod) not in ALLOWED_CROSS_DOMAIN:
                self.violations.append(
                    Violation(
                        fp,
                        line,
                        "CROSS-DOMAIN",
                        f"Cross-domain: {fmod} → {tmod} via '{ipath}'. "
                        f"Domain features must not import from each other.",
                    )
                )

    def report(self) -> int:
        if not self.violations:
            print(f"✓ Architecture check passed ({self.checked} files checked)")
            return 0
        print(
            f"✗ Architecture check FAILED "
            f"({len(self.violations)} violations in {self.checked} files):\n"
        )
        for v in self.violations:
            print(f"  {v.filepath}:{v.line}  [{v.rule}]")
            print(f"    {v.message}\n")
        return 1


# ── File collection ──────────────────────────────────────────────────────────


def _collect(paths: list[str] | None, check_all: bool) -> list[Path]:
    root = Path("django_matt")
    if check_all or not paths:
        return [f for f in root.rglob("*.py") if not any(p in SKIP_DIRS for p in f.parts)]
    return [Path(p) for p in paths if p.endswith(".py")]


def main() -> int:
    p = argparse.ArgumentParser(description="Check django-matt architecture constraints")
    p.add_argument("files", nargs="*", help="Python files to check")
    p.add_argument("--all", action="store_true", help="Check all files under django_matt/")
    args = p.parse_args()

    files = _collect(args.files, args.all)
    checker = ArchChecker()
    for f in files:
        if f.exists():
            checker.check_file(f)
    return checker.report()


if __name__ == "__main__":
    sys.exit(main())
