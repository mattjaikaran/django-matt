"""
Inertia.js response utilities.

Provides the core ``inertia()`` response function, ``InertiaResponse``,
and prop wrappers (``lazy``, ``defer``, ``merge``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template import loader

import orjson

from django_matt.inertia.config import get_inertia_config

# ---------------------------------------------------------------------------
# Prop wrappers
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class LazyProp:
    """Prop evaluated only when explicitly requested in a partial reload."""

    callable: Callable[[], Any]

    def resolve(self) -> Any:
        return self.callable()


@dataclass(slots=True)
class DeferredProp:
    """Prop loaded after the initial page render (client fetches separately)."""

    callable: Callable[[], Any]
    group: str = "default"

    def resolve(self) -> Any:
        return self.callable()


@dataclass(slots=True)
class MergeProp:
    """Prop deep-merged with existing data on the client."""

    data: Any


def lazy(callable: Callable[[], Any]) -> LazyProp:
    """Mark a prop as lazy-evaluated (only included when specifically requested)."""
    return LazyProp(callable=callable)


def defer(callable: Callable[[], Any], group: str = "default") -> DeferredProp:
    """Mark a prop as deferred (loaded after initial page render)."""
    return DeferredProp(callable=callable, group=group)


def merge(data: Any) -> MergeProp:
    """Mark a prop for deep-merge with existing client data."""
    return MergeProp(data=data)


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _resolve_version(config: Any) -> str:
    """Return the current asset version as a string."""
    version = config.version
    if version is None:
        return ""
    if callable(version):
        return str(version())
    return str(version)


def _resolve_props(
    props: dict[str, Any],
    partial_component: str | None,
    component: str,
    partial_data: list[str] | None,
) -> dict[str, Any]:
    """Resolve prop wrappers according to Inertia partial-reload rules."""
    resolved: dict[str, Any] = {}

    is_partial = partial_component == component and partial_data is not None

    for key, value in props.items():
        if isinstance(value, LazyProp):
            # Lazy props only included when explicitly requested
            if is_partial and key in partial_data:
                resolved[key] = value.resolve()
            # Otherwise skip
            continue

        if isinstance(value, DeferredProp):
            if is_partial and key in partial_data:
                resolved[key] = value.resolve()
            elif not is_partial:
                # On full page load, skip deferred props (client fetches later)
                continue
            continue

        if isinstance(value, MergeProp):
            resolved[key] = value.data
            continue

        # Regular prop
        if is_partial:
            if key in partial_data:
                resolved[key] = value() if callable(value) else value
        else:
            resolved[key] = value() if callable(value) else value

    return resolved


def _build_page_data(
    request: HttpRequest,
    component: str,
    props: dict[str, Any],
    config: Any,
) -> dict[str, Any]:
    """Build the Inertia page object."""
    partial_component = request.headers.get("X-Inertia-Partial-Component")
    partial_data_header = request.headers.get("X-Inertia-Partial-Data")
    partial_data = partial_data_header.split(",") if partial_data_header else None

    # Merge shared data
    shared: dict[str, Any] = getattr(request, "_inertia_shared", {})
    merged_props = {**shared, **props}

    resolved = _resolve_props(merged_props, partial_component, component, partial_data)

    # Collect deferred groups for the client
    deferred_groups: dict[str, list[str]] = {}
    if not (partial_component == component and partial_data is not None):
        for key, value in merged_props.items():
            if isinstance(value, DeferredProp):
                deferred_groups.setdefault(value.group, []).append(key)

    page: dict[str, Any] = {
        "component": component,
        "props": resolved,
        "url": request.get_full_path(),
        "version": _resolve_version(config),
    }

    if deferred_groups:
        page["deferredProps"] = deferred_groups

    # Merge props marker for the client
    merge_keys = [k for k, v in merged_props.items() if isinstance(v, MergeProp)]
    if merge_keys:
        page["mergeProps"] = merge_keys

    return page


class InertiaResponse(JsonResponse):
    """JSON response with Inertia protocol headers."""

    def __init__(self, page_data: dict[str, Any], **kwargs: Any) -> None:
        kwargs.setdefault("json_dumps_params", {})
        super().__init__(data=page_data, **kwargs)
        self["X-Inertia"] = "true"
        self["Vary"] = "X-Inertia"
        # Re-encode with orjson for performance
        self.content = orjson.dumps(page_data)
        self["Content-Type"] = "application/json"


def inertia(
    request: HttpRequest,
    component: str,
    props: dict[str, Any] | None = None,
    **kwargs: Any,
) -> HttpResponse:
    """Build an Inertia response.

    If the request has the ``X-Inertia`` header, returns JSON conforming
    to the Inertia protocol.  Otherwise renders the root template with
    the page data embedded in a ``div#app`` data attribute.
    """
    config = get_inertia_config()
    all_props = {**(props or {}), **kwargs}
    page_data = _build_page_data(request, component, all_props, config)

    is_inertia = request.headers.get("X-Inertia") == "true"

    if is_inertia:
        return InertiaResponse(page_data)

    # Full page render — embed page data in the root template
    page_json = orjson.dumps(page_data).decode()

    # Try SSR if enabled
    ssr_head: list[str] = []
    ssr_body: str | None = None
    if config.ssr_enabled:
        from django_matt.inertia.ssr import render_ssr

        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context but called synchronously
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    ssr_result = loop.run_in_executor(
                        pool, lambda: asyncio.run(render_ssr(page_data))
                    )
            else:
                ssr_result = asyncio.run(render_ssr(page_data))
            if ssr_result:
                ssr_head = ssr_result.head
                ssr_body = ssr_result.body
        except Exception:
            # SSR failure falls back to client-side rendering
            pass

    template = loader.get_template(config.root_template)
    context = {
        "page": page_json,
        "page_data": page_data,
        "ssr_head": ssr_head,
        "ssr_body": ssr_body,
    }
    content = template.render(context, request)
    return HttpResponse(content)


__all__ = [
    "DeferredProp",
    "InertiaResponse",
    "LazyProp",
    "MergeProp",
    "defer",
    "inertia",
    "lazy",
    "merge",
]
