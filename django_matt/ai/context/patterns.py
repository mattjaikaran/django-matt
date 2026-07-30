"""
Pattern detector for django-matt AI context generation.

Scans the project filesystem (no Django models loaded) to detect
project conventions and emits agent-readable rules for inclusion
in CONTEXT.md files.

Usage:
    detector = PatternDetector()
    rules = detector.detect()
    for rule in rules:
        print(rule.to_markdown())
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DetectedPattern:
    """A single detected project convention."""

    category: str  # e.g. "architecture", "data", "auth", "performance"
    name: str  # short label, e.g. "Service Layer", "Soft Delete"
    rule: str  # agent directive, e.g. "Always put business logic in services/"
    guidance: str  # longer explanation / import hint
    evidence: list[str] = field(default_factory=list)  # files that prove it

    def to_markdown(self) -> str:
        """Render as a Markdown list item suitable for CONTEXT.md."""
        lines = [f"- **{self.name}**: {self.rule}"]
        if self.guidance:
            lines.append(f"  {self.guidance}")
        return "\n".join(lines)


class PatternDetector:
    """
    Scans a project for known django-matt conventions.

    Operates purely on filesystem scanning — no Django imports,
    no settings dependency. Safe to run at any time.
    """

    # ------------------------------------------------------------------
    # Detection configuration
    # ------------------------------------------------------------------

    # File patterns to skip
    _IGNORE_DIRS: frozenset[str] = frozenset(
        {
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "htmlcov",
            "dist",
            "build",
            "migrations",
            ".planning",
            ".cursor",
            ".claude",
            ".github",
            "eggs",
            ".eggs",
            ".tox",
        }
    )

    _PY_FILE_GLOB = "**/*.py"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else Path.cwd()

    def detect(self) -> list[DetectedPattern]:
        """Run all detectors and return found patterns."""
        py_files = self._collect_py_files()
        patterns: list[DetectedPattern] = []

        # Architecture
        patterns.extend(self._detect_service_layer(py_files))
        patterns.extend(self._detect_controllers(py_files))

        # Data
        patterns.extend(self._detect_soft_delete(py_files))
        patterns.extend(self._detect_uuid_pk(py_files))
        patterns.extend(self._detect_timestamps(py_files))

        # Auth
        patterns.extend(self._detect_jwt_auth(py_files))
        patterns.extend(self._detect_api_keys(py_files))

        # Performance
        patterns.extend(self._detect_caching(py_files))
        patterns.extend(self._detect_connection_pooling(py_files))
        patterns.extend(self._detect_rate_limiting(py_files))

        # Code quality
        patterns.extend(self._detect_async_orm(py_files))
        patterns.extend(self._detect_error_handling(py_files))

        return patterns

    def generate_markdown(self) -> str:
        """Generate a Markdown section for CONTEXT.md."""
        patterns = self.detect()
        if not patterns:
            return ""

        lines = ["## Detected Project Conventions", ""]
        lines.append(
            "_Auto-detected patterns from codebase analysis. "
            "These rules reflect actual conventions found in this project._"
        )
        lines.append("")

        # Group by category
        categories: dict[str, list[DetectedPattern]] = {}
        for p in patterns:
            categories.setdefault(p.category, []).append(p)

        cat_labels = {
            "architecture": "Architecture Patterns",
            "data": "Data Patterns",
            "auth": "Authentication Patterns",
            "performance": "Performance Patterns",
            "code_quality": "Code Quality Patterns",
        }

        for cat, cat_patterns in categories.items():
            label = cat_labels.get(cat, cat.replace("_", " ").title())
            lines.append(f"### {label}")
            lines.append("")
            for p in cat_patterns:
                lines.append(p.to_markdown())
                if p.evidence:
                    files = ", ".join(f"`{e}`" for e in p.evidence[:3])
                    lines.append(f"  _Found in: {files}_")
                lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # File collection
    # ------------------------------------------------------------------

    def _collect_py_files(self) -> list[Path]:
        """Collect all .py files under root, skipping ignored dirs."""
        files: list[Path] = []
        for py_file in self.root.rglob(self._PY_FILE_GLOB):
            parts = set(py_file.parts)
            if parts & self._IGNORE_DIRS:
                continue
            files.append(py_file)
        return files

    # Overrideable for testing — in production uses rglob, tests can inject
    def _collect_py_files_from_paths(self, paths: list[Path]) -> list[Path]:
        return [p for p in paths if not (set(p.parts) & self._IGNORE_DIRS)]

    # ------------------------------------------------------------------
    # File content helpers
    # ------------------------------------------------------------------

    def _read_file(self, path: Path) -> str | None:
        """Safely read a file's text content."""
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            return None

    def _scan_files(self, pattern: str | re.Pattern, files: list[Path]) -> list[Path]:
        """Return files whose content matches `pattern`."""
        regex = re.compile(pattern) if isinstance(pattern, str) else pattern
        matches: list[Path] = []
        for f in files:
            content = self._read_file(f)
            if content and regex.search(content):
                matches.append(f)
        return matches

    def _short_path(self, path: Path) -> str:
        """Return path relative to project root."""
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    # ------------------------------------------------------------------
    # Architecture detectors
    # ------------------------------------------------------------------

    def _detect_service_layer(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect service layer pattern usage."""
        evidence = self._scan_files(
            r"(CRUDService|BaseService|BaseThirdPartyService)",
            files,
        )
        if not evidence:
            return []

        return [
            DetectedPattern(
                category="architecture",
                name="Service Layer",
                rule="This project uses a service layer pattern — always put business "
                "logic in service classes, not in controllers or views.",
                guidance="Import from `django_matt.services`: "
                "`CRUDService`, `BaseService`, `BaseThirdPartyService`.",
                evidence=[self._short_path(p) for p in evidence[:5]],
            )
        ]

    def _detect_controllers(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect APIController / controller pattern usage."""
        evidence = self._scan_files(r"class \w+\(APIController\)", files)
        if not evidence:
            return []

        return [
            DetectedPattern(
                category="architecture",
                name="API Controllers",
                rule="Controllers extend `APIController` — group related endpoints "
                "under a shared prefix with class-based organization.",
                guidance=(
                    "Use `@api.get` / `@api.post` decorators. "
                    "Set `prefix` and `tags` on the controller class."
                ),
                evidence=[self._short_path(p) for p in evidence[:5]],
            )
        ]

    # ------------------------------------------------------------------
    # Data detectors
    # ------------------------------------------------------------------

    def _detect_soft_delete(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect soft delete pattern (SoftDeleteMixin, deleted_at field)."""
        mixin_evidence = self._scan_files(r"SoftDeleteMixin|SoftDeleteWithUserMixin", files)
        field_evidence = self._scan_files(r"deleted_at\s*=", files)

        evidence = mixin_evidence + field_evidence
        if not evidence:
            return []

        rules: list[str] = []
        guidance_parts: list[str] = []

        if mixin_evidence:
            rules.append("never call `.delete()` directly — use `.soft_delete()`")
            rules.append("query via `Model.objects.all()` (automatically excludes deleted)")
            guidance_parts.append("Use `SoftDeleteMixin` from `django_matt.db.soft_delete`.")

        if field_evidence:
            rules.append("filter out soft-deleted rows with `deleted_at__isnull=True`")
            guidance_parts.append("`deleted_at` DateTimeField tracks deletion timestamp.")

        return [
            DetectedPattern(
                category="data",
                name="Soft Delete",
                rule="This project uses soft delete — " + "; ".join(rules) + ".",
                guidance=" ".join(guidance_parts),
                evidence=[self._short_path(p) for p in evidence[:5]],
            )
        ]

    def _detect_uuid_pk(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect UUID primary key pattern."""
        evidence = self._scan_files(
            r"(id\s*=\s*models\.UUIDField|uuid4|UUIDField\s*\()",
            files,
        )
        if not evidence:
            return []

        return [
            DetectedPattern(
                category="data",
                name="UUID Primary Keys",
                rule="Models use UUID primary keys — never rely on sequential integer "
                "IDs for external references or URL patterns.",
                guidance="Use `id = models.UUIDField(primary_key=True, default=uuid.uuid4)`.",
                evidence=[self._short_path(p) for p in evidence[:5]],
            )
        ]

    def _detect_timestamps(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect timestamp patterns (created_at, updated_at)."""
        created = self._scan_files(r"created_at\s*=", files)
        updated = self._scan_files(r"updated_at\s*=", files)
        evidence = created + updated

        if len(evidence) < 2:
            return []

        return [
            DetectedPattern(
                category="data",
                name="Timestamp Fields",
                rule="Models use `created_at` / `updated_at` timestamp fields — "
                "always set `auto_now_add=True` and `auto_now=True` respectively.",
                guidance="Standard django_matt timestamp convention.",
                evidence=[self._short_path(p) for p in evidence[:5]],
            )
        ]

    # ------------------------------------------------------------------
    # Auth detectors
    # ------------------------------------------------------------------

    def _detect_jwt_auth(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect JWT authentication pattern."""
        evidence = self._scan_files(
            r"(jwt_required|jwt_optional|encode_jwt|decode_jwt|JWTError|create_token_pair)",
            files,
        )
        # Also check for the jwt auth module itself
        jwt_modules = [
            f for f in files if "auth/jwt.py" in str(f) or "auth/jwt_builtin.py" in str(f)
        ]
        all_evidence = evidence + jwt_modules

        if not all_evidence:
            return []

        return [
            DetectedPattern(
                category="auth",
                name="JWT Authentication",
                rule="This project uses JWT authentication — import from "
                "`django_matt.auth`, use `@jwt_required` decorator, "
                "and `create_token_pair()` for token generation.",
                guidance=(
                    "Key imports: `from django_matt.auth import jwt_required, create_token_pair`. "
                    "Access user via `request.user`."
                ),
                evidence=[self._short_path(p) for p in all_evidence[:5]],
            )
        ]

    def _detect_api_keys(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect API key authentication pattern."""
        evidence = self._scan_files(
            r"(ApiKeyAuth|API_KEY|api_key_auth|ApiKey\b)",
            files,
        )
        if not evidence:
            return []

        return [
            DetectedPattern(
                category="auth",
                name="API Key Authentication",
                rule="API key authentication detected — use `ApiKeyAuth` "
                "backend and validate keys via `django_matt.auth`.",
                guidance="Configure `DJANGO_MATT_AUTH['API_KEY_BACKEND']` in settings.",
                evidence=[self._short_path(p) for p in evidence[:5]],
            )
        ]

    # ------------------------------------------------------------------
    # Performance detectors
    # ------------------------------------------------------------------

    def _detect_caching(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect caching infrastructure."""
        redis_evidence = self._scan_files(
            r"(redis\.from_url|RedisBackend|REDIS_URL|redis://|CachedLLM|CachedEmbeddings)",
            files,
        )
        cache_config = self._scan_files(
            r"CACHES\s*=",
            files,
        )

        evidence = redis_evidence + cache_config
        if not evidence:
            return []

        rules: list[str] = []
        guidance_parts: list[str] = []

        if redis_evidence:
            rules.append("use `django.core.cache.caches['redis']` for shared cache")
            guidance_parts.append(
                "Configure Redis via `django_matt.utils.cache_invalidation` "
                "or `django_matt.config`."
            )

        if cache_config:
            rules.append(
                "cache configuration found — prefer shared cache (Redis) "
                "over LocMemCache in production"
            )
            if not guidance_parts:
                guidance_parts.append("Check `settings.py` for `CACHES` dict configuration.")

        return [
            DetectedPattern(
                category="performance",
                name="Caching Infrastructure",
                rule="This project uses caching — " + "; ".join(rules) + ".",
                guidance=" ".join(guidance_parts),
                evidence=[self._short_path(p) for p in evidence[:5]],
            )
        ]

    def _detect_connection_pooling(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect database connection pooling."""
        evidence = self._scan_files(
            r"(CONN_MAX_AGE|POOL_SIZE|MAX_OVERFLOW|pool_size|connection_pool|DATABASE_URL)",
            files,
        )
        if not evidence:
            return []

        return [
            DetectedPattern(
                category="performance",
                name="Connection Pooling",
                rule="Database connection pooling detected — configure "
                "`CONN_MAX_AGE`, `POOL_SIZE`, and `MAX_OVERFLOW` in "
                "`DATABASES['default']['OPTIONS']`.",
                guidance="Use `django_matt.db` connection pool helpers.",
                evidence=[self._short_path(p) for p in evidence[:5]],
            )
        ]

    def _detect_rate_limiting(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect rate limiting / throttling."""
        evidence = self._scan_files(
            r"(throttle|rate_limit|Throttle|RateLimiter|TokenBucket)",
            files,
        )
        # Also check if throttling module exists
        throttle_modules = [f for f in files if "django_matt/throttling" in str(f)]
        all_evidence = evidence + throttle_modules

        if not all_evidence:
            return []

        return [
            DetectedPattern(
                category="performance",
                name="Rate Limiting",
                rule="Throttling/rate limiting detected — use "
                "`django_matt.throttling` decorators and middleware "
                "for endpoint protection.",
                guidance=(
                    "Key imports: `from django_matt.throttling import throttle`. "
                    "Configure backends in `DJANGO_MATT_THROTTLING`."
                ),
                evidence=[self._short_path(p) for p in all_evidence[:5]],
            )
        ]

    # ------------------------------------------------------------------
    # Code quality detectors
    # ------------------------------------------------------------------

    def _detect_async_orm(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect async ORM usage pattern."""
        evidence = self._scan_files(
            r"(await .*\.(asave|adelete|acreate|aupdate|abulk_create)|async for.*objects\.)",
            files,
        )
        # Weaker signal: any use of async def with model operations
        if not evidence:
            evidence = self._scan_files(
                r"(aget|afilter|aall|acount|afirst)\(",
                files,
            )

        if not evidence:
            return []

        return [
            DetectedPattern(
                category="code_quality",
                name="Async ORM",
                rule="This project uses async ORM — always use async methods: "
                "`.aget()` not `.get()`, `.asave()` not `.save()`, "
                "`async for` over QuerySets.",
                guidance=(
                    "NEVER use sync ORM in async context. "
                    "Wrap sync code with `sync_to_async()` when unavoidable."
                ),
                evidence=[self._short_path(p) for p in evidence[:5]],
            )
        ]

    def _detect_error_handling(self, files: list[Path]) -> list[DetectedPattern]:
        """Detect custom error handling patterns."""
        evidence = self._scan_files(
            r"(APIError|NotFoundAPIError|ValidationAPIError|PermissionAPIError|raise .*Error)",
            files,
        )
        # Narrower: detect django_matt error hierarchy
        structured = self._scan_files(
            r"from django_matt\.core\.errors import",
            files,
        )
        all_evidence = evidence + structured

        if len(all_evidence) < 2:
            return []

        return [
            DetectedPattern(
                category="code_quality",
                name="Structured Error Handling",
                rule="Raise typed API errors, not generic exceptions — use "
                "`NotFoundAPIError`, `ValidationAPIError`, "
                "`PermissionAPIError` from `django_matt.core.errors`.",
                guidance=(
                    "Error hierarchy: `APIError` → "
                    "`NotFoundAPIError` (404), `ValidationAPIError` (400), "
                    "`PermissionAPIError` (403)."
                ),
                evidence=[self._short_path(p) for p in all_evidence[:5]],
            )
        ]
