# Structured Logging

Django Matt provides structured JSON logging with automatic correlation IDs, request context, and sensitive data redaction.

## Overview

Structured logging outputs logs as JSON, making them easy to parse, search, and analyze with log aggregation tools like ELK, Loki, or Datadog.

**Traditional log:**
```
INFO 2024-01-15 10:30:00 myapp.views - User created successfully
```

**Structured log:**
```json
{
  "level": "INFO",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "logger": "myapp.views",
  "message": "User created successfully",
  "correlation_id": "abc123-def456",
  "request_id": "req-789",
  "user_id": "42",
  "extra": {
    "user_email": "new@example.com",
    "plan": "premium"
  }
}
```

## Configuration

### Basic Configuration

```python
# settings.py

DJANGO_MATT_LOGGING = {
    # Enable/disable structured logging
    "ENABLED": True,

    # Log format: json, pretty, or text
    "FORMAT": "json",

    # Log level
    "LEVEL": "INFO",

    # Include fields
    "INCLUDE_TIMESTAMP": True,
    "INCLUDE_CORRELATION_ID": True,
    "INCLUDE_REQUEST_ID": True,
    "INCLUDE_USER": True,
    "INCLUDE_HOSTNAME": True,

    # Timestamp format (iso or unix)
    "TIMESTAMP_FORMAT": "iso",

    # Extra fields added to every log
    "EXTRA_FIELDS": {
        "service": "myapp",
        "environment": "production",
    },

    # Loggers to exclude from structured formatting
    "EXCLUDE_LOGGERS": ["django.db.backends"],

    # Sensitive fields to redact
    "SENSITIVE_FIELDS": [
        "password",
        "token",
        "secret",
        "api_key",
        "authorization",
        "credit_card",
    ],
}
```

### Using the Logging Config Generator

The easiest way to configure Django's LOGGING setting:

```python
# settings.py
from django_matt.observability import get_logging_config

# Simple configuration
LOGGING = get_logging_config(format="json", level="INFO")

# With Django loggers
LOGGING = get_logging_config(
    format="json",
    level="INFO",
    include_django=True,  # Include django.* loggers
)
```

### Custom Django LOGGING Configuration

For full control:

```python
# settings.py

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "django_matt.observability.logging.JSONFormatter",
        },
        "pretty": {
            "()": "django_matt.observability.logging.PrettyJSONFormatter",
        },
        "colored": {
            "()": "django_matt.observability.logging.ColoredTextFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "/var/log/myapp/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django_matt": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "myapp": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
```

## Getting a Logger

### Structured Logger

```python
from django_matt.observability import get_logger

logger = get_logger(__name__)

# Simple logging
logger.info("User logged in")
logger.warning("Rate limit approaching")
logger.error("Payment failed")

# With context
logger.info_with_context(
    "Order created",
    order_id=12345,
    customer_id=67890,
    total="99.99",
)

logger.error_with_context(
    "Payment failed",
    order_id=12345,
    error_code="CARD_DECLINED",
    exc_info=True,  # Include traceback
)
```

### Bound Logger

Create a logger bound with default context:

```python
from django_matt.observability import get_logger

base_logger = get_logger(__name__)

# Bind context that will be included in all logs
logger = base_logger.bind(
    order_id=12345,
    customer_id=67890,
)

# These logs will include order_id and customer_id
logger.info("Processing order")
logger.info("Validating inventory")
logger.info("Charging payment")

# Add more context
payment_logger = logger.bind(payment_method="credit_card")
payment_logger.info("Payment initiated")  # Includes all three fields
```

## Log Formatters

### JSONFormatter

Compact JSON, one line per log:

```python
from django_matt.observability import JSONFormatter

formatter = JSONFormatter(
    include_timestamp=True,
    include_correlation_id=True,
    include_request_id=True,
    include_user=True,
    include_hostname=True,
    extra_fields={"service": "myapp"},
    sensitive_fields=["password", "token"],
)
```

**Output:**
```json
{"level":"INFO","logger":"myapp","message":"User created","timestamp":"2024-01-15T10:30:00Z","correlation_id":"abc123","extra":{"user_email":"user@example.com"}}
```

### PrettyJSONFormatter

Indented JSON for development:

```python
from django_matt.observability import PrettyJSONFormatter

formatter = PrettyJSONFormatter()
```

**Output:**
```json
{
  "level": "INFO",
  "logger": "myapp",
  "message": "User created",
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "abc123",
  "extra": {
    "user_email": "user@example.com"
  }
}
```

### ColoredTextFormatter

Human-readable colored output for development:

```python
from django_matt.observability import ColoredTextFormatter

formatter = ColoredTextFormatter()
```

**Output:**
```
INFO     [2024-01-15 10:30:00] [abc123] myapp: User created
WARNING  [2024-01-15 10:30:01] [abc123] myapp: Rate limit warning
ERROR    [2024-01-15 10:30:02] [abc123] myapp: Payment failed
```

## Context Management

### Request and Correlation IDs

The `LoggingMiddleware` automatically sets these, but you can also manage them manually:

```python
from django_matt.observability import (
    set_request_id,
    get_request_id,
    set_correlation_id,
    get_correlation_id,
    set_user_id,
    get_user_id,
    clear_context,
)

# Set context (usually done by middleware)
set_request_id("req-12345")
set_correlation_id("corr-67890")
set_user_id("user-42")

# Get context
request_id = get_request_id()
correlation_id = get_correlation_id()
user_id = get_user_id()

# Clear context (usually done after request)
clear_context()
```

### Propagating Context

When making external calls, include correlation IDs:

```python
import requests
from django_matt.observability import get_correlation_id

def call_external_service(data):
    correlation_id = get_correlation_id()

    response = requests.post(
        "https://api.example.com/endpoint",
        json=data,
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Request-ID": get_request_id(),
        }
    )

    return response.json()
```

### Background Tasks

Preserve context in background tasks:

```python
from django_matt.observability import (
    get_correlation_id,
    set_correlation_id,
    get_logger,
)

logger = get_logger(__name__)

def enqueue_task(task_func, *args, **kwargs):
    # Capture current context
    correlation_id = get_correlation_id()

    def wrapper():
        # Restore context in background task
        set_correlation_id(correlation_id)
        logger.info("Background task started")
        try:
            result = task_func(*args, **kwargs)
            logger.info("Background task completed")
            return result
        except Exception as e:
            logger.error("Background task failed", exc_info=True)
            raise

    return background_queue.enqueue(wrapper)
```

## Sensitive Data Redaction

Sensitive fields are automatically redacted:

```python
logger = get_logger(__name__)

# These fields will be redacted
logger.info(
    "User authentication",
    user_email="user@example.com",
    password="secret123",  # Will become "[REDACTED]"
    api_key="sk_live_xxx",  # Will become "[REDACTED]"
)
```

**Output:**
```json
{
  "level": "INFO",
  "message": "User authentication",
  "extra": {
    "user_email": "user@example.com",
    "password": "[REDACTED]",
    "api_key": "[REDACTED]"
  }
}
```

### Configure Sensitive Fields

```python
DJANGO_MATT_LOGGING = {
    "SENSITIVE_FIELDS": [
        "password",
        "token",
        "secret",
        "api_key",
        "authorization",
        "credit_card",
        "ssn",
        "social_security",
    ],
}
```

## Exception Logging

Log exceptions with full tracebacks:

```python
from django_matt.observability import get_logger

logger = get_logger(__name__)

try:
    risky_operation()
except Exception as e:
    logger.error(
        "Operation failed",
        exc_info=True,  # Include full traceback
        operation="risky_operation",
        input_data=sanitized_data,
    )
    raise
```

**Output:**
```json
{
  "level": "ERROR",
  "message": "Operation failed",
  "exception": {
    "type": "ValueError",
    "message": "Invalid input",
    "traceback": [
      "Traceback (most recent call last):",
      "  File \"myapp/services.py\", line 42, in risky_operation",
      "    validate(data)",
      "ValueError: Invalid input"
    ]
  },
  "extra": {
    "operation": "risky_operation",
    "input_data": {"key": "value"}
  }
}
```

## Performance Logging

Log timing information:

```python
import time
from django_matt.observability import get_logger

logger = get_logger(__name__)

def process_data(data):
    start_time = time.time()

    # Process data...
    result = transform(data)

    duration_ms = (time.time() - start_time) * 1000

    logger.info(
        "Data processed",
        duration_ms=duration_ms,
        input_size=len(data),
        output_size=len(result),
    )

    return result
```

## Log Levels

Use appropriate log levels:

```python
from django_matt.observability import get_logger

logger = get_logger(__name__)

# DEBUG - Detailed information for debugging
logger.debug("Cache lookup", key="user:123", hit=True)

# INFO - Confirmation of expected behavior
logger.info("User logged in", user_id=123)

# WARNING - Unexpected but handled situation
logger.warning("Rate limit approaching", current=95, limit=100)

# ERROR - Error that prevented operation
logger.error("Payment failed", order_id=456, error="CARD_DECLINED")

# CRITICAL - Severe error requiring immediate attention
logger.critical("Database connection lost", host="db.example.com")
```

## Integrating with Log Aggregators

### Datadog

```python
# settings.py
import os

LOGGING = {
    "version": 1,
    "formatters": {
        "json": {
            "()": "django_matt.observability.logging.JSONFormatter",
            "extra_fields": {
                "dd.service": os.environ.get("DD_SERVICE", "myapp"),
                "dd.env": os.environ.get("DD_ENV", "production"),
                "dd.version": os.environ.get("DD_VERSION", "1.0.0"),
            },
        },
    },
    # ... rest of config
}
```

### ELK Stack

Logs in JSON format are ready for Elasticsearch:

```yaml
# filebeat.yml
filebeat.inputs:
  - type: log
    paths:
      - /var/log/myapp/*.log
    json:
      keys_under_root: true
      add_error_key: true
```

### Loki / Grafana

```yaml
# promtail-config.yml
scrape_configs:
  - job_name: django
    static_configs:
      - targets:
          - localhost
        labels:
          job: django-app
          __path__: /var/log/myapp/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            logger: logger
```

## Best Practices

### 1. Use Structured Data

```python
# Good - structured data
logger.info(
    "Order created",
    order_id=order.id,
    customer_id=order.customer_id,
    total=str(order.total),
    items=len(order.items),
)

# Bad - string interpolation
logger.info(f"Order {order.id} created for customer {order.customer_id}")
```

### 2. Include Context

```python
# Good - includes relevant context
logger.error(
    "Payment failed",
    order_id=order.id,
    payment_method=payment.method,
    error_code=error.code,
    error_message=str(error),
)

# Bad - minimal context
logger.error("Payment failed")
```

### 3. Use Bound Loggers

```python
# Good - bind common context once
logger = get_logger(__name__).bind(
    request_id=request_id,
    user_id=user_id,
)
logger.info("Step 1")
logger.info("Step 2")
logger.info("Step 3")

# Bad - repeat context in every log
logger.info("Step 1", request_id=request_id, user_id=user_id)
logger.info("Step 2", request_id=request_id, user_id=user_id)
logger.info("Step 3", request_id=request_id, user_id=user_id)
```

### 4. Don't Log Sensitive Data

```python
# Good - sanitize sensitive data
logger.info(
    "User authenticated",
    user_id=user.id,
    email=user.email,
    # Don't log: password, token, etc.
)

# Bad - logging credentials
logger.info("Login attempt", password=password)  # NEVER do this
```

### 5. Use Correlation IDs

Always include correlation IDs for request tracing:

```python
# Middleware automatically sets correlation_id
# It will be included in all logs during the request
logger.info("Processing request")  # correlation_id included automatically
```

## Testing

Mock logging in tests:

```python
import pytest
from unittest.mock import patch

def test_order_creation_logging():
    with patch("myapp.services.logger") as mock_logger:
        create_order(data)

        mock_logger.info.assert_called_with(
            "Order created",
            order_id=1,
            customer_id=42,
        )
```

Or capture log output:

```python
def test_with_caplog(caplog):
    with caplog.at_level("INFO"):
        create_order(data)

    assert "Order created" in caplog.text
    assert '"order_id":' in caplog.text
```
