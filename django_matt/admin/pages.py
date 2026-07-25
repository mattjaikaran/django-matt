# file-length-max: 450
"""
Admin page builder for creating custom admin pages.

Provides utilities to create custom admin pages that seamlessly
integrate with Django Unfold's design system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.safestring import mark_safe


@dataclass
class AdminPage:
    """
    A custom admin page.

    Create custom pages that integrate with Django admin and Unfold.

    Example:
        page = AdminPage(
            title="Reports",
            url_name="reports",
            url_path="reports/",
            icon="chart",
        )

        @page.view
        def reports_view(request):
            return page.render(request, {
                "content": "<h2>Sales Report</h2>..."
            })
    """

    title: str
    url_name: str
    url_path: str
    icon: str | None = None
    permission: str | None = None  # e.g., "app.view_model"
    parent: str | None = None  # Parent menu item
    order: int = 100
    view_func: Callable | None = None

    def view(self, func: Callable) -> Callable:
        """Decorator to set the view function for this page."""
        self.view_func = func
        return func

    def get_url_pattern(self):
        """Get the URL pattern for this page."""
        return path(self.url_path, self._wrapped_view, name=self.url_name)

    def _wrapped_view(self, request: HttpRequest) -> HttpResponse:
        """Wrap the view with admin context."""
        if self.view_func is None:
            raise ValueError(f"No view function set for page {self.url_name}")

        # Check permission
        if self.permission and not request.user.has_perm(self.permission):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied

        return self.view_func(request)

    def render(
        self,
        request: HttpRequest,
        context: dict[str, Any] | None = None,
        template: str | None = None,
    ) -> TemplateResponse:
        """
        Render the page with admin context.

        Args:
            request: HTTP request
            context: Additional context
            template: Custom template (optional)

        Returns:
            TemplateResponse with admin context
        """
        context = context or {}

        # Add admin context
        admin_context = {
            "title": self.title,
            "site_header": admin.site.site_header,
            "site_title": admin.site.site_title,
            "has_permission": True,
            "available_apps": admin.site.get_app_list(request),
            "is_popup": False,
            "is_nav_sidebar_enabled": True,
        }
        admin_context.update(context)

        # Use custom template or default
        template = template or "admin/custom_page.html"

        return TemplateResponse(request, template, admin_context)

    def render_content(
        self,
        request: HttpRequest,
        content: str,
        extra_context: dict[str, Any] | None = None,
    ) -> TemplateResponse:
        """
        Render a page with HTML content.

        Args:
            request: HTTP request
            content: HTML content to render
            extra_context: Additional context

        Returns:
            TemplateResponse
        """
        context = extra_context or {}
        context["content_html"] = mark_safe(content)
        return self.render(request, context)


@dataclass
class AdminPageGroup:
    """
    A group of admin pages under a common parent.

    Example:
        reports = AdminPageGroup(
            title="Reports",
            icon="chart",
            pages=[
                AdminPage(title="Sales", url_name="sales", url_path="reports/sales/"),
                AdminPage(title="Users", url_name="users", url_path="reports/users/"),
            ]
        )
    """

    title: str
    icon: str | None = None
    pages: list[AdminPage] = field(default_factory=list)
    order: int = 100

    def add_page(self, page: AdminPage):
        """Add a page to this group."""
        page.parent = self.title
        self.pages.append(page)
        return page

    def get_url_patterns(self):
        """Get URL patterns for all pages in this group."""
        return [page.get_url_pattern() for page in self.pages]


class AdminPageRegistry:
    """
    Registry for custom admin pages.

    Tracks all custom pages and provides URL patterns and menu items.

    Usage:
        from django_matt.admin.pages import pages

        @pages.register("reports/sales/", title="Sales Report")
        def sales_report(request):
            return pages.render(request, "sales", {"data": get_sales_data()})
    """

    def __init__(self):
        self._pages: dict[str, AdminPage] = {}
        self._groups: dict[str, AdminPageGroup] = {}

    def register(
        self,
        url_path: str,
        title: str,
        icon: str | None = None,
        permission: str | None = None,
        group: str | None = None,
        order: int = 100,
    ) -> Callable:
        """
        Decorator to register a custom admin page.

        Args:
            url_path: URL path for the page
            title: Page title
            icon: Icon name
            permission: Required permission
            group: Group name (creates if doesn't exist)
            order: Menu order

        Returns:
            Decorator function
        """

        def decorator(func: Callable) -> Callable:
            url_name = url_path.strip("/").replace("/", "_") or "index"

            page = AdminPage(
                title=title,
                url_name=f"admin_{url_name}",
                url_path=url_path,
                icon=icon,
                permission=permission,
                order=order,
            )
            page.view(func)

            if group:
                if group not in self._groups:
                    self._groups[group] = AdminPageGroup(title=group)
                self._groups[group].add_page(page)
            else:
                self._pages[url_name] = page

            return func

        return decorator

    def create_page(
        self,
        url_path: str,
        title: str,
        **kwargs,
    ) -> AdminPage:
        """Create a page without registering it yet."""
        url_name = url_path.strip("/").replace("/", "_") or "index"
        return AdminPage(
            title=title,
            url_name=f"admin_{url_name}",
            url_path=url_path,
            **kwargs,
        )

    def add_page(self, page: AdminPage):
        """Add an existing page to the registry."""
        self._pages[page.url_name] = page

    def add_group(self, group: AdminPageGroup):
        """Add a page group to the registry."""
        self._groups[group.title] = group

    def get_url_patterns(self) -> list:
        """Get URL patterns for all registered pages."""
        patterns = []

        for page in self._pages.values():
            patterns.append(page.get_url_pattern())

        for group in self._groups.values():
            patterns.extend(group.get_url_patterns())

        return patterns

    def get_menu_items(self, request: HttpRequest) -> list[dict]:
        """Get menu items for the sidebar."""
        items = []

        # Standalone pages
        for page in sorted(self._pages.values(), key=lambda p: p.order):
            if page.permission and not request.user.has_perm(page.permission):
                continue

            items.append(
                {
                    "title": page.title,
                    "url": reverse(f"admin:{page.url_name}"),
                    "icon": page.icon,
                }
            )

        # Groups
        for group in sorted(self._groups.values(), key=lambda g: g.order):
            children = []
            for page in sorted(group.pages, key=lambda p: p.order):
                if page.permission and not request.user.has_perm(page.permission):
                    continue
                children.append(
                    {
                        "title": page.title,
                        "url": reverse(f"admin:{page.url_name}"),
                        "icon": page.icon,
                    }
                )

            if children:
                items.append(
                    {
                        "title": group.title,
                        "icon": group.icon,
                        "children": children,
                    }
                )

        return items

    def render(
        self,
        request: HttpRequest,
        page_name: str,
        context: dict[str, Any] | None = None,
    ) -> TemplateResponse:
        """
        Render a registered page by name.

        Args:
            request: HTTP request
            page_name: Page URL name
            context: Additional context

        Returns:
            TemplateResponse
        """
        page = self._pages.get(page_name)
        if not page:
            # Search in groups
            for group in self._groups.values():
                for p in group.pages:
                    if p.url_name == page_name or p.url_name == f"admin_{page_name}":
                        page = p
                        break

        if not page:
            raise ValueError(f"Page not found: {page_name}")

        return page.render(request, context)


# Global registry instance
pages = AdminPageRegistry()


def get_custom_page_template() -> str:
    """
    Get a custom admin page template.

    This template extends Unfold's admin/base_site.html for custom pages.
    """
    return """
{% extends "admin/base_site.html" %}
{% load i18n %}

{% block breadcrumbs %}
<div class="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 mb-6">
    <a href="{% url 'admin:index' %}" class="hover:text-primary-600 dark:hover:text-primary-400">{% trans "Home" %}</a>
    <span>/</span>
    <span class="text-gray-900 dark:text-white">{{ title }}</span>
</div>
{% endblock %}

{% block content %}
<div class="custom-admin-page">
    {% if content_html %}
        {{ content_html }}
    {% else %}
        {% block page_content %}{% endblock %}
    {% endif %}
</div>
{% endblock %}
"""


def create_page_template_file(path: str = "templates/admin/custom_page.html"):
    """
    Create the custom page template file.

    Args:
        path: Path to create the template at
    """
    from pathlib import Path

    template_path = Path(path)
    template_path.parent.mkdir(parents=True, exist_ok=True)

    with open(template_path, "w") as f:
        f.write(get_custom_page_template())

    return template_path


class PageBuilderMixin:
    """
    Mixin for AdminSite to add custom page support.

    Usage:
        from django.contrib.admin import AdminSite
        from django_matt.admin.pages import PageBuilderMixin

        class MyAdminSite(PageBuilderMixin, AdminSite):
            pass

        admin_site = MyAdminSite(name="myadmin")
    """

    def get_urls(self):
        """Add custom page URLs to admin."""
        urls = super().get_urls()  # type: ignore
        custom_urls = pages.get_url_patterns()
        return custom_urls + urls

    def each_context(self, request: HttpRequest) -> dict[str, Any]:
        """Add custom pages to admin context."""
        context = super().each_context(request)  # type: ignore
        context["custom_pages"] = pages.get_menu_items(request)
        return context


__all__ = [
    "AdminPage",
    "AdminPageGroup",
    "AdminPageRegistry",
    "pages",
    "PageBuilderMixin",
    "get_custom_page_template",
    "create_page_template_file",
]
