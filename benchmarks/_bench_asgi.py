"""Minimal ASGI app for server backend benchmarks.

Returns a tiny JSON body on GET / so we measure pure server overhead
(socket accept, HTTP parse, worker dispatch, response write) without
Django/ORM/middleware noise. Kept intentionally dependency-free so any
ASGI runner can import it via ``_bench_asgi:app``.
"""

from __future__ import annotations

_BODY = b'{"ok":true,"service":"django-matt-bench"}'
_HEADERS = [
    (b"content-type", b"application/json"),
    (b"content-length", str(len(_BODY)).encode()),
]


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    if scope["type"] != "http":
        return

    await send({"type": "http.response.start", "status": 200, "headers": _HEADERS})
    await send({"type": "http.response.body", "body": _BODY})
