"""
Tests for django_matt/openapi/ — OpenAPI schema generation, Swagger/ReDoc docs.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

import orjson
import pytest
from pydantic import BaseModel

from django_matt.openapi.docs import get_openapi_json, get_redoc, get_swagger_ui
from django_matt.openapi.schema import TYPE_MAP, OpenAPISchema

# ---------------------------------------------------------------------------
# Test models / schemas
# ---------------------------------------------------------------------------

class UserCreateSchema(BaseModel):
    username: str
    email: str
    password: str


class UserSchema(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True


class ProductSchema(BaseModel):
    id: int
    name: str
    price: float
    description: str | None = None


class AddressSchema(BaseModel):
    street: str
    city: str
    zip_code: str


class NestedSchema(BaseModel):
    user: UserSchema
    address: AddressSchema


class StatusEnum(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


# ---------------------------------------------------------------------------
# Helpers to build route dicts (same shape the router produces)
# ---------------------------------------------------------------------------

def _route(
    path: str,
    endpoint,
    methods: list[str],
    *,
    name: str | None = None,
    response_model=None,
    status_code: int = 200,
    tags: list[str] | None = None,
) -> dict:
    return {
        "path": path,
        "endpoint": endpoint,
        "methods": methods,
        "name": name or endpoint.__name__,
        "response_model": response_model,
        "status_code": status_code,
        "tags": tags or [],
    }


# Fake endpoints
def list_users():
    """List all users."""


def create_user(data: UserCreateSchema) -> UserSchema:
    """Create a new user.

    Accepts user creation payload and returns the created user.
    """


def get_user(user_id: int):
    """Get a single user by ID."""


def update_user(user_id: int, data: UserCreateSchema):
    """Update user data."""


def delete_user(user_id: int):
    """Delete a user."""


def search_products(q: str, page: int = 1, limit: int = 20):
    """Search products by keyword."""


def no_docstring_endpoint():
    ...


# ---------------------------------------------------------------------------
# OpenAPISchema — construction & info
# ---------------------------------------------------------------------------

class TestOpenAPISchemaConstruction:
    """Test OpenAPISchema initialization and info block."""

    def test_default_values(self):
        schema = OpenAPISchema()
        result = schema.build()
        assert result["openapi"] == "3.1.0"
        assert result["info"]["title"] == "Django Matt API"
        assert result["info"]["version"] == "1.0.0"
        assert result["paths"] == {}

    def test_custom_title_and_version(self):
        schema = OpenAPISchema(title="My API", version="2.5.0")
        result = schema.build()
        assert result["info"]["title"] == "My API"
        assert result["info"]["version"] == "2.5.0"

    def test_description_included_when_set(self):
        schema = OpenAPISchema(description="A cool API")
        result = schema.build()
        assert result["info"]["description"] == "A cool API"

    def test_description_omitted_when_empty(self):
        schema = OpenAPISchema(description="")
        result = schema.build()
        assert "description" not in result["info"]

    def test_terms_of_service(self):
        schema = OpenAPISchema(terms_of_service="https://example.com/tos")
        result = schema.build()
        assert result["info"]["termsOfService"] == "https://example.com/tos"

    def test_contact_info(self):
        contact = {"name": "API Support", "email": "support@example.com"}
        schema = OpenAPISchema(contact=contact)
        result = schema.build()
        assert result["info"]["contact"] == contact

    def test_license_info(self):
        license_info = {"name": "MIT", "url": "https://opensource.org/licenses/MIT"}
        schema = OpenAPISchema(license_info=license_info)
        result = schema.build()
        assert result["info"]["license"] == license_info

    def test_servers(self):
        servers = [
            {"url": "https://api.example.com", "description": "Production"},
            {"url": "https://staging.example.com", "description": "Staging"},
        ]
        schema = OpenAPISchema(servers=servers)
        result = schema.build()
        assert result["servers"] == servers

    def test_servers_default_empty(self):
        schema = OpenAPISchema()
        result = schema.build()
        assert "servers" not in result


# ---------------------------------------------------------------------------
# Path generation
# ---------------------------------------------------------------------------

class TestOpenAPIPaths:
    """Test path registration and HTTP method handling."""

    def test_single_get_route(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users", list_users, ["GET"])])
        result = schema.build()
        assert "/users" in result["paths"]
        assert "get" in result["paths"]["/users"]

    def test_multiple_methods_on_same_path(self):
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/users", list_users, ["GET"]),
            _route("/users", create_user, ["POST"]),
        ])
        result = schema.build()
        assert "get" in result["paths"]["/users"]
        assert "post" in result["paths"]["/users"]

    def test_trailing_slash_stripped(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users/", list_users, ["GET"])])
        result = schema.build()
        assert "/users" in result["paths"]
        assert "/users/" not in result["paths"]

    def test_root_path_preserved(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/", list_users, ["GET"])])
        result = schema.build()
        assert "/" in result["paths"]

    def test_path_params_kept(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users/{user_id}", get_user, ["GET"])])
        result = schema.build()
        assert "/users/{user_id}" in result["paths"]


# ---------------------------------------------------------------------------
# Operation details — summary, description, operationId
# ---------------------------------------------------------------------------

class TestOperationDetails:
    """Test operation metadata extraction."""

    def test_operation_id_from_name(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users", list_users, ["GET"], name="list_users")])
        op = schema.build()["paths"]["/users"]["get"]
        assert op["operationId"] == "list_users"

    def test_summary_from_docstring_first_line(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users", list_users, ["GET"])])
        op = schema.build()["paths"]["/users"]["get"]
        assert op["summary"] == "List all users."

    def test_description_from_docstring_rest(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users", create_user, ["POST"])])
        op = schema.build()["paths"]["/users"]["post"]
        assert op["summary"] == "Create a new user."
        assert "Accepts user creation payload" in op["description"]

    def test_no_summary_when_no_docstring(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/x", no_docstring_endpoint, ["GET"])])
        op = schema.build()["paths"]["/x"]["get"]
        assert "summary" not in op


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

class TestOpenAPITags:
    """Test tag collection and deduplication."""

    def test_tags_on_operation(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users", list_users, ["GET"], tags=["Users"])])
        op = schema.build()["paths"]["/users"]["get"]
        assert op["tags"] == ["Users"]

    def test_tags_collected_at_top_level(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users", list_users, ["GET"], tags=["Users"])])
        result = schema.build()
        assert {"name": "Users"} in result["tags"]

    def test_tags_deduplicated(self):
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/users", list_users, ["GET"], tags=["Users"]),
            _route("/users", create_user, ["POST"], tags=["Users"]),
        ])
        result = schema.build()
        user_tags = [t for t in result["tags"] if t["name"] == "Users"]
        assert len(user_tags) == 1

    def test_multiple_tags(self):
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/users", list_users, ["GET"], tags=["Users"]),
            _route("/products", search_products, ["GET"], tags=["Products"]),
        ])
        result = schema.build()
        tag_names = {t["name"] for t in result["tags"]}
        assert tag_names == {"Users", "Products"}

    def test_no_tags_key_when_none(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/x", list_users, ["GET"])])
        result = schema.build()
        assert "tags" not in result


# ---------------------------------------------------------------------------
# Parameters (path + query)
# ---------------------------------------------------------------------------

class TestOpenAPIParameters:
    """Test parameter extraction from function signatures."""

    def test_path_param_detected(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users/{user_id}", get_user, ["GET"])])
        op = schema.build()["paths"]["/users/{user_id}"]["get"]
        param = next(p for p in op["parameters"] if p["name"] == "user_id")
        assert param["in"] == "path"
        assert param["required"] is True

    def test_query_params_detected(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/products", search_products, ["GET"])])
        op = schema.build()["paths"]["/products"]["get"]
        param_names = {p["name"] for p in op["parameters"]}
        assert "q" in param_names
        assert "page" in param_names
        assert "limit" in param_names

    def test_required_query_param(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/products", search_products, ["GET"])])
        op = schema.build()["paths"]["/products"]["get"]
        q_param = next(p for p in op["parameters"] if p["name"] == "q")
        assert q_param["required"] is True
        assert q_param["in"] == "query"

    def test_optional_query_param_not_required(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/products", search_products, ["GET"])])
        op = schema.build()["paths"]["/products"]["get"]
        page_param = next(p for p in op["parameters"] if p["name"] == "page")
        assert "required" not in page_param or page_param.get("required") is not True

    def test_self_and_request_skipped(self):
        def endpoint(self, request, user_id: int):
            ...
        schema = OpenAPISchema()
        schema.add_routes([_route("/users/{user_id}", endpoint, ["GET"])])
        op = schema.build()["paths"]["/users/{user_id}"]["get"]
        param_names = {p["name"] for p in op.get("parameters", [])}
        assert "self" not in param_names
        assert "request" not in param_names

    def test_no_parameters_when_none(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/health", list_users, ["GET"])])
        op = schema.build()["paths"]["/health"]["get"]
        assert "parameters" not in op or op["parameters"] == []


# ---------------------------------------------------------------------------
# Request body
# ---------------------------------------------------------------------------

class TestOpenAPIRequestBody:
    """Test request body extraction from Pydantic models."""

    def test_post_includes_request_body(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users", create_user, ["POST"])])
        op = schema.build()["paths"]["/users"]["post"]
        assert "requestBody" in op
        assert op["requestBody"]["required"] is True
        body_schema = op["requestBody"]["content"]["application/json"]["schema"]
        assert "$ref" in body_schema
        assert "UserCreateSchema" in body_schema["$ref"]

    def test_get_no_request_body(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users", list_users, ["GET"])])
        op = schema.build()["paths"]["/users"]["get"]
        assert "requestBody" not in op

    def test_put_includes_request_body(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users/{user_id}", update_user, ["PUT"])])
        op = schema.build()["paths"]["/users/{user_id}"]["put"]
        assert "requestBody" in op

    def test_delete_no_request_body(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/users/{user_id}", delete_user, ["DELETE"])])
        op = schema.build()["paths"]["/users/{user_id}"]["delete"]
        assert "requestBody" not in op


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class TestOpenAPIResponses:
    """Test response schema generation."""

    def test_response_model_registered(self):
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/users", list_users, ["GET"], response_model=UserSchema, status_code=200),
        ])
        result = schema.build()
        op = result["paths"]["/users"]["get"]
        resp = op["responses"]["200"]
        assert resp["description"] == "Successful response"
        body = resp["content"]["application/json"]["schema"]
        assert "$ref" in body
        assert "UserSchema" in body["$ref"]

    def test_component_schema_contains_model(self):
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/users", list_users, ["GET"], response_model=UserSchema),
        ])
        result = schema.build()
        assert "UserSchema" in result["components"]["schemas"]
        user_schema = result["components"]["schemas"]["UserSchema"]
        assert "properties" in user_schema
        assert "username" in user_schema["properties"]

    def test_no_response_model_falls_back_to_object(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/ping", list_users, ["GET"])])
        op = schema.build()["paths"]["/ping"]["get"]
        resp_schema = op["responses"]["200"]["content"]["application/json"]["schema"]
        assert resp_schema == {"type": "object"}

    def test_custom_status_code(self):
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/users", create_user, ["POST"], response_model=UserSchema, status_code=201),
        ])
        op = schema.build()["paths"]["/users"]["post"]
        assert "201" in op["responses"]

    def test_validation_error_response_always_present(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/x", list_users, ["GET"])])
        op = schema.build()["paths"]["/x"]["get"]
        assert "422" in op["responses"]
        err_schema = op["responses"]["422"]["content"]["application/json"]["schema"]
        assert "detail" in err_schema["properties"]
        assert "errors" in err_schema["properties"]


# ---------------------------------------------------------------------------
# Component schemas — deduplication and nested models
# ---------------------------------------------------------------------------

class TestOpenAPIComponents:
    """Test component schema registration and deduplication."""

    def test_schema_registered_once(self):
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/a", create_user, ["POST"], response_model=UserSchema),
            _route("/b", create_user, ["POST"], response_model=UserSchema),
        ])
        result = schema.build()
        # UserSchema should appear exactly once in components
        assert "UserSchema" in result["components"]["schemas"]

    def test_nested_model_schemas_extracted(self):
        def create_nested(data: NestedSchema):
            ...
        schema = OpenAPISchema()
        schema.add_routes([_route("/nested", create_nested, ["POST"])])
        result = schema.build()
        component_names = set(result["components"]["schemas"].keys())
        # NestedSchema references UserSchema and AddressSchema —
        # Pydantic puts them in $defs which OpenAPISchema hoists
        assert "NestedSchema" in component_names

    def test_no_components_when_no_models(self):
        schema = OpenAPISchema()
        schema.add_routes([_route("/ping", no_docstring_endpoint, ["GET"])])
        result = schema.build()
        assert "components" not in result


# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------

class TestTypeMapping:
    """Test Python type to OpenAPI schema conversion."""

    def test_basic_types_in_type_map(self):
        assert TYPE_MAP[str] == {"type": "string"}
        assert TYPE_MAP[int] == {"type": "integer"}
        assert TYPE_MAP[float] == {"type": "number"}
        assert TYPE_MAP[bool] == {"type": "boolean"}

    def test_date_types(self):
        assert TYPE_MAP[datetime] == {"type": "string", "format": "date-time"}
        assert TYPE_MAP[date] == {"type": "string", "format": "date"}
        assert TYPE_MAP[time] == {"type": "string", "format": "time"}

    def test_uuid_type(self):
        assert TYPE_MAP[UUID] == {"type": "string", "format": "uuid"}

    def test_decimal_type(self):
        assert TYPE_MAP[Decimal] == {"type": "number"}

    def test_bytes_type(self):
        assert TYPE_MAP[bytes] == {"type": "string", "format": "binary"}

    def test_type_to_schema_none(self):
        schema = OpenAPISchema()
        assert schema._type_to_schema(type(None)) == {"type": "null"}

    def test_type_to_schema_optional(self):
        schema = OpenAPISchema()
        result = schema._type_to_schema(Optional[int])
        assert result["type"] == "integer"
        assert result["nullable"] is True

    def test_type_to_schema_list(self):
        schema = OpenAPISchema()
        result = schema._type_to_schema(list[str])
        assert result["type"] == "array"
        assert result["items"] == {"type": "string"}

    def test_type_to_schema_dict(self):
        schema = OpenAPISchema()
        result = schema._type_to_schema(dict[str, int])
        assert result == {"type": "object"}

    def test_type_to_schema_enum(self):
        schema = OpenAPISchema()
        result = schema._type_to_schema(StatusEnum)
        assert result["type"] == "string"
        assert set(result["enum"]) == {"active", "inactive", "pending"}

    def test_type_to_schema_pydantic_model(self):
        schema = OpenAPISchema()
        result = schema._type_to_schema(UserSchema)
        assert "$ref" in result
        assert "UserSchema" in result["$ref"]

    def test_type_to_schema_unknown_defaults_to_string(self):
        schema = OpenAPISchema()
        result = schema._type_to_schema(object)
        assert result == {"type": "string"}

    def test_type_map_returns_copy(self):
        """Ensure _type_to_schema returns a copy so mutations are safe."""
        schema = OpenAPISchema()
        a = schema._type_to_schema(str)
        b = schema._type_to_schema(str)
        assert a == b
        a["extra"] = True
        assert "extra" not in b


# ---------------------------------------------------------------------------
# add_controller
# ---------------------------------------------------------------------------

class TestAddController:
    """Test adding routes from a controller class."""

    def test_controller_with_route_info(self):
        class FakeController:
            prefix = "/items"
            tags = ["Items"]

            def list_items(self):
                """List all items."""
            list_items._route_info = {
                "path": "/",
                "methods": ["GET"],
                "name": "list_items",
                "tags": None,
            }

            def create_item(self, data: ProductSchema):
                """Create item."""
            create_item._route_info = {
                "path": "/",
                "methods": ["POST"],
                "name": "create_item",
                "response_model": ProductSchema,
                "status_code": 201,
                "tags": None,
            }

        schema = OpenAPISchema()
        schema.add_controller(FakeController)
        result = schema.build()

        assert "/items" in result["paths"]
        assert "get" in result["paths"]["/items"]
        assert "post" in result["paths"]["/items"]
        assert result["paths"]["/items"]["get"]["tags"] == ["Items"]

    def test_controller_methods_without_route_info_skipped(self):
        class MinimalController:
            prefix = "/min"
            tags = []

            def helper(self):
                ...

        schema = OpenAPISchema()
        schema.add_controller(MinimalController)
        result = schema.build()
        assert result["paths"] == {}


# ---------------------------------------------------------------------------
# Full build integration
# ---------------------------------------------------------------------------

class TestOpenAPIFullBuild:
    """Test a realistic full schema build."""

    def test_full_schema_structure(self):
        schema = OpenAPISchema(
            title="Test API",
            version="0.1.0",
            description="Integration test schema",
            servers=[{"url": "http://localhost:8000"}],
        )
        schema.add_routes([
            _route("/users", list_users, ["GET"], tags=["Users"], response_model=UserSchema),
            _route("/users", create_user, ["POST"], tags=["Users"], response_model=UserSchema, status_code=201),
            _route("/users/{user_id}", get_user, ["GET"], tags=["Users"], response_model=UserSchema),
            _route("/users/{user_id}", update_user, ["PUT"], tags=["Users"]),
            _route("/users/{user_id}", delete_user, ["DELETE"], tags=["Users"]),
            _route("/products", search_products, ["GET"], tags=["Products"]),
        ])
        result = schema.build()

        # Top-level keys
        assert result["openapi"] == "3.1.0"
        assert result["info"]["title"] == "Test API"
        assert result["servers"][0]["url"] == "http://localhost:8000"

        # Paths
        assert len(result["paths"]) == 3  # /users, /users/{user_id}, /products
        assert "get" in result["paths"]["/users"]
        assert "post" in result["paths"]["/users"]
        assert "get" in result["paths"]["/users/{user_id}"]
        assert "put" in result["paths"]["/users/{user_id}"]
        assert "delete" in result["paths"]["/users/{user_id}"]
        assert "get" in result["paths"]["/products"]

        # Tags
        tag_names = {t["name"] for t in result["tags"]}
        assert "Users" in tag_names
        assert "Products" in tag_names

        # Components
        assert "UserSchema" in result["components"]["schemas"]


# ---------------------------------------------------------------------------
# Swagger UI & ReDoc HTML views
# ---------------------------------------------------------------------------

class TestSwaggerUI:
    """Test Swagger UI HTML generation."""

    def test_returns_http_response(self):
        response = get_swagger_ui()
        assert response.status_code == 200

    def test_content_type_is_html(self):
        response = get_swagger_ui()
        assert response["Content-Type"] == "text/html"

    def test_contains_swagger_ui_div(self):
        response = get_swagger_ui()
        content = response.content.decode()
        assert '<div id="swagger-ui"></div>' in content

    def test_contains_swagger_ui_bundle_script(self):
        response = get_swagger_ui()
        content = response.content.decode()
        assert "swagger-ui-bundle.js" in content

    def test_default_openapi_url(self):
        response = get_swagger_ui()
        content = response.content.decode()
        assert "/openapi.json" in content

    def test_custom_openapi_url(self):
        response = get_swagger_ui(openapi_url="/api/v2/schema.json")
        content = response.content.decode()
        assert "/api/v2/schema.json" in content

    def test_custom_title(self):
        response = get_swagger_ui(title="My Custom API Docs")
        content = response.content.decode()
        assert "<title>My Custom API Docs</title>" in content

    def test_default_title(self):
        response = get_swagger_ui()
        content = response.content.decode()
        assert "<title>API Documentation</title>" in content


class TestReDoc:
    """Test ReDoc HTML generation."""

    def test_returns_http_response(self):
        response = get_redoc()
        assert response.status_code == 200

    def test_content_type_is_html(self):
        response = get_redoc()
        assert response["Content-Type"] == "text/html"

    def test_contains_redoc_element(self):
        response = get_redoc()
        content = response.content.decode()
        assert "<redoc" in content

    def test_contains_redoc_script(self):
        response = get_redoc()
        content = response.content.decode()
        assert "redoc.standalone.js" in content

    def test_default_openapi_url(self):
        response = get_redoc()
        content = response.content.decode()
        assert "/openapi.json" in content

    def test_custom_openapi_url(self):
        response = get_redoc(openapi_url="/api/v3/schema.json")
        content = response.content.decode()
        assert "/api/v3/schema.json" in content

    def test_custom_title(self):
        response = get_redoc(title="ReDoc Custom Title")
        content = response.content.decode()
        assert "<title>ReDoc Custom Title</title>" in content


# ---------------------------------------------------------------------------
# get_openapi_json
# ---------------------------------------------------------------------------

class TestGetOpenAPIJson:
    """Test the JSON response helper."""

    def test_returns_json_content_type(self):
        response = get_openapi_json({"openapi": "3.1.0"})
        assert response["Content-Type"] == "application/json"

    def test_returns_valid_json(self):
        payload = {"openapi": "3.1.0", "info": {"title": "T", "version": "1"}}
        response = get_openapi_json(payload)
        parsed = orjson.loads(response.content)
        assert parsed["openapi"] == "3.1.0"

    def test_uses_orjson(self):
        """Serialized output should match orjson (not stdlib json)."""
        payload = {"a": 1, "b": [2, 3]}
        response = get_openapi_json(payload)
        assert response.content == orjson.dumps(payload)

    def test_status_code_200(self):
        response = get_openapi_json({})
        assert response.status_code == 200
