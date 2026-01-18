"""
Django Matt Pages - Server-Driven SPA System.

A modern alternative to Inertia.js with end-to-end type safety,
hybrid API/Page mode, and seamless codegen integration.

Usage:
    from django_matt.pages import page, PageResponse, redirect_page

    @page("UserList")
    def user_list(request):
        users = User.objects.all()
        return {"users": users}

    @page("UserDetail", title="User Profile")
    def user_detail(request, id: int):
        user = get_object_or_404(User, id=id)
        return {"user": user}

    @page("UserCreate")
    def user_create(request):
        if request.method == "POST":
            form = PageForm(UserCreateInput, request.POST)
            if form.is_valid():
                user = User.objects.create(**form.validated_data)
                return redirect_page(f"/users/{user.id}")

            return PageResponse(
                "UserCreate",
                props={"values": form.data},
                errors=form.errors,
                status=422,
            )

        return PageResponse("UserCreate")

Middleware Setup:
    # settings.py
    MIDDLEWARE = [
        ...
        'django_matt.pages.middleware.PageMiddleware',
    ]

Configuration:
    # settings.py
    PAGES = {
        "root_template": "pages/base.html",  # Custom HTML shell
        "root_id": "app",                     # Mount point ID
        "manifest": "static/manifest.json",   # Vite manifest
    }

Shared Data:
    from django_matt.pages import register_shared_data

    @register_shared_data
    def auth_data(request):
        if request.user.is_authenticated:
            return {"user": {"id": request.user.id, "email": request.user.email}}
        return {"user": None}
"""

# Core response classes
from django_matt.pages.response import (
    PageData,
    PageResponse,
    redirect_page,
)

# Decorators
from django_matt.pages.decorators import (
    page,
    layout,
    hybrid,
)

# Middleware
from django_matt.pages.middleware import (
    RequestMode,
    PageMiddleware,
    AsyncPageMiddleware,
    get_request_mode,
    is_page_request,
    is_api_request,
    is_initial_request,
)

# Context and shared data
from django_matt.pages.context import (
    register_shared_data,
    get_shared_data,
    set_shared_data,
    add_flash_message,
    get_flash_messages,
    flash,
    SharedDataContext,
)

# Forms
from django_matt.pages.forms import (
    PageForm,
    PageFormSet,
    form_errors_to_dict,
)

# Error handling
from django_matt.pages.errors import (
    error_page,
    render_error_page,
    handler400,
    handler403,
    handler404,
    handler500,
)

# Assets
from django_matt.pages.assets import (
    get_asset_version,
    clear_version_cache,
)

# Rendering
from django_matt.pages.rendering import (
    render_page_html,
    render_page_script_tag,
)

# Testing
from django_matt.pages.testing import (
    PageTestClient,
    PageTestMixin,
)


__all__ = [
    # Response
    "PageData",
    "PageResponse",
    "redirect_page",
    # Decorators
    "page",
    "layout",
    "hybrid",
    # Middleware
    "RequestMode",
    "PageMiddleware",
    "AsyncPageMiddleware",
    "get_request_mode",
    "is_page_request",
    "is_api_request",
    "is_initial_request",
    # Context
    "register_shared_data",
    "get_shared_data",
    "set_shared_data",
    "add_flash_message",
    "get_flash_messages",
    "flash",
    "SharedDataContext",
    # Forms
    "PageForm",
    "PageFormSet",
    "form_errors_to_dict",
    # Errors
    "error_page",
    "render_error_page",
    "handler400",
    "handler403",
    "handler404",
    "handler500",
    # Assets
    "get_asset_version",
    "clear_version_cache",
    # Rendering
    "render_page_html",
    "render_page_script_tag",
    # Testing
    "PageTestClient",
    "PageTestMixin",
]
