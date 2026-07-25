"""Tests for custom field type registration (Enhancement 2.5)."""

from decimal import Decimal

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
        ],
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )
    django.setup()

from typing import Any

from django.db import models

import pytest

from django_matt.core.schema import (
    _CUSTOM_FIELD_TYPE_MAP,
    _CUSTOM_OPENAPI_SCHEMAS,
    ModelSchema,
    get_custom_openapi_schemas,
    register_field_type,
    unregister_field_type,
)

# ---- Custom Django fields for testing ----


class MoneyField(models.DecimalField):
    """Simulated custom money field."""


class PhoneNumberField(models.CharField):
    """Simulated custom phone number field."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_length", 20)
        super().__init__(*args, **kwargs)


class ColorField(models.CharField):
    """A totally custom field with no special base."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_length", 7)
        super().__init__(*args, **kwargs)


# ---- Test models ----


class Product(models.Model):
    name = models.CharField(max_length=100)
    price = MoneyField(max_digits=10, decimal_places=2)
    phone = PhoneNumberField()
    color = ColorField()

    class Meta:
        app_label = "tests"


# ---- Fixtures ----


@pytest.fixture(autouse=True)
def _cleanup_registry():
    """Ensure custom registrations don't leak between tests."""
    yield
    for cls in [MoneyField, PhoneNumberField, ColorField]:
        unregister_field_type(cls)


# ---- Tests ----


class TestRegisterFieldType:
    def test_register_basic(self) -> None:
        register_field_type(MoneyField, Decimal)
        assert _CUSTOM_FIELD_TYPE_MAP[MoneyField] is Decimal
        assert MoneyField not in _CUSTOM_OPENAPI_SCHEMAS

    def test_register_with_openapi_schema(self) -> None:
        openapi = {"type": "string", "format": "decimal"}
        register_field_type(MoneyField, Decimal, openapi)
        assert _CUSTOM_OPENAPI_SCHEMAS[MoneyField] == openapi

    def test_register_overwrites(self) -> None:
        register_field_type(MoneyField, Decimal, {"type": "number"})
        register_field_type(MoneyField, str, {"type": "string"})
        assert _CUSTOM_FIELD_TYPE_MAP[MoneyField] is str
        assert _CUSTOM_OPENAPI_SCHEMAS[MoneyField] == {"type": "string"}

    def test_register_clears_openapi_on_re_register_without(self) -> None:
        register_field_type(MoneyField, Decimal, {"type": "number"})
        register_field_type(MoneyField, Decimal)  # no openapi_schema
        assert MoneyField not in _CUSTOM_OPENAPI_SCHEMAS


class TestUnregisterFieldType:
    def test_unregister(self) -> None:
        register_field_type(MoneyField, Decimal, {"type": "number"})
        unregister_field_type(MoneyField)
        assert MoneyField not in _CUSTOM_FIELD_TYPE_MAP
        assert MoneyField not in _CUSTOM_OPENAPI_SCHEMAS

    def test_unregister_nonexistent_is_noop(self) -> None:
        unregister_field_type(MoneyField)  # should not raise


class TestGetCustomOpenAPISchemas:
    def test_returns_copy(self) -> None:
        register_field_type(MoneyField, Decimal, {"type": "number"})
        result = get_custom_openapi_schemas()
        assert result == {MoneyField: {"type": "number"}}
        # Mutating the copy should not affect the internal dict
        result[PhoneNumberField] = {"type": "string"}
        assert PhoneNumberField not in _CUSTOM_OPENAPI_SCHEMAS


class TestModelSchemaUsesCustomTypes:
    def test_unregistered_falls_back_to_base_type(self) -> None:
        """MoneyField extends DecimalField, so without registration it resolves to Decimal."""

        class ProductSchemaNoReg(ModelSchema):
            class Config:
                model = Product
                include = ["id", "name", "price"]

        # DecimalField → Decimal by default
        assert ProductSchemaNoReg.model_fields["price"].annotation is Decimal

    def test_registered_custom_type_used(self) -> None:
        register_field_type(MoneyField, Decimal, {"type": "string", "format": "decimal"})

        class ProductSchemaReg(ModelSchema):
            class Config:
                model = Product
                include = ["id", "name", "price"]

        assert ProductSchemaReg.model_fields["price"].annotation is Decimal

    def test_registered_phone_type(self) -> None:
        register_field_type(PhoneNumberField, str, {"type": "string", "format": "phone"})

        class ProductSchemaPhone(ModelSchema):
            class Config:
                model = Product
                include = ["id", "phone"]

        assert ProductSchemaPhone.model_fields["phone"].annotation is str

    def test_custom_type_takes_priority_over_builtin(self) -> None:
        """Register ColorField (CharField subclass) as int — custom should win."""
        register_field_type(ColorField, int)

        class ProductSchemaColor(ModelSchema):
            class Config:
                model = Product
                include = ["id", "color"]

        assert ProductSchemaColor.model_fields["color"].annotation is int

    def test_unregister_restores_default(self) -> None:
        register_field_type(ColorField, int)
        unregister_field_type(ColorField)

        class ProductSchemaDefault(ModelSchema):
            class Config:
                model = Product
                include = ["id", "color"]

        # ColorField inherits CharField → str
        assert ProductSchemaDefault.model_fields["color"].annotation is str
