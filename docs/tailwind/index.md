# Tailwind CSS Integration

Centralized Tailwind CSS configuration with theme presets, color helpers, and component class generation for Django Matt's component system.

## Quick Start

```python
from django_matt.tailwind.config import get_tailwind_config

config = get_tailwind_config()

# Generate color classes
bg_class = config.bg("primary", 500)    # "bg-blue-500"
text_class = config.text("accent", 600)  # "text-indigo-600"
border_class = config.border("secondary") # "border-gray-500"
```

## Configuration

```python
# settings.py
DJANGO_MATT_TAILWIND = {
    "THEME": "default",           # Preset: default, emerald, purple, rose, amber, cyan
    "COLOR_PRIMARY": "blue",      # Override primary color
    "COLOR_SECONDARY": "gray",    # Override secondary color
    "COLOR_ACCENT": "indigo",     # Override accent color
    "BORDER_RADIUS": "rounded-lg",
    "COMPONENT_PREFIX": "",       # Prefix for component classes
    "DARK_MODE": "class",         # "class" or "media"
}
```

### Theme Presets

| Preset | Primary | Secondary | Accent |
|--------|---------|-----------|--------|
| `default` | blue | gray | indigo |
| `emerald` | emerald | slate | teal |
| `purple` | purple | gray | violet |
| `rose` | rose | gray | pink |
| `amber` | amber | stone | orange |
| `cyan` | cyan | slate | sky |

Theme presets provide defaults that you can override with explicit color settings.

## Key Features

### TailwindConfig

```python
from django_matt.tailwind.config import get_tailwind_config, reset_tailwind_config

config = get_tailwind_config()

# Color helpers (any shade from 50-950)
config.bg("primary", 500)       # "bg-blue-500"
config.bg("primary", 100)       # "bg-blue-100"
config.text("primary", 700)     # "text-blue-700"
config.border("secondary", 300) # "border-gray-300"
config.ring("accent", 500)      # "ring-indigo-500"

# Raw color class
config.get_color_class("primary", 600)  # "blue-600"

# Access config values
config.theme              # "default"
config.color_primary      # "blue"
config.border_radius      # "rounded-lg"
config.dark_mode          # "class"

# Reset cached config (useful in tests)
reset_tailwind_config()
```

### Component Classes

The `components` module provides pre-built Tailwind class sets for common UI patterns:

```python
from django_matt.tailwind.components import get_component_classes

classes = get_component_classes("button", variant="primary", size="md")
```

### Utility Functions

```python
from django_matt.tailwind.utils import cn, merge_classes

# Merge and deduplicate Tailwind classes
classes = cn("px-4 py-2", "bg-blue-500", conditional and "text-white")

# Merge with override (later classes win for conflicting utilities)
merged = merge_classes("px-4 py-2 bg-blue-500", "px-6 bg-red-500")
# Result: "py-2 px-6 bg-red-500"
```

### Available Colors

All standard Tailwind colors are available:

```
slate, gray, zinc, neutral, stone, red, orange, amber, yellow,
lime, green, emerald, teal, cyan, sky, blue, indigo, violet,
purple, fuchsia, pink, rose
```

Each with shades: 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950.

## Practical Example

Using Tailwind config with the component system:

```python
from django_matt.tailwind.config import get_tailwind_config
from django_matt.components.layout import Card, Container, Text

config = get_tailwind_config()

dashboard = Card(
    title="Revenue",
    class_name=f"border-l-4 {config.border('primary', 500)}",
    children=[
        Text(
            content="$12,345",
            variant="h2",
            class_name=config.text("primary", 700),
        ),
        Text(
            content="+12.5% from last month",
            variant="small",
            class_name="text-green-600",
        ),
    ],
)
```

Switching themes at runtime:

```python
# settings.py
DJANGO_MATT_TAILWIND = {"THEME": "emerald"}  # All components use emerald palette

# Or override per-request
from django_matt.tailwind.config import TailwindConfig

user_config = TailwindConfig(
    color_primary="rose",
    color_secondary="slate",
    color_accent="pink",
)
bg = user_config.bg("primary", 500)  # "bg-rose-500"
```
