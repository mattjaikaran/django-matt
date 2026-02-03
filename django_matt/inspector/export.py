"""
Export utilities for captured requests.

Provides export functionality to various formats like curl, httpie, python requests, and fetch.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from django_matt.inspector.storage import CapturedRequest


ExportFormat = Literal["curl", "httpie", "python", "fetch"]


def export_as_curl(request: "CapturedRequest", include_response: bool = False) -> str:
    """
    Export a captured request as a curl command.

    Args:
        request: The captured request to export
        include_response: Whether to include expected response as a comment

    Returns:
        A curl command string
    """
    parts = ["curl"]

    # Method
    if request.method != "GET":
        parts.append(f"-X {request.method}")

    # Headers
    for header, value in request.request_headers.items():
        # Skip headers that curl handles automatically
        if header.lower() in ("host", "content-length", "connection"):
            continue
        # Escape single quotes in header values
        escaped_value = value.replace("'", "'\\''")
        parts.append(f"-H '{header}: {escaped_value}'")

    # Body
    if request.request_body:
        # Try to format JSON for readability
        try:
            body_obj = json.loads(request.request_body)
            body_str = json.dumps(body_obj)
        except (json.JSONDecodeError, TypeError):
            body_str = request.request_body

        escaped_body = body_str.replace("'", "'\\''")
        parts.append(f"-d '{escaped_body}'")

    # URL
    url = request.full_url or f"http://localhost{request.path}"
    if request.query_string:
        url = f"{url}?{request.query_string}" if "?" not in url else url
    parts.append(f"'{url}'")

    result = " \\\n  ".join(parts)

    if include_response and request.response_body:
        result += f"\n\n# Expected response (status {request.response_status}):\n# "
        result += request.response_body[:500].replace("\n", "\n# ")
        if len(request.response_body) > 500:
            result += "\n# ... [truncated]"

    return result


def export_as_httpie(request: "CapturedRequest", include_response: bool = False) -> str:
    """
    Export a captured request as an HTTPie command.

    Args:
        request: The captured request to export
        include_response: Whether to include expected response as a comment

    Returns:
        An HTTPie command string
    """
    parts = ["http"]

    # Method and URL
    url = request.full_url or f"http://localhost{request.path}"
    if request.query_string and "?" not in url:
        url = f"{url}?{request.query_string}"
    parts.append(request.method)
    parts.append(f"'{url}'")

    # Headers
    for header, value in request.request_headers.items():
        # Skip headers that httpie handles automatically
        if header.lower() in ("host", "content-length", "connection", "content-type"):
            continue
        escaped_value = value.replace("'", "'\\''")
        parts.append(f"'{header}:{escaped_value}'")

    # Body (as JSON fields if possible)
    if request.request_body:
        try:
            body_obj = json.loads(request.request_body)
            if isinstance(body_obj, dict):
                for key, value in body_obj.items():
                    if isinstance(value, str):
                        escaped_value = value.replace("'", "'\\''")
                        parts.append(f"{key}='{escaped_value}'")
                    else:
                        parts.append(f"{key}:={json.dumps(value)}")
            else:
                # Non-dict JSON, use raw body
                parts.insert(1, "--raw")
                parts.append(f"'{request.request_body}'")
        except (json.JSONDecodeError, TypeError):
            # Raw body
            parts.insert(1, "--raw")
            escaped_body = request.request_body.replace("'", "'\\''")
            parts.append(f"'{escaped_body}'")

    result = " \\\n  ".join(parts)

    if include_response and request.response_body:
        result += f"\n\n# Expected response (status {request.response_status}):\n# "
        result += request.response_body[:500].replace("\n", "\n# ")
        if len(request.response_body) > 500:
            result += "\n# ... [truncated]"

    return result


def export_as_python(request: "CapturedRequest", include_response: bool = False) -> str:
    """
    Export a captured request as Python requests code.

    Args:
        request: The captured request to export
        include_response: Whether to include expected response as a comment

    Returns:
        Python code string using the requests library
    """
    lines = ["import requests", ""]

    # URL
    url = request.full_url or f"http://localhost{request.path}"
    lines.append(f'url = "{url}"')

    # Headers
    if request.request_headers:
        headers_dict = {
            k: v
            for k, v in request.request_headers.items()
            if k.lower() not in ("host", "content-length", "connection")
        }
        if headers_dict:
            lines.append(f"headers = {json.dumps(headers_dict, indent=4)}")
        else:
            headers_dict = None
    else:
        headers_dict = None

    # Query params
    if request.query_string:
        params = {}
        for param in request.query_string.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value
        if params:
            lines.append(f"params = {json.dumps(params, indent=4)}")
    else:
        params = None

    # Body
    body_var = None
    if request.request_body:
        try:
            body_obj = json.loads(request.request_body)
            lines.append(f"json_data = {json.dumps(body_obj, indent=4)}")
            body_var = "json=json_data"
        except (json.JSONDecodeError, TypeError):
            lines.append(f'data = """{request.request_body}"""')
            body_var = "data=data"

    # Make the request
    lines.append("")
    method = request.method.lower()

    args = ["url"]
    if headers_dict:
        args.append("headers=headers")
    if params:
        args.append("params=params")
    if body_var:
        args.append(body_var)

    lines.append(f"response = requests.{method}(")
    for i, arg in enumerate(args):
        comma = "," if i < len(args) - 1 else ""
        lines.append(f"    {arg}{comma}")
    lines.append(")")

    lines.extend(
        [
            "",
            "print(f'Status: {response.status_code}')",
            "print(f'Headers: {dict(response.headers)}')",
            "print(f'Body: {response.text}')",
        ]
    )

    result = "\n".join(lines)

    if include_response and request.response_body:
        result += f'\n\n# Expected response (status {request.response_status}):\n# """\n# '
        result += request.response_body[:500].replace("\n", "\n# ")
        if len(request.response_body) > 500:
            result += "\n# ... [truncated]"
        result += '\n# """'

    return result


def export_as_fetch(request: "CapturedRequest", include_response: bool = False) -> str:
    """
    Export a captured request as JavaScript fetch code.

    Args:
        request: The captured request to export
        include_response: Whether to include expected response as a comment

    Returns:
        JavaScript code string using fetch API
    """
    lines = []

    # URL
    url = request.full_url or f"http://localhost{request.path}"
    lines.append(f'const url = "{url}";')

    # Options object
    lines.append("")
    lines.append("const options = {")
    lines.append(f'  method: "{request.method}",')

    # Headers
    if request.request_headers:
        headers_dict = {
            k: v
            for k, v in request.request_headers.items()
            if k.lower() not in ("host", "content-length", "connection")
        }
        if headers_dict:
            lines.append("  headers: {")
            for i, (key, value) in enumerate(headers_dict.items()):
                comma = "," if i < len(headers_dict) - 1 else ""
                escaped_value = value.replace('"', '\\"')
                lines.append(f'    "{key}": "{escaped_value}"{comma}')
            lines.append("  },")

    # Body
    if request.request_body:
        try:
            body_obj = json.loads(request.request_body)
            body_str = json.dumps(body_obj)
            lines.append(f"  body: JSON.stringify({body_str}),")
        except (json.JSONDecodeError, TypeError):
            escaped_body = request.request_body.replace('"', '\\"').replace("\n", "\\n")
            lines.append(f'  body: "{escaped_body}",')

    lines.append("};")

    # Fetch call
    lines.extend(
        [
            "",
            "fetch(url, options)",
            "  .then(response => {",
            "    console.log('Status:', response.status);",
            "    return response.json();",
            "  })",
            "  .then(data => {",
            "    console.log('Data:', data);",
            "  })",
            "  .catch(error => {",
            "    console.error('Error:', error);",
            "  });",
        ]
    )

    result = "\n".join(lines)

    if include_response and request.response_body:
        result += f"\n\n// Expected response (status {request.response_status}):\n// "
        result += request.response_body[:500].replace("\n", "\n// ")
        if len(request.response_body) > 500:
            result += "\n// ... [truncated]"

    return result


def export_request(
    request: "CapturedRequest",
    format: ExportFormat = "curl",
    include_response: bool = False,
) -> str:
    """
    Export a captured request to the specified format.

    Args:
        request: The captured request to export
        format: The export format (curl, httpie, python, fetch)
        include_response: Whether to include expected response as a comment

    Returns:
        Exported request string in the specified format

    Raises:
        ValueError: If the format is not supported
    """
    exporters = {
        "curl": export_as_curl,
        "httpie": export_as_httpie,
        "python": export_as_python,
        "fetch": export_as_fetch,
    }

    if format not in exporters:
        raise ValueError(f"Unsupported export format: {format}. Supported: {list(exporters.keys())}")

    return exporters[format](request, include_response)


__all__ = [
    "ExportFormat",
    "export_as_curl",
    "export_as_httpie",
    "export_as_python",
    "export_as_fetch",
    "export_request",
]
