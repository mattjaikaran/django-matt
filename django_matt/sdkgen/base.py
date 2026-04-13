"""SDK generator base classes and configuration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SDKConfig:
    """Configuration for SDK generation."""

    package_name: str
    version: str = "0.1.0"
    base_url: str = "http://localhost:8000"
    auth_type: str = "jwt"  # jwt, api_key, oauth
    output_dir: Path = field(default_factory=lambda: Path("./sdk"))
    include_models: bool = True
    include_client: bool = True
    include_tests: bool = True
    description: str = ""
    author: str = ""
    license: str = "MIT"

    def __post_init__(self) -> None:
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)


@dataclass
class SDKOutput:
    """Generated SDK output — files ready to write to disk."""

    files: dict[str, str]  # relative path -> content
    package_config: str  # package.json / pyproject.toml / Package.swift
    target: str  # typescript, python, swift

    def write_to_disk(self, output_dir: Path | None = None) -> list[Path]:
        """Write all generated files to the output directory."""
        base = output_dir or Path()
        written: list[Path] = []
        for rel_path, content in self.files.items():
            full_path = base / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            written.append(full_path)
        return written


class SDKGenerator(ABC):
    """Abstract base for SDK generators."""

    target: str  # "typescript", "python", "swift"

    @abstractmethod
    def generate(self, api_schema: dict[str, Any], config: SDKConfig) -> SDKOutput:
        """Generate a complete SDK package from an OpenAPI schema."""
        ...
