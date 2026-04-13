"""
Fluent form builder API.

Build Django forms programmatically with a chainable interface,
then render them using the component system or generate validation schemas.
"""

from __future__ import annotations

from typing import Any

import django.forms as django_forms

from django_matt.forms.bridge import render_form
from django_matt.forms.validation import form_to_zod


class FormBuilder:
    """
    Fluent builder for Django forms.

    Usage:
        form = (FormBuilder("contact")
            .text("name", required=True, max_length=100)
            .email("email", required=True)
            .select("department", choices=[("eng", "Engineering"), ("sales", "Sales")])
            .textarea("message", rows=5)
            .checkbox("subscribe", label="Subscribe to newsletter")
            .file("attachment", accept=".pdf,.doc")
            .submit("Send Message")
            .build())
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._fields: list[tuple[str, dict[str, Any]]] = []
        self._submit_label: str = "Submit"
        self._method: str = "post"
        self._action: str = ""

    # -------------------------------------------------------------------------
    # Field methods
    # -------------------------------------------------------------------------

    def text(
        self,
        name: str,
        *,
        label: str | None = None,
        required: bool = False,
        max_length: int | None = None,
        min_length: int | None = None,
        help_text: str = "",
        initial: Any = None,
        placeholder: str = "",
    ) -> FormBuilder:
        """Add a text field."""
        self._fields.append(
            (
                name,
                {
                    "type": "char",
                    "label": label,
                    "required": required,
                    "max_length": max_length,
                    "min_length": min_length,
                    "help_text": help_text,
                    "initial": initial,
                    "placeholder": placeholder,
                },
            )
        )
        return self

    def email(
        self,
        name: str,
        *,
        label: str | None = None,
        required: bool = False,
        help_text: str = "",
        initial: Any = None,
    ) -> FormBuilder:
        """Add an email field."""
        self._fields.append(
            (
                name,
                {
                    "type": "email",
                    "label": label,
                    "required": required,
                    "help_text": help_text,
                    "initial": initial,
                },
            )
        )
        return self

    def password(
        self,
        name: str,
        *,
        label: str | None = None,
        required: bool = False,
        min_length: int | None = None,
        max_length: int | None = None,
        help_text: str = "",
    ) -> FormBuilder:
        """Add a password field."""
        self._fields.append(
            (
                name,
                {
                    "type": "password",
                    "label": label,
                    "required": required,
                    "min_length": min_length,
                    "max_length": max_length,
                    "help_text": help_text,
                },
            )
        )
        return self

    def number(
        self,
        name: str,
        *,
        label: str | None = None,
        required: bool = False,
        min_value: int | float | None = None,
        max_value: int | float | None = None,
        help_text: str = "",
        initial: Any = None,
        decimal_places: int | None = None,
    ) -> FormBuilder:
        """Add a number field."""
        self._fields.append(
            (
                name,
                {
                    "type": "decimal" if decimal_places is not None else "integer",
                    "label": label,
                    "required": required,
                    "min_value": min_value,
                    "max_value": max_value,
                    "help_text": help_text,
                    "initial": initial,
                    "decimal_places": decimal_places,
                },
            )
        )
        return self

    def textarea(
        self,
        name: str,
        *,
        label: str | None = None,
        required: bool = False,
        max_length: int | None = None,
        rows: int = 3,
        help_text: str = "",
        initial: Any = None,
    ) -> FormBuilder:
        """Add a textarea field."""
        self._fields.append(
            (
                name,
                {
                    "type": "textarea",
                    "label": label,
                    "required": required,
                    "max_length": max_length,
                    "rows": rows,
                    "help_text": help_text,
                    "initial": initial,
                },
            )
        )
        return self

    def select(
        self,
        name: str,
        *,
        choices: list[tuple[str, str]],
        label: str | None = None,
        required: bool = False,
        help_text: str = "",
        initial: Any = None,
    ) -> FormBuilder:
        """Add a select/dropdown field."""
        self._fields.append(
            (
                name,
                {
                    "type": "choice",
                    "label": label,
                    "required": required,
                    "choices": choices,
                    "help_text": help_text,
                    "initial": initial,
                },
            )
        )
        return self

    def multiselect(
        self,
        name: str,
        *,
        choices: list[tuple[str, str]],
        label: str | None = None,
        required: bool = False,
        help_text: str = "",
        initial: Any = None,
    ) -> FormBuilder:
        """Add a multi-select field."""
        self._fields.append(
            (
                name,
                {
                    "type": "multiple_choice",
                    "label": label,
                    "required": required,
                    "choices": choices,
                    "help_text": help_text,
                    "initial": initial,
                },
            )
        )
        return self

    def checkbox(
        self,
        name: str,
        *,
        label: str | None = None,
        required: bool = False,
        help_text: str = "",
        initial: bool = False,
    ) -> FormBuilder:
        """Add a checkbox field."""
        self._fields.append(
            (
                name,
                {
                    "type": "boolean",
                    "label": label,
                    "required": required,
                    "help_text": help_text,
                    "initial": initial,
                },
            )
        )
        return self

    def radio(
        self,
        name: str,
        *,
        choices: list[tuple[str, str]],
        label: str | None = None,
        required: bool = False,
        help_text: str = "",
        initial: Any = None,
    ) -> FormBuilder:
        """Add a radio button group."""
        self._fields.append(
            (
                name,
                {
                    "type": "radio",
                    "label": label,
                    "required": required,
                    "choices": choices,
                    "help_text": help_text,
                    "initial": initial,
                },
            )
        )
        return self

    def date(
        self,
        name: str,
        *,
        label: str | None = None,
        required: bool = False,
        help_text: str = "",
        initial: Any = None,
    ) -> FormBuilder:
        """Add a date field."""
        self._fields.append(
            (
                name,
                {
                    "type": "date",
                    "label": label,
                    "required": required,
                    "help_text": help_text,
                    "initial": initial,
                },
            )
        )
        return self

    def file(
        self,
        name: str,
        *,
        label: str | None = None,
        required: bool = False,
        accept: str = "",
        help_text: str = "",
    ) -> FormBuilder:
        """Add a file upload field."""
        self._fields.append(
            (
                name,
                {
                    "type": "file",
                    "label": label,
                    "required": required,
                    "accept": accept,
                    "help_text": help_text,
                },
            )
        )
        return self

    def hidden(
        self,
        name: str,
        *,
        initial: Any = None,
    ) -> FormBuilder:
        """Add a hidden field."""
        self._fields.append(
            (
                name,
                {
                    "type": "hidden",
                    "initial": initial,
                },
            )
        )
        return self

    # -------------------------------------------------------------------------
    # Form-level methods
    # -------------------------------------------------------------------------

    def submit(self, label: str) -> FormBuilder:
        """Set the submit button label."""
        self._submit_label = label
        return self

    def method(self, method: str) -> FormBuilder:
        """Set the form HTTP method."""
        self._method = method
        return self

    def action(self, url: str) -> FormBuilder:
        """Set the form action URL."""
        self._action = url
        return self

    # -------------------------------------------------------------------------
    # Build / render / export
    # -------------------------------------------------------------------------

    def build(self) -> type[django_forms.Form]:
        """
        Build and return a Django Form class.

        Returns:
            A dynamically created Django Form class.
        """
        fields: dict[str, django_forms.Field] = {}

        for name, config in self._fields:
            fields[name] = _build_django_field(config)

        # Create the form class dynamically
        form_attrs = dict(fields)
        form_class = type(
            f"{self._name.title().replace(' ', '')}Form",
            (django_forms.Form,),
            form_attrs,
        )
        return form_class

    def render(self, theme: str = "shadcn") -> str:
        """
        Render the form directly to HTML.

        Args:
            theme: CSS theme ("shadcn", "tailwind", "bootstrap").

        Returns:
            HTML string.
        """
        form_class = self.build()
        return render_form(
            form_class,
            theme=theme,
            method=self._method,
            action=self._action,
        )

    def to_zod(self) -> str:
        """
        Generate a Zod validation schema.

        Returns:
            TypeScript code string.
        """
        form_class = self.build()
        return form_to_zod(form_class)


def _build_django_field(config: dict[str, Any]) -> django_forms.Field:
    """Build a Django form field from builder config."""
    field_type = config["type"]
    label = config.get("label")
    required = config.get("required", False)
    help_text = config.get("help_text", "")
    initial = config.get("initial")

    common: dict[str, Any] = {}
    if label is not None:
        common["label"] = label
    common["required"] = required
    if help_text:
        common["help_text"] = help_text
    if initial is not None:
        common["initial"] = initial

    if field_type == "char":
        kwargs: dict[str, Any] = {**common}
        if config.get("max_length") is not None:
            kwargs["max_length"] = config["max_length"]
        if config.get("min_length") is not None:
            kwargs["min_length"] = config["min_length"]
        widget_attrs: dict[str, str] = {}
        if config.get("placeholder"):
            widget_attrs["placeholder"] = config["placeholder"]
        if widget_attrs:
            kwargs["widget"] = django_forms.TextInput(attrs=widget_attrs)
        return django_forms.CharField(**kwargs)

    if field_type == "email":
        return django_forms.EmailField(**common)

    if field_type == "password":
        kwargs = {**common, "widget": django_forms.PasswordInput()}
        if config.get("max_length") is not None:
            kwargs["max_length"] = config["max_length"]
        if config.get("min_length") is not None:
            kwargs["min_length"] = config["min_length"]
        return django_forms.CharField(**kwargs)

    if field_type == "integer":
        kwargs = {**common}
        if config.get("min_value") is not None:
            kwargs["min_value"] = config["min_value"]
        if config.get("max_value") is not None:
            kwargs["max_value"] = config["max_value"]
        return django_forms.IntegerField(**kwargs)

    if field_type == "decimal":
        kwargs = {**common}
        if config.get("min_value") is not None:
            kwargs["min_value"] = config["min_value"]
        if config.get("max_value") is not None:
            kwargs["max_value"] = config["max_value"]
        if config.get("decimal_places") is not None:
            kwargs["decimal_places"] = config["decimal_places"]
            kwargs["max_digits"] = 20  # reasonable default
        return django_forms.DecimalField(**kwargs)

    if field_type == "textarea":
        kwargs = {**common}
        if config.get("max_length") is not None:
            kwargs["max_length"] = config["max_length"]
        rows = config.get("rows", 3)
        kwargs["widget"] = django_forms.Textarea(attrs={"rows": rows})
        return django_forms.CharField(**kwargs)

    if field_type == "choice":
        return django_forms.ChoiceField(
            choices=config.get("choices", []),
            **common,
        )

    if field_type == "multiple_choice":
        return django_forms.MultipleChoiceField(
            choices=config.get("choices", []),
            **common,
        )

    if field_type == "boolean":
        return django_forms.BooleanField(**common)

    if field_type == "radio":
        return django_forms.ChoiceField(
            choices=config.get("choices", []),
            widget=django_forms.RadioSelect(),
            **common,
        )

    if field_type == "date":
        return django_forms.DateField(
            widget=django_forms.DateInput(attrs={"type": "date"}),
            **common,
        )

    if field_type == "file":
        return django_forms.FileField(**common)

    if field_type == "hidden":
        return django_forms.CharField(
            widget=django_forms.HiddenInput(),
            required=False,
            initial=initial,
        )

    # Fallback
    return django_forms.CharField(**common)
