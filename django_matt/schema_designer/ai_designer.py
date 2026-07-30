"""
AI-powered schema designer.

Given a natural-language description of desired models, uses an LLM to generate
a complete Django stack: Model, Pydantic Schema, Controller, Service, and Tests.

Usage:
    from django_matt.schema_designer.ai_designer import SchemaDesignerAI

    designer = SchemaDesignerAI()
    result = designer.design("A blog with Posts and Comments")
    # result.files -> dict[str, str] mapping file paths to code content
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django_matt.ai.base import Message, Role

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_SCHEMA_DESIGN_SYSTEM_PROMPT = """You are an expert Django developer specializing in the django-matt framework.

Given a natural-language description, produce a COMPLETE set of files for a Django app using django-matt conventions.

Guidelines:
- Use Django ORM models with proper field types, nullability, and constraints
- Use Pydantic BaseModel for request/response schemas with Field() validation
- Use django_matt's APIController with decorator-based routing (@get, @post, @put, @patch, @delete)
- Use Service classes for business logic, called from Controllers
- Write comprehensive pytest tests using django_matt's test utilities
- Follow django-matt conventions: async controllers, ModelSchema, sync_to_async for ORM
- Include proper imports, docstrings, and type hints throughout
- Use 'from pydantic import BaseModel, Field' for schemas
- Use 'from django_matt import DjangoMattAPI, APIController, get, post, put, delete'
- Use 'from django_matt.core import ModelSchema' for model-based schemas

For each entity (model), generate these files:
1. models.py — Django Model definition
2. schemas.py — Pydantic request/response schemas
3. controller.py — API controller with endpoints
4. service.py — Business logic service layer
5. tests/test_<name>.py — Pytest tests

Merge all entities' code into their respective files (one models.py with all models, etc.).

Respond with a JSON object that maps file paths to file contents:
```json
{
  "files": {
    "models.py": "from django.db import models\\n\\n...",
    "schemas.py": "from pydantic import BaseModel, Field\\n\\n...",
    "controller.py": "from django_matt import ...\\n\\n...",
    "service.py": "...",
    "tests/test_blog.py": "..."
  },
  "app_name": "blog",
  "entities": ["Post", "Comment"]
}
```

IMPORTANT: Output ONLY the JSON object. No markdown fences, no explanatory text. The response must be parseable by json.loads()."""


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class DesignResult:
    """Result of an AI schema design operation."""
    app_name: str
    """Suggested Django app name."""
    entities: list[str]
    """List of entity names generated."""
    files: dict[str, str]
    """Mapping of relative file paths to code content."""
    raw_response: str = ""
    """Raw LLM response for debugging."""
    warnings: list[str] = field(default_factory=list)
    """Warnings encountered during generation."""


# ── Main class ────────────────────────────────────────────────────────────────


class SchemaDesignerAI:
    """AI-powered schema designer using an LLM provider."""

    def __init__(
        self,
        provider_name: str = "openai",
        model: str | None = None,
        temperature: float = 0.3,
        api_key: str | None = None,
        **provider_kwargs: Any,
    ):
        self.provider_name = provider_name
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.provider_kwargs = provider_kwargs

    def design(
        self,
        description: str,
        *,
        app_name: str | None = None,
        existing_schema: str = "",
    ) -> DesignResult:
        """Generate a complete Django app from a natural-language description.

        Args:
            description: Natural-language description of desired models and their fields.
            app_name: Optional app name hint. If omitted, the LLM will suggest one.
            existing_schema: Optional existing schema text for context.

        Returns:
            DesignResult with generated files and metadata.
        """
        user_prompt = self._build_user_prompt(description, app_name, existing_schema)

        messages = [
            Message.system(_SCHEMA_DESIGN_SYSTEM_PROMPT),
            Message.user(user_prompt),
        ]

        response_text = self._call_llm(messages)

        return self._parse_response(response_text, description)

    # ── Private helpers ───────────────────────────────────────────────────

    def _build_user_prompt(
        self,
        description: str,
        app_name: str | None,
        existing_schema: str,
    ) -> str:
        parts = [f"Design a Django app with these models:\n\n{description}"]

        if app_name:
            parts.append(f"\nUse the app name: {app_name}")

        if existing_schema:
            parts.append(f"\nExisting schema for context:\n{existing_schema}")

        parts.append(
            "\n\nGenerate the full implementation as a JSON object with file paths "
            "and contents. Follow django-matt conventions exactly."
        )
        return "\n".join(parts)

    def _call_llm(self, messages: list[Message]) -> str:
        """Call the LLM provider and return the response text."""
        try:
            from django_matt.ai import get_provider
        except ImportError:
            raise RuntimeError(
                "django_matt.ai is not available. Ensure the AI module is installed."
            )

        kwargs: dict[str, Any] = {}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.model:
            kwargs["model"] = self.model
        kwargs.update(self.provider_kwargs)

        llm = get_provider(self.provider_name, **kwargs)

        response = llm.complete_sync(
            messages,
            temperature=self.temperature,
            max_tokens=4096,
        )

        content = response.content or ""
        logger.debug("LLM response length: %d characters", len(content))
        return content

    def _parse_response(self, text: str, description: str) -> DesignResult:
        """Parse the LLM response into a DesignResult."""
        warnings: list[str] = []

        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Try to extract JSON from the response
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                try:
                    data = json.loads(match.group())
                    warnings.append("Response required JSON extraction; some content may be lost.")
                except json.JSONDecodeError:
                    raise ValueError(
                        f"LLM response was not valid JSON. "
                        f"Parse error: {e}\nResponse preview: {text[:500]}"
                    ) from e
            else:
                raise ValueError(
                    f"LLM response contained no JSON object. "
                    f"Response preview: {text[:500]}"
                ) from e

        files = data.get("files", {})
        app_name = data.get("app_name", "app")
        entities = data.get("entities", [])

        if not files:
            warnings.append("No files were generated by the LLM.")
        if not entities:
            # Infer entities from files
            import re as _re

            model_names: list[str] = []
            for content in files.values():
                found = _re.findall(r"class (\w+)\(models\.Model\)", content)
                model_names.extend(found)
            entities = sorted(set(model_names))
            if entities:
                warnings.append("Entities inferred from generated model classes.")

        return DesignResult(
            app_name=app_name,
            entities=entities,
            files=files,
            raw_response=text,
            warnings=warnings,
        )


# ── Convenience function ──────────────────────────────────────────────────────


def design_schema(
    description: str,
    *,
    app_name: str | None = None,
    provider: str = "openai",
    model: str | None = None,
    existing_schema: str = "",
    output_dir: Path | None = None,
    **kwargs: Any,
) -> DesignResult:
    """Convenience function: design a schema and optionally write files to disk.

    Args:
        description: Natural-language description of desired models.
        app_name: Optional app name hint.
        provider: LLM provider name (default: "openai").
        model: Optional model override.
        existing_schema: Optional existing schema for context.
        output_dir: If provided, write generated files to this directory.
        **kwargs: Additional provider kwargs.

    Returns:
        DesignResult with generated files and metadata.
    """
    designer = SchemaDesignerAI(provider_name=provider, model=model, **kwargs)
    result = designer.design(description, app_name=app_name, existing_schema=existing_schema)

    if output_dir:
        _write_files(result, output_dir)

    return result


def _write_files(result: DesignResult, output_dir: Path) -> None:
    """Write generated files to disk."""
    output_dir = Path(output_dir)
    for filepath, content in result.files.items():
        full_path = output_dir / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        logger.info("Wrote %s (%d bytes)", full_path, len(content))
