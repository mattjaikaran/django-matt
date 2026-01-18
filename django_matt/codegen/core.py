"""
Core code generation primitives.

Provides AST-like nodes for building code in any language.
These primitives are language-agnostic and can be rendered to
TypeScript, JavaScript, Svelte, etc.

Usage:
    from django_matt.codegen.core import Interface, Property, Function

    # Build an interface
    user_interface = Interface(
        name="User",
        properties=[
            Property("id", "number"),
            Property("email", "string"),
            Property("name", "string", optional=True),
        ],
    )

    # Render to TypeScript
    print(user_interface.to_typescript())
    # Output:
    # export interface User {
    #   id: number
    #   email: string
    #   name?: string
    # }
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Union


class CodeNode(ABC):
    """Base class for all code generation nodes."""

    @abstractmethod
    def to_typescript(self, indent: int = 0) -> str:
        """Render this node as TypeScript code."""

    def to_javascript(self, indent: int = 0) -> str:
        """Render this node as JavaScript code. Default: same as TypeScript."""
        return self.to_typescript(indent)

    def _indent(self, level: int) -> str:
        """Get indentation string."""
        return "  " * level


@dataclass
class Comment(CodeNode):
    """A code comment."""

    text: str
    multiline: bool = False
    doc: bool = False  # JSDoc style

    def to_typescript(self, indent: int = 0) -> str:
        prefix = self._indent(indent)
        if self.doc:
            lines = self.text.strip().split("\n")
            if len(lines) == 1:
                return f"{prefix}/** {lines[0]} */"
            result = [f"{prefix}/**"]
            for line in lines:
                result.append(f"{prefix} * {line}")
            result.append(f"{prefix} */")
            return "\n".join(result)
        if self.multiline:
            return f"{prefix}/* {self.text} */"
        return f"{prefix}// {self.text}"


@dataclass
class Import(CodeNode):
    """A default or namespace import."""

    module: str
    name: str  # Import name or * for namespace
    alias: str | None = None  # as alias

    def to_typescript(self, indent: int = 0) -> str:
        prefix = self._indent(indent)
        if self.name == "*":
            if self.alias:
                return f'{prefix}import * as {self.alias} from "{self.module}"'
            return f'{prefix}import * from "{self.module}"'
        if self.alias:
            return f'{prefix}import {self.name} as {self.alias} from "{self.module}"'
        return f'{prefix}import {self.name} from "{self.module}"'


@dataclass
class ImportFrom(CodeNode):
    """A named import from a module."""

    module: str
    names: list[str | tuple]  # ["foo", "bar"] or [("foo", "f"), "bar"]
    type_only: bool = False  # import type { ... }

    def to_typescript(self, indent: int = 0) -> str:
        prefix = self._indent(indent)
        type_prefix = "type " if self.type_only else ""

        imports = []
        for name in self.names:
            if isinstance(name, tuple):
                imports.append(f"{name[0]} as {name[1]}")
            else:
                imports.append(name)

        names_str = ", ".join(imports)
        return f'{prefix}import {type_prefix}{{ {names_str} }} from "{self.module}"'


@dataclass
class Property(CodeNode):
    """A property in an interface or object."""

    name: str
    type: str
    optional: bool = False
    readonly: bool = False
    default: str | None = None
    comment: str | None = None

    def to_typescript(self, indent: int = 0) -> str:
        prefix = self._indent(indent)
        result = []

        if self.comment:
            result.append(Comment(self.comment, doc=True).to_typescript(indent))

        readonly = "readonly " if self.readonly else ""
        optional = "?" if self.optional else ""
        result.append(f"{prefix}{readonly}{self.name}{optional}: {self.type}")

        return "\n".join(result)


@dataclass
class Parameter(CodeNode):
    """A function parameter."""

    name: str
    type: str | None = None
    default: str | None = None
    optional: bool = False
    rest: bool = False  # ...args

    def to_typescript(self, indent: int = 0) -> str:
        rest = "..." if self.rest else ""
        optional = "?" if self.optional and not self.default else ""
        type_annotation = f": {self.type}" if self.type else ""
        default = f" = {self.default}" if self.default else ""
        return f"{rest}{self.name}{optional}{type_annotation}{default}"


@dataclass
class Statement(CodeNode):
    """A raw code statement."""

    code: str

    def to_typescript(self, indent: int = 0) -> str:
        prefix = self._indent(indent)
        return f"{prefix}{self.code}"


@dataclass
class Return(CodeNode):
    """A return statement."""

    value: Union[str, "CodeNode"] | None = None

    def to_typescript(self, indent: int = 0) -> str:
        prefix = self._indent(indent)
        if self.value is None:
            return f"{prefix}return"
        if isinstance(self.value, CodeNode):
            return f"{prefix}return {self.value.to_typescript(0)}"
        return f"{prefix}return {self.value}"


@dataclass
class Variable(CodeNode):
    """A variable declaration."""

    name: str
    value: Union[str, "CodeNode"] | None = None
    type: str | None = None
    const: bool = True
    export: bool = False

    def to_typescript(self, indent: int = 0) -> str:
        prefix = self._indent(indent)
        export = "export " if self.export else ""
        kind = "const" if self.const else "let"
        type_annotation = f": {self.type}" if self.type else ""

        if self.value is None:
            return f"{prefix}{export}{kind} {self.name}{type_annotation}"
        if isinstance(self.value, CodeNode):
            value_str = self.value.to_typescript(0)
            return f"{prefix}{export}{kind} {self.name}{type_annotation} = {value_str}"
        return f"{prefix}{export}{kind} {self.name}{type_annotation} = {self.value}"


@dataclass
class Block(CodeNode):
    """A block of code (statements)."""

    statements: list[CodeNode] = field(default_factory=list)

    def to_typescript(self, indent: int = 0) -> str:
        return "\n".join(s.to_typescript(indent) for s in self.statements)


@dataclass
class ObjectLiteral(CodeNode):
    """An object literal { key: value }."""

    properties: dict[str, Union[str, "CodeNode"]] = field(default_factory=dict)
    multiline: bool = True

    def to_typescript(self, indent: int = 0) -> str:
        if not self.properties:
            return "{}"

        if self.multiline:
            prefix = self._indent(indent)
            inner_prefix = self._indent(indent + 1)
            lines = ["{"]
            for key, value in self.properties.items():
                if isinstance(value, CodeNode):
                    value_str = value.to_typescript(0)
                else:
                    value_str = str(value)
                lines.append(f"{inner_prefix}{key}: {value_str},")
            lines.append(f"{prefix}}}")
            return "\n".join(lines)
        props = []
        for key, value in self.properties.items():
            if isinstance(value, CodeNode):
                value_str = value.to_typescript(0)
            else:
                value_str = str(value)
            props.append(f"{key}: {value_str}")
        return "{ " + ", ".join(props) + " }"


@dataclass
class ArrayLiteral(CodeNode):
    """An array literal [a, b, c]."""

    items: list[Union[str, "CodeNode"]] = field(default_factory=list)
    multiline: bool = False

    def to_typescript(self, indent: int = 0) -> str:
        if not self.items:
            return "[]"

        rendered = []
        for item in self.items:
            if isinstance(item, CodeNode):
                rendered.append(item.to_typescript(0))
            else:
                rendered.append(str(item))

        if self.multiline:
            prefix = self._indent(indent)
            inner_prefix = self._indent(indent + 1)
            lines = ["["]
            for item in rendered:
                lines.append(f"{inner_prefix}{item},")
            lines.append(f"{prefix}]")
            return "\n".join(lines)
        return "[" + ", ".join(rendered) + "]"


@dataclass
class Function(CodeNode):
    """A function declaration."""

    name: str
    parameters: list[Parameter] = field(default_factory=list)
    return_type: str | None = None
    body: list[CodeNode] = field(default_factory=list)
    async_: bool = False
    export: bool = False
    arrow: bool = False
    generic: str | None = None  # <T>
    comment: str | None = None

    def to_typescript(self, indent: int = 0) -> str:
        prefix = self._indent(indent)
        result = []

        if self.comment:
            result.append(Comment(self.comment, doc=True).to_typescript(indent))

        export = "export " if self.export else ""
        async_ = "async " if self.async_ else ""
        generic = f"<{self.generic}>" if self.generic else ""
        params = ", ".join(p.to_typescript() for p in self.parameters)
        return_type = f": {self.return_type}" if self.return_type else ""

        if self.arrow:
            # Arrow function
            result.append(
                f"{prefix}{export}const {self.name} = {async_}{generic}({params}){return_type} => {{"
            )
        else:
            result.append(
                f"{prefix}{export}{async_}function {self.name}{generic}({params}){return_type} {{"
            )

        for statement in self.body:
            result.append(statement.to_typescript(indent + 1))

        result.append(f"{prefix}}}")

        return "\n".join(result)


@dataclass
class Interface(CodeNode):
    """A TypeScript interface."""

    name: str
    properties: list[Property] = field(default_factory=list)
    extends: list[str] | None = None
    export: bool = True
    generic: str | None = None
    comment: str | None = None

    def to_typescript(self, indent: int = 0) -> str:
        prefix = self._indent(indent)
        result = []

        if self.comment:
            result.append(Comment(self.comment, doc=True).to_typescript(indent))

        export = "export " if self.export else ""
        generic = f"<{self.generic}>" if self.generic else ""
        extends = f" extends {', '.join(self.extends)}" if self.extends else ""

        result.append(f"{prefix}{export}interface {self.name}{generic}{extends} {{")

        for prop in self.properties:
            result.append(prop.to_typescript(indent + 1))

        result.append(f"{prefix}}}")

        return "\n".join(result)


@dataclass
class TypeAlias(CodeNode):
    """A type alias."""

    name: str
    type: str
    export: bool = True
    generic: str | None = None
    comment: str | None = None

    def to_typescript(self, indent: int = 0) -> str:
        prefix = self._indent(indent)
        result = []

        if self.comment:
            result.append(Comment(self.comment, doc=True).to_typescript(indent))

        export = "export " if self.export else ""
        generic = f"<{self.generic}>" if self.generic else ""
        result.append(f"{prefix}{export}type {self.name}{generic} = {self.type}")

        return "\n".join(result)


@dataclass
class Class(CodeNode):
    """A class declaration."""

    name: str
    properties: list[Property] = field(default_factory=list)
    methods: list[Function] = field(default_factory=list)
    extends: str | None = None
    implements: list[str] | None = None
    export: bool = True
    abstract: bool = False
    generic: str | None = None
    comment: str | None = None

    def to_typescript(self, indent: int = 0) -> str:
        prefix = self._indent(indent)
        result = []

        if self.comment:
            result.append(Comment(self.comment, doc=True).to_typescript(indent))

        export = "export " if self.export else ""
        abstract = "abstract " if self.abstract else ""
        generic = f"<{self.generic}>" if self.generic else ""
        extends = f" extends {self.extends}" if self.extends else ""
        implements = f" implements {', '.join(self.implements)}" if self.implements else ""

        result.append(
            f"{prefix}{export}{abstract}class {self.name}{generic}{extends}{implements} {{"
        )

        for prop in self.properties:
            result.append(prop.to_typescript(indent + 1))

        if self.properties and self.methods:
            result.append("")

        for method in self.methods:
            result.append(method.to_typescript(indent + 1))

        result.append(f"{prefix}}}")

        return "\n".join(result)


@dataclass
class CodeFile:
    """A complete code file."""

    imports: list[Import | ImportFrom] = field(default_factory=list)
    nodes: list[CodeNode] = field(default_factory=list)
    header_comment: str | None = None

    def add_import(self, imp: Import | ImportFrom) -> None:
        """Add an import, avoiding duplicates."""
        # Check for duplicate
        for existing in self.imports:
            if isinstance(imp, ImportFrom) and isinstance(existing, ImportFrom):
                if imp.module == existing.module:
                    # Merge names
                    for name in imp.names:
                        if name not in existing.names:
                            existing.names.append(name)
                    return
            elif isinstance(imp, Import) and isinstance(existing, Import):
                if imp.module == existing.module and imp.name == existing.name:
                    return

        self.imports.append(imp)

    def add_node(self, node: CodeNode) -> None:
        """Add a code node."""
        self.nodes.append(node)

    def to_typescript(self) -> str:
        """Render the complete file as TypeScript."""
        parts = []

        # Header comment
        if self.header_comment:
            parts.append(Comment(self.header_comment, doc=True).to_typescript())
            parts.append("")

        # Imports grouped by type (external, internal)
        external_imports = []
        internal_imports = []

        for imp in self.imports:
            module = imp.module
            if module.startswith(".") or module.startswith("@/"):
                internal_imports.append(imp)
            else:
                external_imports.append(imp)

        if external_imports:
            for imp in external_imports:
                parts.append(imp.to_typescript())
            parts.append("")

        if internal_imports:
            for imp in internal_imports:
                parts.append(imp.to_typescript())
            parts.append("")

        # Nodes
        for i, node in enumerate(self.nodes):
            parts.append(node.to_typescript())
            if i < len(self.nodes) - 1:
                parts.append("")

        return "\n".join(parts)


class CodeGenerator:
    """
    Base code generator class.

    Subclass to create generators for specific frameworks.
    """

    def __init__(self, output_dir: str = "./generated"):
        self.output_dir = output_dir
        self.files: dict[str, CodeFile] = {}

    def add_file(self, path: str, file: CodeFile) -> None:
        """Add a file to be generated."""
        self.files[path] = file

    def generate(self) -> dict[str, str]:
        """Generate all files and return path -> content mapping."""
        return {path: file.to_typescript() for path, file in self.files.items()}

    def write_files(self) -> list[str]:
        """Write all files to disk."""
        import os

        written = []
        for path, content in self.generate().items():
            full_path = os.path.join(self.output_dir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
            written.append(full_path)
        return written


__all__ = [
    "ArrayLiteral",
    "Block",
    "Class",
    "CodeFile",
    "CodeGenerator",
    "CodeNode",
    "Comment",
    "Function",
    "Import",
    "ImportFrom",
    "Interface",
    "ObjectLiteral",
    "Parameter",
    "Property",
    "Return",
    "Statement",
    "TypeAlias",
    "Variable",
]
