"""
Theming system for components.

Provides theme configuration, color schemes, and design tokens
for consistent styling across components.
"""

from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Color System
# =============================================================================


class ColorScale(BaseModel):
    """Color scale with shades from 50 to 950."""

    _50: str = Field(alias="50")
    _100: str = Field(alias="100")
    _200: str = Field(alias="200")
    _300: str = Field(alias="300")
    _400: str = Field(alias="400")
    _500: str = Field(alias="500")
    _600: str = Field(alias="600")
    _700: str = Field(alias="700")
    _800: str = Field(alias="800")
    _900: str = Field(alias="900")
    _950: str = Field(alias="950")

    class Config:
        populate_by_name = True


class SemanticColors(BaseModel):
    """Semantic color definitions."""

    background: str = "hsl(0 0% 100%)"
    foreground: str = "hsl(222.2 84% 4.9%)"
    card: str = "hsl(0 0% 100%)"
    card_foreground: str = "hsl(222.2 84% 4.9%)"
    popover: str = "hsl(0 0% 100%)"
    popover_foreground: str = "hsl(222.2 84% 4.9%)"
    primary: str = "hsl(222.2 47.4% 11.2%)"
    primary_foreground: str = "hsl(210 40% 98%)"
    secondary: str = "hsl(210 40% 96.1%)"
    secondary_foreground: str = "hsl(222.2 47.4% 11.2%)"
    muted: str = "hsl(210 40% 96.1%)"
    muted_foreground: str = "hsl(215.4 16.3% 46.9%)"
    accent: str = "hsl(210 40% 96.1%)"
    accent_foreground: str = "hsl(222.2 47.4% 11.2%)"
    destructive: str = "hsl(0 84.2% 60.2%)"
    destructive_foreground: str = "hsl(210 40% 98%)"
    border: str = "hsl(214.3 31.8% 91.4%)"
    input: str = "hsl(214.3 31.8% 91.4%)"
    ring: str = "hsl(222.2 84% 4.9%)"
    success: str = "hsl(142.1 76.2% 36.3%)"
    success_foreground: str = "hsl(355.7 100% 97.3%)"
    warning: str = "hsl(47.9 95.8% 53.1%)"
    warning_foreground: str = "hsl(26 83.3% 14.1%)"
    info: str = "hsl(221.2 83.2% 53.3%)"
    info_foreground: str = "hsl(210 40% 98%)"


class DarkColors(SemanticColors):
    """Dark mode color overrides."""

    background: str = "hsl(222.2 84% 4.9%)"
    foreground: str = "hsl(210 40% 98%)"
    card: str = "hsl(222.2 84% 4.9%)"
    card_foreground: str = "hsl(210 40% 98%)"
    popover: str = "hsl(222.2 84% 4.9%)"
    popover_foreground: str = "hsl(210 40% 98%)"
    primary: str = "hsl(210 40% 98%)"
    primary_foreground: str = "hsl(222.2 47.4% 11.2%)"
    secondary: str = "hsl(217.2 32.6% 17.5%)"
    secondary_foreground: str = "hsl(210 40% 98%)"
    muted: str = "hsl(217.2 32.6% 17.5%)"
    muted_foreground: str = "hsl(215 20.2% 65.1%)"
    accent: str = "hsl(217.2 32.6% 17.5%)"
    accent_foreground: str = "hsl(210 40% 98%)"
    destructive: str = "hsl(0 62.8% 30.6%)"
    destructive_foreground: str = "hsl(210 40% 98%)"
    border: str = "hsl(217.2 32.6% 17.5%)"
    input: str = "hsl(217.2 32.6% 17.5%)"
    ring: str = "hsl(212.7 26.8% 83.9%)"


# =============================================================================
# Typography
# =============================================================================


class FontFamily(BaseModel):
    """Font family definitions."""

    sans: str = "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    serif: str = "ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif"
    mono: str = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Monaco, Consolas, monospace"


class FontSize(BaseModel):
    """Font size scale."""

    xs: str = "0.75rem"
    sm: str = "0.875rem"
    base: str = "1rem"
    lg: str = "1.125rem"
    xl: str = "1.25rem"
    _2xl: str = Field(default="1.5rem", alias="2xl")
    _3xl: str = Field(default="1.875rem", alias="3xl")
    _4xl: str = Field(default="2.25rem", alias="4xl")
    _5xl: str = Field(default="3rem", alias="5xl")

    class Config:
        populate_by_name = True


class LineHeight(BaseModel):
    """Line height scale."""

    none: str = "1"
    tight: str = "1.25"
    snug: str = "1.375"
    normal: str = "1.5"
    relaxed: str = "1.625"
    loose: str = "2"


class FontWeight(BaseModel):
    """Font weight scale."""

    thin: str = "100"
    extralight: str = "200"
    light: str = "300"
    normal: str = "400"
    medium: str = "500"
    semibold: str = "600"
    bold: str = "700"
    extrabold: str = "800"
    black: str = "900"


class Typography(BaseModel):
    """Typography configuration."""

    font_family: FontFamily = Field(default_factory=FontFamily)
    font_size: FontSize = Field(default_factory=FontSize)
    line_height: LineHeight = Field(default_factory=LineHeight)
    font_weight: FontWeight = Field(default_factory=FontWeight)


# =============================================================================
# Spacing & Layout
# =============================================================================


class Spacing(BaseModel):
    """Spacing scale (matches Tailwind)."""

    _0: str = Field(default="0", alias="0")
    px: str = "1px"
    _0_5: str = Field(default="0.125rem", alias="0.5")
    _1: str = Field(default="0.25rem", alias="1")
    _1_5: str = Field(default="0.375rem", alias="1.5")
    _2: str = Field(default="0.5rem", alias="2")
    _2_5: str = Field(default="0.625rem", alias="2.5")
    _3: str = Field(default="0.75rem", alias="3")
    _3_5: str = Field(default="0.875rem", alias="3.5")
    _4: str = Field(default="1rem", alias="4")
    _5: str = Field(default="1.25rem", alias="5")
    _6: str = Field(default="1.5rem", alias="6")
    _7: str = Field(default="1.75rem", alias="7")
    _8: str = Field(default="2rem", alias="8")
    _9: str = Field(default="2.25rem", alias="9")
    _10: str = Field(default="2.5rem", alias="10")
    _11: str = Field(default="2.75rem", alias="11")
    _12: str = Field(default="3rem", alias="12")
    _14: str = Field(default="3.5rem", alias="14")
    _16: str = Field(default="4rem", alias="16")
    _20: str = Field(default="5rem", alias="20")
    _24: str = Field(default="6rem", alias="24")
    _28: str = Field(default="7rem", alias="28")
    _32: str = Field(default="8rem", alias="32")
    _36: str = Field(default="9rem", alias="36")
    _40: str = Field(default="10rem", alias="40")
    _44: str = Field(default="11rem", alias="44")
    _48: str = Field(default="12rem", alias="48")
    _52: str = Field(default="13rem", alias="52")
    _56: str = Field(default="14rem", alias="56")
    _60: str = Field(default="15rem", alias="60")
    _64: str = Field(default="16rem", alias="64")
    _72: str = Field(default="18rem", alias="72")
    _80: str = Field(default="20rem", alias="80")
    _96: str = Field(default="24rem", alias="96")

    class Config:
        populate_by_name = True


class BorderRadius(BaseModel):
    """Border radius scale."""

    none: str = "0"
    sm: str = "0.125rem"
    default: str = "0.25rem"
    md: str = "0.375rem"
    lg: str = "0.5rem"
    xl: str = "0.75rem"
    _2xl: str = Field(default="1rem", alias="2xl")
    _3xl: str = Field(default="1.5rem", alias="3xl")
    full: str = "9999px"

    class Config:
        populate_by_name = True


class Shadow(BaseModel):
    """Box shadow scale."""

    sm: str = "0 1px 2px 0 rgb(0 0 0 / 0.05)"
    default: str = "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)"
    md: str = "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)"
    lg: str = "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)"
    xl: str = "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)"
    _2xl: str = Field(default="0 25px 50px -12px rgb(0 0 0 / 0.25)", alias="2xl")
    inner: str = "inset 0 2px 4px 0 rgb(0 0 0 / 0.05)"
    none: str = "none"

    class Config:
        populate_by_name = True


class Breakpoints(BaseModel):
    """Responsive breakpoints."""

    sm: str = "640px"
    md: str = "768px"
    lg: str = "1024px"
    xl: str = "1280px"
    _2xl: str = Field(default="1536px", alias="2xl")

    class Config:
        populate_by_name = True


class ZIndex(BaseModel):
    """Z-index scale."""

    auto: str = "auto"
    _0: str = Field(default="0", alias="0")
    _10: str = Field(default="10", alias="10")
    _20: str = Field(default="20", alias="20")
    _30: str = Field(default="30", alias="30")
    _40: str = Field(default="40", alias="40")
    _50: str = Field(default="50", alias="50")
    dropdown: str = "1000"
    sticky: str = "1020"
    fixed: str = "1030"
    modal_backdrop: str = "1040"
    modal: str = "1050"
    popover: str = "1060"
    tooltip: str = "1070"

    class Config:
        populate_by_name = True


# =============================================================================
# Animation
# =============================================================================


class Animation(BaseModel):
    """Animation configuration."""

    duration_fast: str = "150ms"
    duration_normal: str = "200ms"
    duration_slow: str = "300ms"
    duration_slower: str = "500ms"
    easing_default: str = "cubic-bezier(0.4, 0, 0.2, 1)"
    easing_in: str = "cubic-bezier(0.4, 0, 1, 1)"
    easing_out: str = "cubic-bezier(0, 0, 0.2, 1)"
    easing_in_out: str = "cubic-bezier(0.4, 0, 0.2, 1)"


# =============================================================================
# Theme
# =============================================================================


class Theme(BaseModel):
    """
    Complete theme configuration.

    Usage:
        # Create a custom theme
        theme = Theme(
            name="my-theme",
            colors=SemanticColors(
                primary="hsl(221.2 83.2% 53.3%)",
                secondary="hsl(210 40% 96.1%)",
            ),
        )

        # Use with components
        from django_matt.components import set_theme
        set_theme(theme)
    """

    name: str = "default"
    colors: SemanticColors = Field(default_factory=SemanticColors)
    dark_colors: DarkColors = Field(default_factory=DarkColors)
    typography: Typography = Field(default_factory=Typography)
    spacing: Spacing = Field(default_factory=Spacing)
    border_radius: BorderRadius = Field(default_factory=BorderRadius)
    shadow: Shadow = Field(default_factory=Shadow)
    breakpoints: Breakpoints = Field(default_factory=Breakpoints)
    z_index: ZIndex = Field(default_factory=ZIndex)
    animation: Animation = Field(default_factory=Animation)

    def to_css_variables(self, dark: bool = False) -> dict[str, str]:
        """Convert theme to CSS custom properties."""
        colors = self.dark_colors if dark else self.colors
        variables = {}

        # Colors
        for field_name, value in colors.model_dump().items():
            css_name = field_name.replace("_", "-")
            variables[f"--{css_name}"] = value

        # Border radius
        variables["--radius"] = self.border_radius.lg

        return variables

    def to_tailwind_config(self) -> dict[str, Any]:
        """Convert theme to Tailwind config format."""
        return {
            "colors": {
                "background": "hsl(var(--background))",
                "foreground": "hsl(var(--foreground))",
                "card": {
                    "DEFAULT": "hsl(var(--card))",
                    "foreground": "hsl(var(--card-foreground))",
                },
                "popover": {
                    "DEFAULT": "hsl(var(--popover))",
                    "foreground": "hsl(var(--popover-foreground))",
                },
                "primary": {
                    "DEFAULT": "hsl(var(--primary))",
                    "foreground": "hsl(var(--primary-foreground))",
                },
                "secondary": {
                    "DEFAULT": "hsl(var(--secondary))",
                    "foreground": "hsl(var(--secondary-foreground))",
                },
                "muted": {
                    "DEFAULT": "hsl(var(--muted))",
                    "foreground": "hsl(var(--muted-foreground))",
                },
                "accent": {
                    "DEFAULT": "hsl(var(--accent))",
                    "foreground": "hsl(var(--accent-foreground))",
                },
                "destructive": {
                    "DEFAULT": "hsl(var(--destructive))",
                    "foreground": "hsl(var(--destructive-foreground))",
                },
                "border": "hsl(var(--border))",
                "input": "hsl(var(--input))",
                "ring": "hsl(var(--ring))",
            },
            "borderRadius": {
                "lg": "var(--radius)",
                "md": "calc(var(--radius) - 2px)",
                "sm": "calc(var(--radius) - 4px)",
            },
        }


# =============================================================================
# Preset Themes
# =============================================================================


def create_shadcn_theme() -> Theme:
    """Create shadcn/ui compatible theme."""
    return Theme(name="shadcn")


def create_zinc_theme() -> Theme:
    """Create zinc color theme."""
    return Theme(
        name="zinc",
        colors=SemanticColors(
            background="hsl(0 0% 100%)",
            foreground="hsl(240 10% 3.9%)",
            card="hsl(0 0% 100%)",
            card_foreground="hsl(240 10% 3.9%)",
            popover="hsl(0 0% 100%)",
            popover_foreground="hsl(240 10% 3.9%)",
            primary="hsl(240 5.9% 10%)",
            primary_foreground="hsl(0 0% 98%)",
            secondary="hsl(240 4.8% 95.9%)",
            secondary_foreground="hsl(240 5.9% 10%)",
            muted="hsl(240 4.8% 95.9%)",
            muted_foreground="hsl(240 3.8% 46.1%)",
            accent="hsl(240 4.8% 95.9%)",
            accent_foreground="hsl(240 5.9% 10%)",
            destructive="hsl(0 84.2% 60.2%)",
            destructive_foreground="hsl(0 0% 98%)",
            border="hsl(240 5.9% 90%)",
            input="hsl(240 5.9% 90%)",
            ring="hsl(240 5.9% 10%)",
        ),
        dark_colors=DarkColors(
            background="hsl(240 10% 3.9%)",
            foreground="hsl(0 0% 98%)",
            card="hsl(240 10% 3.9%)",
            card_foreground="hsl(0 0% 98%)",
            popover="hsl(240 10% 3.9%)",
            popover_foreground="hsl(0 0% 98%)",
            primary="hsl(0 0% 98%)",
            primary_foreground="hsl(240 5.9% 10%)",
            secondary="hsl(240 3.7% 15.9%)",
            secondary_foreground="hsl(0 0% 98%)",
            muted="hsl(240 3.7% 15.9%)",
            muted_foreground="hsl(240 5% 64.9%)",
            accent="hsl(240 3.7% 15.9%)",
            accent_foreground="hsl(0 0% 98%)",
            destructive="hsl(0 62.8% 30.6%)",
            destructive_foreground="hsl(0 0% 98%)",
            border="hsl(240 3.7% 15.9%)",
            input="hsl(240 3.7% 15.9%)",
            ring="hsl(240 4.9% 83.9%)",
        ),
    )


def create_blue_theme() -> Theme:
    """Create blue color theme."""
    return Theme(
        name="blue",
        colors=SemanticColors(
            primary="hsl(221.2 83.2% 53.3%)",
            primary_foreground="hsl(210 40% 98%)",
            ring="hsl(221.2 83.2% 53.3%)",
        ),
    )


def create_green_theme() -> Theme:
    """Create green color theme."""
    return Theme(
        name="green",
        colors=SemanticColors(
            primary="hsl(142.1 76.2% 36.3%)",
            primary_foreground="hsl(355.7 100% 97.3%)",
            ring="hsl(142.1 76.2% 36.3%)",
        ),
    )


def create_violet_theme() -> Theme:
    """Create violet color theme."""
    return Theme(
        name="violet",
        colors=SemanticColors(
            primary="hsl(262.1 83.3% 57.8%)",
            primary_foreground="hsl(210 40% 98%)",
            ring="hsl(262.1 83.3% 57.8%)",
        ),
    )


# =============================================================================
# Theme Management
# =============================================================================


class ThemeManager:
    """
    Manages theme configuration and provides global access.

    Usage:
        from django_matt.components.theming import theme_manager

        # Set theme
        theme_manager.set_theme(create_blue_theme())

        # Get current theme
        theme = theme_manager.get_theme()

        # Get CSS variables
        css_vars = theme_manager.get_css_variables()
    """

    def __init__(self):
        self._theme: Theme = Theme()
        self._themes: dict[str, Theme] = {
            "default": Theme(),
            "shadcn": create_shadcn_theme(),
            "zinc": create_zinc_theme(),
            "blue": create_blue_theme(),
            "green": create_green_theme(),
            "violet": create_violet_theme(),
        }

    def set_theme(self, theme: Theme) -> None:
        """Set the current theme."""
        self._theme = theme

    def get_theme(self) -> Theme:
        """Get the current theme."""
        return self._theme

    def use_preset(self, name: str) -> None:
        """Use a preset theme by name."""
        if name in self._themes:
            self._theme = self._themes[name]
        else:
            raise ValueError(f"Unknown theme preset: {name}")

    def register_theme(self, name: str, theme: Theme) -> None:
        """Register a custom theme preset."""
        self._themes[name] = theme

    def list_presets(self) -> list[str]:
        """List available theme presets."""
        return list(self._themes.keys())

    def get_css_variables(self, dark: bool = False) -> dict[str, str]:
        """Get CSS variables for current theme."""
        return self._theme.to_css_variables(dark=dark)

    def get_css_string(self, dark: bool = False) -> str:
        """Get CSS variables as a string for embedding."""
        variables = self.get_css_variables(dark=dark)
        lines = [f"  {name}: {value};" for name, value in variables.items()]
        selector = ".dark" if dark else ":root"
        return f"{selector} {{\n" + "\n".join(lines) + "\n}"

    def get_full_css(self) -> str:
        """Get complete CSS with light and dark modes."""
        light = self.get_css_string(dark=False)
        dark = self.get_css_string(dark=True)
        return f"{light}\n\n{dark}"


# Global theme manager instance
theme_manager = ThemeManager()


# Convenience functions
def set_theme(theme: Theme) -> None:
    """Set the global theme."""
    theme_manager.set_theme(theme)


def get_theme() -> Theme:
    """Get the global theme."""
    return theme_manager.get_theme()


def use_preset(name: str) -> None:
    """Use a preset theme."""
    theme_manager.use_preset(name)


__all__ = [
    # Color
    "ColorScale",
    "SemanticColors",
    "DarkColors",
    # Typography
    "FontFamily",
    "FontSize",
    "LineHeight",
    "FontWeight",
    "Typography",
    # Spacing & Layout
    "Spacing",
    "BorderRadius",
    "Shadow",
    "Breakpoints",
    "ZIndex",
    # Animation
    "Animation",
    # Theme
    "Theme",
    # Presets
    "create_shadcn_theme",
    "create_zinc_theme",
    "create_blue_theme",
    "create_green_theme",
    "create_violet_theme",
    # Management
    "ThemeManager",
    "theme_manager",
    "set_theme",
    "get_theme",
    "use_preset",
]
