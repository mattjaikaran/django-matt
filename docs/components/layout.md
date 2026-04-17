# Layout Components

Structural UI components for containers, cards, modals, drawers, tabs, accordions, alerts, navigation, and display elements. All defined in Python, rendered by any frontend framework.

## Quick Start

```python
from django_matt.components.layout import Card, Container, Text, Button

page = Card(
    title="Welcome",
    description="Get started with your dashboard",
    children=[
        Text(content="Hello, World!", variant="lead"),
        Button(label="Get Started"),
    ],
    variant="elevated",
)

json_data = page.to_json()
```

## Components

### Container

Generic flexbox container.

```python
from django_matt.components.layout import Container

layout = Container(
    tag="section",
    flex=True,
    flex_direction="row",      # row | column | row-reverse | column-reverse
    justify="between",         # start | end | center | between | around | evenly
    align="center",            # start | end | center | stretch | baseline
    gap="1rem",
    padding="2rem",
    children=[...],
)
```

### Card

Card with header, body, and footer sections.

```python
from django_matt.components.layout import Card

card = Card(
    title="User Profile",
    description="View and edit your profile",
    children=[...],
    footer=[Button(label="Save"), Button(label="Cancel", variant="outline")],
    image="/images/header.jpg",
    variant="elevated",  # default | outline | elevated | filled
    hoverable=True,
    clickable=False,
)
```

### Modal

Dialog overlay with configurable size and behavior.

```python
from django_matt.components.layout import Modal

modal = Modal(
    id="confirm-delete",
    title="Confirm Delete",
    description="Are you sure you want to delete this item?",
    children=[Text(content="This action cannot be undone.")],
    footer=[
        Button(label="Cancel", variant="outline"),
        Button(label="Delete", variant="destructive"),
    ],
    size="md",            # sm | md | lg | xl | full
    closable=True,
    close_on_overlay=True,
    close_on_escape=True,
    prevent_scroll=True,
)
```

### Drawer

Slide-out panel from any edge.

```python
from django_matt.components.layout import Drawer

drawer = Drawer(
    id="menu",
    title="Navigation",
    position="left",     # left | right | top | bottom
    size="md",
    children=[...],
    closable=True,
    close_on_overlay=True,
)
```

### Tabs

Tabbed interface with horizontal or vertical orientation.

```python
from django_matt.components.layout import Tabs, TabItem

tabs = Tabs(
    items=[
        TabItem(value="general", label="General", children=[...]),
        TabItem(value="security", label="Security", icon="lock", children=[...]),
        TabItem(value="billing", label="Billing", badge="3", children=[...]),
    ],
    default_value="general",
    orientation="horizontal",  # horizontal | vertical
    variant="default",         # default | outline | pills
)

# Fluent API
tabs.add_tab("notifications", "Notifications", content=[...])
```

### Accordion

Collapsible content sections.

```python
from django_matt.components.layout import Accordion, AccordionItem

faq = Accordion(
    items=[
        AccordionItem(value="q1", title="What is Django Matt?", children=[...]),
        AccordionItem(value="q2", title="How do I install it?", children=[...]),
    ],
    accordion_type="single",  # single | multiple
    collapsible=True,
    default_value="q1",
)
```

### Alert and Toast

```python
from django_matt.components.layout import Alert, Toast

alert = Alert(
    title="Error",
    message="Something went wrong",
    variant="destructive",  # default | success | warning | error | info | destructive
    icon="alert-circle",
    dismissible=True,
)

toast = Toast(
    title="Saved",
    message="Your changes have been saved",
    variant="success",
    duration=5000,
    position="bottom-right",
)
```

### Navigation

```python
from django_matt.components.layout import Nav, NavItem

sidebar = Nav(
    items=[
        NavItem(label="Dashboard", href="/", icon="home", active=True),
        NavItem(label="Users", href="/users", icon="users", badge="12"),
        NavItem(label="Settings", href="/settings", icon="settings", children=[
            NavItem(label="General", href="/settings/general"),
            NavItem(label="Security", href="/settings/security"),
        ]),
    ],
    orientation="vertical",   # horizontal | vertical
    variant="default",        # default | pills | underline
)
```

### Display Components

```python
from django_matt.components.layout import (
    Text, Heading, Image, Avatar, Badge, Spinner, Progress, Divider,
)

title = Text(content="Hello World", variant="h1")
# variant: h1-h6 | p | span | small | lead | muted

heading = Heading(content="Page Title", level=1, subtitle="A brief description")

avatar = Avatar(src="/img/user.jpg", alt="Jane", fallback="JD", size="lg",
                status="online")  # online | offline | away | busy

badge = Badge(content="Active", variant="success", size="md")
# variant: default | secondary | success | warning | error | outline

progress = Progress(value=65, max_value=100, show_label=True, variant="success")

spinner = Spinner(size="md", label="Loading...")

image = Image(src="/img/hero.jpg", alt="Hero", aspect_ratio="16/9",
              object_fit="cover", loading="lazy")

divider = Divider(orientation="horizontal", label="OR")
```

## Practical Example

A settings page with tabs, forms, and alerts:

```python
from django_matt.components.layout import Card, Tabs, TabItem, Alert, Container
from django_matt.components.layout import Text, Heading, Divider

settings_page = Container(
    flex=True,
    flex_direction="column",
    gap="1.5rem",
    children=[
        Heading(content="Settings", level=1, subtitle="Manage your account"),
        Alert(
            title="Email not verified",
            message="Please verify your email address.",
            variant="warning",
            dismissible=True,
        ),
        Card(
            children=[
                Tabs(
                    items=[
                        TabItem(value="profile", label="Profile", children=[
                            Text(content="Update your profile information"),
                        ]),
                        TabItem(value="security", label="Security", children=[
                            Text(content="Change your password and 2FA settings"),
                        ]),
                        TabItem(value="notifications", label="Notifications", children=[
                            Text(content="Configure notification preferences"),
                        ]),
                    ],
                    default_value="profile",
                ),
            ],
        ),
    ],
)
```
