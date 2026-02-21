"""
Tests for django_matt.typegen module.

Covers utility functions, TypeScriptGenerator, SwiftGenerator, ZodGenerator,
and collect_schemas_from_module.
"""

import datetime
import uuid
from enum import Enum
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Inline test schemas
# ---------------------------------------------------------------------------
class SimpleSchema(BaseModel):
    id: int
    name: str


class OptionalSchema(BaseModel):
    id: int
    name: Optional[str] = None
    active: bool = True


class NestedSchema(BaseModel):
    user: SimpleSchema
    tags: list[str] = []


class DictFieldSchema(BaseModel):
    metadata: dict[str, int]


class DescribedSchema(BaseModel):
    """A schema with descriptions."""

    id: int = Field(description="The unique identifier")
    name: str = Field(description="Full name")


class DateFieldSchema(BaseModel):
    created_at: datetime.datetime
    birthday: datetime.date
    unique_id: uuid.UUID


class StatusEnum(str, Enum):
    active = "active"
    inactive = "inactive"


class EnumSchema(BaseModel):
    status: StatusEnum


class IdlessSchema(BaseModel):
    """Schema without an id field."""

    name: str
    value: int


class SnakeCaseSchema(BaseModel):
    first_name: str
    last_name: str
    is_active: bool


# ---------------------------------------------------------------------------
# 1. Utility functions (~10 tests)
# ---------------------------------------------------------------------------
class TestUtilityFunctions:
    """Tests for typegen.utils helper functions."""

    def test_snake_to_camel_basic(self):
        from django_matt.typegen.utils import snake_to_camel

        assert snake_to_camel("hello_world") == "helloWorld"

    def test_snake_to_camel_single_word(self):
        from django_matt.typegen.utils import snake_to_camel

        assert snake_to_camel("hello") == "hello"

    def test_snake_to_camel_multi_underscore(self):
        from django_matt.typegen.utils import snake_to_camel

        assert snake_to_camel("one_two_three_four") == "oneTwoThreeFour"

    def test_camel_to_snake_basic(self):
        from django_matt.typegen.utils import camel_to_snake

        assert camel_to_snake("helloWorld") == "hello_world"

    def test_camel_to_snake_consecutive_caps(self):
        from django_matt.typegen.utils import camel_to_snake

        assert camel_to_snake("parseHTTPResponse") == "parse_http_response"

    def test_snake_to_pascal_basic(self):
        from django_matt.typegen.utils import snake_to_pascal

        assert snake_to_pascal("hello_world") == "HelloWorld"

    def test_python_type_to_typescript_str(self):
        from django_matt.typegen.utils import python_type_to_typescript

        assert python_type_to_typescript(str) == "string"

    def test_python_type_to_typescript_int(self):
        from django_matt.typegen.utils import python_type_to_typescript

        assert python_type_to_typescript(int) == "number"

    def test_python_type_to_typescript_bool(self):
        from django_matt.typegen.utils import python_type_to_typescript

        assert python_type_to_typescript(bool) == "boolean"

    def test_python_type_to_typescript_optional(self):
        from django_matt.typegen.utils import python_type_to_typescript

        result = python_type_to_typescript(Optional[str])
        assert "string" in result
        assert "null" in result

    def test_python_type_to_typescript_list(self):
        from django_matt.typegen.utils import python_type_to_typescript

        assert python_type_to_typescript(list[str]) == "string[]"

    def test_python_type_to_typescript_dict(self):
        from django_matt.typegen.utils import python_type_to_typescript

        result = python_type_to_typescript(dict[str, int])
        assert "Record<string, number>" == result

    def test_python_type_to_typescript_enum(self):
        from django_matt.typegen.utils import python_type_to_typescript

        result = python_type_to_typescript(StatusEnum)
        assert '"active"' in result
        assert '"inactive"' in result

    def test_python_type_to_typescript_basemodel_ref(self):
        from django_matt.typegen.utils import python_type_to_typescript

        result = python_type_to_typescript(SimpleSchema)
        assert result == "SimpleSchema"

    def test_python_type_to_zod_str(self):
        from django_matt.typegen.utils import python_type_to_zod

        assert python_type_to_zod(str) == "z.string()"

    def test_python_type_to_zod_int(self):
        from django_matt.typegen.utils import python_type_to_zod

        assert python_type_to_zod(int) == "z.number().int()"

    def test_python_type_to_zod_optional(self):
        from django_matt.typegen.utils import python_type_to_zod

        result = python_type_to_zod(Optional[str])
        assert "z.string()" in result
        assert ".nullable()" in result

    def test_python_type_to_zod_datetime(self):
        from django_matt.typegen.utils import python_type_to_zod

        assert python_type_to_zod(datetime.datetime) == "z.string().datetime()"


# ---------------------------------------------------------------------------
# 2. TypeScriptGenerator (~12 tests)
# ---------------------------------------------------------------------------
class TestTypeScriptGenerator:
    """Tests for TypeScriptGenerator."""

    def test_basic_schema_to_interface(self):
        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator()
        result = gen.generate([SimpleSchema])
        assert "export interface SimpleSchema {" in result
        assert "id: number;" in result
        assert "name: string;" in result

    def test_optional_fields_marker(self):
        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator()
        result = gen.generate([OptionalSchema])
        assert "name?: string | null;" in result
        assert "active?: boolean;" in result
        # id is required — no ?
        assert "id: number;" in result

    def test_nested_pydantic_schema(self):
        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator()
        result = gen.generate([SimpleSchema, NestedSchema])
        assert "user: SimpleSchema;" in result
        assert "tags?: string[];" in result

    def test_enum_fields(self):
        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator()
        result = gen.generate([EnumSchema])
        assert '"active"' in result
        assert '"inactive"' in result

    def test_camel_case_mode(self):
        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator(camel_case=True)
        result = gen.generate([SnakeCaseSchema])
        assert "firstName: string;" in result
        assert "lastName: string;" in result
        assert "isActive: boolean;" in result

    def test_readonly_mode(self):
        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator(add_readonly=True)
        result = gen.generate([SimpleSchema])
        assert "readonly id: number;" in result
        assert "readonly name: string;" in result

    def test_list_and_dict_fields(self):
        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator()
        result = gen.generate([NestedSchema, DictFieldSchema])
        assert "string[]" in result
        assert "Record<string, number>" in result

    def test_multiple_schemas(self):
        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator()
        result = gen.generate([SimpleSchema, OptionalSchema])
        assert "export interface SimpleSchema {" in result
        assert "export interface OptionalSchema {" in result

    def test_custom_header(self):
        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator()
        result = gen.generate([SimpleSchema], header="Custom header text")
        assert "// Custom header text" in result
        # Default header should NOT be present
        assert "Auto-generated TypeScript types" not in result

    def test_default_header(self):
        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator()
        result = gen.generate([SimpleSchema])
        assert "Auto-generated TypeScript types from Pydantic schemas" in result

    def test_type_alias_mode(self):
        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator(use_interface=False)
        result = gen.generate([SimpleSchema])
        assert "export type SimpleSchema = {" in result

    def test_generate_from_django_models_user(self):
        from django.contrib.auth.models import User

        from django_matt.typegen.typescript import TypeScriptGenerator

        gen = TypeScriptGenerator()
        result = gen.generate_from_django_models([User])
        assert "export interface User {" in result
        assert "username" in result
        assert "email" in result


# ---------------------------------------------------------------------------
# 3. SwiftGenerator (~10 tests)
# ---------------------------------------------------------------------------
class TestSwiftGenerator:
    """Tests for SwiftGenerator."""

    def test_basic_schema_to_struct(self):
        from django_matt.typegen.swift import SwiftGenerator

        gen = SwiftGenerator()
        result = gen.generate([SimpleSchema])
        assert "public struct SimpleSchema" in result
        assert "public let id: Int" in result
        assert "public let name: String" in result

    def test_codable_protocol(self):
        from django_matt.typegen.swift import SwiftGenerator

        gen = SwiftGenerator(add_codable=True)
        result = gen.generate([SimpleSchema])
        assert "Codable" in result

    def test_optional_fields(self):
        from django_matt.typegen.swift import SwiftGenerator

        gen = SwiftGenerator()
        result = gen.generate([OptionalSchema])
        # name is optional, should end with ?
        assert "String?" in result

    def test_coding_keys_for_snake_case(self):
        from django_matt.typegen.swift import SwiftGenerator

        gen = SwiftGenerator(use_coding_keys=True, add_codable=True)
        result = gen.generate([SnakeCaseSchema])
        assert "enum CodingKeys: String, CodingKey {" in result
        assert 'case firstName = "first_name"' in result
        assert 'case lastName = "last_name"' in result
        assert 'case isActive = "is_active"' in result

    def test_identifiable_protocol_with_id(self):
        from django_matt.typegen.swift import SwiftGenerator

        gen = SwiftGenerator(add_identifiable=True)
        result = gen.generate([SimpleSchema])
        assert "Identifiable" in result

    def test_no_identifiable_without_id(self):
        from django_matt.typegen.swift import SwiftGenerator

        gen = SwiftGenerator(add_identifiable=True)
        result = gen.generate([IdlessSchema])
        assert "Identifiable" not in result

    def test_date_field_handling(self):
        from django_matt.typegen.swift import SwiftGenerator

        gen = SwiftGenerator()
        result = gen.generate([DateFieldSchema])
        assert "Date" in result
        assert "UUID" in result

    def test_python_type_to_swift_str(self):
        from django_matt.typegen.swift import python_type_to_swift

        assert python_type_to_swift(str) == "String"

    def test_python_type_to_swift_int(self):
        from django_matt.typegen.swift import python_type_to_swift

        assert python_type_to_swift(int) == "Int"

    def test_python_type_to_swift_optional(self):
        from django_matt.typegen.swift import python_type_to_swift

        result = python_type_to_swift(Optional[str])
        assert result == "String?"

    def test_python_type_to_swift_list(self):
        from django_matt.typegen.swift import python_type_to_swift

        assert python_type_to_swift(list[str]) == "[String]"

    def test_python_type_to_swift_uuid(self):
        from django_matt.typegen.swift import python_type_to_swift

        assert python_type_to_swift(uuid.UUID) == "UUID"

    def test_foundation_import(self):
        from django_matt.typegen.swift import SwiftGenerator

        gen = SwiftGenerator()
        result = gen.generate([SimpleSchema])
        assert "import Foundation" in result


# ---------------------------------------------------------------------------
# 4. ZodGenerator (~8 tests)
# ---------------------------------------------------------------------------
class TestZodGenerator:
    """Tests for ZodGenerator."""

    def test_basic_schema_to_zobject(self):
        from django_matt.typegen.zod import ZodGenerator

        gen = ZodGenerator()
        result = gen.generate([SimpleSchema])
        assert "export const SimpleSchemaSchema = z.object({" in result
        assert "id: z.number().int()," in result
        assert "name: z.string()," in result

    def test_optional_fields(self):
        from django_matt.typegen.zod import ZodGenerator

        gen = ZodGenerator()
        result = gen.generate([OptionalSchema])
        assert ".optional()" in result

    def test_z_import_statement(self):
        from django_matt.typegen.zod import ZodGenerator

        gen = ZodGenerator()
        result = gen.generate([SimpleSchema])
        assert 'import { z } from "zod";' in result

    def test_type_export_infer(self):
        from django_matt.typegen.zod import ZodGenerator

        gen = ZodGenerator()
        result = gen.generate([SimpleSchema])
        assert (
            "export type SimpleSchema = z.infer<typeof SimpleSchemaSchema>;"
            in result
        )

    def test_default_values(self):
        from django_matt.typegen.zod import ZodGenerator

        gen = ZodGenerator(include_defaults=True)
        result = gen.generate([OptionalSchema])
        assert ".default(true)" in result

    def test_description_annotations(self):
        from django_matt.typegen.zod import ZodGenerator

        gen = ZodGenerator(include_descriptions=True)
        result = gen.generate([DescribedSchema])
        assert '.describe("The unique identifier")' in result
        assert '.describe("Full name")' in result

    def test_enum_fields(self):
        from django_matt.typegen.zod import ZodGenerator

        gen = ZodGenerator()
        result = gen.generate([EnumSchema])
        assert "z.enum(" in result
        assert '"active"' in result
        assert '"inactive"' in result

    def test_custom_schema_suffix(self):
        from django_matt.typegen.zod import ZodGenerator

        gen = ZodGenerator(schema_suffix="Validator")
        result = gen.generate([SimpleSchema])
        assert "export const SimpleSchemaValidator = z.object({" in result
        assert (
            "export type SimpleSchema = z.infer<typeof SimpleSchemaValidator>;"
            in result
        )


# ---------------------------------------------------------------------------
# 5. collect_schemas_from_module (~3 tests)
# ---------------------------------------------------------------------------
class TestCollectSchemasFromModule:
    """Tests for collect_schemas_from_module."""

    def test_valid_module_with_schemas(self):
        import types as mod_types

        from django_matt.typegen.utils import collect_schemas_from_module

        # Create a real module object
        mock_module = mod_types.ModuleType("fake_module")

        class FakeSchema(BaseModel):
            id: int

        FakeSchema.__module__ = "fake_module"
        mock_module.FakeSchema = FakeSchema

        with patch("django_matt.typegen.utils.importlib.import_module", return_value=mock_module):
            schemas = collect_schemas_from_module("fake_module")

        assert len(schemas) == 1
        assert schemas[0] is FakeSchema

    def test_module_with_no_schemas(self):
        import types as mod_types

        from django_matt.typegen.utils import collect_schemas_from_module

        mock_module = mod_types.ModuleType("empty_module")
        mock_module.some_func = lambda: None

        with patch("django_matt.typegen.utils.importlib.import_module", return_value=mock_module):
            schemas = collect_schemas_from_module("empty_module")

        assert schemas == []

    def test_invalid_module_path(self):
        from django_matt.typegen.utils import collect_schemas_from_module

        with pytest.raises(ModuleNotFoundError):
            collect_schemas_from_module("nonexistent.module.path")
