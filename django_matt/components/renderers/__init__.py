"""
Component renderers for different frontend frameworks.

Each renderer transforms Python component definitions into
framework-specific output (React, Vue, HTML, Svelte, etc.).
"""

from django_matt.components.renderers.base import (
    BaseRenderer,
    RenderContext,
    RenderOutput,
)
from django_matt.components.renderers.html import HTMLRenderer
from django_matt.components.renderers.json import JSONRenderer
from django_matt.components.renderers.react import ReactRenderer
from django_matt.components.renderers.svelte import (
    SVELTE_COMPONENT_MAP,
    SVELTE_EASING,
    SVELTE_TRANSITIONS,
    SvelteComponentOutput,
    SvelteRenderer,
    SvelteStoreDefinition,
    generate_stores,
    generate_svelte_project,
    generate_svelte_types,
    get_svelte_component_name,
)
from django_matt.components.renderers.vue import (
    VUE_COMPONENT_MAP,
    VueRenderer,
    VueSFCRenderer,
    generate_composables,
    generate_vue_project,
    generate_vue_types,
    get_vue_component_name,
)

__all__ = [
    # Base
    "BaseRenderer",
    "RenderContext",
    "RenderOutput",
    # Renderers
    "HTMLRenderer",
    "JSONRenderer",
    "ReactRenderer",
    "VueRenderer",
    "VueSFCRenderer",
    "SvelteRenderer",
    # Vue utilities
    "VUE_COMPONENT_MAP",
    "get_vue_component_name",
    "generate_vue_project",
    "generate_vue_types",
    "generate_composables",
    # Svelte utilities
    "SvelteComponentOutput",
    "SvelteStoreDefinition",
    "SVELTE_COMPONENT_MAP",
    "SVELTE_TRANSITIONS",
    "SVELTE_EASING",
    "get_svelte_component_name",
    "generate_svelte_project",
    "generate_svelte_types",
    "generate_stores",
]
