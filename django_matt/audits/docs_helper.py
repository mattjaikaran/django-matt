"""
Documentation helper for generating docstrings and type hints.

Provides utilities for systematically improving code documentation
across the django-matt codebase.

Example:
    >>> from django_matt.audits.docs_helper import generate_docstring_stub
    >>> stub = generate_docstring_stub(my_function)
    >>> print(stub)
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, get_type_hints

if TYPE_CHECKING:
    pass


@dataclass
class DocstringStub:
    """
    Generated docstring stub for a function or class.

    Attributes:
        target_name: Name of the function/class.
        docstring: Generated docstring.
        file_path: Path to the source file.
        line_number: Line number where to insert.
        existing_docstring: Current docstring if any.
    """

    target_name: str
    docstring: str
    file_path: str | None = None
    line_number: int | None = None
    existing_docstring: str | None = None


def generate_docstring_stub(
    func: Callable[..., Any],
    style: str = "google",
) -> str:
    """
    Generate a docstring stub for a function.

    Args:
        func: The function to generate a docstring for.
        style: Docstring style ("google", "numpy", "sphinx").

    Returns:
        Generated docstring string.

    Example:
        >>> def my_func(name: str, count: int = 5) -> list[str]:
        ...     pass
        >>> print(generate_docstring_stub(my_func))
    """
    sig = inspect.signature(func)

    # Get existing type hints
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    # Build parameter descriptions
    params = []
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue

        param_type = hints.get(name, "Any")
        if hasattr(param_type, "__name__"):
            type_str = param_type.__name__
        else:
            type_str = str(param_type).replace("typing.", "")

        default = ""
        if param.default is not inspect.Parameter.empty:
            default = f" Defaults to {param.default!r}."

        params.append((name, type_str, default))

    # Get return type
    return_type = hints.get("return")
    if return_type:
        if hasattr(return_type, "__name__"):
            return_str = return_type.__name__
        else:
            return_str = str(return_type).replace("typing.", "")
    else:
        return_str = None

    # Generate docstring
    if style == "google":
        return _google_style(func.__name__, params, return_str)
    if style == "numpy":
        return _numpy_style(func.__name__, params, return_str)
    return _sphinx_style(func.__name__, params, return_str)


def _google_style(
    name: str,
    params: list[tuple[str, str, str]],
    return_type: str | None,
) -> str:
    """Generate Google-style docstring."""
    lines = [
        '"""',
        f"[Brief description of {name}].",
        "",
    ]

    if params:
        lines.append("Args:")
        for param_name, param_type, default in params:
            lines.append(f"    {param_name}: [Description].{default}")
        lines.append("")

    if return_type and return_type != "None":
        lines.append("Returns:")
        lines.append(f"    [Description of {return_type} return value].")
        lines.append("")

    # Add raises section placeholder
    lines.append("Raises:")
    lines.append("    [ExceptionType]: [When raised].")

    lines.append('"""')
    return "\n".join(lines)


def _numpy_style(
    name: str,
    params: list[tuple[str, str, str]],
    return_type: str | None,
) -> str:
    """Generate NumPy-style docstring."""
    lines = [
        '"""',
        f"[Brief description of {name}].",
        "",
    ]

    if params:
        lines.append("Parameters")
        lines.append("----------")
        for param_name, param_type, default in params:
            lines.append(f"{param_name} : {param_type}")
            lines.append(f"    [Description].{default}")
        lines.append("")

    if return_type and return_type != "None":
        lines.append("Returns")
        lines.append("-------")
        lines.append(f"{return_type}")
        lines.append("    [Description of return value].")

    lines.append('"""')
    return "\n".join(lines)


def _sphinx_style(
    name: str,
    params: list[tuple[str, str, str]],
    return_type: str | None,
) -> str:
    """Generate Sphinx-style docstring."""
    lines = [
        '"""',
        f"[Brief description of {name}].",
        "",
    ]

    for param_name, param_type, default in params:
        lines.append(f":param {param_name}: [Description].{default}")
        lines.append(f":type {param_name}: {param_type}")

    if return_type and return_type != "None":
        lines.append(":returns: [Description of return value].")
        lines.append(f":rtype: {return_type}")

    lines.append('"""')
    return "\n".join(lines)


def analyze_file_docs(file_path: Path | str) -> list[DocstringStub]:
    """
    Analyze a Python file and generate docstring stubs for undocumented items.

    Args:
        file_path: Path to the Python file.

    Returns:
        List of DocstringStub objects for items needing documentation.

    Example:
        >>> stubs = analyze_file_docs("my_module.py")
        >>> for stub in stubs:
        ...     print(f"{stub.target_name}: needs docstring")
    """
    file_path = Path(file_path)

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError) as e:
        return []

    stubs = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Skip private and dunder methods
            if node.name.startswith("_") and not node.name.startswith("__"):
                continue

            existing = ast.get_docstring(node)
            if not existing:
                stub = _generate_ast_docstring(node, str(file_path))
                stubs.append(stub)

        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue

            existing = ast.get_docstring(node)
            if not existing:
                stub = DocstringStub(
                    target_name=node.name,
                    docstring=f'"""\n[Description of {node.name} class].\n\nAttributes:\n    [attr]: [Description].\n"""',
                    file_path=str(file_path),
                    line_number=node.lineno,
                )
                stubs.append(stub)

    return stubs


def _generate_ast_docstring(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    file_path: str,
) -> DocstringStub:
    """Generate docstring stub from AST node."""
    params = []

    for arg in node.args.args:
        if arg.arg in ("self", "cls"):
            continue

        # Get type annotation if present
        if arg.annotation:
            try:
                type_str = ast.unparse(arg.annotation)
            except Exception:
                type_str = "Any"
        else:
            type_str = "Any"

        params.append((arg.arg, type_str, ""))

    # Get return type
    return_type = None
    if node.returns:
        try:
            return_type = ast.unparse(node.returns)
        except Exception:
            pass

    docstring = _google_style(node.name, params, return_type)

    return DocstringStub(
        target_name=node.name,
        docstring=docstring,
        file_path=file_path,
        line_number=node.lineno,
    )


def generate_type_hints_stub(
    file_path: Path | str,
) -> str:
    """
    Generate type hint suggestions for a Python file.

    Args:
        file_path: Path to the Python file.

    Returns:
        String with suggested type hints.

    Example:
        >>> hints = generate_type_hints_stub("my_module.py")
        >>> print(hints)
    """
    file_path = Path(file_path)

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return ""

    suggestions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Check for missing return type
            if node.returns is None:
                suggestions.append(
                    f"Line {node.lineno}: {node.name}() - add return type annotation"
                )

            # Check for missing parameter types
            for arg in node.args.args:
                if arg.arg in ("self", "cls"):
                    continue
                if arg.annotation is None:
                    suggestions.append(
                        f"Line {node.lineno}: {node.name}({arg.arg}) - add type annotation"
                    )

    return "\n".join(suggestions)


def batch_generate_stubs(
    directory: Path | str,
    output_file: Path | str | None = None,
    style: str = "google",
) -> dict[str, list[DocstringStub]]:
    """
    Generate docstring stubs for all Python files in a directory.

    Args:
        directory: Directory to scan.
        output_file: Optional file to write stubs to.
        style: Docstring style to use.

    Returns:
        Dict mapping file paths to their docstring stubs.

    Example:
        >>> stubs = batch_generate_stubs("src/", output_file="DOCS_TODO.md")
        >>> print(f"Found {sum(len(s) for s in stubs.values())} items needing docs")
    """
    directory = Path(directory)
    all_stubs: dict[str, list[DocstringStub]] = {}

    for py_file in directory.rglob("*.py"):
        # Skip common directories
        if any(
            part in py_file.parts for part in ("__pycache__", "migrations", ".git", "venv", ".venv")
        ):
            continue

        stubs = analyze_file_docs(py_file)
        if stubs:
            all_stubs[str(py_file)] = stubs

    # Write to file if requested
    if output_file:
        output_path = Path(output_file)
        lines = ["# Documentation TODO", "", "Generated stubs for undocumented items.", ""]

        for file_path, stubs in sorted(all_stubs.items()):
            lines.append(f"## {file_path}")
            lines.append("")
            for stub in stubs:
                lines.append(f"### {stub.target_name} (line {stub.line_number})")
                lines.append("")
                lines.append("```python")
                lines.append(stub.docstring)
                lines.append("```")
                lines.append("")

        output_path.write_text("\n".join(lines))

    return all_stubs


def calculate_doc_coverage(directory: Path | str) -> dict[str, Any]:
    """
    Calculate documentation coverage for a directory.

    Args:
        directory: Directory to analyze.

    Returns:
        Dict with coverage statistics.

    Example:
        >>> stats = calculate_doc_coverage("django_matt/")
        >>> print(f"Coverage: {stats['coverage_pct']:.1f}%")
    """
    directory = Path(directory)

    total_items = 0
    documented_items = 0
    total_params = 0
    typed_params = 0
    total_returns = 0
    typed_returns = 0

    for py_file in directory.rglob("*.py"):
        if any(
            part in py_file.parts for part in ("__pycache__", "migrations", ".git", "venv", ".venv")
        ):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                # Skip private items
                if node.name.startswith("_") and not node.name.startswith("__"):
                    continue

                total_items += 1
                if ast.get_docstring(node):
                    documented_items += 1

            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Count return type annotations
                total_returns += 1
                if node.returns is not None:
                    typed_returns += 1

                # Count parameter type annotations
                for arg in node.args.args:
                    if arg.arg in ("self", "cls"):
                        continue
                    total_params += 1
                    if arg.annotation is not None:
                        typed_params += 1

    coverage_pct = (documented_items / total_items * 100) if total_items > 0 else 100.0
    param_coverage = (typed_params / total_params * 100) if total_params > 0 else 100.0
    return_coverage = (typed_returns / total_returns * 100) if total_returns > 0 else 100.0

    return {
        "total_items": total_items,
        "documented_items": documented_items,
        "coverage_pct": coverage_pct,
        "total_params": total_params,
        "typed_params": typed_params,
        "param_coverage_pct": param_coverage,
        "total_returns": total_returns,
        "typed_returns": typed_returns,
        "return_coverage_pct": return_coverage,
    }
