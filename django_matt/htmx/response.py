# file-length-max: 500
"""
HTMX response utilities.

Provides response classes and helpers for HTMX-specific response headers
like HX-Trigger, HX-Push-Url, HX-Redirect, etc.
"""

from typing import Any

from django.http import HttpResponse
from django.template import loader
from django.template.response import TemplateResponse

import orjson


class HtmxResponse(HttpResponse):
    """
    HTTP response with HTMX header support.

    Provides methods to set HTMX-specific response headers for
    client-side behavior control.

    Usage:
        from django_matt.htmx import HtmxResponse

        def my_view(request):
            response = HtmxResponse("<div>Updated content</div>")
            response.trigger("itemAdded")
            response.push_url("/items/")
            return response

        # Or chain methods:
        return (
            HtmxResponse("<div>Content</div>")
            .trigger("myEvent", {"key": "value"})
            .push_url("/new-url/")
            .reswap("outerHTML")
        )
    """

    def trigger(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        after: str = "receive",
    ) -> "HtmxResponse":
        """
        Trigger a client-side event.

        Args:
            name: Event name to trigger
            params: Optional event parameters (will be JSON encoded)
            after: When to trigger - "receive" (default), "settle", or "swap"

        The event can be listened to with:
            document.body.addEventListener("myEvent", function(evt) {
                console.log(evt.detail);
            });
        """
        header_name = {
            "receive": "HX-Trigger",
            "settle": "HX-Trigger-After-Settle",
            "swap": "HX-Trigger-After-Swap",
        }.get(after, "HX-Trigger")

        # Get existing triggers for this header
        existing = self._get_trigger_dict(header_name)

        # Add new trigger
        if params:
            existing[name] = params
        # If no params, just use the name
        elif name not in existing:
            existing[name] = None

        # Set header
        self._set_trigger_header(header_name, existing)
        return self

    def trigger_after_settle(
        self, name: str, params: dict[str, Any] | None = None
    ) -> "HtmxResponse":
        """Trigger event after settling (DOM updates complete)."""
        return self.trigger(name, params, after="settle")

    def trigger_after_swap(self, name: str, params: dict[str, Any] | None = None) -> "HtmxResponse":
        """Trigger event after swap (content inserted)."""
        return self.trigger(name, params, after="swap")

    def _get_trigger_dict(self, header_name: str) -> dict[str, Any]:
        """Get existing triggers as a dictionary."""
        existing = self.get(header_name)
        if not existing:
            return {}
        try:
            return orjson.loads(existing)
        except (orjson.JSONDecodeError, TypeError):
            # If it's not JSON, treat as single event name
            return {existing: None}

    def _set_trigger_header(self, header_name: str, triggers: dict[str, Any]) -> None:
        """Set the trigger header value."""
        # Filter out None values for cleaner output
        if all(v is None for v in triggers.values()):
            # Just event names, use comma-separated format
            self[header_name] = ", ".join(triggers.keys())
        else:
            # Has params, use JSON format
            self[header_name] = orjson.dumps(triggers).decode()

    def push_url(self, url: str) -> "HtmxResponse":
        """
        Push a new URL into the browser history.

        Args:
            url: The URL to push (or "false" to prevent push)
        """
        self["HX-Push-Url"] = url
        return self

    def replace_url(self, url: str) -> "HtmxResponse":
        """
        Replace the current URL in browser history.

        Args:
            url: The URL to replace with (or "false" to prevent)
        """
        self["HX-Replace-Url"] = url
        return self

    def redirect(self, url: str) -> "HtmxResponse":
        """
        Redirect the browser to a new location.

        This performs a full page redirect, not an HTMX swap.
        """
        self["HX-Redirect"] = url
        return self

    def location(
        self,
        url: str,
        target: str | None = None,
        swap: str | None = None,
        source: str | None = None,
        event: str | None = None,
        handler: str | None = None,
        values: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        select: str | None = None,
    ) -> "HtmxResponse":
        """
        Navigate to a URL with HTMX-style swap.

        More powerful than redirect - allows specifying swap behavior.

        Args:
            url: The URL to navigate to
            target: CSS selector for target element
            swap: Swap strategy (innerHTML, outerHTML, etc.)
            source: Source element for the request
            event: Event that triggered the request
            handler: Path to event handler
            values: Values to submit with the request
            headers: Additional headers
            select: CSS selector to select content from response
        """
        location_data: dict[str, Any] = {"path": url}

        if target:
            location_data["target"] = target
        if swap:
            location_data["swap"] = swap
        if source:
            location_data["source"] = source
        if event:
            location_data["event"] = event
        if handler:
            location_data["handler"] = handler
        if values:
            location_data["values"] = values
        if headers:
            location_data["headers"] = headers
        if select:
            location_data["select"] = select

        self["HX-Location"] = orjson.dumps(location_data).decode()
        return self

    def refresh(self) -> "HtmxResponse":
        """Force a full page refresh."""
        self["HX-Refresh"] = "true"
        return self

    def retarget(self, selector: str) -> "HtmxResponse":
        """
        Change the target element for the swap.

        Args:
            selector: CSS selector for new target
        """
        self["HX-Retarget"] = selector
        return self

    def reselect(self, selector: str) -> "HtmxResponse":
        """
        Select different content from the response.

        Args:
            selector: CSS selector for content to select
        """
        self["HX-Reselect"] = selector
        return self

    def reswap(
        self,
        method: str,
        transition: bool = False,
        settle: int | None = None,
        swap: int | None = None,
        scroll: str | None = None,
        show: str | None = None,
        focus_scroll: bool | None = None,
    ) -> "HtmxResponse":
        """
        Change the swap method.

        Args:
            method: Swap method (innerHTML, outerHTML, beforebegin,
                    afterbegin, beforeend, afterend, delete, none)
            transition: Use view transitions
            settle: Settle delay in ms
            swap: Swap delay in ms
            scroll: Scroll behavior (top, bottom, or element selector)
            show: Show behavior (top, bottom, or element selector)
            focus_scroll: Focus scroll behavior
        """
        value = method

        modifiers = []
        if transition:
            modifiers.append("transition:true")
        if settle is not None:
            modifiers.append(f"settle:{settle}ms")
        if swap is not None:
            modifiers.append(f"swap:{swap}ms")
        if scroll:
            modifiers.append(f"scroll:{scroll}")
        if show:
            modifiers.append(f"show:{show}")
        if focus_scroll is not None:
            modifiers.append(f"focus-scroll:{'true' if focus_scroll else 'false'}")

        if modifiers:
            value = f"{method} {' '.join(modifiers)}"

        self["HX-Reswap"] = value
        return self


class HtmxTemplateResponse(TemplateResponse):
    """
    Template response with HTMX header support.

    Combines Django's TemplateResponse with HtmxResponse methods.

    Usage:
        def my_view(request):
            return (
                HtmxTemplateResponse(request, "partials/item.html", {"item": item})
                .trigger("itemUpdated")
                .push_url(f"/items/{item.id}/")
            )
    """

    def trigger(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        after: str = "receive",
    ) -> "HtmxTemplateResponse":
        """Trigger a client-side event."""
        header_name = {
            "receive": "HX-Trigger",
            "settle": "HX-Trigger-After-Settle",
            "swap": "HX-Trigger-After-Swap",
        }.get(after, "HX-Trigger")

        existing = self._get_trigger_dict(header_name)
        if params:
            existing[name] = params
        elif name not in existing:
            existing[name] = None
        self._set_trigger_header(header_name, existing)
        return self

    def trigger_after_settle(
        self, name: str, params: dict[str, Any] | None = None
    ) -> "HtmxTemplateResponse":
        return self.trigger(name, params, after="settle")

    def trigger_after_swap(
        self, name: str, params: dict[str, Any] | None = None
    ) -> "HtmxTemplateResponse":
        return self.trigger(name, params, after="swap")

    def _get_trigger_dict(self, header_name: str) -> dict[str, Any]:
        existing = self.get(header_name)
        if not existing:
            return {}
        try:
            return orjson.loads(existing)
        except (orjson.JSONDecodeError, TypeError):
            return {existing: None}

    def _set_trigger_header(self, header_name: str, triggers: dict[str, Any]) -> None:
        if all(v is None for v in triggers.values()):
            self[header_name] = ", ".join(triggers.keys())
        else:
            self[header_name] = orjson.dumps(triggers).decode()

    def push_url(self, url: str) -> "HtmxTemplateResponse":
        self["HX-Push-Url"] = url
        return self

    def replace_url(self, url: str) -> "HtmxTemplateResponse":
        self["HX-Replace-Url"] = url
        return self

    def redirect(self, url: str) -> "HtmxTemplateResponse":
        self["HX-Redirect"] = url
        return self

    def refresh(self) -> "HtmxTemplateResponse":
        self["HX-Refresh"] = "true"
        return self

    def retarget(self, selector: str) -> "HtmxTemplateResponse":
        self["HX-Retarget"] = selector
        return self

    def reselect(self, selector: str) -> "HtmxTemplateResponse":
        self["HX-Reselect"] = selector
        return self

    def reswap(self, method: str, **kwargs) -> "HtmxTemplateResponse":
        value = method
        modifiers = []
        if kwargs.get("transition"):
            modifiers.append("transition:true")
        if kwargs.get("settle") is not None:
            modifiers.append(f"settle:{kwargs['settle']}ms")
        if kwargs.get("swap") is not None:
            modifiers.append(f"swap:{kwargs['swap']}ms")
        if kwargs.get("scroll"):
            modifiers.append(f"scroll:{kwargs['scroll']}")
        if kwargs.get("show"):
            modifiers.append(f"show:{kwargs['show']}")
        if modifiers:
            value = f"{method} {' '.join(modifiers)}"
        self["HX-Reswap"] = value
        return self


def render_partial(
    request,
    template_name: str,
    context: dict[str, Any] | None = None,
    content_type: str | None = None,
    status: int = 200,
) -> HtmxResponse:
    """
    Render a template to an HtmxResponse.

    Convenience function for rendering partials with HTMX support.

    Usage:
        def my_view(request):
            return render_partial(
                request,
                "partials/item.html",
                {"item": item}
            ).trigger("itemLoaded")
    """
    template = loader.get_template(template_name)
    content = template.render(context or {}, request)
    response = HtmxResponse(content, content_type=content_type, status=status)
    return response


def trigger_client_event(
    response: HttpResponse,
    name: str,
    params: dict[str, Any] | None = None,
    after: str = "receive",
) -> HttpResponse:
    """
    Add a trigger to any HttpResponse.

    Useful for adding triggers to responses that aren't HtmxResponse.

    Usage:
        response = HttpResponse("OK")
        trigger_client_event(response, "itemSaved", {"id": 123})
    """
    header_name = {
        "receive": "HX-Trigger",
        "settle": "HX-Trigger-After-Settle",
        "swap": "HX-Trigger-After-Swap",
    }.get(after, "HX-Trigger")

    existing = response.get(header_name)
    if existing:
        try:
            triggers = orjson.loads(existing)
        except (orjson.JSONDecodeError, TypeError):
            triggers = {existing: None}
    else:
        triggers = {}

    if params:
        triggers[name] = params
    else:
        triggers[name] = None

    if all(v is None for v in triggers.values()):
        response[header_name] = ", ".join(triggers.keys())
    else:
        response[header_name] = orjson.dumps(triggers).decode()

    return response


class StopPolling(HtmxResponse):
    """
    Response that tells HTMX to stop polling.

    Use this to stop hx-trigger="every Xs" polling.

    Usage:
        @htmx_view
        def poll_status(request):
            status = get_status()
            if status.complete:
                return StopPolling("<div>Complete!</div>")
            return HtmxResponse(f"<div>Progress: {status.progress}%</div>")
    """

    status_code = 286


class HtmxRedirectResponse(HtmxResponse):
    """
    Response that redirects via HTMX.

    Usage:
        return HtmxRedirectResponse("/dashboard/")
    """

    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self["HX-Redirect"] = url


class HtmxRefreshResponse(HtmxResponse):
    """
    Response that forces a full page refresh.

    Usage:
        return HtmxRefreshResponse()
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self["HX-Refresh"] = "true"


__all__ = [
    "HtmxRedirectResponse",
    "HtmxRefreshResponse",
    "HtmxResponse",
    "HtmxTemplateResponse",
    "StopPolling",
    "render_partial",
    "trigger_client_event",
]
