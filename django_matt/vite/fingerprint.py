"""
Static file fingerprinting without Vite.

Content-hash based fingerprinting for cache busting. Works as a standalone
alternative to Vite for projects that just need fingerprinted static files.

Usage:
    # settings.py
    STATICFILES_STORAGE = "django_matt.vite.fingerprint.FingerprintedStorage"

    # templates
    {% load fingerprint %}
    <link rel="stylesheet" href="{% fingerprint 'css/style.css' %}">
    <script src="{% fingerprint 'js/app.js' %}"></script>
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import threading
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.staticfiles.storage import StaticFilesStorage

logger = logging.getLogger("django_matt.vite.fingerprint")

# Module-level manifest cache
_manifest: dict[str, str] = {}
_manifest_lock = threading.Lock()
_manifest_loaded = False


def _compute_file_hash(file_path: Path, length: int = 12) -> str:
    """Compute a content hash for a file."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:length]


def _insert_hash(filename: str, file_hash: str) -> str:
    """Insert content hash into filename: style.css -> style.a1b2c3d4.css"""
    parts = filename.rsplit(".", 1)
    if len(parts) == 2:
        return f"{parts[0]}.{file_hash}.{parts[1]}"
    return f"{filename}.{file_hash}"


class FingerprintManifest:
    """
    Manages the mapping from original filenames to fingerprinted filenames.

    Stores manifest as a JSON file alongside the collected static files.
    """

    def __init__(self, static_root: str | Path | None = None) -> None:
        self.static_root = Path(static_root or settings.STATIC_ROOT)
        self.manifest_path = self.static_root / "fingerprint-manifest.json"
        self._data: dict[str, str] = {}
        self._lock = threading.Lock()

    def build(self) -> dict[str, str]:
        """Scan static files and build the fingerprint manifest."""
        import orjson

        manifest: dict[str, str] = {}

        if not self.static_root.exists():
            logger.warning("STATIC_ROOT does not exist: %s", self.static_root)
            return manifest

        for file_path in sorted(self.static_root.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name == "fingerprint-manifest.json":
                continue

            rel_path = file_path.relative_to(self.static_root)
            rel_str = str(rel_path).replace("\\", "/")

            file_hash = _compute_file_hash(file_path)
            hashed_name = _insert_hash(rel_str, file_hash)

            # Copy file to hashed name
            hashed_path = self.static_root / hashed_name
            hashed_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, hashed_path)

            manifest[rel_str] = hashed_name

        # Write manifest
        self.manifest_path.write_bytes(
            orjson.dumps(manifest, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
        )

        with self._lock:
            self._data = manifest

        logger.info("Built fingerprint manifest: %d files", len(manifest))
        return manifest

    def load(self) -> dict[str, str]:
        """Load manifest from disk."""
        import orjson

        if not self.manifest_path.exists():
            return {}

        with self._lock:
            self._data = orjson.loads(self.manifest_path.read_bytes())
            return dict(self._data)

    def resolve(self, name: str) -> str:
        """Resolve an original filename to its fingerprinted version."""
        with self._lock:
            if not self._data and self.manifest_path.exists():
                import orjson

                self._data = orjson.loads(self.manifest_path.read_bytes())
            return self._data.get(name, name)


class FingerprintedStorage(StaticFilesStorage):
    """
    Django static files storage that adds content hashes to filenames.

    Set as STATICFILES_STORAGE to enable fingerprinting after collectstatic.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._manifest = FingerprintManifest(self.location)

    def url(self, name: str) -> str:
        """Return the URL for the fingerprinted version of the file."""
        hashed_name = self._manifest.resolve(name)
        return super().url(hashed_name)

    def post_process(self, paths: dict[str, Any], dry_run: bool = False, **options: Any):
        """Post-process collected files to add fingerprints."""
        if dry_run:
            return

        # Build manifest after collectstatic
        manifest = self._manifest.build()

        # Yield processed files
        for original, hashed in manifest.items():
            yield original, hashed, True


def get_manifest() -> FingerprintManifest:
    """Get the global fingerprint manifest instance."""
    static_root = getattr(settings, "STATIC_ROOT", None)
    return FingerprintManifest(static_root)


def resolve_fingerprint(name: str) -> str:
    """Resolve a static file name to its fingerprinted version."""
    return get_manifest().resolve(name)
