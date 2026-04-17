"""Tests for django_matt.migrations — advisor, rewriters, and graph renderer."""

from __future__ import annotations

from collections import defaultdict
from unittest.mock import MagicMock

import pytest
from django.db import models
from django.db.migrations.operations.fields import AddField, RenameField
from django.db.migrations.operations.models import AddIndex

from django_matt.migrations.advisor import MigrationAdvisor, MigrationIssue
from django_matt.migrations.graph import MigrationConflict, MigrationGraphRenderer
from django_matt.migrations.rewriters.base import Severity
from django_matt.migrations.rewriters.concurrent import ConcurrentIndexRewriter
from django_matt.migrations.rewriters.non_nullable import AddNonNullableRewriter
from django_matt.migrations.rewriters.rename import RenameFieldRewriter


# ──────────────────────────────────────────────
# AddNonNullableRewriter
# ────���─────────────────────────────────────────


class TestAddNonNullableRewriter:
    def test_detects_non_nullable_with_default(self):
        rw = AddNonNullableRewriter()
        field = models.BooleanField(default=False)
        op = AddField(model_name="user", name="verified", field=field)
        assert rw.can_handle(op) is True

    def test_ignores_nullable_field(self):
        rw = AddNonNullableRewriter()
        field = models.CharField(max_length=100, null=True)
        op = AddField(model_name="user", name="bio", field=field)
        assert rw.can_handle(op) is False

    def test_ignores_field_without_default(self):
        rw = AddNonNullableRewriter()
        field = models.CharField(max_length=100, null=True)
        op = AddField(model_name="user", name="name", field=field)
        assert rw.can_handle(op) is False

    def test_rewrite_produces_3_steps(self):
        rw = AddNonNullableRewriter()
        field = models.BooleanField(default=False)
        op = AddField(model_name="user", name="verified", field=field)
        result = rw.rewrite(op, "myapp", "user")

        assert len(result.steps) == 3
        assert "NULL" in result.steps[0].sql
        assert "UPDATE" in result.steps[1].sql
        assert "NOT NULL" in result.steps[2].sql

    def test_rewrite_includes_table_name(self):
        rw = AddNonNullableRewriter()
        field = models.IntegerField(default=0)
        op = AddField(model_name="product", name="stock", field=field)
        result = rw.rewrite(op, "shop", "product")

        assert "shop_product" in result.steps[0].sql

    def test_rewrite_varchar_type(self):
        rw = AddNonNullableRewriter()
        field = models.CharField(max_length=50, default="")
        op = AddField(model_name="item", name="sku", field=field)
        result = rw.rewrite(op, "app", "item")

        assert "varchar" in result.steps[0].sql.lower()


# ────────────────────────────��─────────────────
# ConcurrentIndexRewriter
# ─────────────────────────────��────────────────


class TestConcurrentIndexRewriter:
    def test_detects_add_index(self):
        rw = ConcurrentIndexRewriter()
        index = models.Index(fields=["email"], name="idx_email")
        op = AddIndex(model_name="user", index=index)
        assert rw.can_handle(op) is True

    def test_rewrite_uses_concurrently(self):
        rw = ConcurrentIndexRewriter()
        index = models.Index(fields=["email"], name="idx_email")
        op = AddIndex(model_name="user", index=index)
        result = rw.rewrite(op, "myapp", "user")

        assert any("CONCURRENTLY" in s.sql for s in result.steps if s.sql)
        assert any("atomic" in s.sql.lower() for s in result.steps if s.sql)

    def test_detects_runsql_create_index(self):
        from django.db.migrations.operations.special import RunSQL

        rw = ConcurrentIndexRewriter()
        op = RunSQL("CREATE INDEX idx_foo ON bar (baz);")
        assert rw.can_handle(op) is True

    def test_ignores_runsql_with_concurrently(self):
        from django.db.migrations.operations.special import RunSQL

        rw = ConcurrentIndexRewriter()
        op = RunSQL("CREATE INDEX CONCURRENTLY idx_foo ON bar (baz);")
        assert rw.can_handle(op) is False


# ───────────────────────���──────────────────────
# RenameFieldRewriter
# ��─────────────────────────────────────────────


class TestRenameFieldRewriter:
    def test_detects_rename(self):
        rw = RenameFieldRewriter()
        op = RenameField(model_name="user", old_name="email", new_name="primary_email")
        assert rw.can_handle(op) is True

    def test_rewrite_produces_5_steps(self):
        rw = RenameFieldRewriter()
        op = RenameField(model_name="user", old_name="email", new_name="primary_email")
        result = rw.rewrite(op, "myapp", "user")

        assert len(result.steps) == 5
        assert "primary_email" in result.steps[0].sql
        assert "dualwrite" in result.steps[1].sql
        assert "UPDATE" in result.steps[2].sql
        assert "DROP" in result.steps[4].sql


# ─���────────────────────────────────────────────
# MigrationAdvisor
# ─────────────────────────────────���────────────


class TestMigrationAdvisor:
    def test_analyze_operations_finds_issues(self):
        advisor = MigrationAdvisor()
        ops = [
            AddField(
                model_name="user",
                name="verified",
                field=models.BooleanField(default=False),
            ),
            RenameField(
                model_name="user",
                old_name="email",
                new_name="primary_email",
            ),
        ]
        issues = advisor.analyze_operations(ops, app_label="myapp")
        assert len(issues) == 2
        assert all(isinstance(i, MigrationIssue) for i in issues)
        assert all(i.rewrite is not None for i in issues)

    def test_analyze_operations_no_issues(self):
        advisor = MigrationAdvisor()
        ops = [
            AddField(
                model_name="user",
                name="bio",
                field=models.CharField(max_length=200, null=True, blank=True),
            ),
        ]
        issues = advisor.analyze_operations(ops)
        assert len(issues) == 0

    def test_severity_is_warning(self):
        advisor = MigrationAdvisor()
        ops = [
            AddField(
                model_name="user",
                name="active",
                field=models.BooleanField(default=True),
            ),
        ]
        issues = advisor.analyze_operations(ops)
        assert issues[0].severity == Severity.WARNING


# ─���────────────────────────���───────────────────
# MigrationGraphRenderer
# ───────────────��──────────────────────────────


class _FakeNode:
    def __init__(self, key, parents=None):
        self.key = key
        self.parents = parents or []


class _FakeGraph:
    def __init__(self, nodes_and_parents):
        self.node_map = {}
        for key, parents in nodes_and_parents:
            self.node_map[key] = _FakeNode(key, parents)


class TestMigrationGraphRenderer:
    def _make_graph(self, nodes_and_parents):
        return _FakeGraph(nodes_and_parents)

    def test_render_ascii_simple(self):
        graph = self._make_graph([
            (("myapp", "0001_initial"), []),
            (("myapp", "0002_add_email"), [("myapp", "0001_initial")]),
        ])
        renderer = MigrationGraphRenderer()
        output = renderer.render_ascii(graph)
        assert "myapp" in output
        assert "0001_initial" in output
        assert "0002_add_email" in output

    def test_render_ascii_cross_app(self):
        graph = self._make_graph([
            (("auth", "0001_initial"), []),
            (("myapp", "0001_initial"), [("auth", "0001_initial")]),
        ])
        renderer = MigrationGraphRenderer()
        output = renderer.render_ascii(graph)
        assert "depends on" in output

    def test_render_dot(self):
        graph = self._make_graph([
            (("myapp", "0001_initial"), []),
            (("myapp", "0002_add_email"), [("myapp", "0001_initial")]),
        ])
        renderer = MigrationGraphRenderer()
        output = renderer.render_dot(graph)
        assert "digraph" in output
        assert "myapp__0001_initial" in output
        assert "->" in output

    def test_render_mermaid(self):
        graph = self._make_graph([
            (("myapp", "0001_initial"), []),
            (("myapp", "0002_add_email"), [("myapp", "0001_initial")]),
        ])
        renderer = MigrationGraphRenderer()
        output = renderer.render_mermaid(graph)
        assert "graph BT" in output
        assert "-->" in output

    def test_filter_by_app(self):
        graph = self._make_graph([
            (("auth", "0001_initial"), []),
            (("myapp", "0001_initial"), []),
        ])
        renderer = MigrationGraphRenderer()
        output = renderer.render_ascii(graph, app_label="myapp")
        assert "myapp" in output
        assert "auth" not in output

    def test_empty_graph(self):
        graph = self._make_graph([])
        renderer = MigrationGraphRenderer()
        output = renderer.render_ascii(graph)
        assert "no migrations" in output

    def test_detect_cycles_none(self):
        graph = self._make_graph([
            (("app", "0001"), []),
            (("app", "0002"), [("app", "0001")]),
        ])
        renderer = MigrationGraphRenderer()
        cycles = renderer.detect_cycles(graph)
        assert cycles == []

    def test_detect_cycles_found(self):
        # Simulate a cycle: 0001 → 0002 → 0001
        graph = self._make_graph([
            (("app", "0001"), [("app", "0002")]),
            (("app", "0002"), [("app", "0001")]),
        ])
        renderer = MigrationGraphRenderer()
        cycles = renderer.detect_cycles(graph)
        assert len(cycles) > 0

    def test_find_conflicts_none(self):
        graph = self._make_graph([
            (("app", "0001"), []),
            (("app", "0002"), [("app", "0001")]),
        ])
        renderer = MigrationGraphRenderer()
        conflicts = renderer.find_conflicts(graph)
        assert conflicts == []

    def test_find_conflicts_detected(self):
        # Two leaf nodes in same app = conflict
        graph = self._make_graph([
            (("app", "0001"), []),
            (("app", "0002_alice"), [("app", "0001")]),
            (("app", "0002_bob"), [("app", "0001")]),
        ])
        renderer = MigrationGraphRenderer()
        conflicts = renderer.find_conflicts(graph)
        assert len(conflicts) == 1
        assert conflicts[0].app_label == "app"
        assert set(conflicts[0].leaves) == {"0002_alice", "0002_bob"}
