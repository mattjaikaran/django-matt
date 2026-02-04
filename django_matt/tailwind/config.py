"""
Tailwind CSS configuration for Django Matt.

Provides centralized configuration for Tailwind classes and theme settings.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

# Color palette presets (defined outside class to be accessible as class attribute)
THEME_PRESETS: dict[str, dict[str, str]] = {
    "default": {
        "color_primary": "blue",
        "color_secondary": "gray",
        "color_accent": "indigo",
    },
    "emerald": {
        "color_primary": "emerald",
        "color_secondary": "slate",
        "color_accent": "teal",
    },
    "purple": {
        "color_primary": "purple",
        "color_secondary": "gray",
        "color_accent": "violet",
    },
    "rose": {
        "color_primary": "rose",
        "color_secondary": "gray",
        "color_accent": "pink",
    },
    "amber": {
        "color_primary": "amber",
        "color_secondary": "stone",
        "color_accent": "orange",
    },
    "cyan": {
        "color_primary": "cyan",
        "color_secondary": "slate",
        "color_accent": "sky",
    },
}


@dataclass
class TailwindConfig:
    """
    Tailwind CSS configuration.

    Configure via Django settings:
        DJANGO_MATT_TAILWIND = {
            "THEME": "default",
            "COLOR_PRIMARY": "blue",
            "COLOR_SECONDARY": "gray",
            "COLOR_ACCENT": "indigo",
            "BORDER_RADIUS": "rounded-lg",
            "COMPONENT_PREFIX": "",
            "DARK_MODE": "class",  # "class" or "media"
        }
    """

    theme: str = "default"
    color_primary: str = "blue"
    color_secondary: str = "gray"
    color_accent: str = "indigo"
    border_radius: str = "rounded-lg"
    component_prefix: str = ""
    dark_mode: str = "class"

    @classmethod
    def from_settings(cls) -> TailwindConfig:
        """Create config from Django settings."""
        config_dict = getattr(settings, "DJANGO_MATT_TAILWIND", {})

        # Get theme preset
        theme = config_dict.get("THEME", "default")
        theme_preset = THEME_PRESETS.get(theme, {})

        return cls(
            theme=theme,
            color_primary=config_dict.get(
                "COLOR_PRIMARY", theme_preset.get("color_primary", "blue")
            ),
            color_secondary=config_dict.get(
                "COLOR_SECONDARY", theme_preset.get("color_secondary", "gray")
            ),
            color_accent=config_dict.get(
                "COLOR_ACCENT", theme_preset.get("color_accent", "indigo")
            ),
            border_radius=config_dict.get("BORDER_RADIUS", "rounded-lg"),
            component_prefix=config_dict.get("COMPONENT_PREFIX", ""),
            dark_mode=config_dict.get("DARK_MODE", "class"),
        )

    def get_color_class(self, color_type: str, shade: int = 500) -> str:
        """
        Get a color class for the specified type and shade.

        Args:
            color_type: "primary", "secondary", or "accent"
            shade: Tailwind shade (50-950)

        Returns:
            Color name with shade (e.g., "blue-500")
        """
        colors = {
            "primary": self.color_primary,
            "secondary": self.color_secondary,
            "accent": self.color_accent,
        }
        color = colors.get(color_type, self.color_primary)
        return f"{color}-{shade}"

    def bg(self, color_type: str, shade: int = 500) -> str:
        """Get background color class."""
        return f"bg-{self.get_color_class(color_type, shade)}"

    def text(self, color_type: str, shade: int = 500) -> str:
        """Get text color class."""
        return f"text-{self.get_color_class(color_type, shade)}"

    def border(self, color_type: str, shade: int = 500) -> str:
        """Get border color class."""
        return f"border-{self.get_color_class(color_type, shade)}"

    def ring(self, color_type: str, shade: int = 500) -> str:
        """Get ring color class."""
        return f"ring-{self.get_color_class(color_type, shade)}"


# Cached config instance
_config: TailwindConfig | None = None


def get_tailwind_config() -> TailwindConfig:
    """Get the global Tailwind configuration instance."""
    global _config
    if _config is None:
        _config = TailwindConfig.from_settings()
    return _config


def reset_tailwind_config():
    """Reset the cached configuration (useful for testing)."""
    global _config
    _config = None


# Tailwind color palette for reference
TAILWIND_COLORS = {
    "slate": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "gray": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "zinc": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "neutral": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "stone": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "red": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "orange": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "amber": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "yellow": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "lime": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "green": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "emerald": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "teal": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "cyan": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "sky": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "blue": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "indigo": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "violet": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "purple": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "fuchsia": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "pink": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
    "rose": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950],
}


# Spacing scale
TAILWIND_SPACING = {
    "0": "0px",
    "px": "1px",
    "0.5": "0.125rem",
    "1": "0.25rem",
    "1.5": "0.375rem",
    "2": "0.5rem",
    "2.5": "0.625rem",
    "3": "0.75rem",
    "3.5": "0.875rem",
    "4": "1rem",
    "5": "1.25rem",
    "6": "1.5rem",
    "7": "1.75rem",
    "8": "2rem",
    "9": "2.25rem",
    "10": "2.5rem",
    "11": "2.75rem",
    "12": "3rem",
    "14": "3.5rem",
    "16": "4rem",
    "20": "5rem",
    "24": "6rem",
    "28": "7rem",
    "32": "8rem",
    "36": "9rem",
    "40": "10rem",
    "44": "11rem",
    "48": "12rem",
    "52": "13rem",
    "56": "14rem",
    "60": "15rem",
    "64": "16rem",
    "72": "18rem",
    "80": "20rem",
    "96": "24rem",
}


__all__ = [
    "TailwindConfig",
    "get_tailwind_config",
    "reset_tailwind_config",
    "TAILWIND_COLORS",
    "TAILWIND_SPACING",
]
