"""
Typed API client generation from OpenAPI schema or controllers.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from django_matt.typegen.utils import snake_to_camel


class APIClientGenerator:
    """
    Generate typed API clients from OpenAPI schema or controller definitions.
    
    Example:
        generator = APIClientGenerator(base_url="/api")
        
        # From OpenAPI schema
        client_code = generator.generate_from_openapi(openapi_schema)
        
        # From controllers
        from myapp.controllers import UserController, PostController
        client_code = generator.generate_from_controllers([UserController, PostController])
    """
    
    def __init__(
        self,
        base_url: str = "/api",
        use_fetch: bool = True,
        include_react_query: bool = False,
        include_swr: bool = False,
        camel_case: bool = True,
    ):
        """
        Initialize API client generator.
        
        Args:
            base_url: Base URL for API requests
            use_fetch: Use native fetch API (vs axios)
            include_react_query: Include React Query hooks
            include_swr: Include SWR hooks
            camel_case: Use camelCase for function names
        """
        self.base_url = base_url
        self.use_fetch = use_fetch
        self.include_react_query = include_react_query
        self.include_swr = include_swr
        self.camel_case = camel_case
    
    def generate_from_openapi(
        self,
        schema: Dict[str, Any],
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate API client from OpenAPI schema.
        
        Args:
            schema: OpenAPI schema dictionary
            output_path: Optional path to write the output file
        
        Returns:
            TypeScript API client code
        """
        lines = self._generate_header()
        
        # Generate types section
        lines.extend(self._generate_types_from_openapi(schema))
        
        # Generate client class
        lines.extend(self._generate_client_class_from_openapi(schema))
        
        # Generate React Query hooks if requested
        if self.include_react_query:
            lines.extend(self._generate_react_query_hooks(schema))
        
        # Generate SWR hooks if requested
        if self.include_swr:
            lines.extend(self._generate_swr_hooks(schema))
        
        code = "\n".join(lines)
        
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(code)
        
        return code
    
    def generate_from_controllers(
        self,
        controllers: List[type],
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate API client from controller classes.
        
        Args:
            controllers: List of controller classes
            output_path: Optional path to write the output file
        
        Returns:
            TypeScript API client code
        """
        lines = self._generate_header()
        
        # Collect schemas from controller methods
        schemas = self._collect_schemas_from_controllers(controllers)
        
        # Generate types
        from django_matt.typegen.typescript import TypeScriptGenerator
        ts_gen = TypeScriptGenerator()
        if schemas:
            lines.append(ts_gen.generate(schemas))
        
        # Generate client class
        lines.extend(self._generate_client_class_from_controllers(controllers))
        
        code = "\n".join(lines)
        
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(code)
        
        return code
    
    def _generate_header(self) -> List[str]:
        """Generate file header and imports."""
        lines = [
            "// Auto-generated API client",
            "// Do not edit manually - regenerate with sync_types command",
            "",
        ]
        
        if self.include_react_query:
            lines.append('import { useQuery, useMutation, UseQueryOptions, UseMutationOptions } from "@tanstack/react-query";')
        
        if self.include_swr:
            lines.append('import useSWR, { SWRConfiguration } from "swr";')
        
        lines.append("")
        
        return lines
    
    def _generate_types_from_openapi(self, schema: Dict[str, Any]) -> List[str]:
        """Generate TypeScript types from OpenAPI schema components."""
        lines = ["// Types", ""]
        
        components = schema.get("components", {})
        schemas_dict = components.get("schemas", {})
        
        for name, schema_def in schemas_dict.items():
            lines.extend(self._openapi_schema_to_typescript(name, schema_def))
            lines.append("")
        
        return lines
    
    def _openapi_schema_to_typescript(
        self,
        name: str,
        schema_def: Dict[str, Any],
    ) -> List[str]:
        """Convert an OpenAPI schema definition to TypeScript interface."""
        lines = []
        
        description = schema_def.get("description", "")
        if description:
            lines.append(f"/** {description} */")
        
        lines.append(f"export interface {name} {{")
        
        properties = schema_def.get("properties", {})
        required = set(schema_def.get("required", []))
        
        for prop_name, prop_def in properties.items():
            ts_type = self._openapi_type_to_typescript(prop_def)
            optional = "?" if prop_name not in required else ""
            output_name = snake_to_camel(prop_name) if self.camel_case else prop_name
            
            prop_desc = prop_def.get("description", "")
            if prop_desc:
                lines.append(f"  /** {prop_desc} */")
            
            lines.append(f"  {output_name}{optional}: {ts_type};")
        
        lines.append("}")
        
        return lines
    
    def _openapi_type_to_typescript(self, schema_def: Dict[str, Any]) -> str:
        """Convert OpenAPI type to TypeScript type."""
        # Handle $ref
        if "$ref" in schema_def:
            ref = schema_def["$ref"]
            # Extract type name from #/components/schemas/TypeName
            return ref.split("/")[-1]
        
        schema_type = schema_def.get("type", "any")
        
        # Handle arrays
        if schema_type == "array":
            items = schema_def.get("items", {})
            item_type = self._openapi_type_to_typescript(items)
            return f"{item_type}[]"
        
        # Handle objects
        if schema_type == "object":
            additional = schema_def.get("additionalProperties", {})
            if additional:
                value_type = self._openapi_type_to_typescript(additional)
                return f"Record<string, {value_type}>"
            return "Record<string, any>"
        
        # Handle enums
        if "enum" in schema_def:
            values = schema_def["enum"]
            return " | ".join(
                f'"{v}"' if isinstance(v, str) else str(v)
                for v in values
            )
        
        # Handle union types (oneOf, anyOf)
        if "oneOf" in schema_def:
            types = [self._openapi_type_to_typescript(s) for s in schema_def["oneOf"]]
            return " | ".join(types)
        
        if "anyOf" in schema_def:
            types = [self._openapi_type_to_typescript(s) for s in schema_def["anyOf"]]
            return " | ".join(types)
        
        # Basic type mapping
        type_map = {
            "string": "string",
            "integer": "number",
            "number": "number",
            "boolean": "boolean",
            "null": "null",
        }
        
        return type_map.get(schema_type, "any")
    
    def _generate_client_class_from_openapi(
        self,
        schema: Dict[str, Any],
    ) -> List[str]:
        """Generate API client class from OpenAPI schema."""
        lines = [
            "// API Client",
            "",
            "export interface ApiClientConfig {",
            "  baseUrl?: string;",
            "  headers?: Record<string, string>;",
            "  onError?: (error: Error) => void;",
            "}",
            "",
            "export class ApiClient {",
            "  private baseUrl: string;",
            "  private headers: Record<string, string>;",
            "  private onError?: (error: Error) => void;",
            "",
            "  constructor(config: ApiClientConfig = {}) {",
            f'    this.baseUrl = config.baseUrl ?? "{self.base_url}";',
            "    this.headers = config.headers ?? {};",
            "    this.onError = config.onError;",
            "  }",
            "",
        ]
        
        # Add fetch helper
        lines.extend(self._generate_fetch_helper())
        
        # Generate methods for each path
        paths = schema.get("paths", {})
        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete"]:
                if method in path_item:
                    operation = path_item[method]
                    lines.extend(self._generate_method(path, method, operation))
        
        lines.append("}")
        lines.append("")
        
        # Export default instance
        lines.append("export const api = new ApiClient();")
        lines.append("")
        
        return lines
    
    def _generate_fetch_helper(self) -> List[str]:
        """Generate the fetch helper method."""
        return [
            "  private async request<T>(",
            "    method: string,",
            "    path: string,",
            "    options: {",
            "      body?: any;",
            "      params?: Record<string, any>;",
            "      headers?: Record<string, string>;",
            "    } = {}",
            "  ): Promise<T> {",
            "    const url = new URL(path, this.baseUrl);",
            "",
            "    if (options.params) {",
            "      Object.entries(options.params).forEach(([key, value]) => {",
            "        if (value !== undefined && value !== null) {",
            "          url.searchParams.append(key, String(value));",
            "        }",
            "      });",
            "    }",
            "",
            "    const response = await fetch(url.toString(), {",
            "      method,",
            '      headers: {',
            '        "Content-Type": "application/json",',
            "        ...this.headers,",
            "        ...options.headers,",
            "      },",
            "      body: options.body ? JSON.stringify(options.body) : undefined,",
            "    });",
            "",
            "    if (!response.ok) {",
            "      const error = new Error(`HTTP ${response.status}: ${response.statusText}`);",
            "      if (this.onError) {",
            "        this.onError(error);",
            "      }",
            "      throw error;",
            "    }",
            "",
            "    return response.json();",
            "  }",
            "",
        ]
    
    def _generate_method(
        self,
        path: str,
        method: str,
        operation: Dict[str, Any],
    ) -> List[str]:
        """Generate a client method for an API operation."""
        lines = []
        
        operation_id = operation.get("operationId", f"{method}_{path.replace('/', '_')}")
        method_name = snake_to_camel(operation_id) if self.camel_case else operation_id
        
        # Build parameters
        params = []
        path_params = []
        query_params = []
        
        for param in operation.get("parameters", []):
            param_name = param["name"]
            param_type = self._openapi_type_to_typescript(param.get("schema", {"type": "string"}))
            required = param.get("required", False)
            optional = "?" if not required else ""
            
            param_str = f"{param_name}{optional}: {param_type}"
            params.append(param_str)
            
            if param["in"] == "path":
                path_params.append(param_name)
            elif param["in"] == "query":
                query_params.append(param_name)
        
        # Request body
        request_body = operation.get("requestBody", {})
        body_type = None
        if request_body:
            content = request_body.get("content", {})
            json_content = content.get("application/json", {})
            body_schema = json_content.get("schema", {})
            body_type = self._openapi_type_to_typescript(body_schema)
            params.append(f"body: {body_type}")
        
        # Response type
        responses = operation.get("responses", {})
        success_response = responses.get("200", responses.get("201", {}))
        response_content = success_response.get("content", {})
        json_response = response_content.get("application/json", {})
        response_schema = json_response.get("schema", {})
        response_type = self._openapi_type_to_typescript(response_schema) if response_schema else "void"
        
        # JSDoc
        summary = operation.get("summary", "")
        description = operation.get("description", "")
        if summary or description:
            lines.append("  /**")
            if summary:
                lines.append(f"   * {summary}")
            if description and description != summary:
                lines.append(f"   * {description}")
            lines.append("   */")
        
        # Method signature
        params_str = ", ".join(params) if params else ""
        lines.append(f"  async {method_name}({params_str}): Promise<{response_type}> {{")
        
        # Build URL with path params
        url_path = path
        for param in path_params:
            url_path = url_path.replace(f"{{{param}}}", f"${{{param}}}")
        
        lines.append(f"    const path = `{url_path}`;")
        
        # Build options
        options_parts = []
        if body_type:
            options_parts.append("body")
        if query_params:
            query_obj = ", ".join(query_params)
            options_parts.append(f"params: {{ {query_obj} }}")
        
        options_str = f"{{ {', '.join(options_parts)} }}" if options_parts else "{}"
        
        lines.append(f'    return this.request<{response_type}>("{method.upper()}", path, {options_str});')
        lines.append("  }")
        lines.append("")
        
        return lines
    
    def _generate_client_class_from_controllers(
        self,
        controllers: List[type],
    ) -> List[str]:
        """Generate API client class from controller classes."""
        lines = [
            "// API Client",
            "",
            "export interface ApiClientConfig {",
            "  baseUrl?: string;",
            "  headers?: Record<string, string>;",
            "  onError?: (error: Error) => void;",
            "}",
            "",
            "export class ApiClient {",
            "  private baseUrl: string;",
            "  private headers: Record<string, string>;",
            "  private onError?: (error: Error) => void;",
            "",
            "  constructor(config: ApiClientConfig = {}) {",
            f'    this.baseUrl = config.baseUrl ?? "{self.base_url}";',
            "    this.headers = config.headers ?? {};",
            "    this.onError = config.onError;",
            "  }",
            "",
        ]
        
        # Add fetch helper
        lines.extend(self._generate_fetch_helper())
        
        # Generate methods for each controller
        for controller in controllers:
            prefix = getattr(controller, "prefix", "")
            
            for method_name in dir(controller):
                if method_name.startswith("_"):
                    continue
                
                method = getattr(controller, method_name)
                if callable(method) and hasattr(method, "_route_info"):
                    route_info = method._route_info
                    lines.extend(self._generate_method_from_controller(
                        prefix,
                        method_name,
                        method,
                        route_info,
                    ))
        
        lines.append("}")
        lines.append("")
        lines.append("export const api = new ApiClient();")
        lines.append("")
        
        return lines
    
    def _generate_method_from_controller(
        self,
        prefix: str,
        method_name: str,
        method: callable,
        route_info: dict,
    ) -> List[str]:
        """Generate client method from controller method."""
        lines = []
        
        http_method = route_info.get("method", "GET")
        path = route_info.get("path", method_name)
        full_path = f"/{prefix}/{path}".replace("//", "/")
        
        # Get type hints
        import inspect
        from typing import get_type_hints
        
        try:
            hints = get_type_hints(method)
        except Exception:
            hints = {}
        
        params = []
        body_type = None
        
        # Get parameters from signature
        sig = inspect.signature(method)
        for param_name, param in sig.parameters.items():
            if param_name in ["self", "request"]:
                continue
            
            param_type = hints.get(param_name, Any)
            
            # Check if it's a body parameter (Pydantic model)
            if hasattr(param_type, "__mro__") and BaseModel in param_type.__mro__:
                body_type = param_type.__name__
                params.append(f"body: {body_type}")
            else:
                ts_type = self._python_type_to_ts(param_type)
                params.append(f"{param_name}: {ts_type}")
        
        # Response type
        return_type = hints.get("return", Any)
        response_type = self._python_type_to_ts(return_type)
        
        output_method_name = snake_to_camel(method_name) if self.camel_case else method_name
        params_str = ", ".join(params) if params else ""
        
        lines.append(f"  async {output_method_name}({params_str}): Promise<{response_type}> {{")
        
        options = "{ body }" if body_type else "{}"
        lines.append(f'    return this.request<{response_type}>("{http_method}", "{full_path}", {options});')
        
        lines.append("  }")
        lines.append("")
        
        return lines
    
    def _python_type_to_ts(self, python_type: type) -> str:
        """Quick conversion of Python type to TypeScript."""
        from django_matt.typegen.utils import python_type_to_typescript
        return python_type_to_typescript(python_type)
    
    def _collect_schemas_from_controllers(
        self,
        controllers: List[type],
    ) -> List[Type[BaseModel]]:
        """Collect Pydantic schemas used in controller methods."""
        import inspect
        from typing import get_type_hints
        
        schemas = set()
        
        for controller in controllers:
            for method_name in dir(controller):
                if method_name.startswith("_"):
                    continue
                
                method = getattr(controller, method_name)
                if not callable(method):
                    continue
                
                try:
                    hints = get_type_hints(method)
                except Exception:
                    continue
                
                for hint_type in hints.values():
                    if hasattr(hint_type, "__mro__") and BaseModel in hint_type.__mro__:
                        schemas.add(hint_type)
        
        return list(schemas)
    
    def _generate_react_query_hooks(
        self,
        schema: Dict[str, Any],
    ) -> List[str]:
        """Generate React Query hooks."""
        lines = [
            "// React Query Hooks",
            "",
        ]
        
        paths = schema.get("paths", {})
        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete"]:
                if method in path_item:
                    operation = path_item[method]
                    lines.extend(self._generate_react_query_hook(path, method, operation))
        
        return lines
    
    def _generate_react_query_hook(
        self,
        path: str,
        method: str,
        operation: Dict[str, Any],
    ) -> List[str]:
        """Generate a React Query hook for an operation."""
        lines = []
        
        operation_id = operation.get("operationId", f"{method}_{path.replace('/', '_')}")
        method_name = snake_to_camel(operation_id) if self.camel_case else operation_id
        hook_name = f"use{method_name[0].upper()}{method_name[1:]}"
        
        # Response type
        responses = operation.get("responses", {})
        success_response = responses.get("200", responses.get("201", {}))
        response_content = success_response.get("content", {})
        json_response = response_content.get("application/json", {})
        response_schema = json_response.get("schema", {})
        response_type = self._openapi_type_to_typescript(response_schema) if response_schema else "any"
        
        if method == "get":
            lines.append(f"export function {hook_name}(")
            lines.append("  options?: UseQueryOptions<" + response_type + ">")
            lines.append(") {")
            lines.append("  return useQuery({")
            lines.append(f'    queryKey: ["{method_name}"],')
            lines.append(f"    queryFn: () => api.{method_name}(),")
            lines.append("    ...options,")
            lines.append("  });")
            lines.append("}")
        else:
            lines.append(f"export function {hook_name}(")
            lines.append("  options?: UseMutationOptions<" + response_type + ", Error, any>")
            lines.append(") {")
            lines.append("  return useMutation({")
            lines.append(f"    mutationFn: (data) => api.{method_name}(data),")
            lines.append("    ...options,")
            lines.append("  });")
            lines.append("}")
        
        lines.append("")
        
        return lines
    
    def _generate_swr_hooks(self, schema: Dict[str, Any]) -> List[str]:
        """Generate SWR hooks."""
        lines = [
            "// SWR Hooks",
            "",
        ]
        
        paths = schema.get("paths", {})
        for path, path_item in paths.items():
            if "get" in path_item:
                operation = path_item["get"]
                lines.extend(self._generate_swr_hook(path, operation))
        
        return lines
    
    def _generate_swr_hook(
        self,
        path: str,
        operation: Dict[str, Any],
    ) -> List[str]:
        """Generate an SWR hook for a GET operation."""
        lines = []
        
        operation_id = operation.get("operationId", f"get_{path.replace('/', '_')}")
        method_name = snake_to_camel(operation_id) if self.camel_case else operation_id
        hook_name = f"use{method_name[0].upper()}{method_name[1:]}"
        
        # Response type
        responses = operation.get("responses", {})
        success_response = responses.get("200", {})
        response_content = success_response.get("content", {})
        json_response = response_content.get("application/json", {})
        response_schema = json_response.get("schema", {})
        response_type = self._openapi_type_to_typescript(response_schema) if response_schema else "any"
        
        lines.append(f"export function {hook_name}(")
        lines.append("  config?: SWRConfiguration<" + response_type + ">")
        lines.append(") {")
        lines.append(f'  return useSWR<{response_type}>("{method_name}", () => api.{method_name}(), config);')
        lines.append("}")
        lines.append("")
        
        return lines


def generate_api_client(
    openapi_schema: Optional[Dict[str, Any]] = None,
    controllers: Optional[List[type]] = None,
    output_path: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Convenience function to generate API client.
    
    Args:
        openapi_schema: OpenAPI schema dictionary
        controllers: List of controller classes
        output_path: Optional path to write the output file
        **kwargs: Additional options passed to APIClientGenerator
    
    Returns:
        TypeScript API client code
    """
    generator = APIClientGenerator(**kwargs)
    
    if openapi_schema:
        return generator.generate_from_openapi(openapi_schema, output_path)
    elif controllers:
        return generator.generate_from_controllers(controllers, output_path)
    else:
        raise ValueError("Either openapi_schema or controllers must be provided")
