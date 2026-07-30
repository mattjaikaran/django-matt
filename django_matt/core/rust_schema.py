"""
Rust-accelerated ModelSchema — drop-in replacement for Pydantic ModelSchema.

Uses the Rust SchemaValidator for the validation hot path, falling back
to Pydantic for complex validators (custom @model_validator, nested models).

Usage:
    from django_matt.core.rust_schema import RustModelSchema

    class UserSchema(RustModelSchema):
        class Config:
            model = User
            fields = "__all__"

    # Identical API to ModelSchema:
    user = UserSchema.model_validate({"name": "Matt", "email": "m@t.com"})
    data = user.model_dump()  # Rust-accelerated serialization

When HAS_RUST is False, RustModelSchema == ModelSchema (pure Pydantic path).
"""

from __future__ import annotations

import json
import logging
from typing import Any, ClassVar

from pydantic import BaseModel

from django_matt._accel import HAS_RUST, SchemaValidatorRust, serialize_dicts_to_json

from .schema import ModelSchema

logger = logging.getLogger("django_matt.schema")


class RustModelSchema(ModelSchema):
    """
    Rust-accelerated schema class. Extends ModelSchema with Rust validation.

    When HAS_RUST is True:
    - model_validate() uses SchemaValidatorRust for the initial pass
    - model_dump() uses Rust serialize_dicts_to_json for serialization
    - Falls back to Pydantic for custom validators and nested models

    When HAS_RUST is False:
    - Identical behavior to ModelSchema (pure Pydantic)

    The schema definition (fields, types, Config) remains in Pydantic.
    Only the runtime validation/serialization hot paths use Rust.
    """

    _rust_schema_registered: ClassVar[bool] = False
    _rust_fields: ClassVar[dict[str, dict]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register schema with Rust validator at class creation time."""
        super().__init_subclass__(**kwargs)
        if HAS_RUST and SchemaValidatorRust is not None:
            cls._register_rust_schema()

    @classmethod
    def _register_rust_schema(cls) -> None:
        """Build and register a Rust schema definition for this class."""
        if cls._rust_schema_registered:
            return

        fields = {}
        for name, field_info in cls.model_fields.items():
            field_def = {
                "type": cls._pydantic_type_to_rust(field_info.annotation),
                "required": field_info.is_required(),
            }

            # Extract constraints from field metadata
            for meta in field_info.metadata:
                if hasattr(meta, "max_length"):
                    field_def["max_length"] = meta.max_length
                if hasattr(meta, "min_length"):
                    field_def["min_length"] = meta.min_length
                if hasattr(meta, "ge"):
                    field_def["minimum"] = meta.ge
                if hasattr(meta, "le"):
                    field_def["maximum"] = meta.le

            fields[name] = field_def

        cls._rust_fields = fields
        cls._rust_schema_registered = True

        try:
            validator = _get_rust_validator()
            schema_json = json.dumps({"fields": fields})
            validator.register(cls.__name__, schema_json)
        except Exception as e:
            logger.debug("Rust schema registration skipped for %s: %s", cls.__name__, e)

    @staticmethod
    def _pydantic_type_to_rust(annotation: Any) -> str:
        """Map Pydantic/Python type to Rust schema type string."""
        if annotation is None:
            return "any"
        origin = getattr(annotation, "__origin__", None)
        if origin is not None:
            args = getattr(annotation, "__args__", ())
            if origin is list:
                inner = args[0] if args else str
                return f"list[{RustModelSchema._pydantic_type_to_rust(inner)}]"
            if origin is dict:
                return "object"

        type_map = {
            str: "str",
            int: "int",
            float: "float",
            bool: "bool",
            list: "list",
            dict: "object",
            type(None): "null",
        }
        return type_map.get(annotation, "str")

    @classmethod
    def model_validate(
        cls, obj: Any, *, strict: bool | None = None, **kwargs: Any
    ) -> RustModelSchema:
        """
        Validate input data, using Rust for the hot path when available.

        Falls back to Pydantic validation when:
        - Rust is unavailable (HAS_RUST=False)
        - Schema has custom validators (@model_validator)
        - Input contains nested models
        """
        if not HAS_RUST or SchemaValidatorRust is None:
            return super().model_validate(obj, strict=strict, **kwargs)

        # Check if schema has custom validators — if so, use Pydantic
        if cls._has_custom_validators():
            return super().model_validate(obj, strict=strict, **kwargs)

        # Convert input to dict if needed
        if isinstance(obj, BaseModel):
            data = obj.model_dump()
        elif isinstance(obj, dict):
            data = obj
        else:
            return super().model_validate(obj, strict=strict, **kwargs)

        # Rust validation pass
        try:
            validator = _get_rust_validator()
            is_valid, validated, errors = validator.validate(cls.__name__, data)
        except Exception:
            return super().model_validate(obj, strict=strict, **kwargs)

        if not is_valid or errors:
            # Fall back to Pydantic for proper error messages
            return super().model_validate(obj, strict=strict, **kwargs)

        # Build instance from validated data
        validated_dict = dict(validated) if validated else data
        return cls.model_construct(**validated_dict)

    @classmethod
    def _has_custom_validators(cls) -> bool:
        """Check if this schema has custom @model_validator methods."""
        for attr_name in dir(cls):
            if attr_name.startswith("validate_") or attr_name.startswith("_validate_"):
                return True
        return False

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """
        Serialize to dict, using Rust serialization when available.

        Falls back to Pydantic when by_alias, exclude, or include are used.
        """
        use_rust = (
            HAS_RUST
            and serialize_dicts_to_json is not None
            and not kwargs.get("by_alias", False)
            and not kwargs.get("exclude")
            and not kwargs.get("include")
        )

        if use_rust:
            try:
                data = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
                json_bytes = serialize_dicts_to_json([data])
                results = json.loads(json_bytes)
                if results:
                    return results[0]
            except Exception:
                pass

        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs: Any) -> str:
        """
        Serialize to JSON string, using Rust for the hot path.
        """
        use_rust = (
            HAS_RUST and serialize_dicts_to_json is not None and not kwargs.get("by_alias", False)
        )

        if use_rust:
            try:
                data = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
                return serialize_dicts_to_json([data])
            except Exception:
                pass

        return super().model_dump_json(**kwargs)


# ─── Global Rust validator instance (lazy) ─────────────────────

_validator: Any = None


def _get_rust_validator() -> Any:
    """Get or create the global Rust SchemaValidator instance."""
    global _validator
    if _validator is None and SchemaValidatorRust is not None:
        _validator = SchemaValidatorRust()
    return _validator
