"""
HTMX component patterns and helpers.

Provides reusable patterns for common HTMX interactions like
infinite scroll, search with debounce, modals, and toasts.
"""

from dataclasses import dataclass
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.template import loader

from django_matt.htmx.response import HtmxResponse

# =============================================================================
# Infinite Scroll
# =============================================================================


@dataclass
class InfiniteScrollConfig:
    """
    Configuration for infinite scroll component.

    Attributes:
        container_id: ID of the scroll container
        item_template: Template for individual items
        trigger_id: ID of the trigger element (loaded last)
        page_param: Query parameter for page number
        page_size: Items per page
        threshold: Intersection threshold (0-1)
        root_margin: IntersectionObserver root margin
    """

    container_id: str = "scroll-container"
    item_template: str = "partials/item.html"
    trigger_id: str = "infinite-scroll-trigger"
    page_param: str = "page"
    page_size: int = 20
    threshold: float = 0.1
    root_margin: str = "200px"

    def get_trigger_html(
        self,
        url: str,
        page: int,
        has_more: bool = True,
    ) -> str:
        """
        Generate the trigger element HTML.

        Place this at the end of your item list to trigger loading
        of the next page when it becomes visible.
        """
        if not has_more:
            return ""

        next_page = page + 1
        separator = "&" if "?" in url else "?"

        return f'''
        <div id="{self.trigger_id}"
             hx-get="{url}{separator}{self.page_param}={next_page}"
             hx-trigger="intersect once threshold:{self.threshold} root-margin:{self.root_margin}"
             hx-swap="outerHTML"
             hx-indicator="#loading-indicator">
        </div>
        '''


def render_infinite_scroll_page(
    request: HttpRequest,
    items: list[Any],
    item_template: str,
    url: str,
    page: int = 1,
    has_more: bool = True,
    config: InfiniteScrollConfig | None = None,
    extra_context: dict[str, Any] | None = None,
) -> HtmxResponse:
    """
    Render a page of items for infinite scroll.

    Usage:
        def item_list(request):
            page = int(request.GET.get("page", 1))
            items = Item.objects.all()[(page-1)*20:page*20]
            has_more = Item.objects.count() > page * 20

            return render_infinite_scroll_page(
                request,
                items=items,
                item_template="items/partials/item.html",
                url=request.path,
                page=page,
                has_more=has_more,
            )
    """
    config = config or InfiniteScrollConfig()
    template = loader.get_template(item_template)

    context = extra_context or {}
    html_parts = []

    for item in items:
        item_context = {
            **context,
            "item": item,
            "htmx": request.htmx if hasattr(request, "htmx") else None,
        }
        html_parts.append(template.render(item_context, request))

    # Add trigger for next page
    trigger_html = config.get_trigger_html(url, page, has_more)
    html_parts.append(trigger_html)

    return HtmxResponse("".join(html_parts))


# =============================================================================
# Search with Debounce
# =============================================================================


@dataclass
class SearchConfig:
    """
    Configuration for search component.

    Attributes:
        input_id: ID of the search input
        results_id: ID of the results container
        url: URL to send search requests to
        debounce_ms: Debounce delay in milliseconds
        min_length: Minimum input length to trigger search
        param_name: Query parameter name for search term
        indicator_id: ID of loading indicator
    """

    input_id: str = "search-input"
    results_id: str = "search-results"
    url: str = "/search/"
    debounce_ms: int = 300
    min_length: int = 2
    param_name: str = "q"
    indicator_id: str = "search-indicator"

    def get_input_html(
        self,
        placeholder: str = "Search...",
        value: str = "",
        extra_classes: str = "",
    ) -> str:
        """Generate the search input HTML with HTMX attributes."""
        return f'''
        <input type="search"
               id="{self.input_id}"
               name="{self.param_name}"
               value="{value}"
               placeholder="{placeholder}"
               class="{extra_classes}"
               hx-get="{self.url}"
               hx-trigger="input changed delay:{self.debounce_ms}ms, search"
               hx-target="#{self.results_id}"
               hx-indicator="#{self.indicator_id}"
               autocomplete="off">
        '''

    def get_container_html(
        self,
        initial_content: str = "",
        extra_classes: str = "",
    ) -> str:
        """Generate the results container HTML."""
        return f'''
        <div id="{self.results_id}" class="{extra_classes}">
            {initial_content}
        </div>
        <div id="{self.indicator_id}" class="htmx-indicator">
            Loading...
        </div>
        '''


def render_search_results(
    request: HttpRequest,
    results: list[Any],
    result_template: str,
    empty_message: str = "No results found",
    extra_context: dict[str, Any] | None = None,
) -> HtmxResponse:
    """
    Render search results.

    Usage:
        def search(request):
            query = request.GET.get("q", "")
            results = Item.objects.filter(name__icontains=query)[:20]

            return render_search_results(
                request,
                results=results,
                result_template="items/partials/search_result.html",
            )
    """
    if not results:
        return HtmxResponse(f'<div class="empty-results">{empty_message}</div>')

    template = loader.get_template(result_template)
    context = extra_context or {}

    html_parts = []
    for result in results:
        result_context = {**context, "result": result}
        html_parts.append(template.render(result_context, request))

    return HtmxResponse("".join(html_parts))


# =============================================================================
# Modal Dialogs
# =============================================================================


@dataclass
class ModalConfig:
    """
    Configuration for modal dialogs.

    Attributes:
        modal_id: ID of the modal container
        backdrop_id: ID of the backdrop element
        close_on_backdrop: Close modal when clicking backdrop
        close_on_escape: Close modal on Escape key
        animation_class: CSS class for animations
    """

    modal_id: str = "modal"
    backdrop_id: str = "modal-backdrop"
    close_on_backdrop: bool = True
    close_on_escape: bool = True
    animation_class: str = "modal-animate"

    def get_container_html(self) -> str:
        """Generate the modal container HTML."""
        backdrop_close = (
            "hx-on:click=\"htmx.trigger('#modal', 'close')\"" if self.close_on_backdrop else ""
        )

        return f'''
        <div id="{self.backdrop_id}"
             class="modal-backdrop hidden"
             {backdrop_close}>
        </div>
        <div id="{self.modal_id}"
             class="modal hidden {self.animation_class}"
             hx-on:close="this.classList.add('hidden'); document.getElementById('{self.backdrop_id}').classList.add('hidden')">
        </div>
        '''


def open_modal(
    content: str,
    title: str | None = None,
    config: ModalConfig | None = None,
    close_button: bool = True,
) -> HtmxResponse:
    """
    Return response that opens a modal with the given content.

    Usage:
        @htmx_only
        def show_user_modal(request, user_id):
            user = get_object_or_404(User, id=user_id)
            content = render_to_string("users/partials/detail.html", {"user": user})
            return open_modal(content, title=f"User: {user.name}")
    """
    config = config or ModalConfig()

    close_btn = ""
    if close_button:
        close_btn = f"""
        <button type="button"
                class="modal-close"
                hx-on:click="htmx.trigger('#{config.modal_id}', 'close')">
            &times;
        </button>
        """

    title_html = ""
    if title:
        title_html = f'<div class="modal-header"><h2>{title}</h2>{close_btn}</div>'
    elif close_button:
        title_html = f'<div class="modal-header">{close_btn}</div>'

    modal_html = f"""
    {title_html}
    <div class="modal-body">
        {content}
    </div>
    """

    response = HtmxResponse(modal_html)
    response.retarget(f"#{config.modal_id}")
    response.reswap("innerHTML")

    # Trigger show event
    response.trigger("modalOpened")

    # Add script to show modal
    show_script = f"""
    <script>
        document.getElementById('{config.modal_id}').classList.remove('hidden');
        document.getElementById('{config.backdrop_id}').classList.remove('hidden');
    </script>
    """
    response.content = response.content + show_script.encode()

    return response


def close_modal(config: ModalConfig | None = None) -> HtmxResponse:
    """
    Return response that closes the modal.

    Usage:
        def handle_form(request):
            if form.is_valid():
                form.save()
                return close_modal().trigger("itemSaved")
    """
    config = config or ModalConfig()

    response = HtmxResponse("")
    response.trigger("close", after="receive")
    response.retarget(f"#{config.modal_id}")
    return response


# =============================================================================
# Toast Notifications
# =============================================================================


@dataclass
class ToastConfig:
    """
    Configuration for toast notifications.

    Attributes:
        container_id: ID of the toast container
        default_duration: Auto-dismiss duration in ms (0 = no auto-dismiss)
        position: Position class (e.g., "top-right", "bottom-center")
        max_toasts: Maximum visible toasts
    """

    container_id: str = "toast-container"
    default_duration: int = 5000
    position: str = "top-right"
    max_toasts: int = 5

    def get_container_html(self) -> str:
        """Generate the toast container HTML."""
        return f'''
        <div id="{self.container_id}"
             class="toast-container {self.position}"
             hx-swap="afterbegin">
        </div>
        '''


@dataclass
class Toast:
    """
    A toast notification.

    Attributes:
        message: Toast message content
        type: Toast type (success, error, warning, info)
        title: Optional title
        duration: Auto-dismiss duration in ms
        dismissible: Whether user can dismiss
        icon: Optional icon HTML
    """

    message: str
    type: str = "info"
    title: str | None = None
    duration: int = 5000
    dismissible: bool = True
    icon: str | None = None

    def to_html(self, toast_id: str) -> str:
        """Generate the toast HTML."""
        dismiss_btn = ""
        if self.dismissible:
            dismiss_btn = """
            <button type="button"
                    class="toast-dismiss"
                    hx-on:click="this.closest('.toast').remove()">
                &times;
            </button>
            """

        icon_html = ""
        if self.icon:
            icon_html = f'<span class="toast-icon">{self.icon}</span>'

        title_html = ""
        if self.title:
            title_html = f'<div class="toast-title">{self.title}</div>'

        auto_remove = ""
        if self.duration > 0:
            auto_remove = f"""
            <script>
                setTimeout(function() {{
                    var el = document.getElementById('{toast_id}');
                    if (el) el.remove();
                }}, {self.duration});
            </script>
            """

        return f'''
        <div id="{toast_id}"
             class="toast toast-{self.type}"
             role="alert">
            {icon_html}
            <div class="toast-content">
                {title_html}
                <div class="toast-message">{self.message}</div>
            </div>
            {dismiss_btn}
        </div>
        {auto_remove}
        '''


def show_toast(
    message: str,
    type: str = "info",
    title: str | None = None,
    duration: int = 5000,
    config: ToastConfig | None = None,
) -> HtmxResponse:
    """
    Return response that shows a toast notification.

    Can be used with OOB swap to add toast to any response.

    Usage:
        def save_item(request):
            item.save()
            return show_toast("Item saved successfully!", type="success")

        # Or combine with other content:
        def update_item(request):
            item.save()
            response = render_partial(request, "items/partials/item.html", {"item": item})
            add_toast_oob(response, "Updated!", type="success")
            return response
    """
    config = config or ToastConfig()
    import uuid

    toast_id = f"toast-{uuid.uuid4().hex[:8]}"

    toast = Toast(
        message=message,
        type=type,
        title=title,
        duration=duration,
    )

    html = toast.to_html(toast_id)

    response = HtmxResponse(html)
    response.retarget(f"#{config.container_id}")
    response.reswap("afterbegin")

    return response


def add_toast_oob(
    response: HttpResponse,
    message: str,
    type: str = "info",
    title: str | None = None,
    duration: int = 5000,
    config: ToastConfig | None = None,
) -> HttpResponse:
    """
    Add a toast notification as an out-of-band swap.

    This adds the toast to an existing response, allowing you to
    update content AND show a notification.

    Usage:
        def update_item(request):
            item.save()
            response = render(request, "items/partials/item.html", {"item": item})
            add_toast_oob(response, "Item updated!", type="success")
            return response
    """
    config = config or ToastConfig()
    import uuid

    toast_id = f"toast-{uuid.uuid4().hex[:8]}"

    toast = Toast(
        message=message,
        type=type,
        title=title,
        duration=duration,
    )

    # Create OOB swap HTML
    oob_html = f'''
    <div id="{config.container_id}" hx-swap-oob="afterbegin">
        {toast.to_html(toast_id)}
    </div>
    '''

    # Append to response content
    if hasattr(response, "content"):
        response.content = response.content + oob_html.encode()

    return response


# =============================================================================
# Out-of-Band (OOB) Swaps
# =============================================================================


def oob_swap(
    target_id: str,
    content: str,
    swap: str = "innerHTML",
) -> str:
    """
    Generate an out-of-band swap element.

    OOB swaps allow updating multiple elements with a single response.

    Args:
        target_id: ID of target element
        content: HTML content to swap
        swap: Swap strategy (innerHTML, outerHTML, etc.)

    Usage:
        def update_item(request):
            item.save()

            # Main content
            main = render_to_string("items/partials/item.html", {"item": item})

            # OOB: Also update the sidebar count
            sidebar = oob_swap("item-count", f"<span>{Item.objects.count()}</span>")

            return HtmxResponse(main + sidebar)
    """
    strategy = f' hx-swap-oob="{swap}"' if swap != "true" else ' hx-swap-oob="true"'
    return f'<div id="{target_id}"{strategy}>{content}</div>'


def oob_delete(target_id: str) -> str:
    """
    Generate an out-of-band delete element.

    Usage:
        def delete_item(request, item_id):
            Item.objects.filter(id=item_id).delete()
            return HtmxResponse(oob_delete(f"item-{item_id}"))
    """
    return f'<div id="{target_id}" hx-swap-oob="delete"></div>'


class OobBuilder:
    """
    Builder for constructing responses with multiple OOB swaps.

    Usage:
        def complex_update(request):
            return (
                OobBuilder()
                .main("<div>Main content</div>")
                .swap("sidebar", "<ul>...</ul>")
                .swap("header", "<h1>New Title</h1>")
                .delete("old-element")
                .build()
            )
    """

    def __init__(self):
        self._main_content: str = ""
        self._oob_parts: list[str] = []

    def main(self, content: str) -> "OobBuilder":
        """Set the main content."""
        self._main_content = content
        return self

    def swap(
        self,
        target_id: str,
        content: str,
        strategy: str = "innerHTML",
    ) -> "OobBuilder":
        """Add an OOB swap."""
        self._oob_parts.append(oob_swap(target_id, content, strategy))
        return self

    def delete(self, target_id: str) -> "OobBuilder":
        """Add an OOB delete."""
        self._oob_parts.append(oob_delete(target_id))
        return self

    def build(self) -> HtmxResponse:
        """Build the final response."""
        content = self._main_content + "".join(self._oob_parts)
        return HtmxResponse(content)


__all__ = [
    # Infinite Scroll
    "InfiniteScrollConfig",
    "render_infinite_scroll_page",
    # Search
    "SearchConfig",
    "render_search_results",
    # Modals
    "ModalConfig",
    "open_modal",
    "close_modal",
    # Toasts
    "ToastConfig",
    "Toast",
    "show_toast",
    "add_toast_oob",
    # OOB Swaps
    "oob_swap",
    "oob_delete",
    "OobBuilder",
]
