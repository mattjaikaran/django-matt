"""
Zod validation schema generation from Pydantic schemas.
"""

import sys
from pathlib import Path
from typing import Any, get_type_hints

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from django_matt.typegen.utils import (
    python_type_to_zod,
    snake_to_camel,
)


class ZodGenerator:
    """
    Generate Zod validation schemas from Pydantic schemas.

    Example:
        generator = ZodGenerator()
        zod_code = generator.generate([UserSchema, PostSchema])

        # With options
        generator = ZodGenerator(
            schema_suffix="Schema",
            camel_case=True,
            include_descriptions=True,
        )
    """

    def __init__(
        self,
        schema_suffix: str = "Schema",
        camel_case: bool = False,
        include_descriptions: bool = True,
        include_defaults: bool = True,
    ):
        """
        Initialize Zod generator.

        Args:
            schema_suffix: Suffix to add to schema names
            camel_case: Convert snake_case field names to camelCase
            include_descriptions: Include field descriptions in schema
            include_defaults: Include default values in schema
        """
        self.schema_suffix = schema_suffix
        self.camel_case = camel_case
        self.include_descriptions = include_descriptions
        self.include_defaults = include_defaults

        self._generated: set[str] = set()
        self._schema_names: set[str] = set()

    def generate(
        self,
        schemas: list[type[BaseModel]],
        header: str | None = None,
    ) -> str:
        """
        Generate Zod schemas from Pydantic schemas.

        Args:
            schemas: List of Pydantic BaseModel classes
            header: Optional header comment

        Returns:
            Zod schema code as string
        """
        self._generated.clear()
        self._schema_names = {s.__name__ for s in schemas}

        lines = []

        # Add header
        if header:
            lines.append(f"// {header}")
        else:
            lines.append("// Auto-generated Zod schemas from Pydantic models")
            lines.append("// Do not edit manually - regenerate with sync_types command")
        lines.append("")

        # Import statement
        lines.append('import { z } from "zod";')
        lines.append("")

        # Generate schemas
        for schema in schemas:
            if schema.__name__ not in self._generated:
                schema_code = self._generate_schema(schema)
                lines.append(schema_code)
                lines.append("")

        # Generate type exports
        lines.append("// Inferred types")
        for schema in schemas:
            name = schema.__name__
            schema_name = f"{name}{self.schema_suffix}"
            lines.append(f"export type {name} = z.infer<typeof {schema_name}>;")

        return "\n".join(lines)

    def _generate_schema(self, schema: type[BaseModel]) -> str:
        """Generate Zod schema for a single Pydantic model."""
        self._generated.add(schema.__name__)

        name = schema.__name__
        schema_name = f"{name}{self.schema_suffix}"

        lines = []

        # Add JSDoc comment
        doc = schema.__doc__
        if doc:
            lines.append("/**")
            for line in doc.strip().split("\n"):
                lines.append(f" * {line.strip()}")
            lines.append(" */")

        # Schema declaration
        lines.append(f"export const {schema_name} = z.object({{")

        # Generate fields
        for field_name, field_info in schema.model_fields.items():
            field_code = self._generate_field(field_name, field_info, schema)
            lines.append(f"  {field_code}")

        lines.append("});")

        return "\n".join(lines)

    def _generate_field(
        self,
        field_name: str,
        field_info: FieldInfo,
        schema: type[BaseModel],
    ) -> str:
        """Generate Zod field declaration."""
        # Use get_type_hints to resolve inherited fields and forward references
        module = sys.modules.get(schema.__module__, None)
        module_ns = vars(module) if module else {}
        try:
            hints = get_type_hints(schema, localns=module_ns)
        except Exception:
            hints = {}
        python_type = hints.get(field_name, Any)

        # Convert to Zod schema
        zod_type = python_type_to_zod(python_type, self._schema_names)

        # Convert field name if camelCase is enabled
        output_name = snake_to_camel(field_name) if self.camel_case else field_name

        # Check if field is optional
        is_optional = not field_info.is_required()

        # Build modifiers
        modifiers = []

        # Add description
        if self.include_descriptions and field_info.description:
            modifiers.append(f'.describe("{field_info.description}")')

        # Add default value
        if self.include_defaults and field_info.default is not None:
            default_val = field_info.default
            if isinstance(default_val, str):
                modifiers.append(f'.default("{default_val}")')
            elif isinstance(default_val, bool):
                modifiers.append(f".default({str(default_val).lower()})")
            elif isinstance(default_val, (int, float)):
                modifiers.append(f".default({default_val})")
            elif isinstance(default_val, dict):
                modifiers.append(".default({})")
            elif isinstance(default_val, list):
                modifiers.append(".default([])")

        # Add optional modifier
        if is_optional and ".nullable()" not in zod_type:
            modifiers.append(".optional()")

        # Combine
        modifier_str = "".join(modifiers)

        return f"{output_name}: {zod_type}{modifier_str},"

    def generate_with_refinements(
        self,
        schemas: list[type[BaseModel]],
        refinements: dict,
    ) -> str:
        """
        Generate Zod schemas with custom refinements.

        Args:
            schemas: List of Pydantic BaseModel classes
            refinements: Dict mapping schema.field to refinement code

        Returns:
            Zod schema code with refinements
        """
        base_code = self.generate(schemas)

        # Add refinements as separate exports
        lines = [base_code, "", "// Schemas with refinements"]

        for schema in schemas:
            name = schema.__name__
            schema_name = f"{name}{self.schema_suffix}"
            refined_name = f"{name}Refined{self.schema_suffix}"

            schema_refinements = {
                k.split(".")[-1]: v for k, v in refinements.items() if k.startswith(f"{name}.")
            }

            if schema_refinements:
                lines.append(f"export const {refined_name} = {schema_name}")
                for field, refinement in schema_refinements.items():
                    lines.append("  .refine(")
                    lines.append(f"    (data) => {refinement},")
                    lines.append(f'    {{ path: ["{field}"], message: "Validation failed" }},')
                    lines.append("  )")
                lines.append(";")
                lines.append("")

        return "\n".join(lines)


def generate_zod_schema(
    schemas: list[type[BaseModel]],
    output_path: str | None = None,
    **kwargs,
) -> str:
    """
    Convenience function to generate Zod schemas.

    Args:
        schemas: List of Pydantic BaseModel classes
        output_path: Optional path to write the output file
        **kwargs: Additional options passed to ZodGenerator

    Returns:
        Zod schema code as string
    """
    generator = ZodGenerator(**kwargs)
    code = generator.generate(schemas)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    return code


def pydantic_to_zod(
    schema: type[BaseModel],
    **kwargs,
) -> str:
    """
    Convert a single Pydantic schema to Zod schema.

    Args:
        schema: Pydantic BaseModel class
        **kwargs: Additional options passed to ZodGenerator

    Returns:
        Zod schema code
    """
    generator = ZodGenerator(**kwargs)
    return generator.generate([schema])
