"""
Django Matt Content Negotiation - Multi-format API responses.

Supports automatic content negotiation based on:
- Accept header (e.g., Accept: application/xml)
- Query parameter (e.g., ?format=xml)
- URL suffix (e.g., /users.xml)

Supported formats:
- JSON (with orjson/ujson support)
- XML
- CSV
- YAML
- MessagePack
- HTML (template-based)

Configuration in settings.py:

    DJANGO_MATT_NEGOTIATION = {
        "DEFAULT_FORMAT": "json",
        "FORMAT_QUERY_PARAM": "format",
        "STRICT_ACCEPT": False,
        "FORMATS": ["json", "xml", "csv", "yaml", "msgpack"],
    }

Example usage:

    # Using middleware (automatic for all API responses)
    MIDDLEWARE = [
        ...
        'django_matt.negotiation.ContentNegotiationMiddleware',
    ]

    # Using decorators
    from django_matt.negotiation import renders, render_as, content_negotiated

    @renders("json", "xml", "csv")
    def list_users(request):
        return users

    @render_as("csv")
    def export_users(request):
        return users

    # Using the negotiator directly
    from django_matt.negotiation import negotiate, render

    def my_view(request):
        data = {"users": users}
        return render(request, data)

    # Or specify format explicitly
    from django_matt.negotiation import render_format

    def export_view(request):
        return render_format(data, "csv")
"""

# Configuration
from django_matt.negotiation.config import (
    NegotiationConfig,
    JSONConfig,
    XMLConfig,
    CSVConfig,
    YAMLConfig,
    HTMLConfig,
    FormatType,
    get_negotiation_config,
    negotiation_config,
)

# Renderers
from django_matt.negotiation.renderers import (
    BaseRenderer,
    JSONRenderer,
    XMLRenderer,
    CSVRenderer,
    YAMLRenderer,
    MessagePackRenderer,
    HTMLRenderer,
    get_renderer,
    get_renderer_for_media_type,
    RENDERERS,
    MEDIA_TYPE_MAP,
)

# Parsers
from django_matt.negotiation.parsers import (
    BaseParser,
    JSONParser,
    XMLParser,
    FormParser,
    MultiPartParser,
    YAMLParser,
    MessagePackParser,
    ParseError,
    get_parser,
    get_parser_for_media_type,
    parse_request_body,
    PARSERS,
)

# Negotiator
from django_matt.negotiation.negotiator import (
    ContentNegotiator,
    NegotiatedFormat,
    NotAcceptable,
    get_negotiator,
    negotiate,
    render,
    render_format,
    parse,
)

# Middleware
from django_matt.negotiation.middleware import (
    ContentNegotiationMiddleware,
    AsyncContentNegotiationMiddleware,
)

# Decorators
from django_matt.negotiation.decorators import (
    renders,
    render_as,
    content_negotiated,
    with_template,
    NegotiatedResponse,
)

__all__ = [
    # Configuration
    "NegotiationConfig",
    "JSONConfig",
    "XMLConfig",
    "CSVConfig",
    "YAMLConfig",
    "HTMLConfig",
    "FormatType",
    "get_negotiation_config",
    "negotiation_config",
    # Renderers
    "BaseRenderer",
    "JSONRenderer",
    "XMLRenderer",
    "CSVRenderer",
    "YAMLRenderer",
    "MessagePackRenderer",
    "HTMLRenderer",
    "get_renderer",
    "get_renderer_for_media_type",
    "RENDERERS",
    "MEDIA_TYPE_MAP",
    # Parsers
    "BaseParser",
    "JSONParser",
    "XMLParser",
    "FormParser",
    "MultiPartParser",
    "YAMLParser",
    "MessagePackParser",
    "ParseError",
    "get_parser",
    "get_parser_for_media_type",
    "parse_request_body",
    "PARSERS",
    # Negotiator
    "ContentNegotiator",
    "NegotiatedFormat",
    "NotAcceptable",
    "get_negotiator",
    "negotiate",
    "render",
    "render_format",
    "parse",
    # Middleware
    "ContentNegotiationMiddleware",
    "AsyncContentNegotiationMiddleware",
    # Decorators
    "renders",
    "render_as",
    "content_negotiated",
    "with_template",
    "NegotiatedResponse",
]
