"""AST-based security analyzer.

Detects hardcoded secrets, SQL injection risks, unsafe eval/exec, insecure
deserialization, open redirects, missing CSRF protection, debug mode, and
weak cryptography usage.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from django_matt.review.analyzers.base import ASTVisitorAnalyzer
from django_matt.review.findings import Category, Finding, Location, Severity


class SecurityAnalyzer(ASTVisitorAnalyzer):
    """Analyzer that detects common security vulnerabilities via AST + regex."""

    name = "security"
    description = "Checks for secrets, injection, unsafe eval, deserialization, CSRF, debug mode, weak crypto"

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        self._findings: list[Finding] = []
        self._file_path = file_path
        self._source = source
        self._source_lines = source.splitlines()
        self._current_class: str | None = None
        self._current_function: str | None = None

        self._compiled_secret_patterns = [
            re.compile(p) for p in self.config.security.secret_patterns
        ]
        self._compiled_sql_patterns = [
            re.compile(p) for p in self.config.security.sql_injection_patterns
        ]

        self._check_hardcoded_secrets()
        self._check_debug_mode()
        self.visit(tree)
        return self._findings

    # ── Line-based checks (regex on source) ──────────────────────────

    def _check_hardcoded_secrets(self) -> None:
        """SEC001: Scan source lines for hardcoded secrets."""
        for lineno, line in enumerate(self._source_lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern in self._compiled_secret_patterns:
                if pattern.search(line):
                    self._add_finding(Finding(
                        rule_id="SEC001",
                        message=f"Hardcoded secret detected: {stripped[:80]}",
                        severity=Severity.CRITICAL,
                        category=Category.SECURITY,
                        location=Location(
                            file=str(self._file_path),
                            line=lineno,
                        ),
                        suggestion="Use environment variables or a secrets manager instead of hardcoding credentials",
                    ))
                    break

    def _check_debug_mode(self) -> None:
        """SEC007: Detect DEBUG = True in settings-like files."""
        filename = self._file_path.name
        if "setting" not in filename.lower() and "config" not in filename.lower():
            return
        debug_pattern = re.compile(r"^\s*DEBUG\s*=\s*True\s*$")
        for lineno, line in enumerate(self._source_lines, start=1):
            if debug_pattern.match(line):
                self._add_finding(Finding(
                    rule_id="SEC007",
                    message="DEBUG = True hardcoded in settings file",
                    severity=Severity.ERROR,
                    category=Category.SECURITY,
                    location=Location(
                        file=str(self._file_path),
                        line=lineno,
                    ),
                    suggestion="Use an environment variable: DEBUG = os.environ.get('DEBUG', 'False') == 'True'",
                ))

    # ── AST visitor methods ──────────────────────────────────────────

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        prev = self._current_class
        self._current_class = node.name
        self._check_csrf_exempt_class(node)
        self.generic_visit(node)
        self._current_class = prev

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        prev = self._current_function
        self._current_function = node.name
        self._check_csrf_exempt_function(node)
        self.generic_visit(node)
        self._current_function = prev

    def visit_Call(self, node: ast.Call) -> None:
        self._check_eval_exec(node)
        self._check_unsafe_deserialization(node)
        self._check_sql_injection(node)
        self._check_open_redirect(node)
        self._check_weak_crypto(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._check_weak_crypto_assign(node)
        self.generic_visit(node)

    # ── SEC002: SQL injection ────────────────────────────────────────

    def _check_sql_injection(self, node: ast.Call) -> None:
        func_name = self._get_call_name(node)
        if func_name not in ("raw", "extra", "execute"):
            return

        if not node.args:
            return

        first_arg = node.args[0]
        if self._is_dynamic_string(first_arg):
            self._add_finding(Finding(
                rule_id="SEC002",
                message=f"SQL injection risk: dynamic string passed to .{func_name}()",
                severity=Severity.CRITICAL,
                category=Category.SECURITY,
                location=Location(
                    file=str(self._file_path),
                    line=node.lineno,
                    function=self._current_function,
                    class_name=self._current_class,
                ),
                suggestion="Use parameterized queries with placeholders instead of string interpolation",
            ))

    def _is_dynamic_string(self, node: ast.expr) -> bool:
        """Check if a node is an f-string or .format() call."""
        if isinstance(node, ast.JoinedStr):
            return True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
                return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            return True
        return False

    # ── SEC003: eval/exec/compile ────────────────────────────────────

    def _check_eval_exec(self, node: ast.Call) -> None:
        func_name = self._get_simple_name(node.func)
        if func_name not in ("eval", "exec", "compile"):
            return

        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            return

        self._add_finding(Finding(
            rule_id="SEC003",
            message=f"Unsafe {func_name}() call with non-literal argument",
            severity=Severity.ERROR,
            category=Category.SECURITY,
            location=Location(
                file=str(self._file_path),
                line=node.lineno,
                function=self._current_function,
                class_name=self._current_class,
            ),
            suggestion="Use ast.literal_eval() or a safer alternative instead of "
                       f"{func_name}()",
        ))

    # ── SEC004: Unsafe deserialization ───────────────────────────────

    _UNSAFE_DESER_FUNCS: frozenset[str] = frozenset({
        "pickle.loads", "pickle.load",
        "marshal.loads", "marshal.load",
        "shelve.open",
    })

    def _check_unsafe_deserialization(self, node: ast.Call) -> None:
        full_name = self._get_dotted_name(node.func)

        if full_name in self._UNSAFE_DESER_FUNCS:
            self._add_finding(Finding(
                rule_id="SEC004",
                message=f"Unsafe deserialization via {full_name}()",
                severity=Severity.ERROR,
                category=Category.SECURITY,
                location=Location(
                    file=str(self._file_path),
                    line=node.lineno,
                    function=self._current_function,
                    class_name=self._current_class,
                ),
                suggestion="Use safe deserialization (json, pydantic) instead of "
                           f"{full_name}()",
            ))
            return

        if full_name == "yaml.load":
            has_safe_loader = self._yaml_has_safe_loader(node)
            if not has_safe_loader:
                self._add_finding(Finding(
                    rule_id="SEC004",
                    message="yaml.load() called without Loader=SafeLoader",
                    severity=Severity.ERROR,
                    category=Category.SECURITY,
                    location=Location(
                        file=str(self._file_path),
                        line=node.lineno,
                        function=self._current_function,
                        class_name=self._current_class,
                    ),
                    suggestion="Use yaml.safe_load() or pass Loader=yaml.SafeLoader",
                ))

    def _yaml_has_safe_loader(self, node: ast.Call) -> bool:
        """Check if yaml.load() call has a safe Loader keyword argument."""
        for kw in node.keywords:
            if kw.arg == "Loader":
                if isinstance(kw.value, ast.Attribute) and kw.value.attr in (
                    "SafeLoader", "CSafeLoader", "FullLoader",
                ):
                    return True
                if isinstance(kw.value, ast.Name) and kw.value.id in (
                    "SafeLoader", "CSafeLoader", "FullLoader",
                ):
                    return True
        return False

    # ── SEC005: Open redirect ────────────────────────────────────────

    _REDIRECT_FUNCS: frozenset[str] = frozenset({
        "redirect", "HttpResponseRedirect", "HttpResponsePermanentRedirect",
    })

    def _check_open_redirect(self, node: ast.Call) -> None:
        func_name = self._get_simple_name(node.func)
        if func_name is None:
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
        if func_name not in self._REDIRECT_FUNCS:
            return

        if not node.args:
            return

        first_arg = node.args[0]
        if self._references_request(first_arg):
            self._add_finding(Finding(
                rule_id="SEC005",
                message=f"Open redirect risk: user-controlled input passed to {func_name}()",
                severity=Severity.WARNING,
                category=Category.SECURITY,
                location=Location(
                    file=str(self._file_path),
                    line=node.lineno,
                    function=self._current_function,
                    class_name=self._current_class,
                ),
                suggestion="Validate the redirect URL against an allowlist of trusted domains",
            ))

    def _references_request(self, node: ast.expr) -> bool:
        """Check if an expression references request data (GET, POST, etc.)."""
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute) and child.attr in (
                "GET", "POST", "get", "data", "query_params",
            ):
                if isinstance(child.value, ast.Name) and child.value.id == "request":
                    return True
            if isinstance(child, ast.Subscript):
                if isinstance(child.value, ast.Attribute):
                    if isinstance(child.value.value, ast.Name) and child.value.value.id == "request":
                        return True
        return False

    # ── SEC006: Missing CSRF protection ──────────────────────────────

    def _check_csrf_exempt_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            name = self._get_decorator_name(decorator)
            if name == "csrf_exempt":
                self._add_finding(Finding(
                    rule_id="SEC006",
                    message=f"@csrf_exempt on function '{node.name}' disables CSRF protection",
                    severity=Severity.WARNING,
                    category=Category.SECURITY,
                    location=Location(
                        file=str(self._file_path),
                        line=node.lineno,
                        function=node.name,
                        class_name=self._current_class,
                    ),
                    suggestion="Remove @csrf_exempt or use API token authentication instead of session auth",
                ))

    def _check_csrf_exempt_class(self, node: ast.ClassDef) -> None:
        for decorator in node.decorator_list:
            name = self._get_decorator_name(decorator)
            if name == "csrf_exempt":
                self._add_finding(Finding(
                    rule_id="SEC006",
                    message=f"@csrf_exempt on class '{node.name}' disables CSRF protection",
                    severity=Severity.WARNING,
                    category=Category.SECURITY,
                    location=Location(
                        file=str(self._file_path),
                        line=node.lineno,
                        class_name=node.name,
                    ),
                    suggestion="Remove @csrf_exempt or use API token authentication instead of session auth",
                ))

    # ── SEC008: Weak cryptography ────────────────────────────────────

    _WEAK_HASH_FUNCS: frozenset[str] = frozenset({
        "md5", "sha1",
    })

    _WEAK_HASH_DOTTED: frozenset[str] = frozenset({
        "hashlib.md5", "hashlib.sha1",
        "Crypto.Cipher.DES.new", "Cryptodome.Cipher.DES.new",
    })

    def _check_weak_crypto(self, node: ast.Call) -> None:
        dotted = self._get_dotted_name(node.func)
        simple = self._get_simple_name(node.func)

        is_weak = (
            dotted in self._WEAK_HASH_DOTTED
            or (simple in self._WEAK_HASH_FUNCS and dotted != simple)
        )

        if not is_weak:
            return

        self._add_finding(Finding(
            rule_id="SEC008",
            message=f"Weak cryptography: {dotted or simple}() is not considered secure",
            severity=Severity.WARNING,
            category=Category.SECURITY,
            location=Location(
                file=str(self._file_path),
                line=node.lineno,
                function=self._current_function,
                class_name=self._current_class,
            ),
            suggestion="Use SHA-256 or stronger (hashlib.sha256) for security-sensitive hashing",
        ))

    def _check_weak_crypto_assign(self, node: ast.Assign) -> None:
        """Detect DES or weak key sizes in variable assignments."""
        source_line = self._get_source_line(node.lineno)
        if re.search(r"\bDES\b", source_line) and "import" not in source_line:
            self._add_finding(Finding(
                rule_id="SEC008",
                message="Weak cryptography: DES cipher detected",
                severity=Severity.WARNING,
                category=Category.SECURITY,
                location=Location(
                    file=str(self._file_path),
                    line=node.lineno,
                    function=self._current_function,
                    class_name=self._current_class,
                ),
                suggestion="Use AES-256 or ChaCha20 instead of DES",
            ))

    # ── Helpers ──────────────────────────────────────────────────────

    def _get_call_name(self, node: ast.Call) -> str | None:
        """Get the method/function name from a Call node."""
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        if isinstance(node.func, ast.Name):
            return node.func.id
        return None

    def _get_simple_name(self, node: ast.expr) -> str | None:
        """Get a simple name from a Name node."""
        if isinstance(node, ast.Name):
            return node.id
        return None

    def _get_dotted_name(self, node: ast.expr) -> str | None:
        """Get a dotted name like 'module.func' from an Attribute chain."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._get_dotted_name(node.value)
            if parent:
                return f"{parent}.{node.attr}"
            return node.attr
        return None

    def _get_decorator_name(self, node: ast.expr) -> str | None:
        """Extract the name of a decorator (handles @name and @module.name)."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return None
