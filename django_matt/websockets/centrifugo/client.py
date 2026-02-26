"""
Async HTTP client for the Centrifugo HTTP API v2.

All requests use the single-endpoint format:
    POST <api_url>
    Content-Type: application/json
    Authorization: apikey <key>
    Body: {"method": "<method>", "params": {...}}

Uses httpx.AsyncClient (already a dep via oauth extra) and orjson.

Usage:
    from django_matt.websockets.centrifugo import get_centrifugo_client

    client = get_centrifugo_client()
    await client.publish("chat:room-1", {"text": "hello"})
"""

from __future__ import annotations

import logging
from typing import Any

import orjson

from django_matt.websockets.centrifugo.config import get_centrifugo_config

try:
    import httpx
except ImportError as e:
    raise ImportError(
        "httpx is required for the Centrifugo backend. "
        "Install with: uv add 'django-matt[centrifugo]' or uv add httpx"
    ) from e

logger = logging.getLogger(__name__)


class CentrifugoAPIError(Exception):
    """Raised when Centrifugo returns an error response."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Centrifugo error {code}: {message}")


class CentrifugoClient:
    """
    Async client for the Centrifugo HTTP API.

    Wraps all documented API methods. Each method posts to the single
    /api endpoint using the ``{"method": ..., "params": ...}`` envelope.
    """

    def __init__(self) -> None:
        self._http: httpx.AsyncClient | None = None

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            cfg = get_centrifugo_config()
            self._http = httpx.AsyncClient(
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"apikey {cfg.api_key}",
                },
                timeout=10.0,
            )
        return self._http

    async def _call(self, method: str, params: dict[str, Any] | None = None) -> dict:
        """Execute a single Centrifugo API call."""
        cfg = get_centrifugo_config()
        body = orjson.dumps({"method": method, "params": params or {}})
        http = self._get_http()

        resp = await http.post(cfg.api_url, content=body)
        resp.raise_for_status()

        data = orjson.loads(resp.content)
        error = data.get("error")
        if error:
            raise CentrifugoAPIError(
                code=error.get("code", 0),
                message=error.get("message", "unknown error"),
            )

        return data.get("result", {})

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    # -------------------------------------------------------------------------
    # Publication
    # -------------------------------------------------------------------------

    async def publish(self, channel: str, data: dict) -> dict:
        """Publish a message to a channel."""
        return await self._call("publish", {"channel": channel, "data": data})

    async def broadcast(self, channels: list[str], data: dict) -> dict:
        """Broadcast a message to multiple channels."""
        return await self._call("broadcast", {"channels": channels, "data": data})

    # -------------------------------------------------------------------------
    # Subscription management
    # -------------------------------------------------------------------------

    async def subscribe(self, user: str, channel: str) -> dict:
        """Forcefully subscribe a user to a channel."""
        return await self._call("subscribe", {"user": user, "channel": channel})

    async def unsubscribe(self, user: str, channel: str) -> dict:
        """Forcefully unsubscribe a user from a channel."""
        return await self._call("unsubscribe", {"user": user, "channel": channel})

    # -------------------------------------------------------------------------
    # Connection management
    # -------------------------------------------------------------------------

    async def disconnect(self, user: str) -> dict:
        """Disconnect all connections for a user."""
        return await self._call("disconnect", {"user": user})

    # -------------------------------------------------------------------------
    # Presence
    # -------------------------------------------------------------------------

    async def presence(self, channel: str) -> dict:
        """Get presence information for a channel."""
        return await self._call("presence", {"channel": channel})

    async def presence_stats(self, channel: str) -> dict:
        """Get presence statistics for a channel."""
        return await self._call("presence_stats", {"channel": channel})

    # -------------------------------------------------------------------------
    # History
    # -------------------------------------------------------------------------

    async def history(self, channel: str, limit: int = 0) -> dict:
        """Get message history for a channel."""
        params: dict[str, Any] = {"channel": channel}
        if limit > 0:
            params["limit"] = limit
        return await self._call("history", params)

    async def history_remove(self, channel: str) -> dict:
        """Remove message history for a channel."""
        return await self._call("history_remove", {"channel": channel})

    # -------------------------------------------------------------------------
    # Server info
    # -------------------------------------------------------------------------

    async def channels(self, pattern: str = "") -> dict:
        """List active channels, optionally filtered by pattern."""
        params: dict[str, Any] = {}
        if pattern:
            params["pattern"] = pattern
        return await self._call("channels", params)

    async def info(self) -> dict:
        """Get Centrifugo server info."""
        return await self._call("info", {})


# Global singleton — created once per process
_client: CentrifugoClient | None = None


def get_centrifugo_client() -> CentrifugoClient:
    """Return the global CentrifugoClient singleton."""
    global _client
    if _client is None:
        _client = CentrifugoClient()
    return _client
