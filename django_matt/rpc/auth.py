"""Authentication strategies for RPC clients (Bearer, API key, Basic, composite)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthStrategy(Protocol):
    """Protocol for authentication strategies that modify request headers."""

    def apply(self, headers: dict[str, str]) -> dict[str, str]: ...


class BearerAuth:
    """Authenticate with a Bearer token in the Authorization header."""

    def __init__(self, token: str):
        self.token = token

    def apply(self, headers: dict[str, str]) -> dict[str, str]:
        headers["Authorization"] = f"Bearer {self.token}"
        return headers


class APIKeyAuth:
    """Authenticate with an API key in a custom header."""

    def __init__(self, key: str, header: str = "X-API-Key"):
        self.key = key
        self.header = header

    def apply(self, headers: dict[str, str]) -> dict[str, str]:
        headers[self.header] = self.key
        return headers


class BasicAuth:
    """Authenticate with HTTP Basic Auth (base64 username:password)."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def apply(self, headers: dict[str, str]) -> dict[str, str]:
        import base64

        credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        headers["Authorization"] = f"Basic {credentials}"
        return headers


class CompositeAuth:
    """Combine multiple auth strategies, applying them in sequence."""

    def __init__(self, *strategies: AuthStrategy):
        self.strategies = strategies

    def apply(self, headers: dict[str, str]) -> dict[str, str]:
        for strategy in self.strategies:
            headers = strategy.apply(headers)
        return headers
