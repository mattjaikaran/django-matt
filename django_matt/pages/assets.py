"""
Asset versioning for page responses.

Manages asset version hashes to ensure clients reload when
assets change (CSS, JS, etc.).
"""

import hashlib
import os

from django.conf import settings

# Cached version hash
_cached_version: str | None = None


def get_asset_version() -> str:
    """
    Get the current asset version hash.

    This is used to detect when assets have changed and the client
    needs to do a full page reload instead of an XHR navigation.

    The version can come from:
    1. PAGES["version"] setting (manual)
    2. Vite/webpack manifest file hash
    3. Git commit hash
    4. Empty string (versioning disabled)
    """
    global _cached_version

    # Return cached version in production
    if _cached_version is not None and not settings.DEBUG:
        return _cached_version

    pages_config = getattr(settings, "PAGES", {})

    # 1. Manual version from settings
    manual_version = pages_config.get("version")
    if manual_version:
        _cached_version = manual_version
        return _cached_version

    # 2. Version from manifest file
    manifest_path = pages_config.get("manifest")
    if manifest_path:
        manifest_version = _get_manifest_version(manifest_path)
        if manifest_version:
            _cached_version = manifest_version
            return _cached_version

    # 3. Git commit hash
    git_version = _get_git_version()
    if git_version:
        _cached_version = git_version
        return _cached_version

    # 4. No versioning
    _cached_version = ""
    return _cached_version


def clear_version_cache() -> None:
    """Clear the cached version. Useful for testing."""
    global _cached_version
    _cached_version = None


def _get_manifest_version(manifest_path: str) -> str | None:
    """Get version hash from manifest file content."""
    try:
        from django.contrib.staticfiles import finders

        # Find the manifest file
        if os.path.isabs(manifest_path):
            full_path = manifest_path
        else:
            full_path = finders.find(manifest_path)

        if full_path and os.path.exists(full_path):
            # Hash the manifest content
            with open(full_path, "rb") as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()[:12]
    except Exception:
        pass

    return None


def _get_git_version() -> str | None:
    """Get version from git commit hash."""
    try:
        import subprocess

        # Get short commit hash
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )

        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


def check_version_match(client_version: str) -> bool:
    """
    Check if the client's version matches the server's.

    Returns True if versions match or versioning is disabled.
    """
    server_version = get_asset_version()

    # No versioning configured
    if not server_version:
        return True

    # Client didn't send version
    if not client_version:
        return True

    return client_version == server_version


__all__ = [
    "check_version_match",
    "clear_version_cache",
    "get_asset_version",
]
