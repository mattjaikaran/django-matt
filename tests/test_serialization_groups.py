from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from django_matt.serialization import (
    Grouped,
    Public,
    Secret,
    SerializationContext,
    SerializationContextMiddleware,
    clear_schema_cache,
    filter_schema,
    schema_for_groups,
    serialize_for,
)


# -- Test schemas --


class UserSchema(BaseModel):
    id: int
    username: str
    email: str = Grouped("admin", "owner")
    ssn: str = Secret()
    display_name: str = Public()


class ProfileSchema(BaseModel):
    user_id: int
    bio: str
    salary: int = Grouped("admin", "hr")
    internal_notes: str = Grouped("internal")


# -- SerializationContext --


class TestSerializationContext:
    def test_from_groups(self):
        ctx = SerializationContext.from_groups("admin", "public")
        assert ctx.groups == frozenset({"admin", "public"})
        assert ctx.include_fields is None
        assert ctx.exclude_fields is None

    def test_frozen(self):
        ctx = SerializationContext.from_groups("admin")
        with pytest.raises(AttributeError):
            ctx.groups = frozenset({"other"})  # type: ignore[misc]


# -- Grouped / Secret / Public fields --


class TestFieldHelpers:
    def test_grouped_stores_groups_in_schema_extra(self):
        info = UserSchema.model_fields["email"]
        assert info.json_schema_extra == {"groups": ["admin", "owner"]}

    def test_secret_is_admin_internal(self):
        info = UserSchema.model_fields["ssn"]
        assert info.json_schema_extra == {"groups": ["admin", "internal"]}

    def test_public_has_no_groups(self):
        info = UserSchema.model_fields["display_name"]
        extra = info.json_schema_extra
        assert extra is None or "groups" not in (extra or {})

    def test_ungrouped_field_has_no_extra(self):
        info = UserSchema.model_fields["username"]
        assert info.json_schema_extra is None


# -- filter_schema --


class TestFilterSchema:
    def test_admin_sees_all(self):
        user = UserSchema(id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt")
        ctx = SerializationContext.from_groups("admin")
        result = filter_schema(user, ctx)
        assert set(result.keys()) == {"id", "username", "email", "ssn", "display_name"}

    def test_public_sees_only_ungrouped(self):
        user = UserSchema(id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt")
        ctx = SerializationContext.from_groups("public")
        result = filter_schema(user, ctx)
        assert "email" not in result
        assert "ssn" not in result
        assert result["username"] == "matt"
        assert result["display_name"] == "Matt"

    def test_owner_sees_email(self):
        user = UserSchema(id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt")
        ctx = SerializationContext.from_groups("owner")
        result = filter_schema(user, ctx)
        assert result["email"] == "m@x.com"
        assert "ssn" not in result

    def test_include_fields_overrides(self):
        user = UserSchema(id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt")
        ctx = SerializationContext(
            groups=frozenset({"admin"}),
            include_fields=frozenset({"id", "username"}),
        )
        result = filter_schema(user, ctx)
        assert set(result.keys()) == {"id", "username"}

    def test_exclude_fields(self):
        user = UserSchema(id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt")
        ctx = SerializationContext(
            groups=frozenset({"admin"}),
            exclude_fields=frozenset({"ssn"}),
        )
        result = filter_schema(user, ctx)
        assert "ssn" not in result
        assert "email" in result

    def test_empty_groups_only_shows_ungrouped(self):
        user = UserSchema(id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt")
        ctx = SerializationContext(groups=frozenset())
        result = filter_schema(user, ctx)
        assert set(result.keys()) == {"id", "username", "display_name"}


# -- schema_for_groups --


class TestSchemaForGroups:
    def setup_method(self):
        clear_schema_cache()

    def test_creates_dynamic_schema(self):
        AdminUser = schema_for_groups(UserSchema, "admin")
        assert "email" in AdminUser.model_fields
        assert "ssn" in AdminUser.model_fields

    def test_public_schema_excludes_grouped(self):
        PubUser = schema_for_groups(UserSchema, "public")
        assert "email" not in PubUser.model_fields
        assert "ssn" not in PubUser.model_fields
        assert "username" in PubUser.model_fields

    def test_caching(self):
        s1 = schema_for_groups(UserSchema, "admin")
        s2 = schema_for_groups(UserSchema, "admin")
        assert s1 is s2

    def test_different_groups_different_schemas(self):
        s1 = schema_for_groups(UserSchema, "admin")
        s2 = schema_for_groups(UserSchema, "public")
        assert s1 is not s2

    def test_dynamic_schema_instantiation(self):
        PubUser = schema_for_groups(UserSchema, "public")
        instance = PubUser(id=1, username="matt", display_name="Matt")
        assert instance.id == 1  # type: ignore[attr-defined]
        assert instance.username == "matt"  # type: ignore[attr-defined]

    def test_hr_group_on_profile(self):
        HRProfile = schema_for_groups(ProfileSchema, "hr")
        assert "salary" in HRProfile.model_fields
        assert "internal_notes" not in HRProfile.model_fields


# -- serialize_for decorator --


class TestSerializeFor:
    def test_sync_decorator_with_static_groups(self):
        @serialize_for(groups=["public"])
        def get_user():
            return UserSchema(id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt")

        result = get_user()
        assert "email" not in result
        assert "ssn" not in result
        assert result["username"] == "matt"

    def test_sync_decorator_admin_groups(self):
        @serialize_for(groups=["admin"])
        def get_user():
            return UserSchema(id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt")

        result = get_user()
        assert "email" in result
        assert "ssn" in result

    def test_async_decorator(self):
        @serialize_for(groups=["public"])
        async def get_user():
            return UserSchema(id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt")

        result = asyncio.get_event_loop().run_until_complete(get_user())
        assert "email" not in result
        assert result["username"] == "matt"

    def test_list_response(self):
        @serialize_for(groups=["public"])
        def get_users():
            return [
                UserSchema(id=1, username="a", email="a@x.com", ssn="1", display_name="A"),
                UserSchema(id=2, username="b", email="b@x.com", ssn="2", display_name="B"),
            ]

        result = get_users()
        assert len(result) == 2
        assert "email" not in result[0]
        assert result[1]["username"] == "b"

    def test_groups_from_request(self):
        request = MagicMock()
        request.user = MagicMock()
        request.user.role = "admin"
        request.META = {}

        @serialize_for(groups_from="user.role")
        def get_user(request):
            return UserSchema(id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt")

        result = get_user(request)
        assert "email" in result
        assert "ssn" in result

    def test_exclude_fields_in_decorator(self):
        @serialize_for(groups=["admin"], exclude_fields={"ssn"})
        def get_user():
            return UserSchema(id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt")

        result = get_user()
        assert "ssn" not in result
        assert "email" in result

    def test_dict_passthrough(self):
        @serialize_for(groups=["public"])
        def get_data():
            return {"key": "value"}

        result = get_data()
        assert result == {"key": "value"}

    def test_primitive_passthrough(self):
        @serialize_for(groups=["public"])
        def get_count():
            return 42

        assert get_count() == 42


# -- Middleware --


class TestSerializationContextMiddleware:
    def _make_request(self, user=None):
        request = MagicMock(spec=["user", "META"])
        request.user = user
        request.META = {}
        return request

    def test_anonymous_user_gets_public(self):
        mw = SerializationContextMiddleware(lambda r: r)
        request = self._make_request(user=MagicMock(is_authenticated=False))
        response = mw(request)
        assert response.serialization_context.groups == frozenset({"public"})

    def test_no_user_gets_public(self):
        mw = SerializationContextMiddleware(lambda r: r)
        request = MagicMock(spec=["META"])
        request.user = None
        request.META = {}
        response = mw(request)
        assert response.serialization_context.groups == frozenset({"public"})

    def test_superuser_gets_all(self):
        mw = SerializationContextMiddleware(lambda r: r)
        user = MagicMock(is_authenticated=True, is_superuser=True, is_staff=True)
        request = self._make_request(user=user)
        response = mw(request)
        assert response.serialization_context.groups == frozenset({"admin", "internal", "public"})

    def test_staff_gets_internal(self):
        mw = SerializationContextMiddleware(lambda r: r)
        user = MagicMock(is_authenticated=True, is_superuser=False, is_staff=True)
        request = self._make_request(user=user)
        response = mw(request)
        assert response.serialization_context.groups == frozenset({"internal", "public"})

    def test_role_based_groups(self):
        mw = SerializationContextMiddleware(lambda r: r)
        user = MagicMock(is_authenticated=True, is_superuser=False, is_staff=False, role="admin")
        request = self._make_request(user=user)
        response = mw(request)
        assert "admin" in response.serialization_context.groups

    def test_regular_user_gets_public(self):
        mw = SerializationContextMiddleware(lambda r: r)
        user = MagicMock(is_authenticated=True, is_superuser=False, is_staff=False)
        del user.role  # no role attr
        request = self._make_request(user=user)
        response = mw(request)
        assert response.serialization_context.groups == frozenset({"public"})


# -- Integration: filter_schema + model_construct --


class TestModelConstructIntegration:
    def test_filter_works_with_model_construct(self):
        instance = UserSchema.model_construct(
            id=1, username="matt", email="m@x.com", ssn="123", display_name="Matt"
        )
        ctx = SerializationContext.from_groups("public")
        result = filter_schema(instance, ctx)
        assert "email" not in result
        assert result["username"] == "matt"

    def test_multiple_groups(self):
        instance = ProfileSchema.model_construct(
            user_id=1, bio="hi", salary=100000, internal_notes="note"
        )
        ctx = SerializationContext.from_groups("hr", "internal")
        result = filter_schema(instance, ctx)
        assert result["salary"] == 100000
        assert result["internal_notes"] == "note"
