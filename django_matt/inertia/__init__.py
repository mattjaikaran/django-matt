"""
Django Matt Inertia.js Adapter.

Server-driven SPA support for React, Vue, and Svelte without building
a REST API.  Implements the Inertia.js protocol with async middleware,
orjson serialization, and SSR support.

Quick Start::

    # settings.py
    MIDDLEWARE = [
        ...
        'django_matt.inertia.InertiaMiddleware',
        'django_matt.inertia.SharedDataMiddleware',
    ]

    INERTIA = {
        "root_template": "base.html",
        "version": "1.0",
    }

    # views.py
    from django_matt.inertia import inertia, lazy, defer

    def dashboard(request):
        return inertia(request, "Dashboard/Index", {
            "stats": get_stats(),
            "notifications": lazy(lambda: get_notifications(request.user)),
            "activity": defer(lambda: get_activity()),
        })

    # Or with decorator:
    from django_matt.inertia import inertia_view

    @inertia_view("Dashboard/Index")
    def dashboard(request):
        return {"stats": get_stats()}

    # templates/base.html
    {% load inertia_tags %}
    <html>
    <head>{% inertia_head %}</head>
    <body>{% inertia %}</body>
    </html>
"""

# Config
from django_matt.inertia.config import InertiaConfig, get_inertia_config

# Middleware
from django_matt.inertia.middleware import AsyncInertiaMiddleware, InertiaMiddleware

# Response
from django_matt.inertia.response import (
    DeferredProp,
    InertiaResponse,
    LazyProp,
    MergeProp,
    defer,
    inertia,
    lazy,
    merge,
)

# Shared data
from django_matt.inertia.share import (
    AsyncSharedDataMiddleware,
    SharedDataMiddleware,
    share,
)

# SSR
from django_matt.inertia.ssr import SSRResponse, render_ssr

# Testing
from django_matt.inertia.testing import (
    InertiaTestMixin,
    get_inertia_page,
    inertia_headers,
)

# Views
from django_matt.inertia.views import InertiaView, inertia_view

__all__ = [
    # Config
    "InertiaConfig",
    "get_inertia_config",
    # Middleware
    "AsyncInertiaMiddleware",
    "InertiaMiddleware",
    # Response
    "DeferredProp",
    "InertiaResponse",
    "LazyProp",
    "MergeProp",
    "defer",
    "inertia",
    "lazy",
    "merge",
    # Shared data
    "AsyncSharedDataMiddleware",
    "SharedDataMiddleware",
    "share",
    # SSR
    "SSRResponse",
    "render_ssr",
    # Testing
    "InertiaTestMixin",
    "get_inertia_page",
    "inertia_headers",
    # Views
    "InertiaView",
    "inertia_view",
]
