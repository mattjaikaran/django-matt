"""
Schema-to-test generator — produces pytest modules from Pydantic schemas.

Generates edge-case validation tests by introspecting Pydantic v2
``model_fields``, then rendering a complete, importable ``pytest`` module
that exercises each field with boundary values, type mismatches, and
constraint violations.

Usage::

    from django_matt.guardrails.testgen import SchemaTestGenerator
    from myapp.schemas import UserCreateSchema

    gen = SchemaTestGenerator(UserCreateSchema)
    code = gen.generate_tests(model_name="user_create")
    print(code)

    # Or write directly to a file:
    gen.generate_test_file(Path("tests/test_user_create_schema.py"))

Edge cases covered per field type
---------------------------------
* **str** — empty, overlong, None (Optional), special/unicode, SQL-ish injection
* **int**  — 0, ±1, ge/le boundaries, ge−1 / le+1 violations, type mismatch
* **float** — 0.0, ±1.0, NaN, inf, type mismatch
* **bool** — True, False, type mismatch
* **list[X]** — empty, single, many, type mismatch in items
* **Optional[X]** — explicit None
* **required** — missing key
* **nested BaseModel** — invalid nested data
"""

from __future__ import annotations

import datetime
import math
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, ClassVar, Literal, Union, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel
from pydantic.fields import FieldInfo, PydanticUndefined


# ── Constraint extraction ─────────────────────────────────────────────────


def _extract_constraints(field_info: FieldInfo) -> dict[str, Any]:
    """Extract Pydantic v2 constraints from FieldInfo.metadata.

    Constraints like ``min_length``, ``ge``, ``pattern`` are stored in
    ``field_info.metadata`` as ``annotated_types.MinLen``, ``Ge``, etc.
    objects — not as direct attributes on FieldInfo.

    Returns a dict with keys: min_length, max_length, ge, le, gt, lt,
    multiple_of, pattern. Missing constraints are set to ``None``.
    """
    constraints: dict[str, Any] = {
        "min_length": None,
        "max_length": None,
        "ge": None,
        "le": None,
        "gt": None,
        "lt": None,
        "multiple_of": None,
        "pattern": None,
    }
    for item in field_info.metadata:
        qn = type(item).__qualname__
        if qn == "MinLen":
            constraints["min_length"] = item.min_length
        elif qn == "MaxLen":
            constraints["max_length"] = item.max_length
        elif qn == "Ge":
            constraints["ge"] = item.ge
        elif qn == "Le":
            constraints["le"] = item.le
        elif qn == "Gt":
            constraints["gt"] = item.gt
        elif qn == "Lt":
            constraints["lt"] = item.lt
        elif qn == "MultipleOf":
            constraints["multiple_of"] = item.multiple_of
        elif hasattr(item, "pattern"):
            constraints["pattern"] = item.pattern
    return constraints
# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OVERLONG_STR = "x" * 10_001
SPECIAL_CHARS_STR = "<script>alert(1)</script>\x00\n\t\r"
UNICODE_STR = "café™🚀日本語한국어🎉"
SQL_INJECTION_STR = "'; DROP TABLE users; --\n' OR 1=1 --"
MANY_ITEMS_COUNT = 256

# ---------------------------------------------------------------------------
# Edge-case descriptor
# ---------------------------------------------------------------------------


@dataclass
class EdgeCase:
    """A single edge-case test input."""

    field_name: str
    label: str
    value: Any
    expect_error: bool = True
    description: str | None = None


# ---------------------------------------------------------------------------
# SchemaTestGenerator
# ---------------------------------------------------------------------------


class SchemaTestGenerator:
    """Generate pytest validation tests for a Pydantic schema.

    Introspects ``schema_class.model_fields`` (Pydantic v2) to discover
    field types, optionality, and constraints, then produces edge-case
    test inputs for every field.
    """

    # Types that are handled as primitives
    PRIMITIVE_TYPES: ClassVar[tuple[type, ...]] = (
        str,
        int,
        float,
        bool,
        bytes,
        Decimal,
        UUID,
        datetime.datetime,
        datetime.date,
        datetime.time,
    )

    def __init__(self, schema_class: type[BaseModel]) -> None:
        self.schema_class = schema_class
        self.model_fields: dict[str, FieldInfo] = schema_class.model_fields
        self._valid_baseline: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_tests(self, model_name: str | None = None) -> str:
        """Return a complete pytest module as a string.

        Args:
            model_name: Override the schema name in the generated module.
                        Defaults to ``schema_class.__name__``.
        """
        name = model_name or self.schema_class.__name__
        edge_cases = self._collect_edge_cases()
        return self._render_test_module(name, edge_cases)

    def generate_test_file(self, output_path: Path) -> Path:
        """Write ``generate_tests()`` to *output_path* and return the path.

        Creates parent directories if they don't exist.
        """
        code = self.generate_tests()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code, encoding="utf-8")
        return output_path

    @classmethod
    def generate_test_file_for(
        cls, schema_class: type[BaseModel], output_path: Path
    ) -> Path:
        """Convenience: create a generator and write tests in one call."""
        return cls(schema_class).generate_test_file(output_path)

    # ------------------------------------------------------------------
    # Edge-case collection
    # ------------------------------------------------------------------

    def _collect_edge_cases(self) -> list[EdgeCase]:
        """Walk every model field and collect edge cases."""
        cases: list[EdgeCase] = []
        for field_name, field_info in self.model_fields.items():
            cases.extend(self._field_edge_cases(field_name, field_info))
        return cases

    def _field_edge_cases(
        self, field_name: str, field_info: FieldInfo
    ) -> list[EdgeCase]:
        """Return edge cases for a single field."""
        annotation = field_info.annotation
        origin = get_origin(annotation)
        args = get_args(annotation)
        is_optional = self._is_optional(annotation)
        is_required = field_info.is_required()

        # Unwrap Optional[X] to X for type inspection
        inner_type = self._unwrap_optional(annotation) if is_optional else annotation
        inner_origin = get_origin(inner_type)
        inner_args = get_args(inner_type)

        cases: list[EdgeCase] = []

        # --- Required-field check ---
        if is_required and not is_optional:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="missing",
                    value=...,
                    expect_error=True,
                    description="Missing required field",
                )
            )

        # --- Dispatch by type ---
        base_type = self._resolve_base_type(inner_type)
        if base_type is str:
            cases.extend(
                self._str_edge_cases(field_name, field_info, is_optional)
            )
        elif base_type is int:
            cases.extend(
                self._int_edge_cases(field_name, field_info, is_optional)
            )
        elif base_type is float:
            cases.extend(
                self._float_edge_cases(field_name, field_info, is_optional)
            )
        elif base_type is bool:
            cases.extend(
                self._bool_edge_cases(field_name, field_info, is_optional)
            )
        elif inner_origin is list or base_type is list:
            cases.extend(
                self._list_edge_cases(
                    field_name, field_info, is_optional, inner_args
                )
            )
        elif isinstance(base_type, type) and issubclass(base_type, BaseModel):
            cases.extend(
                self._nested_edge_cases(
                    field_name, field_info, is_optional, base_type
                )
            )
        else:
            # Generic field: just test None if optional
            if is_optional:
                cases.append(
                    EdgeCase(
                        field_name=field_name,
                        label="none",
                        value=None,
                        expect_error=False,
                        description="Optional field should accept None",
                    )
                )

        # --- Type-mismatch for all non-BaseModel fields ---
        if not self._is_base_model_type(base_type):
            type_name = getattr(base_type, "__name__", str(base_type))
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="type_mismatch",
                    value=self._type_mismatch_value(base_type),
                    expect_error=True,
                    description=f"Type mismatch for {type_name} field",
                )
            )

        return cases

    # ------------------------------------------------------------------
    # Per-type edge-case generators
    # ------------------------------------------------------------------

    def _str_edge_cases(
        self, field_name: str, field_info: FieldInfo, is_optional: bool
    ) -> list[EdgeCase]:
        cases: list[EdgeCase] = []
        c = _extract_constraints(field_info)
        min_len = c["min_length"] or 0
        max_len = c["max_length"]

        # Empty string
        if min_len > 0:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="empty",
                    value="",
                    expect_error=True,
                    description=f"Empty string violates min_length={min_len}",
                )
            )
        else:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="empty",
                    value="",
                    expect_error=False,
                    description="Empty string is valid when no min_length",
                )
            )

        # None (Optional fields only)
        if is_optional:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="none",
                    value=None,
                    expect_error=False,
                    description="Optional str should accept None",
                )
            )

        # Overlong string (max_length + 1)
        overlong_len = (max_len + 1) if max_len else 10_001
        overlong = "x" * min(overlong_len, 50_000)
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="overlong",
                value=overlong,
                expect_error=bool(max_len),
                description=f"String longer than max_length={max_len}"
                if max_len
                else "Very long string (no max_length constraint)",
            )
        )

        # Special characters
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="special_chars",
                value=SPECIAL_CHARS_STR,
                expect_error=False,
                description="Special characters should be accepted",
            )
        )

        # Unicode
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="unicode",
                value=UNICODE_STR,
                expect_error=False,
                description="Unicode characters should be accepted",
            )
        )

        # SQL injection
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="sql_injection",
                value=SQL_INJECTION_STR,
                expect_error=False,
                description="SQL injection strings are data, not code",
            )
        )

        # Pattern constraint
        if c["pattern"]:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="pattern_violation",
                    value="!!!NOT_MATCHING_PATTERN!!!",
                    expect_error=True,
                    description=f"String violates pattern={c["pattern"]!r}",
                )
            )

        return cases

    def _int_edge_cases(
        self, field_name: str, field_info: FieldInfo, is_optional: bool
    ) -> list[EdgeCase]:
        cases: list[EdgeCase] = []
        c = _extract_constraints(field_info)
        ge_val = c["ge"]
        le_val = c["le"]
        gt_val = c["gt"]
        lt_val = c["lt"]

        # Zero
        zero_should_error = (ge_val is not None and ge_val > 0) or (
            gt_val is not None and gt_val >= 0
        )
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="zero",
                value=0,
                expect_error=zero_should_error,
                description="Zero integer" + (" (violates lower bound)" if zero_should_error else ""),
            )
        )

        # Negative one
        neg_one_should_error = (ge_val is not None and ge_val > -1) or (
            gt_val is not None and gt_val >= -1
        )
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="negative_one",
                value=-1,
                expect_error=neg_one_should_error,
                description="Negative one" + (" (violates lower bound)" if neg_one_should_error else ""),
            )
        )

        # Positive one
        pos_one_should_error = (le_val is not None and le_val < 1) or (
            lt_val is not None and lt_val <= 1
        )
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="positive_one",
                value=1,
                expect_error=pos_one_should_error,
                description="Positive one" + (" (violates upper bound)" if pos_one_should_error else ""),
            )
        )

        # Lower boundary (ge - 1)
        if ge_val is not None:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="below_ge",
                    value=ge_val - 1,
                    expect_error=True,
                    description=f"Value {ge_val - 1} below ge={ge_val}",
                )
            )
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="at_ge",
                    value=ge_val,
                    expect_error=False,
                    description=f"Value exactly at ge={ge_val}",
                )
            )

        # Lower boundary (gt + 1 — valid; gt — invalid)
        if gt_val is not None:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="at_gt",
                    value=gt_val,
                    expect_error=True,
                    description=f"Value at gt={gt_val} (not >)",
                )
            )
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="above_gt",
                    value=gt_val + 1,
                    expect_error=False,
                    description=f"Value {gt_val + 1} above gt={gt_val}",
                )
            )

        # Upper boundary (le + 1)
        if le_val is not None:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="above_le",
                    value=le_val + 1,
                    expect_error=True,
                    description=f"Value {le_val + 1} above le={le_val}",
                )
            )
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="at_le",
                    value=le_val,
                    expect_error=False,
                    description=f"Value exactly at le={le_val}",
                )
            )

        # Upper boundary (lt — 1 valid; lt — invalid)
        if lt_val is not None:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="at_lt",
                    value=lt_val,
                    expect_error=True,
                    description=f"Value at lt={lt_val} (not <)",
                )
            )
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="below_lt",
                    value=lt_val - 1,
                    expect_error=False,
                    description=f"Value {lt_val - 1} below lt={lt_val}",
                )
            )

        # None
        if is_optional:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="none",
                    value=None,
                    expect_error=False,
                    description="Optional int should accept None",
                )
            )

        return cases

    def _float_edge_cases(
        self, field_name: str, field_info: FieldInfo, is_optional: bool
    ) -> list[EdgeCase]:
        cases: list[EdgeCase] = []
        c = _extract_constraints(field_info)
        ge_val = c["ge"]
        le_val = c["le"]

        # Zero
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="zero",
                value=0.0,
                expect_error=False,
                description="Zero float",
            )
        )

        # Negative one
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="negative_one",
                value=-1.0,
                expect_error=False,
                description="Negative one float",
            )
        )

        # Positive one
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="positive_one",
                value=1.0,
                expect_error=False,
                description="Positive one float",
            )
        )

        # NaN
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="nan",
                value=float("nan"),
                expect_error=True,
                description="NaN should be rejected by Pydantic",
            )
        )

        # Infinite
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="inf",
                value=float("inf"),
                expect_error=False,
                description="Infinite float",
            )
        )

        # Negative infinite
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="neg_inf",
                value=float("-inf"),
                expect_error=False,
                description="Negative infinite float",
            )
        )

        # Boundary constraints
        if ge_val is not None:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="below_ge",
                    value=float(ge_val) - 0.001,
                    expect_error=True,
                    description=f"Float below ge={ge_val}",
                )
            )
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="at_ge",
                    value=float(ge_val),
                    expect_error=False,
                    description=f"Float exactly at ge={ge_val}",
                )
            )
        if le_val is not None:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="above_le",
                    value=float(le_val) + 0.001,
                    expect_error=True,
                    description=f"Float above le={le_val}",
                )
            )
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="at_le",
                    value=float(le_val),
                    expect_error=False,
                    description=f"Float exactly at le={le_val}",
                )
            )

        # None
        if is_optional:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="none",
                    value=None,
                    expect_error=False,
                    description="Optional float should accept None",
                )
            )

        return cases

    def _bool_edge_cases(
        self, field_name: str, field_info: FieldInfo, is_optional: bool
    ) -> list[EdgeCase]:
        cases: list[EdgeCase] = []

        # True / False are both valid
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="true_val",
                value=True,
                expect_error=False,
                description="bool True is valid",
            )
        )
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="false_val",
                value=False,
                expect_error=False,
                description="bool False is valid",
            )
        )

        if is_optional:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="none",
                    value=None,
                    expect_error=False,
                    description="Optional bool should accept None",
                )
            )

        return cases

    def _list_edge_cases(
        self,
        field_name: str,
        field_info: FieldInfo,
        is_optional: bool,
        inner_args: tuple[type, ...],
    ) -> list[EdgeCase]:
        cases: list[EdgeCase] = []
        c = _extract_constraints(field_info)
        min_len = c["min_length"] or 0
        max_len = c["max_length"]
        item_type = inner_args[0] if inner_args else str

        # Generate a valid single item
        single_item = self._default_value_for_type(item_type)

        # Empty list
        if min_len > 0:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="empty",
                    value=[],
                    expect_error=True,
                    description=f"Empty list violates min_length={min_len}",
                )
            )
        else:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="empty",
                    value=[],
                    expect_error=False,
                    description="Empty list is valid",
                )
            )

        # Single item
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="single_item",
                value=[single_item],
                expect_error=False,
                description="Single-item list",
            )
        )

        # Many items
        many = [single_item] * MANY_ITEMS_COUNT
        expect_err = max_len is not None and MANY_ITEMS_COUNT > max_len
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="many_items",
                value=many,
                expect_error=expect_err,
                description=f"{MANY_ITEMS_COUNT}-item list"
                + (f" (exceeds max_length={max_len})" if expect_err else ""),
            )
        )

        # Wrong item type
        wrong_item: Any = "not_the_right_type"
        if item_type is int:
            wrong_item = "string_not_int"
        elif item_type is float:
            wrong_item = "string_not_float"
        elif item_type is bool:
            wrong_item = 42
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="wrong_item_type",
                value=[wrong_item],
                expect_error=True,
                description=f"List with wrong item type (expected {item_type.__name__})",
            )
        )

        # None
        if is_optional:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="none",
                    value=None,
                    expect_error=False,
                    description="Optional list should accept None",
                )
            )

        return cases

    def _nested_edge_cases(
        self,
        field_name: str,
        field_info: FieldInfo,
        is_optional: bool,
        nested_class: type[BaseModel],
    ) -> list[EdgeCase]:
        cases: list[EdgeCase] = []

        # Valid nested data (empty dict for base case)
        valid_nested = self._valid_baseline_for_model(nested_class)
        cases.append(
            EdgeCase(
                field_name=field_name,
                label="valid_nested",
                value=valid_nested,
                expect_error=False,
                description="Valid nested model data",
            )
        )
        # Invalid nested data — wrong types in required fields
        invalid_nested: dict[str, Any] = {}
        for nf_name, nf_info in nested_class.model_fields.items():
            nf_annotation = self._unwrap_optional(nf_info.annotation)
            if nf_info.is_required() and nf_annotation is str:
                invalid_nested[nf_name] = 12345  # wrong type
            elif nf_info.is_required() and nf_annotation is int:
                invalid_nested[nf_name] = "not_an_int"
            elif nf_info.is_required():
                invalid_nested[nf_name] = None
        if invalid_nested:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="invalid_nested",
                    value=invalid_nested,
                    expect_error=True,
                    description="Invalid nested data should raise ValidationError",
                )
            )

        # None
        if is_optional:
            cases.append(
                EdgeCase(
                    field_name=field_name,
                    label="none",
                    value=None,
                    expect_error=False,
                    description="Optional nested model should accept None",
                )
            )

        return cases

    # ------------------------------------------------------------------
    # Valid baseline generation
    # ------------------------------------------------------------------

    def _valid_baseline_for_model(
        self, model_class: type[BaseModel]
    ) -> dict[str, Any]:
        """Generate a valid dict for instantiating *model_class*."""
        result: dict[str, Any] = {}
        for fname, finfo in model_class.model_fields.items():
            result[fname] = self._default_field_value(fname, finfo)
        return result

    def _valid_baseline_data(self) -> dict[str, Any]:
        """Lazily build and cache valid baseline for ``self.schema_class``."""
        if self._valid_baseline is None:
            self._valid_baseline = self._valid_baseline_for_model(
                self.schema_class
            )
        return self._valid_baseline

    def _default_field_value(
        self, field_name: str, field_info: FieldInfo
    ) -> Any:
        """Return a sensible default value for *field_info*."""
        annotation = field_info.annotation
        inner_type = self._unwrap_optional(annotation)
        if field_info.default is not PydanticUndefined and field_info.default is not None:
            return field_info.default
        if field_info.default_factory is not None:
            return field_info.default_factory()

        return self._default_value_for_type(inner_type, field_info)

    def _default_value_for_type(
        self, typ: type, field_info: FieldInfo | None = None
    ) -> Any:
        """Produce a reasonable valid default for *typ*."""
        if typ is str:
            min_len = (_extract_constraints(field_info)["min_length"] or 0) if field_info else 0
            base = "test_value"
            return base.ljust(max(len(base), min_len), "x")
        if typ is int:
            ge_val = _extract_constraints(field_info)["ge"] if field_info else None
            le_val = _extract_constraints(field_info)["le"] if field_info else None
            if ge_val is not None and le_val is not None:
                return max(ge_val, min(le_val, (ge_val + le_val) // 2))
            if ge_val is not None:
                return ge_val
            if le_val is not None:
                return le_val
            return 1
        if typ is float:
            ge_val = _extract_constraints(field_info)["ge"] if field_info else None
            le_val = _extract_constraints(field_info)["le"] if field_info else None
            if ge_val is not None and le_val is not None:
                return float((ge_val + le_val) / 2)
            if ge_val is not None:
                return float(ge_val)
            if le_val is not None:
                return float(le_val)
            return 1.0
        if typ is bool:
            return True
        if typ is bytes:
            return b"test_bytes"
        if typ is Decimal:
            return Decimal("1.0")
        if typ is UUID:
            return UUID("12345678-1234-5678-1234-567812345678")
        if typ in (datetime.datetime,):
            return datetime.datetime(2026, 1, 1, 12, 0, 0)
        if typ in (datetime.date,):
            return datetime.date(2026, 1, 1)
        if typ in (datetime.time,):
            return datetime.time(12, 0, 0)

        origin = get_origin(typ)
        args = get_args(typ)
        if origin is list:
            item_type = args[0] if args else str
            return [self._default_value_for_type(item_type)]
        if isinstance(typ, type):
            if issubclass(typ, BaseModel):
                return self._valid_baseline_for_model(typ)

        # Fallback for enums, literals, etc.
        if isinstance(typ, type) and hasattr(typ, "__members__"):
            # Enum
            return next(iter(typ.__members__.values()))
        if origin is Literal:
            return args[0] if args else None
        if origin is dict:
            return {}

        return None

    # ------------------------------------------------------------------
    # Type helpers
    # ------------------------------------------------------------------


    @staticmethod
    def _resolve_base_type(typ: type) -> type:
        """Resolve the concrete base type from potentially Annotated wrappers.

        For example, ``Annotated[str, StringConstraints(min_length=1)]``
        resolves to ``str``.
        """
        from typing import Annotated as AnnotatedType

        origin = get_origin(typ)
        if origin is AnnotatedType:
            args = get_args(typ)
            if args:
                return args[0]
        return typ

    def _is_nested_model_field(self, field_info: FieldInfo) -> bool:
        """Check whether *field_info* represents a nested BaseModel field."""
        annotation = field_info.annotation
        inner = self._unwrap_optional(annotation)
        return self._is_base_model_type(self._resolve_base_type(inner))

    @staticmethod
    def _is_optional(annotation: type | None) -> bool:
        """Check whether the annotation allows None."""
        if annotation is None:
            return False
        origin = get_origin(annotation)
        args = get_args(annotation)
        # Union[X, None] or X | None
        if origin in (UnionType, Union):
            return NoneType in args or type(None) in args
        if isinstance(annotation, type):
            return False
        return False

    @staticmethod
    def _unwrap_optional(annotation: type) -> type:
        """Return the inner type for Optional[X], otherwise *annotation*."""
        origin = get_origin(annotation)
        args = get_args(annotation)
        if origin in (UnionType, Union):
            non_none = [a for a in args if a is not NoneType and a is not type(None)]
            if len(non_none) == 1:
                return non_none[0]
        return annotation

    @staticmethod
    def _is_base_model_type(typ: type) -> bool:
        """Check whether *typ* is a Pydantic BaseModel subclass."""
        if not isinstance(typ, type):
            return False
        try:
            return issubclass(typ, BaseModel)
        except TypeError:
            return False

    def _type_mismatch_value(self, typ: type) -> Any:
        """Return a wrong-type value for *typ*."""
        if typ is str:
            return 12345
        if typ is int:
            return "not_an_int"
        if typ is float:
            return "not_a_float"
        if typ is bool:
            return "not_a_bool"
        if typ is bytes:
            return "not_bytes"
        origin = get_origin(typ)
        if origin is list:
            return "not_a_list"
        if origin is dict:
            return "not_a_dict"
        return None  # fallback — None will error on required non-optional

    # ------------------------------------------------------------------
    # Code rendering
    # ------------------------------------------------------------------

    def _render_test_module(
        self,
        schema_name: str,
        edge_cases: list[EdgeCase],
    ) -> str:
        """Render the full pytest module string."""
        module_path = self.schema_class.__module__
        schema_cls_name = self.schema_class.__name__
        valid_data = self._valid_baseline_data()

        lines: list[str] = []
        lines.append('"""')
        lines.append(
            f"Tests for {schema_cls_name} — auto-generated by "
            f"django_matt.guardrails.testgen.SchemaTestGenerator."
        )
        lines.append("")
        lines.append(f"Schema module: {module_path}")
        lines.append(f"Schema class:  {schema_cls_name}")
        lines.append(f"Total cases:  {len(edge_cases)}")
        lines.append('"""')
        lines.append("")
        lines.append("from __future__ import annotations")
        lines.append("")
        lines.append("import math")
        lines.append("import pytest")
        lines.append("from pydantic import ValidationError")
        lines.append(f"from {module_path} import {schema_cls_name}")
        lines.append("")
        lines.append("")
        lines.append(f"# Valid baseline data for {schema_cls_name}")
        lines.append(
            f"_VALID_DATA: dict = {self._format_py_value(valid_data)}"
        )
        lines.append("")
        lines.append("")
        lines.append(f"class Test{schema_cls_name}Validation:")
        lines.append(f'    """Edge-case validation tests for {schema_cls_name}."""')
        lines.append("")

        # Group edge cases by field
        from itertools import groupby

        sorted_cases = sorted(edge_cases, key=lambda c: c.field_name)
        for field_name, group in groupby(sorted_cases, key=lambda c: c.field_name):
            field_cases = list(group)
            lines.append(f"    # ── {field_name} ──")
            lines.append("")
            for case in field_cases:
                test_name = f"test_{case.field_name}_{case.label}"
                lines.extend(
                    self._render_single_test(test_name, case, valid_data)
                )

        return "\n".join(lines) + "\n"

    def _render_single_test(
        self,
        test_name: str,
        case: EdgeCase,
        valid_data: dict[str, Any],
    ) -> list[str]:
        """Render a single pytest test method."""
        lines: list[str] = []

        # Docstring
        desc = case.description or f"Edge case: {case.label}"
        lines.append(f"    def {test_name}(self) -> None:")
        lines.append(f'        """{desc}."""')

        if case.value is ...:
            # Missing key — exclude from data dict
            data_expr = (
                "{k: v for k, v in _VALID_DATA.items() "
                f"if k != {case.field_name!r}}}"
            )
            lines.append(f"        data = {data_expr}")
        else:
            val_str = self._format_py_value(case.value)
            lines.append(
                f"        data = {{**_VALID_DATA, "
                f"{case.field_name!r}: {val_str}}}"
            )

        if case.expect_error:
            lines.append("        with pytest.raises(ValidationError):")
            lines.append(
                f"            {self.schema_class.__name__}(**data)"
            )
        else:
            lines.append(
                f"        obj = {self.schema_class.__name__}(**data)"
            )
            # Add a lightweight assertion for valid cases
            # Skip assertion if field is a nested BaseModel (obj.field is instance, not dict)
            field_info = self.model_fields.get(case.field_name)
            if field_info is not None and not self._is_nested_model_field(field_info):
                val_str = self._format_py_value(case.value)
                lines.append(
                    f"        assert obj.{case.field_name} == {val_str}"
                )
        lines.append("")
        return lines

    @staticmethod
    def _format_py_value(value: Any) -> str:
        """Format a Python value as a code literal string."""
        if value is None:
            return "None"
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, str):
            # Use repr and handle multi-line
            r = repr(value)
            if "\n" in value or len(r) > 80:
                r = repr(value[:120]) + " ..."
            return r
        if isinstance(value, float):
            if math.isnan(value):
                return "float('nan')"
            if math.isinf(value):
                return "float('inf')" if value > 0 else "float('-inf')"
            return repr(value)
        if isinstance(value, int):
            return repr(value)
        if isinstance(value, list):
            if not value:
                return "[]"
            if len(value) <= 3:
                items = ", ".join(
                    SchemaTestGenerator._format_py_value(v) for v in value
                )
                return f"[{items}]"
            first = SchemaTestGenerator._format_py_value(value[0])
            return f"[{first}] * {len(value)}"
        if isinstance(value, dict):
            if not value:
                return "{}"
            items = ", ".join(
                f"{SchemaTestGenerator._format_py_value(k)}: "
                f"{SchemaTestGenerator._format_py_value(v)}"
                for k, v in list(value.items())[:5]
            )
            return f"{{{items}}}"
        if isinstance(value, bytes):
            return repr(value)
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            cls_name = type(value).__name__
            args_str = repr(value.isoformat())
            return f"datetime.{cls_name.split('.')[-1]}.fromisoformat({args_str})"
        if isinstance(value, Decimal):
            return f"Decimal('{value}')"
        if isinstance(value, UUID):
            return f"UUID('{value}')"
        return repr(value)


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------


def generate_tests(schema_class: type[BaseModel], model_name: str | None = None) -> str:
    """Convenience: generate tests for *schema_class*.

    >>> from myapp.schemas import UserCreateSchema
    >>> code = generate_tests(UserCreateSchema)
    >>> print(code)
    """
    return SchemaTestGenerator(schema_class).generate_tests(model_name=model_name)


def generate_test_file(
    schema_class: type[BaseModel], output_path: Path
) -> Path:
    """Convenience: write tests for *schema_class* to *output_path*."""
    return SchemaTestGenerator(schema_class).generate_test_file(output_path)
