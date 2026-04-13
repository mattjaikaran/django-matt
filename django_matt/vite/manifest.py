"""
Vite manifest parser.

Parses the Vite build manifest (manifest.json) to resolve entry points
to their output files, CSS dependencies, and import chains.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.conf import settings

import orjson

from django_matt.vite.config import get_vite_config

logger = logging.getLogger("django_matt.vite")


@dataclass
class ManifestEntry:
    """A single entry in the Vite manifest."""

    file: str
    src: str = ""
    is_entry: bool = False
    css: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    dynamic_imports: list[str] = field(default_factory=list)


class ViteManifest:
    """
    Parser and resolver for Vite build manifests.

    Caches the parsed manifest in production. In development (DEBUG=True),
    reloads on every access to pick up rebuilds.
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._entries: dict[str, ManifestEntry] = {}
        self._lock = threading.Lock()
        self._loaded = False

    def load(self, path: str | Path | None = None) -> None:
        """
        Parse manifest.json and populate entries.

        Args:
            path: Path to manifest.json. Falls back to config.
        """
        if path is None:
            config = get_vite_config()
            path = Path(settings.BASE_DIR) / config.manifest_path

        manifest_path = Path(path)
        if not manifest_path.exists():
            logger.warning("Vite manifest not found at %s", manifest_path)
            self._data = {}
            self._entries = {}
            self._loaded = True
            return

        raw = manifest_path.read_bytes()
        self._data = orjson.loads(raw)
        self._entries = {}

        for key, value in self._data.items():
            self._entries[key] = ManifestEntry(
                file=value.get("file", ""),
                src=value.get("src", key),
                is_entry=value.get("isEntry", False),
                css=value.get("css", []),
                imports=value.get("imports", []),
                dynamic_imports=value.get("dynamicImports", []),
            )

        self._loaded = True

    def _ensure_loaded(self) -> None:
        """Load manifest if not yet loaded, or reload in dev mode."""
        is_dev = getattr(settings, "DEBUG", False)
        if not self._loaded or is_dev:
            with self._lock:
                if not self._loaded or is_dev:
                    self.load()

    def resolve(self, entry: str) -> ManifestEntry | None:
        """
        Look up an asset by entry point name.

        Args:
            entry: The source entry point (e.g., "src/main.js").

        Returns:
            ManifestEntry or None if not found.
        """
        self._ensure_loaded()
        return self._entries.get(entry)

    def _collect_css(self, entry: str, seen: set[str] | None = None) -> list[str]:
        """Recursively collect CSS files for an entry and its imports."""
        if seen is None:
            seen = set()
        if entry in seen:
            return []
        seen.add(entry)

        result: list[str] = []
        manifest_entry = self._entries.get(entry)
        if manifest_entry is None:
            return result

        result.extend(manifest_entry.css)

        for imp in manifest_entry.imports:
            result.extend(self._collect_css(imp, seen))

        return result

    def _collect_imports(
        self, entry: str, seen: set[str] | None = None
    ) -> list[str]:
        """Recursively collect imported chunk files."""
        if seen is None:
            seen = set()
        if entry in seen:
            return []
        seen.add(entry)

        result: list[str] = []
        manifest_entry = self._entries.get(entry)
        if manifest_entry is None:
            return result

        for imp in manifest_entry.imports:
            imp_entry = self._entries.get(imp)
            if imp_entry and imp not in seen:
                result.append(imp_entry.file)
                result.extend(self._collect_imports(imp, seen))

        return result

    def get_js_tags(self, entry: str) -> list[str]:
        """
        Return <script> tags for an entry point and its imports.

        Args:
            entry: The source entry point name.

        Returns:
            List of HTML script tags.
        """
        self._ensure_loaded()
        config = get_vite_config()
        prefix = config.static_url_prefix

        manifest_entry = self._entries.get(entry)
        if manifest_entry is None:
            logger.warning("Vite entry '%s' not found in manifest", entry)
            return []

        tags: list[str] = []

        # Import chunks first
        for imp_file in self._collect_imports(entry):
            tags.append(
                f'<script type="module" src="{prefix}{imp_file}"></script>'
            )

        # Main entry
        tags.append(
            f'<script type="module" src="{prefix}{manifest_entry.file}"></script>'
        )

        return tags

    def get_css_tags(self, entry: str) -> list[str]:
        """
        Return <link> tags for CSS associated with an entry point.

        Args:
            entry: The source entry point name.

        Returns:
            List of HTML link tags.
        """
        self._ensure_loaded()
        config = get_vite_config()
        prefix = config.static_url_prefix

        css_files = self._collect_css(entry)
        seen: set[str] = set()
        tags: list[str] = []
        for css_file in css_files:
            if css_file not in seen:
                seen.add(css_file)
                tags.append(
                    f'<link rel="stylesheet" href="{prefix}{css_file}" />'
                )

        return tags

    def get_preload_tags(self, entry: str) -> list[str]:
        """
        Return modulepreload link tags for an entry's imports.

        Args:
            entry: The source entry point name.

        Returns:
            List of HTML link tags with rel="modulepreload".
        """
        self._ensure_loaded()
        config = get_vite_config()
        prefix = config.static_url_prefix

        import_files = self._collect_imports(entry)
        tags: list[str] = []
        for imp_file in import_files:
            tags.append(
                f'<link rel="modulepreload" href="{prefix}{imp_file}" />'
            )

        return tags


# Module-level singleton
_manifest: ViteManifest | None = None


def get_manifest() -> ViteManifest:
    """Get the global ViteManifest instance."""
    global _manifest
    if _manifest is None:
        _manifest = ViteManifest()
    return _manifest


def reset_manifest() -> None:
    """Reset the cached manifest (useful for testing)."""
    global _manifest
    _manifest = None


__all__ = [
    "ManifestEntry",
    "ViteManifest",
    "get_manifest",
    "reset_manifest",
]
