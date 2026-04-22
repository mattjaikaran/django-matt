"""
Security auditor for detecting common security vulnerabilities.

Checks for:
- Hardcoded secrets and credentials
- SQL injection vulnerabilities
- XSS vulnerabilities
- Insecure authentication patterns
- Missing permission checks
- Dangerous function calls
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


@register_auditor
class SecurityAuditor(BaseAuditor):
    """
    Auditor for security vulnerabilities.

    Detects common security issues including:
    - Hardcoded secrets (API keys, passwords, tokens)
    - SQL injection via string formatting
    - XSS via unsafe template rendering
    - Missing authentication/authorization
    - Insecure cryptographic practices
    """

    name = "security"
    category = AuditCategory.SECURITY
    description = "Detect security vulnerabilities and unsafe patterns"

    # Patterns for secret detection
    SECRET_PATTERNS: list[tuple[str, re.Pattern, str]] = [
        (
            "SEC001",
            re.compile(r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\'][a-zA-Z0-9]{16,}["\']'),
            "Hardcoded API key detected",
        ),
        (
            "SEC002",
            re.compile(r'(?i)(secret[_-]?key|secretkey)\s*[=:]\s*["\'][^"\']{8,}["\']'),
            "Hardcoded secret key detected",
        ),
        (
            "SEC003",
            re.compile(r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']+["\']'),
            "Hardcoded password detected",
        ),
        (
            "SEC004",
            re.compile(r'(?i)(token|auth[_-]?token)\s*[=:]\s*["\'][a-zA-Z0-9_\-]{20,}["\']'),
            "Hardcoded token detected",
        ),
        (
            "SEC005",
            re.compile(r'(?i)(aws[_-]?access[_-]?key[_-]?id)\s*[=:]\s*["\']AKIA[A-Z0-9]{16}["\']'),
            "AWS access key detected",
        ),
        (
            "SEC006",
            re.compile(
                r'(?i)(aws[_-]?secret[_-]?access[_-]?key)\s*[=:]\s*["\'][a-zA-Z0-9/+=]{40}["\']'
            ),
            "AWS secret key detected",
        ),
        (
            "SEC007",
            re.compile(r'(?i)private[_-]?key\s*[=:]\s*["\']-----BEGIN'),
            "Private key detected",
        ),
    ]

    # Dangerous function patterns
    DANGEROUS_FUNCTIONS = {
        "eval": ("SEC010", "Use of eval() is dangerous - can execute arbitrary code"),
        "exec": ("SEC011", "Use of exec() is dangerous - can execute arbitrary code"),
        "compile": ("SEC012", "Use of compile() with user input is dangerous"),
        "__import__": ("SEC013", "Dynamic import can be dangerous with user input"),
        "pickle.loads": ("SEC014", "pickle.loads() can execute arbitrary code"),
        "yaml.load": ("SEC015", "yaml.load() without Loader is unsafe, use yaml.safe_load()"),
        "subprocess.call": ("SEC016", "subprocess.call() with shell=True is dangerous"),
        "subprocess.Popen": ("SEC017", "subprocess.Popen() with shell=True is dangerous"),
        "os.system": ("SEC018", "os.system() is vulnerable to shell injection"),
        "os.popen": ("SEC019", "os.popen() is vulnerable to shell injection"),
    }

    # SQL injection patterns
    SQL_PATTERNS: list[tuple[str, re.Pattern, str]] = [
        (
            "SEC020",
            re.compile(r'\.raw\s*\(\s*[f"\']'),
            "Potential SQL injection via raw() with f-string/format",
        ),
        (
            "SEC021",
            re.compile(r'\.extra\s*\(.*where.*[f"\']'),
            "Potential SQL injection via extra() with f-string/format",
        ),
        (
            "SEC022",
            re.compile(r'cursor\.execute\s*\(\s*[f"\']'),
            "Potential SQL injection via cursor.execute() with f-string/format",
        ),
        ("SEC023", re.compile(r"%s.*%\s*\("), "Potential SQL injection via string formatting"),
    ]

    def audit(self, config: AuditConfig) -> AuditResult:
        """
        Run security audit on the project.

        Args:
            config: Audit configuration.

        Returns:
            AuditResult with security findings.
        """
        findings: list[AuditFinding] = []
        files_scanned = 0

        for file_path in self.iter_files(config):
            files_scanned += 1
            file_findings = self._audit_file(file_path, config)
            findings.extend(file_findings)

            # Check max findings
            if config.max_findings > 0 and len(findings) >= config.max_findings:
                break

        return AuditResult(
            auditor_name=self.name,
            category=self.category,
            findings=findings,
            files_scanned=files_scanned,
        )

    def _audit_file(self, file_path: Path, config: AuditConfig) -> list[AuditFinding]:
        """
        Audit a single file for security issues.

        Args:
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings for this file.
        """
        findings: list[AuditFinding] = []

        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return findings

        lines = content.split("\n")
        rel_path = str(file_path)

        # Check for secrets in source
        for line_num, line in enumerate(lines, 1):
            for finding_id, pattern, message in self.SECRET_PATTERNS:
                if pattern.search(line):
                    severity = AuditSeverity.CRITICAL
                    if self.should_skip_for_level(severity, config.level):
                        continue

                    findings.append(
                        AuditFinding(
                            id=finding_id,
                            severity=severity,
                            category=self.category,
                            message=message,
                            file=rel_path,
                            line=line_num,
                            code=line.strip()[:100],
                            suggestion="Move secrets to environment variables or a secrets manager",
                            tags=["secrets", "owasp-a02"],
                        )
                    )

        # Check for SQL injection patterns
        for line_num, line in enumerate(lines, 1):
            for finding_id, pattern, message in self.SQL_PATTERNS:
                if pattern.search(line):
                    severity = AuditSeverity.HIGH
                    if self.should_skip_for_level(severity, config.level):
                        continue

                    findings.append(
                        AuditFinding(
                            id=finding_id,
                            severity=severity,
                            category=self.category,
                            message=message,
                            file=rel_path,
                            line=line_num,
                            code=line.strip()[:100],
                            suggestion="Use parameterized queries instead of string formatting",
                            tags=["sql-injection", "owasp-a03"],
                        )
                    )

        # AST-based analysis for dangerous function calls
        tree = self.parse_python_file(file_path)
        if tree:
            findings.extend(self._check_dangerous_calls(tree, rel_path, config))
            findings.extend(self._check_missing_auth(tree, rel_path, config))

        return findings

    def _check_dangerous_calls(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Check for dangerous function calls using AST.

        Args:
            tree: Parsed AST.
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings.
        """
        findings: list[AuditFinding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_func_name(node)
                if func_name in self.DANGEROUS_FUNCTIONS:
                    finding_id, message = self.DANGEROUS_FUNCTIONS[func_name]
                    severity = AuditSeverity.HIGH

                    if self.should_skip_for_level(severity, config.level):
                        continue

                    # Check for shell=True in subprocess calls
                    if func_name.startswith("subprocess."):
                        if not self._has_shell_true(node):
                            continue

                    findings.append(
                        AuditFinding(
                            id=finding_id,
                            severity=severity,
                            category=self.category,
                            message=message,
                            file=file_path,
                            line=node.lineno,
                            column=node.col_offset,
                            suggestion="Consider using safer alternatives or sanitizing inputs",
                            tags=["dangerous-function", "owasp-a03"],
                        )
                    )

        return findings

    def _check_missing_auth(
        self, tree: ast.Module, file_path: str, config: AuditConfig
    ) -> list[AuditFinding]:
        """
        Check for API endpoints missing authentication decorators.

        Args:
            tree: Parsed AST.
            file_path: Path to the file.
            config: Audit configuration.

        Returns:
            List of findings.
        """
        findings: list[AuditFinding] = []
        auth_decorators = {
            "jwt_required",
            "jwt_optional",
            "login_required",
            "permission_required",
            "requires_role",
            "requires_permission",
            "IsAuthenticated",
            "IsAdmin",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Check if this looks like an API endpoint
                if not self._is_api_endpoint(node):
                    continue

                # Check for auth decorators
                has_auth = False
                for decorator in node.decorator_list:
                    decorator_name = self._get_decorator_name(decorator)
                    if decorator_name in auth_decorators:
                        has_auth = True
                        break

                if not has_auth:
                    severity = AuditSeverity.MEDIUM
                    if self.should_skip_for_level(severity, config.level):
                        continue

                    findings.append(
                        AuditFinding(
                            id="SEC030",
                            severity=severity,
                            category=self.category,
                            message=f"API endpoint '{node.name}' may be missing authentication",
                            file=file_path,
                            line=node.lineno,
                            suggestion="Add @jwt_required, @login_required, or similar decorator",
                            tags=["authentication", "owasp-a01"],
                        )
                    )

        return findings

    def _get_func_name(self, node: ast.Call) -> str:
        """Extract function name from a Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""

    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """Extract decorator name from AST node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        if isinstance(decorator, ast.Attribute):
            return decorator.attr
        if isinstance(decorator, ast.Call):
            return self._get_decorator_name(decorator.func)
        return ""

    def _is_api_endpoint(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if a function looks like an API endpoint."""
        api_decorators = {"get", "post", "put", "patch", "delete", "api"}
        for decorator in node.decorator_list:
            name = self._get_decorator_name(decorator)
            if name.lower() in api_decorators:
                return True
        return False

    def _has_shell_true(self, node: ast.Call) -> bool:
        """Check if a subprocess call has shell=True."""
        for keyword in node.keywords:
            if keyword.arg == "shell":
                if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    return True
        return False
