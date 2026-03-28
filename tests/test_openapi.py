"""
Tests for django_matt/openapi/ — OpenAPI schema generation, Swagger/ReDoc docs.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Optional
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
    responses: dict[int, type] | None = None,
) -> dict:
    return {
        "path": path,
        "endpoint": endpoint,
        "methods": methods,
        "name": name or endpoint.__name__,
        "response_model": response_model,
        "status_code": status_code,
        "tags": tags or [],
        "responses": responses or {},
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


# ---------------------------------------------------------------------------
# Schema mode separation (request=validation vs response=serialization)
# ---------------------------------------------------------------------------

from pydantic import computed_field


class ItemSchema(BaseModel):
    """Schema with a computed field — differs between validation and serialization."""
    name: str
    price: float

    @computed_field
    @property
    def display(self) -> str:
        return f"{self.name}: ${self.price:.2f}"


class ItemCreateSchema(BaseModel):
    name: str
    price: float


def list_items() -> list[ItemSchema]:
    """List items."""


def create_item(data: ItemCreateSchema) -> ItemSchema:
    """Create an item."""


def update_item(data: ItemSchema) -> ItemSchema:
    """Update using the same schema for request and response."""


class TestSchemaModeSeparation:
    """Verify request schemas use validation mode and response schemas use serialization mode."""

    def test_response_schema_includes_computed_field(self):
        """Serialization mode includes computed fields in the response schema."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/items", list_items, ["GET"], response_model=ItemSchema),
        ])
        result = schema.build()
        # The component schema should include the computed 'display' field
        # (serialization mode exposes computed fields)
        item_schema = result["components"]["schemas"]["ItemSchema"]
        assert "display" in item_schema["properties"]

    def test_request_schema_excludes_computed_field(self):
        """Validation mode excludes computed fields from request body schemas."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/items", create_item, ["POST"]),
        ])
        result = schema.build()
        # ItemCreateSchema has no computed fields so it's straightforward,
        # but let's also check that a model with computed fields used as
        # request body does NOT include the computed field.
        def post_item(data: ItemSchema):
            """Post with ItemSchema as body."""
        schema2 = OpenAPISchema()
        schema2.add_routes([_route("/items", post_item, ["POST"])])
        result2 = schema2.build()
        req_schema = result2["components"]["schemas"]["ItemSchema"]
        assert "display" not in req_schema["properties"]

    def test_same_model_both_modes_produces_separate_components(self):
        """When the same model is used for request and response and schemas differ,
        two separate component entries are created."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/items", update_item, ["PUT"], response_model=ItemSchema),
        ])
        result = schema.build()
        component_names = set(result["components"]["schemas"].keys())
        # ItemSchema has a computed field so validation != serialization
        assert "ItemSchemaRequest" in component_names
        assert "ItemSchemaResponse" in component_names

    def test_same_model_both_modes_refs_are_correct(self):
        """$ref values point to the correct suffixed component names."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/items", update_item, ["PUT"], response_model=ItemSchema),
        ])
        result = schema.build()
        op = result["paths"]["/items"]["put"]
        # Request body ref
        req_ref = op["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        assert req_ref == "#/components/schemas/ItemSchemaRequest"
        # Response ref
        resp_ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        assert resp_ref == "#/components/schemas/ItemSchemaResponse"

    def test_identical_modes_share_component(self):
        """When validation and serialization produce the same schema, share one component."""
        # UserCreateSchema has no computed fields — modes are identical
        def create_and_return(data: UserCreateSchema) -> UserCreateSchema:
            ...
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/echo", create_and_return, ["POST"], response_model=UserCreateSchema),
        ])
        result = schema.build()
        component_names = set(result["components"]["schemas"].keys())
        # Should NOT have suffixed variants
        assert "UserCreateSchema" in component_names
        assert "UserCreateSchemaRequest" not in component_names
        assert "UserCreateSchemaResponse" not in component_names

    def test_response_computed_field_is_required(self):
        """In serialization mode, computed fields are marked as required."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/items", list_items, ["GET"], response_model=ItemSchema),
        ])
        result = schema.build()
        item_schema = result["components"]["schemas"]["ItemSchema"]
        assert "display" in item_schema.get("required", [])


# ---------------------------------------------------------------------------
# Permission extensions (x-auth-required, x-permissions, x-roles)
# ---------------------------------------------------------------------------

from django_matt.permissions.common import (
    AllowAny,
    HasPermission,
    HasRole,
    IsAdmin,
    IsAuthenticated,
    IsOwner,
)


class TestPermissionExtensions:
    """Test x-auth-required, x-permissions, x-roles OpenAPI extension fields."""

    def test_no_extensions_when_no_permissions(self):
        """Endpoints without permissions have no extension fields."""
        schema = OpenAPISchema()
        schema.add_routes([_route("/ping", list_users, ["GET"])])
        op = schema.build()["paths"]["/ping"]["get"]
        assert "x-auth-required" not in op
        assert "x-permissions" not in op
        assert "x-roles" not in op

    def test_controller_level_is_authenticated(self):
        """Controller with IsAuthenticated sets x-auth-required: true."""

        class AuthController:
            prefix = "/protected"
            tags = []
            permission_classes = [IsAuthenticated]

            def get_data(self):
                """Get data."""
            get_data._route_info = {
                "path": "/",
                "methods": ["GET"],
                "name": "get_data",
                "tags": None,
            }

        schema = OpenAPISchema()
        schema.add_controller(AuthController)
        op = schema.build()["paths"]["/protected"]["get"]
        assert op["x-auth-required"] is True

    def test_controller_level_is_admin(self):
        """Controller with IsAdmin sets x-auth-required: true."""

        class AdminController:
            prefix = "/admin"
            tags = []
            permission_classes = [IsAdmin]

            def get_admin(self):
                """Admin endpoint."""
            get_admin._route_info = {
                "path": "/",
                "methods": ["GET"],
                "name": "get_admin",
                "tags": None,
            }

        schema = OpenAPISchema()
        schema.add_controller(AdminController)
        op = schema.build()["paths"]["/admin"]["get"]
        assert op["x-auth-required"] is True

    def test_controller_level_has_role(self):
        """Controller with HasRole instance sets x-roles and x-auth-required."""

        class RoleController:
            prefix = "/manager"
            tags = []
            permission_classes = [HasRole(roles=["manager", "admin"])]

            def get_report(self):
                """Manager report."""
            get_report._route_info = {
                "path": "/",
                "methods": ["GET"],
                "name": "get_report",
                "tags": None,
            }

        schema = OpenAPISchema()
        schema.add_controller(RoleController)
        op = schema.build()["paths"]["/manager"]["get"]
        assert op["x-auth-required"] is True
        assert op["x-roles"] == ["admin", "manager"]

    def test_controller_level_has_permission(self):
        """Controller with HasPermission instance sets x-permissions."""

        class PermController:
            prefix = "/edit"
            tags = []
            permission_classes = [HasPermission(permissions=["myapp.change_model"])]

            def edit(self):
                """Edit endpoint."""
            edit._route_info = {
                "path": "/",
                "methods": ["PUT"],
                "name": "edit",
                "tags": None,
            }

        schema = OpenAPISchema()
        schema.add_controller(PermController)
        op = schema.build()["paths"]["/edit"]["put"]
        assert op["x-auth-required"] is True
        assert op["x-permissions"] == ["myapp.change_model"]

    def test_guard_override(self):
        """Method-level @guard overrides controller-level permissions."""

        class MixedController:
            prefix = "/mix"
            tags = []
            permission_classes = [IsAuthenticated]

            def public_endpoint(self):
                """Public endpoint."""
            public_endpoint._route_info = {
                "path": "/public",
                "methods": ["GET"],
                "name": "public_endpoint",
                "tags": None,
            }
            public_endpoint._guard_permissions = [AllowAny]

        schema = OpenAPISchema()
        schema.add_controller(MixedController)
        op = schema.build()["paths"]["/mix/public"]["get"]
        # AllowAny is not in _AUTH_PERMISSION_NAMES so auth_required stays False
        assert "x-auth-required" not in op

    def test_allow_any_flag(self):
        """Methods with _allow_any=True have no auth extensions."""

        class AllowAnyController:
            prefix = "/open"
            tags = []
            permission_classes = [IsAuthenticated]

            def open_endpoint(self):
                """Open endpoint."""
            open_endpoint._route_info = {
                "path": "/",
                "methods": ["GET"],
                "name": "open_endpoint",
                "tags": None,
            }
            open_endpoint._allow_any = True

        schema = OpenAPISchema()
        schema.add_controller(AllowAnyController)
        op = schema.build()["paths"]["/open"]["get"]
        assert "x-auth-required" not in op

    def test_required_roles_from_decorator(self):
        """Endpoint with _required_roles attribute sets x-roles."""
        def admin_only():
            """Admin only endpoint."""
        admin_only._required_roles = ["admin"]

        schema = OpenAPISchema()
        schema.add_routes([_route("/admin", admin_only, ["GET"])])
        op = schema.build()["paths"]["/admin"]["get"]
        assert op["x-auth-required"] is True
        assert op["x-roles"] == ["admin"]

    def test_required_permissions_from_decorator(self):
        """Endpoint with _required_permissions attribute sets x-permissions."""
        def edit_stuff():
            """Edit stuff."""
        edit_stuff._required_permissions = ["app.edit", "app.delete"]

        schema = OpenAPISchema()
        schema.add_routes([_route("/edit", edit_stuff, ["PUT"])])
        op = schema.build()["paths"]["/edit"]["put"]
        assert op["x-auth-required"] is True
        assert op["x-permissions"] == ["app.delete", "app.edit"]

    def test_combined_roles_and_permissions(self):
        """Both roles and permissions appear when both are present."""

        class ComboController:
            prefix = "/combo"
            tags = []
            permission_classes = [
                HasRole(roles=["editor"]),
                HasPermission(permissions=["content.publish"]),
            ]

            def publish(self):
                """Publish content."""
            publish._route_info = {
                "path": "/",
                "methods": ["POST"],
                "name": "publish",
                "tags": None,
            }

        schema = OpenAPISchema()
        schema.add_controller(ComboController)
        op = schema.build()["paths"]["/combo"]["post"]
        assert op["x-auth-required"] is True
        assert op["x-roles"] == ["editor"]
        assert op["x-permissions"] == ["content.publish"]

    def test_no_empty_arrays(self):
        """Extension fields are omitted when empty, not set to []."""
        class AuthOnly:
            prefix = "/auth"
            tags = []
            permission_classes = [IsAuthenticated]

            def me(self):
                """Get self."""
            me._route_info = {
                "path": "/me",
                "methods": ["GET"],
                "name": "me",
                "tags": None,
            }

        schema = OpenAPISchema()
        schema.add_controller(AuthOnly)
        op = schema.build()["paths"]["/auth/me"]["get"]
        assert op["x-auth-required"] is True
        assert "x-roles" not in op
        assert "x-permissions" not in op

    def test_multiple_permission_classes(self):
        """Multiple permission classes are all processed."""

        class MultiController:
            prefix = "/multi"
            tags = []
            permission_classes = [IsAuthenticated, IsOwner]

            def my_resource(self):
                """My resource."""
            my_resource._route_info = {
                "path": "/",
                "methods": ["GET"],
                "name": "my_resource",
                "tags": None,
            }

        schema = OpenAPISchema()
        schema.add_controller(MultiController)
        op = schema.build()["paths"]["/multi"]["get"]
        assert op["x-auth-required"] is True

    def test_roles_deduplicated_and_sorted(self):
        """Duplicate roles from multiple sources are deduplicated and sorted."""
        def endpoint():
            """Test."""
        endpoint._required_roles = ["admin", "editor", "admin"]

        schema = OpenAPISchema()
        schema.add_routes([_route("/dedup", endpoint, ["GET"])])
        op = schema.build()["paths"]["/dedup"]["get"]
        assert op["x-roles"] == ["admin", "editor"]

    def test_is_owner_sets_auth_required(self):
        """IsOwner permission class triggers x-auth-required."""

        class OwnerController:
            prefix = "/owned"
            tags = []
            permission_classes = [IsOwner]

            def get_owned(self):
                """Get owned."""
            get_owned._route_info = {
                "path": "/",
                "methods": ["GET"],
                "name": "get_owned",
                "tags": None,
            }

        schema = OpenAPISchema()
        schema.add_controller(OwnerController)
        op = schema.build()["paths"]["/owned"]["get"]
        assert op["x-auth-required"] is True


# ---------------------------------------------------------------------------
# Qualified schema names (Enhancement 2.7)
# ---------------------------------------------------------------------------

def _make_schema_in_module(module_name: str, class_name: str, fields: dict[str, type]) -> type:
    """Create a Pydantic BaseModel subclass that lives in the given module."""
    ns: dict[str, Any] = {"__annotations__": fields}
    cls = type(class_name, (BaseModel,), ns)
    cls.__module__ = module_name
    cls.__qualname__ = class_name
    return cls


class TestQualifiedSchemaNames:
    """Test DJANGO_MATT.QUALIFIED_SCHEMA_NAMES setting and auto-collision detection."""

    def test_default_uses_bare_names(self):
        """With default settings (off), bare class names are used."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/users", list_users, ["GET"], response_model=UserSchema),
        ])
        result = schema.build()
        assert "UserSchema" in result["components"]["schemas"]

    def test_qualified_names_enabled(self, settings):
        """When QUALIFIED_SCHEMA_NAMES is True, module prefix is added."""
        settings.DJANGO_MATT = {"QUALIFIED_SCHEMA_NAMES": True}
        AccountUser = _make_schema_in_module("myapp.accounts.schemas", "UserSchema", {"id": int, "name": str})

        def list_account_users() -> list[AccountUser]:
            """List users."""

        schema = OpenAPISchema()
        schema.add_routes([
            _route("/users", list_account_users, ["GET"], response_model=AccountUser),
        ])
        result = schema.build()
        # Should use the "accounts" prefix (last meaningful segment)
        assert "accounts.UserSchema" in result["components"]["schemas"]
        assert "UserSchema" not in result["components"]["schemas"]

    def test_qualified_name_strips_schemas_module(self, settings):
        """The qualifier skips 'schemas' module name, using the parent."""
        settings.DJANGO_MATT = {"QUALIFIED_SCHEMA_NAMES": True}
        MyModel = _make_schema_in_module("myapp.billing.schemas", "InvoiceSchema", {"total": float})

        schema = OpenAPISchema()
        schema.add_routes([
            _route("/invoices", list_users, ["GET"], response_model=MyModel),
        ])
        result = schema.build()
        assert "billing.InvoiceSchema" in result["components"]["schemas"]

    def test_qualified_name_strips_models_module(self, settings):
        """The qualifier skips 'models' module name, using the parent."""
        settings.DJANGO_MATT = {"QUALIFIED_SCHEMA_NAMES": True}
        MyModel = _make_schema_in_module("myapp.products.models", "ProductSchema", {"name": str})

        schema = OpenAPISchema()
        schema.add_routes([
            _route("/products", list_users, ["GET"], response_model=MyModel),
        ])
        result = schema.build()
        assert "products.ProductSchema" in result["components"]["schemas"]

    def test_collision_auto_qualifies(self):
        """Without the setting, colliding names are auto-qualified."""
        AccountUser = _make_schema_in_module("myapp.accounts.schemas", "UserSchema", {"id": int, "email": str})
        AdminUser = _make_schema_in_module("myapp.admin.schemas", "UserSchema", {"id": int, "role": str})

        def list_account_users() -> list[AccountUser]:
            """List account users."""

        def list_admin_users() -> list[AdminUser]:
            """List admin users."""

        schema = OpenAPISchema()
        schema.add_routes([
            _route("/accounts/users", list_account_users, ["GET"], response_model=AccountUser),
            _route("/admin/users", list_admin_users, ["GET"], response_model=AdminUser),
        ])
        result = schema.build()
        component_names = set(result["components"]["schemas"].keys())
        # Both should be qualified now, bare "UserSchema" should not exist
        assert "accounts.UserSchema" in component_names
        assert "admin.UserSchema" in component_names
        assert "UserSchema" not in component_names

    def test_collision_refs_rewritten(self):
        """When a collision triggers qualification, $ref values are updated."""
        AccountUser = _make_schema_in_module("myapp.accounts.schemas", "UserSchema", {"id": int, "email": str})
        AdminUser = _make_schema_in_module("myapp.admin.schemas", "UserSchema", {"id": int, "role": str})

        def list_account_users() -> list[AccountUser]:
            """List account users."""

        def list_admin_users() -> list[AdminUser]:
            """List admin users."""

        schema = OpenAPISchema()
        schema.add_routes([
            _route("/accounts/users", list_account_users, ["GET"], response_model=AccountUser),
            _route("/admin/users", list_admin_users, ["GET"], response_model=AdminUser),
        ])
        result = schema.build()

        # Check that refs point to the qualified names
        acc_ref = result["paths"]["/accounts/users"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        adm_ref = result["paths"]["/admin/users"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        assert "accounts.UserSchema" in acc_ref
        assert "admin.UserSchema" in adm_ref

    def test_no_collision_keeps_bare_name(self):
        """When there's no collision, bare names are kept (backwards compat)."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route("/users", list_users, ["GET"], response_model=UserSchema),
            _route("/products", search_products, ["GET"], response_model=ProductSchema),
        ])
        result = schema.build()
        component_names = set(result["components"]["schemas"].keys())
        assert "UserSchema" in component_names
        assert "ProductSchema" in component_names

    def test_qualified_with_mode_separation(self, settings):
        """Qualified names work correctly with request/response mode separation."""
        settings.DJANGO_MATT = {"QUALIFIED_SCHEMA_NAMES": True}

        def update_item_qualified(data: ItemSchema) -> ItemSchema:
            """Update item."""

        schema = OpenAPISchema()
        schema.add_routes([
            _route("/items", update_item_qualified, ["PUT"], response_model=ItemSchema),
        ])
        result = schema.build()
        component_names = set(result["components"]["schemas"].keys())
        # ItemSchema has computed fields so request != response
        # With qualified names, they should still get Request/Response suffixes
        qualified_names = [n for n in component_names if "ItemSchema" in n]
        assert len(qualified_names) >= 2  # Request and Response variants


# ---------------------------------------------------------------------------
# Multi-response schemas (Enhancement 2.8)
# ---------------------------------------------------------------------------


class ErrorSchema(BaseModel):
    """Error occurred."""

    detail: str
    code: str


class NotFoundSchema(BaseModel):
    """Resource not found."""

    detail: str


class ConflictSchema(BaseModel):
    """Conflict with existing resource."""

    detail: str
    existing_id: int


class TestMultiResponseSchemas:
    """Test responses={status: Schema} on routes and controllers."""

    def test_extra_responses_appear_in_operation(self):
        """Extra response schemas are added to the operation responses."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route(
                "/users/{user_id}",
                get_user,
                ["GET"],
                response_model=UserSchema,
                responses={404: NotFoundSchema, 403: ErrorSchema},
            ),
        ])
        result = schema.build()
        op = result["paths"]["/users/{user_id}"]["get"]
        assert "200" in op["responses"]
        assert "404" in op["responses"]
        assert "403" in op["responses"]

    def test_extra_response_schema_ref(self):
        """Extra response entries contain $ref to registered component schemas."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route(
                "/users/{user_id}",
                get_user,
                ["GET"],
                response_model=UserSchema,
                responses={404: NotFoundSchema},
            ),
        ])
        result = schema.build()
        resp_404 = result["paths"]["/users/{user_id}"]["get"]["responses"]["404"]
        body = resp_404["content"]["application/json"]["schema"]
        assert "$ref" in body
        assert "NotFoundSchema" in body["$ref"]

    def test_extra_response_schema_registered_as_component(self):
        """Extra response Pydantic models are registered in components/schemas."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route(
                "/users/{user_id}",
                get_user,
                ["GET"],
                response_model=UserSchema,
                responses={404: NotFoundSchema, 409: ConflictSchema},
            ),
        ])
        result = schema.build()
        component_names = set(result["components"]["schemas"].keys())
        assert "NotFoundSchema" in component_names
        assert "ConflictSchema" in component_names

    def test_extra_response_description_from_docstring(self):
        """Extra response description is taken from model docstring."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route(
                "/users/{user_id}",
                get_user,
                ["GET"],
                response_model=UserSchema,
                responses={404: NotFoundSchema},
            ),
        ])
        result = schema.build()
        resp_404 = result["paths"]["/users/{user_id}"]["get"]["responses"]["404"]
        assert resp_404["description"] == "Resource not found."

    def test_extra_response_does_not_overwrite_success(self):
        """If the same status code as the success response is in responses,
        the primary success response takes precedence."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route(
                "/users",
                list_users,
                ["GET"],
                response_model=UserSchema,
                status_code=200,
                responses={200: ErrorSchema},  # should be ignored
            ),
        ])
        result = schema.build()
        resp_200 = result["paths"]["/users"]["get"]["responses"]["200"]
        body = resp_200["content"]["application/json"]["schema"]
        assert "UserSchema" in body["$ref"]

    def test_validation_error_422_still_present(self):
        """The default 422 validation error response is still generated."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route(
                "/users/{user_id}",
                get_user,
                ["GET"],
                response_model=UserSchema,
                responses={404: NotFoundSchema},
            ),
        ])
        result = schema.build()
        assert "422" in result["paths"]["/users/{user_id}"]["get"]["responses"]

    def test_empty_responses_dict_no_change(self):
        """An empty responses dict produces the same output as no responses."""
        schema_with = OpenAPISchema()
        schema_with.add_routes([
            _route(
                "/users", list_users, ["GET"], response_model=UserSchema, responses={}
            ),
        ])
        schema_without = OpenAPISchema()
        schema_without.add_routes([
            _route("/users", list_users, ["GET"], response_model=UserSchema),
        ])
        assert (
            schema_with.build()["paths"]["/users"]["get"]["responses"]
            == schema_without.build()["paths"]["/users"]["get"]["responses"]
        )

    def test_controller_with_responses(self):
        """Controller methods with responses in _route_info work correctly."""

        class UserController:
            prefix = "/users"
            tags = ["Users"]
            permission_classes = []

            def get_user(self, user_id: int):
                """Get a user."""

            get_user._route_info = {
                "path": "/{user_id}",
                "methods": ["GET"],
                "name": "get_user",
                "response_model": UserSchema,
                "status_code": 200,
                "tags": None,
                "responses": {404: NotFoundSchema, 403: ErrorSchema},
            }

        schema = OpenAPISchema()
        schema.add_controller(UserController)
        result = schema.build()
        op = result["paths"]["/users/{user_id}"]["get"]
        assert "200" in op["responses"]
        assert "404" in op["responses"]
        assert "403" in op["responses"]

    def test_route_decorator_stores_responses(self):
        """The standalone route decorators store responses in _route_info."""
        from django_matt.core.router import get as route_get

        @route_get(
            "/items/{id}", responses={404: NotFoundSchema, 409: ConflictSchema}
        )
        def get_item(self, request, id: int): ...

        info = get_item._route_info
        assert info["responses"] == {404: NotFoundSchema, 409: ConflictSchema}

    def test_router_method_decorator_stores_responses(self):
        """APIRouter.get/post/etc decorators store responses in route dict."""
        from django_matt.core.router import APIRouter

        router = APIRouter()

        @router.get("/items/{id}", responses={404: NotFoundSchema})
        def get_item(request, id: int): ...

        assert len(router.routes) == 1
        assert router.routes[0]["responses"] == {404: NotFoundSchema}

    def test_multiple_extra_responses_all_registered(self):
        """Multiple extra response schemas are all registered and referenced."""
        schema = OpenAPISchema()
        schema.add_routes([
            _route(
                "/users",
                create_user,
                ["POST"],
                response_model=UserSchema,
                status_code=201,
                responses={400: ErrorSchema, 409: ConflictSchema},
            ),
        ])
        result = schema.build()
        op = result["paths"]["/users"]["post"]
        assert "201" in op["responses"]
        assert "400" in op["responses"]
        assert "409" in op["responses"]
        assert "422" in op["responses"]
        # Verify component schemas exist
        components = set(result["components"]["schemas"].keys())
        assert "ErrorSchema" in components
        assert "ConflictSchema" in components
