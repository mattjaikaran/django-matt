"""
API Playground utilities for Django Matt.

Provides:
- Session management for saved requests
- Code snippet generation for multiple languages
- Request history tracking
"""

import secrets
from dataclasses import dataclass, field
from datetime import datetime

import orjson


@dataclass
class PlaygroundRequest:
    """Represents a saved playground request."""

    id: str
    method: str
    url: str
    headers: dict[str, str]
    body: str | None
    created_at: datetime = field(default_factory=datetime.now)
    name: str | None = None
    description: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
            "name": self.name,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlaygroundRequest":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            method=data["method"],
            url=data["url"],
            headers=data.get("headers", {}),
            body=data.get("body"),
            created_at=datetime.fromisoformat(data["created_at"]),
            name=data.get("name"),
            description=data.get("description"),
        )


@dataclass
class PlaygroundSession:
    """Manages playground session state."""

    id: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    requests: list[PlaygroundRequest] = field(default_factory=list)
    auth_token: str | None = None
    base_url: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def add_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        name: str | None = None,
    ) -> PlaygroundRequest:
        """Add a request to the session history."""
        request = PlaygroundRequest(
            id=secrets.token_urlsafe(8),
            method=method,
            url=url,
            headers=headers or {},
            body=body,
            name=name,
        )
        self.requests.append(request)
        return request

    def get_request(self, request_id: str) -> PlaygroundRequest | None:
        """Get a request by ID."""
        for request in self.requests:
            if request.id == request_id:
                return request
        return None

    def delete_request(self, request_id: str) -> bool:
        """Delete a request by ID."""
        for i, request in enumerate(self.requests):
            if request.id == request_id:
                self.requests.pop(i)
                return True
        return False

    def get_history(self, limit: int = 50) -> list[PlaygroundRequest]:
        """Get request history, most recent first."""
        return sorted(
            self.requests,
            key=lambda r: r.created_at,
            reverse=True,
        )[:limit]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "requests": [r.to_dict() for r in self.requests],
            "auth_token": self.auth_token,
            "base_url": self.base_url,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlaygroundSession":
        """Create from dictionary."""
        session = cls(
            id=data["id"],
            auth_token=data.get("auth_token"),
            base_url=data.get("base_url", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
        session.requests = [PlaygroundRequest.from_dict(r) for r in data.get("requests", [])]
        return session


class CodeGenerator:
    """Generate code snippets for API requests."""

    def __init__(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | dict | None = None,
        auth_token: str | None = None,
    ):
        self.method = method.upper()
        self.url = url
        self.headers = headers or {}
        self.body = body
        self.auth_token = auth_token

        # Add auth header if token provided
        if auth_token and "Authorization" not in self.headers:
            self.headers["Authorization"] = f"Bearer {auth_token}"

    def _format_body(self) -> str | None:
        """Format body as JSON string."""
        if self.body is None:
            return None
        if isinstance(self.body, str):
            return self.body
        return orjson.dumps(self.body, option=orjson.OPT_INDENT_2).decode()

    def curl(self) -> str:
        """Generate cURL command."""
        parts = [f"curl -X {self.method}"]

        # Add headers
        for key, value in self.headers.items():
            parts.append(f'  -H "{key}: {value}"')

        # Add body
        body = self._format_body()
        if body and self.method in ("POST", "PUT", "PATCH"):
            # Escape single quotes in body
            escaped_body = body.replace("'", "'\\''")
            parts.append(f"  -d '{escaped_body}'")

        # Add URL
        parts.append(f'  "{self.url}"')

        return " \\\n".join(parts)

    def python(self) -> str:
        """Generate Python code using httpx."""
        lines = [
            "import httpx",
            "",
        ]

        # Determine if async
        if self.method in ("GET", "DELETE"):
            lines.append(f"response = httpx.{self.method.lower()}(")
        else:
            lines.append(f"response = httpx.{self.method.lower()}(")

        lines.append(f'    "{self.url}",')

        # Add headers
        if self.headers:
            lines.append("    headers={")
            for key, value in self.headers.items():
                lines.append(f'        "{key}": "{value}",')
            lines.append("    },")

        # Add body
        body = self._format_body()
        if body and self.method in ("POST", "PUT", "PATCH"):
            try:
                # Try to parse as JSON for better formatting
                json_body = orjson.loads(body)
                lines.append(f"    json={orjson.dumps(json_body).decode()},")
            except orjson.JSONDecodeError:
                lines.append(f'    content="""{body}""",')

        lines.append(")")
        lines.append("")
        lines.append("print(response.status_code)")
        lines.append("print(response.json())")

        return "\n".join(lines)

    def python_async(self) -> str:
        """Generate async Python code using httpx."""
        lines = [
            "import httpx",
            "",
            "async def make_request():",
            "    async with httpx.AsyncClient() as client:",
        ]

        lines.append(f"        response = await client.{self.method.lower()}(")
        lines.append(f'            "{self.url}",')

        # Add headers
        if self.headers:
            lines.append("            headers={")
            for key, value in self.headers.items():
                lines.append(f'                "{key}": "{value}",')
            lines.append("            },")

        # Add body
        body = self._format_body()
        if body and self.method in ("POST", "PUT", "PATCH"):
            try:
                json_body = orjson.loads(body)
                lines.append(f"            json={orjson.dumps(json_body).decode()},")
            except orjson.JSONDecodeError:
                lines.append(f'            content="""{body}""",')

        lines.append("        )")
        lines.append("        return response.json()")
        lines.append("")
        lines.append("# Run with: asyncio.run(make_request())")

        return "\n".join(lines)

    def javascript(self) -> str:
        """Generate JavaScript code using fetch."""
        lines = [
            f'const response = await fetch("{self.url}", {{',
            f'  method: "{self.method}",',
        ]

        # Add headers
        if self.headers:
            lines.append("  headers: {")
            for key, value in self.headers.items():
                lines.append(f'    "{key}": "{value}",')
            lines.append("  },")

        # Add body
        body = self._format_body()
        if body and self.method in ("POST", "PUT", "PATCH"):
            lines.append(f"  body: JSON.stringify({body}),")

        lines.append("});")
        lines.append("")
        lines.append("const data = await response.json();")
        lines.append("console.log(data);")

        return "\n".join(lines)

    def typescript(self) -> str:
        """Generate TypeScript code with types."""
        lines = [
            "interface ResponseData {",
            "  // Define your response type here",
            "  [key: string]: unknown;",
            "}",
            "",
            f'const response = await fetch("{self.url}", {{',
            f'  method: "{self.method}",',
        ]

        # Add headers
        if self.headers:
            lines.append("  headers: {")
            for key, value in self.headers.items():
                lines.append(f'    "{key}": "{value}",')
            lines.append("  },")

        # Add body
        body = self._format_body()
        if body and self.method in ("POST", "PUT", "PATCH"):
            lines.append(f"  body: JSON.stringify({body}),")

        lines.append("});")
        lines.append("")
        lines.append("const data: ResponseData = await response.json();")
        lines.append("console.log(data);")

        return "\n".join(lines)

    def httpie(self) -> str:
        """Generate HTTPie command."""
        parts = [f"http {self.method} {self.url}"]

        # Add headers
        for key, value in self.headers.items():
            parts.append(f'"{key}:{value}"')

        # Add body (HTTPie uses key=value for JSON)
        body = self._format_body()
        if body and self.method in ("POST", "PUT", "PATCH"):
            try:
                json_body = orjson.loads(body)
                for key, value in json_body.items():
                    if isinstance(value, str):
                        parts.append(f'{key}="{value}"')
                    else:
                        parts.append(f"{key}:={orjson.dumps(value).decode()}")
            except orjson.JSONDecodeError:
                parts.append(f"< echo '{body}'")

        return " \\\n  ".join(parts)

    def swift(self) -> str:
        """Generate Swift code using URLSession."""
        lines = [
            "import Foundation",
            "",
            f'let url = URL(string: "{self.url}")!',
            "var request = URLRequest(url: url)",
            f'request.httpMethod = "{self.method}"',
            "",
        ]

        # Add headers
        for key, value in self.headers.items():
            lines.append(f'request.setValue("{value}", forHTTPHeaderField: "{key}")')

        # Add body
        body = self._format_body()
        if body and self.method in ("POST", "PUT", "PATCH"):
            lines.append("")
            lines.append(f'let body = """{body}"""')
            lines.append("request.httpBody = body.data(using: .utf8)")

        lines.extend(
            [
                "",
                "let (data, response) = try await URLSession.shared.data(for: request)",
                "let json = try JSONSerialization.jsonObject(with: data)",
                "print(json)",
            ]
        )

        return "\n".join(lines)

    def go(self) -> str:
        """Generate Go code using net/http."""
        lines = [
            "package main",
            "",
            "import (",
            '    "bytes"',
            '    "encoding/json"',
            '    "fmt"',
            '    "io"',
            '    "net/http"',
            ")",
            "",
            "func main() {",
        ]

        # Add body
        body = self._format_body()
        if body and self.method in ("POST", "PUT", "PATCH"):
            lines.append(f"    body := []byte(`{body}`)")
            lines.append(
                f'    req, err := http.NewRequest("{self.method}", "{self.url}", bytes.NewBuffer(body))'
            )
        else:
            lines.append(f'    req, err := http.NewRequest("{self.method}", "{self.url}", nil)')

        lines.extend(
            [
                "    if err != nil {",
                "        panic(err)",
                "    }",
                "",
            ]
        )

        # Add headers
        for key, value in self.headers.items():
            lines.append(f'    req.Header.Set("{key}", "{value}")')

        lines.extend(
            [
                "",
                "    client := &http.Client{}",
                "    resp, err := client.Do(req)",
                "    if err != nil {",
                "        panic(err)",
                "    }",
                "    defer resp.Body.Close()",
                "",
                "    body, _ := io.ReadAll(resp.Body)",
                '    fmt.Printf("%s\\n", body)',
                "}",
            ]
        )

        return "\n".join(lines)

    def all(self) -> dict[str, str]:
        """Generate all code snippets."""
        return {
            "curl": self.curl(),
            "python": self.python(),
            "python_async": self.python_async(),
            "javascript": self.javascript(),
            "typescript": self.typescript(),
            "httpie": self.httpie(),
            "swift": self.swift(),
            "go": self.go(),
        }


# Convenience functions
def generate_curl(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: str | dict | None = None,
) -> str:
    """Generate a cURL command."""
    return CodeGenerator(method, url, headers, body).curl()


def generate_python(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: str | dict | None = None,
) -> str:
    """Generate Python code."""
    return CodeGenerator(method, url, headers, body).python()


def generate_javascript(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: str | dict | None = None,
) -> str:
    """Generate JavaScript code."""
    return CodeGenerator(method, url, headers, body).javascript()


def generate_httpie(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: str | dict | None = None,
) -> str:
    """Generate HTTPie command."""
    return CodeGenerator(method, url, headers, body).httpie()
