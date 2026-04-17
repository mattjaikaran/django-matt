# Forms Bridge

Bridge Django forms to the component system. Introspects Django form fields and maps them to typed UI components with preserved validators, help text, error messages, and CSS framework theming (shadcn, Tailwind, Bootstrap).

## Quick Start

```python
from django import forms
from django_matt.forms.bridge import form_to_components

class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, help_text="Your full name")
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}))

# Convert to component tree
component = form_to_components(ContactForm(), theme="shadcn")
json_data = component.to_json()
```

## Configuration

The bridge supports three CSS framework themes out of the box:

| Theme | Description |
|-------|-------------|
| `shadcn` | shadcn/ui classes (default) |
| `tailwind` | Plain Tailwind CSS classes |
| `bootstrap` | Bootstrap 5 classes |

Each theme provides classes for: form, field_wrapper, label, input, textarea, select, checkbox, help_text, error, submit, error_list.

## Key Features

### form_to_components

Converts a Django form instance to a `Form` component with typed fields:

```python
from django_matt.forms.bridge import form_to_components

# With shadcn theme (default)
component = form_to_components(form, theme="shadcn")

# With Tailwind classes
component = form_to_components(form, theme="tailwind")

# With Bootstrap classes
component = form_to_components(form, theme="bootstrap")
```

### Field Type Mapping

Django form fields are mapped to component types:

| Django Field | Component |
|-------------|-----------|
| `CharField` | `TextField` |
| `EmailField` | `EmailField` |
| `CharField(widget=PasswordInput)` | `PasswordField` |
| `IntegerField`, `FloatField`, `DecimalField` | `NumberField` |
| `CharField(widget=Textarea)` | `Textarea` |
| `ChoiceField` | `Select` |
| `MultipleChoiceField` | `MultiSelect` |
| `BooleanField` | `Checkbox` |
| `DateField` | `DatePicker` |
| `FileField`, `ImageField` | `FileUpload` |

### Validation Rules

Django validators are converted to component validation rules:

```python
from django import forms

class SignupForm(forms.Form):
    username = forms.CharField(min_length=3, max_length=20)
    email = forms.EmailField(required=True)
    age = forms.IntegerField(min_value=18, max_value=120)

# Converts to ValidationRule objects:
# username: [required, minLength(3), maxLength(20)]
# email: [required, email]
# age: [required, min(18), max(120)]
```

### Theme Classes

Access theme CSS classes directly:

```python
from django_matt.forms.bridge import THEME_CLASSES

shadcn = THEME_CLASSES["shadcn"]
print(shadcn["input"])
# "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 ..."

print(shadcn["submit"])
# "inline-flex items-center justify-center ... bg-primary text-primary-foreground ..."
```

### Form Validation Decorator

```python
from django_matt.forms.decorators import validate_form

@validate_form(ContactForm)
async def submit_contact(request, form: ContactForm):
    # form is already validated
    send_email(form.cleaned_data["email"], form.cleaned_data["message"])
    return {"status": "sent"}
```

### Form Builder

Build forms programmatically:

```python
from django_matt.forms.builder import FormBuilder

form = (
    FormBuilder()
    .text_field("name", label="Full Name", required=True)
    .email_field("email", label="Email Address")
    .select("role", label="Role", options=[
        ("admin", "Admin"),
        ("user", "User"),
    ])
    .textarea("bio", label="Biography", rows=4)
    .submit("Save Profile")
    .build()
)
```

## Practical Example

A complete form flow from Django form to frontend component:

```python
from django import forms
from django_matt.forms.bridge import form_to_components
from django_matt.components.renderers import ReactRenderer

class UserProfileForm(forms.Form):
    first_name = forms.CharField(max_length=50, help_text="Your first name")
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField()
    bio = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        help_text="Tell us about yourself",
    )
    role = forms.ChoiceField(choices=[
        ("developer", "Developer"),
        ("designer", "Designer"),
        ("manager", "Manager"),
    ])
    notifications = forms.BooleanField(
        required=False,
        label="Enable email notifications",
    )

# Convert to components with shadcn styling
form = UserProfileForm(initial={"role": "developer", "notifications": True})
component = form_to_components(form, theme="shadcn")

# Render as React JSON
renderer = ReactRenderer()
output = renderer.render(component)
# Send output.content to your React frontend

# Or render as Vue SFC
from django_matt.components.renderers import VueRenderer
vue_renderer = VueRenderer(typescript=True)
sfc = vue_renderer.render_to_string(component, component_name="UserProfileForm")
```

Handle form submission with errors:

```python
async def update_profile(request):
    form = UserProfileForm(request.POST)
    if form.is_valid():
        # Process form...
        return JsonResponse({"status": "ok"})

    # Convert form with errors to component (errors are preserved)
    component = form_to_components(form, theme="shadcn")
    renderer = ReactRenderer()
    output = renderer.render(component)
    return JsonResponse({"form": output.content, "errors": form.errors}, status=422)
```
