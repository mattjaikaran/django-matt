"""Tests for django_matt.sdkgen — SDK generation from OpenAPI schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from django_matt.sdkgen import (
    PythonSDKGenerator,
    SDKConfig,
    SDKGenerator,
    SDKOutput,
    SwiftSDKGenerator,
    TypeScriptSDKGenerator,
)
from django_matt.sdkgen.schema_parser import SchemaParser
from django_matt.sdkgen.template_engine import (
    openapi_type_to_python,
    openapi_type_to_swift,
    openapi_type_to_ts,
    to_camel_case,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_openapi_schema() -> dict[str, Any]:
    """A minimal but realistic OpenAPI 3.1 schema."""
    return {
        "openapi": "3.1.0",
        "info": {"title": "Pet Store", "version": "1.0.0", "description": "A pet store API"},
        "servers": [{"url": "https://api.petstore.io"}],
        "paths": {
            "/pets": {
                "get": {
                    "operationId": "list_pets",
                    "summary": "List all pets",
                    "tags": ["pets"],
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "status",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "enum": ["available", "sold"]},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "A list of pets",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/Pet"},
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {
                    "operationId": "create_pet",
                    "summary": "Create a pet",
                    "tags": ["pets"],
                    "x-auth-required": True,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PetCreate"},
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"},
                                }
                            },
                        }
                    },
                },
            },
            "/pets/{pet_id}": {
                "get": {
                    "operationId": "get_pet",
                    "summary": "Get a pet by ID",
                    "tags": ["pets"],
                    "parameters": [
                        {
                            "name": "pet_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "A pet",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"},
                                }
                            },
                        }
                    },
                },
                "delete": {
                    "operationId": "delete_pet",
                    "summary": "Delete a pet",
                    "tags": ["pets"],
                    "x-auth-required": True,
                    "parameters": [
                        {
                            "name": "pet_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "204": {"description": "Deleted"},
                    },
                },
            },
        },
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "description": "A pet in the store",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "name": {"type": "string"},
                        "status": {"type": "string", "enum": ["available", "sold"]},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "created_at": {"type": "string", "format": "date-time"},
                        "owner_id": {"type": "string", "format": "uuid", "nullable": True},
                    },
                    "required": ["id", "name", "status"],
                },
                "PetCreate": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "status": {"type": "string", "enum": ["available", "sold"]},
                    },
                    "required": ["name"],
                },
                "PetStatus": {
                    "type": "string",
                    "enum": ["available", "pending", "sold"],
                },
            },
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                },
            },
        },
    }


@pytest.fixture
def sdk_config(tmp_path: Path) -> SDKConfig:
    return SDKConfig(
        package_name="petstore-client",
        version="1.0.0",
        base_url="https://api.petstore.io",
        auth_type="jwt",
        output_dir=tmp_path / "sdk",
    )


# ---------------------------------------------------------------------------
# Schema Parser Tests
# ---------------------------------------------------------------------------

class TestSchemaParser:
    def test_parse_endpoints(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        api = parser.parse()
        assert len(api.endpoints) == 4  # list, create, get, delete

        op_ids = {ep.operation_id for ep in api.endpoints}
        assert "list_pets" in op_ids
        assert "create_pet" in op_ids
        assert "get_pet" in op_ids
        assert "delete_pet" in op_ids

    def test_parse_models(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        api = parser.parse()
        assert "Pet" in api.models
        assert "PetCreate" in api.models
        assert "PetStatus" in api.models

    def test_parse_enum_model(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        api = parser.parse()
        status = api.models["PetStatus"]
        assert status.enum_values == ["available", "pending", "sold"]

    def test_parse_model_properties(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        api = parser.parse()
        pet = api.models["Pet"]
        assert "id" in pet.properties
        assert "name" in pet.properties
        assert pet.required_fields == ["id", "name", "status"]

    def test_parse_path_params(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        api = parser.parse()
        get_pet = next(ep for ep in api.endpoints if ep.operation_id == "get_pet")
        path_params = [p for p in get_pet.parameters if p.location == "path"]
        assert len(path_params) == 1
        assert path_params[0].name == "pet_id"

    def test_parse_query_params(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        api = parser.parse()
        list_pets = next(ep for ep in api.endpoints if ep.operation_id == "list_pets")
        query_params = [p for p in list_pets.parameters if p.location == "query"]
        assert len(query_params) == 2

    def test_parse_request_body_ref(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        api = parser.parse()
        create_pet = next(ep for ep in api.endpoints if ep.operation_id == "create_pet")
        assert create_pet.request_body_ref == "PetCreate"

    def test_parse_response_ref(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        api = parser.parse()
        get_pet = next(ep for ep in api.endpoints if ep.operation_id == "get_pet")
        assert get_pet.response_ref == "Pet"

    def test_parse_auth_required(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        api = parser.parse()
        create_pet = next(ep for ep in api.endpoints if ep.operation_id == "create_pet")
        assert create_pet.auth_required is True

        list_pets = next(ep for ep in api.endpoints if ep.operation_id == "list_pets")
        assert list_pets.auth_required is False

    def test_parse_auth_schemes(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        api = parser.parse()
        assert "bearerAuth" in api.auth_schemes

    def test_resolve_ref(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        resolved = parser.resolve_ref({"$ref": "#/components/schemas/Pet"})
        assert resolved.get("type") == "object"
        assert "id" in resolved.get("properties", {})

    def test_ref_name(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        assert parser.ref_name({"$ref": "#/components/schemas/Pet"}) == "Pet"
        assert parser.ref_name({}) is None

    def test_parse_api_metadata(self, sample_openapi_schema: dict) -> None:
        parser = SchemaParser(sample_openapi_schema)
        api = parser.parse()
        assert api.title == "Pet Store"
        assert api.version == "1.0.0"
        assert api.base_url == "https://api.petstore.io"

    def test_allof_schema(self) -> None:
        schema: dict[str, Any] = {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Base": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"],
                    },
                    "Extended": {
                        "allOf": [
                            {"$ref": "#/components/schemas/Base"},
                            {
                                "type": "object",
                                "properties": {"extra": {"type": "string"}},
                            },
                        ],
                    },
                },
            },
        }
        parser = SchemaParser(schema)
        api = parser.parse()
        extended = api.models["Extended"]
        assert len(extended.all_of) == 2


# ---------------------------------------------------------------------------
# Naming Convention Tests
# ---------------------------------------------------------------------------

class TestNamingConventions:
    def test_to_camel_case(self) -> None:
        assert to_camel_case("list_pets") == "listPets"
        assert to_camel_case("get_pet_by_id") == "getPetById"
        assert to_camel_case("already") == "already"
        assert to_camel_case("kebab-case") == "kebabCase"

    def test_to_pascal_case(self) -> None:
        assert to_pascal_case("pet_create") == "PetCreate"
        assert to_pascal_case("user") == "User"
        assert to_pascal_case("my-api") == "MyApi"

    def test_to_snake_case(self) -> None:
        assert to_snake_case("listPets") == "list_pets"
        assert to_snake_case("PetCreate") == "pet_create"
        assert to_snake_case("HTTPResponse") == "http_response"

    def test_to_kebab_case(self) -> None:
        assert to_kebab_case("petStore") == "pet-store"
        assert to_kebab_case("MyAPI") == "my-api"


# ---------------------------------------------------------------------------
# Type Mapping Tests
# ---------------------------------------------------------------------------

class TestTypeMapping:
    def test_openapi_to_ts_string(self) -> None:
        assert openapi_type_to_ts({"type": "string"}) == "string"

    def test_openapi_to_ts_integer(self) -> None:
        assert openapi_type_to_ts({"type": "integer"}) == "number"

    def test_openapi_to_ts_boolean(self) -> None:
        assert openapi_type_to_ts({"type": "boolean"}) == "boolean"

    def test_openapi_to_ts_array(self) -> None:
        assert openapi_type_to_ts({"type": "array", "items": {"type": "string"}}) == "string[]"

    def test_openapi_to_ts_ref(self) -> None:
        assert openapi_type_to_ts({"$ref": "#/components/schemas/Pet"}) == "Pet"

    def test_openapi_to_ts_nullable(self) -> None:
        assert openapi_type_to_ts({"type": "string", "nullable": True}) == "string | null"

    def test_openapi_to_ts_enum(self) -> None:
        result = openapi_type_to_ts({"type": "string", "enum": ["a", "b"]})
        assert '"a"' in result
        assert '"b"' in result

    def test_openapi_to_python_string(self) -> None:
        assert openapi_type_to_python({"type": "string"}) == "str"

    def test_openapi_to_python_integer(self) -> None:
        assert openapi_type_to_python({"type": "integer"}) == "int"

    def test_openapi_to_python_array(self) -> None:
        assert openapi_type_to_python({"type": "array", "items": {"type": "string"}}) == "list[str]"

    def test_openapi_to_python_ref(self) -> None:
        assert openapi_type_to_python({"$ref": "#/components/schemas/Pet"}) == "Pet"

    def test_openapi_to_python_nullable(self) -> None:
        assert openapi_type_to_python({"type": "string", "nullable": True}) == "str | None"

    def test_openapi_to_swift_string(self) -> None:
        assert openapi_type_to_swift({"type": "string"}) == "String"

    def test_openapi_to_swift_integer(self) -> None:
        assert openapi_type_to_swift({"type": "integer"}) == "Int"

    def test_openapi_to_swift_array(self) -> None:
        assert openapi_type_to_swift({"type": "array", "items": {"type": "string"}}) == "[String]"

    def test_openapi_to_swift_nullable(self) -> None:
        assert openapi_type_to_swift({"type": "string", "nullable": True}) == "String?"

    def test_openapi_to_swift_ref(self) -> None:
        assert openapi_type_to_swift({"$ref": "#/components/schemas/Pet"}) == "Pet"

    def test_openapi_to_ts_datetime(self) -> None:
        assert openapi_type_to_ts({"type": "string", "format": "date-time"}) == "string"

    def test_openapi_to_python_datetime(self) -> None:
        assert openapi_type_to_python({"type": "string", "format": "date-time"}) == "datetime"

    def test_openapi_to_swift_uuid(self) -> None:
        assert openapi_type_to_swift({"type": "string", "format": "uuid"}) == "UUID"


# ---------------------------------------------------------------------------
# TypeScript Generator Tests
# ---------------------------------------------------------------------------

class TestTypeScriptGenerator:
    def test_generates_all_files(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        assert "src/client.ts" in output.files
        assert "src/models.ts" in output.files
        assert "src/errors.ts" in output.files
        assert "src/auth.ts" in output.files
        assert "src/index.ts" in output.files
        assert "package.json" in output.files
        assert "tsconfig.json" in output.files

    def test_models_contain_interfaces(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        models = output.files["src/models.ts"]
        assert "export interface Pet {" in models
        assert "export interface PetCreate {" in models

    def test_models_contain_enum_type(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        models = output.files["src/models.ts"]
        assert "PetStatus" in models
        assert '"available"' in models

    def test_client_has_endpoint_methods(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = output.files["src/client.ts"]
        assert "listPets" in client
        assert "createPet" in client
        assert "getPet" in client
        assert "deletePet" in client

    def test_client_has_pagination_helper(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = output.files["src/client.ts"]
        assert "paginate" in client
        assert "AsyncGenerator" in client

    def test_client_has_file_upload(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = output.files["src/client.ts"]
        assert "uploadFile" in client
        assert "FormData" in client

    def test_client_has_websocket(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = output.files["src/client.ts"]
        assert "createWebSocket" in client
        assert "WebSocket" in client

    def test_errors_file(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        errors = output.files["src/errors.ts"]
        assert "class APIError" in errors
        assert "class ValidationError" in errors
        assert "class AuthenticationError" in errors
        assert "class RateLimitError" in errors

    def test_auth_providers(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        auth = output.files["src/auth.ts"]
        assert "class JWTAuth" in auth
        assert "class APIKeyAuth" in auth
        assert "interface AuthProvider" in auth

    def test_package_json_valid(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        pkg = json.loads(output.files["package.json"])
        assert pkg["name"] == "petstore-client"
        assert pkg["version"] == "1.0.0"
        assert "typescript" in pkg.get("devDependencies", {})

    def test_tsconfig_strict(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        tsconfig = json.loads(output.files["tsconfig.json"])
        assert tsconfig["compilerOptions"]["strict"] is True

    def test_index_barrel_exports(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        index = output.files["src/index.ts"]
        assert "Client" in index
        assert "APIError" in index
        assert "JWTAuth" in index

    def test_client_has_retry(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = output.files["src/client.ts"]
        assert "maxRetries" in client
        assert "retryDelay" in client

    def test_client_has_interceptors(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = output.files["src/client.ts"]
        assert "RequestInterceptor" in client
        assert "ResponseInterceptor" in client

    def test_write_to_disk(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig, tmp_path: Path
    ) -> None:
        gen = TypeScriptSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        written = output.write_to_disk(tmp_path / "ts_sdk")
        assert len(written) == len(output.files)
        for path in written:
            assert path.exists()


# ---------------------------------------------------------------------------
# Python Generator Tests
# ---------------------------------------------------------------------------

class TestPythonGenerator:
    def test_generates_all_files(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        pkg = "petstore_client"
        assert f"{pkg}/client.py" in output.files
        assert f"{pkg}/models.py" in output.files
        assert f"{pkg}/errors.py" in output.files
        assert f"{pkg}/auth.py" in output.files
        assert f"{pkg}/__init__.py" in output.files
        assert "pyproject.toml" in output.files

    def test_models_contain_pydantic(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        models = output.files["petstore_client/models.py"]
        assert "from pydantic import BaseModel" in models
        assert "class Pet(BaseModel):" in models
        assert "class PetCreate(BaseModel):" in models

    def test_models_enum_generation(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        models = output.files["petstore_client/models.py"]
        assert "class PetStatus" in models
        assert "Enum" in models

    def test_client_sync_and_async(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = output.files["petstore_client/client.py"]
        assert "class Client:" in client
        assert "class AsyncClient:" in client

    def test_client_has_endpoint_methods(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = output.files["petstore_client/client.py"]
        assert "def list_pets" in client
        assert "def create_pet" in client
        assert "def get_pet" in client
        assert "async def list_pets" in client

    def test_client_file_upload(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = output.files["petstore_client/client.py"]
        assert "upload_file" in client

    def test_client_retry(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = output.files["petstore_client/client.py"]
        assert "max_retries" in client
        assert "retry_backoff" in client

    def test_errors_file(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        errors = output.files["petstore_client/errors.py"]
        assert "class APIError" in errors
        assert "class ValidationError" in errors
        assert "class AuthenticationError" in errors
        assert "class RateLimitError" in errors

    def test_auth_providers(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        auth = output.files["petstore_client/auth.py"]
        assert "class JWTAuth" in auth
        assert "class APIKeyAuth" in auth

    def test_pyproject_toml(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        pyproject = output.files["pyproject.toml"]
        assert "petstore-client" in pyproject
        assert "httpx" in pyproject
        assert "pydantic" in pyproject

    def test_init_exports(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        init = output.files["petstore_client/__init__.py"]
        assert "Client" in init
        assert "AsyncClient" in init
        assert "JWTAuth" in init

    def test_write_to_disk(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig, tmp_path: Path
    ) -> None:
        gen = PythonSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        written = output.write_to_disk(tmp_path / "py_sdk")
        assert len(written) == len(output.files)
        for path in written:
            assert path.exists()


# ---------------------------------------------------------------------------
# Swift Generator Tests
# ---------------------------------------------------------------------------

class TestSwiftGenerator:
    def test_generates_all_files(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = SwiftSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        assert any("Models.swift" in k for k in output.files)
        assert any("Client.swift" in k for k in output.files)
        assert any("Auth.swift" in k for k in output.files)
        assert any("Errors.swift" in k for k in output.files)
        assert "Package.swift" in output.files

    def test_models_codable_structs(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = SwiftSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        models = [v for k, v in output.files.items() if "Models.swift" in k][0]
        assert "struct Pet: Codable" in models
        assert "struct PetCreate: Codable" in models

    def test_models_enum(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = SwiftSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        models = [v for k, v in output.files.items() if "Models.swift" in k][0]
        assert "enum PetStatus" in models

    def test_client_has_methods(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = SwiftSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = [v for k, v in output.files.items() if "Client.swift" in k][0]
        assert "func listPets" in client
        assert "func createPet" in client
        assert "func getPet" in client

    def test_client_actor(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = SwiftSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        client = [v for k, v in output.files.items() if "Client.swift" in k][0]
        assert "public actor Client" in client

    def test_package_swift(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = SwiftSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        pkg = output.files["Package.swift"]
        assert "swift-tools-version" in pkg
        assert "PetstoreClient" in pkg

    def test_auth_providers(
        self, sample_openapi_schema: dict, sdk_config: SDKConfig
    ) -> None:
        gen = SwiftSDKGenerator()
        output = gen.generate(sample_openapi_schema, sdk_config)
        auth = [v for k, v in output.files.items() if "Auth.swift" in k][0]
        assert "class JWTAuth" in auth
        assert "class APIKeyAuth" in auth
        assert "protocol AuthProvider" in auth


# ---------------------------------------------------------------------------
# SDKOutput Tests
# ---------------------------------------------------------------------------

class TestSDKOutput:
    def test_target_set(self, sample_openapi_schema: dict, sdk_config: SDKConfig) -> None:
        ts = TypeScriptSDKGenerator().generate(sample_openapi_schema, sdk_config)
        assert ts.target == "typescript"

        py = PythonSDKGenerator().generate(sample_openapi_schema, sdk_config)
        assert py.target == "python"

        sw = SwiftSDKGenerator().generate(sample_openapi_schema, sdk_config)
        assert sw.target == "swift"


# ---------------------------------------------------------------------------
# SDKConfig Tests
# ---------------------------------------------------------------------------

class TestSDKConfig:
    def test_defaults(self) -> None:
        config = SDKConfig(package_name="test")
        assert config.version == "0.1.0"
        assert config.base_url == "http://localhost:8000"
        assert config.auth_type == "jwt"
        assert config.include_models is True

    def test_output_dir_coercion(self) -> None:
        config = SDKConfig(package_name="test", output_dir="/tmp/sdk")  # type: ignore[arg-type]
        assert isinstance(config.output_dir, Path)


# ---------------------------------------------------------------------------
# Management Command Argument Parsing
# ---------------------------------------------------------------------------

class TestManagementCommand:
    def test_command_importable(self) -> None:
        from django_matt.management.commands.matt_sdk import Command
        cmd = Command()
        assert cmd.help

    def test_command_has_subcommands(self) -> None:
        from django.core.management import BaseCommand

        from django_matt.management.commands.matt_sdk import Command
        cmd = Command()
        parser = cmd.create_parser("manage.py", "matt_sdk")
        # Just verify it doesn't blow up when creating the parser
        assert parser is not None
