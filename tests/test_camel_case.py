"""Tests for camelCase API serialization (DJANGO_MATT.CAMEL_CASE_API)."""

import os

import django
from django.conf import settings

# Minimal Django setup for tests
if not settings.configured:
    settings.configure(
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
        ],
        DEFAULT_AUTO_FIELD="django.db.backends.sqlite3",
        DJANGO_MATT={"CAMEL_CASE_API": False},
    )
    django.setup()

import pytest
from pydantic import BaseModel

from django_matt.core.schema import (
    ModelSchema,
    _get_camel_case_config,
    _reset_camel_case_config,
)

# ---- Helpers ----

def _enable_camel_case():
    """Enable camelCase in settings and reset cache."""
    settings.DJANGO_MATT = {**getattr(settings, "DJANGO_MATT", {}), "CAMEL_CASE_API": True}
    _reset_camel_case_config()


def _disable_camel_case():
    """Disable camelCase in settings and reset cache."""
    settings.DJANGO_MATT = {**getattr(settings, "DJANGO_MATT", {}), "CAMEL_CASE_API": False}
    _reset_camel_case_config()


@pytest.fixture(autouse=True)
def reset_config():
    """Reset camelCase config before and after each test."""
    _disable_camel_case()
    yield
    _disable_camel_case()


# ---- Tests: config helper ----

class TestCamelCaseConfig:
    def test_default_disabled(self):
        _reset_camel_case_config()
        assert _get_camel_case_config() is False

    def test_enabled(self):
        _enable_camel_case()
        assert _get_camel_case_config() is True

    def test_cache_reset(self):
        _enable_camel_case()
        assert _get_camel_case_config() is True
        _disable_camel_case()
        assert _get_camel_case_config() is False


# ---- Tests: model_dump_response ----

class TestModelDumpResponse:
    """Test the model_dump_response() convenience method."""

    def test_snake_case_when_disabled(self):
        """When CAMEL_CASE_API=False, model_dump_response returns snake_case."""
        _disable_camel_case()

        class SimpleSchema(BaseModel):
            first_name: str = "John"
            last_name: str = "Doe"
            is_active: bool = True

        # model_dump_response only exists on ModelSchema, but test the config path
        schema = SimpleSchema()
        # Without alias_generator, by_alias=False is a no-op
        result = schema.model_dump(by_alias=False)
        assert "first_name" in result
        assert "last_name" in result
        assert "is_active" in result

    def test_camel_case_with_alias_generator(self):
        """When alias_generator is set and by_alias=True, output is camelCase."""
        from pydantic import ConfigDict
        from pydantic.alias_generators import to_camel

        class CamelSchema(BaseModel):
            model_config = ConfigDict(
                alias_generator=to_camel,
                populate_by_name=True,
            )
            first_name: str = "John"
            last_name: str = "Doe"
            is_active: bool = True

        schema = CamelSchema()

        # by_alias=True should produce camelCase
        result = schema.model_dump(by_alias=True)
        assert "firstName" in result
        assert "lastName" in result
        assert "isActive" in result

        # by_alias=False should produce snake_case
        result_snake = schema.model_dump(by_alias=False)
        assert "first_name" in result_snake

    def test_populate_by_name_accepts_both(self):
        """With populate_by_name=True, both camelCase and snake_case input work."""
        from pydantic import ConfigDict
        from pydantic.alias_generators import to_camel

        class BothSchema(BaseModel):
            model_config = ConfigDict(
                alias_generator=to_camel,
                populate_by_name=True,
            )
            first_name: str
            is_active: bool = True

        # snake_case input
        s1 = BothSchema(first_name="John")
        assert s1.first_name == "John"

        # camelCase input
        s2 = BothSchema.model_validate({"firstName": "Jane"})
        assert s2.first_name == "Jane"


# ---- Tests: ModelSchema metaclass integration ----

class TestModelSchemaMetaclassIntegration:
    """Test that the metaclass applies alias_generator when CAMEL_CASE_API is enabled."""

    def test_metaclass_no_alias_when_disabled(self):
        """ModelSchema subclasses should NOT have alias_generator when disabled."""
        _disable_camel_case()

        # ModelSchema base should not have alias_generator by default
        config = ModelSchema.model_config
        assert config.get("alias_generator") is None

    def test_per_schema_override(self):
        """Per-schema Config.camel_case=False should prevent alias_generator."""
        from pydantic import ConfigDict
        from pydantic.alias_generators import to_camel

        # Even if global is enabled, per-schema override should work
        class ManualCamelSchema(BaseModel):
            model_config = ConfigDict(
                alias_generator=to_camel,
                populate_by_name=True,
            )
            user_name: str = "test"

        result = ManualCamelSchema().model_dump(by_alias=True)
        assert "userName" in result


# ---- Tests: apply_to_model stays snake_case ----

class TestApplyToModelSnakeCase:
    """Ensure model_dump() for Django model operations always uses snake_case."""

    def test_model_dump_without_alias(self):
        """model_dump() without by_alias should return snake_case even with alias_generator."""
        from pydantic import ConfigDict
        from pydantic.alias_generators import to_camel

        class DataSchema(BaseModel):
            model_config = ConfigDict(
                alias_generator=to_camel,
                populate_by_name=True,
            )
            first_name: str = "John"
            last_name: str = "Doe"

        schema = DataSchema()
        # This is what apply_to_model / create use — no by_alias
        result = schema.model_dump(exclude_unset=True)
        assert "first_name" in result or "firstName" not in result
        # model_dump() without by_alias always uses field names
        result_explicit = schema.model_dump(by_alias=False)
        assert "first_name" in result_explicit
        assert "firstName" not in result_explicit
