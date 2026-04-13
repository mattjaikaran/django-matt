"""
Inertia.js server-side rendering.

Calls a Node.js SSR server (e.g. ``@inertiajs/server``) to pre-render
the page on the server for SEO and initial load performance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import orjson

from django_matt.inertia.config import get_inertia_config


@dataclass(slots=True)
class SSRResponse:
    """Result from the SSR server."""

    head: list[str] = field(default_factory=list)
    body: str = ""


async def render_ssr(page_data: dict[str, Any]) -> SSRResponse | None:
    """Call the Inertia SSR server and return rendered HTML.

    Returns ``None`` if the SSR server is unreachable or returns an
    error, allowing graceful fallback to client-side rendering.
    """
    config = get_inertia_config()
    if not config.ssr_enabled:
        return None

    import httpx

    url = f"{config.ssr_url.rstrip('/')}/render"
    payload = orjson.dumps(page_data)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                url,
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
    except (httpx.HTTPError, OSError):
        return None

    data = orjson.loads(response.content)
    return SSRResponse(
        head=data.get("head", []),
        body=data.get("body", ""),
    )


__all__ = [
    "SSRResponse",
    "render_ssr",
]
