"""Starter templates for django-matt startapi command."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

STARTERS_DIR = Path(__file__).parent

TEMPLATE_NAMES = ["api-only", "ai-saas", "marketplace", "internal-tools"]

# Map old template names to new starter templates for backward compat
TEMPLATE_ALIASES: dict[str, str] = {
    "starter": "api-only",
    "b2b": "api-only",
    "b2c": "api-only",
    "saas": "ai-saas",
}


def get_template_dir(name: str) -> Path:
    """Get the directory for a starter template."""
    resolved = TEMPLATE_ALIASES.get(name, name)
    template_dir = STARTERS_DIR / resolved
    if not template_dir.exists():
        msg = f"Unknown template: {name!r}. Available: {', '.join(TEMPLATE_NAMES)}"
        raise ValueError(msg)
    return template_dir


def load_metadata(name: str) -> dict[str, Any]:
    """Load metadata.json for a template."""
    template_dir = get_template_dir(name)
    metadata_path = template_dir / "metadata.json"
    with open(metadata_path) as f:
        return json.load(f)


def list_templates() -> list[dict[str, Any]]:
    """List all available starter templates with metadata."""
    templates = []
    for name in TEMPLATE_NAMES:
        try:
            meta = load_metadata(name)
            templates.append(meta)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return templates


def render_template(
    name: str,
    project_name: str,
    output_dir: Path,
) -> Path:
    """Copy template to output_dir and replace {{ project_name }} placeholders.

    The `app/` directory in the template is renamed to `{project_name}_app/`.

    Returns the output directory path.
    """
    template_dir = get_template_dir(name)
    source = template_dir / "project_template"
    if not source.exists():
        msg = f"Template {name!r} has no project_template/ directory"
        raise ValueError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy all files from template
    for item in source.iterdir():
        dest_name = item.name
        # Rename app/ to {project_name}_app/
        if item.name == "app":
            dest_name = f"{project_name}_app"

        dest = output_dir / dest_name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    # Replace {{ project_name }} in all text files
    _replace_placeholders(output_dir, project_name)

    return output_dir


def _replace_placeholders(directory: Path, project_name: str) -> None:
    """Recursively replace {{ project_name }} in all text files."""
    text_extensions = {
        ".py", ".toml", ".yml", ".yaml", ".json", ".md",
        ".cfg", ".ini", ".txt", ".env", ".sh",
    }
    # Also handle extensionless files like Dockerfile
    extensionless_names = {"Dockerfile", "Makefile", "Procfile"}

    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in text_extensions and path.name not in extensionless_names:
            continue
        try:
            content = path.read_text(encoding="utf-8")
            if "{{ project_name }}" in content:
                path.write_text(
                    content.replace("{{ project_name }}", project_name),
                    encoding="utf-8",
                )
        except (UnicodeDecodeError, PermissionError):
            continue
