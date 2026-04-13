"""Tests for enhanced review analyzers: async_safety, n_plus_one, migration_safety, api_design."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from django_matt.review.analyzers.api_design import APIDesignAnalyzer
from django_matt.review.analyzers.async_safety import AsyncSafetyAnalyzer
from django_matt.review.analyzers.migration_safety import MigrationSafetyAnalyzer
from django_matt.review.analyzers.n_plus_one import NPlusOneAnalyzer
from django_matt.review.config import ReviewConfig
from django_matt.review.findings import Category, Severity


def _analyze(analyzer_cls: type, source: str, *, file_path: str = "test.py", **config_kwargs) -> list:
    tree = ast.parse(source)
    config = ReviewConfig(**config_kwargs)
    analyzer = analyzer_cls(config)
    return analyzer.analyze_file(Path(file_path), tree, source)


def _rule_ids(findings: list) -> set[str]:
    return {f.rule_id for f in findings}


# =========================================================================
# AsyncSafetyAnalyzer
# =========================================================================


class TestAsyncSafetyAnalyzer:
    def test_as001_sync_orm_in_async(self) -> None:
        source = """
async def get_user(user_id):
    user = User.objects.get(pk=user_id)
    return user
"""
        findings = _analyze(AsyncSafetyAnalyzer, source)
        assert "AS001" in _rule_ids(findings)
        assert any(".get()" in f.message for f in findings)

    def test_as001_sync_save_in_async(self) -> None:
        source = """
async def update_user(user):
    user.name = "new"
    user.save()
"""
        findings = _analyze(AsyncSafetyAnalyzer, source)
        assert "AS001" in _rule_ids(findings)

    def test_as001_no_finding_in_sync(self) -> None:
        source = """
def get_user(user_id):
    user = User.objects.get(pk=user_id)
    return user
"""
        findings = _analyze(AsyncSafetyAnalyzer, source)
        assert "AS001" not in _rule_ids(findings)

    def test_as002_time_sleep_in_async(self) -> None:
        source = """
import time

async def slow_handler():
    time.sleep(5)
"""
        findings = _analyze(AsyncSafetyAnalyzer, source)
        assert "AS002" in _rule_ids(findings)

    def test_as002_no_finding_in_sync(self) -> None:
        source = """
import time

def slow_handler():
    time.sleep(5)
"""
        findings = _analyze(AsyncSafetyAnalyzer, source)
        assert "AS002" not in _rule_ids(findings)

    def test_as003_blocking_io_open(self) -> None:
        source = """
async def read_file():
    f = open("data.txt")
    return f.read()
"""
        findings = _analyze(AsyncSafetyAnalyzer, source)
        assert "AS003" in _rule_ids(findings)

    def test_as003_blocking_requests_in_async(self) -> None:
        source = """
import requests

async def fetch_data():
    resp = requests.get("https://api.example.com/data")
    return resp.json()
"""
        findings = _analyze(AsyncSafetyAnalyzer, source)
        assert "AS003" in _rule_ids(findings)

    def test_as004_missing_await_on_async_orm(self) -> None:
        source = """
async def get_user(user_id):
    User.objects.aget(pk=user_id)
"""
        findings = _analyze(AsyncSafetyAnalyzer, source)
        assert "AS004" in _rule_ids(findings)

    def test_no_false_positive_sync_nested_in_async(self) -> None:
        """Sync function nested inside async should not flag."""
        source = """
async def outer():
    def inner():
        User.objects.get(pk=1)
    inner()
"""
        findings = _analyze(AsyncSafetyAnalyzer, source)
        # inner() is sync, so no AS001
        assert "AS001" not in _rule_ids(findings)

    def test_severity_is_error(self) -> None:
        source = """
async def handler():
    User.objects.get(pk=1)
"""
        findings = _analyze(AsyncSafetyAnalyzer, source)
        as001 = [f for f in findings if f.rule_id == "AS001"]
        assert as001
        assert as001[0].severity == Severity.ERROR

    def test_category_is_async_safety(self) -> None:
        source = """
async def handler():
    User.objects.get(pk=1)
"""
        findings = _analyze(AsyncSafetyAnalyzer, source)
        as001 = [f for f in findings if f.rule_id == "AS001"]
        assert as001
        assert as001[0].category == Category.ASYNC_SAFETY


# =========================================================================
# NPlusOneAnalyzer
# =========================================================================


class TestNPlusOneAnalyzer:
    def test_np001_related_field_access_in_loop(self) -> None:
        source = """
def show_orders(orders):
    for order in orders:
        print(order.customer.name)
"""
        findings = _analyze(NPlusOneAnalyzer, source)
        assert "NP001" in _rule_ids(findings)
        assert any("customer" in f.message for f in findings)

    def test_np001_no_finding_with_select_related(self) -> None:
        source = """
def show_orders():
    orders = Order.objects.select_related("customer").all()
    for order in orders:
        print(order.customer.name)
"""
        findings = _analyze(NPlusOneAnalyzer, source)
        # Should not flag because select_related is used
        np001 = [f for f in findings if f.rule_id == "NP001"]
        assert len(np001) == 0

    def test_np002_orm_call_in_loop(self) -> None:
        source = """
def process_items(items):
    for item in items:
        related = RelatedModel.objects.filter(item=item)
"""
        findings = _analyze(NPlusOneAnalyzer, source)
        assert "NP002" in _rule_ids(findings)

    def test_np001_deep_traversal(self) -> None:
        source = """
def show_orders(orders):
    for order in orders:
        print(order.customer.address)
"""
        findings = _analyze(NPlusOneAnalyzer, source)
        assert "NP001" in _rule_ids(findings)

    def test_no_finding_for_simple_attrs(self) -> None:
        """Common model fields like .id, .name should not trigger."""
        source = """
def show_items(items):
    for item in items:
        print(item.id)
        print(item.name)
"""
        findings = _analyze(NPlusOneAnalyzer, source)
        assert "NP001" not in _rule_ids(findings)

    def test_np001_suggestion_content(self) -> None:
        source = """
def show_orders(orders):
    for order in orders:
        print(order.author.email)
"""
        findings = _analyze(NPlusOneAnalyzer, source)
        np001 = [f for f in findings if f.rule_id == "NP001"]
        assert np001
        assert "select_related" in np001[0].suggestion or "prefetch_related" in np001[0].suggestion


# =========================================================================
# MigrationSafetyAnalyzer
# =========================================================================


class TestMigrationSafetyAnalyzer:
    def test_mig001_non_nullable_field_no_default(self) -> None:
        source = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="mymodel",
            name="new_field",
            field=models.CharField(max_length=100),
        ),
    ]
"""
        findings = _analyze(
            MigrationSafetyAnalyzer,
            source,
            file_path="myapp/migrations/0002_add_field.py",
        )
        assert "MIG001" in _rule_ids(findings)

    def test_mig001_no_finding_with_null_true(self) -> None:
        source = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="mymodel",
            name="new_field",
            field=models.CharField(max_length=100, null=True),
        ),
    ]
"""
        findings = _analyze(
            MigrationSafetyAnalyzer,
            source,
            file_path="myapp/migrations/0002_add_field.py",
        )
        assert "MIG001" not in _rule_ids(findings)

    def test_mig001_no_finding_with_default(self) -> None:
        source = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="mymodel",
            name="new_field",
            field=models.CharField(max_length=100, default=""),
        ),
    ]
"""
        findings = _analyze(
            MigrationSafetyAnalyzer,
            source,
            file_path="myapp/migrations/0002_add_field.py",
        )
        assert "MIG001" not in _rule_ids(findings)

    def test_mig002_run_python_without_reverse(self) -> None:
        source = """
from django.db import migrations

def forward(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(forward),
    ]
"""
        findings = _analyze(
            MigrationSafetyAnalyzer,
            source,
            file_path="myapp/migrations/0003_data.py",
        )
        assert "MIG002" in _rule_ids(findings)

    def test_mig002_no_finding_with_reverse(self) -> None:
        source = """
from django.db import migrations

def forward(apps, schema_editor):
    pass

def backward(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(forward, backward),
    ]
"""
        findings = _analyze(
            MigrationSafetyAnalyzer,
            source,
            file_path="myapp/migrations/0003_data.py",
        )
        assert "MIG002" not in _rule_ids(findings)

    def test_mig004_orm_without_using(self) -> None:
        source = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("myapp", "MyModel")
    MyModel.objects.filter(active=True).update(status="migrated")
"""
        findings = _analyze(
            MigrationSafetyAnalyzer,
            source,
            file_path="myapp/migrations/0004_data.py",
        )
        assert "MIG004" in _rule_ids(findings)

    def test_mig004_no_finding_with_using(self) -> None:
        source = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("myapp", "MyModel")
    MyModel.objects.using(schema_editor.connection.alias).filter(active=True).update(status="migrated")
"""
        findings = _analyze(
            MigrationSafetyAnalyzer,
            source,
            file_path="myapp/migrations/0004_data.py",
        )
        assert "MIG004" not in _rule_ids(findings)

    def test_skips_non_migration_files(self) -> None:
        source = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="mymodel",
            name="new_field",
            field=models.CharField(max_length=100),
        ),
    ]
"""
        findings = _analyze(
            MigrationSafetyAnalyzer,
            source,
            file_path="myapp/models.py",
        )
        assert len(findings) == 0


# =========================================================================
# APIDesignAnalyzer
# =========================================================================


class TestAPIDesignAnalyzer:
    def test_api002_missing_pagination(self) -> None:
        source = """
class UserController:
    @api.get("/users")
    def list_users(self):
        return User.objects.all()
"""
        findings = _analyze(APIDesignAnalyzer, source)
        assert "API002" in _rule_ids(findings)

    def test_api003_missing_auth_on_mutation(self) -> None:
        source = """
@api.post("/items")
def create_item(data):
    return Item.objects.create(**data)
"""
        findings = _analyze(APIDesignAnalyzer, source)
        assert "API003" in _rule_ids(findings)

    def test_api003_no_finding_with_auth(self) -> None:
        source = """
@jwt_required
@api.post("/items")
def create_item(data):
    return Item.objects.create(**data)
"""
        findings = _analyze(APIDesignAnalyzer, source)
        assert "API003" not in _rule_ids(findings)

    def test_api004_broad_serialization(self) -> None:
        source = """
class UserSerializer:
    class Meta:
        fields = "__all__"
"""
        findings = _analyze(APIDesignAnalyzer, source)
        assert "API004" in _rule_ids(findings)

    def test_api004_no_finding_with_explicit_fields(self) -> None:
        source = """
class UserSerializer:
    class Meta:
        fields = ["id", "name", "email"]
"""
        findings = _analyze(APIDesignAnalyzer, source)
        assert "API004" not in _rule_ids(findings)

    def test_api005_missing_return_annotation(self) -> None:
        source = """
@api.post("/items")
def create_item(data):
    pass
"""
        findings = _analyze(APIDesignAnalyzer, source)
        assert "API005" in _rule_ids(findings)

    def test_api005_no_finding_with_annotation(self) -> None:
        source = """
@api.post("/items")
def create_item(data) -> ItemSchema:
    pass
"""
        findings = _analyze(APIDesignAnalyzer, source)
        assert "API005" not in _rule_ids(findings)

    def test_api001_inconsistent_trailing_slashes(self) -> None:
        source = """
@api.get("/users/")
def list_users():
    pass

@api.get("/items")
def list_items():
    pass
"""
        findings = _analyze(APIDesignAnalyzer, source)
        assert "API001" in _rule_ids(findings)


# =========================================================================
# JSON Reporter
# =========================================================================


class TestJSONReporter:
    def test_json_output_structure(self) -> None:
        import orjson

        from django_matt.review.findings import Finding, Location, ReviewSummary
        from django_matt.review.reporters.json_reporter import report_json

        summary = ReviewSummary(
            findings=[
                Finding(
                    rule_id="AS001",
                    message="Sync ORM in async",
                    severity=Severity.ERROR,
                    category=Category.ASYNC_SAFETY,
                    location=Location(file="test.py", line=10),
                ),
            ],
            files_analyzed=1,
            analyzers_run=["async_safety"],
            duration_ms=42.0,
        )
        config = ReviewConfig()
        output = report_json(summary, config)
        data = orjson.loads(output)

        assert "summary" in data
        assert "findings" in data
        assert data["summary"]["total_findings"] == 1
        assert data["summary"]["files_analyzed"] == 1
        assert data["findings"][0]["rule_id"] == "AS001"
        assert data["findings"][0]["severity"] == "ERROR"
        assert data["findings"][0]["category"] == "async_safety"

    def test_json_empty_findings(self) -> None:
        import orjson

        from django_matt.review.findings import ReviewSummary
        from django_matt.review.reporters.json_reporter import report_json

        summary = ReviewSummary(files_analyzed=5, analyzers_run=["async_safety"])
        config = ReviewConfig()
        output = report_json(summary, config)
        data = orjson.loads(output)

        assert data["summary"]["total_findings"] == 0
        assert len(data["findings"]) == 0


# =========================================================================
# GitHub Reporter
# =========================================================================


class TestGitHubReporter:
    def test_github_annotation_format(self) -> None:
        import orjson

        from django_matt.review.findings import Finding, Location, ReviewSummary
        from django_matt.review.reporters.github import report_github

        summary = ReviewSummary(
            findings=[
                Finding(
                    rule_id="AS001",
                    message="Sync ORM in async",
                    severity=Severity.ERROR,
                    category=Category.ASYNC_SAFETY,
                    location=Location(file="test.py", line=10),
                    suggestion="Use .aget() instead",
                ),
            ],
            files_analyzed=1,
            analyzers_run=["async_safety"],
        )
        config = ReviewConfig()
        output = report_github(summary, config)
        data = orjson.loads(output)

        assert "body" in data
        assert "comments" in data
        assert data["event"] == "REQUEST_CHANGES"
        assert len(data["comments"]) == 1
        assert data["comments"][0]["path"] == "test.py"
        assert data["comments"][0]["line"] == 10
        assert "AS001" in data["comments"][0]["body"]

    def test_github_no_errors_is_comment(self) -> None:
        import orjson

        from django_matt.review.findings import Finding, Location, ReviewSummary
        from django_matt.review.reporters.github import report_github

        summary = ReviewSummary(
            findings=[
                Finding(
                    rule_id="API001",
                    message="Inconsistent URLs",
                    severity=Severity.HINT,
                    category=Category.API_DESIGN,
                    location=Location(file="test.py", line=1),
                ),
            ],
            files_analyzed=1,
            analyzers_run=["api_design"],
        )
        config = ReviewConfig()
        output = report_github(summary, config)
        data = orjson.loads(output)

        assert data["event"] == "COMMENT"


# =========================================================================
# Severity threshold filtering
# =========================================================================


class TestSeverityFiltering:
    def test_filter_by_min_severity(self) -> None:
        from django_matt.review.findings import Finding, Location, ReviewSummary

        summary = ReviewSummary(
            findings=[
                Finding(
                    rule_id="AS001",
                    message="Error",
                    severity=Severity.ERROR,
                    category=Category.ASYNC_SAFETY,
                    location=Location(file="test.py", line=1),
                ),
                Finding(
                    rule_id="API001",
                    message="Hint",
                    severity=Severity.HINT,
                    category=Category.API_DESIGN,
                    location=Location(file="test.py", line=2),
                ),
                Finding(
                    rule_id="NP001",
                    message="Warning",
                    severity=Severity.WARNING,
                    category=Category.N_PLUS_ONE,
                    location=Location(file="test.py", line=3),
                ),
            ],
        )
        filtered = summary.filter(min_severity=Severity.WARNING)
        assert len(filtered) == 2
        assert all(f.severity >= Severity.WARNING for f in filtered)

    def test_filter_by_category(self) -> None:
        from django_matt.review.findings import Finding, Location, ReviewSummary

        summary = ReviewSummary(
            findings=[
                Finding(
                    rule_id="AS001",
                    message="Async issue",
                    severity=Severity.ERROR,
                    category=Category.ASYNC_SAFETY,
                    location=Location(file="test.py", line=1),
                ),
                Finding(
                    rule_id="NP001",
                    message="N+1 issue",
                    severity=Severity.WARNING,
                    category=Category.N_PLUS_ONE,
                    location=Location(file="test.py", line=2),
                ),
            ],
        )
        filtered = summary.filter(categories={Category.ASYNC_SAFETY})
        assert len(filtered) == 1
        assert filtered[0].rule_id == "AS001"
