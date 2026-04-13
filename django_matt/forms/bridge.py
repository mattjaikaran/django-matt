"""
Bridge Django forms to django-matt component system.

Introspects Django form fields and maps them to the component system,
preserving validators, help text, error messages, and initial values.
"""

from __future__ import annotations

from html import escape
from typing import Any

import django.forms as django_forms

from django_matt.components.base import ComponentTree, ValidationRule
from django_matt.components.forms import (
    BaseField,
    Checkbox,
    DatePicker,
    EmailField,
    FileUpload,
    Form,
    MultiSelect,
    NumberField,
    PasswordField,
    Select,
    SelectOption,
    SubmitButton,
    Textarea,
    TextField,
)

# =============================================================================
# Theme CSS classes
# =============================================================================

THEME_CLASSES: dict[str, dict[str, str]] = {
    "shadcn": {
        "form": "space-y-6",
        "field_wrapper": "space-y-2",
        "label": "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
        "input": "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        "textarea": "flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        "select": "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        "checkbox": "peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground",
        "help_text": "text-sm text-muted-foreground",
        "error": "text-sm font-medium text-destructive",
        "submit": "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2",
        "error_list": "rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive",
    },
    "tailwind": {
        "form": "space-y-6",
        "field_wrapper": "space-y-1",
        "label": "block text-sm font-medium text-gray-700",
        "input": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
        "textarea": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
        "select": "block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
        "checkbox": "h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
        "help_text": "text-sm text-gray-500",
        "error": "text-sm text-red-600",
        "submit": "inline-flex justify-center rounded-md border border-transparent bg-indigo-600 py-2 px-4 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2",
        "error_list": "rounded-md bg-red-50 p-4 text-sm text-red-700",
    },
    "bootstrap": {
        "form": "",
        "field_wrapper": "mb-3",
        "label": "form-label",
        "input": "form-control",
        "textarea": "form-control",
        "select": "form-select",
        "checkbox": "form-check-input",
        "help_text": "form-text",
        "error": "invalid-feedback d-block",
        "submit": "btn btn-primary",
        "error_list": "alert alert-danger",
    },
}


# =============================================================================
# Django field -> Component mapping
# =============================================================================


def _extract_validators(field: django_forms.Field) -> list[ValidationRule]:
    """Extract validation rules from a Django form field."""
    rules: list[ValidationRule] = []

    if field.required:
        rules.append(
            ValidationRule(
                type="required",
                message=str(field.error_messages.get("required", "This field is required.")),
            )
        )

    if hasattr(field, "max_length") and field.max_length is not None:
        rules.append(
            ValidationRule(
                type="maxLength",
                value=field.max_length,
                message=f"Must be at most {field.max_length} characters.",
            )
        )

    if hasattr(field, "min_length") and field.min_length is not None:
        rules.append(
            ValidationRule(
                type="minLength",
                value=field.min_length,
                message=f"Must be at least {field.min_length} characters.",
            )
        )

    if hasattr(field, "max_value") and field.max_value is not None:
        rules.append(
            ValidationRule(
                type="max",
                value=field.max_value,
                message=f"Must be at most {field.max_value}.",
            )
        )

    if hasattr(field, "min_value") and field.min_value is not None:
        rules.append(
            ValidationRule(
                type="min",
                value=field.min_value,
                message=f"Must be at least {field.min_value}.",
            )
        )

    # Check validators list for regex
    for validator in field.validators:
        validator_cls = type(validator).__name__
        if validator_cls == "RegexValidator":
            rules.append(
                ValidationRule(
                    type="pattern",
                    value=validator.regex.pattern
                    if hasattr(validator.regex, "pattern")
                    else str(validator.regex),
                    message=str(validator.message) if validator.message else "Invalid format.",
                )
            )
        elif validator_cls == "EmailValidator":
            if not any(r.type == "email" for r in rules):
                rules.append(ValidationRule(type="email", message="Enter a valid email address."))
        elif validator_cls == "URLValidator":
            if not any(r.type == "url" for r in rules):
                rules.append(ValidationRule(type="url", message="Enter a valid URL."))

    return rules


def _choices_to_options(choices: list[tuple[Any, str]]) -> list[SelectOption]:
    """Convert Django choices to SelectOption list."""
    options: list[SelectOption] = []
    for value, label in choices:
        if isinstance(label, (list, tuple)):
            # Optgroup: (group_label, [(value, label), ...])
            for sub_value, sub_label in label:
                options.append(
                    SelectOption(
                        value=str(sub_value),
                        label=str(sub_label),
                        group=str(value),
                    )
                )
        else:
            options.append(SelectOption(value=str(value), label=str(label)))
    return options


def _map_field(name: str, field: django_forms.Field) -> BaseField:
    """Map a Django form field to a component field."""
    common: dict[str, Any] = {
        "name": name,
        "label": field.label or name.replace("_", " ").title(),
        "help_text": str(field.help_text) if field.help_text else None,
        "required": field.required,
        "validation": _extract_validators(field),
    }

    if field.initial is not None:
        common["default_value"] = field.initial

    # Type-specific mapping
    if isinstance(field, django_forms.EmailField):
        return EmailField(**common)

    if isinstance(field, django_forms.URLField):
        return TextField(input_type="url", **common)

    if isinstance(field, django_forms.SlugField):
        return TextField(
            pattern=r"^[-a-zA-Z0-9_]+$",
            **common,
        )

    if isinstance(field, django_forms.CharField):
        widget = field.widget
        if isinstance(widget, django_forms.PasswordInput):
            return PasswordField(
                min_length=getattr(field, "min_length", None),
                **common,
            )
        if isinstance(widget, django_forms.Textarea):
            return Textarea(
                min_length=getattr(field, "min_length", None),
                max_length=getattr(field, "max_length", None),
                rows=int(widget.attrs.get("rows", 3)),
                **common,
            )
        if isinstance(widget, django_forms.HiddenInput):
            return TextField(**common)
        return TextField(
            min_length=getattr(field, "min_length", None),
            max_length=getattr(field, "max_length", None),
            **common,
        )

    if isinstance(field, django_forms.IntegerField):
        return NumberField(
            min_value=getattr(field, "min_value", None),
            max_value=getattr(field, "max_value", None),
            step=1,
            **common,
        )

    if isinstance(field, (django_forms.FloatField, django_forms.DecimalField)):
        precision = None
        if isinstance(field, django_forms.DecimalField) and field.decimal_places is not None:
            precision = field.decimal_places
        return NumberField(
            min_value=getattr(field, "min_value", None),
            max_value=getattr(field, "max_value", None),
            precision=precision,
            **common,
        )

    if isinstance(field, django_forms.BooleanField):
        return Checkbox(**common)

    if isinstance(field, django_forms.MultipleChoiceField):
        return MultiSelect(
            options=_choices_to_options(list(field.choices)),
            **common,
        )

    if isinstance(field, django_forms.ChoiceField):
        return Select(
            options=_choices_to_options(list(field.choices)),
            **common,
        )

    if isinstance(field, django_forms.DateField):
        return DatePicker(**common)

    if isinstance(field, django_forms.DateTimeField):
        return DatePicker(show_time=True, **common)

    if isinstance(field, django_forms.TimeField):
        return DatePicker(show_time=True, format="HH:mm", **common)

    if isinstance(field, django_forms.FileField):
        accept: list[str] = []
        if isinstance(field, django_forms.ImageField):
            accept = ["image/*"]
        return FileUpload(
            accept=accept,
            multiple=False,
            **common,
        )

    # Fallback: treat as text
    return TextField(**common)


# =============================================================================
# Public API
# =============================================================================


def form_to_components(
    form_class_or_instance: type[django_forms.BaseForm] | django_forms.BaseForm,
    theme: str = "shadcn",
) -> ComponentTree:
    """
    Introspect a Django form and convert its fields to a component tree.

    Args:
        form_class_or_instance: A Django Form class or instance.
        theme: CSS theme to apply ("shadcn", "tailwind", "bootstrap").

    Returns:
        A Form component containing mapped fields.
    """
    if isinstance(form_class_or_instance, type):
        form = form_class_or_instance()
    else:
        form = form_class_or_instance

    fields: list[BaseField] = []
    for name, field in form.fields.items():
        component = _map_field(name, field)
        # Apply theme class
        classes = THEME_CLASSES.get(theme, THEME_CLASSES["shadcn"])
        input_class = classes.get("input", "")
        if isinstance(component, (Textarea,)):
            input_class = classes.get("textarea", input_class)
        elif isinstance(component, (Select, MultiSelect)):
            input_class = classes.get("select", input_class)
        elif isinstance(component, (Checkbox,)):
            input_class = classes.get("checkbox", input_class)
        component.class_name = input_class
        fields.append(component)

    return Form(
        action="",
        method="POST",
        fields=fields,
        submit=SubmitButton(label="Submit"),
    )


def render_form(
    form: type[django_forms.BaseForm] | django_forms.BaseForm,
    theme: str = "shadcn",
    method: str = "post",
    action: str = "",
) -> str:
    """
    Render a Django form to themed HTML using the component system.

    Args:
        form: A Django Form class or bound instance.
        theme: CSS framework theme ("shadcn", "tailwind", "bootstrap").
        method: HTTP method for the form.
        action: Form action URL.

    Returns:
        HTML string of the rendered form.
    """
    if isinstance(form, type):
        instance = form()
    else:
        instance = form

    classes = THEME_CLASSES.get(theme, THEME_CLASSES["shadcn"])
    parts: list[str] = []

    # Determine enctype
    has_file = any(isinstance(f, django_forms.FileField) for f in instance.fields.values())
    enctype = ' enctype="multipart/form-data"' if has_file else ""

    parts.append(
        f'<form method="{escape(method)}" action="{escape(action)}"{enctype}'
        f' class="{escape(classes["form"])}">'
    )
    parts.append('  <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">')

    # Non-field errors
    if hasattr(instance, "errors") and instance.errors.get("__all__"):
        parts.append(f'  <div class="{escape(classes["error_list"])}">')
        parts.append("    <ul>")
        for err in instance.errors["__all__"]:
            parts.append(f"      <li>{escape(str(err))}</li>")
        parts.append("    </ul>")
        parts.append("  </div>")

    # Fields
    for name, field in instance.fields.items():
        field_errors: list[str] = []
        if hasattr(instance, "errors") and name in instance.errors:
            field_errors = [str(e) for e in instance.errors[name]]

        parts.append(f'  <div class="{escape(classes["field_wrapper"])}">')

        label_text = field.label or name.replace("_", " ").title()
        required_mark = ' <span class="text-destructive">*</span>' if field.required else ""

        # Checkbox has label after input
        if isinstance(field, django_forms.BooleanField):
            parts.append('    <div class="flex items-center gap-2">')
            parts.append(
                f'      <input type="checkbox" id="id_{escape(name)}" name="{escape(name)}"'
                f' class="{escape(classes["checkbox"])}"'
                f"{' checked' if instance.initial.get(name) else ''}>"
            )
            parts.append(
                f'      <label for="id_{escape(name)}" class="{escape(classes["label"])}">'
                f"{escape(label_text)}{required_mark}</label>"
            )
            parts.append("    </div>")
        else:
            parts.append(
                f'    <label for="id_{escape(name)}" class="{escape(classes["label"])}">'
                f"{escape(label_text)}{required_mark}</label>"
            )
            parts.append(_render_field_html(name, field, instance, classes))

        # Help text
        if field.help_text:
            parts.append(
                f'    <p class="{escape(classes["help_text"])}">{escape(str(field.help_text))}</p>'
            )

        # Errors
        for err in field_errors:
            parts.append(f'    <p class="{escape(classes["error"])}">{escape(err)}</p>')

        parts.append("  </div>")

    # Submit button
    parts.append(f'  <button type="submit" class="{escape(classes["submit"])}">Submit</button>')
    parts.append("</form>")

    return "\n".join(parts)


def _render_field_html(
    name: str,
    field: django_forms.Field,
    form_instance: django_forms.BaseForm,
    classes: dict[str, str],
) -> str:
    """Render a single field's input HTML."""
    value = ""
    if hasattr(form_instance, "cleaned_data") and name in form_instance.cleaned_data:
        value = str(form_instance.cleaned_data[name] or "")
    elif form_instance.initial.get(name) is not None:
        value = str(form_instance.initial[name])

    attrs = f'id="id_{escape(name)}" name="{escape(name)}"'
    req = " required" if field.required else ""

    if isinstance(field, django_forms.EmailField):
        return (
            f'    <input type="email" {attrs} value="{escape(value)}"'
            f' class="{escape(classes["input"])}"{req}>'
        )

    if isinstance(field, django_forms.URLField):
        return (
            f'    <input type="url" {attrs} value="{escape(value)}"'
            f' class="{escape(classes["input"])}"{req}>'
        )

    if isinstance(field, django_forms.CharField):
        widget = field.widget
        if isinstance(widget, django_forms.PasswordInput):
            return f'    <input type="password" {attrs} class="{escape(classes["input"])}"{req}>'
        if isinstance(widget, django_forms.Textarea):
            rows = widget.attrs.get("rows", 3)
            return (
                f'    <textarea {attrs} rows="{rows}"'
                f' class="{escape(classes["textarea"])}"{req}>'
                f"{escape(value)}</textarea>"
            )
        if isinstance(widget, django_forms.HiddenInput):
            return f'    <input type="hidden" {attrs} value="{escape(value)}">'
        ml = ""
        if field.max_length:
            ml = f' maxlength="{field.max_length}"'
        return (
            f'    <input type="text" {attrs} value="{escape(value)}"'
            f' class="{escape(classes["input"])}"{ml}{req}>'
        )

    if isinstance(field, django_forms.IntegerField):
        min_v = f' min="{field.min_value}"' if getattr(field, "min_value", None) is not None else ""
        max_v = f' max="{field.max_value}"' if getattr(field, "max_value", None) is not None else ""
        return (
            f'    <input type="number" {attrs} value="{escape(value)}" step="1"'
            f' class="{escape(classes["input"])}"{min_v}{max_v}{req}>'
        )

    if isinstance(field, (django_forms.FloatField, django_forms.DecimalField)):
        step = "any"
        if isinstance(field, django_forms.DecimalField) and field.decimal_places is not None:
            step = str(10**-field.decimal_places)
        min_v = f' min="{field.min_value}"' if getattr(field, "min_value", None) is not None else ""
        max_v = f' max="{field.max_value}"' if getattr(field, "max_value", None) is not None else ""
        return (
            f'    <input type="number" {attrs} value="{escape(value)}" step="{step}"'
            f' class="{escape(classes["input"])}"{min_v}{max_v}{req}>'
        )

    if isinstance(field, (django_forms.ChoiceField, django_forms.MultipleChoiceField)):
        multiple = " multiple" if isinstance(field, django_forms.MultipleChoiceField) else ""
        lines = [f'    <select {attrs} class="{escape(classes["select"])}"{multiple}{req}>']
        current_group: str | None = None
        for choice_value, choice_label in field.choices:
            if isinstance(choice_label, (list, tuple)):
                if current_group is not None:
                    lines.append("      </optgroup>")
                current_group = str(choice_value)
                lines.append(f'      <optgroup label="{escape(current_group)}">')
                for sub_val, sub_label in choice_label:
                    sel = " selected" if str(sub_val) == value else ""
                    lines.append(
                        f'        <option value="{escape(str(sub_val))}"{sel}>'
                        f"{escape(str(sub_label))}</option>"
                    )
            else:
                sel = " selected" if str(choice_value) == value else ""
                lines.append(
                    f'      <option value="{escape(str(choice_value))}"{sel}>'
                    f"{escape(str(choice_label))}</option>"
                )
        if current_group is not None:
            lines.append("      </optgroup>")
        lines.append("    </select>")
        return "\n".join(lines)

    if isinstance(field, django_forms.DateField):
        return (
            f'    <input type="date" {attrs} value="{escape(value)}"'
            f' class="{escape(classes["input"])}"{req}>'
        )

    if isinstance(field, django_forms.DateTimeField):
        return (
            f'    <input type="datetime-local" {attrs} value="{escape(value)}"'
            f' class="{escape(classes["input"])}"{req}>'
        )

    if isinstance(field, django_forms.TimeField):
        return (
            f'    <input type="time" {attrs} value="{escape(value)}"'
            f' class="{escape(classes["input"])}"{req}>'
        )

    if isinstance(field, django_forms.FileField):
        accept = ""
        if isinstance(field, django_forms.ImageField):
            accept = ' accept="image/*"'
        return f'    <input type="file" {attrs} class="{escape(classes["input"])}"{accept}{req}>'

    # Fallback
    return (
        f'    <input type="text" {attrs} value="{escape(value)}"'
        f' class="{escape(classes["input"])}"{req}>'
    )
