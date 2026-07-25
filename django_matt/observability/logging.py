# file-length-max: 650
"""
Structured JSON logging for Django Matt.

This module provides structured logging with JSON output, correlation IDs,
and integration with various logging backends.

Configuration in settings.py:

    DJANGO_MATT_LOGGING = {
        "ENABLED": True,
        "FORMAT": "json",  # json, text, or pretty
        "LEVEL": "INFO",
        "INCLUDE_TIMESTAMP": True,
        "INCLUDE_CORRELATION_ID": True,
        "INCLUDE_REQUEST_ID": True,
        "INCLUDE_USER": True,
        "INCLUDE_HOSTNAME": True,
        "EXTRA_FIELDS": {},
    }

    # Or use the logging config generator
    LOGGING = get_logging_config(format="json", level="INFO")
"""

import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Optional

from django.conf import settings

import orjson

# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class LoggingConfig:
    """Configuration for structured logging."""

    def __init__(self):
        self._config = getattr(settings, "DJANGO_MATT_LOGGING", {})

    @property
    def enabled(self) -> bool:
        return self._config.get("ENABLED", True)

    @property
    def format(self) -> str:
        return self._config.get("FORMAT", "json")

    @property
    def level(self) -> str:
        return self._config.get("LEVEL", "INFO")

    @property
    def include_timestamp(self) -> bool:
        return self._config.get("INCLUDE_TIMESTAMP", True)

    @property
    def include_correlation_id(self) -> bool:
        return self._config.get("INCLUDE_CORRELATION_ID", True)

    @property
    def include_request_id(self) -> bool:
        return self._config.get("INCLUDE_REQUEST_ID", True)

    @property
    def include_user(self) -> bool:
        return self._config.get("INCLUDE_USER", True)

    @property
    def include_hostname(self) -> bool:
        return self._config.get("INCLUDE_HOSTNAME", True)

    @property
    def timestamp_format(self) -> str:
        return self._config.get("TIMESTAMP_FORMAT", "iso")

    @property
    def extra_fields(self) -> dict[str, Any]:
        return self._config.get("EXTRA_FIELDS", {})

    @property
    def exclude_loggers(self) -> list[str]:
        return self._config.get("EXCLUDE_LOGGERS", [])

    @property
    def sensitive_fields(self) -> list[str]:
        return self._config.get(
            "SENSITIVE_FIELDS",
            ["password", "token", "secret", "api_key", "authorization"],
        )


logging_config = LoggingConfig()


def get_hostname() -> str:
    """Get the current hostname."""
    import socket

    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Formats log records as JSON with configurable fields.
    """

    def __init__(
        self,
        include_timestamp: bool = True,
        include_correlation_id: bool = True,
        include_request_id: bool = True,
        include_user: bool = True,
        include_hostname: bool = True,
        extra_fields: Optional[dict[str, Any]] = None,
        sensitive_fields: Optional[list[str]] = None,
    ):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_correlation_id = include_correlation_id
        self.include_request_id = include_request_id
        self.include_user = include_user
        self.include_hostname = include_hostname
        self.extra_fields = extra_fields or {}
        self.sensitive_fields = sensitive_fields or ["password", "token", "secret"]
        self._hostname = get_hostname() if include_hostname else None

    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize sensitive values."""
        if isinstance(value, dict):
            return {
                k: "[REDACTED]"
                if any(sf in k.lower() for sf in self.sensitive_fields)
                else self._sanitize_value(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self._sanitize_value(v) for v in value]
        return value

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        log_data: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add timestamp
        if self.include_timestamp:
            log_data["timestamp"] = datetime.fromtimestamp(record.created, tz=UTC).isoformat()

        # Add location info
        log_data["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add correlation ID
        if self.include_correlation_id:
            correlation_id = correlation_id_var.get()
            if correlation_id:
                log_data["correlation_id"] = correlation_id

        # Add request ID
        if self.include_request_id:
            request_id = request_id_var.get()
            if request_id:
                log_data["request_id"] = request_id

        # Add user ID
        if self.include_user:
            user_id = user_id_var.get()
            if user_id:
                log_data["user_id"] = user_id

        # Add hostname
        if self.include_hostname and self._hostname:
            log_data["hostname"] = self._hostname

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
                if record.exc_info[2]
                else None,
            }

        # Add extra fields from record
        if hasattr(record, "extra"):
            log_data["extra"] = self._sanitize_value(record.extra)

        # Add any additional attributes on the record
        standard_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "message",
            "extra",
        }
        custom_attrs = {
            k: self._sanitize_value(v)
            for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith("_")
        }
        if custom_attrs:
            log_data["extra"] = {**log_data.get("extra", {}), **custom_attrs}

        # Add static extra fields
        if self.extra_fields:
            log_data["extra"] = {**log_data.get("extra", {}), **self.extra_fields}

        # Serialize to JSON
        return orjson.dumps(log_data, default=str).decode("utf-8")


class PrettyJSONFormatter(JSONFormatter):
    """
    Pretty-printed JSON formatter for development.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as pretty JSON."""
        json_str = super().format(record)

        # Parse and re-format with indentation
        log_data = orjson.loads(json_str)
        return orjson.dumps(log_data, default=str, option=orjson.OPT_INDENT_2).decode()


class ColoredTextFormatter(logging.Formatter):
    """
    Colored text formatter for console output.
    """

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors."""
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Build the log message
        parts = [
            f"{color}{record.levelname:8}{reset}",
            f"[{timestamp}]",
            f"{record.name}:",
            record.getMessage(),
        ]

        # Add correlation ID if present
        correlation_id = correlation_id_var.get()
        if correlation_id:
            parts.insert(2, f"[{correlation_id[:8]}]")

        # Add exception if present
        if record.exc_info:
            parts.append("\n" + "".join(traceback.format_exception(*record.exc_info)))

        return " ".join(parts)


class StructuredLogger(logging.Logger):
    """
    Enhanced logger with structured logging support.
    """

    def __init__(self, name: str, level: int = logging.NOTSET):
        super().__init__(name, level)

    def _log_with_extra(
        self,
        level: int,
        msg: str,
        args: tuple,
        exc_info: Any = None,
        extra: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Log with extra context data."""
        if extra is None:
            extra = {}
        extra_data = {"extra": {**extra, **kwargs}}
        super()._log(level, msg, args, exc_info=exc_info, extra=extra_data)

    def debug_with_context(self, msg: str, **kwargs) -> None:
        """Log debug message with context."""
        self._log_with_extra(logging.DEBUG, msg, (), **kwargs)

    def info_with_context(self, msg: str, **kwargs) -> None:
        """Log info message with context."""
        self._log_with_extra(logging.INFO, msg, (), **kwargs)

    def warning_with_context(self, msg: str, **kwargs) -> None:
        """Log warning message with context."""
        self._log_with_extra(logging.WARNING, msg, (), **kwargs)

    def error_with_context(self, msg: str, exc_info: bool = False, **kwargs) -> None:
        """Log error message with context."""
        self._log_with_extra(logging.ERROR, msg, (), exc_info=exc_info, **kwargs)

    def critical_with_context(self, msg: str, exc_info: bool = True, **kwargs) -> None:
        """Log critical message with context."""
        self._log_with_extra(logging.CRITICAL, msg, (), exc_info=exc_info, **kwargs)

    def bind(self, **kwargs) -> "BoundLogger":
        """Create a bound logger with default context."""
        return BoundLogger(self, kwargs)


class BoundLogger:
    """
    A logger bound with default context values.
    """

    def __init__(self, logger: StructuredLogger, context: dict[str, Any]):
        self._logger = logger
        self._context = context

    def bind(self, **kwargs) -> "BoundLogger":
        """Create a new bound logger with additional context."""
        return BoundLogger(self._logger, {**self._context, **kwargs})

    def debug(self, msg: str, **kwargs) -> None:
        self._logger._log_with_extra(logging.DEBUG, msg, (), **{**self._context, **kwargs})

    def info(self, msg: str, **kwargs) -> None:
        self._logger._log_with_extra(logging.INFO, msg, (), **{**self._context, **kwargs})

    def warning(self, msg: str, **kwargs) -> None:
        self._logger._log_with_extra(logging.WARNING, msg, (), **{**self._context, **kwargs})

    def error(self, msg: str, exc_info: bool = False, **kwargs) -> None:
        self._logger._log_with_extra(
            logging.ERROR, msg, (), exc_info=exc_info, **{**self._context, **kwargs}
        )

    def critical(self, msg: str, exc_info: bool = True, **kwargs) -> None:
        self._logger._log_with_extra(
            logging.CRITICAL, msg, (), exc_info=exc_info, **{**self._context, **kwargs}
        )

    def exception(self, msg: str, **kwargs) -> None:
        self._logger._log_with_extra(
            logging.ERROR, msg, (), exc_info=True, **{**self._context, **kwargs}
        )


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name

    Returns:
        StructuredLogger instance
    """
    logging.setLoggerClass(StructuredLogger)
    logger = logging.getLogger(name)
    logging.setLoggerClass(logging.Logger)

    if not isinstance(logger, StructuredLogger):
        # Wrap existing logger
        return StructuredLogger(name)

    return logger


def configure_logging(
    format: str = "json",
    level: str = "INFO",
    handlers: Optional[list[str]] = None,
) -> None:
    """
    Configure logging for the application.

    Args:
        format: Log format (json, pretty, or text)
        level: Log level
        handlers: List of handler types (console, file)
    """
    # Create formatter
    if format == "json":
        formatter = JSONFormatter(
            include_timestamp=logging_config.include_timestamp,
            include_correlation_id=logging_config.include_correlation_id,
            include_request_id=logging_config.include_request_id,
            include_user=logging_config.include_user,
            include_hostname=logging_config.include_hostname,
            extra_fields=logging_config.extra_fields,
            sensitive_fields=logging_config.sensitive_fields,
        )
    elif format == "pretty":
        formatter = PrettyJSONFormatter(
            include_timestamp=logging_config.include_timestamp,
            include_correlation_id=logging_config.include_correlation_id,
            include_request_id=logging_config.include_request_id,
            include_user=logging_config.include_user,
            include_hostname=logging_config.include_hostname,
            extra_fields=logging_config.extra_fields,
            sensitive_fields=logging_config.sensitive_fields,
        )
    else:
        formatter = ColoredTextFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers = []

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def get_logging_config(
    format: str = "json",
    level: str = "INFO",
    include_django: bool = True,
) -> dict:
    """
    Generate a Django LOGGING configuration dictionary.

    Args:
        format: Log format (json, pretty, or text)
        level: Log level
        include_django: Whether to include Django loggers

    Returns:
        Django LOGGING configuration dictionary

    Example:
        # In settings.py
        from django_matt.observability.logging import get_logging_config

        LOGGING = get_logging_config(format="json", level="INFO")
    """
    formatter_class = "django_matt.observability.logging.JSONFormatter"
    if format == "pretty":
        formatter_class = "django_matt.observability.logging.PrettyJSONFormatter"
    elif format == "text":
        formatter_class = "django_matt.observability.logging.ColoredTextFormatter"

    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": formatter_class,
            },
            "simple": {
                "format": "%(levelname)s %(name)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "structured",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
        "loggers": {
            "django_matt": {
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
        },
    }

    if include_django:
        config["loggers"].update(
            {
                "django": {
                    "handlers": ["console"],
                    "level": level,
                    "propagate": False,
                },
                "django.request": {
                    "handlers": ["console"],
                    "level": level,
                    "propagate": False,
                },
                "django.db.backends": {
                    "handlers": ["console"],
                    "level": "WARNING",
                    "propagate": False,
                },
            }
        )

    return config


# Context management functions
def set_request_id(request_id: str) -> None:
    """Set the request ID for the current context."""
    request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """Get the request ID for the current context."""
    return request_id_var.get()


def set_user_id(user_id: str) -> None:
    """Set the user ID for the current context."""
    user_id_var.set(user_id)


def get_user_id() -> Optional[str]:
    """Get the user ID for the current context."""
    return user_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context."""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get the correlation ID for the current context."""
    return correlation_id_var.get()


def clear_context() -> None:
    """Clear all context variables."""
    request_id_var.set(None)
    user_id_var.set(None)
    correlation_id_var.set(None)


__all__ = [
    "LoggingConfig",
    "logging_config",
    "JSONFormatter",
    "PrettyJSONFormatter",
    "ColoredTextFormatter",
    "StructuredLogger",
    "BoundLogger",
    "get_logger",
    "configure_logging",
    "get_logging_config",
    "set_request_id",
    "get_request_id",
    "set_user_id",
    "get_user_id",
    "set_correlation_id",
    "get_correlation_id",
    "clear_context",
]
