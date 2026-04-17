"""Stateful reloader — preserve WebSocket connections and state across code reloads.

In development, code reloads normally kill all WebSocket connections. This module
serializes active consumer states before reload, reconstructs them after, and
sends a "reload" frame to connected clients — no reconnection needed.

Usage::

    from django_matt.dev.stateful_reload import StatefulReloader

    reloader = StatefulReloader()

    # Before reload (called by file watcher):
    snapshot = reloader.capture_states(consumers)
    reloader.save_snapshot(snapshot)

    # After reload:
    snapshot = reloader.load_snapshot()
    instructions = reloader.restore_states(snapshot)

    # Send reload frame to clients:
    frame = StatefulReloader.build_reload_frame()
"""

from __future__ import annotations

import importlib
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("django_matt.dev.stateful_reload")


@dataclass
class ConsumerState:
    """Serialized state of a WebSocket consumer."""

    consumer_class: str
    channel_name: str
    groups: list[str] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    user_id: str | int | None = None
    connected_at: float = 0.0


@dataclass
class ReloadSnapshot:
    """Complete state snapshot before a reload."""

    timestamp: float = 0.0
    consumers: list[ConsumerState] = field(default_factory=list)
    module_versions: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)

    @classmethod
    def from_json(cls, data: str) -> ReloadSnapshot:
        raw = json.loads(data)
        raw["consumers"] = [ConsumerState(**c) for c in raw.get("consumers", [])]
        return cls(**raw)


class StatefulReloader:
    """Preserve WebSocket state across code reloads.

    Workflow:
    1. File watcher detects change
    2. ``capture_states()`` serializes all active consumer states
    3. Python modules are reloaded
    4. ``restore_states()`` reconstructs consumers with preserved state
    5. "reload" frame sent to connected clients
    """

    def __init__(self, state_file: Path | None = None) -> None:
        self._state_file = state_file or Path(".matt_reload_state.json")
        self._pre_reload_callbacks: list[Any] = []
        self._post_reload_callbacks: list[Any] = []

    def on_pre_reload(self, func: Any) -> Any:
        """Register a callback to run before code reload."""
        self._pre_reload_callbacks.append(func)
        return func

    def on_post_reload(self, func: Any) -> Any:
        """Register a callback to run after code reload."""
        self._post_reload_callbacks.append(func)
        return func

    def capture_states(self, consumers: list[Any]) -> ReloadSnapshot:
        """Serialize active WebSocket consumer states."""
        snapshot = ReloadSnapshot(timestamp=time.time())

        for consumer in consumers:
            state = ConsumerState(
                consumer_class=f"{type(consumer).__module__}.{type(consumer).__qualname__}",
                channel_name=getattr(consumer, "channel_name", ""),
                groups=list(getattr(consumer, "groups", [])),
                user_id=getattr(
                    getattr(consumer, "scope", {}).get("user"), "pk", None
                ),
                connected_at=getattr(consumer, "_connected_at", 0.0),
            )

            if hasattr(consumer, "get_state"):
                try:
                    state.state = consumer.get_state()
                except Exception as e:
                    logger.warning(
                        "Failed to capture state for %s: %s",
                        state.consumer_class,
                        e,
                    )

            snapshot.consumers.append(state)

        for callback in self._pre_reload_callbacks:
            try:
                callback(snapshot)
            except Exception:
                logger.exception("Pre-reload callback failed")

        return snapshot

    def save_snapshot(self, snapshot: ReloadSnapshot) -> Path:
        """Persist snapshot to disk for cross-process reload."""
        self._state_file.write_text(snapshot.to_json())
        return self._state_file

    def load_snapshot(self) -> ReloadSnapshot | None:
        """Load snapshot from disk."""
        if not self._state_file.exists():
            return None
        try:
            return ReloadSnapshot.from_json(self._state_file.read_text())
        except Exception:
            logger.warning("Failed to load reload snapshot")
            return None

    def restore_states(
        self, snapshot: ReloadSnapshot
    ) -> list[dict[str, Any]]:
        """Reconstruct consumer state from a snapshot.

        Returns a list of restoration instructions.
        """
        instructions = []
        for cs in snapshot.consumers:
            instructions.append({
                "class": cs.consumer_class,
                "channel": cs.channel_name,
                "groups": cs.groups,
                "state": cs.state,
                "user_id": cs.user_id,
            })

        for callback in self._post_reload_callbacks:
            try:
                callback(snapshot, instructions)
            except Exception:
                logger.exception("Post-reload callback failed")

        if self._state_file.exists():
            self._state_file.unlink()

        return instructions

    def reload_module(self, module_path: str) -> None:
        """Reload a Python module by dotted path."""
        if module_path in sys.modules:
            module = sys.modules[module_path]
            importlib.reload(module)
            logger.info("Reloaded module: %s", module_path)

    @staticmethod
    def build_reload_frame() -> bytes:
        """Build a WebSocket frame for code reload notification."""
        return json.dumps({
            "type": "matt.reload",
            "timestamp": time.time(),
            "action": "refresh_state",
        }).encode("utf-8")
