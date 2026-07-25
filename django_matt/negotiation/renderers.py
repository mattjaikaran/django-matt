# file-length-max: 650
"""
Content renderers for different output formats.

Renderers convert Python data structures to various formats:
- JSON (with orjson/ujson support)
- XML
- CSV
- YAML
- MessagePack
- HTML (template-based)
"""

import csv
import io
import json
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from django.http import HttpResponse

import orjson

from django_matt.negotiation.config import (
    CSVConfig,
    HTMLConfig,
    JSONConfig,
    XMLConfig,
    YAMLConfig,
    get_negotiation_config,
)


class BaseRenderer(ABC):
    """Base class for all renderers."""

    media_type: str = "application/octet-stream"
    format: str = "raw"
    charset: str = "utf-8"

    @abstractmethod
    def render(self, data: Any, **kwargs) -> bytes:
        """Render data to bytes."""

    def to_response(self, data: Any, status: int = 200, **kwargs) -> HttpResponse:
        """Render data to HttpResponse."""
        content = self.render(data, **kwargs)
        return HttpResponse(
            content,
            status=status,
            content_type=f"{self.media_type}; charset={self.charset}",
        )


class JSONRenderer(BaseRenderer):
    """
    JSON renderer with orjson/ujson support for performance.

    Falls back to standard json if neither is available.
    """

    media_type = "application/json"
    format = "json"

    def __init__(self, config: JSONConfig | None = None):
        self.config = config or get_negotiation_config().json
        self._encoder = self._get_encoder()

    def _get_encoder(self):
        """Get the best available JSON encoder. orjson is a base dep, always available."""
        return "orjson"

    def _serialize_value(self, obj: Any) -> Any:
        """Serialize non-standard types for JSON."""
        if isinstance(obj, datetime) or isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if hasattr(obj, "model_dump_response"):  # Django Matt schema
            return obj.model_dump_response()
        if hasattr(obj, "model_dump"):  # Pydantic v2
            return obj.model_dump()
        if hasattr(obj, "dict"):  # Pydantic v1
            return obj.dict()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def render(self, data: Any, **kwargs) -> bytes:
        """Render data to JSON bytes."""
        indent = kwargs.get("indent", self.config.indent)
        ensure_ascii = kwargs.get("ensure_ascii", self.config.ensure_ascii)

        if self._encoder == "orjson":
            options = orjson.OPT_NON_STR_KEYS
            if indent:
                options |= orjson.OPT_INDENT_2
            if self.config.sort_keys:
                options |= orjson.OPT_SORT_KEYS
            return orjson.dumps(data, default=self._serialize_value, option=options)

        if self._encoder == "ujson":
            import ujson

            return ujson.dumps(
                data,
                indent=indent,
                ensure_ascii=ensure_ascii,
                default=self._serialize_value,
            ).encode(self.charset)

        return json.dumps(
            data,
            indent=indent,
            ensure_ascii=ensure_ascii,
            default=self._serialize_value,
            sort_keys=self.config.sort_keys,
        ).encode(self.charset)


class XMLRenderer(BaseRenderer):
    """
    XML renderer for structured data.

    Converts Python dicts/lists to XML format.
    """

    media_type = "application/xml"
    format = "xml"

    def __init__(self, config: XMLConfig | None = None):
        self.config = config or get_negotiation_config().xml

    def _serialize_value(self, value: Any) -> str:
        """Convert value to string for XML."""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal) or isinstance(value, UUID):
            return str(value)
        if isinstance(value, Enum):
            return str(value.value)
        if hasattr(value, "model_dump_response"):
            return self._dict_to_xml(value.model_dump_response())
        if hasattr(value, "model_dump"):
            return self._dict_to_xml(value.model_dump())
        if hasattr(value, "dict"):
            return self._dict_to_xml(value.dict())
        return str(value)

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def _dict_to_xml(self, data: dict, indent: int = 0) -> str:
        """Convert dictionary to XML string."""
        xml_parts = []
        prefix = "  " * indent if self.config.pretty_print else ""

        for key, value in data.items():
            # Sanitize key for XML tag name
            tag = str(key).replace(" ", "_")
            if tag[0].isdigit():
                tag = f"_{tag}"

            if isinstance(value, dict):
                inner = self._dict_to_xml(value, indent + 1)
                if self.config.pretty_print:
                    xml_parts.append(f"{prefix}<{tag}>\n{inner}{prefix}</{tag}>")
                else:
                    xml_parts.append(f"<{tag}>{inner}</{tag}>")

            elif isinstance(value, (list, tuple)):
                items = []
                for item in value:
                    if isinstance(item, dict):
                        inner = self._dict_to_xml(item, indent + 2)
                        if self.config.pretty_print:
                            items.append(
                                f"{prefix}  <{self.config.item_tag}>\n{inner}{prefix}  </{self.config.item_tag}>"
                            )
                        else:
                            items.append(
                                f"<{self.config.item_tag}>{inner}</{self.config.item_tag}>"
                            )
                    else:
                        items.append(
                            f"{prefix}  <{self.config.item_tag}>{self._escape_xml(self._serialize_value(item))}</{self.config.item_tag}>"
                        )

                if self.config.pretty_print:
                    xml_parts.append(
                        f"{prefix}<{tag}>\n" + "\n".join(items) + f"\n{prefix}</{tag}>"
                    )
                else:
                    xml_parts.append(f"<{tag}>{''.join(items)}</{tag}>")

            else:
                xml_parts.append(
                    f"{prefix}<{tag}>{self._escape_xml(self._serialize_value(value))}</{tag}>"
                )

        separator = "\n" if self.config.pretty_print else ""
        return separator.join(xml_parts) + (
            separator if self.config.pretty_print and xml_parts else ""
        )

    def render(self, data: Any, **kwargs) -> bytes:
        """Render data to XML bytes."""
        root_tag = kwargs.get("root_tag", self.config.root_tag)

        # Handle Pydantic models
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif hasattr(data, "dict"):
            data = data.dict()

        # Handle lists at root level
        if isinstance(data, (list, tuple)):
            items = []
            for item in data:
                if isinstance(item, dict):
                    inner = self._dict_to_xml(item, 1)
                elif hasattr(item, "model_dump"):
                    inner = self._dict_to_xml(item.model_dump(), 1)
                elif hasattr(item, "dict"):
                    inner = self._dict_to_xml(item.dict(), 1)
                else:
                    inner = self._escape_xml(self._serialize_value(item))

                if self.config.pretty_print:
                    items.append(f"  <{self.config.item_tag}>\n{inner}  </{self.config.item_tag}>")
                else:
                    items.append(f"<{self.config.item_tag}>{inner}</{self.config.item_tag}>")

            separator = "\n" if self.config.pretty_print else ""
            body = separator.join(items)
        elif isinstance(data, dict):
            body = self._dict_to_xml(data, 1)
        else:
            body = self._escape_xml(self._serialize_value(data))

        # Build XML
        parts = []
        if self.config.declaration:
            parts.append(f'<?xml version="1.0" encoding="{self.config.encoding}"?>')

        if self.config.pretty_print:
            parts.append(f"<{root_tag}>\n{body}</{root_tag}>")
        else:
            parts.append(f"<{root_tag}>{body}</{root_tag}>")

        separator = "\n" if self.config.pretty_print else ""
        return separator.join(parts).encode(self.config.encoding)


class CSVRenderer(BaseRenderer):
    """
    CSV renderer for tabular data.

    Best suited for lists of dictionaries with consistent keys.
    """

    media_type = "text/csv"
    format = "csv"

    def __init__(self, config: CSVConfig | None = None):
        self.config = config or get_negotiation_config().csv

    def _flatten_dict(self, data: dict, parent_key: str = "", sep: str = ".") -> dict:
        """Flatten nested dictionaries."""
        items = []
        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key
            if isinstance(value, dict):
                items.extend(self._flatten_dict(value, new_key, sep).items())
            else:
                items.append((new_key, value))
        return dict(items)

    def _serialize_value(self, value: Any) -> str:
        """Convert value to string for CSV."""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, (list, tuple)):
            return "|".join(str(v) for v in value)
        if isinstance(value, dict):
            return orjson.dumps(value).decode()
        if hasattr(value, "model_dump"):
            return orjson.dumps(value.model_dump()).decode()
        if hasattr(value, "dict"):
            return orjson.dumps(value.dict()).decode()
        return str(value)

    def render(self, data: Any, **kwargs) -> bytes:
        """Render data to CSV bytes."""
        output = io.StringIO()

        # Handle Pydantic models
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif hasattr(data, "dict"):
            data = data.dict()

        # Ensure we have a list
        if isinstance(data, dict):
            # Check if it's a paginated response with items
            if "items" in data and isinstance(data["items"], list):
                data = data["items"]
            else:
                data = [data]
        elif not isinstance(data, (list, tuple)):
            data = [data]

        if not data:
            return b""

        # Convert all items to dicts and flatten
        rows = []
        for item in data:
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            elif hasattr(item, "dict"):
                item = item.dict()
            elif not isinstance(item, dict):
                item = {"value": item}

            rows.append(self._flatten_dict(item))

        # Get all unique keys
        fieldnames = []
        seen = set()
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    fieldnames.append(key)
                    seen.add(key)

        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            delimiter=self.config.delimiter,
            extrasaction="ignore",
        )

        if self.config.include_header:
            writer.writeheader()

        for row in rows:
            writer.writerow({k: self._serialize_value(v) for k, v in row.items()})

        return output.getvalue().encode(self.charset)


class YAMLRenderer(BaseRenderer):
    """
    YAML renderer for human-readable output.

    Requires: uv add pyyaml
    """

    media_type = "application/yaml"
    format = "yaml"

    def __init__(self, config: YAMLConfig | None = None):
        self.config = config or get_negotiation_config().yaml

    def _prepare_data(self, data: Any) -> Any:
        """Prepare data for YAML serialization."""
        if hasattr(data, "model_dump"):
            return self._prepare_data(data.model_dump())
        if hasattr(data, "dict"):
            return self._prepare_data(data.dict())
        if isinstance(data, dict):
            return {k: self._prepare_data(v) for k, v in data.items()}
        if isinstance(data, (list, tuple)):
            return [self._prepare_data(item) for item in data]
        if isinstance(data, (datetime, date)):
            return data.isoformat()
        if isinstance(data, Decimal):
            return float(data)
        if isinstance(data, UUID):
            return str(data)
        if isinstance(data, Enum):
            return data.value
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return data

    def render(self, data: Any, **kwargs) -> bytes:
        """Render data to YAML bytes."""
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML is not installed. Install with: uv add pyyaml")

        prepared = self._prepare_data(data)

        return yaml.dump(
            prepared,
            default_flow_style=self.config.default_flow_style,
            allow_unicode=self.config.allow_unicode,
            indent=self.config.indent,
            sort_keys=False,
        ).encode(self.charset)


class MessagePackRenderer(BaseRenderer):
    """
    MessagePack renderer for efficient binary serialization.

    Requires: uv add msgpack
    """

    media_type = "application/msgpack"
    format = "msgpack"

    def _prepare_data(self, data: Any) -> Any:
        """Prepare data for MessagePack serialization."""
        if hasattr(data, "model_dump"):
            return self._prepare_data(data.model_dump())
        if hasattr(data, "dict"):
            return self._prepare_data(data.dict())
        if isinstance(data, dict):
            return {k: self._prepare_data(v) for k, v in data.items()}
        if isinstance(data, (list, tuple)):
            return [self._prepare_data(item) for item in data]
        if isinstance(data, (datetime, date)):
            return data.isoformat()
        if isinstance(data, Decimal):
            return float(data)
        if isinstance(data, UUID):
            return str(data)
        if isinstance(data, Enum):
            return data.value
        return data

    def render(self, data: Any, **kwargs) -> bytes:
        """Render data to MessagePack bytes."""
        try:
            import msgpack
        except ImportError:
            raise ImportError("msgpack is not installed. Install with: uv add msgpack")

        prepared = self._prepare_data(data)
        return msgpack.packb(prepared, use_bin_type=True)


class HTMLRenderer(BaseRenderer):
    """
    HTML renderer using Django templates.

    Useful for HTMX responses or server-rendered content.
    """

    media_type = "text/html"
    format = "html"

    def __init__(self, config: HTMLConfig | None = None):
        self.config = config or get_negotiation_config().html

    def render(self, data: Any, **kwargs) -> bytes:
        """Render data to HTML bytes using Django templates."""
        from django.template import TemplateDoesNotExist, loader

        template_name = kwargs.get("template_name", self.config.template_name)

        if not template_name:
            # Auto-generate simple HTML table for data
            return self._render_simple_html(data)

        try:
            template = loader.get_template(template_name)
        except TemplateDoesNotExist:
            # Fallback to simple HTML
            return self._render_simple_html(data)

        # Prepare context
        context = kwargs.get("context", {})
        if hasattr(data, "model_dump"):
            context["data"] = data.model_dump()
        elif hasattr(data, "dict"):
            context["data"] = data.dict()
        else:
            context["data"] = data

        return template.render(context).encode(self.charset)

    def _render_simple_html(self, data: Any) -> bytes:
        """Render simple HTML representation of data."""
        # Handle Pydantic models
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif hasattr(data, "dict"):
            data = data.dict()

        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            '<meta charset="utf-8">',
            "<title>API Response</title>",
            "<style>",
            "body { font-family: system-ui, sans-serif; margin: 2rem; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f5f5f5; }",
            "tr:nth-child(even) { background-color: #fafafa; }",
            "pre { background: #f5f5f5; padding: 1rem; overflow-x: auto; }",
            "</style>",
            "</head>",
            "<body>",
        ]

        if isinstance(data, (list, tuple)) and data and isinstance(data[0], dict):
            # Render as table
            html_parts.append("<table>")
            headers = list(data[0].keys())
            html_parts.append("<thead><tr>")
            for h in headers:
                html_parts.append(f"<th>{self._escape_html(str(h))}</th>")
            html_parts.append("</tr></thead>")
            html_parts.append("<tbody>")
            for row in data:
                html_parts.append("<tr>")
                for h in headers:
                    value = row.get(h, "")
                    html_parts.append(f"<td>{self._escape_html(str(value))}</td>")
                html_parts.append("</tr>")
            html_parts.append("</tbody></table>")
        else:
            # Render as formatted JSON
            html_parts.append("<pre>")
            html_parts.append(
                self._escape_html(
                    orjson.dumps(data, default=str, option=orjson.OPT_INDENT_2).decode()
                )
            )
            html_parts.append("</pre>")

        html_parts.extend(["</body>", "</html>"])
        return "\n".join(html_parts).encode(self.charset)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )


# Registry of available renderers
RENDERERS: dict[str, type[BaseRenderer]] = {
    "json": JSONRenderer,
    "xml": XMLRenderer,
    "csv": CSVRenderer,
    "yaml": YAMLRenderer,
    "msgpack": MessagePackRenderer,
    "html": HTMLRenderer,
}


# Media type to format mapping
MEDIA_TYPE_MAP: dict[str, str] = {
    "application/json": "json",
    "text/json": "json",
    "application/xml": "xml",
    "text/xml": "xml",
    "text/csv": "csv",
    "application/csv": "csv",
    "application/yaml": "yaml",
    "application/x-yaml": "yaml",
    "text/yaml": "yaml",
    "text/x-yaml": "yaml",
    "application/msgpack": "msgpack",
    "application/x-msgpack": "msgpack",
    "text/html": "html",
    "application/xhtml+xml": "html",
    "*/*": "json",  # Default
}


def get_renderer(format_name: str) -> BaseRenderer:
    """Get a renderer instance by format name."""
    config = get_negotiation_config()

    # Check aliases
    format_name = config.format_aliases.get(format_name, format_name)

    renderer_class = RENDERERS.get(format_name)
    if not renderer_class:
        raise ValueError(f"Unknown format: {format_name}")

    return renderer_class()


def get_renderer_for_media_type(media_type: str) -> BaseRenderer:
    """Get a renderer instance by media type."""
    # Parse media type (e.g., "application/json; charset=utf-8")
    media_type = media_type.split(";")[0].strip().lower()

    format_name = MEDIA_TYPE_MAP.get(media_type, "json")
    return get_renderer(format_name)
