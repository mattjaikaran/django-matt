"""
State management for Livewire components.

Provides state serialization, snapshots, and persistence.
"""

import base64
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django_matt.livewire.component import LiveComponent


# =============================================================================
# Snapshot
# =============================================================================


@dataclass
class Snapshot:
    """
    A serialized snapshot of component state.

    Used for transmitting state between server and client,
    and for caching/persisting component state.
    """

    component_name: str
    component_id: str
    state: dict[str, Any]
    checksum: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.component_name,
            "id": self.component_id,
            "state": self.state,
            "checksum": self.checksum,
            "ts": self.timestamp.isoformat(),
            "v": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Snapshot":
        """Create from dictionary."""
        return cls(
            component_name=data["name"],
            component_id=data["id"],
            state=data["state"],
            checksum=data["checksum"],
            timestamp=datetime.fromisoformat(data["ts"]),
            version=data.get("v", 1),
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "Snapshot":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_token(self) -> str:
        """
        Create a signed token for client transmission.

        The token includes the snapshot data and a signature
        to prevent tampering.
        """
        data = self.to_json()
        signature = self._sign(data)
        payload = json.dumps({"d": data, "s": signature})
        return base64.urlsafe_b64encode(payload.encode()).decode()

    @classmethod
    def from_token(cls, token: str, secret: str | None = None) -> "Snapshot":
        """
        Restore snapshot from signed token.

        Raises ValueError if signature is invalid.
        """
        try:
            payload = json.loads(base64.urlsafe_b64decode(token.encode()).decode())
            data = payload["d"]
            signature = payload["s"]

            expected = cls._sign(data, secret)
            if signature != expected:
                raise ValueError("Invalid snapshot signature")

            return cls.from_json(data)
        except Exception as e:
            raise ValueError(f"Invalid snapshot token: {e}")

    @staticmethod
    def _sign(data: str, secret: str | None = None) -> str:
        """Create signature for data."""
        from django.conf import settings

        key = secret or getattr(settings, "SECRET_KEY", "insecure-default")
        return hashlib.sha256(f"{data}{key}".encode()).hexdigest()[:16]

    def verify_checksum(self, component: "LiveComponent") -> bool:
        """Verify that component state matches snapshot checksum."""
        return component.get_checksum() == self.checksum


# =============================================================================
# State
# =============================================================================


@dataclass
class State:
    """
    Represents the current state of a component.

    Tracks dirty fields, provides diff capabilities, and handles
    state transformations.
    """

    data: dict[str, Any] = field(default_factory=dict)
    dirty_fields: set = field(default_factory=set)
    version: int = 0

    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        """Set a state value and mark as dirty."""
        if self.data.get(key) != value:
            self.data[key] = value
            self.dirty_fields.add(key)
            self.version += 1

    def update(self, values: dict[str, Any]):
        """Update multiple values."""
        for key, value in values.items():
            self.set(key, value)

    def clear_dirty(self):
        """Clear dirty field tracking."""
        self.dirty_fields.clear()

    def is_dirty(self, field: str | None = None) -> bool:
        """Check if state (or specific field) is dirty."""
        if field:
            return field in self.dirty_fields
        return len(self.dirty_fields) > 0

    def get_dirty_values(self) -> dict[str, Any]:
        """Get only the dirty field values."""
        return {k: self.data[k] for k in self.dirty_fields if k in self.data}

    def diff(self, other: "State") -> dict[str, dict[str, Any]]:
        """
        Get the difference between two states.

        Returns dict with 'added', 'removed', 'changed' keys.
        """
        added = {}
        removed = {}
        changed = {}

        all_keys = set(self.data.keys()) | set(other.data.keys())

        for key in all_keys:
            in_self = key in self.data
            in_other = key in other.data

            if in_self and not in_other:
                added[key] = self.data[key]
            elif not in_self and in_other:
                removed[key] = other.data[key]
            elif self.data[key] != other.data[key]:
                changed[key] = {"old": other.data[key], "new": self.data[key]}

        return {"added": added, "removed": removed, "changed": changed}

    def clone(self) -> "State":
        """Create a copy of the state."""
        import copy

        return State(
            data=copy.deepcopy(self.data),
            dirty_fields=self.dirty_fields.copy(),
            version=self.version,
        )


# =============================================================================
# State Manager
# =============================================================================


class StateManager:
    """
    Manages component state persistence and retrieval.

    Supports multiple backends: memory, cache, database.

    Usage:
        manager = StateManager(backend="cache")

        # Save component state
        manager.save(component)

        # Restore component state
        manager.restore(component, snapshot_id)

        # Get component history
        history = manager.get_history(component_id)
    """

    def __init__(
        self,
        backend: str = "memory",
        ttl: int = 3600,  # 1 hour default
        max_snapshots: int = 100,
    ):
        self.backend = backend
        self.ttl = ttl
        self.max_snapshots = max_snapshots

        # In-memory storage
        self._memory_store: dict[str, list[Snapshot]] = {}

    def save(self, component: "LiveComponent") -> Snapshot:
        """
        Save component state as a snapshot.

        Returns the created snapshot.
        """
        snapshot = Snapshot(
            component_name=component._component_name,
            component_id=component._component_id,
            state=component.dehydrate(),
            checksum=component.get_checksum(),
        )

        if self.backend == "memory":
            self._save_memory(snapshot)
        elif self.backend == "cache":
            self._save_cache(snapshot)
        elif self.backend == "database":
            self._save_database(snapshot)

        return snapshot

    def load(
        self,
        component_id: str,
        version: int | None = None,
    ) -> Snapshot | None:
        """
        Load a component snapshot.

        Args:
            component_id: The component ID
            version: Specific version to load (latest if None)

        Returns:
            The snapshot or None if not found
        """
        if self.backend == "memory":
            return self._load_memory(component_id, version)
        if self.backend == "cache":
            return self._load_cache(component_id, version)
        if self.backend == "database":
            return self._load_database(component_id, version)
        return None

    def restore(
        self,
        component: "LiveComponent",
        snapshot: Snapshot | None = None,
    ) -> bool:
        """
        Restore component state from snapshot.

        Returns True if restoration was successful.
        """
        if snapshot is None:
            snapshot = self.load(component._component_id)

        if snapshot is None:
            return False

        component.hydrate(snapshot.state)
        return True

    def get_history(
        self,
        component_id: str,
        limit: int = 10,
    ) -> list[Snapshot]:
        """Get snapshot history for a component."""
        if self.backend == "memory":
            snapshots = self._memory_store.get(component_id, [])
            return snapshots[-limit:]
        return []

    def clear(self, component_id: str | None = None):
        """Clear snapshots for a component or all components."""
        if self.backend == "memory":
            if component_id:
                self._memory_store.pop(component_id, None)
            else:
                self._memory_store.clear()

    # Memory backend
    def _save_memory(self, snapshot: Snapshot):
        if snapshot.component_id not in self._memory_store:
            self._memory_store[snapshot.component_id] = []

        snapshots = self._memory_store[snapshot.component_id]
        snapshots.append(snapshot)

        # Trim to max
        if len(snapshots) > self.max_snapshots:
            self._memory_store[snapshot.component_id] = snapshots[-self.max_snapshots :]

    def _load_memory(
        self,
        component_id: str,
        version: int | None,
    ) -> Snapshot | None:
        snapshots = self._memory_store.get(component_id, [])
        if not snapshots:
            return None

        if version is not None:
            for s in snapshots:
                if s.version == version:
                    return s
            return None

        return snapshots[-1]  # Latest

    # Cache backend
    def _save_cache(self, snapshot: Snapshot):
        from django.core.cache import cache

        key = f"livewire:snapshot:{snapshot.component_id}"
        history_key = f"livewire:history:{snapshot.component_id}"

        # Save current
        cache.set(key, snapshot.to_json(), self.ttl)

        # Update history
        history = cache.get(history_key, [])
        history.append(snapshot.to_dict())
        if len(history) > self.max_snapshots:
            history = history[-self.max_snapshots :]
        cache.set(history_key, history, self.ttl)

    def _load_cache(
        self,
        component_id: str,
        version: int | None,
    ) -> Snapshot | None:
        from django.core.cache import cache

        if version is not None:
            history_key = f"livewire:history:{component_id}"
            history = cache.get(history_key, [])
            for s in history:
                if s.get("v") == version:
                    return Snapshot.from_dict(s)
            return None

        key = f"livewire:snapshot:{component_id}"
        data = cache.get(key)
        if data:
            return Snapshot.from_json(data)
        return None

    # Database backend
    def _save_database(self, snapshot: Snapshot):
        # Would use a ComponentSnapshot model
        # For now, fall back to cache
        self._save_cache(snapshot)

    def _load_database(
        self,
        component_id: str,
        version: int | None,
    ) -> Snapshot | None:
        # Would query ComponentSnapshot model
        return self._load_cache(component_id, version)


# Global state manager instance
state_manager = StateManager()


__all__ = [
    "Snapshot",
    "State",
    "StateManager",
    "state_manager",
]
