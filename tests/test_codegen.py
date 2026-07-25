"""Tests for django_matt.codegen module."""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# =============================================================================
# CORE CODE NODE TESTS
# =============================================================================


class TestComment:
    """Tests for Comment code node."""

    def test_single_line_comment(self):
        """Test single line comment generation."""
        from django_matt.codegen.core import Comment

        comment = Comment("This is a comment")
        result = comment.to_typescript()
        assert result == "// This is a comment"

    def test_multiline_comment(self):
        """Test multiline comment generation."""
        from django_matt.codegen.core import Comment

        comment = Comment("This is a comment", multiline=True)
        result = comment.to_typescript()
        assert result == "/* This is a comment */"

    def test_doc_comment_single_line(self):
        """Test JSDoc style single line comment."""
        from django_matt.codegen.core import Comment

        comment = Comment("A description", doc=True)
        result = comment.to_typescript()
        assert result == "/** A description */"

    def test_doc_comment_multiline(self):
        """Test JSDoc style multiline comment."""
        from django_matt.codegen.core import Comment

        comment = Comment("Line 1\nLine 2\nLine 3", doc=True)
        result = comment.to_typescript()
        assert "/**" in result
        assert "* Line 1" in result
        assert "* Line 2" in result
        assert "*/" in result

    def test_comment_with_indentation(self):
        """Test comment with indentation."""
        from django_matt.codegen.core import Comment

        comment = Comment("Indented comment")
        result = comment.to_typescript(indent=2)
        assert result.startswith("    ")  # 2 * 2 spaces


class TestImport:
    """Tests for Import code node."""

    def test_default_import(self):
        """Test default import generation."""
        from django_matt.codegen.core import Import

        imp = Import(module="react", name="React")
        result = imp.to_typescript()
        assert result == 'import React from "react"'

    def test_namespace_import(self):
        """Test namespace import generation."""
        from django_matt.codegen.core import Import

        imp = Import(module="lodash", name="*", alias="_")
        result = imp.to_typescript()
        assert result == 'import * as _ from "lodash"'

    def test_import_with_alias(self):
        """Test import with alias."""
        from django_matt.codegen.core import Import

        imp = Import(module="react", name="Component", alias="Comp")
        result = imp.to_typescript()
        assert result == 'import Component as Comp from "react"'


class TestImportFrom:
    """Tests for ImportFrom code node."""

    def test_named_import(self):
        """Test named import generation."""
        from django_matt.codegen.core import ImportFrom

        imp = ImportFrom(module="react", names=["useState", "useEffect"])
        result = imp.to_typescript()
        assert result == 'import { useState, useEffect } from "react"'

    def test_named_import_with_alias(self):
        """Test named import with alias."""
        from django_matt.codegen.core import ImportFrom

        imp = ImportFrom(module="react", names=[("Component", "Comp"), "useState"])
        result = imp.to_typescript()
        assert result == 'import { Component as Comp, useState } from "react"'

    def test_type_only_import(self):
        """Test type-only import."""
        from django_matt.codegen.core import ImportFrom

        imp = ImportFrom(module="./types", names=["User", "Post"], type_only=True)
        result = imp.to_typescript()
        assert result == 'import type { User, Post } from "./types"'


class TestProperty:
    """Tests for Property code node."""

    def test_simple_property(self):
        """Test simple property generation."""
        from django_matt.codegen.core import Property

        prop = Property(name="id", type="number")
        result = prop.to_typescript()
        assert result == "id: number"

    def test_optional_property(self):
        """Test optional property generation."""
        from django_matt.codegen.core import Property

        prop = Property(name="name", type="string", optional=True)
        result = prop.to_typescript()
        assert result == "name?: string"

    def test_readonly_property(self):
        """Test readonly property generation."""
        from django_matt.codegen.core import Property

        prop = Property(name="id", type="number", readonly=True)
        result = prop.to_typescript()
        assert result == "readonly id: number"

    def test_property_with_comment(self):
        """Test property with JSDoc comment."""
        from django_matt.codegen.core import Property

        prop = Property(name="email", type="string", comment="User's email address")
        result = prop.to_typescript()
        assert "/** User's email address */" in result
        assert "email: string" in result


class TestParameter:
    """Tests for Parameter code node."""

    def test_simple_parameter(self):
        """Test simple parameter generation."""
        from django_matt.codegen.core import Parameter

        param = Parameter(name="id", type="number")
        result = param.to_typescript()
        assert result == "id: number"

    def test_optional_parameter(self):
        """Test optional parameter generation."""
        from django_matt.codegen.core import Parameter

        param = Parameter(name="name", type="string", optional=True)
        result = param.to_typescript()
        assert result == "name?: string"

    def test_parameter_with_default(self):
        """Test parameter with default value."""
        from django_matt.codegen.core import Parameter

        param = Parameter(name="count", type="number", default="0")
        result = param.to_typescript()
        assert result == "count: number = 0"

    def test_rest_parameter(self):
        """Test rest parameter generation."""
        from django_matt.codegen.core import Parameter

        param = Parameter(name="args", type="string[]", rest=True)
        result = param.to_typescript()
        assert result == "...args: string[]"


class TestVariable:
    """Tests for Variable code node."""

    def test_const_variable(self):
        """Test const variable generation."""
        from django_matt.codegen.core import Variable

        var = Variable(name="count", value="0", type="number")
        result = var.to_typescript()
        assert result == "const count: number = 0"

    def test_let_variable(self):
        """Test let variable generation."""
        from django_matt.codegen.core import Variable

        var = Variable(name="count", value="0", const=False)
        result = var.to_typescript()
        assert result == "let count = 0"

    def test_export_variable(self):
        """Test export variable generation."""
        from django_matt.codegen.core import Variable

        var = Variable(name="API_URL", value='"/api"', export=True)
        result = var.to_typescript()
        assert result == 'export const API_URL = "/api"'


class TestFunction:
    """Tests for Function code node."""

    def test_simple_function(self):
        """Test simple function generation."""
        from django_matt.codegen.core import Function, Return

        func = Function(
            name="add",
            parameters=[],
            return_type="number",
            body=[Return("1 + 2")],
        )
        result = func.to_typescript()
        assert "function add(): number {" in result
        assert "return 1 + 2" in result

    def test_async_function(self):
        """Test async function generation."""
        from django_matt.codegen.core import Function

        func = Function(name="fetchData", async_=True)
        result = func.to_typescript()
        assert "async function fetchData()" in result

    def test_exported_function(self):
        """Test exported function generation."""
        from django_matt.codegen.core import Function

        func = Function(name="helper", export=True)
        result = func.to_typescript()
        assert "export function helper()" in result

    def test_arrow_function(self):
        """Test arrow function generation."""
        from django_matt.codegen.core import Function, Parameter

        func = Function(
            name="double",
            parameters=[Parameter("x", "number")],
            return_type="number",
            arrow=True,
        )
        result = func.to_typescript()
        assert "const double = (x: number): number => {" in result

    def test_generic_function(self):
        """Test generic function generation."""
        from django_matt.codegen.core import Function

        func = Function(name="identity", generic="T", return_type="T")
        result = func.to_typescript()
        assert "function identity<T>(): T {" in result


class TestInterface:
    """Tests for Interface code node."""

    def test_simple_interface(self):
        """Test simple interface generation."""
        from django_matt.codegen.core import Interface, Property

        interface = Interface(
            name="User",
            properties=[
                Property("id", "number"),
                Property("name", "string"),
            ],
        )
        result = interface.to_typescript()
        assert "export interface User {" in result
        assert "id: number" in result
        assert "name: string" in result

    def test_interface_extends(self):
        """Test interface with extends."""
        from django_matt.codegen.core import Interface

        interface = Interface(name="Admin", extends=["User", "HasPermissions"])
        result = interface.to_typescript()
        assert "export interface Admin extends User, HasPermissions {" in result

    def test_generic_interface(self):
        """Test generic interface generation."""
        from django_matt.codegen.core import Interface

        interface = Interface(name="Response", generic="T")
        result = interface.to_typescript()
        assert "export interface Response<T> {" in result

    def test_non_exported_interface(self):
        """Test non-exported interface."""
        from django_matt.codegen.core import Interface

        interface = Interface(name="Internal", export=False)
        result = interface.to_typescript()
        assert result.startswith("interface Internal")


class TestTypeAlias:
    """Tests for TypeAlias code node."""

    def test_simple_type_alias(self):
        """Test simple type alias generation."""
        from django_matt.codegen.core import TypeAlias

        alias = TypeAlias(name="ID", type="number | string")
        result = alias.to_typescript()
        assert result == "export type ID = number | string"

    def test_generic_type_alias(self):
        """Test generic type alias generation."""
        from django_matt.codegen.core import TypeAlias

        alias = TypeAlias(name="Nullable", type="T | null", generic="T")
        result = alias.to_typescript()
        assert result == "export type Nullable<T> = T | null"


class TestObjectLiteral:
    """Tests for ObjectLiteral code node."""

    def test_empty_object(self):
        """Test empty object generation."""
        from django_matt.codegen.core import ObjectLiteral

        obj = ObjectLiteral()
        result = obj.to_typescript()
        assert result == "{}"

    def test_object_with_properties(self):
        """Test object with properties."""
        from django_matt.codegen.core import ObjectLiteral

        obj = ObjectLiteral(properties={"name": '"John"', "age": "30"}, multiline=False)
        result = obj.to_typescript()
        assert result == '{ name: "John", age: 30 }'


class TestArrayLiteral:
    """Tests for ArrayLiteral code node."""

    def test_empty_array(self):
        """Test empty array generation."""
        from django_matt.codegen.core import ArrayLiteral

        arr = ArrayLiteral()
        result = arr.to_typescript()
        assert result == "[]"

    def test_array_with_items(self):
        """Test array with items."""
        from django_matt.codegen.core import ArrayLiteral

        arr = ArrayLiteral(items=['"a"', '"b"', '"c"'])
        result = arr.to_typescript()
        assert result == '["a", "b", "c"]'


class TestClass:
    """Tests for Class code node."""

    def test_simple_class(self):
        """Test simple class generation."""
        from django_matt.codegen.core import Class, Property

        cls = Class(
            name="User",
            properties=[Property("id", "number")],
        )
        result = cls.to_typescript()
        assert "export class User {" in result
        assert "id: number" in result

    def test_class_extends(self):
        """Test class with extends."""
        from django_matt.codegen.core import Class

        cls = Class(name="Admin", extends="User")
        result = cls.to_typescript()
        assert "export class Admin extends User {" in result

    def test_class_implements(self):
        """Test class with implements."""
        from django_matt.codegen.core import Class

        cls = Class(name="User", implements=["Serializable", "Comparable"])
        result = cls.to_typescript()
        assert "export class User implements Serializable, Comparable {" in result

    def test_abstract_class(self):
        """Test abstract class generation."""
        from django_matt.codegen.core import Class

        cls = Class(name="BaseModel", abstract=True)
        result = cls.to_typescript()
        assert "export abstract class BaseModel {" in result


class TestCodeFile:
    """Tests for CodeFile code node."""

    def test_empty_file(self):
        """Test empty file generation."""
        from django_matt.codegen.core import CodeFile

        file = CodeFile()
        result = file.to_typescript()
        assert result == ""

    def test_file_with_imports(self):
        """Test file with imports."""
        from django_matt.codegen.core import CodeFile, ImportFrom

        file = CodeFile(imports=[ImportFrom("react", ["useState"])])
        result = file.to_typescript()
        assert 'import { useState } from "react"' in result

    def test_file_groups_imports(self):
        """Test that file groups external and internal imports."""
        from django_matt.codegen.core import CodeFile, ImportFrom

        file = CodeFile(
            imports=[
                ImportFrom("./types", ["User"]),
                ImportFrom("react", ["useState"]),
                ImportFrom("@/components", ["Button"]),
            ]
        )
        result = file.to_typescript()
        # External imports should come first
        react_pos = result.find("react")
        types_pos = result.find("./types")
        assert react_pos < types_pos

    def test_file_add_import_deduplicates(self):
        """Test that add_import merges duplicate imports."""
        from django_matt.codegen.core import CodeFile, ImportFrom

        file = CodeFile()
        file.add_import(ImportFrom("react", ["useState"]))
        file.add_import(ImportFrom("react", ["useEffect"]))

        assert len(file.imports) == 1
        assert "useState" in file.imports[0].names
        assert "useEffect" in file.imports[0].names


class TestCodeGenerator:
    """Tests for CodeGenerator class."""

    def test_generator_creation(self):
        """Test creating a CodeGenerator."""
        from django_matt.codegen.core import CodeGenerator

        gen = CodeGenerator(output_dir="./generated")
        assert gen.output_dir == "./generated"
        assert gen.files == {}

    def test_generator_add_file(self):
        """Test adding a file to generator."""
        from django_matt.codegen.core import CodeFile, CodeGenerator

        gen = CodeGenerator()
        file = CodeFile()
        gen.add_file("types.ts", file)

        assert "types.ts" in gen.files
        assert gen.files["types.ts"] is file

    def test_generator_generate(self):
        """Test generating file content."""
        from django_matt.codegen.core import CodeFile, CodeGenerator, Interface

        gen = CodeGenerator()
        file = CodeFile(nodes=[Interface(name="User")])
        gen.add_file("types.ts", file)

        result = gen.generate()
        assert "types.ts" in result
        assert "interface User" in result["types.ts"]


# =============================================================================
# INTROSPECTION TESTS
# =============================================================================


class TestFieldInfo:
    """Tests for FieldInfo dataclass."""

    def test_field_info_is_required(self):
        """Test is_required property."""
        from django_matt.codegen.introspection import FieldInfo

        # Required field
        field = FieldInfo(
            name="email",
            field_type="EmailField",
            python_type="str",
            typescript_type="string",
            nullable=False,
            blank=False,
            has_default=False,
            default_value=None,
            max_length=255,
            choices=None,
            help_text="",
            verbose_name="email",
            validators=[],
            is_primary_key=False,
            is_unique=True,
            is_editable=True,
            is_auto=False,
        )
        assert field.is_required is True

        # Optional field (nullable)
        field.nullable = True
        assert field.is_required is False

        # Optional field (has default)
        field.nullable = False
        field.has_default = True
        assert field.is_required is False

        # Auto field
        field.has_default = False
        field.is_auto = True
        assert field.is_required is False


class TestModelInfo:
    """Tests for ModelInfo dataclass."""

    def test_model_info_full_name(self):
        """Test full_name property."""
        from django_matt.codegen.introspection import ModelInfo

        info = ModelInfo(
            name="User",
            app_label="users",
            verbose_name="user",
            verbose_name_plural="users",
            db_table="users_user",
        )
        assert info.full_name == "users.User"

    def test_model_info_required_fields(self):
        """Test required_fields property."""
        from django_matt.codegen.introspection import FieldInfo, ModelInfo

        def make_field(name, nullable=False, blank=False, has_default=False, is_auto=False):
            return FieldInfo(
                name=name,
                field_type="CharField",
                python_type="str",
                typescript_type="string",
                nullable=nullable,
                blank=blank,
                has_default=has_default,
                default_value=None,
                max_length=255,
                choices=None,
                help_text="",
                verbose_name=name,
                validators=[],
                is_primary_key=False,
                is_unique=False,
                is_editable=True,
                is_auto=is_auto,
            )

        info = ModelInfo(
            name="User",
            app_label="users",
            verbose_name="user",
            verbose_name_plural="users",
            db_table="users_user",
            fields=[
                make_field("id", is_auto=True),
                make_field("email"),  # Required
                make_field("name", blank=True),  # Optional
                make_field("bio", nullable=True),  # Optional
            ],
        )

        required = info.required_fields
        assert len(required) == 1
        assert required[0].name == "email"


class TestModelIntrospector:
    """Tests for ModelIntrospector class."""

    def test_introspector_type_maps(self):
        """Test that type maps exist and have expected entries."""
        from django_matt.codegen.introspection import ModelIntrospector

        # Python type map
        assert ModelIntrospector.PYTHON_TYPE_MAP["IntegerField"] == "int"
        assert ModelIntrospector.PYTHON_TYPE_MAP["CharField"] == "str"
        assert ModelIntrospector.PYTHON_TYPE_MAP["BooleanField"] == "bool"

        # TypeScript type map
        assert ModelIntrospector.TYPESCRIPT_TYPE_MAP["IntegerField"] == "number"
        assert ModelIntrospector.TYPESCRIPT_TYPE_MAP["CharField"] == "string"
        assert ModelIntrospector.TYPESCRIPT_TYPE_MAP["BooleanField"] == "boolean"

    def test_introspector_with_mock_model(self):
        """Test introspector with a mock Django model."""
        from django_matt.codegen.introspection import ModelIntrospector

        # Create mock model
        mock_model = Mock()
        mock_model._meta = Mock()
        mock_model._meta.object_name = "User"
        mock_model._meta.app_label = "users"
        mock_model._meta.verbose_name = "user"
        mock_model._meta.verbose_name_plural = "users"
        mock_model._meta.db_table = "users_user"
        mock_model._meta.ordering = ["-created_at"]
        mock_model._meta.unique_together = []
        mock_model._meta.indexes = []

        # Mock field
        mock_field = Mock()
        mock_field.name = "email"
        mock_field.__class__.__name__ = "CharField"
        mock_field.is_relation = False
        mock_field.column = "email"
        mock_field.null = False
        mock_field.blank = False
        mock_field.has_default = Mock(return_value=False)
        mock_field.default = None
        mock_field.max_length = 255
        mock_field.choices = None
        mock_field.help_text = ""
        mock_field.verbose_name = "email"
        mock_field.validators = []
        mock_field.primary_key = False
        mock_field.unique = True
        mock_field.editable = True

        mock_model._meta.get_fields = Mock(return_value=[mock_field])

        introspector = ModelIntrospector(mock_model)
        info = introspector.introspect()

        assert info.name == "User"
        assert info.app_label == "users"
        assert len(info.fields) == 1
        assert info.fields[0].name == "email"


# =============================================================================
# TYPESCRIPT GENERATOR TESTS
# =============================================================================


class TestDjangoFieldToTypescript:
    """Tests for django_field_to_typescript function."""

    def test_basic_types(self):
        """Test basic field type conversion."""
        from django_matt.codegen.introspection import FieldInfo
        from django_matt.codegen.typescript import django_field_to_typescript

        def make_field(field_type, nullable=False, choices=None):
            return FieldInfo(
                name="test",
                field_type=field_type,
                python_type="",
                typescript_type="",
                nullable=nullable,
                blank=False,
                has_default=False,
                default_value=None,
                max_length=None,
                choices=choices,
                help_text="",
                verbose_name="",
                validators=[],
                is_primary_key=False,
                is_unique=False,
                is_editable=True,
                is_auto=False,
            )

        assert django_field_to_typescript(make_field("IntegerField")) == "number"
        assert django_field_to_typescript(make_field("CharField")) == "string"
        assert django_field_to_typescript(make_field("BooleanField")) == "boolean"

    def test_nullable_types(self):
        """Test nullable field type conversion."""
        from django_matt.codegen.introspection import FieldInfo
        from django_matt.codegen.typescript import django_field_to_typescript

        field = FieldInfo(
            name="test",
            field_type="CharField",
            python_type="",
            typescript_type="",
            nullable=True,
            blank=False,
            has_default=False,
            default_value=None,
            max_length=None,
            choices=None,
            help_text="",
            verbose_name="",
            validators=[],
            is_primary_key=False,
            is_unique=False,
            is_editable=True,
            is_auto=False,
        )

        result = django_field_to_typescript(field)
        assert result == "string | null"

    def test_choices_type(self):
        """Test field with choices conversion."""
        from django_matt.codegen.introspection import FieldInfo
        from django_matt.codegen.typescript import django_field_to_typescript

        field = FieldInfo(
            name="status",
            field_type="CharField",
            python_type="",
            typescript_type="",
            nullable=False,
            blank=False,
            has_default=False,
            default_value=None,
            max_length=None,
            choices=[("active", "Active"), ("inactive", "Inactive")],
            help_text="",
            verbose_name="",
            validators=[],
            is_primary_key=False,
            is_unique=False,
            is_editable=True,
            is_auto=False,
        )

        result = django_field_to_typescript(field)
        assert '"active"' in result
        assert '"inactive"' in result
        assert " | " in result


class TestDjangoFieldToZod:
    """Tests for django_field_to_zod function."""

    def test_basic_zod_types(self):
        """Test basic field to Zod conversion."""
        from django_matt.codegen.introspection import FieldInfo
        from django_matt.codegen.typescript import django_field_to_zod

        def make_field(field_type, nullable=False, max_length=None, is_required=True):
            return FieldInfo(
                name="test",
                field_type=field_type,
                python_type="",
                typescript_type="",
                nullable=nullable,
                blank=not is_required,
                has_default=not is_required,
                default_value=None,
                max_length=max_length,
                choices=None,
                help_text="",
                verbose_name="",
                validators=[],
                is_primary_key=False,
                is_unique=False,
                is_editable=True,
                is_auto=False,
            )

        assert "z.number().int()" in django_field_to_zod(make_field("IntegerField"))
        assert "z.string()" in django_field_to_zod(make_field("CharField"))
        assert "z.boolean()" in django_field_to_zod(make_field("BooleanField"))
        assert "z.string().email()" in django_field_to_zod(make_field("EmailField"))
        assert "z.string().url()" in django_field_to_zod(make_field("URLField"))
        assert "z.string().uuid()" in django_field_to_zod(make_field("UUIDField"))

    def test_zod_with_max_length(self):
        """Test Zod schema with max length."""
        from django_matt.codegen.introspection import FieldInfo
        from django_matt.codegen.typescript import django_field_to_zod

        field = FieldInfo(
            name="test",
            field_type="CharField",
            python_type="",
            typescript_type="",
            nullable=False,
            blank=False,
            has_default=False,
            default_value=None,
            max_length=100,
            choices=None,
            help_text="",
            verbose_name="",
            validators=[],
            is_primary_key=False,
            is_unique=False,
            is_editable=True,
            is_auto=False,
        )

        result = django_field_to_zod(field)
        assert "z.string()" in result
        assert ".max(100)" in result


class TestDjangoToTsMapping:
    """Tests for Django to TypeScript type mappings."""

    def test_django_to_ts_mapping_exists(self):
        """Test that DJANGO_TO_TS mapping has expected entries."""
        from django_matt.codegen.typescript import DJANGO_TO_TS

        # Numeric types
        assert DJANGO_TO_TS["IntegerField"] == "number"
        assert DJANGO_TO_TS["FloatField"] == "number"
        assert DJANGO_TO_TS["BigIntegerField"] == "number"

        # String types
        assert DJANGO_TO_TS["CharField"] == "string"
        assert DJANGO_TO_TS["TextField"] == "string"
        assert DJANGO_TO_TS["EmailField"] == "string"
        assert DJANGO_TO_TS["UUIDField"] == "string"

        # Boolean
        assert DJANGO_TO_TS["BooleanField"] == "boolean"

        # Date/time (as strings in JSON)
        assert DJANGO_TO_TS["DateField"] == "string"
        assert DJANGO_TO_TS["DateTimeField"] == "string"

        # JSON
        assert DJANGO_TO_TS["JSONField"] == "Record<string, unknown>"


# =============================================================================
# CONFIG TESTS
# =============================================================================


class TestModelConfig:
    """Tests for ModelConfig dataclass."""

    def test_from_string(self):
        """Test creating ModelConfig from string."""
        from django_matt.codegen.config import ModelConfig

        config = ModelConfig.from_string("users.User")
        assert config.path == "users.User"
        assert config.generate_crud is True
        assert config.generate_forms is True

    def test_from_dict(self):
        """Test creating ModelConfig from dict."""
        from django_matt.codegen.config import ModelConfig

        config = ModelConfig.from_dict(
            {
                "path": "posts.Post",
                "exclude_fields": ["internal_notes"],
                "generate_crud": False,
                "display_name": "Blog Post",
            }
        )
        assert config.path == "posts.Post"
        assert "internal_notes" in config.exclude_fields
        assert config.generate_crud is False
        assert config.display_name == "Blog Post"


class TestCodegenConfig:
    """Tests for CodegenConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        from django_matt.codegen.config import CodegenConfig

        config = CodegenConfig()
        assert config.framework == "react"
        assert config.ui_library == "shadcn"
        assert config.use_typescript is True
        assert config.generate_zod is True

    def test_from_dict(self):
        """Test creating config from dict."""
        from django_matt.codegen.config import CodegenConfig

        config = CodegenConfig.from_dict(
            {
                "framework": "svelte",
                "ui_library": "tailwind",
                "output_dir": "./frontend/generated",
                "models": ["users.User", "posts.Post"],
            }
        )
        assert config.framework == "svelte"
        assert config.ui_library == "tailwind"
        assert len(config.models) == 2

    def test_get_model_configs(self):
        """Test get_model_configs method."""
        from django_matt.codegen.config import CodegenConfig, ModelConfig

        config = CodegenConfig(
            models=[
                "users.User",
                {"path": "posts.Post", "generate_forms": False},
            ]
        )
        model_configs = config.get_model_configs()

        assert len(model_configs) == 2
        assert all(isinstance(mc, ModelConfig) for mc in model_configs)
        assert model_configs[0].path == "users.User"
        assert model_configs[1].path == "posts.Post"
        assert model_configs[1].generate_forms is False

    def test_get_output_path(self):
        """Test get_output_path method."""
        from django_matt.codegen.config import CodegenConfig

        config = CodegenConfig(output_dir="./frontend/src/generated")
        path = config.get_output_path()

        assert isinstance(path, Path)
        assert str(path) == "frontend/src/generated"


class TestFindProjectRoot:
    """Tests for find_project_root function."""

    def test_find_project_root_with_manage_py(self):
        """Test finding project root with manage.py."""
        from django_matt.codegen.config import find_project_root

        # This should find the project root (current directory has manage.py or markers)
        root = find_project_root()
        assert isinstance(root, Path)


class TestCreateConfigFile:
    """Tests for create_config_file function."""

    def test_create_config_file_content(self):
        """Test config file content generation."""
        from django_matt.codegen.config import create_config_file

        content = create_config_file(
            framework="react",
            ui_library="shadcn",
            output_dir="./frontend/generated",
            models=["users.User", "posts.Post"],
        )

        assert 'framework": "react"' in content
        assert 'ui_library": "shadcn"' in content
        assert "users.User" in content
        assert "posts.Post" in content
        assert "CODEGEN = {" in content

    def test_create_config_file_writes_to_path(self):
        """Test that config file is written to path."""
        from django_matt.codegen.config import create_config_file

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "django_matt_codegen.py"
            create_config_file(output_path=output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "CODEGEN" in content


# =============================================================================
# REACT GENERATOR TESTS
# =============================================================================


class TestReactHelperFunctions:
    """Tests for React generator helper functions."""

    def test_to_camel_case(self):
        """Test snake_case to camelCase conversion."""
        from django_matt.codegen.react import _to_camel_case

        assert _to_camel_case("user_name") == "userName"
        assert _to_camel_case("first_name") == "firstName"
        assert _to_camel_case("id") == "id"

    def test_to_pascal_case(self):
        """Test snake_case to PascalCase conversion."""
        from django_matt.codegen.react import _to_pascal_case

        assert _to_pascal_case("user_name") == "UserName"
        assert _to_pascal_case("first_name") == "FirstName"
        assert _to_pascal_case("user") == "User"

    def test_pluralize(self):
        """Test simple pluralization."""
        from django_matt.codegen.react import _pluralize

        assert _pluralize("user") == "users"
        assert _pluralize("category") == "categories"
        assert _pluralize("status") == "statuses"


class TestGenerateReactHooks:
    """Tests for generate_react_hooks function."""

    def test_generates_hooks_with_mock_model(self):
        """Test generating React hooks from mock model."""
        from django_matt.codegen.react import generate_react_hooks

        # Create mock model
        mock_model = Mock()
        mock_model._meta = Mock()
        mock_model._meta.object_name = "User"
        mock_model._meta.app_label = "users"
        mock_model._meta.verbose_name = "user"
        mock_model._meta.verbose_name_plural = "users"
        mock_model._meta.db_table = "users_user"
        mock_model._meta.ordering = []
        mock_model._meta.unique_together = []
        mock_model._meta.indexes = []
        mock_model._meta.get_fields = Mock(return_value=[])

        result = generate_react_hooks(mock_model, api_base="/api")

        assert "useUser" in result
        assert "useUsers" in result
        assert "useCreateUser" in result
        assert "useUpdateUser" in result
        assert "useDeleteUser" in result
        assert "userKeys" in result
        assert "@tanstack/react-query" in result

    def test_hooks_without_mutations(self):
        """Test generating hooks without mutations."""
        from django_matt.codegen.react import generate_react_hooks

        mock_model = Mock()
        mock_model._meta = Mock()
        mock_model._meta.object_name = "Post"
        mock_model._meta.app_label = "posts"
        mock_model._meta.verbose_name = "post"
        mock_model._meta.verbose_name_plural = "posts"
        mock_model._meta.db_table = "posts_post"
        mock_model._meta.ordering = []
        mock_model._meta.unique_together = []
        mock_model._meta.indexes = []
        mock_model._meta.get_fields = Mock(return_value=[])

        result = generate_react_hooks(mock_model, include_mutations=False)

        assert "usePost" in result
        assert "usePosts" in result
        assert "useCreatePost" not in result
        assert "useUpdatePost" not in result
        assert "useDeletePost" not in result


class TestGenerateReactForm:
    """Tests for generate_react_form function."""

    def test_generates_form_component(self):
        """Test generating form component."""
        from django_matt.codegen.react import generate_react_form

        # Create mock model with fields
        mock_model = Mock()
        mock_model._meta = Mock()
        mock_model._meta.object_name = "User"
        mock_model._meta.app_label = "users"
        mock_model._meta.verbose_name = "user"
        mock_model._meta.verbose_name_plural = "users"
        mock_model._meta.db_table = "users_user"
        mock_model._meta.ordering = []
        mock_model._meta.unique_together = []
        mock_model._meta.indexes = []

        # Mock email field
        mock_field = Mock()
        mock_field.name = "email"
        mock_field.__class__.__name__ = "EmailField"
        mock_field.is_relation = False
        mock_field.column = "email"
        mock_field.null = False
        mock_field.blank = False
        mock_field.has_default = Mock(return_value=False)
        mock_field.default = None
        mock_field.max_length = 255
        mock_field.choices = None
        mock_field.help_text = ""
        mock_field.verbose_name = "email"
        mock_field.validators = []
        mock_field.primary_key = False
        mock_field.unique = True
        mock_field.editable = True

        mock_model._meta.get_fields = Mock(return_value=[mock_field])

        result = generate_react_form(mock_model, ui_library="shadcn")

        assert "UserForm" in result
        assert "react-hook-form" in result
        assert "zodResolver" in result
        assert "@/components/ui" in result


class TestGenerateReactList:
    """Tests for generate_react_list function."""

    def test_generates_list_component(self):
        """Test generating list component."""
        from django_matt.codegen.react import generate_react_list

        mock_model = Mock()
        mock_model._meta = Mock()
        mock_model._meta.object_name = "User"
        mock_model._meta.app_label = "users"
        mock_model._meta.verbose_name = "user"
        mock_model._meta.verbose_name_plural = "users"
        mock_model._meta.db_table = "users_user"
        mock_model._meta.ordering = []
        mock_model._meta.unique_together = []
        mock_model._meta.indexes = []

        # Mock field
        mock_field = Mock()
        mock_field.name = "email"
        mock_field.__class__.__name__ = "EmailField"
        mock_field.is_relation = False
        mock_field.column = "email"
        mock_field.null = False
        mock_field.blank = False
        mock_field.has_default = Mock(return_value=False)
        mock_field.default = None
        mock_field.max_length = 255
        mock_field.choices = None  # Must be None, not Mock
        mock_field.help_text = ""
        mock_field.verbose_name = "email"
        mock_field.validators = []
        mock_field.unique = True
        mock_field.editable = True
        mock_field.primary_key = False

        mock_model._meta.get_fields = Mock(return_value=[mock_field])

        result = generate_react_list(mock_model, ui_library="shadcn")

        assert "UserList" in result
        assert "useUsers" in result
        assert "Table" in result
        assert "Skeleton" in result


class TestGenerateReactDetail:
    """Tests for generate_react_detail function."""

    def test_generates_detail_component(self):
        """Test generating detail component."""
        from django_matt.codegen.react import generate_react_detail

        mock_model = Mock()
        mock_model._meta = Mock()
        mock_model._meta.object_name = "User"
        mock_model._meta.app_label = "users"
        mock_model._meta.verbose_name = "user"
        mock_model._meta.verbose_name_plural = "users"
        mock_model._meta.db_table = "users_user"
        mock_model._meta.ordering = []
        mock_model._meta.unique_together = []
        mock_model._meta.indexes = []

        mock_field = Mock()
        mock_field.name = "email"
        mock_field.__class__.__name__ = "EmailField"
        mock_field.is_relation = False
        mock_field.column = "email"
        mock_field.null = False
        mock_field.blank = False
        mock_field.verbose_name = "email"
        mock_field.has_default = Mock(return_value=False)
        mock_field.default = None
        mock_field.max_length = 255
        mock_field.choices = None  # Must be None, not Mock
        mock_field.help_text = ""
        mock_field.validators = []
        mock_field.unique = True
        mock_field.editable = True
        mock_field.primary_key = False

        mock_model._meta.get_fields = Mock(return_value=[mock_field])

        result = generate_react_detail(mock_model, ui_library="shadcn")

        assert "UserDetail" in result
        assert "useUser" in result
        assert "Card" in result


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestCodegenIntegration:
    """Integration tests for code generation."""

    def test_full_interface_generation(self):
        """Test generating a complete TypeScript interface."""
        from django_matt.codegen.core import CodeFile, Interface, Property

        file = CodeFile()
        file.header_comment = "Auto-generated types"
        file.add_node(
            Interface(
                name="User",
                properties=[
                    Property("id", "number", readonly=True),
                    Property("email", "string"),
                    Property("name", "string", optional=True),
                    Property("createdAt", "string", readonly=True),
                ],
                comment="User model",
            )
        )

        result = file.to_typescript()

        assert "/** Auto-generated types */" in result
        assert "export interface User {" in result
        assert "readonly id: number" in result
        assert "email: string" in result
        assert "name?: string" in result

    def test_code_generator_write_files(self):
        """Test writing generated files to disk."""
        from django_matt.codegen.core import CodeFile, CodeGenerator, Interface

        with tempfile.TemporaryDirectory() as tmpdir:
            gen = CodeGenerator(output_dir=tmpdir)
            file = CodeFile(nodes=[Interface(name="User")])
            gen.add_file("types.ts", file)

            written = gen.write_files()

            assert len(written) == 1
            assert os.path.exists(written[0])

            with open(written[0]) as f:
                content = f.read()
                assert "interface User" in content
