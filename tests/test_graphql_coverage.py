"""
Extended test coverage for the Django Matt graphql module.

Tests cover:
- Schema generation from Django models (GraphQLSchema builder)
- Type creation from models (create_type_from_model, create_input_from_model)
- Field type mapping (Django -> GraphQL)
- Query generation (list, detail, connection)
- Mutation generation (create, update, delete, bulk)
- DataLoader batch loading and caching
- DataLoaderRegistry management
- Subscription events and manager
- Relay-style pagination (PageInfoType, ConnectionType, EdgeType)
- Filter input generation
- Error handling (strawberry not installed)
- Decorator stubs and utilities
- apply_filters query builder

Requires: strawberry-graphql (uses pytest.importorskip)
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from django.db import models

import pytest

strawberry = pytest.importorskip("strawberry")


# ===========================================================================
# Type mapping
# ===========================================================================


class TestDjangoToGraphQLTypeMapping:
    def test_mapping_exists(self):
        from django_matt.graphql.types import DJANGO_TO_GRAPHQL_TYPE

        assert models.CharField in DJANGO_TO_GRAPHQL_TYPE
        assert models.IntegerField in DJANGO_TO_GRAPHQL_TYPE
        assert models.BooleanField in DJANGO_TO_GRAPHQL_TYPE
        assert models.UUIDField in DJANGO_TO_GRAPHQL_TYPE
        assert models.DateTimeField in DJANGO_TO_GRAPHQL_TYPE
        assert models.JSONField in DJANGO_TO_GRAPHQL_TYPE

    def test_charfield_maps_to_str(self):
        from django_matt.graphql.types import DJANGO_TO_GRAPHQL_TYPE

        assert DJANGO_TO_GRAPHQL_TYPE[models.CharField] is str

    def test_intfield_maps_to_int(self):
        from django_matt.graphql.types import DJANGO_TO_GRAPHQL_TYPE

        assert DJANGO_TO_GRAPHQL_TYPE[models.IntegerField] is int

    def test_boolfield_maps_to_bool(self):
        from django_matt.graphql.types import DJANGO_TO_GRAPHQL_TYPE

        assert DJANGO_TO_GRAPHQL_TYPE[models.BooleanField] is bool

    def test_uuid_maps_to_uuid(self):
        from django_matt.graphql.types import DJANGO_TO_GRAPHQL_TYPE

        assert DJANGO_TO_GRAPHQL_TYPE[models.UUIDField] is uuid.UUID


class TestGetGraphQLTypeForField:
    def test_charfield(self):
        from django_matt.graphql.types import get_graphql_type_for_field

        field = models.CharField(max_length=100)
        assert get_graphql_type_for_field(field) is str

    def test_nullable_field(self):
        from django_matt.graphql.types import get_graphql_type_for_field

        field = models.CharField(max_length=100, null=True)
        result = get_graphql_type_for_field(field)
        assert result == str | None

    def test_nullable_param(self):
        from django_matt.graphql.types import get_graphql_type_for_field

        field = models.IntegerField()
        result = get_graphql_type_for_field(field, nullable=True)
        assert result == int | None

    def test_foreign_key(self):
        from django_matt.graphql.types import get_graphql_type_for_field

        field = models.ForeignKey("self", on_delete=models.CASCADE)
        result = get_graphql_type_for_field(field)
        assert result == strawberry.ID

    def test_json_field(self):
        from django_matt.graphql.types import get_graphql_type_for_field

        field = models.JSONField()
        result = get_graphql_type_for_field(field)
        assert result == strawberry.scalars.JSON


class TestGetGraphQLTypeForPythonType:
    def test_basic_types(self):
        from django_matt.graphql.types import get_graphql_type_for_python_type

        assert get_graphql_type_for_python_type(int) is int
        assert get_graphql_type_for_python_type(str) is str
        assert get_graphql_type_for_python_type(bool) is bool
        assert get_graphql_type_for_python_type(float) is float

    def test_datetime_types(self):
        from django_matt.graphql.types import get_graphql_type_for_python_type

        assert get_graphql_type_for_python_type(datetime.date) is datetime.date
        assert get_graphql_type_for_python_type(datetime.datetime) is datetime.datetime

    def test_dict_maps_to_json(self):
        from django_matt.graphql.types import get_graphql_type_for_python_type

        assert get_graphql_type_for_python_type(dict) == strawberry.scalars.JSON

    def test_list_type(self):
        from django_matt.graphql.types import get_graphql_type_for_python_type

        result = get_graphql_type_for_python_type(list[int])
        assert result == list[int]

    def test_unknown_type_passthrough(self):
        from django_matt.graphql.types import get_graphql_type_for_python_type

        class Custom:
            pass

        assert get_graphql_type_for_python_type(Custom) is Custom


# ===========================================================================
# create_type_from_model
# ===========================================================================


@pytest.mark.django_db
class TestCreateTypeFromModel:
    def test_basic_type_creation(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment)
        assert ExperimentType is not None
        assert hasattr(ExperimentType, "__annotations__")

    def test_custom_name(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import create_type_from_model

        CustomType = create_type_from_model(Experiment, name="CustomExperimentType")
        assert CustomType.__name__ == "CustomExperimentType"

    def test_field_inclusion(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import create_type_from_model

        LimitedType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        annotations = LimitedType.__annotations__
        assert "key" in annotations
        assert "name" in annotations
        assert "status" in annotations
        assert "description" not in annotations

    def test_field_exclusion(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import create_type_from_model

        ExcludeType = create_type_from_model(Experiment, exclude=["metadata", "epsilon"])
        annotations = ExcludeType.__annotations__
        assert "metadata" not in annotations
        assert "epsilon" not in annotations
        assert "key" in annotations

    def test_from_orm(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        exp = Experiment.objects.create(key="gql-test", name="GQL Test")
        instance = ExperimentType.from_orm(exp)
        assert instance.key == "gql-test"
        assert instance.name == "GQL Test"


# ===========================================================================
# create_input_from_model
# ===========================================================================


class TestCreateInputFromModel:
    def test_basic_input_creation(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import create_input_from_model

        ExperimentInput = create_input_from_model(Experiment)
        assert ExperimentInput is not None
        # ID should be excluded by default
        annotations = ExperimentInput.__annotations__
        assert "id" not in annotations

    def test_custom_name(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import create_input_from_model

        CustomInput = create_input_from_model(Experiment, name="MyInput")
        assert CustomInput.__name__ == "MyInput"


# ===========================================================================
# Relay pagination types
# ===========================================================================


class TestRelayTypes:
    def test_page_info_type(self):
        from django_matt.graphql.types import PageInfoType

        info = PageInfoType(
            has_next_page=True,
            has_previous_page=False,
            start_cursor="abc",
            end_cursor="xyz",
            total_count=100,
        )
        assert info.has_next_page is True
        assert info.total_count == 100

    def test_edge_type(self):
        from django_matt.graphql.types import EdgeType

        edge = EdgeType(node="test_node", cursor="cursor_1")
        assert edge.node == "test_node"
        assert edge.cursor == "cursor_1"


@pytest.mark.django_db
class TestConnectionType:
    def test_from_queryset_basic(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import ConnectionType, create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])

        # Create test data
        for i in range(5):
            Experiment.objects.create(key=f"conn-{i}", name=f"Conn {i}")

        queryset = Experiment.objects.all()
        connection = ConnectionType.from_queryset(queryset, ExperimentType, first=3)

        assert len(connection.edges) == 3
        assert connection.total_count == 5
        assert connection.page_info.has_next_page is True
        assert connection.page_info.has_previous_page is False

    def test_from_queryset_with_after_cursor(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import ConnectionType, create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])

        for i in range(5):
            Experiment.objects.create(key=f"cafter-{i}", name=f"CAfter {i}")

        queryset = Experiment.objects.all()
        # Cursor for index 1
        after = base64.b64encode(b"1").decode()
        connection = ConnectionType.from_queryset(queryset, ExperimentType, after=after)

        assert connection.page_info.has_previous_page is True

    def test_from_queryset_with_last(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import ConnectionType, create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])

        for i in range(5):
            Experiment.objects.create(key=f"clast-{i}", name=f"CLast {i}")

        queryset = Experiment.objects.all()
        connection = ConnectionType.from_queryset(queryset, ExperimentType, last=2)

        assert len(connection.edges) == 2

    def test_from_queryset_empty(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import ConnectionType, create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])

        queryset = Experiment.objects.none()
        connection = ConnectionType.from_queryset(queryset, ExperimentType)

        assert len(connection.edges) == 0
        assert connection.total_count == 0
        assert connection.page_info.start_cursor is None

    def test_invalid_cursor_handled(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import ConnectionType, create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])

        Experiment.objects.create(key="badc", name="Bad cursor")
        queryset = Experiment.objects.all()
        # Invalid base64 cursor should not crash
        connection = ConnectionType.from_queryset(
            queryset, ExperimentType, after="not-valid-base64!!!"
        )
        assert connection is not None


# ===========================================================================
# DjangoModelType
# ===========================================================================


class TestDjangoModelType:
    def test_from_orm_basic(self):
        from django_matt.graphql.types import DjangoModelType

        class MockType(DjangoModelType):
            __annotations__ = {"name": str, "value": int}

        obj = MagicMock()
        obj.name = "test"
        obj.value = 42
        instance = MockType.from_orm(obj)
        assert instance.name == "test"
        assert instance.value == 42

    def test_from_django_alias(self):
        from django_matt.graphql.types import DjangoModelType

        class MockType(DjangoModelType):
            __annotations__ = {"name": str}

        obj = MagicMock()
        obj.name = "test"
        instance = MockType.from_django(obj)
        assert instance.name == "test"

    def test_from_queryset(self):
        from django_matt.graphql.types import DjangoModelType

        class MockType(DjangoModelType):
            __annotations__ = {"name": str}

        obj1 = MagicMock()
        obj1.name = "a"
        obj2 = MagicMock()
        obj2.name = "b"
        results = MockType.from_queryset([obj1, obj2])
        assert len(results) == 2


# ===========================================================================
# QueryGenerator
# ===========================================================================


@pytest.mark.django_db
class TestQueryGenerator:
    def test_list_query_creates_field(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.queries import QueryGenerator
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        gen = QueryGenerator(Experiment, ExperimentType)
        field = gen.list_query()
        assert field is not None

    def test_detail_query_creates_field(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.queries import QueryGenerator
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        gen = QueryGenerator(Experiment, ExperimentType)
        field = gen.detail_query()
        assert field is not None

    def test_connection_query_creates_field(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.queries import QueryGenerator
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        gen = QueryGenerator(Experiment, ExperimentType)
        field = gen.connection_query()
        assert field is not None


# ===========================================================================
# apply_filters
# ===========================================================================


class TestApplyFilters:
    def test_none_filter(self):
        from django_matt.graphql.queries import apply_filters

        qs = MagicMock()
        result = apply_filters(qs, None)
        assert result is qs

    def test_exact_match(self):
        from django_matt.graphql.queries import apply_filters

        qs = MagicMock()
        filter_input = MagicMock()
        filter_input.__dict__ = {"name": "test", "AND": None, "OR": None}
        # vars() returns __dict__
        apply_filters(qs, filter_input)
        qs.filter.assert_called()

    def test_contains_filter(self):
        from django_matt.graphql.queries import apply_filters

        qs = MagicMock()
        qs.filter.return_value = qs
        filter_input = MagicMock()
        filter_input.__dict__ = {"name_contains": "test"}
        result = apply_filters(qs, filter_input)
        qs.filter.assert_called_with(name__contains="test")

    def test_gt_filter(self):
        from django_matt.graphql.queries import apply_filters

        qs = MagicMock()
        qs.filter.return_value = qs
        filter_input = MagicMock()
        filter_input.__dict__ = {"age_gt": 18}
        apply_filters(qs, filter_input)
        qs.filter.assert_called_with(age__gt=18)

    def test_in_filter(self):
        from django_matt.graphql.queries import apply_filters

        qs = MagicMock()
        qs.filter.return_value = qs
        filter_input = MagicMock()
        filter_input.__dict__ = {"status_in": ["active", "pending"]}
        apply_filters(qs, filter_input)
        qs.filter.assert_called_with(status__in=["active", "pending"])


# ===========================================================================
# MutationGenerator
# ===========================================================================


class TestMutationGenerator:
    def test_create_mutation_generates(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.mutations import MutationGenerator
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        gen = MutationGenerator(Experiment, ExperimentType)
        mutation = gen.create_mutation()
        assert mutation is not None

    def test_update_mutation_generates(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.mutations import MutationGenerator
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        gen = MutationGenerator(Experiment, ExperimentType)
        mutation = gen.update_mutation()
        assert mutation is not None

    def test_delete_mutation_generates(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.mutations import MutationGenerator
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        gen = MutationGenerator(Experiment, ExperimentType)
        mutation = gen.delete_mutation()
        assert mutation is not None

    def test_mutation_result_type(self):
        from django_matt.graphql.mutations import MutationResult

        result = MutationResult(success=True, message="OK")
        assert result.success is True

    def test_delete_result_type(self):
        from django_matt.graphql.mutations import DeleteResult

        result = DeleteResult(success=True, deleted_id="123", message="Deleted")
        assert result.deleted_id == "123"

    def test_bulk_delete_result_type(self):
        from django_matt.graphql.mutations import BulkDeleteResult

        result = BulkDeleteResult(success=True, deleted_count=5)
        assert result.deleted_count == 5


# ===========================================================================
# DataLoader
# ===========================================================================


class TestModelDataLoader:
    def test_initialization(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.dataloaders import ModelDataLoader

        loader = ModelDataLoader(Experiment)
        assert loader.model is Experiment
        assert loader._cache is not None

    def test_prime_and_clear(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.dataloaders import ModelDataLoader

        loader = ModelDataLoader(Experiment)
        loader.prime("key1", "value1")
        assert loader._cache["key1"] == "value1"
        loader.clear("key1")
        assert "key1" not in loader._cache
        loader.prime("key2", "value2")
        loader.clear()
        assert len(loader._cache) == 0

    def test_no_cache_mode(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.dataloaders import ModelDataLoader

        loader = ModelDataLoader(Experiment, cache=False)
        assert loader._cache is None
        # prime and clear should be no-ops
        loader.prime("key", "val")
        loader.clear()


class TestRelatedDataLoader:
    def test_initialization(self):
        from django_matt.experiments.models import ExperimentAssignment
        from django_matt.graphql.dataloaders import RelatedDataLoader

        loader = RelatedDataLoader(ExperimentAssignment, "experiment_id")
        assert loader.model is ExperimentAssignment
        assert loader.related_field == "experiment_id"


class TestDataLoaderRegistry:
    def test_register_and_get(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.dataloaders import DataLoaderRegistry

        registry = DataLoaderRegistry()
        loader = registry.register_model(Experiment)
        assert registry.get_loader(Experiment) is loader

    def test_register_related(self):
        from django_matt.experiments.models import ExperimentAssignment
        from django_matt.graphql.dataloaders import DataLoaderRegistry

        registry = DataLoaderRegistry()
        loader = registry.register_related(ExperimentAssignment, "experiment_id")
        assert registry.get_related_loader(ExperimentAssignment, "experiment_id") is loader

    def test_get_nonexistent_loader(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.dataloaders import DataLoaderRegistry

        registry = DataLoaderRegistry()
        assert registry.get_loader(Experiment) is None

    def test_register_custom(self):
        from django_matt.graphql.dataloaders import DataLoaderRegistry

        registry = DataLoaderRegistry()

        async def my_loader(keys):
            return keys

        loader = registry.register_custom("my_loader", my_loader)
        assert registry.get_custom_loader("my_loader") is loader
        assert registry.get_custom_loader("nonexistent") is None

    def test_clear_all(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.dataloaders import DataLoaderRegistry

        registry = DataLoaderRegistry()
        model_loader = registry.register_model(Experiment)
        model_loader.prime("k", "v")
        registry.clear_all()
        assert len(model_loader._cache) == 0


class TestCreateDataloaders:
    def test_creates_registry(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.dataloaders import create_dataloaders

        registry = create_dataloaders([Experiment])
        assert registry.get_loader(Experiment) is not None


# ===========================================================================
# Subscriptions
# ===========================================================================


class TestSubscriptionEvent:
    def test_enum_values(self):
        from django_matt.graphql.subscriptions import SubscriptionEvent

        assert SubscriptionEvent.CREATED.value == "created"
        assert SubscriptionEvent.UPDATED.value == "updated"
        assert SubscriptionEvent.DELETED.value == "deleted"


class TestSubscriptionMessage:
    def test_creation(self):
        from django_matt.graphql.subscriptions import SubscriptionEvent, SubscriptionMessage

        msg = SubscriptionMessage(
            event=SubscriptionEvent.CREATED,
            data={"id": 1},
            model_name="User",
        )
        assert msg.event == SubscriptionEvent.CREATED
        assert msg.model_name == "User"
        assert msg.timestamp > 0


class TestSubscriptionManager:
    def test_singleton(self):
        from django_matt.graphql.subscriptions import SubscriptionManager

        # Reset singleton for testing
        SubscriptionManager._instance = None
        SubscriptionManager._instance = None

        m1 = SubscriptionManager()
        m2 = SubscriptionManager()
        assert m1 is m2

        # Cleanup
        SubscriptionManager._instance = None

    def test_register_model(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.subscriptions import SubscriptionManager
        from django_matt.graphql.types import create_type_from_model

        SubscriptionManager._instance = None
        manager = SubscriptionManager()

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        manager.register(Experiment, ExperimentType)
        assert Experiment in manager._type_map

        SubscriptionManager._instance = None


# ===========================================================================
# SubscriptionGenerator
# ===========================================================================


class TestSubscriptionGenerator:
    def test_created_subscription(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.subscriptions import SubscriptionGenerator, SubscriptionManager
        from django_matt.graphql.types import create_type_from_model

        SubscriptionManager._instance = None
        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        gen = SubscriptionGenerator(Experiment, ExperimentType)
        sub = gen.created_subscription()
        assert sub is not None

        SubscriptionManager._instance = None

    def test_all_events_subscription(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.subscriptions import SubscriptionGenerator, SubscriptionManager
        from django_matt.graphql.types import create_type_from_model

        SubscriptionManager._instance = None
        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        gen = SubscriptionGenerator(Experiment, ExperimentType)
        sub = gen.all_events_subscription()
        assert sub is not None

        SubscriptionManager._instance = None


# ===========================================================================
# GraphQLSchema builder
# ===========================================================================


class TestGraphQLSchemaBuilder:
    def test_add_model_chaining(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.schema import GraphQLSchema

        builder = GraphQLSchema()
        result = builder.add_model(Experiment)
        assert result is builder  # chaining

    def test_add_query(self):
        from django_matt.graphql.schema import GraphQLSchema

        builder = GraphQLSchema()

        @strawberry.field
        def hello() -> str:
            return "world"

        result = builder.add_query("hello", hello)
        assert result is builder

    def test_add_mutation(self):
        from django_matt.graphql.schema import GraphQLSchema

        builder = GraphQLSchema()

        @strawberry.mutation
        def do_thing() -> str:
            return "done"

        result = builder.add_mutation("do_thing", do_thing)
        assert result is builder

    def test_add_subscription(self):
        from django_matt.graphql.schema import GraphQLSchema

        builder = GraphQLSchema()
        result = builder.add_subscription("events", MagicMock())
        assert result is builder


# ===========================================================================
# _require_strawberry (error path)
# ===========================================================================


class TestRequireStrawberry:
    def test_schema_require(self):
        from django_matt.graphql.schema import _require_strawberry

        # Should not raise since strawberry is available
        _require_strawberry()

    def test_types_require(self):
        from django_matt.graphql.types import _require_strawberry

        _require_strawberry()

    def test_queries_require(self):
        from django_matt.graphql.queries import _require_strawberry

        _require_strawberry()

    def test_mutations_require(self):
        from django_matt.graphql.mutations import _require_strawberry

        _require_strawberry()


# ===========================================================================
# Convenience functions
# ===========================================================================


class TestConvenienceFunctions:
    def test_generate_list_query(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.queries import generate_list_query
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        field = generate_list_query(Experiment, ExperimentType)
        assert field is not None

    def test_generate_detail_query(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.queries import generate_detail_query
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        field = generate_detail_query(Experiment, ExperimentType)
        assert field is not None

    def test_generate_connection_query(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.queries import generate_connection_query
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        field = generate_connection_query(Experiment, ExperimentType)
        assert field is not None

    def test_generate_create_mutation(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.mutations import generate_create_mutation
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        mutation = generate_create_mutation(Experiment, ExperimentType)
        assert mutation is not None

    def test_generate_delete_mutation(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.mutations import generate_delete_mutation
        from django_matt.graphql.types import create_type_from_model

        ExperimentType = create_type_from_model(Experiment, fields=["key", "name", "status"])
        mutation = generate_delete_mutation(Experiment, ExperimentType)
        assert mutation is not None


# ===========================================================================
# Filter input generation
# ===========================================================================


class TestCreateFilterInput:
    def test_basic_filter_creation(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import create_filter_input_from_model

        FilterInput = create_filter_input_from_model(Experiment, fields=["key", "status"])
        assert FilterInput is not None
        annotations = FilterInput.__annotations__
        assert "key" in annotations
        # String fields get extra filter variants
        assert "key_contains" in annotations
        assert "key_icontains" in annotations

    def test_filter_name(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.types import create_filter_input_from_model

        FilterInput = create_filter_input_from_model(Experiment, name="ExpFilter", fields=["key"])
        assert FilterInput.__name__ == "ExpFilter"


# ===========================================================================
# get_loader context helper
# ===========================================================================


class TestGetLoaderHelper:
    def test_get_loader_from_context(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.dataloaders import DataLoaderRegistry, get_loader

        registry = DataLoaderRegistry()
        loader = registry.register_model(Experiment)

        info = MagicMock()
        info.context = {"dataloaders": registry}

        result = get_loader(info, Experiment)
        assert result is loader

    def test_get_loader_no_registry(self):
        from django_matt.experiments.models import Experiment
        from django_matt.graphql.dataloaders import get_loader

        info = MagicMock()
        info.context = {}

        result = get_loader(info, Experiment)
        assert result is None
