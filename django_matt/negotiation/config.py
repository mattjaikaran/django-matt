"""
Content negotiation configuration.

Configuration in settings.py:

    DJANGO_MATT_NEGOTIATION = {
        "DEFAULT_FORMAT": "json",
        "FORMAT_QUERY_PARAM": "format",
        "STRICT_ACCEPT": False,  # Return 406 if format not supported

        # Enabled formats (order matters for priority)
        "FORMATS": ["json", "xml", "csv", "yaml", "msgpack", "html"],

        # Format aliases
        "FORMAT_ALIASES": {
            "javascript": "json",
            "yml": "yaml",
        },

        # Renderer settings
        "JSON": {
            "INDENT": None,  # Pretty print with indent
            "ENSURE_ASCII": False,
        },
        "XML": {
            "ROOT_TAG": "response",
            "ITEM_TAG": "item",
            "DECLARATION": True,
        },
        "CSV": {
            "DELIMITER": ",",
            "INCLUDE_HEADER": True,
        },
        "YAML": {
            "DEFAULT_FLOW_STYLE": False,
            "ALLOW_UNICODE": True,
        },
    }
"""

from dataclasses import dataclass, field
from typing import Literal

from django.conf import settings

FormatType = Literal["json", "xml", "csv", "yaml", "msgpack", "html"]


@dataclass
class JSONConfig:
    """JSON renderer configuration."""

    indent: int | None = None
    ensure_ascii: bool = False
    sort_keys: bool = False


@dataclass
class XMLConfig:
    """XML renderer configuration."""

    root_tag: str = "response"
    item_tag: str = "item"
    declaration: bool = True
    encoding: str = "utf-8"
    pretty_print: bool = False


@dataclass
class CSVConfig:
    """CSV renderer configuration."""

    delimiter: str = ","
    include_header: bool = True
    quoting: int = 0  # csv.QUOTE_MINIMAL


@dataclass
class YAMLConfig:
    """YAML renderer configuration."""

    default_flow_style: bool = False
    allow_unicode: bool = True
    indent: int = 2


@dataclass
class HTMLConfig:
    """HTML renderer configuration."""

    template_name: str | None = None
    base_template: str = "base.html"


@dataclass
class NegotiationConfig:
    """Main content negotiation configuration."""

    default_format: FormatType = "json"
    format_query_param: str = "format"
    strict_accept: bool = False  # Return 406 if format not supported

    # Enabled formats in priority order
    formats: list[FormatType] = field(
        default_factory=lambda: ["json", "xml", "csv", "yaml", "msgpack"]
    )

    # Format aliases (e.g., "yml" -> "yaml")
    format_aliases: dict[str, FormatType] = field(default_factory=dict)

    # Per-format configuration
    json: JSONConfig = field(default_factory=JSONConfig)
    xml: XMLConfig = field(default_factory=XMLConfig)
    csv: CSVConfig = field(default_factory=CSVConfig)
    yaml: YAMLConfig = field(default_factory=YAMLConfig)
    html: HTMLConfig = field(default_factory=HTMLConfig)

    @classmethod
    def from_settings(cls) -> "NegotiationConfig":
        """Load configuration from Django settings."""
        config_dict = getattr(settings, "DJANGO_MATT_NEGOTIATION", {})

        json_dict = config_dict.get("JSON", {})
        json_config = JSONConfig(
            indent=json_dict.get("INDENT"),
            ensure_ascii=json_dict.get("ENSURE_ASCII", False),
            sort_keys=json_dict.get("SORT_KEYS", False),
        )

        xml_dict = config_dict.get("XML", {})
        xml_config = XMLConfig(
            root_tag=xml_dict.get("ROOT_TAG", "response"),
            item_tag=xml_dict.get("ITEM_TAG", "item"),
            declaration=xml_dict.get("DECLARATION", True),
            encoding=xml_dict.get("ENCODING", "utf-8"),
            pretty_print=xml_dict.get("PRETTY_PRINT", False),
        )

        csv_dict = config_dict.get("CSV", {})
        csv_config = CSVConfig(
            delimiter=csv_dict.get("DELIMITER", ","),
            include_header=csv_dict.get("INCLUDE_HEADER", True),
        )

        yaml_dict = config_dict.get("YAML", {})
        yaml_config = YAMLConfig(
            default_flow_style=yaml_dict.get("DEFAULT_FLOW_STYLE", False),
            allow_unicode=yaml_dict.get("ALLOW_UNICODE", True),
            indent=yaml_dict.get("INDENT", 2),
        )

        html_dict = config_dict.get("HTML", {})
        html_config = HTMLConfig(
            template_name=html_dict.get("TEMPLATE_NAME"),
            base_template=html_dict.get("BASE_TEMPLATE", "base.html"),
        )

        return cls(
            default_format=config_dict.get("DEFAULT_FORMAT", "json"),
            format_query_param=config_dict.get("FORMAT_QUERY_PARAM", "format"),
            strict_accept=config_dict.get("STRICT_ACCEPT", False),
            formats=config_dict.get("FORMATS", ["json", "xml", "csv", "yaml", "msgpack"]),
            format_aliases=config_dict.get("FORMAT_ALIASES", {"yml": "yaml", "javascript": "json"}),
            json=json_config,
            xml=xml_config,
            csv=csv_config,
            yaml=yaml_config,
            html=html_config,
        )


# Global config instance (lazy-loaded)
_negotiation_config: NegotiationConfig | None = None


def get_negotiation_config() -> NegotiationConfig:
    """Get the negotiation configuration singleton."""
    global _negotiation_config
    if _negotiation_config is None:
        _negotiation_config = NegotiationConfig.from_settings()
    return _negotiation_config


def negotiation_config() -> NegotiationConfig:
    """Alias for get_negotiation_config()."""
    return get_negotiation_config()
