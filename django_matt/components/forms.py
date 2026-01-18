"""
Form components for collecting user input.

Provides form fields, buttons, and complete form components
with built-in validation support.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from django_matt.components.base import (
    Component,
    ComponentType,
    ValidationRule,
    registry,
)

# =============================================================================
# Base Field Component
# =============================================================================


class BaseField(Component):
    """Base class for form fields."""

    name: str
    label: str | None = None
    placeholder: str | None = None
    help_text: str | None = None
    required: bool = False
    readonly: bool = False
    autocomplete: str | None = None
    validation: list[ValidationRule] = Field(default_factory=list)
    error: str | None = None
    default_value: Any | None = None

    def with_validation(self, rule: ValidationRule) -> "BaseField":
        """Add a validation rule."""
        self.validation.append(rule)
        return self

    def required_field(self, message: str = "This field is required") -> "BaseField":
        """Make field required."""
        self.required = True
        self.validation.append(ValidationRule(type="required", message=message))
        return self


# =============================================================================
# Text Input Fields
# =============================================================================


@registry.register("text_field", aliases=["text", "input"])
class TextField(BaseField):
    """
    Text input field.

    Usage:
        name_field = TextField(
            name="username",
            label="Username",
            placeholder="Enter your username",
            required=True,
            min_length=3,
            max_length=20,
        )
    """

    type: ComponentType = ComponentType.TEXT_FIELD
    input_type: Literal["text", "search", "tel", "url"] = "text"
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    prefix: str | None = None
    suffix: str | None = None


@registry.register("email_field", aliases=["email"])
class EmailField(BaseField):
    """
    Email input field with built-in email validation.

    Usage:
        email = EmailField(name="email", label="Email Address", required=True)
    """

    type: ComponentType = ComponentType.EMAIL_FIELD
    autocomplete: str = "email"

    def model_post_init(self, __context) -> None:
        # Add email validation rule
        if not any(r.type == "email" for r in self.validation):
            self.validation.append(
                ValidationRule(type="email", message="Please enter a valid email address")
            )


@registry.register("password_field", aliases=["password"])
class PasswordField(BaseField):
    """
    Password input field.

    Usage:
        password = PasswordField(
            name="password",
            label="Password",
            required=True,
            show_toggle=True,
            min_length=8,
        )
    """

    type: ComponentType = ComponentType.PASSWORD_FIELD
    autocomplete: str = "current-password"
    show_toggle: bool = True  # Show/hide password toggle
    min_length: int | None = None
    strength_meter: bool = False  # Show password strength indicator


@registry.register("number_field", aliases=["number"])
class NumberField(BaseField):
    """
    Numeric input field.

    Usage:
        age = NumberField(
            name="age",
            label="Age",
            min_value=0,
            max_value=120,
            step=1,
        )
    """

    type: ComponentType = ComponentType.NUMBER_FIELD
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    precision: int | None = None  # Decimal places


@registry.register("textarea", aliases=["text_area"])
class Textarea(BaseField):
    """
    Multi-line text input.

    Usage:
        bio = Textarea(
            name="bio",
            label="Biography",
            rows=4,
            max_length=500,
            show_count=True,
        )
    """

    type: ComponentType = ComponentType.TEXTAREA
    rows: int = 3
    min_length: int | None = None
    max_length: int | None = None
    show_count: bool = False  # Show character count
    resize: Literal["none", "vertical", "horizontal", "both"] = "vertical"


# =============================================================================
# Selection Fields
# =============================================================================


class SelectOption(BaseModel):
    """Option for select fields."""

    value: str
    label: str
    disabled: bool = False
    group: str | None = None


@registry.register("select", aliases=["dropdown"])
class Select(BaseField):
    """
    Dropdown select field.

    Usage:
        country = Select(
            name="country",
            label="Country",
            options=[
                SelectOption(value="us", label="United States"),
                SelectOption(value="uk", label="United Kingdom"),
                SelectOption(value="ca", label="Canada"),
            ],
            searchable=True,
        )
    """

    type: ComponentType = ComponentType.SELECT
    options: list[SelectOption] = Field(default_factory=list)
    searchable: bool = False
    clearable: bool = False
    empty_label: str = "Select an option..."

    def add_option(self, value: str, label: str, **kwargs) -> "Select":
        """Add an option."""
        self.options.append(SelectOption(value=value, label=label, **kwargs))
        return self


@registry.register("multi_select")
class MultiSelect(BaseField):
    """
    Multi-selection field.

    Usage:
        tags = MultiSelect(
            name="tags",
            label="Tags",
            options=[...],
            max_selections=5,
        )
    """

    type: ComponentType = ComponentType.MULTI_SELECT
    options: list[SelectOption] = Field(default_factory=list)
    searchable: bool = True
    max_selections: int | None = None
    min_selections: int | None = None


@registry.register("checkbox")
class Checkbox(BaseField):
    """
    Checkbox field.

    Usage:
        terms = Checkbox(
            name="terms",
            label="I agree to the terms and conditions",
            required=True,
        )
    """

    type: ComponentType = ComponentType.CHECKBOX
    checked: bool = False
    indeterminate: bool = False


@registry.register("radio")
class RadioGroup(BaseField):
    """
    Radio button group.

    Usage:
        gender = RadioGroup(
            name="gender",
            label="Gender",
            options=[
                SelectOption(value="male", label="Male"),
                SelectOption(value="female", label="Female"),
                SelectOption(value="other", label="Other"),
            ],
            direction="horizontal",
        )
    """

    type: ComponentType = ComponentType.RADIO
    options: list[SelectOption] = Field(default_factory=list)
    direction: Literal["horizontal", "vertical"] = "vertical"


@registry.register("switch", aliases=["toggle"])
class Switch(BaseField):
    """
    Toggle switch field.

    Usage:
        notifications = Switch(
            name="notifications",
            label="Enable notifications",
            checked=True,
        )
    """

    type: ComponentType = ComponentType.SWITCH
    checked: bool = False
    on_label: str | None = None
    off_label: str | None = None


# =============================================================================
# Date/Time Fields
# =============================================================================


@registry.register("date_picker", aliases=["date"])
class DatePicker(BaseField):
    """
    Date picker field.

    Usage:
        dob = DatePicker(
            name="dob",
            label="Date of Birth",
            max_date="today",
        )
    """

    type: ComponentType = ComponentType.DATE_PICKER
    format: str = "YYYY-MM-DD"
    min_date: str | None = None
    max_date: str | None = None
    disabled_dates: list[str] = Field(default_factory=list)
    show_time: bool = False
    time_format: str = "HH:mm"


# =============================================================================
# File Upload
# =============================================================================


@registry.register("file_upload", aliases=["file"])
class FileUpload(BaseField):
    """
    File upload field.

    Usage:
        avatar = FileUpload(
            name="avatar",
            label="Profile Picture",
            accept=["image/*"],
            max_size_mb=5,
        )
    """

    type: ComponentType = ComponentType.FILE_UPLOAD
    accept: list[str] = Field(default_factory=list)  # MIME types or extensions
    multiple: bool = False
    max_size_mb: float | None = None
    max_files: int | None = None
    drag_drop: bool = True
    preview: bool = True


# =============================================================================
# Buttons
# =============================================================================


@registry.register("button")
class Button(Component):
    """
    Button component.

    Usage:
        submit = Button(
            label="Submit",
            variant="primary",
            type="submit",
        )

        cancel = Button(
            label="Cancel",
            variant="outline",
        ).on_click("/cancel")
    """

    type: ComponentType = ComponentType.BUTTON
    label: str
    button_type: Literal["button", "submit", "reset"] = "button"
    variant: Literal["primary", "secondary", "outline", "ghost", "destructive", "link"] = "primary"
    size: Literal["sm", "md", "lg", "icon"] = "md"
    icon: str | None = None
    icon_position: Literal["left", "right"] = "left"
    full_width: bool = False


@registry.register("submit_button")
class SubmitButton(Button):
    """Submit button with default settings."""

    button_type: Literal["button", "submit", "reset"] = "submit"
    variant: Literal["primary", "secondary", "outline", "ghost", "destructive", "link"] = "primary"


# =============================================================================
# Form Container
# =============================================================================


@registry.register("form")
class Form(Component):
    """
    Form container component.

    Usage:
        login_form = Form(
            id="login-form",
            action="/api/auth/login",
            method="POST",
            fields=[
                EmailField(name="email", label="Email", required=True),
                PasswordField(name="password", label="Password", required=True),
            ],
            submit=SubmitButton(label="Sign In"),
        )
    """

    type: ComponentType = ComponentType.FORM
    action: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    fields: list[BaseField] = Field(default_factory=list)
    submit: Button | None = None
    reset: Button | None = None
    enctype: Literal[
        "application/x-www-form-urlencoded", "multipart/form-data", "application/json"
    ] = "application/json"
    redirect_on_success: str | None = None
    show_validation_summary: bool = True
    inline: bool = False  # Inline form layout
    columns: int = 1  # Grid columns

    def add_field(self, field: BaseField) -> "Form":
        """Add a field to the form."""
        self.fields.append(field)
        return self


# =============================================================================
# Pre-built Auth Forms
# =============================================================================


@registry.register("login_form")
class LoginForm(Component):
    """
    Complete login form component.

    Usage:
        login = LoginForm(
            action="/api/auth/login",
            show_remember_me=True,
            show_forgot_password=True,
            oauth_providers=["google", "github"],
        )
    """

    type: ComponentType = ComponentType.LOGIN_FORM
    action: str = "/api/auth/login"
    email_label: str = "Email"
    password_label: str = "Password"
    submit_label: str = "Sign In"
    show_remember_me: bool = True
    show_forgot_password: bool = True
    forgot_password_url: str = "/forgot-password"
    show_register_link: bool = True
    register_url: str = "/register"
    oauth_providers: list[str] = Field(default_factory=list)
    show_magic_link: bool = False
    show_passkeys: bool = False
    redirect_url: str | None = None


@registry.register("register_form")
class RegisterForm(Component):
    """
    Complete registration form component.

    Usage:
        register = RegisterForm(
            action="/api/auth/register",
            require_password_confirm=True,
            show_terms_checkbox=True,
        )
    """

    type: ComponentType = ComponentType.REGISTER_FORM
    action: str = "/api/auth/register"
    email_label: str = "Email"
    password_label: str = "Password"
    confirm_password_label: str = "Confirm Password"
    submit_label: str = "Create Account"
    require_password_confirm: bool = True
    password_min_length: int = 8
    show_password_strength: bool = True
    show_terms_checkbox: bool = True
    terms_url: str = "/terms"
    privacy_url: str = "/privacy"
    show_login_link: bool = True
    login_url: str = "/login"
    oauth_providers: list[str] = Field(default_factory=list)
    redirect_url: str | None = None


@registry.register("oauth_buttons")
class OAuthButtons(Component):
    """
    OAuth provider buttons.

    Usage:
        oauth = OAuthButtons(
            providers=["google", "github", "apple"],
            mode="login",
        )
    """

    type: ComponentType = ComponentType.OAUTH_BUTTONS
    providers: list[str] = Field(default_factory=list)
    mode: Literal["login", "register", "connect"] = "login"
    redirect_url: str | None = None
    button_variant: Literal["primary", "outline", "ghost"] = "outline"
    show_labels: bool = True
    layout: Literal["horizontal", "vertical", "grid"] = "vertical"


__all__ = [
    # Base
    "BaseField",
    "ValidationRule",
    "SelectOption",
    # Text inputs
    "TextField",
    "EmailField",
    "PasswordField",
    "NumberField",
    "Textarea",
    # Selection
    "Select",
    "MultiSelect",
    "Checkbox",
    "RadioGroup",
    "Switch",
    # Date/Time
    "DatePicker",
    # File
    "FileUpload",
    # Buttons
    "Button",
    "SubmitButton",
    # Form
    "Form",
    # Auth forms
    "LoginForm",
    "RegisterForm",
    "OAuthButtons",
]
