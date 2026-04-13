"""
Generate client-side validation schemas from Django form validators.

Supports Zod (TypeScript), Yup (TypeScript), and JSON Schema output.
"""

from __future__ import annotations

from typing import Any

import django.forms as django_forms
from django.core.validators import (
    EmailValidator,
    MaxLengthValidator,
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
    RegexValidator,
    URLValidator,
)

# =============================================================================
# Field analysis
# =============================================================================


def _analyze_field(name: str, field: django_forms.Field) -> dict[str, Any]:
    """Extract validation metadata from a Django form field."""
    info: dict[str, Any] = {
        "name": name,
        "required": field.required,
        "type": "string",
        "constraints": [],
    }

    # Determine base type
    if isinstance(field, django_forms.BooleanField):
        info["type"] = "boolean"
    elif isinstance(field, django_forms.IntegerField):
        info["type"] = "integer"
    elif isinstance(field, (django_forms.FloatField, django_forms.DecimalField)):
        info["type"] = "number"
    elif isinstance(field, django_forms.DateTimeField):
        info["type"] = "datetime"
    elif isinstance(field, django_forms.DateField):
        info["type"] = "date"
    elif isinstance(field, django_forms.TimeField):
        info["type"] = "time"
    elif isinstance(field, django_forms.FileField):
        info["type"] = "file"
    elif isinstance(field, django_forms.MultipleChoiceField):
        info["type"] = "array"
        info["choices"] = [str(v) for v, _ in field.choices]
    elif isinstance(field, django_forms.ChoiceField):
        info["type"] = "enum"
        info["choices"] = [str(v) for v, _ in field.choices]
    elif isinstance(field, django_forms.EmailField):
        info["type"] = "email"
    elif isinstance(field, django_forms.URLField):
        info["type"] = "url"

    # Extract constraints from field attributes
    if hasattr(field, "max_length") and field.max_length is not None:
        info["constraints"].append(("maxLength", field.max_length))
    if hasattr(field, "min_length") and field.min_length is not None:
        info["constraints"].append(("minLength", field.min_length))
    if hasattr(field, "max_value") and field.max_value is not None:
        info["constraints"].append(("max", field.max_value))
    if hasattr(field, "min_value") and field.min_value is not None:
        info["constraints"].append(("min", field.min_value))

    # Extract constraints from validators
    for validator in field.validators:
        if isinstance(validator, MaxLengthValidator):
            if not any(c[0] == "maxLength" for c in info["constraints"]):
                info["constraints"].append(("maxLength", validator.limit_value))
        elif isinstance(validator, MinLengthValidator):
            if not any(c[0] == "minLength" for c in info["constraints"]):
                info["constraints"].append(("minLength", validator.limit_value))
        elif isinstance(validator, MaxValueValidator):
            if not any(c[0] == "max" for c in info["constraints"]):
                info["constraints"].append(("max", validator.limit_value))
        elif isinstance(validator, MinValueValidator):
            if not any(c[0] == "min" for c in info["constraints"]):
                info["constraints"].append(("min", validator.limit_value))
        elif isinstance(validator, EmailValidator):
            info["type"] = "email"
        elif isinstance(validator, URLValidator):
            info["type"] = "url"
        elif isinstance(validator, RegexValidator):
            pattern = (
                validator.regex.pattern
                if hasattr(validator.regex, "pattern")
                else str(validator.regex)
            )
            info["constraints"].append(("regex", pattern))

    return info


def _get_form_instance(
    form_class: type[django_forms.BaseForm] | django_forms.BaseForm,
) -> django_forms.BaseForm:
    """Get a form instance from a class or instance."""
    if isinstance(form_class, type):
        return form_class()
    return form_class


# =============================================================================
# Zod schema generation
# =============================================================================


def _escape_ts_string(s: str) -> str:
    """Escape a string for use in TypeScript."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def form_to_zod(form_class: type[django_forms.BaseForm] | django_forms.BaseForm) -> str:
    """
    Generate a Zod validation schema from a Django form.

    Args:
        form_class: Django Form class or instance.

    Returns:
        TypeScript code string defining a Zod schema.
    """
    form = _get_form_instance(form_class)
    lines: list[str] = ['import { z } from "zod";', "", "export const formSchema = z.object({"]

    for name, field in form.fields.items():
        info = _analyze_field(name, field)
        chain = _zod_base_type(info)

        # Apply constraints
        for constraint_type, value in info["constraints"]:
            if constraint_type == "maxLength":
                chain += f".max({value})"
            elif constraint_type == "minLength":
                chain += f".min({value})"
            elif constraint_type == "max":
                chain += f".max({value})"
            elif constraint_type == "min":
                chain += f".min({value})"
            elif constraint_type == "regex":
                escaped = _escape_ts_string(value)
                chain += f".regex(/{escaped}/)"

        if not info["required"]:
            chain += ".optional()"

        lines.append(f"  {name}: {chain},")

    lines.append("});")
    lines.append("")
    lines.append("export type FormData = z.infer<typeof formSchema>;")
    lines.append("")

    return "\n".join(lines)


def _zod_base_type(info: dict[str, Any]) -> str:
    """Get the Zod base type for a field."""
    field_type = info["type"]
    if field_type == "boolean":
        return "z.boolean()"
    if field_type in ("integer", "number"):
        return "z.number()"
    if field_type == "email":
        return "z.string().email()"
    if field_type == "url":
        return "z.string().url()"
    if field_type == "date":
        return "z.string().date()"
    if field_type == "datetime":
        return "z.string().datetime()"
    if field_type == "time":
        return "z.string().time()"
    if field_type == "file":
        return "z.instanceof(File)"
    if field_type == "enum":
        choices = info.get("choices", [])
        if choices:
            values = ", ".join(f'"{_escape_ts_string(c)}"' for c in choices)
            return f"z.enum([{values}])"
        return "z.string()"
    if field_type == "array":
        choices = info.get("choices", [])
        if choices:
            values = ", ".join(f'"{_escape_ts_string(c)}"' for c in choices)
            return f"z.array(z.enum([{values}]))"
        return "z.array(z.string())"
    return "z.string()"


# =============================================================================
# Yup schema generation
# =============================================================================


def form_to_yup(form_class: type[django_forms.BaseForm] | django_forms.BaseForm) -> str:
    """
    Generate a Yup validation schema from a Django form.

    Args:
        form_class: Django Form class or instance.

    Returns:
        TypeScript code string defining a Yup schema.
    """
    form = _get_form_instance(form_class)
    lines: list[str] = ['import * as yup from "yup";', "", "export const formSchema = yup.object({"]

    for name, field in form.fields.items():
        info = _analyze_field(name, field)
        chain = _yup_base_type(info)

        if info["required"]:
            chain += ".required()"

        for constraint_type, value in info["constraints"]:
            if constraint_type == "maxLength":
                chain += f".max({value})"
            elif constraint_type == "minLength":
                chain += f".min({value})"
            elif constraint_type == "max":
                chain += f".max({value})"
            elif constraint_type == "min":
                chain += f".min({value})"
            elif constraint_type == "regex":
                escaped = _escape_ts_string(value)
                chain += f".matches(/{escaped}/)"

        if not info["required"]:
            chain += ".optional()"

        lines.append(f"  {name}: {chain},")

    lines.append("});")
    lines.append("")
    lines.append("export type FormData = yup.InferType<typeof formSchema>;")
    lines.append("")

    return "\n".join(lines)


def _yup_base_type(info: dict[str, Any]) -> str:
    """Get the Yup base type for a field."""
    field_type = info["type"]
    if field_type == "boolean":
        return "yup.boolean()"
    if field_type in ("integer", "number"):
        return "yup.number()"
    if field_type == "email":
        return "yup.string().email()"
    if field_type == "url":
        return "yup.string().url()"
    if field_type in ("date", "datetime", "time"):
        return "yup.string()"
    if field_type == "file":
        return "yup.mixed()"
    if field_type == "enum":
        choices = info.get("choices", [])
        if choices:
            values = ", ".join(f'"{_escape_ts_string(c)}"' for c in choices)
            return f"yup.string().oneOf([{values}])"
        return "yup.string()"
    if field_type == "array":
        choices = info.get("choices", [])
        if choices:
            values = ", ".join(f'"{_escape_ts_string(c)}"' for c in choices)
            return f"yup.array().of(yup.string().oneOf([{values}]))"
        return "yup.array().of(yup.string())"
    return "yup.string()"


# =============================================================================
# JSON Schema generation
# =============================================================================


def form_to_json_schema(
    form_class: type[django_forms.BaseForm] | django_forms.BaseForm,
) -> dict[str, Any]:
    """
    Generate a JSON Schema from a Django form.

    Args:
        form_class: Django Form class or instance.

    Returns:
        JSON Schema dict.
    """
    form = _get_form_instance(form_class)
    properties: dict[str, Any] = {}
    required_fields: list[str] = []

    for name, field in form.fields.items():
        info = _analyze_field(name, field)
        prop = _json_schema_property(info)
        properties[name] = prop

        if info["required"]:
            required_fields.append(name)

    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": properties,
    }
    if required_fields:
        schema["required"] = required_fields

    return schema


def _json_schema_property(info: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON Schema property for a field."""
    field_type = info["type"]
    prop: dict[str, Any] = {}

    if field_type == "boolean":
        prop["type"] = "boolean"
    elif field_type == "integer":
        prop["type"] = "integer"
    elif field_type == "number":
        prop["type"] = "number"
    elif field_type == "email":
        prop["type"] = "string"
        prop["format"] = "email"
    elif field_type == "url":
        prop["type"] = "string"
        prop["format"] = "uri"
    elif field_type == "date":
        prop["type"] = "string"
        prop["format"] = "date"
    elif field_type == "datetime":
        prop["type"] = "string"
        prop["format"] = "date-time"
    elif field_type == "time":
        prop["type"] = "string"
        prop["format"] = "time"
    elif field_type == "file":
        prop["type"] = "string"
        prop["format"] = "binary"
    elif field_type == "enum":
        prop["type"] = "string"
        choices = info.get("choices", [])
        if choices:
            prop["enum"] = choices
    elif field_type == "array":
        prop["type"] = "array"
        choices = info.get("choices", [])
        if choices:
            prop["items"] = {"type": "string", "enum": choices}
        else:
            prop["items"] = {"type": "string"}
    else:
        prop["type"] = "string"

    # Apply constraints
    for constraint_type, value in info["constraints"]:
        if constraint_type == "maxLength":
            prop["maxLength"] = value
        elif constraint_type == "minLength":
            prop["minLength"] = value
        elif constraint_type == "max":
            prop["maximum"] = value
        elif constraint_type == "min":
            prop["minimum"] = value
        elif constraint_type == "regex":
            prop["pattern"] = value

    return prop
