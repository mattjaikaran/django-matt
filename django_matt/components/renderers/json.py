"""
JSON renderer for components.

Simple JSON serialization for API responses and debugging.
"""

import json
from typing import Any, Dict, Optional

from django_matt.components.base import Component
from django_matt.components.renderers.base import (
    BaseRenderer,
    RenderContext,
    RenderOutput,
)


class JSONRenderer(BaseRenderer):
    """
    Renders components as raw JSON.

    This is the simplest renderer - it just serializes the component
    to JSON using Pydantic's model_dump.

    Usage:
        from django_matt.components import Card
        from django_matt.components.renderers import JSONRenderer

        renderer = JSONRenderer()
        card = Card(title="Hello")
        output = renderer.render(card)
        # output.content is JSON string
    """

    def __init__(
        self,
        indent: Optional[int] = None,
        exclude_none: bool = True,
        exclude_defaults: bool = False,
    ):
        """
        Initialize JSON renderer.

        Args:
            indent: JSON indentation (None for compact)
            exclude_none: Exclude None values from output
            exclude_defaults: Exclude default values from output
        """
        self.indent = indent
        self.exclude_none = exclude_none
        self.exclude_defaults = exclude_defaults
        super().__init__()

    def _register_default_renderers(self) -> None:
        """No special renderers needed for JSON."""
        pass

    def render_component(
        self,
        component: Component,
        context: Optional[RenderContext] = None,
    ) -> RenderOutput:
        """Render a component to JSON."""
        data = component.model_dump(
            exclude_none=self.exclude_none,
            exclude_defaults=self.exclude_defaults,
        )

        # Convert enums to strings
        data = self._process_enums(data)

        content = json.dumps(
            data,
            indent=self.indent,
            default=str,
            ensure_ascii=False,
        )

        return RenderOutput(
            content=content,
            content_type="application/json",
        )

    def _process_enums(self, data: Any) -> Any:
        """Recursively convert enum values to strings."""
        if isinstance(data, dict):
            return {k: self._process_enums(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._process_enums(item) for item in data]
        elif hasattr(data, "value"):  # Enum
            return data.value
        return data


class PrettyJSONRenderer(JSONRenderer):
    """JSON renderer with pretty printing enabled by default."""

    def __init__(self, indent: int = 2, **kwargs):
        super().__init__(indent=indent, **kwargs)


class CompactJSONRenderer(JSONRenderer):
    """JSON renderer optimized for minimal size."""

    def __init__(self):
        super().__init__(
            indent=None,
            exclude_none=True,
            exclude_defaults=True,
        )
