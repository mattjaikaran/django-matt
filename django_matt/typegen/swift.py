# file-length-max: 600
"""
Swift code generation from Pydantic schemas.
"""

import datetime
import decimal
import inspect
import uuid
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

# Python type to Swift type mapping
PYTHON_TO_SWIFT: dict[type, str] = {
    str: "String",
    int: "Int",
    float: "Double",
    bool: "Bool",
    bytes: "Data",
    type(None): "nil",
    None: "nil",
    Any: "Any",
    datetime.datetime: "Date",
    datetime.date: "Date",
    datetime.time: "Date",
    datetime.timedelta: "TimeInterval",
    decimal.Decimal: "Decimal",
    uuid.UUID: "UUID",
    dict: "[String: Any]",
    list: "[Any]",
    set: "[Any]",
}


def python_type_to_swift(
    python_type: type,
    schema_names: set[str] | None = None,
) -> str:
    """
    Convert a Python type to its Swift equivalent.

    Args:
        python_type: The Python type to convert
        schema_names: Set of known schema names (for references)

    Returns:
        Swift type string
    """
    schema_names = schema_names or set()

    # Handle None type
    if python_type is None or python_type is type(None):
        return "nil"

    # Handle basic types
    if python_type in PYTHON_TO_SWIFT:
        return PYTHON_TO_SWIFT[python_type]

    # Handle Pydantic models
    if inspect.isclass(python_type) and issubclass(python_type, BaseModel):
        return python_type.__name__

    # Handle Enums
    from enum import Enum

    if inspect.isclass(python_type) and issubclass(python_type, Enum):
        return python_type.__name__

    # Handle generic types
    origin = get_origin(python_type)
    if origin is not None:
        args = get_args(python_type)

        # Literal types → String for string literals, Int for int literals
        if origin is Literal:
            if all(isinstance(v, str) for v in args):
                return "String"
            if all(isinstance(v, int) and not isinstance(v, bool) for v in args):
                return "Int"
            return "String"

        # Union types (including Optional)
        if origin is Union:
            non_none_args = [a for a in args if a is not type(None)]
            if len(args) == 2 and type(None) in args:
                # Optional type
                inner_type = python_type_to_swift(non_none_args[0], schema_names)
                return f"{inner_type}?"

            # Swift doesn't have union types, use Any
            return "Any"

        # List types
        if origin is list or origin is list:
            if args:
                inner_type = python_type_to_swift(args[0], schema_names)
                return f"[{inner_type}]"
            return "[Any]"

        # Dict types
        if origin is dict or origin is dict:
            if args and len(args) == 2:
                key_type = python_type_to_swift(args[0], schema_names)
                value_type = python_type_to_swift(args[1], schema_names)
                return f"[{key_type}: {value_type}]"
            return "[String: Any]"

        # Set types
        if origin is set or origin is set:
            if args:
                inner_type = python_type_to_swift(args[0], schema_names)
                return f"Set<{inner_type}>"
            return "Set<Any>"

    # Check if it's a known schema name
    if hasattr(python_type, "__name__") and python_type.__name__ in schema_names:
        return python_type.__name__

    # Default to Any
    return "Any"


class SwiftGenerator:
    """
    Generate Swift Codable structs from Pydantic schemas.

    Example:
        generator = SwiftGenerator()
        swift_code = generator.generate([UserSchema, PostSchema])

        # With options
        generator = SwiftGenerator(
            use_class=False,     # Use struct (default) or class
            add_codable=True,    # Add Codable conformance
            add_equatable=True,  # Add Equatable conformance
            add_hashable=False,  # Add Hashable conformance
        )
    """

    def __init__(
        self,
        use_class: bool = False,
        add_codable: bool = True,
        add_equatable: bool = True,
        add_hashable: bool = False,
        add_identifiable: bool = True,
        use_coding_keys: bool = True,
    ):
        """
        Initialize Swift generator.

        Args:
            use_class: Use `class` instead of `struct`
            add_codable: Add Codable protocol conformance
            add_equatable: Add Equatable protocol conformance
            add_hashable: Add Hashable protocol conformance
            add_identifiable: Add Identifiable protocol if id field exists
            use_coding_keys: Generate CodingKeys enum for snake_case conversion
        """
        self.use_class = use_class
        self.add_codable = add_codable
        self.add_equatable = add_equatable
        self.add_hashable = add_hashable
        self.add_identifiable = add_identifiable
        self.use_coding_keys = use_coding_keys

        self._generated: set[str] = set()
        self._schema_names: set[str] = set()

    def generate(
        self,
        schemas: list[type[BaseModel]],
        header: str | None = None,
    ) -> str:
        """
        Generate Swift code from Pydantic schemas.

        Args:
            schemas: List of Pydantic BaseModel classes
            header: Optional header comment

        Returns:
            Swift code as string
        """
        self._generated.clear()
        self._schema_names = {s.__name__ for s in schemas}

        lines = []

        # Add header
        if header:
            lines.append(f"// {header}")
        else:
            lines.append("// Auto-generated Swift types from Pydantic schemas")
            lines.append("// Do not edit manually - regenerate with sync_types command")
        lines.append("")

        # Import Foundation
        lines.append("import Foundation")
        lines.append("")

        # Generate structs/classes for each schema
        for schema in schemas:
            if schema.__name__ not in self._generated:
                struct_code = self._generate_struct(schema)
                lines.append(struct_code)
                lines.append("")

        return "\n".join(lines)

    def _generate_struct(self, schema: type[BaseModel]) -> str:
        """Generate Swift struct/class for a single schema."""
        self._generated.add(schema.__name__)

        name = schema.__name__

        lines = []

        # Add doc comment
        doc = schema.__doc__
        if doc:
            lines.append("/**")
            for line in doc.strip().split("\n"):
                lines.append(f" * {line.strip()}")
            lines.append(" */")

        # Build protocols
        protocols = []
        if self.add_codable:
            protocols.append("Codable")
        if self.add_equatable:
            protocols.append("Equatable")
        if self.add_hashable:
            protocols.append("Hashable")

        # Check for id field for Identifiable
        has_id = "id" in schema.model_fields
        if self.add_identifiable and has_id:
            protocols.append("Identifiable")

        # Struct/class declaration
        keyword = "class" if self.use_class else "struct"
        protocol_str = f": {', '.join(protocols)}" if protocols else ""

        lines.append(f"public {keyword} {name}{protocol_str} {{")

        # Generate properties
        fields_info = []
        for field_name, field_info in schema.model_fields.items():
            swift_name, swift_type, is_optional = self._generate_property(
                field_name, field_info, schema
            )
            fields_info.append((field_name, swift_name, swift_type, is_optional))

            # Add property doc if available
            if field_info.description:
                lines.append(f"    /// {field_info.description}")

            lines.append(f"    public let {swift_name}: {swift_type}")

        # Add CodingKeys if needed
        needs_coding_keys = self.use_coding_keys and self.add_codable
        has_snake_case = any("_" in field_name for field_name, _, _, _ in fields_info)

        if needs_coding_keys and has_snake_case:
            lines.append("")
            lines.append("    enum CodingKeys: String, CodingKey {")
            for field_name, swift_name, _, _ in fields_info:
                if "_" in field_name:
                    lines.append(f'        case {swift_name} = "{field_name}"')
                else:
                    lines.append(f"        case {swift_name}")
            lines.append("    }")

        # Add initializer for class
        if self.use_class:
            lines.append("")
            params = ", ".join(
                f"{name}: {swift_type}" + ("" if not is_optional else " = nil")
                for _, name, swift_type, is_optional in fields_info
            )
            lines.append(f"    public init({params}) {{")
            for _, swift_name, _, _ in fields_info:
                lines.append(f"        self.{swift_name} = {swift_name}")
            lines.append("    }")

        lines.append("}")

        return "\n".join(lines)

    def _generate_property(
        self,
        field_name: str,
        field_info: FieldInfo,
        schema: type[BaseModel],
    ) -> tuple:
        """Generate Swift property declaration."""
        # Get field type from annotation
        annotations = schema.__annotations__
        python_type = annotations.get(field_name, Any)

        # Convert to Swift type
        swift_type = python_type_to_swift(python_type, self._schema_names)

        # Convert snake_case to camelCase
        swift_name = self._snake_to_camel(field_name)

        # Check if optional
        is_optional = not field_info.is_required()

        # Handle optional wrapping
        if is_optional and not swift_type.endswith("?"):
            swift_type = f"{swift_type}?"

        return swift_name, swift_type, is_optional

    def _snake_to_camel(self, name: str) -> str:
        """Convert snake_case to camelCase."""
        components = name.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    def generate_api_client(
        self,
        base_url: str = "",
        schemas: list[type[BaseModel]] | None = None,
    ) -> str:
        """
        Generate Swift API client using URLSession.

        Args:
            base_url: Base URL for API requests
            schemas: List of schemas (optional, for type imports)

        Returns:
            Swift API client code
        """
        lines = [
            "// Auto-generated Swift API Client",
            "// Do not edit manually - regenerate with sync_types command",
            "",
            "import Foundation",
            "",
            "/// HTTP method enumeration",
            "public enum HTTPMethod: String {",
            '    case get = "GET"',
            '    case post = "POST"',
            '    case put = "PUT"',
            '    case patch = "PATCH"',
            '    case delete = "DELETE"',
            "}",
            "",
            "/// API error types",
            "public enum APIError: Error {",
            "    case invalidURL",
            "    case noData",
            "    case decodingError(Error)",
            "    case networkError(Error)",
            "    case httpError(statusCode: Int, data: Data?)",
            "}",
            "",
            "/// Generic API response wrapper",
            "public struct APIResponse<T: Codable>: Codable {",
            "    public let data: T?",
            "    public let error: String?",
            "    public let message: String?",
            "}",
            "",
            "/// API Client for making network requests",
            "public class APIClient {",
            "    private let baseURL: String",
            "    private var headers: [String: String] = [:]",
            "    private let decoder: JSONDecoder",
            "    private let encoder: JSONEncoder",
            "",
            f'    public init(baseURL: String = "{base_url}") {{',
            "        self.baseURL = baseURL",
            "        ",
            "        self.decoder = JSONDecoder()",
            "        self.decoder.dateDecodingStrategy = .iso8601",
            "        self.decoder.keyDecodingStrategy = .convertFromSnakeCase",
            "        ",
            "        self.encoder = JSONEncoder()",
            "        self.encoder.dateEncodingStrategy = .iso8601",
            "        self.encoder.keyEncodingStrategy = .convertToSnakeCase",
            "    }",
            "",
            "    /// Set authorization header",
            "    public func setAuthToken(_ token: String) {",
            '        headers["Authorization"] = "Bearer \\(token)"',
            "    }",
            "",
            "    /// Clear authorization header",
            "    public func clearAuthToken() {",
            '        headers.removeValue(forKey: "Authorization")',
            "    }",
            "",
            "    /// Add custom header",
            "    public func setHeader(_ key: String, value: String) {",
            "        headers[key] = value",
            "    }",
            "",
            "    /// Make a request and decode the response",
            "    public func request<T: Codable>(",
            "        _ method: HTTPMethod,",
            "        path: String,",
            "        body: Encodable? = nil,",
            "        queryParams: [String: String]? = nil",
            "    ) async throws -> T {",
            "        guard var urlComponents = URLComponents(string: baseURL + path) else {",
            "            throw APIError.invalidURL",
            "        }",
            "",
            "        // Add query parameters",
            "        if let params = queryParams {",
            "            urlComponents.queryItems = params.map { URLQueryItem(name: $0.key, value: $0.value) }",
            "        }",
            "",
            "        guard let url = urlComponents.url else {",
            "            throw APIError.invalidURL",
            "        }",
            "",
            "        var request = URLRequest(url: url)",
            "        request.httpMethod = method.rawValue",
            '        request.setValue("application/json", forHTTPHeaderField: "Content-Type")',
            "",
            "        // Add headers",
            "        for (key, value) in headers {",
            "            request.setValue(value, forHTTPHeaderField: key)",
            "        }",
            "",
            "        // Add body",
            "        if let body = body {",
            "            request.httpBody = try encoder.encode(AnyEncodable(body))",
            "        }",
            "",
            "        // Make request",
            "        let (data, response): (Data, URLResponse)",
            "        do {",
            "            (data, response) = try await URLSession.shared.data(for: request)",
            "        } catch {",
            "            throw APIError.networkError(error)",
            "        }",
            "",
            "        // Check response",
            "        guard let httpResponse = response as? HTTPURLResponse else {",
            "            throw APIError.noData",
            "        }",
            "",
            "        guard 200...299 ~= httpResponse.statusCode else {",
            "            throw APIError.httpError(statusCode: httpResponse.statusCode, data: data)",
            "        }",
            "",
            "        // Decode response",
            "        do {",
            "            return try decoder.decode(T.self, from: data)",
            "        } catch {",
            "            throw APIError.decodingError(error)",
            "        }",
            "    }",
            "",
            "    /// GET request",
            "    public func get<T: Codable>(",
            "        _ path: String,",
            "        queryParams: [String: String]? = nil",
            "    ) async throws -> T {",
            "        try await request(.get, path: path, queryParams: queryParams)",
            "    }",
            "",
            "    /// POST request",
            "    public func post<T: Codable, B: Encodable>(",
            "        _ path: String,",
            "        body: B",
            "    ) async throws -> T {",
            "        try await request(.post, path: path, body: body)",
            "    }",
            "",
            "    /// PUT request",
            "    public func put<T: Codable, B: Encodable>(",
            "        _ path: String,",
            "        body: B",
            "    ) async throws -> T {",
            "        try await request(.put, path: path, body: body)",
            "    }",
            "",
            "    /// PATCH request",
            "    public func patch<T: Codable, B: Encodable>(",
            "        _ path: String,",
            "        body: B",
            "    ) async throws -> T {",
            "        try await request(.patch, path: path, body: body)",
            "    }",
            "",
            "    /// DELETE request",
            "    public func delete<T: Codable>(",
            "        _ path: String",
            "    ) async throws -> T {",
            "        try await request(.delete, path: path)",
            "    }",
            "}",
            "",
            "/// Type-erased Encodable wrapper",
            "private struct AnyEncodable: Encodable {",
            "    private let _encode: (Encoder) throws -> Void",
            "",
            "    init<T: Encodable>(_ wrapped: T) {",
            "        _encode = wrapped.encode",
            "    }",
            "",
            "    func encode(to encoder: Encoder) throws {",
            "        try _encode(encoder)",
            "    }",
            "}",
        ]

        return "\n".join(lines)


def generate_swift(
    schemas: list[type[BaseModel]],
    output_path: str | None = None,
    **kwargs,
) -> str:
    """
    Convenience function to generate Swift code.

    Args:
        schemas: List of Pydantic BaseModel classes
        output_path: Optional path to write the output file
        **kwargs: Additional options passed to SwiftGenerator

    Returns:
        Swift code as string
    """
    generator = SwiftGenerator(**kwargs)
    code = generator.generate(schemas)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    return code


def pydantic_to_swift(
    schema: type[BaseModel],
    **kwargs,
) -> str:
    """
    Convert a single Pydantic schema to Swift struct.

    Args:
        schema: Pydantic BaseModel class
        **kwargs: Additional options passed to SwiftGenerator

    Returns:
        Swift struct code
    """
    generator = SwiftGenerator(**kwargs)
    return generator.generate([schema])
