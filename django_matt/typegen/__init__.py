"""
Django Matt Type Generation - TypeScript and Swift code generation from Python types.

Provides:
- Pydantic schema to TypeScript interface conversion
- Django model to TypeScript interface conversion
- Zod validation schema generation
- Typed API client generation
- Watch mode for development

Example:
    from django_matt.typegen import (
        TypeScriptGenerator,
        generate_typescript,
        generate_zod_schema,
        generate_api_client,
    )

    # Generate TypeScript from Pydantic models
    from myapp.schemas import UserSchema, PostSchema

    generator = TypeScriptGenerator()
    ts_code = generator.generate([UserSchema, PostSchema])

    # Or use the convenience function
    ts_code = generate_typescript(
        schemas=[UserSchema, PostSchema],
        output_path="frontend/src/types/api.ts",
    )
"""

# TypeScript Generation
# API Client Generation
from django_matt.typegen.api_client import (
    APIClientGenerator,
    generate_api_client,
)

# Swift Generation
from django_matt.typegen.swift import (
    SwiftGenerator,
    generate_swift,
    pydantic_to_swift,
)
from django_matt.typegen.typescript import (
    TypeScriptGenerator,
    django_model_to_typescript,
    generate_typescript,
    pydantic_to_typescript,
)

# Utilities
from django_matt.typegen.utils import (
    collect_models_from_app,
    collect_schemas_from_module,
    get_type_name,
    python_type_to_typescript,
    python_type_to_zod,
)

# Zod Generation
from django_matt.typegen.zod import (
    ZodGenerator,
    generate_zod_schema,
    pydantic_to_zod,
)

__all__ = [
    # TypeScript
    "TypeScriptGenerator",
    "generate_typescript",
    "pydantic_to_typescript",
    "django_model_to_typescript",
    # Zod
    "ZodGenerator",
    "generate_zod_schema",
    "pydantic_to_zod",
    # API Client
    "APIClientGenerator",
    "generate_api_client",
    # Swift
    "SwiftGenerator",
    "generate_swift",
    "pydantic_to_swift",
    # Utilities
    "get_type_name",
    "python_type_to_typescript",
    "python_type_to_zod",
    "collect_schemas_from_module",
    "collect_models_from_app",
]
