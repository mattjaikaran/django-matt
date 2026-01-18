"""
Base renderer class for component rendering.

Provides the abstract interface that all renderers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union

from django_matt.components.base import Component, ComponentType
from django_matt.components.theming import Theme, get_theme


@dataclass
class RenderContext:
    """Context passed to renderers during component rendering."""
    theme: Theme = field(default_factory=get_theme)
    dark_mode: bool = False
    locale: str = "en"
    data: Dict[str, Any] = field(default_factory=dict)
    user: Optional[Any] = None
    request: Optional[Any] = None
    path: List[str] = field(default_factory=list)  # Component path for debugging

    def child_context(self, component_id: str) -> "RenderContext":
        """Create a child context for nested components."""
        return RenderContext(
            theme=self.theme,
            dark_mode=self.dark_mode,
            locale=self.locale,
            data=self.data,
            user=self.user,
            request=self.request,
            path=[*self.path, component_id],
        )


@dataclass
class RenderOutput:
    """Output from a renderer."""
    content: str  # Rendered content (HTML, JSON, etc.)
    content_type: str = "text/html"  # MIME type
    scripts: List[str] = field(default_factory=list)  # Additional scripts to include
    styles: List[str] = field(default_factory=list)  # Additional styles to include
    head: List[str] = field(default_factory=list)  # Content for <head>
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata


class BaseRenderer(ABC):
    """
    Abstract base class for component renderers.

    Subclasses must implement the render_component method to transform
    Component instances into their target format.

    Usage:
        class MyRenderer(BaseRenderer):
            def render_component(self, component, context):
                # Transform component to output format
                ...
                return RenderOutput(content=html)
    """

    def __init__(self):
        self._component_renderers: Dict[ComponentType, callable] = {}
        self._register_default_renderers()

    @abstractmethod
    def _register_default_renderers(self) -> None:
        """Register default component-specific renderers."""
        pass

    def register_renderer(
        self,
        component_type: ComponentType,
        renderer: callable,
    ) -> None:
        """Register a custom renderer for a component type."""
        self._component_renderers[component_type] = renderer

    @abstractmethod
    def render_component(
        self,
        component: Component,
        context: Optional[RenderContext] = None,
    ) -> RenderOutput:
        """
        Render a single component.

        Args:
            component: The component to render
            context: Rendering context with theme, data, etc.

        Returns:
            RenderOutput with the rendered content
        """
        pass

    def render(
        self,
        component: Union[Component, List[Component]],
        context: Optional[RenderContext] = None,
    ) -> RenderOutput:
        """
        Render one or more components.

        Args:
            component: Single component or list of components
            context: Rendering context

        Returns:
            Combined RenderOutput
        """
        if context is None:
            context = RenderContext()

        if isinstance(component, list):
            outputs = [self.render_component(c, context) for c in component]
            return self._combine_outputs(outputs)

        return self.render_component(component, context)

    def _combine_outputs(self, outputs: List[RenderOutput]) -> RenderOutput:
        """Combine multiple render outputs into one."""
        if not outputs:
            return RenderOutput(content="")

        combined_content = "\n".join(o.content for o in outputs)
        combined_scripts = []
        combined_styles = []
        combined_head = []
        combined_metadata = {}

        for output in outputs:
            combined_scripts.extend(output.scripts)
            combined_styles.extend(output.styles)
            combined_head.extend(output.head)
            combined_metadata.update(output.metadata)

        # Deduplicate
        combined_scripts = list(dict.fromkeys(combined_scripts))
        combined_styles = list(dict.fromkeys(combined_styles))
        combined_head = list(dict.fromkeys(combined_head))

        return RenderOutput(
            content=combined_content,
            content_type=outputs[0].content_type,
            scripts=combined_scripts,
            styles=combined_styles,
            head=combined_head,
            metadata=combined_metadata,
        )

    def render_children(
        self,
        children: List[Component],
        context: RenderContext,
    ) -> str:
        """Render a list of child components."""
        if not children:
            return ""

        parts = []
        for child in children:
            output = self.render_component(child, context)
            parts.append(output.content)

        return "\n".join(parts)


class ComponentNotFoundError(Exception):
    """Raised when a component type has no registered renderer."""
    pass
