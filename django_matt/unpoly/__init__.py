"""
Django Matt Unpoly Integration.

A comprehensive Unpoly integration for Django with:
- Request detection and parsing (X-Up-* headers)
- Response helpers with Unpoly header support
- View decorators for target, layer, and validation control
- Middleware for automatic Unpoly handling
- Template tags for nav and configuration

Quick Start:
    # settings.py
    MIDDLEWARE = [
        ...
        'django_matt.unpoly.UnpolyMiddleware',
    ]

    TEMPLATES = [{
        ...
        'OPTIONS': {
            'context_processors': [
                ...
                'django_matt.unpoly.unpoly_context_processor',
            ],
        },
    }]

    # views.py
    from django_matt.unpoly import UnpolyResponse, up_target

    @up_target(".content")
    def my_view(request):
        if request.up:
            return render(request, "partials/content.html", context)
        return render(request, "full.html", context)

    def update_item(request, item_id):
        item = get_object_or_404(Item, id=item_id)
        item.name = request.POST["name"]
        item.save()

        return (
            UnpolyResponse(render_to_string("partials/item.html", {"item": item}))
            .emit_event("item:updated", id=item.id)
            .clear_cache("/items/*")
        )

    # templates/base.html
    {% load unpoly_tags %}
    <nav>
        {% up_nav %}
            <a href="/" {% up_current "/" %}>Home</a>
        {% end_up_nav %}
    </nav>
    {% up_config %}
"""

# Config
from django_matt.unpoly.config import (
    UnpolyConfig,
    get_unpoly_config,
)

# Decorators
from django_matt.unpoly.decorators import (
    up_fail_target,
    up_layer,
    up_only,
    up_target,
    up_validate,
    vary_on_unpoly,
)

# Middleware
from django_matt.unpoly.middleware import (
    AsyncUnpolyMiddleware,
    UnpolyMiddleware,
    unpoly_context_processor,
)

# Request
from django_matt.unpoly.request import (
    UnpolyDetails,
    get_up_mode,
    get_up_target,
    get_up_validate,
    is_unpoly_request,
)

# Response
from django_matt.unpoly.response import (
    UnpolyResponse,
    up_redirect,
)

__all__ = [
    # Config
    "UnpolyConfig",
    "get_unpoly_config",
    # Request
    "UnpolyDetails",
    "is_unpoly_request",
    "get_up_target",
    "get_up_mode",
    "get_up_validate",
    # Response
    "UnpolyResponse",
    "up_redirect",
    # Decorators
    "up_target",
    "up_layer",
    "up_fail_target",
    "up_only",
    "up_validate",
    "vary_on_unpoly",
    # Middleware
    "UnpolyMiddleware",
    "AsyncUnpolyMiddleware",
    "unpoly_context_processor",
]
