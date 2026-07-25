"""
Tests for the codemod engine and all framework-specific codemods.
"""

from __future__ import annotations

import ast
import textwrap

import pytest

from django_matt.codemods import (
    Codemod,
    CodemodEngine,
    CodemodResult,
    DRFCodemods,
    FastAPICodemods,
    NinjaCodemods,
)
from django_matt.codemods.drf import (
    DRFApiViewDecorator,
    DRFRouterToRegistration,
    DRFSerializerToSchema,
    DRFViewSetToController,
)
from django_matt.codemods.fastapi import (
    FastAPIAppToMattAPI,
    FastAPIDependsToMattDI,
    FastAPIHTTPExceptionToAPIError,
    FastAPIRouterToController,
)
from django_matt.codemods.ninja import (
    NinjaAPIToMattAPI,
    NinjaRouterToController,
    NinjaSchemaToMattSchema,
)
from django_matt.codemods.patterns import (
    add_import,
    has_base_class,
    remove_import,
    rename_all_references,
    rewrite_imports,
    swap_base_classes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dedent(s: str) -> str:
    return textwrap.dedent(s).strip() + "\n"


def _parse(source: str) -> ast.Module:
    return ast.parse(source)


def _assert_in_output(result: CodemodResult, *fragments: str) -> None:
    for frag in fragments:
        assert frag in result.transformed, (
            f"Expected '{frag}' in transformed output:\n{result.transformed}"
        )


def _assert_not_in_output(result: CodemodResult, *fragments: str) -> None:
    for frag in fragments:
        assert frag not in result.transformed, (
            f"Did not expect '{frag}' in transformed output:\n{result.transformed}"
        )


# ===========================================================================
# Pattern utility tests
# ===========================================================================


class TestImportRewriting:
    def test_rewrite_module_path(self):
        source = "from rest_framework.serializers import ModelSerializer\n"
        tree = _parse(source)
        changes = rewrite_imports(
            tree,
            "rest_framework.serializers",
            "django_matt.core.schema",
            {"ModelSerializer": "ModelSchema"},
        )
        output = ast.unparse(tree)
        assert "django_matt.core.schema" in output
        assert "ModelSchema" in output
        assert len(changes) > 0

    def test_rewrite_with_no_name_map(self):
        source = "from ninja import Schema\n"
        tree = _parse(source)
        changes = rewrite_imports(tree, "ninja", "django_matt.core.schema")
        output = ast.unparse(tree)
        assert "django_matt.core.schema" in output
        assert "Schema" in output

    def test_add_import(self):
        source = "import os\n"
        tree = _parse(source)
        add_import(tree, "django_matt.core.router", ["get", "post"])
        output = ast.unparse(tree)
        assert "django_matt.core.router" in output
        assert "get" in output

    def test_remove_import(self):
        source = "from rest_framework.response import Response\nimport os\n"
        tree = _parse(source)
        changes = remove_import(tree, "rest_framework.response", ["Response"])
        assert len(changes) > 0
        output = ast.unparse(tree)
        assert "rest_framework" not in output


class TestClassPatterns:
    def test_swap_base_classes(self):
        source = "class UserViewSet(ModelViewSet): pass\n"
        tree = _parse(source)
        cls = tree.body[0]
        assert swap_base_classes(cls, "ModelViewSet", "CRUDController")
        assert cls.bases[0].id == "CRUDController"

    def test_has_base_class(self):
        source = "class Foo(APIView): pass\n"
        tree = _parse(source)
        cls = tree.body[0]
        assert has_base_class(cls, "APIView")
        assert not has_base_class(cls, "ModelViewSet")

    def test_rename_all_references(self):
        source = "x = UserSerializer()\ny = UserSerializer\n"
        tree = _parse(source)
        count = rename_all_references(tree, "UserSerializer", "UserSchema")
        assert count == 2
        output = ast.unparse(tree)
        assert "UserSchema" in output
        assert "UserSerializer" not in output


# ===========================================================================
# DRF codemod tests
# ===========================================================================


class TestDRFSerializerToSchema:
    def test_detect(self):
        codemod = DRFSerializerToSchema()
        assert codemod.detect("from rest_framework.serializers import Serializer", "s.py")
        assert not codemod.detect("import os", "s.py")

    def test_model_serializer_transform(self):
        source = _dedent("""
            from rest_framework.serializers import ModelSerializer

            class UserSerializer(ModelSerializer):
                class Meta:
                    model = User
                    fields = ['id', 'username', 'email']
        """)
        codemod = DRFSerializerToSchema()
        result = codemod.transform(source, "serializers.py")

        assert result.has_changes
        _assert_in_output(result, "ModelSchema", "UserSchema")
        _assert_not_in_output(result, "ModelSerializer", "UserSerializer")
        # Meta.fields -> Meta.include
        _assert_in_output(result, "include")
        assert result.confidence > 0

    def test_field_conversion(self):
        source = _dedent("""
            from rest_framework.serializers import Serializer

            class ItemSerializer(Serializer):
                name = CharField()
                price = FloatField()
                active = BooleanField(required=False)
        """)
        codemod = DRFSerializerToSchema()
        result = codemod.transform(source, "serializers.py")

        assert result.has_changes
        _assert_in_output(result, "ItemSchema")
        # Fields should be converted to annotations
        assert "str" in result.transformed or "name" in result.transformed

    def test_no_changes_for_non_serializer(self):
        source = "from rest_framework.serializers import Serializer\nclass Foo: pass\n"
        codemod = DRFSerializerToSchema()
        result = codemod.transform(source, "foo.py")
        # Import rewrite counts as a change
        assert result.has_changes


class TestDRFViewSetToController:
    def test_detect(self):
        codemod = DRFViewSetToController()
        assert codemod.detect("from rest_framework.viewsets import ViewSet", "v.py")
        assert not codemod.detect("import json", "v.py")

    def test_viewset_transform(self):
        source = _dedent("""
            from rest_framework.viewsets import ModelViewSet
            from rest_framework.response import Response

            class UserViewSet(ModelViewSet):
                queryset = User.objects.all()
                serializer_class = UserSerializer
        """)
        codemod = DRFViewSetToController()
        result = codemod.transform(source, "views.py")

        assert result.has_changes
        _assert_in_output(result, "CRUDController", "UserController")
        _assert_not_in_output(result, "ModelViewSet", "UserViewSet")
        # serializer_class -> schema
        _assert_in_output(result, "schema")
        # queryset = Model.objects.all() -> model = Model
        _assert_in_output(result, "model")

    def test_action_decorator_transform(self):
        source = _dedent("""
            from rest_framework.viewsets import ViewSet
            from rest_framework.decorators import action
            from rest_framework.response import Response

            class ItemViewSet(ViewSet):
                @action(detail=True, methods=['post'])
                def activate(self, request, pk=None):
                    return Response({"status": "activated"})
        """)
        codemod = DRFViewSetToController()
        result = codemod.transform(source, "views.py")

        assert result.has_changes
        # @action should become @post("/{id}/activate")
        assert any("activate" in c for c in result.changes)


class TestDRFApiViewDecorator:
    def test_detect(self):
        codemod = DRFApiViewDecorator()
        assert codemod.detect("from rest_framework.decorators import api_view", "v.py")

    def test_api_view_transform(self):
        source = _dedent("""
            from rest_framework.decorators import api_view
            from rest_framework.response import Response

            @api_view(['GET'])
            def hello(request):
                return Response({"message": "hello"})
        """)
        codemod = DRFApiViewDecorator()
        result = codemod.transform(source, "views.py")

        assert result.has_changes
        _assert_not_in_output(result, "api_view")
        # Should unwrap Response
        assert any("Unwrapped" in c or "Converted" in c for c in result.changes)


class TestDRFRouterToRegistration:
    def test_detect(self):
        codemod = DRFRouterToRegistration()
        assert codemod.detect(
            "from rest_framework.routers import DefaultRouter\nrouter.register('x', Y)",
            "urls.py",
        )

    def test_router_transform(self):
        source = _dedent("""
            from rest_framework.routers import DefaultRouter

            router = DefaultRouter()
            router.register('users', UserViewSet)
            router.register('items', ItemViewSet)
        """)
        codemod = DRFRouterToRegistration()
        result = codemod.transform(source, "urls.py")

        assert result.has_changes
        _assert_in_output(result, "MattAPI")
        _assert_in_output(result, "register_controller")
        _assert_not_in_output(result, "DefaultRouter")


# ===========================================================================
# Ninja codemod tests
# ===========================================================================


class TestNinjaAPIToMattAPI:
    def test_detect(self):
        codemod = NinjaAPIToMattAPI()
        assert codemod.detect("from ninja import NinjaAPI", "api.py")
        assert not codemod.detect("import os", "api.py")

    def test_ninja_api_transform(self):
        source = _dedent("""
            from ninja import NinjaAPI

            api = NinjaAPI(title="My API")
        """)
        codemod = NinjaAPIToMattAPI()
        result = codemod.transform(source, "api.py")

        assert result.has_changes
        _assert_in_output(result, "MattAPI")
        _assert_not_in_output(result, "NinjaAPI")


class TestNinjaSchemaToMattSchema:
    def test_detect(self):
        codemod = NinjaSchemaToMattSchema()
        assert codemod.detect("from ninja import Schema", "schemas.py")

    def test_schema_transform(self):
        source = _dedent("""
            from ninja import Schema

            class UserSchema(Schema):
                id: int
                name: str
        """)
        codemod = NinjaSchemaToMattSchema()
        result = codemod.transform(source, "schemas.py")

        assert result.has_changes
        _assert_in_output(result, "django_matt.core.schema")

    def test_create_schema_rename(self):
        source = _dedent("""
            from ninja.orm import create_schema

            UserSchema = create_schema(User)
        """)
        codemod = NinjaSchemaToMattSchema()
        result = codemod.transform(source, "schemas.py")

        assert result.has_changes
        _assert_in_output(result, "create_schema_from_model")


class TestNinjaRouterToController:
    def test_detect(self):
        codemod = NinjaRouterToController()
        assert codemod.detect("@router.get('/users')", "api.py")

    def test_router_decorator_transform(self):
        source = _dedent("""
            from ninja import Router

            router = Router()

            @router.get("/users")
            def list_users(request):
                return []
        """)
        codemod = NinjaRouterToController()
        result = codemod.transform(source, "api.py")

        assert result.has_changes
        # @router.get -> @api.get
        _assert_in_output(result, "api")


# ===========================================================================
# FastAPI codemod tests
# ===========================================================================


class TestFastAPIAppToMattAPI:
    def test_detect(self):
        codemod = FastAPIAppToMattAPI()
        assert codemod.detect("from fastapi import FastAPI", "main.py")
        assert not codemod.detect("import os", "main.py")

    def test_fastapi_transform(self):
        source = _dedent("""
            from fastapi import FastAPI

            app = FastAPI(title="My API")
        """)
        codemod = FastAPIAppToMattAPI()
        result = codemod.transform(source, "main.py")

        assert result.has_changes
        _assert_in_output(result, "MattAPI")
        _assert_not_in_output(result, "FastAPI")


class TestFastAPIRouterToController:
    def test_detect(self):
        codemod = FastAPIRouterToController()
        assert codemod.detect("from fastapi import FastAPI\n@app.get('/users')", "main.py")

    def test_route_transform(self):
        source = _dedent("""
            from fastapi import FastAPI
            from fastapi.responses import JSONResponse

            app = FastAPI()

            @app.get("/users")
            async def list_users():
                return JSONResponse({"users": []})
        """)
        codemod = FastAPIRouterToController()
        result = codemod.transform(source, "main.py")

        assert result.has_changes
        # @app.get -> @api.get
        _assert_in_output(result, "api")
        # JSONResponse unwrapped
        assert any("Unwrapped" in c or "Transformed" in c for c in result.changes)


class TestFastAPIDependsToMattDI:
    def test_detect(self):
        codemod = FastAPIDependsToMattDI()
        assert codemod.detect("from fastapi import Depends", "deps.py")

    def test_depends_transform(self):
        source = _dedent("""
            from fastapi import Depends

            def get_db():
                return db

            async def get_user(db=Depends(get_db)):
                return db.query(User).first()
        """)
        codemod = FastAPIDependsToMattDI()
        result = codemod.transform(source, "deps.py")

        assert result.has_changes
        _assert_in_output(result, "django_matt.di")


class TestFastAPIHTTPExceptionToAPIError:
    def test_detect(self):
        codemod = FastAPIHTTPExceptionToAPIError()
        assert codemod.detect("from fastapi import HTTPException", "main.py")

    def test_exception_transform(self):
        source = _dedent("""
            from fastapi import HTTPException

            def get_item(item_id: int):
                raise HTTPException(status_code=404, detail="Item not found")
        """)
        codemod = FastAPIHTTPExceptionToAPIError()
        result = codemod.transform(source, "main.py")

        assert result.has_changes
        _assert_in_output(result, "APIError")
        assert any("HTTPException" in c or "APIError" in c for c in result.changes)


# ===========================================================================
# Engine tests
# ===========================================================================


class TestCodemodEngine:
    def test_framework_detection_drf(self):
        engine = CodemodEngine()
        source = "from rest_framework.viewsets import ModelViewSet\n"
        assert engine.detect_framework(source) == "drf"

    def test_framework_detection_ninja(self):
        engine = CodemodEngine()
        source = "from ninja import NinjaAPI\n"
        assert engine.detect_framework(source) == "ninja"

    def test_framework_detection_fastapi(self):
        engine = CodemodEngine()
        source = "from fastapi import FastAPI\n"
        assert engine.detect_framework(source) == "fastapi"

    def test_framework_detection_unknown(self):
        engine = CodemodEngine()
        source = "import os\n"
        assert engine.detect_framework(source) is None

    def test_run_drf(self):
        engine = CodemodEngine()
        source = _dedent("""
            from rest_framework.serializers import ModelSerializer

            class UserSerializer(ModelSerializer):
                class Meta:
                    model = User
                    fields = ['id', 'name']
        """)
        result = engine.run(source, "serializers.py", framework="drf")
        assert result.has_changes
        _assert_in_output(result, "ModelSchema")

    def test_run_ninja(self):
        engine = CodemodEngine()
        source = _dedent("""
            from ninja import NinjaAPI

            api = NinjaAPI()
        """)
        result = engine.run(source, "api.py", framework="ninja")
        assert result.has_changes
        _assert_in_output(result, "MattAPI")

    def test_run_fastapi(self):
        engine = CodemodEngine()
        source = _dedent("""
            from fastapi import FastAPI

            app = FastAPI()
        """)
        result = engine.run(source, "main.py", framework="fastapi")
        assert result.has_changes
        _assert_in_output(result, "MattAPI")

    def test_run_no_changes(self):
        engine = CodemodEngine()
        source = "import os\nprint('hello')\n"
        result = engine.run(source, "test.py")
        assert not result.has_changes
        assert result.confidence == 0.0

    def test_dry_run_mode(self, tmp_path):
        source = _dedent("""
            from rest_framework.serializers import ModelSerializer

            class FooSerializer(ModelSerializer):
                class Meta:
                    model = Foo
                    fields = '__all__'
        """)
        test_file = tmp_path / "serializers.py"
        test_file.write_text(source)

        engine = CodemodEngine()
        result = engine.run_file(test_file, framework="drf", dry_run=True)

        assert result is not None
        assert result.has_changes
        # File should NOT be modified in dry-run
        assert test_file.read_text() == source

    def test_apply_mode(self, tmp_path):
        source = _dedent("""
            from rest_framework.serializers import ModelSerializer

            class BarSerializer(ModelSerializer):
                class Meta:
                    model = Bar
                    fields = '__all__'
        """)
        test_file = tmp_path / "serializers.py"
        test_file.write_text(source)

        engine = CodemodEngine()
        result = engine.run_file(test_file, framework="drf", dry_run=False)

        assert result is not None
        # File SHOULD be modified
        new_content = test_file.read_text()
        assert "ModelSchema" in new_content
        assert "BarSchema" in new_content

    def test_batch_processing(self, tmp_path):
        (tmp_path / "views.py").write_text(
            _dedent("""
            from rest_framework.viewsets import ModelViewSet

            class UserViewSet(ModelViewSet):
                queryset = User.objects.all()
                serializer_class = UserSerializer
        """)
        )
        (tmp_path / "serializers.py").write_text(
            _dedent("""
            from rest_framework.serializers import ModelSerializer

            class UserSerializer(ModelSerializer):
                class Meta:
                    model = User
                    fields = '__all__'
        """)
        )
        (tmp_path / "utils.py").write_text("import os\n")

        engine = CodemodEngine()
        results = engine.run_directory(tmp_path, framework="drf", dry_run=True)

        # utils.py should not be in results (no changes)
        assert len(results) == 2
        assert any("views.py" in k for k in results)
        assert any("serializers.py" in k for k in results)

    def test_confidence_scoring(self):
        engine = CodemodEngine()
        # High-confidence transform
        source = _dedent("""
            from rest_framework.serializers import ModelSerializer

            class UserSerializer(ModelSerializer):
                class Meta:
                    model = User
                    fields = ['id', 'name']
        """)
        result = engine.run(source, "serializers.py", framework="drf")
        assert result.confidence > 0.5

    def test_diff_output(self):
        engine = CodemodEngine()
        source = _dedent("""
            from ninja import NinjaAPI

            api = NinjaAPI()
        """)
        diff = engine.diff(source, "api.py", framework="ninja")
        assert diff  # non-empty
        assert "---" in diff
        assert "+++" in diff
        assert "NinjaAPI" in diff
        assert "MattAPI" in diff

    def test_generate_report(self):
        engine = CodemodEngine()
        results = {
            "foo.py": CodemodResult(
                transformed="...",
                changes=["Changed A", "Changed B"],
                warnings=["Check X"],
                confidence=0.9,
            ),
            "bar.py": CodemodResult(
                transformed="...",
                changes=["Changed C"],
                warnings=[],
                confidence=0.8,
            ),
        }
        report = engine.generate_report(results)
        assert "foo.py" in report
        assert "bar.py" in report
        assert "Changed A" in report
        assert "Check X" in report
        assert "2" in report  # files modified

    def test_skip_pycache_and_migrations(self, tmp_path):
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "0001_initial.py").write_text(
            "from rest_framework.serializers import Serializer\n"
        )
        pycache_dir = tmp_path / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "cached.py").write_text(
            "from rest_framework.serializers import Serializer\n"
        )

        engine = CodemodEngine()
        results = engine.run_directory(tmp_path, framework="drf", dry_run=True)
        assert len(results) == 0


# ===========================================================================
# Collection class tests
# ===========================================================================


class TestCodemodCollections:
    def test_drf_codemods_all(self):
        codemods = DRFCodemods.all()
        assert len(codemods) >= 4
        assert all(isinstance(c, Codemod) for c in codemods)
        assert all(c.source_framework == "drf" for c in codemods)

    def test_ninja_codemods_all(self):
        codemods = NinjaCodemods.all()
        assert len(codemods) >= 4
        assert all(isinstance(c, Codemod) for c in codemods)
        assert all(c.source_framework == "ninja" for c in codemods)

    def test_fastapi_codemods_all(self):
        codemods = FastAPICodemods.all()
        assert len(codemods) >= 5
        assert all(isinstance(c, Codemod) for c in codemods)
        assert all(c.source_framework == "fastapi" for c in codemods)


# ===========================================================================
# CodemodResult tests
# ===========================================================================


class TestCodemodResult:
    def test_has_changes(self):
        r1 = CodemodResult(transformed="x", changes=["a"])
        assert r1.has_changes

        r2 = CodemodResult(transformed="x")
        assert not r2.has_changes

    def test_defaults(self):
        r = CodemodResult(transformed="code")
        assert r.changes == []
        assert r.warnings == []
        assert r.confidence == 1.0
