"""
Template tags for Livewire components.

Usage:
    {% load livewire_tags %}

    <!-- Include Livewire scripts -->
    {% livewire_scripts %}

    <!-- Render a component -->
    {% livewire "counter" count=5 %}

    <!-- With WebSocket support -->
    {% livewire_scripts websocket="/ws/livewire/" %}
"""

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from django_matt.livewire.registry import registry
from django_matt.livewire.views import render_component

register = template.Library()


@register.simple_tag
def livewire_scripts(websocket: str = None, csrf: bool = True) -> str:
    """
    Include Livewire JavaScript.

    Args:
        websocket: WebSocket URL for real-time updates
        csrf: Include CSRF token meta tag

    Usage:
        {% livewire_scripts %}
        {% livewire_scripts websocket="/ws/livewire/" %}
    """
    html_parts = []

    # CSRF token
    if csrf:
        from django.middleware.csrf import get_token
        html_parts.append(
            '<meta name="csrf-token" content="{% csrf_token %}">'
        )

    # Main script
    html_parts.append(
        '<script src="{% static \'livewire/livewire.js\' %}"></script>'
    )

    # WebSocket connection
    if websocket:
        html_parts.append(f'''
<script>
    document.addEventListener('DOMContentLoaded', function() {{
        Livewire.connectWebSocket('{websocket}');
    }});
</script>
''')

    return mark_safe("\n".join(html_parts))


@register.simple_tag
def livewire_styles() -> str:
    """
    Include Livewire CSS (loading states, transitions).

    Usage:
        {% livewire_styles %}
    """
    return mark_safe('''
<style>
    [wire\\:loading] {
        opacity: 0.5;
        pointer-events: none;
    }

    [wire\\:loading\\.remove] {
        display: none !important;
    }

    [wire\\:loading\\.class] {
        /* Applied via JavaScript */
    }

    .livewire-loading {
        position: relative;
    }

    .livewire-loading::after {
        content: "";
        position: absolute;
        top: 50%;
        left: 50%;
        width: 1rem;
        height: 1rem;
        margin: -0.5rem 0 0 -0.5rem;
        border: 2px solid currentColor;
        border-right-color: transparent;
        border-radius: 50%;
        animation: livewire-spin 0.75s linear infinite;
    }

    @keyframes livewire-spin {
        to { transform: rotate(360deg); }
    }
</style>
''')


@register.simple_tag(takes_context=True)
def livewire(context, component_name: str, **kwargs) -> str:
    """
    Render a Livewire component.

    Args:
        component_name: Name of the registered component
        **kwargs: Props to pass to the component

    Usage:
        {% livewire "counter" count=5 %}
        {% livewire "todo-list" items=items %}
    """
    component_class = registry.get(component_name)
    if component_class is None:
        return mark_safe(f'<!-- Unknown component: {component_name} -->')

    # Create component with props
    component = component_class(**kwargs)

    # Get request from context
    request = context.get("request")

    # Render
    html = render_component(component, request=request)
    return mark_safe(html)


@register.inclusion_tag("livewire/component.html", takes_context=True)
def livewire_component(context, component_name: str, **kwargs):
    """
    Render a component using a template.

    Usage:
        {% livewire_component "counter" count=5 %}
    """
    component_class = registry.get(component_name)
    if component_class is None:
        return {"error": f"Unknown component: {component_name}"}

    component = component_class(**kwargs)
    request = context.get("request")

    if request:
        component._request = request

    if not component._mounted:
        component.mount()

    from django_matt.livewire.state import Snapshot

    snapshot = Snapshot(
        component_name=component._component_name,
        component_id=component._component_id,
        state=component.dehydrate(),
        checksum=component.get_checksum(),
    )

    return {
        "component": component,
        "component_id": component.component_id,
        "snapshot_token": snapshot.to_token(),
        "html": component.to_html(),
    }


@register.simple_tag
def wire_model(field_name: str, modifiers: str = "") -> str:
    """
    Generate wire:model attribute.

    Usage:
        <input {% wire_model "email" %}>
        <input {% wire_model "search" "debounce.300ms" %}>
    """
    if modifiers:
        return format_html('wire:model.{}="{}"', modifiers, field_name)
    return format_html('wire:model="{}"', field_name)


@register.simple_tag
def wire_click(action: str) -> str:
    """
    Generate wire:click attribute.

    Usage:
        <button {% wire_click "increment" %}>+</button>
        <button {% wire_click "delete(item.id)" %}>Delete</button>
    """
    return format_html('wire:click="{}"', action)


@register.simple_tag
def wire_submit(action: str) -> str:
    """
    Generate wire:submit attribute.

    Usage:
        <form {% wire_submit "save" %}>
    """
    return format_html('wire:submit.prevent="{}"', action)


@register.simple_tag
def wire_loading(style: str = "opacity") -> str:
    """
    Generate wire:loading attribute.

    Usage:
        <div {% wire_loading %}>Loading...</div>
        <div {% wire_loading "remove" %}>Hidden when loading</div>
    """
    if style == "opacity":
        return mark_safe('wire:loading')
    return format_html('wire:loading.{}', style)


@register.filter
def wire_key(value, key: str) -> str:
    """
    Generate wire:key attribute for list items.

    Usage:
        {% for item in items %}
            <div {{ item|wire_key:"id" }}>{{ item.name }}</div>
        {% endfor %}
    """
    key_value = getattr(value, key, None) or value.get(key, str(value))
    return format_html('wire:key="{}"', key_value)
