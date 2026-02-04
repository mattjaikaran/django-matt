"""
Django Matt Interactive Documentation Module.

Provides an interactive API playground and documentation views.

Usage:
    # In your urls.py
    from django_matt.docs import get_docs_urls

    urlpatterns = [
        ...
        path("_matt/", include(get_docs_urls(api))),
    ]

This adds:
    - /_matt/docs/ - Interactive documentation
    - /_matt/docs/playground/ - API playground
    - /_matt/docs/search/ - Search endpoint
"""

from .playground import (
    CodeGenerator,
    PlaygroundRequest,
    PlaygroundSession,
    generate_curl,
    generate_httpie,
    generate_javascript,
    generate_python,
)
from .views import (
    DocsView,
    PlaygroundView,
    docs_view,
    get_docs_urls,
    playground_view,
)

__all__ = [
    # Views
    "DocsView",
    "PlaygroundView",
    "get_docs_urls",
    "docs_view",
    "playground_view",
    # Playground
    "PlaygroundSession",
    "PlaygroundRequest",
    "CodeGenerator",
    "generate_curl",
    "generate_python",
    "generate_javascript",
    "generate_httpie",
]
