# file-length-max: 550
"""
SOLID principles analyzer — AST-based detection of SRP, OCP, LSP, ISP, DIP violations.
"""

from __future__ import annotations

import ast

from django_matt.review.analyzers.base import ASTVisitorAnalyzer
from django_matt.review.findings import Category, Finding, Location, Severity

# Heuristic method-name prefixes for responsibility classification
_IO_PATTERNS = frozenset(
    {
        "save",
        "write",
        "send",
        "fetch",
        "read",
        "load",
        "download",
        "upload",
        "open",
        "close",
        "connect",
        "disconnect",
        "publish",
        "consume",
        "emit",
    }
)
_COMPUTE_PATTERNS = frozenset(
    {
        "calculate",
        "compute",
        "process",
        "transform",
        "parse",
        "evaluate",
        "analyze",
        "aggregate",
        "reduce",
        "merge",
        "solve",
        "derive",
    }
)
_SERIALIZE_PATTERNS = frozenset(
    {
        "serialize",
        "deserialize",
        "to_dict",
        "to_json",
        "to_xml",
        "to_csv",
        "from_dict",
        "from_json",
        "from_xml",
        "as_dict",
        "as_json",
        "encode",
        "decode",
        "marshal",
        "unmarshal",
        "to_yaml",
        "from_yaml",
    }
)

# Base classes that indicate an abstract interface
_ABSTRACT_BASES = frozenset({"ABC", "Protocol"})


def _is_public_method(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if the method is public (not dunder, not private)."""
    return not node.name.startswith("_")


def _method_matches_patterns(name: str, patterns: frozenset[str]) -> bool:
    """Check if a method name starts with or exactly matches any pattern."""
    name_lower = name.lower()
    return any(name_lower == p or name_lower.startswith(p + "_") for p in patterns)


def _get_class_name(node: ast.ClassDef) -> str:
    return node.name


def _has_abstract_base(node: ast.ClassDef) -> bool:
    """Check if a class inherits from ABC or Protocol."""
    for base in node.bases:
        name = _base_name(base)
        if name in _ABSTRACT_BASES:
            return True
    return False


def _base_name(node: ast.expr) -> str | None:
    """Extract a simple name from a base class expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_abstract_method(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a method is decorated with @abstractmethod."""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "abstractmethod":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "abstractmethod":
            return True
    return False


def _count_isinstance_calls(node: ast.AST) -> int:
    """Count isinstance() calls in a subtree."""
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name) and func.id == "isinstance":
                count += 1
    return count


def _count_type_comparisons(node: ast.AST) -> int:
    """Count `obj.type == "..."` style comparisons in a subtree."""
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Compare) and len(child.ops) == 1:
            if isinstance(child.ops[0], (ast.Eq, ast.Is)):
                left = child.left
                if isinstance(left, ast.Attribute) and left.attr in ("type", "kind", "tag"):
                    count += 1
    return count


def _is_concrete_annotation(ann: ast.expr | None) -> bool:
    """Heuristic: annotation is a concrete class if it's a Name starting uppercase
    and is NOT Protocol/ABC/a common abstract type alias."""
    if ann is None:
        return False
    if isinstance(ann, ast.Constant):
        # String annotation like "SomeClass"
        if isinstance(ann.value, str):
            val = ann.value
            return val[:1].isupper() and val not in _ABSTRACT_BASES and "Protocol" not in val
        return False
    if isinstance(ann, ast.Name):
        return (
            ann.id[:1].isupper()
            and ann.id not in _ABSTRACT_BASES
            and "Protocol" not in ann.id
            and ann.id not in {"Optional", "Union", "Any", "Type", "Callable"}
        )
    if isinstance(ann, ast.Attribute):
        return ann.attr[:1].isupper() and ann.attr not in _ABSTRACT_BASES
    # Subscript like Optional[X], list[X] — not concrete
    if isinstance(ann, ast.Subscript):
        return False
    # BinOp for X | Y union syntax — not concrete
    if isinstance(ann, ast.BinOp):
        return False
    return False


class SolidAnalyzer(ASTVisitorAnalyzer):
    """Detect SOLID principle violations via AST analysis."""

    name = "solid"
    description = "Checks for SOLID principle violations (SRP, OCP, ISP, DIP)"

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        methods = self._collect_methods(node)
        public_methods = [m for m in methods if _is_public_method(m)]

        self._check_srp_method_count(node, public_methods)
        self._check_srp_mixed_responsibilities(node, methods)
        self._check_ocp_in_methods(node, methods)
        self._check_isp_fat_interface(node, methods)
        self._check_dip_concrete_deps(node, methods)
        self._check_god_class(node, public_methods)

        # Recurse into nested classes / inner functions
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_ocp_function(node, enclosing_class=None)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_ocp_function(node, enclosing_class=None)
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # SOL001 — SRP: Too many methods
    # ------------------------------------------------------------------

    def _check_srp_method_count(
        self,
        node: ast.ClassDef,
        public_methods: list[ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> None:
        threshold = self.config.solid.max_class_methods
        count = len(public_methods)
        if count > threshold:
            self._add_finding(
                Finding(
                    rule_id="SOL001",
                    message=(
                        f"Class '{node.name}' has {count} public methods "
                        f"(threshold: {threshold}), suggesting too many responsibilities"
                    ),
                    severity=Severity.WARNING,
                    category=Category.SOLID,
                    location=Location(
                        file=str(self._file_path),
                        line=node.lineno,
                        class_name=node.name,
                    ),
                    suggestion=(
                        "Split into smaller, focused classes — each with a single responsibility"
                    ),
                    metadata={"public_method_count": count, "threshold": threshold},
                )
            )

    # ------------------------------------------------------------------
    # SOL002 — SRP: Mixed responsibilities
    # ------------------------------------------------------------------

    def _check_srp_mixed_responsibilities(
        self,
        node: ast.ClassDef,
        methods: list[ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> None:
        has_io = False
        has_compute = False
        has_serialize = False

        for method in methods:
            name = method.name
            if _method_matches_patterns(name, _IO_PATTERNS):
                has_io = True
            if _method_matches_patterns(name, _COMPUTE_PATTERNS):
                has_compute = True
            if _method_matches_patterns(name, _SERIALIZE_PATTERNS):
                has_serialize = True

        categories_found = sum([has_io, has_compute, has_serialize])
        if categories_found >= 2:
            labels = []
            if has_io:
                labels.append("I/O")
            if has_compute:
                labels.append("computation")
            if has_serialize:
                labels.append("serialization")

            self._add_finding(
                Finding(
                    rule_id="SOL002",
                    message=(f"Class '{node.name}' mixes {' + '.join(labels)} responsibilities"),
                    severity=Severity.WARNING,
                    category=Category.SOLID,
                    location=Location(
                        file=str(self._file_path),
                        line=node.lineno,
                        class_name=node.name,
                    ),
                    suggestion=(
                        "Separate into dedicated classes: one for I/O, one for "
                        "business logic, one for serialization"
                    ),
                    metadata={"responsibilities": labels},
                )
            )

    # ------------------------------------------------------------------
    # SOL003 — OCP: Excessive type checking
    # ------------------------------------------------------------------

    def _check_ocp_in_methods(
        self,
        node: ast.ClassDef,
        methods: list[ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> None:
        for method in methods:
            self._check_ocp_function(method, enclosing_class=node.name)

    def _check_ocp_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        enclosing_class: str | None,
    ) -> None:
        threshold = self.config.solid.max_type_checks
        isinstance_count = _count_isinstance_calls(node)
        type_cmp_count = _count_type_comparisons(node)
        total = isinstance_count + type_cmp_count

        if total > threshold:
            self._add_finding(
                Finding(
                    rule_id="SOL003",
                    message=(
                        f"Function '{node.name}' has {total} type checks "
                        f"(threshold: {threshold}), consider a visitor or strategy pattern"
                    ),
                    severity=Severity.HINT,
                    category=Category.SOLID,
                    location=Location(
                        file=str(self._file_path),
                        line=node.lineno,
                        function=node.name,
                        class_name=enclosing_class,
                    ),
                    suggestion=(
                        "Replace branching on type with polymorphism "
                        "(visitor pattern, strategy pattern, or dispatch dict)"
                    ),
                    metadata={
                        "isinstance_calls": isinstance_count,
                        "type_comparisons": type_cmp_count,
                        "total": total,
                        "threshold": threshold,
                    },
                )
            )

    # ------------------------------------------------------------------
    # SOL004 — ISP: Fat interface
    # ------------------------------------------------------------------

    def _check_isp_fat_interface(
        self,
        node: ast.ClassDef,
        methods: list[ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> None:
        if not _has_abstract_base(node):
            return

        abstract_methods = [m for m in methods if _is_abstract_method(m)]
        threshold = self.config.solid.max_interface_methods
        count = len(abstract_methods)

        if count > threshold:
            self._add_finding(
                Finding(
                    rule_id="SOL004",
                    message=(
                        f"Interface '{node.name}' has {count} abstract methods "
                        f"(threshold: {threshold}), violating Interface Segregation"
                    ),
                    severity=Severity.WARNING,
                    category=Category.SOLID,
                    location=Location(
                        file=str(self._file_path),
                        line=node.lineno,
                        class_name=node.name,
                    ),
                    suggestion=(
                        "Split into smaller, role-specific interfaces that clients "
                        "can implement independently"
                    ),
                    metadata={
                        "abstract_method_count": count,
                        "threshold": threshold,
                        "method_names": [m.name for m in abstract_methods],
                    },
                )
            )

    # ------------------------------------------------------------------
    # SOL005 — DIP: Too many concrete dependencies
    # ------------------------------------------------------------------

    def _check_dip_concrete_deps(
        self,
        node: ast.ClassDef,
        methods: list[ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> None:
        init_methods = [m for m in methods if m.name == "__init__"]
        if not init_methods:
            return

        init = init_methods[0]
        threshold = self.config.solid.max_dependencies
        concrete_params: list[str] = []

        for arg in init.args.args:
            if arg.arg == "self":
                continue
            if _is_concrete_annotation(arg.annotation):
                concrete_params.append(arg.arg)

        count = len(concrete_params)
        if count > threshold:
            self._add_finding(
                Finding(
                    rule_id="SOL005",
                    message=(
                        f"Class '{node.name}.__init__' has {count} concrete dependencies "
                        f"(threshold: {threshold}), violating Dependency Inversion"
                    ),
                    severity=Severity.HINT,
                    category=Category.SOLID,
                    location=Location(
                        file=str(self._file_path),
                        line=init.lineno,
                        function="__init__",
                        class_name=node.name,
                    ),
                    suggestion=(
                        "Depend on abstractions (Protocol/ABC) instead of concrete classes. "
                        "Use dependency injection to provide implementations"
                    ),
                    metadata={
                        "concrete_dependencies": concrete_params,
                        "count": count,
                        "threshold": threshold,
                    },
                )
            )

    # ------------------------------------------------------------------
    # SOL006 — God class
    # ------------------------------------------------------------------

    def _check_god_class(
        self,
        node: ast.ClassDef,
        public_methods: list[ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> None:
        method_threshold = self.config.solid.max_class_methods * 2
        line_threshold = self.config.complexity.max_class_lines
        method_count = len(public_methods)

        # Calculate class line span
        end_line = getattr(node, "end_lineno", None)
        if end_line is not None:
            class_lines = end_line - node.lineno + 1
        else:
            # Fallback: estimate from last child node
            class_lines = self._estimate_class_lines(node)

        if method_count > method_threshold and class_lines > line_threshold:
            self._add_finding(
                Finding(
                    rule_id="SOL006",
                    message=(
                        f"God class '{node.name}': {method_count} public methods "
                        f"and {class_lines} lines — far too many responsibilities"
                    ),
                    severity=Severity.ERROR,
                    category=Category.SOLID,
                    location=Location(
                        file=str(self._file_path),
                        line=node.lineno,
                        class_name=node.name,
                    ),
                    suggestion=(
                        "Decompose into smaller, cohesive classes using composition. "
                        "Extract service objects, value objects, and strategy patterns"
                    ),
                    metadata={
                        "public_method_count": method_count,
                        "class_lines": class_lines,
                        "method_threshold": method_threshold,
                        "line_threshold": line_threshold,
                    },
                )
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_methods(
        node: ast.ClassDef,
    ) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        """Collect direct method definitions (not nested class methods)."""
        return [
            child
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

    @staticmethod
    def _estimate_class_lines(node: ast.ClassDef) -> int:
        """Estimate class line count from child nodes when end_lineno is unavailable."""
        max_line = node.lineno
        for child in ast.walk(node):
            lineno = getattr(child, "lineno", 0)
            max_line = max(max_line, lineno)
        return max_line - node.lineno + 1
