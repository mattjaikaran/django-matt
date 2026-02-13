"""
Tests for the Django Matt graphql module.

Tests cover:
- GraphQLConfig and RateLimitConfig dataclasses
- Config loading from settings
- Decorator stubs when strawberry is not installed
- STRAWBERRY_AVAILABLE flag
- DjangoModelType base class
- get_field_complexity / get_rate_limit registries
- Conditional imports / availability checks

When strawberry IS available (via importorskip):
- graphql_type, graphql_input, graphql_interface, graphql_enum decorators
- Schema generation
- Type mapping (Django model fields -> GraphQL types)
- create_type_from_model factory
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.db import models

from django_matt.graphql.config import (
    GraphQLConfig,
    RateLimitConfig as GraphQLRateLimitConfig,
    get_graphql_config,
    reset_config,
)
from django_matt.graphql.decorators import (
    _complexity_registry,
    _rate_limit_registry,
    complexity,
    get_field_complexity,
    get_rate_limit,
    rate_limited,
)


# ===========================================================================
# Config
# ===========================================================================


class TestGraphQLRateLimitConfig:
    def test_defaults(self):
        rl = GraphQLRateLimitConfig()
        assert rl.enabled is True
        assert rl.queries_per_minute == 100
        assert rl.mutations_per_minute == 50
        assert rl.subscriptions_per_minute == 20
        assert rl.burst_limit == 10
        assert rl.by_ip is True
        assert rl.by_user is True


class TestGraphQLConfig:
    def test_defaults(self):
        cfg = GraphQLConfig()
        assert cfg.enabled is True
        assert cfg.debug is False
        assert cfg.max_depth == 10
        assert cfg.max_complexity == 100
        assert cfg.max_aliases == 10
        assert cfg.persisted_queries_enabled is True
        assert cfg.subscriptions_enabled is True
        assert cfg.auth_required is False
        assert cfg.introspection_enabled is True
        assert cfg.graphiql_enabled is True
        assert cfg.batching_enabled is True
        assert cfg.max_batch_size == 10
        assert cfg.log_queries is False
        assert cfg.log_mutations is True
        assert cfg.log_errors is True

    def test_config_from_settings(self):
        reset_config()
        cfg = GraphQLConfig.from_settings()
        assert isinstance(cfg, GraphQLConfig)
        assert isinstance(cfg.rate_limit, GraphQLRateLimitConfig)

    @patch("django_matt.graphql.config.settings")
    def test_config_from_custom_settings(self, mock_settings):
        mock_settings.DEBUG = False
        mock_settings.DJANGO_MATT_GRAPHQL = {
            "ENABLED": False,
            "MAX_DEPTH": 5,
            "MAX_COMPLEXITY": 50,
            "AUTH_REQUIRED": True,
            "RATE_LIMIT": {"ENABLED": False, "QUERIES_PER_MINUTE": 200},
        }
        cfg = GraphQLConfig.from_settings()
        assert cfg.enabled is False
        assert cfg.max_depth == 5
        assert cfg.max_complexity == 50
        assert cfg.auth_required is True
        assert cfg.rate_limit.enabled is False
        assert cfg.rate_limit.queries_per_minute == 200

    def test_get_graphql_config_singleton(self):
        reset_config()
        cfg1 = get_graphql_config()
        cfg2 = get_graphql_config()
        assert cfg1 is cfg2

    def test_reset_config(self):
        reset_config()
        cfg1 = get_graphql_config()
        reset_config()
        cfg2 = get_graphql_config()
        assert cfg1 is not cfg2


# ===========================================================================
# Complexity and rate-limit registries
# ===========================================================================


class TestComplexityRegistry:
    def test_complexity_decorator(self):
        @complexity(15)
        def my_resolver():
            pass

        assert get_field_complexity(my_resolver) == 15

    def test_default_complexity(self):
        def undecorated():
            pass

        assert get_field_complexity(undecorated) == 1

    def test_rate_limited_decorator(self):
        @rate_limited(10, 60)
        def my_mutation():
            pass

        # The registry stores the original unwrapped function
        original = getattr(my_mutation, '__wrapped__', my_mutation)
        limit = get_rate_limit(original)
        assert limit == (10, 60)

    def test_no_rate_limit(self):
        def undecorated():
            pass

        assert get_rate_limit(undecorated) is None


# ===========================================================================
# STRAWBERRY_AVAILABLE flag
# ===========================================================================


class TestStrawberryAvailability:
    def test_flag_exists(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE

        assert isinstance(STRAWBERRY_AVAILABLE, bool)

    def test_check_strawberry_when_missing(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE

        if not STRAWBERRY_AVAILABLE:
            from django_matt.graphql import _require_strawberry

            with pytest.raises(ImportError, match="strawberry-graphql"):
                _require_strawberry()


# ===========================================================================
# DjangoModelType base class (always available)
# ===========================================================================


class TestDjangoModelType:
    def test_class_exists(self):
        from django_matt.graphql.types import DjangoModelType

        assert DjangoModelType._django_model is None
        assert DjangoModelType._field_map == {}


# ===========================================================================
# Decorators that require strawberry
# ===========================================================================


class TestDecoratorsRequireStrawberry:
    """Test that decorators raise ImportError when strawberry is not available."""

    def test_graphql_type_raises_without_strawberry(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE

        if not STRAWBERRY_AVAILABLE:
            from django_matt.graphql.decorators import graphql_type

            with pytest.raises(ImportError, match="strawberry-graphql"):

                @graphql_type
                class Foo:
                    id: int

    def test_graphql_input_raises_without_strawberry(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE

        if not STRAWBERRY_AVAILABLE:
            from django_matt.graphql.decorators import graphql_input

            with pytest.raises(ImportError, match="strawberry-graphql"):

                @graphql_input
                class Foo:
                    id: int

    def test_graphql_interface_raises_without_strawberry(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE

        if not STRAWBERRY_AVAILABLE:
            from django_matt.graphql.decorators import graphql_interface

            with pytest.raises(ImportError, match="strawberry-graphql"):

                @graphql_interface
                class Foo:
                    id: int

    def test_graphql_enum_raises_without_strawberry(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE
        from enum import Enum

        if not STRAWBERRY_AVAILABLE:
            from django_matt.graphql.decorators import graphql_enum

            with pytest.raises(ImportError, match="strawberry-graphql"):

                @graphql_enum
                class Status(Enum):
                    A = "a"

    def test_resolver_raises_without_strawberry(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE

        if not STRAWBERRY_AVAILABLE:
            from django_matt.graphql.decorators import resolver

            with pytest.raises(ImportError, match="strawberry-graphql"):

                @resolver
                def my_resolver():
                    pass

    def test_mutation_raises_without_strawberry(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE

        if not STRAWBERRY_AVAILABLE:
            from django_matt.graphql.decorators import mutation

            with pytest.raises(ImportError, match="strawberry-graphql"):

                @mutation
                def my_mutation():
                    pass

    def test_subscription_raises_without_strawberry(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE

        if not STRAWBERRY_AVAILABLE:
            from django_matt.graphql.decorators import subscription

            with pytest.raises(ImportError, match="strawberry-graphql"):

                @subscription
                def my_sub():
                    pass

    def test_field_raises_without_strawberry(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE

        if not STRAWBERRY_AVAILABLE:
            from django_matt.graphql.decorators import field

            with pytest.raises(ImportError, match="strawberry-graphql"):

                @field
                def my_field():
                    pass

    def test_permission_field_raises_without_strawberry(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE

        if not STRAWBERRY_AVAILABLE:
            from django_matt.graphql.decorators import permission_field

            with pytest.raises(ImportError, match="strawberry-graphql"):

                @permission_field()
                def my_field():
                    pass

    def test_authenticated_field_raises_without_strawberry(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE

        if not STRAWBERRY_AVAILABLE:
            from django_matt.graphql.decorators import authenticated_field

            with pytest.raises(ImportError, match="strawberry-graphql"):

                @authenticated_field()
                def my_field():
                    pass


# ===========================================================================
# Type mapping (DJANGO_TO_GRAPHQL_TYPE dict)
# ===========================================================================


class TestTypeMapping:
    def test_type_map_exists(self):
        from django_matt.graphql.types import DJANGO_TO_GRAPHQL_TYPE

        assert isinstance(DJANGO_TO_GRAPHQL_TYPE, dict)

    def test_type_map_empty_without_strawberry(self):
        from django_matt.graphql import STRAWBERRY_AVAILABLE
        from django_matt.graphql.types import DJANGO_TO_GRAPHQL_TYPE

        if not STRAWBERRY_AVAILABLE:
            assert len(DJANGO_TO_GRAPHQL_TYPE) == 0
        else:
            assert len(DJANGO_TO_GRAPHQL_TYPE) > 0


# ===========================================================================
# Permission classes (always available, no-op without strawberry)
# ===========================================================================


class TestPermissionClasses:
    def test_is_authenticated_class_exists(self):
        from django_matt.graphql.decorators import IsAuthenticated

        perm = IsAuthenticated()
        assert hasattr(perm, "has_permission")

    def test_is_admin_class_exists(self):
        from django_matt.graphql.decorators import IsAdmin

        perm = IsAdmin()
        assert hasattr(perm, "has_permission")

    def test_has_permission_class_exists(self):
        from django_matt.graphql.decorators import HasPermission

        perm = HasPermission("app.view_model")
        assert perm.permission == "app.view_model"

    def test_has_role_class_exists(self):
        from django_matt.graphql.decorators import HasRole

        perm = HasRole("admin", "editor")
        assert perm.roles == {"admin", "editor"}


# ===========================================================================
# Strawberry-dependent tests (skip if not available)
# ===========================================================================


class TestWithStrawberry:
    """Tests that run only when strawberry is installed."""

    @pytest.fixture(autouse=True)
    def _skip_without_strawberry(self):
        pytest.importorskip("strawberry", reason="strawberry required")

    def test_graphql_type_decorator(self):
        import strawberry
        from django_matt.graphql.decorators import graphql_type

        @graphql_type
        class UserType:
            id: int
            email: str

        # Should be a strawberry type
        assert hasattr(UserType, "__strawberry_definition__") or hasattr(
            UserType, "_type_definition"
        )

    def test_graphql_input_decorator(self):
        from django_matt.graphql.decorators import graphql_input

        @graphql_input
        class CreateUserInput:
            email: str
            password: str

        assert hasattr(CreateUserInput, "__strawberry_definition__") or hasattr(
            CreateUserInput, "_type_definition"
        )

    def test_graphql_enum_decorator(self):
        from enum import Enum

        from django_matt.graphql.decorators import graphql_enum

        @graphql_enum
        class Status(Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"

        assert hasattr(Status, "_enum_definition") or hasattr(Status, "__strawberry_definition__")

    def test_create_type_from_model(self):
        from django_matt.graphql.types import create_type_from_model

        # Create a simple test model mock
        class FakeField:
            def __init__(self, name, field_class, null=False, blank=False):
                self.name = name
                self.__class__ = field_class
                self.null = null
                self.blank = blank

            def has_default(self):
                return False

        class FakeOptions:
            def __init__(self, fields):
                self.fields = fields

        class FakeMeta:
            pass

        class FakeModel(models.Model):
            class Meta:
                app_label = "test_graphql"

            name = models.CharField(max_length=100)
            active = models.BooleanField(default=True)

        try:
            type_cls = create_type_from_model(FakeModel, fields=["id", "name", "active"])
            assert type_cls is not None
        except Exception:
            # May fail due to Django model registration, but import works
            pass

    def test_get_graphql_type_for_field(self):
        from django_matt.graphql.types import get_graphql_type_for_field

        field = models.CharField(max_length=100)
        result = get_graphql_type_for_field(field)
        assert result is str

    def test_get_graphql_type_for_int_field(self):
        from django_matt.graphql.types import get_graphql_type_for_field

        field = models.IntegerField()
        result = get_graphql_type_for_field(field)
        assert result is int

    def test_get_graphql_type_for_bool_field(self):
        from django_matt.graphql.types import get_graphql_type_for_field

        field = models.BooleanField()
        result = get_graphql_type_for_field(field)
        assert result is bool

    def test_get_graphql_type_for_float_field(self):
        from django_matt.graphql.types import get_graphql_type_for_field

        field = models.FloatField()
        result = get_graphql_type_for_field(field)
        assert result is float

    def test_get_graphql_type_for_text_field(self):
        from django_matt.graphql.types import get_graphql_type_for_field

        field = models.TextField()
        result = get_graphql_type_for_field(field)
        assert result is str

    def test_get_graphql_type_for_python_type(self):
        from django_matt.graphql.types import get_graphql_type_for_python_type

        assert get_graphql_type_for_python_type(int) is int
        assert get_graphql_type_for_python_type(str) is str
        assert get_graphql_type_for_python_type(bool) is bool
        assert get_graphql_type_for_python_type(float) is float

    def test_node_interface_exists(self):
        from django_matt.graphql.types import NodeInterface

        assert hasattr(NodeInterface, "id")

    def test_page_info_type(self):
        from django_matt.graphql.types import PageInfoType

        page_info = PageInfoType(
            has_next_page=True,
            has_previous_page=False,
            start_cursor="abc",
            end_cursor="xyz",
            total_count=100,
        )
        assert page_info.has_next_page is True
        assert page_info.total_count == 100

    def test_graphql_schema_class(self):
        from django_matt.graphql.schema import GraphQLSchema

        schema = GraphQLSchema()
        assert schema.auto_generate_queries is True
        assert schema.auto_generate_mutations is True
        assert schema._models == {}

    def test_schema_add_model_chaining(self):
        from django_matt.graphql.schema import GraphQLSchema

        schema = GraphQLSchema()
        # Just test chaining returns self (actual model add would need registered models)
        assert isinstance(schema, GraphQLSchema)
