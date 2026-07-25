"""Tests for API evolution tracker and schema transforms."""

from __future__ import annotations

import pytest

from django_matt.versioning.evolution.tracker import APIEvolutionTracker
from django_matt.versioning.evolution.transforms import (
    AddField,
    RemoveField,
    RenameField,
    TransformChain,
)


class TestRenameField:
    def test_forward(self):
        t = RenameField(old="username", new="handle")
        assert t.forward({"username": "matt"}) == {"handle": "matt"}

    def test_backward(self):
        t = RenameField(old="username", new="handle")
        assert t.backward({"handle": "matt"}) == {"username": "matt"}

    def test_missing_field_is_noop(self):
        t = RenameField(old="username", new="handle")
        assert t.forward({"email": "m@e.com"}) == {"email": "m@e.com"}


class TestAddField:
    def test_forward_adds_default(self):
        t = AddField(field="avatar_url", default=None)
        assert t.forward({}) == {"avatar_url": None}

    def test_forward_preserves_existing(self):
        t = AddField(field="avatar_url", default=None)
        assert t.forward({"avatar_url": "http://..."}) == {"avatar_url": "http://..."}

    def test_backward_removes(self):
        t = AddField(field="avatar_url")
        assert t.backward({"avatar_url": "http://...", "name": "Matt"}) == {"name": "Matt"}


class TestRemoveField:
    def test_forward_removes(self):
        t = RemoveField(field="legacy")
        assert t.forward({"legacy": True, "name": "Matt"}) == {"name": "Matt"}

    def test_backward_restores_default(self):
        t = RemoveField(field="legacy", default=False)
        assert t.backward({"name": "Matt"}) == {"name": "Matt", "legacy": False}


class TestTransformChain:
    def test_forward_applies_in_order(self):
        chain = TransformChain(
            [
                RenameField(old="username", new="handle"),
                AddField(field="verified", default=False),
            ]
        )
        result = chain.forward({"username": "matt"})
        assert result == {"handle": "matt", "verified": False}

    def test_backward_applies_in_reverse(self):
        chain = TransformChain(
            [
                RenameField(old="username", new="handle"),
                AddField(field="verified", default=False),
            ]
        )
        result = chain.backward({"handle": "matt", "verified": True})
        assert result == {"username": "matt"}

    def test_add_fluent(self):
        chain = TransformChain()
        chain.add(RenameField(old="a", new="b")).add(AddField(field="c"))
        assert len(chain.transforms) == 2


class TestAPIEvolutionTracker:
    def test_no_transforms_for_current_version(self):
        tracker = APIEvolutionTracker()
        tracker.register_schema_change(
            "/users/{id}", "2026-04", [RenameField(old="username", new="handle")]
        )
        # Client on same version — no transform
        data = tracker.transform_response("/users/{id}", "2026-04", {"handle": "matt"})
        assert data == {"handle": "matt"}

    def test_backward_transform_for_old_client(self):
        tracker = APIEvolutionTracker()
        tracker.register_schema_change(
            "/users/{id}", "2026-04", [RenameField(old="username", new="handle")]
        )
        # Client on older version
        data = tracker.transform_response("/users/{id}", "2026-03", {"handle": "matt"})
        assert data == {"username": "matt"}

    def test_multiple_version_changes(self):
        tracker = APIEvolutionTracker()
        tracker.register_schema_change(
            "/users/{id}", "2026-03", [RenameField(old="email", new="primary_email")]
        )
        tracker.register_schema_change(
            "/users/{id}", "2026-04", [AddField(field="avatar", default=None)]
        )
        # Client on 2026-02 sees both transforms reversed
        data = tracker.transform_response(
            "/users/{id}", "2026-02", {"primary_email": "m@e.com", "avatar": "http://..."}
        )
        assert "email" in data
        assert "primary_email" not in data
        assert "avatar" not in data

    def test_forward_transform_request(self):
        tracker = APIEvolutionTracker()
        tracker.register_schema_change(
            "/users/{id}", "2026-04", [RenameField(old="username", new="handle")]
        )
        # Old client sends old field name
        data = tracker.transform_request("/users/{id}", "2026-03", {"username": "matt"})
        assert data == {"handle": "matt"}

    def test_none_version_is_noop(self):
        tracker = APIEvolutionTracker()
        tracker.register_schema_change("/users/{id}", "2026-04", [RenameField(old="a", new="b")])
        data = tracker.transform_response("/users/{id}", None, {"b": 1})
        assert data == {"b": 1}

    def test_get_changes(self):
        tracker = APIEvolutionTracker()
        tracker.register_schema_change("/users/{id}", "2026-03", [])
        tracker.register_schema_change("/users/{id}", "2026-04", [])
        tracker.register_schema_change("/posts/{id}", "2026-04", [])

        all_changes = tracker.get_changes()
        assert len(all_changes) == 3

        user_changes = tracker.get_changes("/users/{id}")
        assert len(user_changes) == 2

    def test_path_normalization(self):
        tracker = APIEvolutionTracker()
        tracker.register_schema_change("/users/{id}", "2026-04", [RenameField(old="a", new="b")])
        # Different param name should still match
        data = tracker.transform_response("/users/{user_id}", "2026-03", {"b": 1})
        assert data == {"a": 1}
