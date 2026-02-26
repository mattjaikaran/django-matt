"""
Base class for third-party service clients.

Wraps httpx.AsyncClient with auth headers, base URL, error handling,
and orjson serialization. Subclass it once per external service.

Usage — Stripe example:

    class StripeService(BaseThirdPartyService):
        base_url = "https://api.stripe.com/v1"

        def _auth_headers(self) -> dict:
            from django.conf import settings
            return {"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"}

        async def create_customer(self, email: str, name: str) -> dict:
            return await self._post("/customers", {"email": email, "name": name})

        async def create_checkout_session(self, price_id: str, success_url: str) -> dict:
            return await self._post("/checkout/sessions", {
                "mode": "payment",
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": 1,
                "success_url": success_url,
            })

Usage — Resend email example:

    class ResendService(BaseThirdPartyService):
        base_url = "https://api.resend.com"

        def _auth_headers(self) -> dict:
            from django.conf import settings
            return {"Authorization": f"Bearer {settings.RESEND_API_KEY}"}

        async def send_email(self, to: str, subject: str, html: str) -> dict:
            return await self._post("/emails", {
                "from": "noreply@yourapp.com",
                "to": to,
                "subject": subject,
                "html": html,
            })
"""

from __future__ import annotations

import logging
from typing import Any

import orjson

try:
    import httpx
except ImportError as exc:
    raise ImportError(
        "httpx is required for BaseThirdPartyService. "
        "Install with: uv add httpx"
    ) from exc


class ThirdPartyServiceError(Exception):
    """HTTP or API-level error from a third-party service."""

    def __init__(self, status: int, message: str, body: dict | None = None):
        self.status = status
        self.message = message
        self.body = body or {}
        super().__init__(f"[{status}] {message}")


class BaseThirdPartyService:
    """
    Async HTTP client base for third-party service integrations.

    Override:
    - ``base_url`` — service root URL
    - ``_auth_headers()`` — authentication headers (Bearer, Basic, apikey, etc.)
    - ``_default_headers()`` — any additional static headers
    - ``_on_error()`` — custom error handling / parsing

    The underlying ``httpx.AsyncClient`` is created lazily and reused
    across calls. Call ``await service.close()`` (or use as async context
    manager) to release it.
    """

    base_url: str = ""
    timeout: float = 30.0

    def __init__(self) -> None:
        self._http: httpx.AsyncClient | None = None
        self._log = logging.getLogger(f"django_matt.services.{self.__class__.__name__}")

    # ------------------------------------------------------------------
    # Override these in subclasses
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        """Return authentication headers. Override in subclass."""
        return {}

    def _default_headers(self) -> dict[str, str]:
        """Return static headers sent with every request."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _on_error(self, status: int, body: dict) -> None:
        """
        Called when the service returns a non-2xx response.

        Override to extract service-specific error messages or codes:

            def _on_error(self, status: int, body: dict) -> None:
                msg = body.get("error", {}).get("message", "Unknown error")
                raise ThirdPartyServiceError(status, msg, body)
        """
        message = (
            body.get("message")
            or body.get("error")
            or body.get("detail")
            or f"HTTP {status}"
        )
        raise ThirdPartyServiceError(status, str(message), body)

    # ------------------------------------------------------------------
    # HTTP client
    # ------------------------------------------------------------------

    def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers={**self._default_headers(), **self._auth_headers()},
                timeout=self.timeout,
            )
        return self._http

    async def close(self) -> None:
        """Close the underlying HTTP client and release connections."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    async def __aenter__(self) -> BaseThirdPartyService:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Core request helpers
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        body: dict | None = None,
        extra_headers: dict | None = None,
    ) -> dict:
        """
        Execute an HTTP request and return the parsed JSON body.

        Raises ``ThirdPartyServiceError`` on non-2xx status.
        """
        client = self._get_client()
        kwargs: dict[str, Any] = {}
        if params:
            kwargs["params"] = params
        if body is not None:
            kwargs["content"] = orjson.dumps(body)
        if extra_headers:
            kwargs["headers"] = extra_headers

        self._log.debug("%s %s%s", method.upper(), self.base_url, path)

        resp = await client.request(method, path, **kwargs)

        raw = resp.content
        parsed: dict = orjson.loads(raw) if raw else {}

        if not resp.is_success:
            self._on_error(resp.status_code, parsed)

        return parsed

    async def _get(self, path: str, *, params: dict | None = None, **kw: Any) -> dict:
        """GET request."""
        return await self._request("GET", path, params=params, **kw)

    async def _post(self, path: str, body: dict | None = None, **kw: Any) -> dict:
        """POST request."""
        return await self._request("POST", path, body=body, **kw)

    async def _put(self, path: str, body: dict | None = None, **kw: Any) -> dict:
        """PUT request."""
        return await self._request("PUT", path, body=body, **kw)

    async def _patch(self, path: str, body: dict | None = None, **kw: Any) -> dict:
        """PATCH request."""
        return await self._request("PATCH", path, body=body, **kw)

    async def _delete(self, path: str, **kw: Any) -> dict:
        """DELETE request."""
        return await self._request("DELETE", path, **kw)
