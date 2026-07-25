"""
Common AST transformation patterns shared across codemods.

Provides reusable utilities for import rewriting, decorator transformation,
class base swapping, method signature changes, and return value manipulation.
"""

from __future__ import annotations

import ast
import copy


def rewrite_imports(
    tree: ast.Module,
    old_module: str,
    new_module: str,
    name_map: dict[str, str] | None = None,
) -> list[str]:
    """Rewrite import statements from old_module to new_module.

    Args:
        tree: AST module to mutate in place.
        old_module: Source module path (e.g. "rest_framework.serializers").
        new_module: Target module path (e.g. "django_matt.core.schema").
        name_map: Optional rename mapping (e.g. {"ModelSerializer": "ModelSchema"}).

    Returns:
        List of human-readable change descriptions.
    """
    changes: list[str] = []
    name_map = name_map or {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == old_module:
            node.module = new_module
            for alias in node.names:
                original = alias.name
                if original in name_map:
                    new_name = name_map[original]
                    if alias.asname is None or alias.asname == original:
                        alias.asname = None
                    alias.name = new_name
                    changes.append(f"Renamed import {original} -> {new_name}")
                else:
                    changes.append(f"Moved import {original} from {old_module} to {new_module}")

    return changes


def add_import(tree: ast.Module, module: str, names: list[str]) -> None:
    """Add an import statement if not already present."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            existing = {a.name for a in node.names}
            for name in names:
                if name not in existing:
                    node.names.append(ast.alias(name=name, asname=None))
            return

    # Insert after existing imports
    insert_idx = 0
    for i, node in enumerate(tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            insert_idx = i + 1

    new_import = ast.ImportFrom(
        module=module,
        names=[ast.alias(name=n, asname=None) for n in names],
        level=0,
    )
    tree.body.insert(insert_idx, new_import)


def remove_import(tree: ast.Module, module: str, names: list[str] | None = None) -> list[str]:
    """Remove import(s) from a module. If names is None, remove the entire import."""
    changes: list[str] = []
    to_remove: list[int] = []

    for i, node in enumerate(tree.body):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            if names is None:
                to_remove.append(i)
                changes.append(f"Removed import from {module}")
            else:
                node.names = [a for a in node.names if a.name not in names]
                changes.append(f"Removed {', '.join(names)} from {module}")
                if not node.names:
                    to_remove.append(i)

    for idx in reversed(to_remove):
        tree.body.pop(idx)

    return changes


def swap_base_classes(
    node: ast.ClassDef,
    old_base: str,
    new_base: str,
) -> bool:
    """Swap a base class name on a ClassDef. Returns True if swapped."""
    for i, base in enumerate(node.bases):
        base_name = _get_name(base)
        if base_name == old_base:
            node.bases[i] = ast.Name(id=new_base, ctx=ast.Load())
            return True
    return False


def has_base_class(node: ast.ClassDef, name: str) -> bool:
    """Check if a ClassDef has a specific base class (by simple name or attr)."""
    for base in node.bases:
        if _get_name(base) == name:
            return True
    return False


def rename_class(node: ast.ClassDef, old_suffix: str, new_suffix: str) -> str | None:
    """Rename a class by replacing a suffix. Returns new name or None."""
    if old_suffix in node.name:
        old_name = node.name
        node.name = node.name.replace(old_suffix, new_suffix)
        return old_name
    return None


def transform_decorators(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    old_obj: str,
    new_obj: str,
    method_map: dict[str, str] | None = None,
) -> list[str]:
    """Transform decorator calls like @old_obj.get() -> @new_obj.get().

    Args:
        node: Function node to mutate.
        old_obj: Old decorator object name (e.g. "router").
        new_obj: New decorator object name (e.g. "api").
        method_map: Optional method rename mapping.

    Returns:
        List of change descriptions.
    """
    changes: list[str] = []
    method_map = method_map or {}

    for dec in node.decorator_list:
        call_node = dec if isinstance(dec, ast.Call) else None
        attr_node = None

        if call_node and isinstance(call_node.func, ast.Attribute):
            attr_node = call_node.func
        elif isinstance(dec, ast.Attribute):
            attr_node = dec

        if attr_node is None:
            continue

        obj_name = _get_name(attr_node.value)
        if obj_name == old_obj:
            attr_node.value = ast.Name(id=new_obj, ctx=ast.Load())
            old_method = attr_node.attr
            if old_method in method_map:
                attr_node.attr = method_map[old_method]
                changes.append(
                    f"Transformed @{old_obj}.{old_method}() -> @{new_obj}.{method_map[old_method]}()"
                )
            else:
                changes.append(
                    f"Transformed @{old_obj}.{old_method}() -> @{new_obj}.{old_method}()"
                )

    return changes


def wrap_in_class(
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef],
    class_name: str,
    base_class: str,
    prefix: str = "",
    tags: list[str] | None = None,
) -> ast.ClassDef:
    """Wrap standalone functions into a controller class."""
    body: list[ast.stmt] = []

    if prefix:
        body.append(
            ast.Assign(
                targets=[ast.Name(id="prefix", ctx=ast.Store())],
                value=ast.Constant(value=prefix),
                lineno=0,
            )
        )

    if tags:
        body.append(
            ast.Assign(
                targets=[ast.Name(id="tags", ctx=ast.Store())],
                value=ast.List(elts=[ast.Constant(value=t) for t in tags], ctx=ast.Load()),
                lineno=0,
            )
        )

    for func in functions:
        # Add 'self' as first argument if not present
        func_copy = copy.deepcopy(func)
        args = func_copy.args
        if not args.args or args.args[0].arg != "self":
            self_arg = ast.arg(arg="self", annotation=None)
            args.args.insert(0, self_arg)
        body.append(func_copy)

    class_def = ast.ClassDef(
        name=class_name,
        bases=[ast.Name(id=base_class, ctx=ast.Load())],
        keywords=[],
        body=body or [ast.Pass()],
        decorator_list=[],
    )
    return class_def


def remove_response_wrapper(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Replace `return Response(data)` with `return data`.

    Handles both DRF Response() and FastAPI JSONResponse().
    """
    changes: list[str] = []

    class ResponseUnwrapper(ast.NodeTransformer):
        def visit_Return(self, ret: ast.Return) -> ast.Return:
            if ret.value and isinstance(ret.value, ast.Call):
                func_name = _get_name(ret.value.func)
                if func_name in ("Response", "JSONResponse", "JsonResponse"):
                    if ret.value.args:
                        ret.value = ret.value.args[0]
                        changes.append(f"Unwrapped {func_name}() -> direct return")
            return ret

    ResponseUnwrapper().visit(node)
    return changes


def transform_method_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    remove_params: list[str] | None = None,
    rename_params: dict[str, str] | None = None,
    add_params: list[tuple[str, str | None]] | None = None,
) -> list[str]:
    """Transform a function's parameter list.

    Args:
        node: Function node to mutate.
        remove_params: Param names to remove.
        rename_params: {old_name: new_name} mapping.
        add_params: [(name, annotation_str), ...] to add.

    Returns:
        Change descriptions.
    """
    changes: list[str] = []
    remove_params = remove_params or []
    rename_params = rename_params or {}
    add_params = add_params or []

    # Remove
    new_args = []
    for arg in node.args.args:
        if arg.arg in remove_params:
            changes.append(f"Removed parameter '{arg.arg}'")
        else:
            new_args.append(arg)
    node.args.args = new_args

    # Rename
    for arg in node.args.args:
        if arg.arg in rename_params:
            old = arg.arg
            arg.arg = rename_params[old]
            changes.append(f"Renamed parameter '{old}' -> '{arg.arg}'")

    # Add
    for name, annotation_str in add_params:
        existing = {a.arg for a in node.args.args}
        if name not in existing:
            ann = ast.Name(id=annotation_str, ctx=ast.Load()) if annotation_str else None
            node.args.args.append(ast.arg(arg=name, annotation=ann))
            changes.append(f"Added parameter '{name}'")

    return changes


def rename_all_references(tree: ast.Module, old_name: str, new_name: str) -> int:
    """Rename all Name references from old_name to new_name. Returns count."""
    count = 0

    class Renamer(ast.NodeTransformer):
        nonlocal count

        def visit_Name(self, node: ast.Name) -> ast.Name:
            nonlocal count
            if node.id == old_name:
                node.id = new_name
                count += 1
            return node

    Renamer().visit(tree)
    return count


def _get_name(node: ast.expr) -> str:
    """Extract a simple name string from an AST expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _get_name(node.func)
    return ""
