"""
Content parsers for different input formats.

Parsers convert incoming request bodies to Python data structures:
- JSON
- XML
- Form data
- Multipart form data
- YAML
- MessagePack
"""

import json
from abc import ABC, abstractmethod
from typing import Any
from xml.etree import ElementTree

from django.http import HttpRequest


class ParseError(Exception):
    """Raised when parsing fails."""

    def __init__(self, message: str, detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(message)


class BaseParser(ABC):
    """Base class for all parsers."""

    media_type: str = "application/octet-stream"
    format: str = "raw"

    @abstractmethod
    def parse(self, data: bytes, **kwargs) -> Any:
        """Parse bytes to Python data structure."""

    def parse_request(self, request: HttpRequest, **kwargs) -> Any:
        """Parse request body."""
        return self.parse(request.body, **kwargs)


class JSONParser(BaseParser):
    """
    JSON parser with orjson/ujson support for performance.
    """

    media_type = "application/json"
    format = "json"

    def __init__(self):
        self._decoder = self._get_decoder()

    def _get_decoder(self) -> str:
        """Get the best available JSON decoder. orjson is a base dep, always available."""
        return "orjson"

    def parse(self, data: bytes, **kwargs) -> Any:
        """Parse JSON bytes to Python data."""
        if not data:
            return None

        try:
            import orjson

            return orjson.loads(data)
        except (ValueError, orjson.JSONDecodeError) as e:
            raise ParseError("Invalid JSON", str(e))


class XMLParser(BaseParser):
    """
    XML parser using ElementTree.

    Converts XML to nested dictionaries.
    """

    media_type = "application/xml"
    format = "xml"

    def _element_to_dict(self, element: ElementTree.Element) -> dict | str | list:
        """Convert XML element to dictionary."""
        result: dict[str, Any] = {}

        # Add attributes
        if element.attrib:
            result["@attributes"] = dict(element.attrib)

        # Process children
        children: dict[str, list] = {}
        for child in element:
            child_data = self._element_to_dict(child)
            if child.tag in children:
                children[child.tag].append(child_data)
            else:
                children[child.tag] = [child_data]

        # Flatten single-item lists
        for key, value in children.items():
            if len(value) == 1:
                result[key] = value[0]
            else:
                result[key] = value

        # Handle text content
        if element.text and element.text.strip():
            if result:
                result["#text"] = element.text.strip()
            else:
                return element.text.strip()

        return result if result else ""

    def parse(self, data: bytes, **kwargs) -> Any:
        """Parse XML bytes to Python data."""
        if not data:
            return None

        try:
            root = ElementTree.fromstring(data)
            return {root.tag: self._element_to_dict(root)}
        except ElementTree.ParseError as e:
            raise ParseError("Invalid XML", str(e))


class FormParser(BaseParser):
    """
    Form data parser (application/x-www-form-urlencoded).
    """

    media_type = "application/x-www-form-urlencoded"
    format = "form"

    def parse(self, data: bytes, **kwargs) -> Any:
        """Parse form data to dictionary."""
        from urllib.parse import parse_qs

        if not data:
            return {}

        try:
            decoded = data.decode("utf-8")
            parsed = parse_qs(decoded, keep_blank_values=True)

            # Convert single-value lists to values
            result = {}
            for key, values in parsed.items():
                if len(values) == 1:
                    result[key] = values[0]
                else:
                    result[key] = values

            return result
        except Exception as e:
            raise ParseError("Invalid form data", str(e))

    def parse_request(self, request: HttpRequest, **kwargs) -> Any:
        """Parse form data from request."""
        # Django already parses form data
        return dict(request.POST)


class MultiPartParser(BaseParser):
    """
    Multipart form data parser (multipart/form-data).

    Handles file uploads.
    """

    media_type = "multipart/form-data"
    format = "multipart"

    def parse(self, data: bytes, **kwargs) -> Any:
        """Parse multipart data."""
        # This is typically handled by Django's request parsing
        raise ParseError(
            "Multipart parsing not supported on raw bytes",
            "Use parse_request() instead",
        )

    def parse_request(self, request: HttpRequest, **kwargs) -> Any:
        """Parse multipart form data from request."""
        result = dict(request.POST)
        result["_files"] = dict(request.FILES)
        return result


class YAMLParser(BaseParser):
    """
    YAML parser.

    Requires: pip install pyyaml
    """

    media_type = "application/yaml"
    format = "yaml"

    def parse(self, data: bytes, **kwargs) -> Any:
        """Parse YAML bytes to Python data."""
        if not data:
            return None

        try:
            import yaml
        except ImportError:
            raise ParseError(
                "PyYAML not installed",
                "Install with: pip install pyyaml",
            )

        try:
            return yaml.safe_load(data)
        except yaml.YAMLError as e:
            raise ParseError("Invalid YAML", str(e))


class MessagePackParser(BaseParser):
    """
    MessagePack parser.

    Requires: pip install msgpack
    """

    media_type = "application/msgpack"
    format = "msgpack"

    def parse(self, data: bytes, **kwargs) -> Any:
        """Parse MessagePack bytes to Python data."""
        if not data:
            return None

        try:
            import msgpack
        except ImportError:
            raise ParseError(
                "msgpack not installed",
                "Install with: pip install msgpack",
            )

        try:
            return msgpack.unpackb(data, raw=False)
        except Exception as e:
            raise ParseError("Invalid MessagePack", str(e))


# Registry of available parsers
PARSERS: dict[str, type[BaseParser]] = {
    "json": JSONParser,
    "xml": XMLParser,
    "form": FormParser,
    "multipart": MultiPartParser,
    "yaml": YAMLParser,
    "msgpack": MessagePackParser,
}


# Media type to parser mapping
MEDIA_TYPE_PARSER_MAP: dict[str, str] = {
    "application/json": "json",
    "text/json": "json",
    "application/xml": "xml",
    "text/xml": "xml",
    "application/x-www-form-urlencoded": "form",
    "multipart/form-data": "multipart",
    "application/yaml": "yaml",
    "application/x-yaml": "yaml",
    "text/yaml": "yaml",
    "text/x-yaml": "yaml",
    "application/msgpack": "msgpack",
    "application/x-msgpack": "msgpack",
}


def get_parser(format_name: str) -> BaseParser:
    """Get a parser instance by format name."""
    parser_class = PARSERS.get(format_name)
    if not parser_class:
        raise ValueError(f"Unknown format: {format_name}")
    return parser_class()


def get_parser_for_media_type(media_type: str) -> BaseParser:
    """Get a parser instance by media type."""
    # Parse media type (e.g., "application/json; charset=utf-8")
    base_type = media_type.split(";")[0].strip().lower()

    # Handle multipart with boundary
    if base_type.startswith("multipart/"):
        return get_parser("multipart")

    format_name = MEDIA_TYPE_PARSER_MAP.get(base_type)
    if not format_name:
        # Default to JSON
        format_name = "json"

    return get_parser(format_name)


def parse_request_body(request: HttpRequest) -> Any:
    """
    Parse request body based on Content-Type header.

    Returns parsed data or None if no body.
    """
    content_type = request.content_type or "application/json"

    try:
        parser = get_parser_for_media_type(content_type)
        return parser.parse_request(request)
    except ParseError:
        raise
    except Exception as e:
        raise ParseError(f"Failed to parse request body: {e}")
