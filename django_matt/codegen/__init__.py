"""
Django Matt Codegen - Universal Frontend Code Generation.

Built-in code generation engine that replaces Jinja2 for type/component generation.

Usage:
    from django_matt.codegen import generate_typescript, generate_react
    from myapp.models import User

    # Generate TypeScript types
    ts_code = generate_typescript(User)

    # Generate React components with TanStack Query hooks
    react_code = generate_react(User, include_hooks=True, include_forms=True)

    # Full generation for a directory
    from django_matt.codegen import CodeGenerator

    gen = CodeGenerator(
        models=[User, Post, Comment],
        framework="react",
        output_dir="./frontend/src/generated",
    )
    gen.generate_all()
"""

from django_matt.codegen.core import (
    CodeNode,
    Statement,
    Block,
    Import,
    ImportFrom,
    Variable,
    Function,
    Class,
    Interface,
    TypeAlias,
    ObjectLiteral,
    ArrayLiteral,
    Property,
    Parameter,
    Return,
    Comment,
    CodeFile,
    CodeGenerator as BaseCodeGenerator,
)

from django_matt.codegen.typescript import (
    TypeScriptGenerator,
    generate_typescript_interface,
    generate_zod_schema,
    django_field_to_typescript,
)

from django_matt.codegen.react import (
    ReactGenerator,
    generate_react_hooks,
    generate_react_form,
    generate_react_list,
    generate_react_detail,
)

from django_matt.codegen.introspection import (
    ModelIntrospector,
    FieldInfo,
    RelationInfo,
    ModelInfo,
)

__all__ = [
    # Core AST nodes
    "CodeNode",
    "Statement",
    "Block",
    "Import",
    "ImportFrom",
    "Variable",
    "Function",
    "Class",
    "Interface",
    "TypeAlias",
    "ObjectLiteral",
    "ArrayLiteral",
    "Property",
    "Parameter",
    "Return",
    "Comment",
    "CodeFile",
    "BaseCodeGenerator",
    # TypeScript generation
    "TypeScriptGenerator",
    "generate_typescript_interface",
    "generate_zod_schema",
    "django_field_to_typescript",
    # React generation
    "ReactGenerator",
    "generate_react_hooks",
    "generate_react_form",
    "generate_react_list",
    "generate_react_detail",
    # Model introspection
    "ModelIntrospector",
    "FieldInfo",
    "RelationInfo",
    "ModelInfo",
]
