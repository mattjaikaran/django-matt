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
    ArrayLiteral,
    Block,
    Class,
    CodeFile,
    CodeNode,
    Comment,
    Function,
    Import,
    ImportFrom,
    Interface,
    ObjectLiteral,
    Parameter,
    Property,
    Return,
    Statement,
    TypeAlias,
    Variable,
)
from django_matt.codegen.core import (
    CodeGenerator as BaseCodeGenerator,
)
from django_matt.codegen.introspection import (
    FieldInfo,
    ModelInfo,
    ModelIntrospector,
    RelationInfo,
)
from django_matt.codegen.react import (
    ReactGenerator,
    generate_react_detail,
    generate_react_form,
    generate_react_hooks,
    generate_react_list,
)
from django_matt.codegen.solid import (
    SolidGenerator,
    generate_solid_detail,
    generate_solid_form,
    generate_solid_list,
    generate_solid_resource,
)
from django_matt.codegen.svelte import (
    SvelteGenerator,
    generate_svelte5_stores,
    generate_svelte_detail,
    generate_svelte_form,
    generate_svelte_list,
    generate_svelte_stores,
)
from django_matt.codegen.typescript import (
    TypeScriptGenerator,
    django_field_to_typescript,
    generate_typescript_interface,
    generate_zod_schema,
)
from django_matt.codegen.watcher import (
    CodegenWatcher,
    DebouncedCallback,
    HAS_WATCHDOG,
    PollingWatcher,
    WatchConfig,
    get_module_file,
    reload_module,
)
from django_matt.codegen.config import (
    CodegenConfig,
    ModelConfig,
    create_config_file,
    find_project_root,
    load_config,
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
    # Svelte generation
    "SvelteGenerator",
    "generate_svelte_stores",
    "generate_svelte5_stores",
    "generate_svelte_form",
    "generate_svelte_list",
    "generate_svelte_detail",
    # SolidJS generation
    "SolidGenerator",
    "generate_solid_resource",
    "generate_solid_form",
    "generate_solid_list",
    "generate_solid_detail",
    # Model introspection
    "ModelIntrospector",
    "FieldInfo",
    "RelationInfo",
    "ModelInfo",
    # File watching
    "CodegenWatcher",
    "WatchConfig",
    "DebouncedCallback",
    "PollingWatcher",
    "HAS_WATCHDOG",
    "reload_module",
    "get_module_file",
    # Configuration
    "CodegenConfig",
    "ModelConfig",
    "load_config",
    "create_config_file",
    "find_project_root",
]
