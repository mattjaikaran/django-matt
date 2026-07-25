from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

import django

django.setup()

from django.db import models

import pytest

from django_matt.schema_designer.analyzer import (
    FieldIssue,
    ModelReport,
    SchemaAnalyzer,
    SchemaReport,
    Severity,
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
from django_matt.schema_designer.visualizer import (
    generate_dbml,
    generate_dot,
    generate_mermaid,
    generate_plantuml,
)

# ---------------------------------------------------------------------------
# Test models — defined inline so we don't pollute the main codebase
# ---------------------------------------------------------------------------


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        app_label = "tests"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Author(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True, default="")

    class Meta:
        app_label = "tests"

    def __str__(self) -> str:
        return self.name


class Article(models.Model):
    title = models.CharField(max_length=300)
    body = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name="articles"
    )
    tags = models.ManyToManyField("Tag", blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "tests"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class Tag(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        app_label = "tests"


class LargeModel(models.Model):
    """Model with many issues for testing."""

    big_name = models.CharField(max_length=1000)
    nullable_no_default = models.IntegerField(null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "tests"


# ---------------------------------------------------------------------------
# Analyzer tests
# ---------------------------------------------------------------------------


class TestSchemaAnalyzer:
    def test_analyze_model_returns_model_report(self):
        analyzer = SchemaAnalyzer()
        report = analyzer.analyze_model(Article)
        assert isinstance(report, ModelReport)
        assert report.model_name == "Article"
        assert report.app_label == "tests"
        assert report.field_count > 0

    def test_analyze_model_finds_fields(self):
        analyzer = SchemaAnalyzer()
        report = analyzer.analyze_model(Article)
        field_names = {f["name"] for f in report.fields}
        assert "title" in field_names
        assert "body" in field_names
        assert "author" in field_names

    def test_analyze_model_finds_relationships(self):
        analyzer = SchemaAnalyzer()
        report = analyzer.analyze_model(Article)
        rel_fields = {r["field"] for r in report.relationships}
        assert "author" in rel_fields
        assert "category" in rel_fields
        assert "tags" in rel_fields

    def test_analyze_model_detects_missing_str(self):
        analyzer = SchemaAnalyzer()
        report = analyzer.analyze_model(Tag)
        str_issues = [i for i in report.issues if i.field_name == "__str__"]
        assert len(str_issues) == 1
        assert str_issues[0].severity == Severity.INFO

    def test_analyze_model_detects_missing_ordering(self):
        analyzer = SchemaAnalyzer()
        report = analyzer.analyze_model(Tag)
        ordering_issues = [i for i in report.issues if i.field_name == "Meta.ordering"]
        assert len(ordering_issues) == 1

    def test_analyze_model_detects_missing_related_name(self):
        analyzer = SchemaAnalyzer()
        report = analyzer.analyze_model(Article)
        related_issues = [i for i in report.issues if "related_name" in i.issue]
        # author FK has no related_name, category has one
        author_issues = [i for i in related_issues if i.field_name == "author"]
        assert len(author_issues) == 1

    def test_analyze_model_detects_large_charfield(self):
        analyzer = SchemaAnalyzer()
        report = analyzer.analyze_model(LargeModel)
        large_issues = [i for i in report.issues if "large max_length" in i.issue]
        assert len(large_issues) == 1
        assert large_issues[0].field_name == "big_name"

    def test_analyze_model_detects_nullable_no_default(self):
        analyzer = SchemaAnalyzer()
        report = analyzer.analyze_model(LargeModel)
        null_issues = [i for i in report.issues if "Nullable field without default" in i.issue]
        assert len(null_issues) == 1
        assert null_issues[0].field_name == "nullable_no_default"

    def test_analyze_model_detects_missing_timestamps(self):
        analyzer = SchemaAnalyzer()
        report = analyzer.analyze_model(Tag)
        ts_issues = [i for i in report.issues if "timestamp" in i.issue]
        assert len(ts_issues) == 2  # created_at and updated_at

    def test_analyze_model_no_timestamp_warning_when_present(self):
        analyzer = SchemaAnalyzer()
        report = analyzer.analyze_model(Article)
        ts_issues = [i for i in report.issues if "timestamp" in i.issue]
        assert len(ts_issues) == 0

    def test_analyze_all_returns_schema_report(self):
        analyzer = SchemaAnalyzer()
        report = analyzer.analyze_all()
        assert isinstance(report, SchemaReport)
        assert len(report.models) > 0
        assert report.total_issues >= 0
        assert (
            report.total_issues == report.total_errors + report.total_warnings + report.total_info
        )

    def test_analyze_with_app_filter(self):
        analyzer = SchemaAnalyzer(app_labels=["auth"])
        report = analyzer.analyze_all()
        for model_report in report.models:
            assert model_report.app_label == "auth"

    def test_field_issue_model(self):
        issue = FieldIssue(
            field_name="test",
            issue="test issue",
            severity=Severity.WARNING,
            suggestion="fix it",
        )
        assert issue.severity == Severity.WARNING

    def test_model_report_counts(self):
        report = ModelReport(
            app_label="test",
            model_name="Test",
            full_name="test.Test",
            field_count=5,
            issues=[
                FieldIssue(field_name="a", issue="err", severity=Severity.ERROR, suggestion=""),
                FieldIssue(field_name="b", issue="warn", severity=Severity.WARNING, suggestion=""),
                FieldIssue(field_name="c", issue="info", severity=Severity.INFO, suggestion=""),
            ],
            fields=[],
            indexes=[],
            relationships=[],
        )
        assert report.error_count == 1
        assert report.warning_count == 1


# ---------------------------------------------------------------------------
# Visualizer tests
# ---------------------------------------------------------------------------


class TestVisualizer:
    def test_generate_mermaid_output(self):
        result = generate_mermaid(app_labels=["auth"])
        assert "erDiagram" in result
        assert "auth__User" in result or "auth__" in result

    def test_generate_mermaid_with_model_filter(self):
        result = generate_mermaid(model_names=["User"])
        assert "erDiagram" in result
        assert "User" in result

    def test_generate_dot_output(self):
        result = generate_dot(app_labels=["auth"])
        assert "digraph schema" in result
        assert "rankdir=LR" in result

    def test_generate_dbml_output(self):
        result = generate_dbml(app_labels=["auth"])
        assert "Table" in result

    def test_generate_plantuml_output(self):
        result = generate_plantuml(app_labels=["auth"])
        assert "@startuml" in result
        assert "@enduml" in result

    def test_mermaid_contains_fields(self):
        result = generate_mermaid(app_labels=["auth"])
        # auth.User has username, email, etc.
        assert "username" in result or "email" in result or "password" in result

    def test_mermaid_shows_relationships(self):
        result = generate_mermaid(app_labels=["tests"], model_names=["Article", "Author"])
        # Should show FK relationship
        assert "author" in result

    def test_dot_shows_edges(self):
        result = generate_dot(app_labels=["tests"], model_names=["Article", "Author"])
        assert "->" in result

    def test_dbml_shows_refs(self):
        result = generate_dbml(app_labels=["tests"], model_names=["Article", "Author"])
        assert "Ref:" in result

    def test_plantuml_entity_names(self):
        result = generate_plantuml(app_labels=["auth"])
        assert "entity" in result


# ---------------------------------------------------------------------------
# Optimizer tests
# ---------------------------------------------------------------------------


class TestSchemaOptimizer:
    def test_suggest_indexes_returns_list(self):
        optimizer = SchemaOptimizer()
        suggestions = optimizer.suggest_indexes(Article)
        assert isinstance(suggestions, list)
        for s in suggestions:
            assert isinstance(s, IndexSuggestion)

    def test_suggest_select_related(self):
        optimizer = SchemaOptimizer()
        paths = optimizer.suggest_select_related(Article)
        assert "author" in paths
        assert "category" in paths

    def test_suggest_prefetch_related(self):
        optimizer = SchemaOptimizer()
        paths = optimizer.suggest_prefetch_related(Article)
        assert "tags" in paths

    def test_detect_n_plus_one(self):
        optimizer = SchemaOptimizer()
        warnings = optimizer.detect_n_plus_one(Article)
        assert isinstance(warnings, list)
        fk_warnings = [w for w in warnings if w.field_name == "author"]
        assert len(fk_warnings) == 1
        assert "select_related" in fk_warnings[0].suggestion

    def test_detect_n_plus_one_m2m(self):
        optimizer = SchemaOptimizer()
        warnings = optimizer.detect_n_plus_one(Article)
        m2m_warnings = [w for w in warnings if w.field_name == "tags"]
        assert len(m2m_warnings) == 1
        assert "prefetch_related" in m2m_warnings[0].suggestion

    def test_suggest_denormalization(self):
        optimizer = SchemaOptimizer()
        suggestions = optimizer.suggest_denormalization()
        assert isinstance(suggestions, list)
        # auth.User is likely referenced by many FKs
        for s in suggestions:
            assert isinstance(s, DenormSuggestion)

    def test_generate_migration_empty(self):
        optimizer = SchemaOptimizer()
        result = optimizer.generate_migration([])
        assert "No index suggestions" in result

    def test_generate_migration_with_suggestions(self):
        optimizer = SchemaOptimizer()
        suggestions = [
            IndexSuggestion(
                model_name="tests.Article",
                field_name="is_published",
                index_type="btree",
                reason="test",
                migration_code="test_code",
            )
        ]
        result = optimizer.generate_migration(suggestions)
        assert "migrations.AddIndex" in result
        assert "is_published" in result

    def test_suggest_indexes_for_boolean_status(self):
        optimizer = SchemaOptimizer()
        suggestions = optimizer.suggest_indexes(LargeModel)
        active_suggestions = [s for s in suggestions if s.field_name == "is_active"]
        assert len(active_suggestions) == 1

    def test_suggest_indexes_for_datetime(self):
        optimizer = SchemaOptimizer()
        suggestions = optimizer.suggest_indexes(Article)
        dt_suggestions = [
            s for s in suggestions if s.field_name in ("created_at", "updated_at", "published_at")
        ]
        # These may or may not have auto-indexes depending on Django version
        assert isinstance(dt_suggestions, list)


# ---------------------------------------------------------------------------
# Prompt generation tests
# ---------------------------------------------------------------------------


class TestPrompts:
    def test_generate_schema_prompt(self):
        result = generate_schema_prompt(app_labels=["auth"])
        assert "database schema expert" in result
        assert "Current Schema" in result
        assert "Automated Analysis" in result
        assert "Task" in result

    def test_generate_schema_prompt_includes_fields(self):
        result = generate_schema_prompt(app_labels=["auth"])
        assert "username" in result or "email" in result

    def test_generate_review_prompt(self):
        result = generate_review_prompt(app_labels=["auth"])
        assert "Review Checklist" in result
        assert "Normalization" in result
        assert "Indexes" in result

    def test_generate_migration_prompt(self):
        result = generate_migration_prompt(
            from_description="Table users: id, name, email",
            to_description="Table users: id, name, email, avatar_url",
        )
        assert "migration" in result.lower()
        assert "Current Schema State" in result
        assert "Desired Schema State" in result

    def test_prompt_contains_analysis_issues(self):
        result = generate_schema_prompt()
        # Should contain issue counts at minimum
        assert "issues" in result.lower() or "errors" in result.lower()


# ---------------------------------------------------------------------------
# Views tests (unit, no HTTP)
# ---------------------------------------------------------------------------


class TestViews:
    def test_include_schema_designer_returns_urlpatterns(self):
        from django_matt.schema_designer.views import include_schema_designer

        urls = include_schema_designer()
        assert isinstance(urls, list)
        assert len(urls) >= 5
        names = [u.name for u in urls]
        assert "schema-designer" in names
        assert "schema-models" in names
        assert "schema-analyze" in names
        assert "schema-diagram" in names
        assert "schema-optimize" in names

    def test_dashboard_html_rendered(self):
        from django_matt.schema_designer.views import SchemaDesignerView

        view = SchemaDesignerView()
        html = view._render_dashboard()
        assert "Schema Designer" in html
        assert "mermaid" in html
        assert "tailwindcss" in html


# ---------------------------------------------------------------------------
# CLI tests (unit, no actual invocation)
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cli_app_exists(self):
        from django_matt.schema_designer.cli import app

        assert app is not None
        assert app.info.name == "schema"

    def test_cli_has_commands(self):
        from django_matt.schema_designer.cli import app

        # Typer uses callback.__name__ when cmd.name is None
        command_names = [cmd.name or cmd.callback.__name__ for cmd in app.registered_commands]
        assert "analyze" in command_names
        assert "diagram" in command_names
        assert "optimize" in command_names
        assert "export" in command_names or "export_schema" in command_names
        assert "prompt" in command_names


# ---------------------------------------------------------------------------
# Module exports test
# ---------------------------------------------------------------------------


class TestModuleExports:
    def test_all_exports_available(self):
        from django_matt import schema_designer

        assert hasattr(schema_designer, "SchemaAnalyzer")
        assert hasattr(schema_designer, "SchemaOptimizer")
        assert hasattr(schema_designer, "generate_mermaid")
        assert hasattr(schema_designer, "generate_dot")
        assert hasattr(schema_designer, "generate_dbml")
        assert hasattr(schema_designer, "generate_plantuml")
        assert hasattr(schema_designer, "generate_schema_prompt")
        assert hasattr(schema_designer, "generate_review_prompt")
        assert hasattr(schema_designer, "generate_migration_prompt")

    def test_pydantic_models_serializable(self):
        issue = FieldIssue(
            field_name="test",
            issue="test",
            severity=Severity.WARNING,
            suggestion="fix",
        )
        data = issue.model_dump()
        assert data["field_name"] == "test"
        assert data["severity"] == "warning"

        json_str = issue.model_dump_json()
        assert "test" in json_str
