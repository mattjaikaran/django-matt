"""
Component renderers for different frontend frameworks.

Each renderer transforms Python component definitions into
framework-specific output (React, Vue, HTML, Svelte, etc.).

Renderers are lazy-loaded — importing this module does NOT pull in
Vue, Svelte, Astro, or Remix code. Only the renderer you actually
use gets imported. Base, HTML, JSON, and React are always available
since they have no heavy dependencies.
"""

from django_matt.components.renderers.base import (
    BaseRenderer,
    RenderContext,
    RenderOutput,
)
from django_matt.components.renderers.html import HTMLRenderer
from django_matt.components.renderers.json import JSONRenderer
from django_matt.components.renderers.react import ReactRenderer


def __getattr__(name: str):
    """Lazy import for framework-specific renderers."""
    _lazy = {
        # Vue
        "VueRenderer": "django_matt.components.renderers.vue",
        "VueSFCRenderer": "django_matt.components.renderers.vue",
        "VUE_COMPONENT_MAP": "django_matt.components.renderers.vue",
        "get_vue_component_name": "django_matt.components.renderers.vue",
        "generate_vue_project": "django_matt.components.renderers.vue",
        "generate_vue_types": "django_matt.components.renderers.vue",
        "generate_composables": "django_matt.components.renderers.vue",
        # Svelte
        "SvelteRenderer": "django_matt.components.renderers.svelte",
        "SvelteComponentOutput": "django_matt.components.renderers.svelte",
        "SvelteStoreDefinition": "django_matt.components.renderers.svelte",
        "SVELTE_COMPONENT_MAP": "django_matt.components.renderers.svelte",
        "SVELTE_TRANSITIONS": "django_matt.components.renderers.svelte",
        "SVELTE_EASING": "django_matt.components.renderers.svelte",
        "get_svelte_component_name": "django_matt.components.renderers.svelte",
        "generate_svelte_project": "django_matt.components.renderers.svelte",
        "generate_svelte_types": "django_matt.components.renderers.svelte",
        "generate_stores": "django_matt.components.renderers.svelte",
        # Astro
        "AstroRenderer": "django_matt.components.renderers.astro",
        "ASTRO_COMPONENT_MAP": "django_matt.components.renderers.astro",
        "INTERACTIVE_COMPONENTS": "django_matt.components.renderers.astro",
        "get_astro_component_name": "django_matt.components.renderers.astro",
        "generate_astro_page": "django_matt.components.renderers.astro",
        "generate_astro_project": "django_matt.components.renderers.astro",
        # Remix
        "RemixRenderer": "django_matt.components.renderers.remix",
        "REMIX_COMPONENT_MAP": "django_matt.components.renderers.remix",
        "get_remix_component_name": "django_matt.components.renderers.remix",
        "generate_remix_route": "django_matt.components.renderers.remix",
        "generate_remix_project": "django_matt.components.renderers.remix",
    }

    if name in _lazy:
        import importlib

        module = importlib.import_module(_lazy[name])
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Base (always loaded)
    "BaseRenderer",
    "RenderContext",
    "RenderOutput",
    # Core renderers (always loaded — no heavy deps)
    "HTMLRenderer",
    "JSONRenderer",
    "ReactRenderer",
    # Vue (lazy)
    "VueRenderer",
    "VueSFCRenderer",
    "VUE_COMPONENT_MAP",
    "get_vue_component_name",
    "generate_vue_project",
    "generate_vue_types",
    "generate_composables",
    # Svelte (lazy)
    "SvelteRenderer",
    "SvelteComponentOutput",
    "SvelteStoreDefinition",
    "SVELTE_COMPONENT_MAP",
    "SVELTE_TRANSITIONS",
    "SVELTE_EASING",
    "get_svelte_component_name",
    "generate_svelte_project",
    "generate_svelte_types",
    "generate_stores",
    # Astro (lazy)
    "AstroRenderer",
    "ASTRO_COMPONENT_MAP",
    "INTERACTIVE_COMPONENTS",
    "get_astro_component_name",
    "generate_astro_page",
    "generate_astro_project",
    # Remix (lazy)
    "RemixRenderer",
    "REMIX_COMPONENT_MAP",
    "get_remix_component_name",
    "generate_remix_route",
    "generate_remix_project",
]
