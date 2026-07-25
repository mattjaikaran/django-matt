# file-length-max: 700
"""
Component Playground for live preview and testing.

Provides an interactive environment for exploring and testing
components with live props editing and theme switching.
"""

from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template import Context, Template
from django.views import View

import orjson

from django_matt.components.base import Component, registry
from django_matt.components.renderers import HTMLRenderer, JSONRenderer, ReactRenderer
from django_matt.components.theming import theme_manager

# =============================================================================
# Playground View
# =============================================================================


class PlaygroundView(View):
    """
    Component playground for interactive testing.

    Provides:
    - Live component preview
    - Props editor
    - Theme switcher
    - Code export (React, Vue, HTML)

    Usage:
        # urls.py
        from django_matt.components.playground import PlaygroundView

        urlpatterns = [
            path('playground/', PlaygroundView.as_view(), name='component-playground'),
        ]
    """

    template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Component Playground - Django Matt</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        {{ theme_css }}

        .playground-container {
            display: grid;
            grid-template-columns: 300px 1fr 350px;
            height: 100vh;
        }

        .sidebar {
            background: var(--card);
            border-right: 1px solid var(--border);
            overflow-y: auto;
        }

        .preview-area {
            background: var(--background);
            padding: 2rem;
            overflow-y: auto;
        }

        .props-panel {
            background: var(--card);
            border-left: 1px solid var(--border);
            overflow-y: auto;
        }

        .component-item {
            padding: 0.75rem 1rem;
            cursor: pointer;
            border-bottom: 1px solid var(--border);
            transition: background 0.15s;
        }

        .component-item:hover {
            background: var(--accent);
        }

        .component-item.active {
            background: var(--primary);
            color: var(--primary-foreground);
        }

        .prop-input {
            width: 100%;
            padding: 0.5rem;
            border: 1px solid var(--border);
            border-radius: 0.375rem;
            background: var(--background);
            margin-top: 0.25rem;
        }

        .preview-frame {
            border: 1px solid var(--border);
            border-radius: 0.5rem;
            background: white;
            padding: 2rem;
            min-height: 200px;
        }

        pre.code-block {
            background: var(--muted);
            padding: 1rem;
            border-radius: 0.5rem;
            overflow-x: auto;
            font-size: 0.875rem;
        }

        .dark pre.code-block {
            background: #1e1e1e;
        }
    </style>
</head>
<body class="{{ 'dark' if dark_mode else '' }}">
    <div class="playground-container">
        <!-- Component List Sidebar -->
        <div class="sidebar">
            <div class="p-4 border-b border-gray-200 dark:border-gray-700">
                <h1 class="text-lg font-semibold">Components</h1>
                <input
                    type="search"
                    placeholder="Search components..."
                    class="prop-input mt-2"
                    oninput="filterComponents(this.value)"
                >
            </div>
            <div id="component-list">
                {% for name, info in components.items %}
                <div
                    class="component-item {% if name == selected %}active{% endif %}"
                    onclick="selectComponent('{{ name }}')"
                    data-name="{{ name }}"
                >
                    <div class="font-medium">{{ name }}</div>
                    <div class="text-xs text-gray-500">{{ info.type }}</div>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- Preview Area -->
        <div class="preview-area">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-semibold">{{ selected|default:"Select a component" }}</h2>
                <div class="flex gap-2">
                    <button
                        onclick="toggleTheme()"
                        class="px-3 py-1 border rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                        {{ '🌙' if dark_mode else '☀️' }} Theme
                    </button>
                    <select
                        onchange="changeThemePreset(this.value)"
                        class="px-3 py-1 border rounded-md"
                    >
                        {% for preset in theme_presets %}
                        <option value="{{ preset }}" {% if preset == current_preset %}selected{% endif %}>
                            {{ preset|title }}
                        </option>
                        {% endfor %}
                    </select>
                </div>
            </div>

            {% if selected %}
            <div class="preview-frame" id="preview">
                {{ preview_html|safe }}
            </div>

            <div class="mt-6">
                <div class="flex border-b border-gray-200 dark:border-gray-700">
                    <button
                        class="px-4 py-2 border-b-2 border-primary font-medium"
                        onclick="showTab('json')"
                        id="tab-json"
                    >JSON</button>
                    <button
                        class="px-4 py-2 border-b-2 border-transparent"
                        onclick="showTab('html')"
                        id="tab-html"
                    >HTML</button>
                    <button
                        class="px-4 py-2 border-b-2 border-transparent"
                        onclick="showTab('react')"
                        id="tab-react"
                    >React</button>
                </div>
                <div id="code-json" class="mt-4">
                    <pre class="code-block">{{ json_output }}</pre>
                </div>
                <div id="code-html" class="mt-4 hidden">
                    <pre class="code-block">{{ html_output|escape }}</pre>
                </div>
                <div id="code-react" class="mt-4 hidden">
                    <pre class="code-block">{{ react_output }}</pre>
                </div>
            </div>
            {% else %}
            <div class="text-center text-gray-500 py-12">
                Select a component from the sidebar to preview
            </div>
            {% endif %}
        </div>

        <!-- Props Panel -->
        <div class="props-panel">
            <div class="p-4 border-b border-gray-200 dark:border-gray-700">
                <h2 class="text-lg font-semibold">Props</h2>
            </div>
            {% if selected and props_schema %}
            <form id="props-form" class="p-4 space-y-4" onsubmit="updatePreview(event)">
                {% for prop_name, prop_info in props_schema.items %}
                <div>
                    <label class="block text-sm font-medium">
                        {{ prop_name }}
                        {% if prop_info.required %}<span class="text-red-500">*</span>{% endif %}
                    </label>
                    <div class="text-xs text-gray-500 mb-1">{{ prop_info.type }}</div>
                    {% if prop_info.type == 'boolean' %}
                    <input
                        type="checkbox"
                        name="{{ prop_name }}"
                        {% if prop_info.value %}checked{% endif %}
                        class="h-4 w-4"
                    >
                    {% elif prop_info.type == 'number' %}
                    <input
                        type="number"
                        name="{{ prop_name }}"
                        value="{{ prop_info.value|default:'' }}"
                        class="prop-input"
                    >
                    {% elif prop_info.choices %}
                    <select name="{{ prop_name }}" class="prop-input">
                        {% for choice in prop_info.choices %}
                        <option value="{{ choice }}" {% if choice == prop_info.value %}selected{% endif %}>
                            {{ choice }}
                        </option>
                        {% endfor %}
                    </select>
                    {% elif prop_info.type == 'list' or prop_info.type == 'dict' %}
                    <textarea
                        name="{{ prop_name }}"
                        class="prop-input h-24 font-mono text-sm"
                        placeholder="JSON value"
                    >{{ prop_info.json_value }}</textarea>
                    {% else %}
                    <input
                        type="text"
                        name="{{ prop_name }}"
                        value="{{ prop_info.value|default:'' }}"
                        class="prop-input"
                    >
                    {% endif %}
                </div>
                {% endfor %}
                <button
                    type="submit"
                    class="w-full py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90"
                >
                    Update Preview
                </button>
            </form>
            {% else %}
            <div class="p-4 text-gray-500 text-center">
                Select a component to edit props
            </div>
            {% endif %}
        </div>
    </div>

    <script>
        function selectComponent(name) {
            const params = new URLSearchParams(window.location.search);
            params.set('component', name);
            window.location.search = params.toString();
        }

        function filterComponents(query) {
            const items = document.querySelectorAll('#component-list .component-item');
            const lowerQuery = query.toLowerCase();
            items.forEach(item => {
                const name = item.dataset.name.toLowerCase();
                item.style.display = name.includes(lowerQuery) ? '' : 'none';
            });
        }

        function toggleTheme() {
            const params = new URLSearchParams(window.location.search);
            const isDark = params.get('dark') === 'true';
            params.set('dark', (!isDark).toString());
            window.location.search = params.toString();
        }

        function changeThemePreset(preset) {
            const params = new URLSearchParams(window.location.search);
            params.set('theme', preset);
            window.location.search = params.toString();
        }

        function showTab(tab) {
            ['json', 'html', 'react'].forEach(t => {
                document.getElementById('code-' + t).classList.toggle('hidden', t !== tab);
                document.getElementById('tab-' + t).classList.toggle('border-primary', t === tab);
                document.getElementById('tab-' + t).classList.toggle('border-transparent', t !== tab);
            });
        }

        function updatePreview(event) {
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);
            const params = new URLSearchParams(window.location.search);

            // Build props from form
            const props = {};
            for (const [key, value] of formData.entries()) {
                if (form.elements[key].type === 'checkbox') {
                    props[key] = form.elements[key].checked;
                } else if (form.elements[key].type === 'number') {
                    props[key] = parseFloat(value) || 0;
                } else {
                    try {
                        props[key] = JSON.parse(value);
                    } catch {
                        props[key] = value;
                    }
                }
            }

            params.set('props', JSON.stringify(props));
            window.location.search = params.toString();
        }
    </script>
</body>
</html>
"""

    def get(self, request: HttpRequest) -> HttpResponse:
        # Get query params
        selected = request.GET.get("component")
        dark_mode = request.GET.get("dark") == "true"
        theme_preset = request.GET.get("theme", "default")
        props_json = request.GET.get("props", "{}")

        try:
            props = orjson.loads(props_json)
        except orjson.JSONDecodeError:
            props = {}

        # Set theme
        try:
            theme_manager.use_preset(theme_preset)
        except ValueError:
            theme_preset = "default"

        # Get all registered components
        components = self._get_components_info()

        # Prepare context
        context = {
            "components": components,
            "selected": selected,
            "dark_mode": dark_mode,
            "current_preset": theme_preset,
            "theme_presets": theme_manager.list_presets(),
            "theme_css": theme_manager.get_full_css(),
        }

        # If component selected, render preview
        if selected:
            component_class = registry.get(selected)
            if component_class:
                context.update(self._render_component(component_class, props))

        # Render template
        template = Template(self.template)
        html = template.render(Context(context))

        return HttpResponse(html)

    def _get_components_info(self) -> dict[str, dict[str, Any]]:
        """Get info about all registered components."""
        components = {}

        for name in registry.list():
            cls = registry.get(name)
            if cls:
                components[name] = {
                    "type": cls.__name__,
                    "module": cls.__module__,
                }

        return dict(sorted(components.items()))

    def _render_component(
        self,
        component_class: type[Component],
        props: dict[str, Any],
    ) -> dict[str, Any]:
        """Render a component with given props."""
        # Get props schema
        props_schema = self._get_props_schema(component_class, props)

        # Create component
        try:
            component = component_class(**props)
        except Exception:
            # Use defaults if props invalid
            component = component_class()

        # Render with different renderers
        html_renderer = HTMLRenderer()
        json_renderer = JSONRenderer(indent=2)
        react_renderer = ReactRenderer()

        html_output = html_renderer.render(component)
        json_output = json_renderer.render(component)
        react_output = react_renderer.render(component)

        # Generate React code example
        react_code = self._generate_react_code(component_class.__name__, props)

        return {
            "props_schema": props_schema,
            "preview_html": html_output.content,
            "html_output": html_output.content,
            "json_output": json_output.content,
            "react_output": react_code,
        }

    def _get_props_schema(
        self,
        component_class: type[Component],
        current_props: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Extract props schema from component class."""
        schema = {}

        for name, field in component_class.model_fields.items():
            if name.startswith("_"):
                continue

            # Get type info
            type_str = "string"
            choices = None

            annotation = field.annotation
            if annotation:
                if annotation == bool:
                    type_str = "boolean"
                elif annotation == int or annotation == float:
                    type_str = "number"
                elif annotation == list or str(annotation).startswith("typing.List"):
                    type_str = "list"
                elif annotation == dict or str(annotation).startswith("typing.Dict"):
                    type_str = "dict"
                elif hasattr(annotation, "__args__"):  # Literal
                    if str(annotation).startswith("typing.Literal"):
                        choices = list(annotation.__args__)
                        type_str = "choice"

            # Get current value
            value = current_props.get(name, field.default)
            json_value = None

            if type_str in ("list", "dict") and value:
                try:
                    json_value = orjson.dumps(value, option=orjson.OPT_INDENT_2).decode()
                except (TypeError, ValueError):
                    json_value = str(value)

            schema[name] = {
                "type": type_str,
                "required": field.is_required(),
                "value": value,
                "json_value": json_value,
                "choices": choices,
                "description": field.description or "",
            }

        return schema

    def _generate_react_code(self, component_name: str, props: dict[str, Any]) -> str:
        """Generate React component code."""
        props_str = ""
        for key, value in props.items():
            if isinstance(value, bool):
                if value:
                    props_str += f"\n  {key}"
                else:
                    props_str += f"\n  {key}={{false}}"
            elif isinstance(value, str):
                props_str += f'\n  {key}="{value}"'
            elif isinstance(value, (int, float)):
                props_str += f"\n  {key}={{{value}}}"
            elif isinstance(value, (list, dict)):
                props_str += f"\n  {key}={{{orjson.dumps(value).decode()}}}"

        return f"""import {{ {component_name} }} from '@django-matt/react'

export function Example() {{
  return (
    <{component_name}{props_str}
    />
  )
}}"""


# =============================================================================
# API Endpoints
# =============================================================================


def playground_api_list(request: HttpRequest) -> JsonResponse:
    """
    List all available components.

    GET /api/components/
    """
    components = []

    for name in registry.list():
        cls = registry.get(name)
        if cls:
            components.append(
                {
                    "name": name,
                    "type": cls.__name__,
                    "module": cls.__module__,
                }
            )

    return JsonResponse({"components": components})


def playground_api_render(request: HttpRequest) -> JsonResponse:
    """
    Render a component with given props.

    POST /api/components/render
    {
        "component": "card",
        "props": {"title": "Hello"},
        "renderer": "html"  // or "json", "react"
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = orjson.loads(request.body)
    except orjson.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    component_name = data.get("component")
    props = data.get("props", {})
    renderer_type = data.get("renderer", "html")

    if not component_name:
        return JsonResponse({"error": "Missing component name"}, status=400)

    component_class = registry.get(component_name)
    if not component_class:
        return JsonResponse({"error": f"Unknown component: {component_name}"}, status=404)

    try:
        component = component_class(**props)
    except Exception as e:
        return JsonResponse({"error": f"Invalid props: {e}"}, status=400)

    # Select renderer
    renderers = {
        "html": HTMLRenderer(),
        "json": JSONRenderer(indent=2),
        "react": ReactRenderer(),
    }
    renderer = renderers.get(renderer_type, HTMLRenderer())

    output = renderer.render(component)

    return JsonResponse(
        {
            "content": output.content,
            "content_type": output.content_type,
        }
    )


def playground_api_schema(request: HttpRequest, component_name: str) -> JsonResponse:
    """
    Get component props schema.

    GET /api/components/{name}/schema
    """
    component_class = registry.get(component_name)
    if not component_class:
        return JsonResponse({"error": f"Unknown component: {component_name}"}, status=404)

    schema = {"properties": {}, "required": []}

    for name, field in component_class.model_fields.items():
        if name.startswith("_"):
            continue

        prop_schema = {
            "type": "string",
            "description": field.description or "",
        }

        annotation = field.annotation
        if annotation == bool:
            prop_schema["type"] = "boolean"
        elif annotation in (int, float):
            prop_schema["type"] = "number"
        elif annotation == list:
            prop_schema["type"] = "array"
        elif annotation == dict:
            prop_schema["type"] = "object"

        if field.default is not None:
            prop_schema["default"] = field.default

        schema["properties"][name] = prop_schema

        if field.is_required():
            schema["required"].append(name)

    return JsonResponse(schema)


__all__ = [
    "PlaygroundView",
    "playground_api_list",
    "playground_api_render",
    "playground_api_schema",
]
