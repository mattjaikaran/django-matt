"""
GraphQL client code generation for Django Matt.

Generates TypeScript types and API clients from GraphQL schemas.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import strawberry
    from strawberry import Schema
    from strawberry.printer import print_schema
    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False
    Schema = object


def _require_strawberry():
    """Raise an error if strawberry is not installed."""
    if not STRAWBERRY_AVAILABLE:
        raise ImportError(
            "strawberry-graphql is required for GraphQL code generation. "
            "Install it with: pip install strawberry-graphql[django]"
        )


class TypeScriptGenerator:
    """
    Generate TypeScript types from a GraphQL schema.

    Usage:
        generator = TypeScriptGenerator(schema)
        ts_code = generator.generate()

        # Or generate specific parts
        types = generator.generate_types()
        operations = generator.generate_operations()
        client = generator.generate_client()
    """

    # GraphQL to TypeScript type mapping
    TYPE_MAP = {
        "ID": "string",
        "String": "string",
        "Int": "number",
        "Float": "number",
        "Boolean": "boolean",
        "DateTime": "string",
        "Date": "string",
        "Time": "string",
        "UUID": "string",
        "JSON": "Record<string, any>",
        "Decimal": "number",
    }

    def __init__(
        self,
        schema: Schema,
        export_style: str = "named",
        use_enums: bool = True,
        add_typename: bool = True,
        nullable_style: str = "union",  # "union" or "optional"
    ):
        """
        Initialize the TypeScript generator.

        Args:
            schema: Strawberry GraphQL schema
            export_style: "named" for export interface, "default" for no export
            use_enums: Generate TypeScript enums for GraphQL enums
            add_typename: Add __typename field to types
            nullable_style: How to handle nullable types
        """
        _require_strawberry()
        self.schema = schema
        self.export_style = export_style
        self.use_enums = use_enums
        self.add_typename = add_typename
        self.nullable_style = nullable_style

        # Get SDL representation
        self.sdl = print_schema(schema)

    def generate(self) -> str:
        """
        Generate complete TypeScript code.

        Returns:
            TypeScript code as string
        """
        parts = [
            "// Auto-generated TypeScript types from GraphQL schema",
            "// Do not edit manually",
            "",
            "// Scalar types",
            "export type Scalars = {",
            "  ID: string;",
            "  String: string;",
            "  Boolean: boolean;",
            "  Int: number;",
            "  Float: number;",
            "  DateTime: string;",
            "  Date: string;",
            "  JSON: Record<string, any>;",
            "};",
            "",
        ]

        # Generate types
        parts.append(self.generate_types())
        parts.append("")

        # Generate input types
        parts.append(self.generate_input_types())
        parts.append("")

        # Generate enums
        if self.use_enums:
            parts.append(self.generate_enums())
            parts.append("")

        # Generate operations
        parts.append(self.generate_operations())

        return "\n".join(parts)

    def generate_types(self) -> str:
        """Generate TypeScript interfaces for GraphQL types."""
        lines = ["// Object Types"]

        # Parse types from SDL
        type_pattern = r'type\s+(\w+)\s*(?:implements\s+[\w\s&]+)?\s*\{([^}]+)\}'
        matches = re.findall(type_pattern, self.sdl)

        for type_name, fields_str in matches:
            # Skip built-in types
            if type_name.startswith("__"):
                continue
            if type_name in ("Query", "Mutation", "Subscription"):
                continue

            export = "export " if self.export_style == "named" else ""
            lines.append(f"{export}interface {type_name} {{")

            if self.add_typename:
                lines.append(f'  __typename?: "{type_name}";')

            # Parse fields
            fields = self._parse_fields(fields_str)
            for field_name, field_type in fields.items():
                ts_type = self._graphql_to_typescript(field_type)
                lines.append(f"  {field_name}: {ts_type};")

            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def generate_input_types(self) -> str:
        """Generate TypeScript interfaces for GraphQL input types."""
        lines = ["// Input Types"]

        # Parse input types from SDL
        input_pattern = r'input\s+(\w+)\s*\{([^}]+)\}'
        matches = re.findall(input_pattern, self.sdl)

        for type_name, fields_str in matches:
            export = "export " if self.export_style == "named" else ""
            lines.append(f"{export}interface {type_name} {{")

            # Parse fields
            fields = self._parse_fields(fields_str)
            for field_name, field_type in fields.items():
                ts_type = self._graphql_to_typescript(field_type)
                # Input fields can be optional
                optional = "?" if "!" not in field_type else ""
                lines.append(f"  {field_name}{optional}: {ts_type};")

            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def generate_enums(self) -> str:
        """Generate TypeScript enums from GraphQL enums."""
        lines = ["// Enums"]

        # Parse enums from SDL
        enum_pattern = r'enum\s+(\w+)\s*\{([^}]+)\}'
        matches = re.findall(enum_pattern, self.sdl)

        for enum_name, values_str in matches:
            export = "export " if self.export_style == "named" else ""

            if self.use_enums:
                lines.append(f"{export}enum {enum_name} {{")
                values = [v.strip() for v in values_str.split() if v.strip()]
                for value in values:
                    lines.append(f'  {value} = "{value}",')
                lines.append("}")
            else:
                # Use union type instead
                values = [v.strip() for v in values_str.split() if v.strip()]
                union_values = " | ".join(f'"{v}"' for v in values)
                lines.append(f"{export}type {enum_name} = {union_values};")

            lines.append("")

        return "\n".join(lines)

    def generate_operations(self) -> str:
        """Generate TypeScript types for queries, mutations, and subscriptions."""
        lines = ["// Operations"]

        # Parse Query type
        query_pattern = r'type\s+Query\s*\{([^}]+)\}'
        query_match = re.search(query_pattern, self.sdl)

        if query_match:
            lines.append("export interface QueryOperations {")
            fields = self._parse_fields(query_match.group(1))
            for field_name, field_type in fields.items():
                ts_type = self._graphql_to_typescript(field_type)
                lines.append(f"  {field_name}: {ts_type};")
            lines.append("}")
            lines.append("")

        # Parse Mutation type
        mutation_pattern = r'type\s+Mutation\s*\{([^}]+)\}'
        mutation_match = re.search(mutation_pattern, self.sdl)

        if mutation_match:
            lines.append("export interface MutationOperations {")
            fields = self._parse_fields(mutation_match.group(1))
            for field_name, field_type in fields.items():
                ts_type = self._graphql_to_typescript(field_type)
                lines.append(f"  {field_name}: {ts_type};")
            lines.append("}")
            lines.append("")

        # Parse Subscription type
        subscription_pattern = r'type\s+Subscription\s*\{([^}]+)\}'
        subscription_match = re.search(subscription_pattern, self.sdl)

        if subscription_match:
            lines.append("export interface SubscriptionOperations {")
            fields = self._parse_fields(subscription_match.group(1))
            for field_name, field_type in fields.items():
                ts_type = self._graphql_to_typescript(field_type)
                lines.append(f"  {field_name}: {ts_type};")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def _parse_fields(self, fields_str: str) -> dict[str, str]:
        """Parse fields from a type definition."""
        fields = {}
        field_pattern = r'(\w+)(?:\([^)]*\))?\s*:\s*([^\n]+)'
        matches = re.findall(field_pattern, fields_str)

        for field_name, field_type in matches:
            fields[field_name] = field_type.strip()

        return fields

    def _graphql_to_typescript(self, graphql_type: str) -> str:
        """Convert a GraphQL type to TypeScript."""
        graphql_type = graphql_type.strip()

        # Handle non-null types
        is_required = graphql_type.endswith("!")
        if is_required:
            graphql_type = graphql_type[:-1]

        # Handle list types
        is_list = graphql_type.startswith("[") and graphql_type.endswith("]")
        if is_list:
            inner_type = graphql_type[1:-1]
            inner_required = inner_type.endswith("!")
            if inner_required:
                inner_type = inner_type[:-1]
            ts_inner = self._graphql_to_typescript(inner_type)
            if not inner_required and self.nullable_style == "union":
                ts_inner = f"({ts_inner} | null)"
            ts_type = f"{ts_inner}[]"
        else:
            # Scalar or custom type
            ts_type = self.TYPE_MAP.get(graphql_type, graphql_type)

        # Handle nullable
        if not is_required:
            if self.nullable_style == "union":
                ts_type = f"{ts_type} | null"
            # Optional style is handled at field level

        return ts_type


def generate_typescript_types(
    schema: Schema,
    output_path: str | None = None,
    **kwargs,
) -> str:
    """
    Generate TypeScript types from a GraphQL schema.

    Args:
        schema: Strawberry GraphQL schema
        output_path: Optional path to write output file
        **kwargs: Additional arguments for TypeScriptGenerator

    Returns:
        TypeScript code as string
    """
    _require_strawberry()
    generator = TypeScriptGenerator(schema, **kwargs)
    code = generator.generate()

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    return code


def generate_typescript_client(
    schema: Schema,
    output_path: str | None = None,
    client_name: str = "GraphQLClient",
    base_url: str = "/graphql",
) -> str:
    """
    Generate a TypeScript GraphQL client.

    Args:
        schema: Strawberry GraphQL schema
        output_path: Optional path to write output file
        client_name: Name for the client class
        base_url: Default GraphQL endpoint URL

    Returns:
        TypeScript code as string
    """
    _require_strawberry()

    # Generate types first
    type_generator = TypeScriptGenerator(schema)
    types_code = type_generator.generate()

    # Generate client code
    client_code = f'''
// GraphQL Client
// Auto-generated - do not edit manually

{types_code}

export interface GraphQLError {{
  message: string;
  locations?: {{ line: number; column: number }}[];
  path?: (string | number)[];
  extensions?: Record<string, any>;
}}

export interface GraphQLResponse<T> {{
  data?: T;
  errors?: GraphQLError[];
}}

export interface {client_name}Options {{
  baseUrl?: string;
  headers?: Record<string, string>;
  credentials?: RequestCredentials;
}}

export class {client_name} {{
  private baseUrl: string;
  private headers: Record<string, string>;
  private credentials: RequestCredentials;

  constructor(options: {client_name}Options = {{}}) {{
    this.baseUrl = options.baseUrl || "{base_url}";
    this.headers = {{
      "Content-Type": "application/json",
      ...options.headers,
    }};
    this.credentials = options.credentials || "same-origin";
  }}

  setHeader(key: string, value: string): void {{
    this.headers[key] = value;
  }}

  setAuthToken(token: string): void {{
    this.headers["Authorization"] = `Bearer ${{token}}`;
  }}

  async query<T>(
    query: string,
    variables?: Record<string, any>,
    operationName?: string,
  ): Promise<GraphQLResponse<T>> {{
    const response = await fetch(this.baseUrl, {{
      method: "POST",
      headers: this.headers,
      credentials: this.credentials,
      body: JSON.stringify({{
        query,
        variables,
        operationName,
      }}),
    }});

    return response.json();
  }}

  async mutate<T>(
    mutation: string,
    variables?: Record<string, any>,
    operationName?: string,
  ): Promise<GraphQLResponse<T>> {{
    return this.query<T>(mutation, variables, operationName);
  }}
}}

// Default client instance
export const graphqlClient = new {client_name}();
'''

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(client_code)

    return client_code


def generate_graphql_operations(
    schema: Schema,
    output_path: str | None = None,
) -> str:
    """
    Generate GraphQL operation strings (queries, mutations, subscriptions).

    Args:
        schema: Strawberry GraphQL schema
        output_path: Optional path to write output file

    Returns:
        TypeScript code with GraphQL operation strings
    """
    _require_strawberry()

    sdl = print_schema(schema)
    lines = [
        "// GraphQL Operations",
        "// Auto-generated - do not edit manually",
        "",
    ]

    # Extract Query operations
    query_pattern = r'type\s+Query\s*\{([^}]+)\}'
    query_match = re.search(query_pattern, sdl)

    if query_match:
        lines.append("// Queries")
        fields_str = query_match.group(1)
        field_pattern = r'(\w+)(?:\(([^)]*)\))?\s*:\s*([^\n]+)'
        matches = re.findall(field_pattern, fields_str)

        for field_name, args_str, return_type in matches:
            # Generate query string
            operation_name = _to_pascal_case(field_name)

            if args_str:
                # Parse arguments
                arg_pattern = r'(\w+)\s*:\s*(\S+)'
                args = re.findall(arg_pattern, args_str)
                variables = ", ".join(f"${name}: {atype}" for name, atype in args)
                field_args = ", ".join(f"{name}: ${name}" for name, _ in args)
                query = f"""
export const {operation_name}Query = `
  query {operation_name}({variables}) {{
    {field_name}({field_args}) {{
      ...{_get_type_name(return_type)}Fields
    }}
  }}
`;
"""
            else:
                query = f"""
export const {operation_name}Query = `
  query {operation_name} {{
    {field_name} {{
      ...{_get_type_name(return_type)}Fields
    }}
  }}
`;
"""
            lines.append(query)

    # Extract Mutation operations
    mutation_pattern = r'type\s+Mutation\s*\{([^}]+)\}'
    mutation_match = re.search(mutation_pattern, sdl)

    if mutation_match:
        lines.append("// Mutations")
        fields_str = mutation_match.group(1)
        field_pattern = r'(\w+)(?:\(([^)]*)\))?\s*:\s*([^\n]+)'
        matches = re.findall(field_pattern, fields_str)

        for field_name, args_str, return_type in matches:
            operation_name = _to_pascal_case(field_name)

            if args_str:
                arg_pattern = r'(\w+)\s*:\s*(\S+)'
                args = re.findall(arg_pattern, args_str)
                variables = ", ".join(f"${name}: {atype}" for name, atype in args)
                field_args = ", ".join(f"{name}: ${name}" for name, _ in args)
                mutation = f"""
export const {operation_name}Mutation = `
  mutation {operation_name}({variables}) {{
    {field_name}({field_args}) {{
      ...{_get_type_name(return_type)}Fields
    }}
  }}
`;
"""
            else:
                mutation = f"""
export const {operation_name}Mutation = `
  mutation {operation_name} {{
    {field_name} {{
      ...{_get_type_name(return_type)}Fields
    }}
  }}
`;
"""
            lines.append(mutation)

    code = "\n".join(lines)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    return code


def _to_pascal_case(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in name.split("_"))


def _get_type_name(type_str: str) -> str:
    """Extract the base type name from a GraphQL type string."""
    # Remove non-null indicator and list brackets
    type_str = type_str.replace("!", "").replace("[", "").replace("]", "").strip()
    return type_str


__all__ = [
    "TypeScriptGenerator",
    "generate_typescript_types",
    "generate_typescript_client",
    "generate_graphql_operations",
]
