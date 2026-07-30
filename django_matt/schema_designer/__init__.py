from __future__ import annotations

from django_matt.schema_designer.analyzer import (
    FieldIssue,
    ModelReport,
    SchemaAnalyzer,
    SchemaReport,
)
from django_matt.schema_designer.optimizer import (
    DenormSuggestion,
    IndexSuggestion,
    NPlusOneWarning,
    SchemaOptimizer,
)
from django_matt.schema_designer.prompts import (
    generate_migration_prompt,
    generate_review_prompt,
    generate_schema_prompt,
)
from django_matt.schema_designer.ai_designer import (
    DesignResult,
    SchemaDesignerAI,
    design_schema,
)
from django_matt.schema_designer.visualizer import (
    generate_dbml,
    generate_dot,
    generate_mermaid,
    generate_plantuml,
)

__all__ = [
    "DenormSuggestion",
    "DesignResult",
    "FieldIssue",
    "IndexSuggestion",
    "ModelReport",
    "NPlusOneWarning",
    "SchemaAnalyzer",
    "SchemaDesignerAI",
    "SchemaOptimizer",
    "SchemaReport",
    "design_schema",
    "generate_dbml",
    "generate_dot",
    "generate_mermaid",
    "generate_migration_prompt",
    "generate_plantuml",
    "generate_review_prompt",
    "generate_schema_prompt",
]
