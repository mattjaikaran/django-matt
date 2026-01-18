"""
Configuration utilities for Django Unfold admin theme.

Provides helpers to configure Unfold settings in Django settings.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UnfoldConfig:
    """
    Configuration for Django Unfold admin theme.

    Usage:
        from django_matt.admin.config import UnfoldConfig, configure_unfold

        config = UnfoldConfig(
            site_title="My Admin",
            site_header="My Company Admin",
            show_history=True,
            colors={
                "primary": {
                    "50": "#f0f9ff",
                    "100": "#e0f2fe",
                    ...
                }
            }
        )

        UNFOLD = configure_unfold(config)
    """

    # Site information
    site_title: str = "Django Admin"
    site_header: str = "Django Admin"
    site_url: str = "/"

    # Branding
    site_icon: dict[str, str] | None = None
    site_logo: dict[str, str] | None = None
    site_favicon: str | None = None
    site_symbol: str | None = None

    # Features
    show_history: bool = True
    show_view_on_site: bool = True
    show_languages: bool = True

    # Environment indicator
    environment: str | None = None
    environment_callback: str | None = None

    # Login
    login_redirect_url: str = "/"
    login_image: str | None = None

    # Theme
    theme: str = "dark"  # "dark", "light", or None for system

    # Colors (Tailwind color scale)
    colors: dict[str, dict[str, str]] = field(default_factory=dict)

    # Sidebar
    sidebar_show_all_applications: bool = True
    sidebar_show_search: bool = True
    sidebar_navigation: list[dict[str, Any]] = field(default_factory=list)

    # Tabs for model detail pages
    tabs: list[dict[str, Any]] = field(default_factory=list)

    # Custom styles and scripts
    styles: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to UNFOLD settings dict."""
        settings: dict[str, Any] = {
            "SITE_TITLE": self.site_title,
            "SITE_HEADER": self.site_header,
            "SITE_URL": self.site_url,
            "SHOW_HISTORY": self.show_history,
            "SHOW_VIEW_ON_SITE": self.show_view_on_site,
            "SHOW_LANGUAGES": self.show_languages,
            "LOGIN_REDIRECT_URL": self.login_redirect_url,
            "SIDEBAR": {
                "show_all_applications": self.sidebar_show_all_applications,
                "show_search": self.sidebar_show_search,
            },
        }

        # Optional fields
        if self.site_icon:
            settings["SITE_ICON"] = self.site_icon

        if self.site_logo:
            settings["SITE_LOGO"] = self.site_logo

        if self.site_favicon:
            settings["SITE_FAVICON"] = self.site_favicon

        if self.site_symbol:
            settings["SITE_SYMBOL"] = self.site_symbol

        if self.environment:
            settings["ENVIRONMENT"] = self.environment

        if self.environment_callback:
            settings["ENVIRONMENT"] = self.environment_callback

        if self.login_image:
            settings["LOGIN"] = {"image": self.login_image}

        if self.theme:
            settings["THEME"] = self.theme

        if self.colors:
            settings["COLORS"] = self.colors

        if self.sidebar_navigation:
            settings["SIDEBAR"]["navigation"] = self.sidebar_navigation

        if self.tabs:
            settings["TABS"] = self.tabs

        if self.styles:
            settings["STYLES"] = self.styles

        if self.scripts:
            settings["SCRIPTS"] = self.scripts

        return settings


def configure_unfold(config: UnfoldConfig | None = None, **kwargs) -> dict[str, Any]:
    """
    Generate UNFOLD settings dict from configuration.

    Usage:
        # In settings.py
        from django_matt.admin.config import configure_unfold

        UNFOLD = configure_unfold(
            site_title="My Admin",
            site_header="My Company",
            theme="dark",
        )

        # Or with config object
        config = UnfoldConfig(site_title="My Admin")
        UNFOLD = configure_unfold(config)
    """
    if config is None:
        config = UnfoldConfig(**kwargs)
    elif kwargs:
        # Merge kwargs into config
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

    return config.to_dict()


def get_unfold_settings() -> dict[str, Any]:
    """
    Get current UNFOLD settings from Django settings.

    Returns empty dict if not configured.
    """
    try:
        from django.conf import settings

        return getattr(settings, "UNFOLD", {})
    except Exception:
        return {}


def create_navigation_item(
    title: str,
    icon: str | None = None,
    link: str | None = None,
    permission: str | None = None,
    badge: str | None = None,
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Create a sidebar navigation item.

    Usage:
        navigation = [
            create_navigation_item(
                title="Dashboard",
                icon="dashboard",
                link="/admin/",
            ),
            create_navigation_item(
                title="Users",
                icon="people",
                items=[
                    create_navigation_item("All Users", link="/admin/users/user/"),
                    create_navigation_item("Groups", link="/admin/auth/group/"),
                ],
            ),
        ]
    """
    item: dict[str, Any] = {"title": title}

    if icon:
        item["icon"] = icon

    if link:
        item["link"] = link

    if permission:
        item["permission"] = permission

    if badge:
        item["badge"] = badge

    if items:
        item["items"] = items

    return item


def create_app_navigation(
    app_label: str,
    title: str | None = None,
    icon: str | None = None,
    models: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create navigation for a Django app with its models.

    Usage:
        navigation = [
            create_app_navigation(
                "users",
                title="User Management",
                icon="people",
                models=["user", "profile"],
            ),
        ]
    """
    items = []

    if models:
        for model_name in models:
            items.append(
                {
                    "title": model_name.replace("_", " ").title(),
                    "link": f"/admin/{app_label}/{model_name}/",
                }
            )
    else:
        # Auto-discover models
        try:
            from django.apps import apps

            app_config = apps.get_app_config(app_label)
            for model in app_config.get_models():
                items.append(
                    {
                        "title": model._meta.verbose_name_plural.title(),
                        "link": f"/admin/{app_label}/{model._meta.model_name}/",
                    }
                )
        except Exception:
            pass

    return create_navigation_item(
        title=title or app_label.replace("_", " ").title(),
        icon=icon,
        items=items if items else None,
    )


# Predefined color schemes
COLOR_SCHEMES = {
    "blue": {
        "primary": {
            "50": "#eff6ff",
            "100": "#dbeafe",
            "200": "#bfdbfe",
            "300": "#93c5fd",
            "400": "#60a5fa",
            "500": "#3b82f6",
            "600": "#2563eb",
            "700": "#1d4ed8",
            "800": "#1e40af",
            "900": "#1e3a8a",
            "950": "#172554",
        }
    },
    "green": {
        "primary": {
            "50": "#f0fdf4",
            "100": "#dcfce7",
            "200": "#bbf7d0",
            "300": "#86efac",
            "400": "#4ade80",
            "500": "#22c55e",
            "600": "#16a34a",
            "700": "#15803d",
            "800": "#166534",
            "900": "#14532d",
            "950": "#052e16",
        }
    },
    "purple": {
        "primary": {
            "50": "#faf5ff",
            "100": "#f3e8ff",
            "200": "#e9d5ff",
            "300": "#d8b4fe",
            "400": "#c084fc",
            "500": "#a855f7",
            "600": "#9333ea",
            "700": "#7e22ce",
            "800": "#6b21a8",
            "900": "#581c87",
            "950": "#3b0764",
        }
    },
    "orange": {
        "primary": {
            "50": "#fff7ed",
            "100": "#ffedd5",
            "200": "#fed7aa",
            "300": "#fdba74",
            "400": "#fb923c",
            "500": "#f97316",
            "600": "#ea580c",
            "700": "#c2410c",
            "800": "#9a3412",
            "900": "#7c2d12",
            "950": "#431407",
        }
    },
    "slate": {
        "primary": {
            "50": "#f8fafc",
            "100": "#f1f5f9",
            "200": "#e2e8f0",
            "300": "#cbd5e1",
            "400": "#94a3b8",
            "500": "#64748b",
            "600": "#475569",
            "700": "#334155",
            "800": "#1e293b",
            "900": "#0f172a",
            "950": "#020617",
        }
    },
}


def get_color_scheme(name: str) -> dict[str, dict[str, str]]:
    """
    Get a predefined color scheme.

    Available schemes: blue, green, purple, orange, slate
    """
    return COLOR_SCHEMES.get(name, COLOR_SCHEMES["blue"])


__all__ = [
    "UnfoldConfig",
    "configure_unfold",
    "get_unfold_settings",
    "create_navigation_item",
    "create_app_navigation",
    "COLOR_SCHEMES",
    "get_color_scheme",
]
