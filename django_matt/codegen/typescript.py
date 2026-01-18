"""
TypeScript code generator.

Generates TypeScript interfaces and Zod schemas from Django models.

Usage:
    from django_matt.codegen.typescript import TypeScriptGenerator
    from myapp.models import User

    # Generate TypeScript interface
    ts_code = generate_typescript_interface(User)

    # Generate Zod schema
    zod_code = generate_zod_schema(User)

    # Full generation
    gen = TypeScriptGenerator([User, Post])
    gen.generate_types("./frontend/src/types")
"""

from django.db import models

from django_matt.codegen.core import (
    CodeFile,
    CodeGenerator,
    ImportFrom,
    Interface,
    Property,
    Statement,
    TypeAlias,
)
from django_matt.codegen.introspection import (
    FieldInfo,
    ModelIntrospector,
)

# Django field to TypeScript type mapping
DJANGO_TO_TS: dict[str, str] = {
    "AutoField": "number",
    "BigAutoField": "number",
    "SmallAutoField": "number",
    "IntegerField": "number",
    "SmallIntegerField": "number",
    "BigIntegerField": "number",
    "PositiveIntegerField": "number",
    "PositiveSmallIntegerField": "number",
    "PositiveBigIntegerField": "number",
    "FloatField": "number",
    "DecimalField": "string",
    "CharField": "string",
    "TextField": "string",
    "EmailField": "string",
    "URLField": "string",
    "SlugField": "string",
    "UUIDField": "string",
    "BooleanField": "boolean",
    "NullBooleanField": "boolean | null",
    "DateField": "string",
    "DateTimeField": "string",
    "TimeField": "string",
    "DurationField": "string",
    "BinaryField": "string",
    "FileField": "string",
    "ImageField": "string",
    "FilePathField": "string",
    "IPAddressField": "string",
    "GenericIPAddressField": "string",
    "JSONField": "Record<string, unknown>",
}

# Django field to Zod schema mapping
DJANGO_TO_ZOD: dict[str, str] = {
    "AutoField": "z.number().int()",
    "BigAutoField": "z.number().int()",
    "SmallAutoField": "z.number().int()",
    "IntegerField": "z.number().int()",
    "SmallIntegerField": "z.number().int()",
    "BigIntegerField": "z.number().int()",
    "PositiveIntegerField": "z.number().int().positive()",
    "PositiveSmallIntegerField": "z.number().int().positive()",
    "PositiveBigIntegerField": "z.number().int().positive()",
    "FloatField": "z.number()",
    "DecimalField": "z.string()",  # Or z.number() with coerce
    "CharField": "z.string()",
    "TextField": "z.string()",
    "EmailField": "z.string().email()",
    "URLField": "z.string().url()",
    "SlugField": "z.string()",
    "UUIDField": "z.string().uuid()",
    "BooleanField": "z.boolean()",
    "NullBooleanField": "z.boolean().nullable()",
    "DateField": "z.string()",  # Or z.coerce.date()
    "DateTimeField": "z.string()",  # Or z.coerce.date()
    "TimeField": "z.string()",
    "DurationField": "z.string()",
    "BinaryField": "z.string()",
    "FileField": "z.string()",
    "ImageField": "z.string()",
    "FilePathField": "z.string()",
    "IPAddressField": "z.string().ip()",
    "GenericIPAddressField": "z.string().ip()",
    "JSONField": "z.record(z.unknown())",
}


def django_field_to_typescript(field: FieldInfo) -> str:
    """Convert a Django field to its TypeScript type."""
    # Handle choices
    if field.choices:
        choice_values = [f'"{c[0]}"' for c in field.choices]
        ts_type = " | ".join(choice_values)
    else:
        ts_type = DJANGO_TO_TS.get(field.field_type, "unknown")

    # Handle nullable
    if field.nullable:
        ts_type = f"{ts_type} | null"

    return ts_type


def django_field_to_zod(field: FieldInfo) -> str:
    """Convert a Django field to its Zod schema."""
    # Handle choices
    if field.choices:
        choice_values = [f'"{c[0]}"' for c in field.choices]
        zod_schema = f"z.enum([{', '.join(choice_values)}])"
    else:
        zod_schema = DJANGO_TO_ZOD.get(field.field_type, "z.unknown()")

    # Add max length
    if field.max_length and field.field_type in ("CharField", "TextField", "SlugField"):
        zod_schema = f"{zod_schema}.max({field.max_length})"

    # Handle nullable and optional
    if field.nullable:
        zod_schema = f"{zod_schema}.nullable()"
    if not field.is_required:
        zod_schema = f"{zod_schema}.optional()"

    return zod_schema


def generate_typescript_interface(
    model: type[models.Model],
    include_relations: bool = False,
) -> str:
    """
    Generate a TypeScript interface for a Django model.

    Args:
        model: Django model class
        include_relations: Include relation fields

    Returns:
        TypeScript interface code
    """
    info = ModelIntrospector(model).introspect()

    properties = []
    for field in info.fields:
        ts_type = django_field_to_typescript(field)
        properties.append(
            Property(
                name=field.name,
                type=ts_type,
                optional=not field.is_required,
                readonly=not field.is_editable or field.is_auto,
                comment=field.help_text if field.help_text else None,
            )
        )

    interface = Interface(
        name=info.name,
        properties=properties,
        comment=f"Generated from {info.full_name}",
    )

    return interface.to_typescript()


def generate_zod_schema(
    model: type[models.Model],
    schema_name: str | None = None,
) -> str:
    """
    Generate a Zod schema for a Django model.

    Args:
        model: Django model class
        schema_name: Custom schema name (default: {ModelName}Schema)

    Returns:
        Zod schema code
    """
    info = ModelIntrospector(model).introspect()
    schema_name = schema_name or f"{info.name}Schema"

    # Build schema object
    schema_props = {}
    for field in info.fields:
        zod_type = django_field_to_zod(field)
        schema_props[field.name] = zod_type

    # Build the code
    lines = [f"export const {schema_name} = z.object({{"]
    for name, zod_type in schema_props.items():
        lines.append(f"  {name}: {zod_type},")
    lines.append("})")

    return "\n".join(lines)


def generate_create_schema(model: type[models.Model]) -> str:
    """Generate a Zod schema for creating a model (excludes auto fields)."""
    info = ModelIntrospector(model).introspect()

    # Build schema object with only required/editable fields
    schema_props = {}
    for field in info.fields:
        if field.is_auto or field.is_primary_key:
            continue
        zod_type = django_field_to_zod(field)
        schema_props[field.name] = zod_type

    lines = [f"export const {info.name}CreateSchema = z.object({{"]
    for name, zod_type in schema_props.items():
        lines.append(f"  {name}: {zod_type},")
    lines.append("})")

    return "\n".join(lines)


def generate_update_schema(model: type[models.Model]) -> str:
    """Generate a Zod schema for updating a model (all fields optional)."""
    info = ModelIntrospector(model).introspect()

    # Build schema object with all editable fields as optional
    schema_props = {}
    for field in info.fields:
        if field.is_auto or field.is_primary_key:
            continue
        if not field.is_editable:
            continue
        zod_type = django_field_to_zod(field)
        # Make all optional for update
        if ".optional()" not in zod_type:
            zod_type = f"{zod_type}.optional()"
        schema_props[field.name] = zod_type

    lines = [f"export const {info.name}UpdateSchema = z.object({{"]
    for name, zod_type in schema_props.items():
        lines.append(f"  {name}: {zod_type},")
    lines.append("})")

    return "\n".join(lines)


class TypeScriptGenerator(CodeGenerator):
    """
    Generate TypeScript types and schemas from Django models.

    Usage:
        gen = TypeScriptGenerator([User, Post, Comment])
        gen.generate_types("./frontend/src/types")
    """

    def __init__(self, models: list[type[models.Model]], output_dir: str = "./generated"):
        super().__init__(output_dir)
        self.models = models
        self.model_infos = {m._meta.object_name: ModelIntrospector(m).introspect() for m in models}

    def generate_types_file(self) -> CodeFile:
        """Generate a types.ts file with all interfaces."""
        file = CodeFile()
        file.header_comment = (
            "Auto-generated TypeScript types from Django models.\nDo not edit manually."
        )

        for model in self.models:
            info = self.model_infos[model._meta.object_name]

            # Generate interface
            properties = []
            for field in info.fields:
                ts_type = django_field_to_typescript(field)
                properties.append(
                    Property(
                        name=field.name,
                        type=ts_type,
                        optional=not field.is_required,
                        readonly=not field.is_editable or field.is_auto,
                        comment=field.help_text if field.help_text else None,
                    )
                )

            interface = Interface(
                name=info.name,
                properties=properties,
                comment=f"Generated from {info.full_name}",
            )
            file.add_node(interface)

            # Generate input types
            create_props = [p for p in properties if not p.readonly]
            if create_props:
                # Make all optional for create input (server may have defaults)
                create_input_props = []
                for p in create_props:
                    create_input_props.append(
                        Property(
                            name=p.name,
                            type=p.type,
                            optional=True,  # All optional for input
                        )
                    )
                create_interface = Interface(
                    name=f"{info.name}CreateInput",
                    properties=create_input_props,
                    comment=f"Input type for creating {info.name}",
                )
                file.add_node(create_interface)

                update_interface = Interface(
                    name=f"{info.name}UpdateInput",
                    properties=create_input_props,  # Same as create but partial
                    comment=f"Input type for updating {info.name}",
                )
                file.add_node(update_interface)

        return file

    def generate_schemas_file(self) -> CodeFile:
        """Generate a schemas.ts file with all Zod schemas."""
        file = CodeFile()
        file.header_comment = (
            "Auto-generated Zod schemas from Django models.\nDo not edit manually."
        )

        # Add zod import
        file.add_import(ImportFrom("zod", ["z"]))

        for model in self.models:
            info = self.model_infos[model._meta.object_name]

            # Full schema
            schema_code = generate_zod_schema(model, f"{info.name}Schema")
            file.add_node(Statement(schema_code))

            # Create schema
            create_code = generate_create_schema(model)
            file.add_node(Statement(create_code))

            # Update schema
            update_code = generate_update_schema(model)
            file.add_node(Statement(update_code))

            # Infer types
            file.add_node(
                TypeAlias(
                    name=f"{info.name}",
                    type=f"z.infer<typeof {info.name}Schema>",
                )
            )
            file.add_node(
                TypeAlias(
                    name=f"{info.name}Create",
                    type=f"z.infer<typeof {info.name}CreateSchema>",
                )
            )
            file.add_node(
                TypeAlias(
                    name=f"{info.name}Update",
                    type=f"z.infer<typeof {info.name}UpdateSchema>",
                )
            )

        return file

    def generate_all(self) -> dict[str, str]:
        """Generate all TypeScript files."""
        self.add_file("types.ts", self.generate_types_file())
        self.add_file("schemas.ts", self.generate_schemas_file())
        return self.generate()


__all__ = [
    "DJANGO_TO_TS",
    "DJANGO_TO_ZOD",
    "TypeScriptGenerator",
    "django_field_to_typescript",
    "django_field_to_zod",
    "generate_create_schema",
    "generate_typescript_interface",
    "generate_update_schema",
    "generate_zod_schema",
]
