"""Tests for state hash verifier and smart squasher."""

from __future__ import annotations

from unittest.mock import MagicMock

from django.db import models
from django.db.migrations.operations.fields import AddField, RenameField

import pytest

from django_matt.migration_tools.squash import SmartSquasher, SquashPreview
from django_matt.migration_tools.state_hash import HashVerificationResult, StateHashVerifier


class TestStateHashVerifier:
    def test_compute_migration_hash_deterministic(self):
        verifier = StateHashVerifier()
        migration = MagicMock()
        migration.operations = [
            AddField(model_name="user", name="email", field=models.CharField(max_length=100)),
        ]
        h1 = verifier.compute_migration_hash(migration)
        h2 = verifier.compute_migration_hash(migration)
        assert h1 == h2
        assert len(h1) == 16

    def test_different_operations_different_hash(self):
        verifier = StateHashVerifier()
        m1 = MagicMock()
        m1.operations = [
            AddField(model_name="user", name="email", field=models.CharField(max_length=100)),
        ]
        m2 = MagicMock()
        m2.operations = [
            AddField(model_name="user", name="phone", field=models.CharField(max_length=20)),
        ]
        assert verifier.compute_migration_hash(m1) != verifier.compute_migration_hash(m2)

    def test_canonicalize_operation(self):
        op = AddField(model_name="user", name="bio", field=models.TextField())
        canon = StateHashVerifier._canonicalize_operation(op)
        assert "AddField" in canon
        assert "user" in canon
        assert "bio" in canon

    def test_rename_field_canonicalize(self):
        op = RenameField(model_name="user", old_name="email", new_name="primary_email")
        canon = StateHashVerifier._canonicalize_operation(op)
        assert "RenameField" in canon
        assert "email" in canon
        assert "primary_email" in canon


class TestHashVerificationResult:
    def test_valid_result(self):
        r = HashVerificationResult(
            app_label="myapp",
            migration_name="0001",
            expected_hash="abc",
            actual_hash="abc",
            valid=True,
        )
        assert r.valid

    def test_invalid_result(self):
        r = HashVerificationResult(
            app_label="myapp",
            migration_name="0001",
            expected_hash="abc",
            actual_hash="def",
            valid=False,
            message="Hash mismatch",
        )
        assert not r.valid


class TestSquashPreview:
    def test_preview_dataclass(self):
        p = SquashPreview(
            app_label="myapp",
            from_migration="0001",
            to_migration="0010",
            migrations_to_squash=["0001", "0002", "0003"],
            total_operations=15,
            optimized_operations=8,
            has_run_python=False,
            has_run_sql=True,
            warnings=["0003: contains RunSQL"],
        )
        assert len(p.migrations_to_squash) == 3
        assert p.total_operations == 15
        assert p.has_run_sql is True
        assert len(p.warnings) == 1
