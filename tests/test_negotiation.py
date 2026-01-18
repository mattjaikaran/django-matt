"""
Tests for the Content Negotiation module in Django Matt.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, TestCase, override_settings

from django_matt.negotiation import (
    BaseRenderer,
    JSONRenderer,
    XMLRenderer,
    CSVRenderer,
    YAMLRenderer,
    HTMLRenderer,
    MessagePackRenderer,
    get_renderer,
    get_renderer_for_media_type,
    RENDERERS,
    MEDIA_TYPE_MAP,
    BaseParser,
    JSONParser,
    XMLParser,
    FormParser,
    YAMLParser,
    MessagePackParser,
    ParseError,
    get_parser,
    get_parser_for_media_type,
    parse_request_body,
    PARSERS,
    ContentNegotiator,
    NegotiatedFormat,
    NotAcceptable,
    negotiate,
    render,
    render_format,
    ContentNegotiationMiddleware,
    renders,
    render_as,
    content_negotiated,
    with_template,
    NegotiatedResponse,
    NegotiationConfig,
    JSONConfig,
    XMLConfig,
    CSVConfig,
    YAMLConfig,
    HTMLConfig,
    get_negotiation_config,
)


# =============================================================================
# Test Fixtures
# =============================================================================


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class MockPydanticModel:
    """Mock Pydantic model for testing."""

    def __init__(self, data):
        self._data = data

    def model_dump(self):
        return self._data


# =============================================================================
# Configuration Tests
# =============================================================================


class TestJSONConfig(TestCase):
    """Tests for JSONConfig."""

    def test_default_values(self):
        """Test default JSON configuration values."""
        config = JSONConfig()
        self.assertIsNone(config.indent)
        self.assertFalse(config.ensure_ascii)
        self.assertFalse(config.sort_keys)

    def test_custom_values(self):
        """Test custom JSON configuration values."""
        config = JSONConfig(indent=2, ensure_ascii=True, sort_keys=True)
        self.assertEqual(config.indent, 2)
        self.assertTrue(config.ensure_ascii)
        self.assertTrue(config.sort_keys)


class TestXMLConfig(TestCase):
    """Tests for XMLConfig."""

    def test_default_values(self):
        """Test default XML configuration values."""
        config = XMLConfig()
        self.assertEqual(config.root_tag, "response")
        self.assertEqual(config.item_tag, "item")
        self.assertTrue(config.declaration)
        self.assertEqual(config.encoding, "utf-8")
        self.assertFalse(config.pretty_print)

    def test_custom_values(self):
        """Test custom XML configuration values."""
        config = XMLConfig(root_tag="data", item_tag="element", pretty_print=True)
        self.assertEqual(config.root_tag, "data")
        self.assertEqual(config.item_tag, "element")
        self.assertTrue(config.pretty_print)


class TestCSVConfig(TestCase):
    """Tests for CSVConfig."""

    def test_default_values(self):
        """Test default CSV configuration values."""
        config = CSVConfig()
        self.assertEqual(config.delimiter, ",")
        self.assertTrue(config.include_header)

    def test_custom_values(self):
        """Test custom CSV configuration values."""
        config = CSVConfig(delimiter=";", include_header=False)
        self.assertEqual(config.delimiter, ";")
        self.assertFalse(config.include_header)


class TestNegotiationConfig(TestCase):
    """Tests for NegotiationConfig."""

    def test_default_values(self):
        """Test default negotiation configuration."""
        config = NegotiationConfig()
        self.assertEqual(config.default_format, "json")
        self.assertEqual(config.format_query_param, "format")
        self.assertFalse(config.strict_accept)
        self.assertIn("json", config.formats)


# =============================================================================
# JSON Renderer Tests
# =============================================================================


class TestJSONRenderer(TestCase):
    """Tests for JSONRenderer."""

    def setUp(self):
        self.renderer = JSONRenderer()

    def test_media_type(self):
        """Test JSON media type."""
        self.assertEqual(self.renderer.media_type, "application/json")
        self.assertEqual(self.renderer.format, "json")

    def test_render_dict(self):
        """Test rendering a dictionary."""
        data = {"key": "value", "number": 42}
        result = self.renderer.render(data)
        self.assertIsInstance(result, bytes)
        parsed = json.loads(result)
        self.assertEqual(parsed, data)

    def test_render_list(self):
        """Test rendering a list."""
        data = [1, 2, 3, "four"]
        result = self.renderer.render(data)
        parsed = json.loads(result)
        self.assertEqual(parsed, data)

    def test_render_datetime(self):
        """Test rendering datetime objects."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        data = {"timestamp": dt}
        result = self.renderer.render(data)
        parsed = json.loads(result)
        self.assertEqual(parsed["timestamp"], "2024-01-15T10:30:00")

    def test_render_date(self):
        """Test rendering date objects."""
        d = date(2024, 1, 15)
        data = {"date": d}
        result = self.renderer.render(data)
        parsed = json.loads(result)
        self.assertEqual(parsed["date"], "2024-01-15")

    def test_render_decimal(self):
        """Test rendering Decimal objects."""
        data = {"price": Decimal("19.99")}
        result = self.renderer.render(data)
        parsed = json.loads(result)
        self.assertEqual(parsed["price"], 19.99)

    def test_render_uuid(self):
        """Test rendering UUID objects."""
        uid = UUID("12345678-1234-5678-1234-567812345678")
        data = {"id": uid}
        result = self.renderer.render(data)
        parsed = json.loads(result)
        self.assertEqual(parsed["id"], str(uid))

    def test_render_enum(self):
        """Test rendering Enum objects."""
        data = {"color": Color.RED}
        result = self.renderer.render(data)
        parsed = json.loads(result)
        self.assertEqual(parsed["color"], "red")

    def test_render_pydantic_model(self):
        """Test rendering Pydantic-like model."""
        model = MockPydanticModel({"name": "test", "value": 123})
        data = {"model": model}
        result = self.renderer.render(data)
        parsed = json.loads(result)
        self.assertEqual(parsed["model"], {"name": "test", "value": 123})

    def test_to_response(self):
        """Test rendering to HttpResponse."""
        data = {"key": "value"}
        response = self.renderer.to_response(data, status=201)
        self.assertEqual(response.status_code, 201)
        self.assertIn("application/json", response["Content-Type"])


# =============================================================================
# XML Renderer Tests
# =============================================================================


class TestXMLRenderer(TestCase):
    """Tests for XMLRenderer."""

    def setUp(self):
        self.renderer = XMLRenderer()

    def test_media_type(self):
        """Test XML media type."""
        self.assertEqual(self.renderer.media_type, "application/xml")
        self.assertEqual(self.renderer.format, "xml")

    def test_render_dict(self):
        """Test rendering a dictionary to XML."""
        data = {"name": "John", "age": 30}
        result = self.renderer.render(data)
        self.assertIsInstance(result, bytes)
        self.assertIn(b"<name>John</name>", result)
        self.assertIn(b"<age>30</age>", result)

    def test_render_with_declaration(self):
        """Test XML declaration is included."""
        data = {"key": "value"}
        result = self.renderer.render(data)
        self.assertIn(b'<?xml version="1.0"', result)

    def test_render_list(self):
        """Test rendering a list to XML."""
        data = [{"id": 1}, {"id": 2}]
        result = self.renderer.render(data)
        self.assertIn(b"<item>", result)
        self.assertIn(b"<id>1</id>", result)
        self.assertIn(b"<id>2</id>", result)

    def test_escape_special_chars(self):
        """Test XML special characters are escaped."""
        data = {"value": "<test>&\"'"}
        result = self.renderer.render(data)
        self.assertIn(b"&lt;test&gt;&amp;&quot;&apos;", result)

    def test_nested_dict(self):
        """Test rendering nested dictionaries."""
        data = {"user": {"name": "John", "address": {"city": "NYC"}}}
        result = self.renderer.render(data)
        self.assertIn(b"<user>", result)
        self.assertIn(b"<address>", result)
        self.assertIn(b"<city>NYC</city>", result)

    def test_custom_root_tag(self):
        """Test custom root tag."""
        data = {"key": "value"}
        result = self.renderer.render(data, root_tag="custom")
        self.assertIn(b"<custom>", result)
        self.assertIn(b"</custom>", result)


# =============================================================================
# CSV Renderer Tests
# =============================================================================


class TestCSVRenderer(TestCase):
    """Tests for CSVRenderer."""

    def setUp(self):
        self.renderer = CSVRenderer()

    def test_media_type(self):
        """Test CSV media type."""
        self.assertEqual(self.renderer.media_type, "text/csv")
        self.assertEqual(self.renderer.format, "csv")

    def test_render_list_of_dicts(self):
        """Test rendering list of dictionaries to CSV."""
        data = [
            {"name": "John", "age": 30},
            {"name": "Jane", "age": 25},
        ]
        result = self.renderer.render(data)
        lines = result.decode().strip().split("\n")
        self.assertEqual(len(lines), 3)  # Header + 2 rows
        self.assertIn("name", lines[0])
        self.assertIn("age", lines[0])
        self.assertIn("John", lines[1])
        self.assertIn("Jane", lines[2])

    def test_render_single_dict(self):
        """Test rendering single dictionary to CSV."""
        data = {"name": "John", "age": 30}
        result = self.renderer.render(data)
        lines = result.decode().strip().split("\n")
        self.assertEqual(len(lines), 2)  # Header + 1 row

    def test_render_empty_list(self):
        """Test rendering empty list."""
        data = []
        result = self.renderer.render(data)
        self.assertEqual(result, b"")

    def test_flatten_nested_dict(self):
        """Test flattening nested dictionaries."""
        data = [{"user": {"name": "John"}}]
        result = self.renderer.render(data)
        self.assertIn(b"user.name", result)

    def test_render_with_datetime(self):
        """Test rendering datetime values."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        data = [{"timestamp": dt}]
        result = self.renderer.render(data)
        self.assertIn(b"2024-01-15T10:30:00", result)

    def test_paginated_response(self):
        """Test rendering paginated response with items."""
        data = {
            "items": [{"id": 1}, {"id": 2}],
            "total": 2,
            "page": 1,
        }
        result = self.renderer.render(data)
        lines = result.decode().strip().split("\n")
        # Should only render the items
        self.assertEqual(len(lines), 3)


# =============================================================================
# HTML Renderer Tests
# =============================================================================


class TestHTMLRenderer(TestCase):
    """Tests for HTMLRenderer."""

    def setUp(self):
        self.renderer = HTMLRenderer()

    def test_media_type(self):
        """Test HTML media type."""
        self.assertEqual(self.renderer.media_type, "text/html")
        self.assertEqual(self.renderer.format, "html")

    def test_render_simple_html(self):
        """Test rendering simple HTML."""
        data = {"key": "value"}
        result = self.renderer.render(data)
        self.assertIn(b"<!DOCTYPE html>", result)
        self.assertIn(b"<html>", result)
        self.assertIn(b"</html>", result)

    def test_render_table_for_list(self):
        """Test rendering list of dicts as table."""
        data = [{"name": "John"}, {"name": "Jane"}]
        result = self.renderer.render(data)
        self.assertIn(b"<table>", result)
        self.assertIn(b"<th>", result)
        self.assertIn(b"<td>", result)

    def test_escape_html(self):
        """Test HTML special characters are escaped."""
        data = {"value": "<script>alert('xss')</script>"}
        result = self.renderer.render(data)
        self.assertNotIn(b"<script>", result)
        self.assertIn(b"&lt;script&gt;", result)


# =============================================================================
# YAML Renderer Tests
# =============================================================================


class TestYAMLRenderer(TestCase):
    """Tests for YAMLRenderer."""

    def setUp(self):
        self.renderer = YAMLRenderer()

    def test_media_type(self):
        """Test YAML media type."""
        self.assertEqual(self.renderer.media_type, "application/yaml")
        self.assertEqual(self.renderer.format, "yaml")

    def test_render_dict(self):
        """Test rendering dictionary to YAML."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")

        data = {"name": "John", "age": 30}
        result = self.renderer.render(data)
        self.assertIn(b"name: John", result)
        self.assertIn(b"age: 30", result)

    def test_render_list(self):
        """Test rendering list to YAML."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")

        data = [1, 2, 3]
        result = self.renderer.render(data)
        self.assertIn(b"- 1", result)
        self.assertIn(b"- 2", result)

    def test_render_datetime(self):
        """Test rendering datetime in YAML."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")

        dt = datetime(2024, 1, 15, 10, 30, 0)
        data = {"timestamp": dt}
        result = self.renderer.render(data)
        self.assertIn(b"2024-01-15T10:30:00", result)


# =============================================================================
# Renderer Registry Tests
# =============================================================================


class TestRendererRegistry(TestCase):
    """Tests for renderer registry functions."""

    def test_renderers_registry(self):
        """Test RENDERERS dictionary contains expected formats."""
        self.assertIn("json", RENDERERS)
        self.assertIn("xml", RENDERERS)
        self.assertIn("csv", RENDERERS)
        self.assertIn("yaml", RENDERERS)
        self.assertIn("html", RENDERERS)
        self.assertIn("msgpack", RENDERERS)

    def test_media_type_map(self):
        """Test MEDIA_TYPE_MAP contains expected mappings."""
        self.assertEqual(MEDIA_TYPE_MAP["application/json"], "json")
        self.assertEqual(MEDIA_TYPE_MAP["application/xml"], "xml")
        self.assertEqual(MEDIA_TYPE_MAP["text/csv"], "csv")
        self.assertEqual(MEDIA_TYPE_MAP["text/html"], "html")

    def test_get_renderer(self):
        """Test get_renderer returns correct renderer."""
        renderer = get_renderer("json")
        self.assertIsInstance(renderer, JSONRenderer)

        renderer = get_renderer("xml")
        self.assertIsInstance(renderer, XMLRenderer)

    def test_get_renderer_unknown(self):
        """Test get_renderer raises for unknown format."""
        with self.assertRaises(ValueError):
            get_renderer("unknown_format")

    def test_get_renderer_for_media_type(self):
        """Test get_renderer_for_media_type."""
        renderer = get_renderer_for_media_type("application/json")
        self.assertIsInstance(renderer, JSONRenderer)

        renderer = get_renderer_for_media_type("text/xml")
        self.assertIsInstance(renderer, XMLRenderer)

    def test_get_renderer_for_media_type_with_charset(self):
        """Test media type with charset parameter."""
        renderer = get_renderer_for_media_type("application/json; charset=utf-8")
        self.assertIsInstance(renderer, JSONRenderer)


# =============================================================================
# JSON Parser Tests
# =============================================================================


class TestJSONParser(TestCase):
    """Tests for JSONParser."""

    def setUp(self):
        self.parser = JSONParser()

    def test_media_type(self):
        """Test JSON parser media type."""
        self.assertEqual(self.parser.media_type, "application/json")

    def test_parse_dict(self):
        """Test parsing JSON dict."""
        data = b'{"key": "value"}'
        result = self.parser.parse(data)
        self.assertEqual(result, {"key": "value"})

    def test_parse_list(self):
        """Test parsing JSON list."""
        data = b'[1, 2, 3]'
        result = self.parser.parse(data)
        self.assertEqual(result, [1, 2, 3])

    def test_parse_empty(self):
        """Test parsing empty data."""
        result = self.parser.parse(b"")
        self.assertIsNone(result)

    def test_parse_invalid(self):
        """Test parsing invalid JSON."""
        with self.assertRaises(ParseError):
            self.parser.parse(b"not valid json")


# =============================================================================
# XML Parser Tests
# =============================================================================


class TestXMLParser(TestCase):
    """Tests for XMLParser."""

    def setUp(self):
        self.parser = XMLParser()

    def test_media_type(self):
        """Test XML parser media type."""
        self.assertEqual(self.parser.media_type, "application/xml")

    def test_parse_simple(self):
        """Test parsing simple XML."""
        data = b"<root><name>John</name></root>"
        result = self.parser.parse(data)
        self.assertIn("root", result)
        self.assertEqual(result["root"]["name"], "John")

    def test_parse_with_attributes(self):
        """Test parsing XML with attributes."""
        data = b'<root id="1"><name>John</name></root>'
        result = self.parser.parse(data)
        self.assertIn("@attributes", result["root"])
        self.assertEqual(result["root"]["@attributes"]["id"], "1")

    def test_parse_empty(self):
        """Test parsing empty data."""
        result = self.parser.parse(b"")
        self.assertIsNone(result)

    def test_parse_invalid(self):
        """Test parsing invalid XML."""
        with self.assertRaises(ParseError):
            self.parser.parse(b"<invalid><unclosed>")


# =============================================================================
# Form Parser Tests
# =============================================================================


class TestFormParser(TestCase):
    """Tests for FormParser."""

    def setUp(self):
        self.parser = FormParser()

    def test_media_type(self):
        """Test form parser media type."""
        self.assertEqual(self.parser.media_type, "application/x-www-form-urlencoded")

    def test_parse_simple(self):
        """Test parsing simple form data."""
        data = b"name=John&age=30"
        result = self.parser.parse(data)
        self.assertEqual(result["name"], "John")
        self.assertEqual(result["age"], "30")

    def test_parse_multiple_values(self):
        """Test parsing multiple values for same key."""
        data = b"color=red&color=blue"
        result = self.parser.parse(data)
        self.assertEqual(result["color"], ["red", "blue"])

    def test_parse_empty(self):
        """Test parsing empty data."""
        result = self.parser.parse(b"")
        self.assertEqual(result, {})


# =============================================================================
# Parser Registry Tests
# =============================================================================


class TestParserRegistry(TestCase):
    """Tests for parser registry functions."""

    def test_parsers_registry(self):
        """Test PARSERS dictionary contains expected formats."""
        self.assertIn("json", PARSERS)
        self.assertIn("xml", PARSERS)
        self.assertIn("form", PARSERS)
        self.assertIn("yaml", PARSERS)
        self.assertIn("msgpack", PARSERS)

    def test_get_parser(self):
        """Test get_parser returns correct parser."""
        parser = get_parser("json")
        self.assertIsInstance(parser, JSONParser)

        parser = get_parser("xml")
        self.assertIsInstance(parser, XMLParser)

    def test_get_parser_unknown(self):
        """Test get_parser raises for unknown format."""
        with self.assertRaises(ValueError):
            get_parser("unknown_format")

    def test_get_parser_for_media_type(self):
        """Test get_parser_for_media_type."""
        parser = get_parser_for_media_type("application/json")
        self.assertIsInstance(parser, JSONParser)

        parser = get_parser_for_media_type("application/xml")
        self.assertIsInstance(parser, XMLParser)

    def test_get_parser_for_multipart(self):
        """Test multipart parser detection."""
        parser = get_parser_for_media_type("multipart/form-data; boundary=----")
        self.assertEqual(parser.format, "multipart")


# =============================================================================
# Content Negotiator Tests
# =============================================================================


class TestContentNegotiator(TestCase):
    """Tests for ContentNegotiator."""

    def setUp(self):
        self.factory = RequestFactory()
        self.negotiator = ContentNegotiator()

    def test_negotiate_query_param(self):
        """Test negotiation via query parameter."""
        request = self.factory.get("/api/users/?format=xml")
        result = self.negotiator.negotiate(request)
        self.assertEqual(result.format, "xml")

    def test_negotiate_url_suffix(self):
        """Test negotiation via URL suffix."""
        request = self.factory.get("/api/users.csv")
        result = self.negotiator.negotiate(request)
        self.assertEqual(result.format, "csv")

    def test_negotiate_accept_header(self):
        """Test negotiation via Accept header."""
        request = self.factory.get(
            "/api/users/",
            HTTP_ACCEPT="application/xml"
        )
        result = self.negotiator.negotiate(request)
        self.assertEqual(result.format, "xml")

    def test_negotiate_accept_wildcard(self):
        """Test negotiation with wildcard Accept."""
        request = self.factory.get(
            "/api/users/",
            HTTP_ACCEPT="*/*"
        )
        result = self.negotiator.negotiate(request)
        # Should return default format
        self.assertEqual(result.format, "json")

    def test_negotiate_accept_with_quality(self):
        """Test negotiation with quality values."""
        request = self.factory.get(
            "/api/users/",
            HTTP_ACCEPT="application/xml;q=0.5, application/json;q=0.9"
        )
        result = self.negotiator.negotiate(request)
        # Should prefer JSON due to higher quality
        self.assertEqual(result.format, "json")

    def test_negotiate_type_wildcard(self):
        """Test negotiation with type wildcard."""
        request = self.factory.get(
            "/api/users/",
            HTTP_ACCEPT="application/*"
        )
        result = self.negotiator.negotiate(request)
        # Should return first matching format
        self.assertIsNotNone(result)

    def test_negotiate_default_format(self):
        """Test default format when no negotiation hints."""
        request = self.factory.get("/api/users/")
        result = self.negotiator.negotiate(request)
        self.assertEqual(result.format, "json")

    def test_negotiated_format_dataclass(self):
        """Test NegotiatedFormat contains expected fields."""
        request = self.factory.get("/api/users/?format=json")
        result = self.negotiator.negotiate(request)
        self.assertEqual(result.format, "json")
        self.assertIsInstance(result.renderer, JSONRenderer)
        self.assertEqual(result.media_type, "application/json")
        self.assertEqual(result.quality, 1.0)

    def test_render_method(self):
        """Test render convenience method."""
        request = self.factory.get("/api/users/?format=json")
        data = {"users": [{"name": "John"}]}
        response = self.negotiator.render(request, data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response["Content-Type"])

    def test_render_format_method(self):
        """Test render_format method."""
        data = {"users": [{"name": "John"}]}
        response = self.negotiator.render_format(data, "json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response["Content-Type"])


# =============================================================================
# NotAcceptable Tests
# =============================================================================


class TestNotAcceptable(TestCase):
    """Tests for NotAcceptable exception."""

    def test_exception_message(self):
        """Test exception contains requested and available formats."""
        error = NotAcceptable("application/pdf", ["json", "xml"])
        self.assertIn("application/pdf", str(error))
        self.assertIn("json", str(error))
        self.assertIn("xml", str(error))

    def test_exception_attributes(self):
        """Test exception has requested and available attributes."""
        error = NotAcceptable("application/pdf", ["json", "xml"])
        self.assertEqual(error.requested, "application/pdf")
        self.assertEqual(error.available, ["json", "xml"])


# =============================================================================
# Convenience Functions Tests
# =============================================================================


class TestConvenienceFunctions(TestCase):
    """Tests for module-level convenience functions."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_negotiate_function(self):
        """Test negotiate() function."""
        request = self.factory.get("/api/users/?format=xml")
        result = negotiate(request)
        self.assertEqual(result.format, "xml")

    def test_render_function(self):
        """Test render() function."""
        request = self.factory.get("/api/users/?format=json")
        data = {"key": "value"}
        response = render(request, data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response["Content-Type"])

    def test_render_format_function(self):
        """Test render_format() function."""
        data = {"key": "value"}
        response = render_format(data, "json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response["Content-Type"])


# =============================================================================
# Decorator Tests
# =============================================================================


class TestRendersDecorator(TestCase):
    """Tests for @renders decorator."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_renders_allowed_format(self):
        """Test view renders allowed format."""
        @renders("json", "xml")
        def my_view(request):
            return {"data": "value"}

        request = self.factory.get("/api/data/?format=json")
        response = my_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response["Content-Type"])

    def test_renders_disallowed_format(self):
        """Test view returns 406 for disallowed format."""
        @renders("json", "xml")
        def my_view(request):
            return {"data": "value"}

        request = self.factory.get("/api/data/?format=csv")
        response = my_view(request)
        self.assertEqual(response.status_code, 406)

    def test_renders_preserves_response(self):
        """Test decorator preserves HttpResponse."""
        @renders("json")
        def my_view(request):
            return HttpResponse("custom", status=201)

        request = self.factory.get("/api/data/")
        response = my_view(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.content, b"custom")


class TestRenderAsDecorator(TestCase):
    """Tests for @render_as decorator."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_render_as_forces_format(self):
        """Test @render_as forces specific format."""
        @render_as("csv")
        def export_view(request):
            return [{"name": "John"}, {"name": "Jane"}]

        request = self.factory.get("/api/export/?format=json")
        response = export_view(request)
        # Should still be CSV despite query param
        self.assertIn("text/csv", response["Content-Type"])

    def test_render_as_preserves_response(self):
        """Test decorator preserves HttpResponse."""
        @render_as("json")
        def my_view(request):
            return HttpResponse("custom", content_type="text/plain")

        request = self.factory.get("/api/data/")
        response = my_view(request)
        self.assertEqual(response.content, b"custom")


class TestContentNegotiatedDecorator(TestCase):
    """Tests for @content_negotiated decorator."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_content_negotiated(self):
        """Test @content_negotiated enables negotiation."""
        @content_negotiated
        def my_view(request):
            return {"data": "value"}

        request = self.factory.get("/api/data/?format=xml")
        response = my_view(request)
        self.assertIn("application/xml", response["Content-Type"])

    def test_content_negotiated_default(self):
        """Test @content_negotiated defaults to JSON."""
        @content_negotiated
        def my_view(request):
            return {"data": "value"}

        request = self.factory.get("/api/data/")
        response = my_view(request)
        self.assertIn("application/json", response["Content-Type"])


# =============================================================================
# NegotiatedResponse Tests
# =============================================================================


class TestNegotiatedResponse(TestCase):
    """Tests for NegotiatedResponse helper."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_with_status(self):
        """Test setting status code."""
        response = NegotiatedResponse({"key": "value"}).with_status(201).render()
        self.assertEqual(response.status_code, 201)

    def test_as_format(self):
        """Test forcing specific format."""
        response = NegotiatedResponse({"key": "value"}).as_format("json").render()
        self.assertIn("application/json", response["Content-Type"])

    def test_render_with_request(self):
        """Test rendering with request negotiation."""
        request = self.factory.get("/api/data/?format=xml")
        response = NegotiatedResponse({"key": "value"}).render(request)
        self.assertIn("application/xml", response["Content-Type"])

    def test_render_without_request(self):
        """Test rendering without request defaults to JSON."""
        response = NegotiatedResponse({"key": "value"}).render()
        self.assertIn("application/json", response["Content-Type"])

    def test_chaining(self):
        """Test method chaining."""
        response = (
            NegotiatedResponse({"key": "value"})
            .with_status(201)
            .as_format("json")
            .render()
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("application/json", response["Content-Type"])


# =============================================================================
# Middleware Tests
# =============================================================================


class TestContentNegotiationMiddleware(TestCase):
    """Tests for ContentNegotiationMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_middleware_sets_negotiated_format(self):
        """Test middleware sets negotiated_format on request."""
        def get_response(request):
            self.assertTrue(hasattr(request, "negotiated_format"))
            return JsonResponse({"key": "value"})

        middleware = ContentNegotiationMiddleware(get_response)
        request = self.factory.get("/api/data/?format=xml")
        middleware(request)

    def test_middleware_transforms_json_response(self):
        """Test middleware transforms JsonResponse to negotiated format."""
        def get_response(request):
            return JsonResponse({"key": "value"})

        middleware = ContentNegotiationMiddleware(get_response)
        request = self.factory.get("/api/data/?format=xml")
        response = middleware(request)
        self.assertIn("application/xml", response["Content-Type"])

    def test_middleware_skips_204_response(self):
        """Test middleware skips 204 No Content responses."""
        def get_response(request):
            return HttpResponse(status=204)

        middleware = ContentNegotiationMiddleware(get_response)
        request = self.factory.get("/api/data/?format=xml")
        response = middleware(request)
        self.assertEqual(response.status_code, 204)

    def test_middleware_skips_non_json_response(self):
        """Test middleware skips non-JSON responses."""
        def get_response(request):
            return HttpResponse("Plain text", content_type="text/plain")

        middleware = ContentNegotiationMiddleware(get_response)
        request = self.factory.get("/api/data/?format=xml")
        response = middleware(request)
        self.assertIn("text/plain", response["Content-Type"])

    def test_middleware_parses_request_body(self):
        """Test middleware parses request body for POST."""
        def get_response(request):
            self.assertTrue(hasattr(request, "parsed_data"))
            return JsonResponse({"status": "ok"})

        middleware = ContentNegotiationMiddleware(get_response)
        request = self.factory.post(
            "/api/data/",
            data=b'{"key": "value"}',
            content_type="application/json",
        )
        middleware(request)


# =============================================================================
# ParseError Tests
# =============================================================================


class TestParseError(TestCase):
    """Tests for ParseError exception."""

    def test_error_message(self):
        """Test error contains message."""
        error = ParseError("Invalid data", "Expected JSON")
        self.assertEqual(str(error), "Invalid data")
        self.assertEqual(error.message, "Invalid data")
        self.assertEqual(error.detail, "Expected JSON")

    def test_error_without_detail(self):
        """Test error without detail."""
        error = ParseError("Invalid data")
        self.assertEqual(str(error), "Invalid data")
        self.assertIsNone(error.detail)
