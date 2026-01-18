"""
Django Matt HTMX Integration.

A comprehensive HTMX integration for Django with:
- Request detection and parsing
- Response helpers with HTMX header support
- View decorators for partial rendering
- Middleware for automatic HTMX handling
- Reusable component patterns

Quick Start:
    # settings.py
    MIDDLEWARE = [
        ...
        'django_matt.htmx.HtmxMiddleware',
    ]

    TEMPLATES = [{
        ...
        'OPTIONS': {
            'context_processors': [
                ...
                'django_matt.htmx.htmx_context_processor',
            ],
        },
    }]

    # views.py
    from django_matt.htmx import htmx_view, HtmxResponse

    @htmx_view(
        template="users/list.html",
        partial_template="users/partials/list.html"
    )
    def user_list(request):
        users = User.objects.all()
        return {"users": users}

    def update_user(request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.name = request.POST.get("name")
        user.save()

        return (
            HtmxResponse(render_to_string("users/partials/user.html", {"user": user}))
            .trigger("userUpdated", {"id": user.id})
            .push_url(f"/users/{user.id}/")
        )

    # templates/users/list.html
    {% load htmx_tags %}
    <html>
    <head>{% htmx_script %}</head>
    <body {% htmx_csrf %}>
        {% include "users/partials/list.html" %}
    </body>
    </html>
"""

# Request utilities
# Component patterns
from django_matt.htmx.components import (
    # Infinite Scroll
    InfiniteScrollConfig,
    # Modals
    ModalConfig,
    OobBuilder,
    # Search
    SearchConfig,
    Toast,
    # Toasts
    ToastConfig,
    add_toast_oob,
    close_modal,
    oob_delete,
    # OOB Swaps
    oob_swap,
    open_modal,
    render_infinite_scroll_page,
    render_search_results,
    show_toast,
)

# Decorators
from django_matt.htmx.decorators import (
    htmx_only,
    htmx_partial,
    htmx_trigger,
    htmx_view,
    require_htmx_target,
    vary_on_htmx,
)

# Middleware
from django_matt.htmx.middleware import (
    AsyncHtmxMiddleware,
    HtmxMiddleware,
    HtmxTemplateContextMiddleware,
    htmx_context_processor,
)
from django_matt.htmx.request import (
    HtmxDetails,
    get_htmx_current_url,
    get_htmx_prompt,
    get_htmx_target,
    get_htmx_trigger,
    get_htmx_trigger_name,
    is_htmx_boosted,
    is_htmx_history_restore,
    is_htmx_request,
)

# Response utilities
from django_matt.htmx.response import (
    HtmxRedirectResponse,
    HtmxRefreshResponse,
    HtmxResponse,
    HtmxTemplateResponse,
    StopPolling,
    render_partial,
    trigger_client_event,
)

__all__ = [
    # Request
    "HtmxDetails",
    "is_htmx_request",
    "is_htmx_boosted",
    "is_htmx_history_restore",
    "get_htmx_target",
    "get_htmx_trigger",
    "get_htmx_trigger_name",
    "get_htmx_prompt",
    "get_htmx_current_url",
    # Response
    "HtmxResponse",
    "HtmxTemplateResponse",
    "render_partial",
    "trigger_client_event",
    "StopPolling",
    "HtmxRedirectResponse",
    "HtmxRefreshResponse",
    # Decorators
    "htmx_view",
    "htmx_only",
    "htmx_partial",
    "htmx_trigger",
    "require_htmx_target",
    "vary_on_htmx",
    # Middleware
    "HtmxMiddleware",
    "AsyncHtmxMiddleware",
    "HtmxTemplateContextMiddleware",
    "htmx_context_processor",
    # Components - Infinite Scroll
    "InfiniteScrollConfig",
    "render_infinite_scroll_page",
    # Components - Search
    "SearchConfig",
    "render_search_results",
    # Components - Modals
    "ModalConfig",
    "open_modal",
    "close_modal",
    # Components - Toasts
    "ToastConfig",
    "Toast",
    "show_toast",
    "add_toast_oob",
    # Components - OOB
    "oob_swap",
    "oob_delete",
    "OobBuilder",
]
