"""
AST block-level source comparison.

Compares two versions of a Python file at the AST node level, not the line level.
A comment change or whitespace change does NOT invalidate tests — only structural
changes to functions, classes, and top-level statements trigger re-runs.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Block:
    """An AST block range with a content hash."""

    start_line: int
    end_line: int
    block_type: str  # "function", "class", "method", "statement"
    name: str  # qualified name (e.g., "MyClass.my_method")
    content_hash: str

    @property
    def key(self) -> tuple[int, int]:
        return (self.start_line, self.end_line)


@dataclass(frozen=True, slots=True)
class BlockChange:
    """A change between two file versions at block level."""

    start_line: int
    end_line: int
    change_type: str  # "modified", "added", "removed"
    block_type: str
    name: str


class ASTBlockDiffer:
    """Compare two versions of a Python file at the AST block level."""

    def extract_blocks(self, source: str) -> list[Block]:
        """Extract all top-level AST blocks (functions, classes, statements)."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # If we can't parse, treat the whole file as one block
            h = self._hash(source)
            return [Block(1, source.count("\n") + 1, "unparseable", "<file>", h)]

        blocks: list[Block] = []
        lines = source.splitlines()

        for node in ast.iter_child_nodes(tree):
            if not hasattr(node, "lineno"):
                continue
            blocks.extend(self._extract_node_blocks(node, lines, prefix=""))

        return blocks

    def _extract_node_blocks(self, node: ast.AST, lines: list[str], prefix: str) -> list[Block]:
        """Recursively extract blocks from an AST node."""
        blocks: list[Block] = []

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            name = f"{prefix}{node.name}" if prefix else node.name
            start = node.lineno
            end = node.end_lineno or node.lineno
            content = "\n".join(lines[start - 1 : end])
            blocks.append(Block(start, end, "function", name, self._hash(content)))

        elif isinstance(node, ast.ClassDef):
            name = f"{prefix}{node.name}" if prefix else node.name
            start = node.lineno
            end = node.end_lineno or node.lineno
            content = "\n".join(lines[start - 1 : end])
            blocks.append(Block(start, end, "class", name, self._hash(content)))

            # Extract methods within the class
            class_prefix = f"{name}."
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    method_start = child.lineno
                    method_end = child.end_lineno or child.lineno
                    method_content = "\n".join(lines[method_start - 1 : method_end])
                    method_name = f"{class_prefix}{child.name}"
                    blocks.append(
                        Block(
                            method_start,
                            method_end,
                            "method",
                            method_name,
                            self._hash(method_content),
                        )
                    )

        elif hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            start = node.lineno
            end = node.end_lineno or node.lineno
            content = "\n".join(lines[start - 1 : end])
            name = self._statement_name(node)
            blocks.append(Block(start, end, "statement", name, self._hash(content)))

        return blocks

    def changed_blocks(self, old_source: str, new_source: str) -> list[BlockChange]:
        """Return blocks that changed between two versions of a file.

        Comparison is by name+hash: if a function moved lines but content is
        identical, it's NOT considered changed.
        """
        old_blocks = self.extract_blocks(old_source)
        new_blocks = self.extract_blocks(new_source)

        # Index by (block_type, name) for matching
        old_by_name: dict[tuple[str, str], Block] = {(b.block_type, b.name): b for b in old_blocks}
        new_by_name: dict[tuple[str, str], Block] = {(b.block_type, b.name): b for b in new_blocks}

        changes: list[BlockChange] = []

        # Modified or removed blocks
        for key, old_block in old_by_name.items():
            new_block = new_by_name.get(key)
            if new_block is None:
                changes.append(
                    BlockChange(
                        old_block.start_line,
                        old_block.end_line,
                        "removed",
                        old_block.block_type,
                        old_block.name,
                    )
                )
            elif new_block.content_hash != old_block.content_hash:
                changes.append(
                    BlockChange(
                        new_block.start_line,
                        new_block.end_line,
                        "modified",
                        new_block.block_type,
                        new_block.name,
                    )
                )

        # Added blocks
        for key, new_block in new_by_name.items():
            if key not in old_by_name:
                changes.append(
                    BlockChange(
                        new_block.start_line,
                        new_block.end_line,
                        "added",
                        new_block.block_type,
                        new_block.name,
                    )
                )

        return changes

    def file_has_changes(self, old_source: str, new_source: str) -> bool:
        """Quick check: did any AST blocks change between versions?"""
        return bool(self.changed_blocks(old_source, new_source))

    @staticmethod
    def _hash(content: str) -> str:
        """Hash content, stripping comments and normalizing whitespace."""
        # Remove comment-only lines and normalize
        filtered = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                filtered.append(stripped)
        normalized = "\n".join(filtered)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    @staticmethod
    def _statement_name(node: ast.AST) -> str:
        """Best-effort name for a top-level statement."""
        if isinstance(node, ast.Assign):
            targets = []
            for t in node.targets:
                if isinstance(t, ast.Name):
                    targets.append(t.id)
            return f"assign:{','.join(targets)}" if targets else f"assign:L{node.lineno}"
        if isinstance(node, ast.Import):
            return f"import:{','.join(a.name for a in node.names)}"
        if isinstance(node, ast.ImportFrom):
            return f"from:{node.module or '?'}"
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            return f"augassign:{node.target.id}"
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            return f"annassign:{node.target.id}"
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            return f"docstring:L{node.lineno}"
        return f"stmt:L{node.lineno}"
