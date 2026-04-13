from __future__ import annotations

from pathlib import Path


class PluginScaffolder:
    """Generates a new django-matt plugin project structure."""

    def __init__(self, name: str, *, author: str = "", description: str = "") -> None:
        self.name = name
        self.package_name = name.replace("-", "_")
        self.class_name = "".join(
            word.capitalize() for word in name.replace("-", " ").replace("_", " ").split()
        )
        self.author = author
        self.description = description or f"A django-matt plugin: {name}"

    def generate(self, output_dir: str | Path) -> list[str]:
        """Generate plugin project files. Returns list of created file paths."""
        base = Path(output_dir) / self.name
        pkg = base / self.package_name
        tests_dir = base / "tests"
        gh_dir = base / ".github" / "workflows"

        created: list[str] = []

        for d in [pkg, tests_dir, gh_dir]:
            d.mkdir(parents=True, exist_ok=True)

        files: dict[str, str] = {
            str(base / "pyproject.toml"): self._pyproject_toml(),
            str(base / "README.md"): self._readme(),
            str(pkg / "__init__.py"): self._init_py(),
            str(pkg / "plugin.py"): self._plugin_py(),
            str(pkg / "controllers.py"): self._controllers_py(),
            str(pkg / "schemas.py"): self._schemas_py(),
            str(pkg / "services.py"): self._services_py(),
            str(tests_dir / "__init__.py"): "",
            str(tests_dir / "test_plugin.py"): self._test_py(),
            str(gh_dir / "ci.yml"): self._ci_yml(),
        }

        for filepath, content in files.items():
            Path(filepath).write_text(content)
            created.append(filepath)

        return created

    def _pyproject_toml(self) -> str:
        return f"""[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{self.name}"
version = "0.1.0"
description = "{self.description}"
requires-python = ">=3.12"
dependencies = ["django-matt>=0.9.0"]
authors = [{{ name = "{self.author}" }}]

[project.entry-points."matt.plugins"]
{self.package_name} = "{self.package_name}.plugin:{self.class_name}Plugin"

[tool.ruff]
line-length = 88
target-version = "py312"
"""

    def _readme(self) -> str:
        return f"""# {self.name}

{self.description}

## Installation

```bash
uv add {self.name}
```

## Configuration

Add to your Django settings:

```python
MATT_PLUGINS = ["{self.package_name}.plugin"]
```

## Usage

The plugin registers automatically when installed via entry points.
"""

    def _init_py(self) -> str:
        return f'from {self.package_name}.plugin import {self.class_name}Plugin\n\n__all__ = ["{self.class_name}Plugin"]\n'

    def _plugin_py(self) -> str:
        return f"""from __future__ import annotations

from typing import TYPE_CHECKING

from django_matt.plugins import MattPlugin

if TYPE_CHECKING:
    from django_matt.api import MattAPI


class {self.class_name}Plugin(MattPlugin):
    name = "{self.package_name}"
    version = "0.1.0"
    description = "{self.description}"
    author = "{self.author}"
    django_matt_version = "0.9.0"
    settings_prefix = "MATT_{self.package_name.upper()}"

    def setup(self, api: MattAPI) -> None:
        pass

    def get_settings_schema(self) -> dict:
        return {{
            "type": "object",
            "properties": {{
                "enabled": {{"type": "boolean", "default": True}},
            }},
        }}
"""

    def _controllers_py(self) -> str:
        return f"""from __future__ import annotations


class {self.class_name}Controller:
    prefix = "/{self.package_name}"
    tags = ["{self.class_name}"]
"""

    def _schemas_py(self) -> str:
        return f"""from __future__ import annotations

from pydantic import BaseModel


class {self.class_name}Schema(BaseModel):
    id: int
    name: str
"""

    def _services_py(self) -> str:
        return f"""from __future__ import annotations


class {self.class_name}Service:
    pass
"""

    def _test_py(self) -> str:
        return f"""import pytest

from {self.package_name}.plugin import {self.class_name}Plugin


class Test{self.class_name}Plugin:
    def test_plugin_name(self):
        plugin = {self.class_name}Plugin()
        assert plugin.name == "{self.package_name}"

    def test_plugin_version(self):
        plugin = {self.class_name}Plugin()
        assert plugin.version == "0.1.0"

    def test_setup(self):
        plugin = {self.class_name}Plugin()
        plugin.setup(None)  # type: ignore[arg-type]
"""

    def _ci_yml(self) -> str:
        return """name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --dev
      - run: uv run pytest tests/ -x -q
      - run: uv run ruff check .
"""
