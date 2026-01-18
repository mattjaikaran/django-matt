# Backend Components Overview

django-matt includes a backend-served UI component system that generates components for multiple frontend frameworks.

## Concept

```mermaid
flowchart LR
    subgraph "Backend"
        DEF[Component Definition<br/>Pydantic Models]
        REG[Component Registry]
        THEME[Theme System]
    end

    subgraph "Renderers"
        JSON[JSON Renderer]
        HTML[HTML Renderer]
        REACT[React Renderer]
    end

    subgraph "Output"
        API[JSON API Response]
        SSR[Server-Side HTML]
        PROPS[React Props]
    end

    DEF --> REG
    REG --> JSON
    REG --> HTML
    REG --> REACT
    THEME --> HTML
    THEME --> REACT

    JSON --> API
    HTML --> SSR
    REACT --> PROPS
```

## Component Categories

```mermaid
mindmap
  root((Components))
    Forms
      TextField
      EmailField
      PasswordField
      Select
      Checkbox
      DatePicker
      FileUpload
    Layout
      Card
      Modal
      Drawer
      Tabs
      Accordion
    Data
      DataTable
      Pagination
      SearchInput
    Feedback
      Alert
      Toast
      Badge
    Auth
      LoginForm
      RegisterForm
      OAuthButtons
```

## Architecture

```mermaid
classDiagram
    class Component {
        +id: str
        +class_name: str
        +style: dict
        +to_dict()
        +render()
    }

    class Form {
        +fields: list[Field]
        +action: str
        +method: str
        +submit: SubmitButton
    }

    class DataTable {
        +columns: list[Column]
        +data: list
        +sortable: bool
        +pagination: Pagination
    }

    class Theme {
        +name: str
        +colors: SemanticColors
        +typography: Typography
        +to_css_variables()
    }

    class Renderer {
        +render(component)
    }

    Component <|-- Form
    Component <|-- DataTable
    Renderer <|-- JSONRenderer
    Renderer <|-- HTMLRenderer
    Renderer <|-- ReactRenderer
    Theme --> Renderer
```

## Quick Start

### Define a Component

```python
from django_matt.components import (
    Form, TextField, EmailField, PasswordField, SubmitButton
)

login_form = Form(
    id="login-form",
    fields=[
        EmailField(name="email", label="Email", required=True),
        PasswordField(name="password", label="Password", required=True),
    ],
    submit=SubmitButton(label="Sign In"),
    action="/api/auth/login",
)
```

### Serve as JSON

```python
from django_matt.components import JsonComponentResponse

@api.get("/components/login")
def get_login_form(request):
    return JsonComponentResponse(login_form)
```

### Serve as HTML

```python
from django_matt.components import HtmlComponentResponse

@api.get("/login")
def login_page(request):
    return HtmlComponentResponse(login_form)
```

### With Theme

```python
from django_matt.components.themes import Theme, ShadcnPreset

theme = Theme.from_preset(ShadcnPreset.BLUE, mode="dark")

return HtmlComponentResponse(login_form, theme=theme)
```

## Related Documentation

- [Form Components](./forms.md)
- [Layout Components](./layout.md)
- [Data Components](./data.md)
- [Theming](./theming.md)
- [Renderers](./renderers.md)
