"""Tests for stateful hot-reload system."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from django_matt.dev.stateful_reload import (
    ConsumerState,
    ReloadSnapshot,
    StatefulReloader,
)


class TestConsumerState:
    def test_defaults(self):
        cs = ConsumerState(consumer_class="app.Consumer", channel_name="ch1")
        assert cs.groups == []
        assert cs.state == {}
        assert cs.user_id is None


class TestReloadSnapshot:
    def test_roundtrip_json(self):
        snap = ReloadSnapshot(
            timestamp=12345.0,
            consumers=[
                ConsumerState(
                    consumer_class="app.ChatConsumer",
                    channel_name="chat_1",
                    groups=["room_42"],
                    state={"last_message_id": 99},
                    user_id=5,
                )
            ],
            metadata={"git_sha": "abc123"},
        )
        data = snap.to_json()
        restored = ReloadSnapshot.from_json(data)

        assert restored.timestamp == 12345.0
        assert len(restored.consumers) == 1
        assert restored.consumers[0].consumer_class == "app.ChatConsumer"
        assert restored.consumers[0].state == {"last_message_id": 99}
        assert restored.consumers[0].user_id == 5
        assert restored.metadata["git_sha"] == "abc123"

    def test_empty_snapshot(self):
        snap = ReloadSnapshot()
        data = snap.to_json()
        restored = ReloadSnapshot.from_json(data)
        assert restored.consumers == []


class TestStatefulReloader:
    @pytest.fixture
    def reloader(self, tmp_path):
        return StatefulReloader(state_file=tmp_path / "state.json")

    def test_capture_states(self, reloader):
        consumer = MagicMock()
        consumer.__class__.__module__ = "myapp.consumers"
        consumer.__class__.__qualname__ = "ChatConsumer"
        consumer.channel_name = "chat_42"
        consumer.groups = ["room_1"]
        consumer.scope = {"user": MagicMock(pk=7)}
        consumer._connected_at = 100.0
        consumer.get_state.return_value = {"typing": True}

        snapshot = reloader.capture_states([consumer])
        assert len(snapshot.consumers) == 1
        assert snapshot.consumers[0].channel_name == "chat_42"
        assert snapshot.consumers[0].state == {"typing": True}

    def test_capture_without_get_state(self, reloader):
        consumer = MagicMock(spec=["channel_name", "groups"])
        consumer.channel_name = "ch_1"
        consumer.groups = []

        snapshot = reloader.capture_states([consumer])
        assert len(snapshot.consumers) == 1
        assert snapshot.consumers[0].state == {}

    def test_save_and_load(self, reloader):
        snapshot = ReloadSnapshot(
            timestamp=1.0,
            consumers=[
                ConsumerState(consumer_class="app.C", channel_name="ch")
            ],
        )
        reloader.save_snapshot(snapshot)
        loaded = reloader.load_snapshot()

        assert loaded is not None
        assert loaded.timestamp == 1.0
        assert len(loaded.consumers) == 1

    def test_load_nonexistent(self, reloader):
        assert reloader.load_snapshot() is None

    def test_restore_states(self, reloader):
        snapshot = ReloadSnapshot(
            consumers=[
                ConsumerState(
                    consumer_class="app.ChatConsumer",
                    channel_name="ch_1",
                    groups=["room_42"],
                    state={"cursor": 10},
                    user_id=3,
                )
            ]
        )
        reloader.save_snapshot(snapshot)
        loaded = reloader.load_snapshot()
        instructions = reloader.restore_states(loaded)

        assert len(instructions) == 1
        assert instructions[0]["class"] == "app.ChatConsumer"
        assert instructions[0]["state"] == {"cursor": 10}
        assert instructions[0]["user_id"] == 3
        # State file should be cleaned up
        assert reloader.load_snapshot() is None

    def test_pre_post_callbacks(self, reloader):
        pre_called = []
        post_called = []

        @reloader.on_pre_reload
        def pre(snapshot):
            pre_called.append(snapshot)

        @reloader.on_post_reload
        def post(snapshot, instructions):
            post_called.append((snapshot, instructions))

        snapshot = reloader.capture_states([])
        assert len(pre_called) == 1

        reloader.restore_states(snapshot)
        assert len(post_called) == 1

    def test_build_reload_frame(self):
        frame = StatefulReloader.build_reload_frame()
        data = json.loads(frame)
        assert data["type"] == "matt.reload"
        assert data["action"] == "refresh_state"
        assert "timestamp" in data

    def test_reload_module(self, reloader):
        import os
        reloader.reload_module("os")
        # Should not raise — os is always in sys.modules

    def test_reload_nonexistent_module(self, reloader):
        reloader.reload_module("nonexistent.module.path")
        # Should not raise — just a no-op
