"""
TypeScript code generation from Pydantic schemas and Django models.
"""

import datetime
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from django_matt.typegen.utils import (
    python_type_to_typescript,
    snake_to_camel,
)


class TypeScriptGenerator:
    """
    Generate TypeScript interfaces from Pydantic schemas and Django models.
    
    Example:
        generator = TypeScriptGenerator()
        ts_code = generator.generate([UserSchema, PostSchema])
        
        # With options
        generator = TypeScriptGenerator(
            export_style="named",  # or "default"
            use_interface=True,    # False for type aliases
            add_readonly=False,
            camel_case=True,
        )
    """
    
    def __init__(
        self,
        export_style: str = "named",
        use_interface: bool = True,
        add_readonly: bool = False,
        camel_case: bool = False,
        include_validators: bool = False,
    ):
        """
        Initialize TypeScript generator.
        
        Args:
            export_style: "named" for `export interface`, "default" for no export
            use_interface: Use `interface` (True) or `type` (False)
            add_readonly: Add `readonly` modifier to all properties
            camel_case: Convert snake_case field names to camelCase
            include_validators: Include validation comments
        """
        self.export_style = export_style
        self.use_interface = use_interface
        self.add_readonly = add_readonly
        self.camel_case = camel_case
        self.include_validators = include_validators
        
        # Track generated schemas to avoid duplicates
        self._generated: Set[str] = set()
        self._schema_names: Set[str] = set()
    
    def generate(
        self,
        schemas: List[Type[BaseModel]],
        header: Optional[str] = None,
    ) -> str:
        """
        Generate TypeScript code from Pydantic schemas.
        
        Args:
            schemas: List of Pydantic BaseModel classes
            header: Optional header comment to add at top
        
        Returns:
            TypeScript code as string
        """
        self._generated.clear()
        self._schema_names = {s.__name__ for s in schemas}
        
        lines = []
        
        # Add header
        if header:
            lines.append(f"// {header}")
            lines.append("")
        else:
            lines.append("// Auto-generated TypeScript types from Pydantic schemas")
            lines.append("// Do not edit manually - regenerate with sync_types command")
            lines.append("")
        
        # Generate interfaces for each schema
        for schema in schemas:
            if schema.__name__ not in self._generated:
                interface_code = self._generate_interface(schema)
                lines.append(interface_code)
                lines.append("")
        
        return "\n".join(lines)
    
    def generate_from_django_models(
        self,
        models: List[type],
        include_fields: Optional[Dict[str, List[str]]] = None,
        exclude_fields: Optional[Dict[str, List[str]]] = None,
    ) -> str:
        """
        Generate TypeScript interfaces from Django models.
        
        Args:
            models: List of Django model classes
            include_fields: Dict mapping model name to list of fields to include
            exclude_fields: Dict mapping model name to list of fields to exclude
        
        Returns:
            TypeScript code as string
        """
        lines = [
            "// Auto-generated TypeScript types from Django models",
            "// Do not edit manually - regenerate with sync_types command",
            "",
        ]
        
        for model in models:
            interface_code = self._generate_from_django_model(
                model,
                include_fields.get(model.__name__) if include_fields else None,
                exclude_fields.get(model.__name__) if exclude_fields else None,
            )
            lines.append(interface_code)
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_interface(self, schema: Type[BaseModel]) -> str:
        """Generate TypeScript interface for a single schema."""
        self._generated.add(schema.__name__)
        
        name = schema.__name__
        
        # Get doc string
        doc = schema.__doc__
        
        lines = []
        
        # Add JSDoc comment if available
        if doc:
            lines.append("/**")
            for line in doc.strip().split("\n"):
                lines.append(f" * {line.strip()}")
            lines.append(" */")
        
        # Interface declaration
        keyword = "interface" if self.use_interface else "type"
        export = "export " if self.export_style == "named" else ""
        equals = " =" if not self.use_interface else ""
        
        lines.append(f"{export}{keyword} {name}{equals} {{")
        
        # Generate fields
        for field_name, field_info in schema.model_fields.items():
            field_code = self._generate_field(field_name, field_info, schema)
            lines.append(f"  {field_code}")
        
        lines.append("}")
        
        return "\n".join(lines)
    
    def _generate_field(
        self,
        field_name: str,
        field_info: FieldInfo,
        schema: Type[BaseModel],
    ) -> str:
        """Generate TypeScript field declaration."""
        # Get field type from annotation
        annotations = schema.__annotations__
        python_type = annotations.get(field_name, Any)
        
        # Convert to TypeScript type
        ts_type = python_type_to_typescript(python_type, self._schema_names)
        
        # Convert field name if camelCase is enabled
        output_name = snake_to_camel(field_name) if self.camel_case else field_name
        
        # Check if field is optional
        is_optional = not field_info.is_required()
        optional_marker = "?" if is_optional else ""
        
        # Add readonly modifier
        readonly = "readonly " if self.add_readonly else ""
        
        # Build field declaration
        field_decl = f"{readonly}{output_name}{optional_marker}: {ts_type};"
        
        # Add description comment if available
        description = field_info.description
        if description:
            field_decl = f"/** {description} */ {field_decl}"
        
        return field_decl
    
    def _generate_from_django_model(
        self,
        model: type,
        include_fields: Optional[List[str]] = None,
        exclude_fields: Optional[List[str]] = None,
    ) -> str:
        """Generate TypeScript interface from a Django model."""
        from django.db import models
        
        name = model.__name__
        exclude_fields = exclude_fields or []
        
        lines = []
        
        # Add JSDoc comment
        doc = model.__doc__
        if doc:
            lines.append("/**")
            for line in doc.strip().split("\n"):
                lines.append(f" * {line.strip()}")
            lines.append(" */")
        
        # Interface declaration
        keyword = "interface" if self.use_interface else "type"
        export = "export " if self.export_style == "named" else ""
        equals = " =" if not self.use_interface else ""
        
        lines.append(f"{export}{keyword} {name}{equals} {{")
        
        # Get all fields from model
        for field in model._meta.fields:
            field_name = field.name
            
            # Apply include/exclude filters
            if include_fields and field_name not in include_fields:
                continue
            if field_name in exclude_fields:
                continue
            
            ts_type = self._django_field_to_typescript(field)
            
            # Check if nullable
            is_optional = field.null or field.blank or field.has_default()
            optional_marker = "?" if is_optional else ""
            
            # Convert field name if camelCase is enabled
            output_name = snake_to_camel(field_name) if self.camel_case else field_name
            
            # Add readonly modifier
            readonly = "readonly " if self.add_readonly else ""
            
            # Help text as comment
            help_text = field.help_text
            if help_text:
                lines.append(f"  /** {help_text} */")
            
            lines.append(f"  {readonly}{output_name}{optional_marker}: {ts_type};")
        
        lines.append("}")
        
        return "\n".join(lines)
    
    def _django_field_to_typescript(self, field) -> str:
        """Convert a Django field to TypeScript type."""
        from django.db import models
        
        # Mapping of Django field types to TypeScript
        type_map = {
            models.AutoField: "number",
            models.BigAutoField: "number",
            models.BigIntegerField: "number",
            models.BooleanField: "boolean",
            models.CharField: "string",
            models.DateField: "string",
            models.DateTimeField: "string",
            models.DecimalField: "number",
            models.EmailField: "string",
            models.FloatField: "number",
            models.IntegerField: "number",
            models.PositiveIntegerField: "number",
            models.PositiveSmallIntegerField: "number",
            models.SlugField: "string",
            models.SmallIntegerField: "number",
            models.TextField: "string",
            models.TimeField: "string",
            models.URLField: "string",
            models.UUIDField: "string",
            models.JSONField: "Record<string, any>",
            models.BinaryField: "string",
            models.IPAddressField: "string",
            models.GenericIPAddressField: "string",
            models.FileField: "string",
            models.ImageField: "string",
        }
        
        for field_class, ts_type in type_map.items():
            if isinstance(field, field_class):
                return ts_type
        
        # Handle foreign keys
        if isinstance(field, (models.ForeignKey, models.OneToOneField)):
            return "number | string"  # Usually the ID
        
        # Handle many-to-many (shouldn't appear in model._meta.fields)
        if isinstance(field, models.ManyToManyField):
            return "(number | string)[]"
        
        return "any"


def generate_typescript(
    schemas: List[Type[BaseModel]] = None,
    models: List[type] = None,
    output_path: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Convenience function to generate TypeScript code.
    
    Args:
        schemas: List of Pydantic BaseModel classes
        models: List of Django model classes
        output_path: Optional path to write the output file
        **kwargs: Additional options passed to TypeScriptGenerator
    
    Returns:
        TypeScript code as string
    """
    generator = TypeScriptGenerator(**kwargs)
    
    code_parts = []
    
    if schemas:
        code_parts.append(generator.generate(schemas))
    
    if models:
        code_parts.append(generator.generate_from_django_models(models))
    
    code = "\n".join(code_parts)
    
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)
    
    return code


def pydantic_to_typescript(
    schema: Type[BaseModel],
    **kwargs,
) -> str:
    """
    Convert a single Pydantic schema to TypeScript interface.
    
    Args:
        schema: Pydantic BaseModel class
        **kwargs: Additional options passed to TypeScriptGenerator
    
    Returns:
        TypeScript interface code
    """
    generator = TypeScriptGenerator(**kwargs)
    return generator.generate([schema])


def django_model_to_typescript(
    model: type,
    include_fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None,
    **kwargs,
) -> str:
    """
    Convert a single Django model to TypeScript interface.
    
    Args:
        model: Django model class
        include_fields: List of fields to include
        exclude_fields: List of fields to exclude
        **kwargs: Additional options passed to TypeScriptGenerator
    
    Returns:
        TypeScript interface code
    """
    generator = TypeScriptGenerator(**kwargs)
    include_map = {model.__name__: include_fields} if include_fields else None
    exclude_map = {model.__name__: exclude_fields} if exclude_fields else None
    
    return generator.generate_from_django_models(
        [model],
        include_fields=include_map,
        exclude_fields=exclude_map,
    )
