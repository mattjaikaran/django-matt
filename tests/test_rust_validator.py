"""Tests for Rust-accelerated schema validator."""

from __future__ import annotations

import pytest

from django_matt._accel import HAS_RUST, SchemaValidatorRust

pytestmark = pytest.mark.skipif(not HAS_RUST, reason="Rust extensions not compiled")


@pytest.fixture
def validator():
    v = SchemaValidatorRust()
    v.register(
        "User",
        '{"fields": {"name": {"type": "str", "required": true, "max_length": 50},'
        ' "age": {"type": "int", "min_value": 0, "max_value": 150},'
        ' "email": {"type": "str", "required": true},'
        ' "role": {"type": "str", "choices": ["admin", "user", "guest"]},'
        ' "active": {"type": "bool"},'
        ' "bio": {"type": "str", "nullable": true}'
        '}, "allow_extra": false}',
    )
    return v


class TestSchemaValidatorBasic:
    def test_valid_data(self, validator):
        valid, errors = validator.validate(
            "User", {"name": "Matt", "age": 30, "email": "m@e.com", "role": "admin"}
        )
        assert valid is True
        assert len(errors) == 0

    def test_missing_required(self, validator):
        valid, errors = validator.validate("User", {"age": 25})
        assert valid is False
        error_fields = {e["field"] for e in errors}
        assert "name" in error_fields
        assert "email" in error_fields

    def test_wrong_type_str(self, validator):
        valid, errors = validator.validate(
            "User", {"name": 123, "email": "x@y.com"}
        )
        assert valid is False
        assert any(e["field"] == "name" and e["type"] == "type" for e in errors)

    def test_wrong_type_int(self, validator):
        valid, errors = validator.validate(
            "User", {"name": "Matt", "email": "x@y.com", "age": "thirty"}
        )
        assert valid is False
        assert any(e["field"] == "age" for e in errors)

    def test_wrong_type_bool(self, validator):
        valid, errors = validator.validate(
            "User", {"name": "Matt", "email": "x@y.com", "active": "yes"}
        )
        assert valid is False
        assert any(e["field"] == "active" for e in errors)

    def test_max_length(self, validator):
        valid, errors = validator.validate(
            "User", {"name": "A" * 100, "email": "x@y.com"}
        )
        assert valid is False
        assert any(e["type"] == "max_length" for e in errors)

    def test_min_value(self, validator):
        valid, errors = validator.validate(
            "User", {"name": "Matt", "email": "x@y.com", "age": -5}
        )
        assert valid is False
        assert any(e["type"] == "min_value" for e in errors)

    def test_max_value(self, validator):
        valid, errors = validator.validate(
            "User", {"name": "Matt", "email": "x@y.com", "age": 200}
        )
        assert valid is False
        assert any(e["type"] == "max_value" for e in errors)

    def test_choices(self, validator):
        valid, errors = validator.validate(
            "User", {"name": "Matt", "email": "x@y.com", "role": "superadmin"}
        )
        assert valid is False
        assert any(e["type"] == "choices" for e in errors)

    def test_valid_choices(self, validator):
        valid, errors = validator.validate(
            "User", {"name": "Matt", "email": "x@y.com", "role": "guest"}
        )
        assert valid is True

    def test_extra_fields_rejected(self, validator):
        valid, errors = validator.validate(
            "User", {"name": "Matt", "email": "x@y.com", "unknown_field": "val"}
        )
        assert valid is False
        assert any(e["type"] == "extra" for e in errors)

    def test_nullable_field_accepts_none(self, validator):
        valid, errors = validator.validate(
            "User", {"name": "Matt", "email": "x@y.com", "bio": None}
        )
        assert valid is True

    def test_non_nullable_field_rejects_none(self, validator):
        valid, errors = validator.validate(
            "User", {"name": None, "email": "x@y.com"}
        )
        assert valid is False
        assert any(e["type"] == "null" for e in errors)


class TestSchemaValidatorParseAndValidate:
    def test_valid_json(self, validator):
        valid, data, errors = validator.parse_and_validate(
            "User", b'{"name": "Alice", "email": "a@b.com", "age": 25}'
        )
        assert valid is True
        assert data["name"] == "Alice"
        assert data["age"] == 25
        assert len(errors) == 0

    def test_invalid_json(self, validator):
        with pytest.raises(ValueError, match="Invalid JSON"):
            validator.parse_and_validate("User", b"not json")

    def test_invalid_data(self, validator):
        valid, data, errors = validator.parse_and_validate(
            "User", b'{"age": -1}'
        )
        assert valid is False
        assert len(errors) > 0


class TestSchemaValidatorManagement:
    def test_schema_count(self):
        v = SchemaValidatorRust()
        assert v.schema_count == 0
        v.register("A", '{"fields": {"x": {"type": "str"}}}')
        v.register("B", '{"fields": {"y": {"type": "int"}}}')
        assert v.schema_count == 2

    def test_schema_names(self):
        v = SchemaValidatorRust()
        v.register("Foo", '{"fields": {"x": {"type": "str"}}}')
        v.register("Bar", '{"fields": {"y": {"type": "int"}}}')
        names = set(v.schema_names())
        assert names == {"Foo", "Bar"}

    def test_unknown_schema(self):
        v = SchemaValidatorRust()
        with pytest.raises(ValueError, match="Unknown schema"):
            v.validate("Nonexistent", {})

    def test_invalid_schema_json(self):
        v = SchemaValidatorRust()
        with pytest.raises(ValueError, match="Invalid schema JSON"):
            v.register("Bad", "not json")

    def test_allow_extra_default(self):
        v = SchemaValidatorRust()
        v.register("Flex", '{"fields": {"x": {"type": "str"}}}')
        valid, errors = v.validate("Flex", {"x": "hi", "extra": "ok"})
        assert valid is True  # allow_extra defaults to True
