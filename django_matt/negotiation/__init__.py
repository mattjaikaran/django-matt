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
    CSVConfig,
    FormatType,
    HTMLConfig,
    JSONConfig,
    NegotiationConfig,
    XMLConfig,
    YAMLConfig,
    get_negotiation_config,
    negotiation_config,
)

# Decorators
from django_matt.negotiation.decorators import (
    NegotiatedResponse,
    content_negotiated,
    render_as,
    renders,
    with_template,
)

# Middleware
from django_matt.negotiation.middleware import (
    AsyncContentNegotiationMiddleware,
    ContentNegotiationMiddleware,
)

# Negotiator
from django_matt.negotiation.negotiator import (
    ContentNegotiator,
    NegotiatedFormat,
    NotAcceptable,
    get_negotiator,
    negotiate,
    parse,
    render,
    render_format,
)

# Parsers
from django_matt.negotiation.parsers import (
    PARSERS,
    BaseParser,
    FormParser,
    JSONParser,
    MessagePackParser,
    MultiPartParser,
    ParseError,
    XMLParser,
    YAMLParser,
    get_parser,
    get_parser_for_media_type,
    parse_request_body,
)

# Renderers
from django_matt.negotiation.renderers import (
    MEDIA_TYPE_MAP,
    RENDERERS,
    BaseRenderer,
    CSVRenderer,
    HTMLRenderer,
    JSONRenderer,
    MessagePackRenderer,
    XMLRenderer,
    YAMLRenderer,
    get_renderer,
    get_renderer_for_media_type,
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
