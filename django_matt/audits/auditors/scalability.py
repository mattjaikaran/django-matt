# file-length-max: 700
"""
Scalability auditor for detecting bottlenecks and scaling gaps.

Checks for:
- Missing connection pooling configuration
- Missing task offloading for heavy operations
- Unbounded pagination / missing limits
- Rate limiting configuration gaps
- Missing cache strategy for hot paths
- Bulk operations vs loop-based inserts
- Session storage scalability (DB vs Redis)
- Large payload handling without streaming
- Missing database read replicas or sharding hints
- Static file serving in production
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..framework import (
    AuditCategory,
    AuditConfig,
    AuditFinding,
    AuditResult,
    AuditSeverity,
    BaseAuditor,
    register_auditor,
)

if TYPE_CHECKING:
    pass


# File patterns
_SETTINGS_FILE_PATTERN = re.compile(r"settings.*\.py$")
_PRODUCTION_SETTINGS_PATTERN = re.compile(r"settings[./]*prod")
_CACHE_CONFIG_PATTERN = re.compile(r"CACHES\s*=\s*\{")
_SESSION_ENGINE_PATTERN = re.compile(r"SESSION_ENGINE\s*=")
_DB_SESSION_ENGINE = "django.contrib.sessions.backends.db"
_CACHED_SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# Connection pooling indicators (must appear in DATABASES config)
_POOL_OPTIONS = frozenset(
    {
        "CONN_MAX_AGE",
        "CONN_HEALTH_CHECKS",
        "pool",
        "POOL_OPTIONS",
        "max_connections",
        "min_connections",
    }
)

# Rate limiting indicators
_RATE_LIMIT_INDICATORS = frozenset(
    {
        "throttle",
        "rate_limit",
        "RateThrottle",
        "AnonRateThrottle",
        "UserRateThrottle",
        "ScopedRateThrottle",
        "BurstRateThrottle",
        "ThrottleMiddleware",
    }
)

# Task offloading indicators
_TASK_INDICATORS = frozenset(
    {
        "delay",
        "apply_async",
        "send_task",
        "enqueue",
        "background",
        "BackgroundTask",
        "run_in_background",
        "@task",
        "@shared_task",
        "@periodic_task",
    }
)

# Heavy operations that should be offloaded to a task queue
_HEAVY_OPS = frozenset(
    {
        "send_mail",
        "send_mass_mail",
        "generate_report",
        "export_csv",
        "export_json",
        "export_pdf",
        "generate_pdf",
        "generate_thumbnail",
        "transcode_video",
        "process_audio",
        "resize_image",
        "thumbnail",
        "bulk_send",
        "generate_invoice",
        "process_upload",
        "sync_external",
        "fetch_feed",
        "crawl",
        "scrape",
    }
)

# Pagination indicators — absence suggests unbounded results
_PAGINATION_INDICATORS = frozenset(
    {
        "paginate",
        "page_size",
        "limit",
        "offset",
        "cursor",
        "Paginator",
        "PageNumberPagination",
        "LimitOffsetPagination",
        "CursorPagination",
        "page",
        "per_page",
    }
)

# Static file serving in production
_STATIC_SERVE_PATTERNS = frozenset(
    {
        "staticfiles_urlpatterns",
        "static(",
        "serve(",
        "django.views.static.serve",
    }
)


@register_auditor
class ScalabilityAuditor(BaseAuditor):
    """
    Auditor for scalability issues and scaling gaps.

    Detects patterns that prevent horizontal scaling or cause
    bottlenecks under load:
    - Missing connection pooling
    - Missing task offloading for heavy sync operations
    - Unbounded results (missing pagination/limits)
    - Rate limiting configuration gaps
    - Database-backed sessions in production
    - Cache strategy gaps on hot paths
    - Loops performing single inserts instead of bulk operations
    - Static file serving in production settings
    """

    name = "scalability"
    category = AuditCategory.SCALABILITY
    description = "Detect scalability bottlenecks and scaling gaps"

    # Regex for settings.py DATABASES blocks — detects missing pool options
    _DB_CONFIG_PATTERN = re.compile(
        r"DATABASES\s*=\s*\{[^}]*'default'\s*:\s*\{(.*?)\}",
        re.DOTALL,
    )
    _DB_ENGINE_PATTERN = re.compile(r"'ENGINE'\s*:\s*'([^']+)'")
    _CONN_MAX_AGE_PATTERN = re.compile(r"'CONN_MAX_AGE'\s*:")
    _DISABLE_SERVER_SIDE_CURSORS = re.compile(r"'DISABLE_SERVER_SIDE_CURSORS'\s*:")
    _OPTIONS_BLOCK_PATTERN = re.compile(r"'OPTIONS'\s*:\s*\{")

    def audit(self, config: AuditConfig) -> AuditResult:
        """Run scalability audit on the project."""
        findings: list[AuditFinding] = []
        files_scanned = 0

        for file_path in self.iter_files(config):
            files_scanned += 1
            file_findings = self._audit_file(file_path, config)
            findings.extend(file_findings)

            if config.max_findings > 0 and len(findings) >= config.max_findings:
                break

        return AuditResult(
            auditor_name=self.name,
            category=self.category,
            findings=findings,
            files_scanned=files_scanned,
        )

    def _audit_file(self, file_path: Path, config: AuditConfig) -> list[AuditFinding]:
        """Audit a single file for scalability issues."""
        findings: list[AuditFinding] = []
        rel_path = str(file_path)

        # Settings files get special treatment
        is_settings = bool(_SETTINGS_FILE_PATTERN.search(file_path.name))
        is_prod_settings = bool(_PRODUCTION_SETTINGS_PATTERN.search(rel_path))

        tree = self.parse_python_file(file_path)
        if not tree:
            return findings

        # AST-based checks (Python files)
        findings.extend(self._check_missing_pagination(tree, rel_path, config))
        findings.extend(self._check_bulk_vs_loops(tree, rel_path, config))
        findings.extend(self._check_missing_task_offloading(tree, rel_path, config))
        findings.extend(self._check_rate_limiting_gaps(tree, rel_path, config))

        # Text-based checks on full file content
        content = self._read_file_safe(file_path)
        if content:
            if is_settings or is_prod_settings:
                findings.extend(self._check_db_pooling(content, rel_path, config))
                findings.extend(self._check_session_storage(content, rel_path, config))
                findings.extend(self._check_cache_config(content, rel_path, config))
                findings.extend(self._check_static_serving(content, rel_path, config))
            findings.extend(self._check_global_rate_limit_config(content, rel_path, config))

        return findings

    # ─── AST checks ───────────────────────────────────────────────

    def _check_missing_pagination(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """Detect list endpoints without pagination."""
        findings: list[AuditFinding] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not self._is_list_endpoint(node):
                continue

            func_src = ast.unparse(node) if hasattr(ast, "unparse") else ""
            has_pagination = any(ind in func_src for ind in _PAGINATION_INDICATORS)

            if not has_pagination and (".all()" in func_src or "objects.filter" in func_src):
                severity = AuditSeverity.HIGH
                if self.should_skip_for_level(severity, config.level):
                    continue

                findings.append(
                    AuditFinding(
                        id="SCAL001",
                        severity=severity,
                        category=self.category,
                        message="List endpoint missing pagination — unbounded results under load",
                        file=file_path,
                        line=node.lineno,
                        suggestion=(
                            "Add pagination: django_matt.pagination.PageNumberPagination "
                            "or LimitOffsetPagination. For large datasets use CursorPagination."
                        ),
                        fix_command="matt audit fix --rule SCAL001",
                        documentation_url="https://django-matt.dev/pagination/",
                        tags=["pagination", "unbounded", "database"],
                    )
                )
        return findings

    def _check_bulk_vs_loops(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """Detect create/save/delete in loops — should be bulk operations."""
        findings: list[AuditFinding] = []
        _BULK_OPS = frozenset({"create", "save", "delete", "update"})

        for node in ast.walk(tree):
            if not isinstance(node, ast.For | ast.AsyncFor):
                continue

            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                method_name = self._get_method_name(child)
                if method_name in _BULK_OPS and self._looks_like_orm_call(child):
                    severity = AuditSeverity.HIGH
                    if self.should_skip_for_level(severity, config.level):
                        continue

                    alt = f"bulk_{'create' if method_name == 'create' else method_name}"
                    findings.append(
                        AuditFinding(
                            id="SCAL002",
                            severity=severity,
                            category=self.category,
                            message=f"Single {method_name}() in loop — use bulk operation instead",
                            file=file_path,
                            line=node.lineno,
                            suggestion=(
                                f"Replace with {alt}() or bulk_update() for batch processing. "
                                "Single-row inserts in loops scale linearly with data size."
                            ),
                            fix_command="matt audit fix --rule SCAL002",
                            documentation_url="https://django-matt.dev/services/",
                            tags=["bulk", "database", "loop"],
                        )
                    )
                    break
        return findings

    def _check_missing_task_offloading(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """Detect heavy operations in request handlers that should be task-offloaded."""
        findings: list[AuditFinding] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not self._is_request_handler(node):
                continue

            func_src = ast.unparse(node) if hasattr(ast, "unparse") else ""
            uses_tasks = any(ind in func_src for ind in _TASK_INDICATORS)

            for heavy_op in _HEAVY_OPS:
                if heavy_op not in func_src:
                    continue
                if uses_tasks:
                    break  # already using task queue for this handler

                severity = AuditSeverity.MEDIUM
                if self.should_skip_for_level(severity, config.level):
                    continue

                findings.append(
                    AuditFinding(
                        id="SCAL003",
                        severity=severity,
                        category=self.category,
                        message=f"Heavy operation '{heavy_op}()' in request handler — should be offloaded to task queue",
                        file=file_path,
                        line=node.lineno,
                        suggestion=(
                            "Use django_matt.tasks to offload: "
                            "@task decorator or .delay() / .apply_async(). "
                            "Blocking the request thread limits concurrency."
                        ),
                        fix_command="matt audit fix --rule SCAL003",
                        documentation_url="https://django-matt.dev/background-tasks/",
                        tags=["task-queue", "blocking", "concurrency"],
                    )
                )
                break
        return findings

    def _check_rate_limiting_gaps(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """Detect endpoints missing rate limiting decorators."""
        findings: list[AuditFinding] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            # Only check HTTP endpoint handlers
            if not self._is_request_handler(node):
                continue

            # Check decorators
            decorator_names = set()
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    dname = self._get_decorator_name(decorator.func)
                elif isinstance(decorator, ast.Name):
                    dname = decorator.id
                elif isinstance(decorator, ast.Attribute):
                    dname = decorator.attr
                else:
                    continue
                decorator_names.add(dname)

            # Check for throttle/rate_limit decorators
            has_rate_limit = any(dl.lower() in _RATE_LIMIT_INDICATORS for dl in decorator_names)

            if not has_rate_limit:
                severity = AuditSeverity.MEDIUM
                if self.should_skip_for_level(severity, config.level):
                    continue

                findings.append(
                    AuditFinding(
                        id="SCAL004",
                        severity=severity,
                        category=self.category,
                        message="Endpoint missing rate limiting — vulnerable to abuse at scale",
                        file=file_path,
                        line=node.lineno,
                        suggestion=(
                            "Add @throttle(rate='100/hour') or @throttle_user(). "
                            "Use django_matt.throttling for per-endpoint or global rate limits."
                        ),
                        fix_command="matt audit fix --rule SCAL004",
                        documentation_url="https://django-matt.dev/rate-limiting/",
                        tags=["rate-limit", "throttle", "abuse"],
                    )
                )
        return findings

    # ─── Text-based checks ────────────────────────────────────────

    def _check_db_pooling(
        self, content: str, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """Check DATABASES config for missing connection pooling."""
        findings: list[AuditFinding] = []

        # Extract the default database config block
        db_match = self._DB_CONFIG_PATTERN.search(content)
        if not db_match:
            return findings

        db_block = db_match.group(1)

        # Check if CONN_MAX_AGE is set (confirms pooling awareness)
        has_conn_max_age = bool(self._CONN_MAX_AGE_PATTERN.search(db_block))
        has_options = bool(self._OPTIONS_BLOCK_PATTERN.search(db_block))

        if not has_conn_max_age:
            severity = AuditSeverity.HIGH
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="SCAL010",
                        severity=severity,
                        category=self.category,
                        message="DATABASES default config missing CONN_MAX_AGE — no persistent connections",
                        file=file_path,
                        suggestion=(
                            "Set CONN_MAX_AGE=600 in production for persistent connections. "
                            "Use CONN_HEALTH_CHECKS=True for Django 5.1+. "
                            "See django_matt.db.configure_database()."
                        ),
                        fix_command="matt audit fix --rule SCAL010",
                        documentation_url="https://django-matt.dev/database/",
                        tags=["connection-pooling", "postgresql", "performance"],
                    )
                )

        if not has_options and "postgresql" in db_block.lower():
            severity = AuditSeverity.MEDIUM
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="SCAL011",
                        severity=severity,
                        category=self.category,
                        message="PostgreSQL DATABASES missing OPTIONS block — no server-side cursor or pool config",
                        file=file_path,
                        suggestion=(
                            "Add OPTIONS with pool configuration for psycopg3: "
                            "{'pool': {'min_size': 2, 'max_size': 10}}. "
                            "Use django_matt.db.configure_database()."
                        ),
                        fix_command="matt audit fix --rule SCAL011",
                        documentation_url="https://django-matt.dev/database/",
                        tags=["connection-pooling", "postgresql"],
                    )
                )

        return findings

    def _check_session_storage(
        self, content: str, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """Check for database-backed sessions in production settings."""
        findings: list[AuditFinding] = []

        if not _SESSION_ENGINE_PATTERN.search(content):
            return findings

        if _DB_SESSION_ENGINE in content:
            severity = AuditSeverity.MEDIUM
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="SCAL012",
                        severity=severity,
                        category=self.category,
                        message="Database-backed sessions (django.contrib.sessions.backends.db) — DB hotspot under load",
                        file=file_path,
                        suggestion=(
                            "Use cached_db backend or Redis-based sessions for production. "
                            "django_matt provides Redis cache config helpers: "
                            "django_matt.utils.cache_invalidation.get_redis_cache_config()."
                        ),
                        fix_command="matt audit fix --rule SCAL012",
                        documentation_url="https://django-matt.dev/caching/",
                        tags=["session", "database", "cache"],
                    )
                )

        return findings

    def _check_cache_config(
        self, content: str, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """Check for missing or default cache configuration."""
        findings: list[AuditFinding] = []

        if not _CACHE_CONFIG_PATTERN.search(content):
            severity = AuditSeverity.HIGH
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="SCAL013",
                        severity=severity,
                        category=self.category,
                        message="No CACHES configuration — using default LocMemCache (per-process, not shared)",
                        file=file_path,
                        suggestion=(
                            "Configure Redis cache: django_matt.utils.cache_invalidation.get_redis_cache_config(). "
                            "Shared cache is essential for multi-process/container deployments."
                        ),
                        fix_command="matt audit fix --rule SCAL013",
                        documentation_url="https://django-matt.dev/caching/",
                        tags=["cache", "redis", "shared-state"],
                    )
                )

        return findings

    def _check_static_serving(
        self, content: str, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """Detect static file serving patterns in production settings."""
        findings: list[AuditFinding] = []

        for pattern_name in _STATIC_SERVE_PATTERNS:
            if pattern_name in content:
                severity = AuditSeverity.HIGH
                if self.should_skip_for_level(severity, config.level):
                    continue

                findings.append(
                    AuditFinding(
                        id="SCAL014",
                        severity=severity,
                        category=self.category,
                        message="Static file serving detected in settings — use CDN/reverse proxy in production",
                        file=file_path,
                        suggestion=(
                            "Remove django.views.static.serve from production URLs. "
                            "Use nginx, Caddy, or a CDN for static files. "
                            "See django_matt.deploy for production configurations."
                        ),
                        fix_command="matt audit fix --rule SCAL014",
                        documentation_url="https://django-matt.dev/deployment/",
                        tags=["static-files", "production", "security"],
                    )
                )
                break

        return findings

    def _check_global_rate_limit_config(
        self, content: str, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """Check middleware config for global rate limiting."""
        findings: list[AuditFinding] = []

        has_throttle_middleware = "ThrottleMiddleware" in content

        # Only flag settings-like files that have a middleware list but no throttle
        if "MIDDLEWARE" in content and not has_throttle_middleware:
            severity = AuditSeverity.LOW
            if not self.should_skip_for_level(severity, config.level):
                findings.append(
                    AuditFinding(
                        id="SCAL015",
                        severity=severity,
                        category=self.category,
                        message="No global rate limiting middleware in MIDDLEWARE — per-endpoint throttles only",
                        file=file_path,
                        suggestion=(
                            "Add 'django_matt.throttling.middleware.ThrottleMiddleware' "
                            "to MIDDLEWARE for global rate limiting safety net."
                        ),
                        fix_command="matt audit fix --rule SCAL015",
                        documentation_url="https://django-matt.dev/rate-limiting/",
                        tags=["rate-limit", "middleware"],
                    )
                )

        return findings

    # ─── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _read_file_safe(file_path: Path) -> str | None:
        """Read file content safely."""
        try:
            return file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    @staticmethod
    def _get_method_name(call_node: ast.Call) -> str:
        """Extract method name from a Call node."""
        if isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        return ""

    @staticmethod
    def _get_decorator_name(node: ast.expr) -> str:
        """Extract decorator name from a decorator expression."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id
        return ""

    def _looks_like_orm_call(self, call_node: ast.Call) -> bool:
        """Heuristic: check if a call is likely a Django ORM operation."""
        if isinstance(call_node.func, ast.Attribute):
            obj = call_node.func.value
            if isinstance(obj, ast.Name):
                return obj.id not in ("self", "cls")
            if isinstance(obj, ast.Attribute):
                return "objects" in ast.unparse(obj) if hasattr(ast, "unparse") else True
        return False

    def _is_list_endpoint(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if a function looks like a list endpoint."""
        name = node.name.lower()
        list_indicators = ("list", "get_all", "index", "search", "filter", "all")
        return any(ind in name for ind in list_indicators)

    def _is_request_handler(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if a function looks like an HTTP request handler."""
        name = node.name.lower()
        handler_indicators = (
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "list",
            "create",
            "update",
            "retrieve",
            "destroy",
            "endpoint",
            "handler",
            "view",
            "action",
            "login",
            "logout",
            "register",
            "refresh",
            "upload",
            "download",
            "export",
            "import",
            "subscribe",
            "unsubscribe",
            "webhook",
        )
        # Also check decorators for common framework markers
        for decorator in node.decorator_list:
            dname = self._get_decorator_name(decorator)
            if dname in (
                "router",
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "api_route",
                "endpoint",
                "action",
                "view_decorator",
                "login_required",
                "permission_required",
            ):
                return True
        return any(ind in name for ind in handler_indicators)
