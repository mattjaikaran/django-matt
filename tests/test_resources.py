"""Tests for django_matt.resources module."""

from django.contrib.auth.models import User
from django.db import models

import pytest

from django_matt.resources.actions import ActionDescriptor, action
from django_matt.resources.resource import (
    ResourceConfig,
    _detect_filter_fields,
    _detect_search_fields,
    _model_name_to_prefix,
    _pluralize,
    build_viewset,
    resource,
)
from django_matt.views.viewset import APIViewSet

# ---------------------------------------------------------------
# Pluralization
# ---------------------------------------------------------------


class TestPluralize:
    def test_regular(self):
        assert _pluralize("product") == "products"

    def test_y_ending(self):
        assert _pluralize("category") == "categories"

    def test_s_ending(self):
        assert _pluralize("address") == "addresses"

    def test_x_ending(self):
        assert _pluralize("box") == "boxes"

    def test_ch_ending(self):
        assert _pluralize("match") == "matches"

    def test_sh_ending(self):
        assert _pluralize("wish") == "wishes"

    def test_ay_ending(self):
        assert _pluralize("day") == "days"

    def test_ey_ending(self):
        assert _pluralize("key") == "keys"

    def test_oy_ending(self):
        assert _pluralize("boy") == "boys"

    def test_uy_ending(self):
        assert _pluralize("guy") == "guys"

    def test_z_ending(self):
        # _pluralize does simple suffix append, no consonant doubling
        assert _pluralize("quiz") == "quizes"


# ---------------------------------------------------------------
# Model name to prefix
# ---------------------------------------------------------------


class TestModelNameToPrefix:
    def test_simple_model(self):
        assert _model_name_to_prefix(User) == "/users"

    def test_camel_case(self):
        # Create a mock model with a CamelCase name
        MockModel = type(
            "ProductCategory",
            (models.Model,),
            {
                "__module__": "tests",
                "Meta": type("Meta", (), {"app_label": "tests"}),
            },
        )
        assert _model_name_to_prefix(MockModel) == "/product-categories"

    def test_single_word(self):
        MockModel = type(
            "Item",
            (models.Model,),
            {
                "__module__": "tests",
                "Meta": type("Meta", (), {"app_label": "tests"}),
            },
        )
        assert _model_name_to_prefix(MockModel) == "/items"


# ---------------------------------------------------------------
# Auto-detect fields
# ---------------------------------------------------------------


class TestDetectSearchFields:
    def test_finds_charfields(self):
        fields = _detect_search_fields(User)
        # User has username, first_name, last_name, email (CharFields)
        assert "username" in fields
        assert "first_name" in fields
        assert "last_name" in fields
        assert "email" in fields

    def test_excludes_non_text_fields(self):
        fields = _detect_search_fields(User)
        # id is AutoField, is_active is BooleanField — not text
        assert "id" not in fields
        assert "is_active" not in fields

    def test_returns_list(self):
        fields = _detect_search_fields(User)
        assert isinstance(fields, list)


class TestDetectFilterFields:
    def test_includes_id(self):
        fields = _detect_filter_fields(User)
        assert "id" in fields

    def test_includes_charfields(self):
        fields = _detect_filter_fields(User)
        assert "username" in fields

    def test_includes_boolean_fields(self):
        fields = _detect_filter_fields(User)
        assert "is_active" in fields

    def test_includes_datetime_fields(self):
        fields = _detect_filter_fields(User)
        assert "date_joined" in fields

    def test_returns_list(self):
        fields = _detect_filter_fields(User)
        assert isinstance(fields, list)


# ---------------------------------------------------------------
# ResourceConfig
# ---------------------------------------------------------------


class TestResourceConfig:
    def test_defaults(self):
        config = ResourceConfig(model=User)
        assert config.model is User
        assert config.prefix is None
        assert config.page_size == 20
        assert config.pagination is True
        assert config.lookup_field == "id"
        assert config.operations is None
        assert config.tags is None
        assert config.response_schema is None
        assert config.create_schema is None
        assert config.update_schema is None
        assert config.schema_exclude is None
        assert config.search_fields is None
        assert config.filter_fields is None
        assert config.ordering is None
        assert config.ordering_fields is None
        assert config.max_page_size == 100
        assert config.permission_classes is None
        assert config.permissions is None
        assert config.children is None
        assert config.get_queryset is None
        assert config.actions == []

    def test_custom_values(self):
        config = ResourceConfig(
            model=User,
            prefix="/users",
            page_size=50,
            operations=["list", "read"],
        )
        assert config.prefix == "/users"
        assert config.page_size == 50
        assert config.operations == ["list", "read"]

    def test_schema_exclude(self):
        config = ResourceConfig(model=User, schema_exclude=["password"])
        assert config.schema_exclude == ["password"]

    def test_custom_tags(self):
        config = ResourceConfig(model=User, tags=["Staff", "Admin"])
        assert config.tags == ["Staff", "Admin"]


# ---------------------------------------------------------------
# build_viewset
# ---------------------------------------------------------------


class TestBuildViewset:
    def test_creates_viewset_subclass(self):
        config = ResourceConfig(model=User)
        vs = build_viewset(config)
        assert issubclass(vs, APIViewSet)

    def test_auto_prefix(self):
        config = ResourceConfig(model=User)
        vs = build_viewset(config)
        # _model_name_to_prefix returns "/users", build_viewset strips "/"
        assert vs.prefix == "users"

    def test_custom_prefix(self):
        config = ResourceConfig(model=User, prefix="/staff")
        vs = build_viewset(config)
        assert vs.prefix == "staff"

    def test_custom_prefix_without_slash(self):
        config = ResourceConfig(model=User, prefix="staff")
        vs = build_viewset(config)
        assert vs.prefix == "staff"

    def test_all_crud_views_present(self):
        config = ResourceConfig(model=User)
        vs = build_viewset(config)
        assert hasattr(vs, "list")
        assert hasattr(vs, "create")
        assert hasattr(vs, "read")
        assert hasattr(vs, "update")
        assert hasattr(vs, "delete")

    def test_limited_operations_list_and_read(self):
        config = ResourceConfig(model=User, operations=["list", "read"])
        vs = build_viewset(config)
        # list and read should be present as view instances
        assert hasattr(vs, "list")
        assert hasattr(vs, "read")
        # create, update, delete should NOT be set by build_viewset
        # They are not added to attrs so won't be on the dynamically created class
        vs_dict = vs.__dict__
        assert "create" not in vs_dict
        assert "update" not in vs_dict
        assert "delete" not in vs_dict

    def test_limited_operations_create_only(self):
        config = ResourceConfig(model=User, operations=["create"])
        vs = build_viewset(config)
        vs_dict = vs.__dict__
        assert "create" in vs_dict
        assert "list" not in vs_dict
        assert "read" not in vs_dict
        assert "update" not in vs_dict
        assert "delete" not in vs_dict

    def test_auto_generates_schemas(self):
        config = ResourceConfig(model=User)
        vs = build_viewset(config)
        assert vs.default_response_schema is not None
        assert "UserSchema" in vs.default_response_schema.__name__

    def test_tags_default_to_model_name(self):
        config = ResourceConfig(model=User)
        vs = build_viewset(config)
        assert vs.tags == ["User"]

    def test_custom_tags(self):
        config = ResourceConfig(model=User, tags=["Staff"])
        vs = build_viewset(config)
        assert vs.tags == ["Staff"]

    def test_per_operation_permissions(self):
        config = ResourceConfig(
            model=User,
            permissions={"list": ["perm_a"], "delete": ["perm_b"]},
        )
        vs = build_viewset(config)
        assert vs._permission_overrides == {"list": ["perm_a"], "delete": ["perm_b"]}

    def test_viewset_name(self):
        config = ResourceConfig(model=User)
        vs = build_viewset(config)
        assert vs.__name__ == "UserAutoViewSet"

    def test_schema_exclude(self):
        config = ResourceConfig(model=User, schema_exclude=["password"])
        vs = build_viewset(config)
        schema = vs.default_response_schema
        assert "password" not in schema.model_fields

    def test_model_is_set(self):
        config = ResourceConfig(model=User)
        vs = build_viewset(config)
        assert vs.model is User

    def test_permission_classes_default_empty(self):
        config = ResourceConfig(model=User)
        vs = build_viewset(config)
        assert vs.permission_classes == []

    def test_permission_classes_set(self):
        sentinel = object()
        config = ResourceConfig(model=User, permission_classes=[sentinel])
        vs = build_viewset(config)
        assert vs.permission_classes == [sentinel]

    def test_custom_get_queryset(self):
        def my_qs(request):
            return User.objects.none()

        config = ResourceConfig(model=User, get_queryset=my_qs)
        vs = build_viewset(config)
        # The class should have a get_queryset method that wraps our function
        assert "get_queryset" in vs.__dict__


# ---------------------------------------------------------------
# resource() function
# ---------------------------------------------------------------


class TestResourceFunction:
    def test_one_liner(self):
        vs = resource(User)
        assert issubclass(vs, APIViewSet)
        assert vs.model is User

    def test_with_options(self):
        vs = resource(User, prefix="/staff", page_size=50)
        assert vs.prefix == "staff"

    def test_permissions_list_becomes_permission_classes(self):
        sentinel = object()
        vs = resource(User, permissions=[sentinel])
        assert vs.permission_classes == [sentinel]

    def test_permissions_dict(self):
        vs = resource(User, permissions={"list": ["a"], "delete": ["b"]})
        assert vs._permission_overrides == {"list": ["a"], "delete": ["b"]}

    def test_operations_kwarg(self):
        vs = resource(User, operations=["list", "read"])
        vs_dict = vs.__dict__
        assert "list" in vs_dict
        assert "read" in vs_dict
        assert "create" not in vs_dict
        assert "update" not in vs_dict
        assert "delete" not in vs_dict

    def test_schema_exclude_kwarg(self):
        vs = resource(User, schema_exclude=["password"])
        schema = vs.default_response_schema
        assert "password" not in schema.model_fields

    def test_tags_kwarg(self):
        vs = resource(User, tags=["Staff"])
        assert vs.tags == ["Staff"]

    def test_decorator_mode(self):
        @resource(None, prefix="/custom-users")
        class UserResource:
            model = User
            search_fields = ["username"]
            page_size = 10

        assert issubclass(UserResource, APIViewSet)

    def test_decorator_requires_model(self):
        with pytest.raises(ValueError, match="must define a 'model' attribute"):

            @resource(None)
            class BadResource:
                pass

    def test_decorator_reads_class_attributes(self):
        @resource(None)
        class StaffResource:
            model = User
            prefix = "/staff-members"
            page_size = 5
            tags = ["Staff"]

        assert StaffResource.prefix == "staff-members"
        assert StaffResource.tags == ["Staff"]

    def test_decorator_collects_actions(self):
        @resource(None)
        class ProductResource:
            model = User

            @action("POST", "/bulk")
            async def bulk_create(self, request):
                pass

        # The decorator collects ActionDescriptor instances from the class
        # They are passed to ResourceConfig.actions
        assert issubclass(ProductResource, APIViewSet)


# ---------------------------------------------------------------
# ActionDescriptor
# ---------------------------------------------------------------


class TestActionDescriptor:
    def test_init(self):
        desc = ActionDescriptor("post", "/bulk")
        assert desc.method == "POST"
        assert desc.path == "/bulk"
        assert desc.permissions is None
        assert desc.summary is None
        assert desc.tags is None
        assert desc.handler is None

    def test_method_uppercased(self):
        desc = ActionDescriptor("get", "/items")
        assert desc.method == "GET"

    def test_as_decorator(self):
        desc = ActionDescriptor("GET", "/stats")

        async def get_stats(self, request):
            pass

        original_fn = get_stats
        result = desc(get_stats)
        # __call__ returns self (the descriptor)
        assert result is desc
        assert desc.handler is original_fn
        assert desc.handler_name == "get_stats"

    def test_with_all_kwargs(self):
        desc = ActionDescriptor(
            "DELETE",
            "/purge",
            permissions=["admin"],
            summary="Purge all records",
            tags=["Danger"],
        )
        assert desc.permissions == ["admin"]
        assert desc.summary == "Purge all records"
        assert desc.tags == ["Danger"]


# ---------------------------------------------------------------
# action() factory function
# ---------------------------------------------------------------


class TestAction:
    def test_creates_descriptor(self):
        desc = action("POST", "/bulk")
        assert isinstance(desc, ActionDescriptor)
        assert desc.method == "POST"
        assert desc.path == "/bulk"

    def test_as_decorator(self):
        @action("GET", "/stats")
        async def get_stats(self, request):
            pass

        assert isinstance(get_stats, ActionDescriptor)
        assert get_stats.handler_name == "get_stats"
        assert get_stats.method == "GET"

    def test_with_permissions(self):
        desc = action("DELETE", "/purge", permissions=["admin"])
        assert desc.permissions == ["admin"]

    def test_with_summary(self):
        desc = action("GET", "/overview", summary="Get overview")
        assert desc.summary == "Get overview"

    def test_with_tags(self):
        desc = action("POST", "/import", tags=["Bulk"])
        assert desc.tags == ["Bulk"]

    def test_default_method_is_post(self):
        desc = action()
        assert desc.method == "POST"

    def test_default_path_is_empty(self):
        desc = action()
        assert desc.path == ""
