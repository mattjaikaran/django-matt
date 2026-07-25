"""API evolution tracker — version-aware response transformation.

Tracks schema changes per API path and automatically transforms responses
so old clients continue to receive data in the shape they expect.

Usage::

    tracker = APIEvolutionTracker()
    tracker.register_schema_change(
        path="/users/{id}",
        version="2026-04",
        transforms=[RenameField(old="username", new="handle")],
    )

    # Client on version 2026-03:
    data = tracker.transform_response("/users/1", "2026-03", {"handle": "matt"})
    # → {"username": "matt"}

    # Client on version 2026-04+:
    data = tracker.transform_response("/users/1", "2026-04", {"handle": "matt"})
    # → {"handle": "matt"} (no transform needed)
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from django_matt.versioning.evolution.transforms import SchemaTransform, TransformChain

logger = logging.getLogger("django_matt.versioning.evolution")


@dataclass
class SchemaChange:
    """A registered schema change."""

    path_pattern: str
    version: str
    transforms: TransformChain
    description: str = ""


class APIEvolutionTracker:
    """Track API schema versions and auto-transform responses.

    Maintains a registry of schema changes per path. When a client requests
    with an older API version header, the tracker applies backward transforms
    to serve the old schema shape.

    Version comparison is lexicographic (e.g. "2026-03" < "2026-04").
    """

    def __init__(self, version_header: str = "X-API-Version") -> None:
        self.version_header = version_header
        self._changes: dict[str, list[SchemaChange]] = defaultdict(list)

    def register_schema_change(
        self,
        path: str,
        version: str,
        transforms: list[SchemaTransform],
        description: str = "",
    ) -> None:
        """Register a breaking schema change.

        Args:
            path: URL path pattern (e.g. "/users/{id}").
            version: Version string when this change was introduced.
            transforms: List of transforms describing the change.
            description: Human-readable description.
        """
        chain = TransformChain(transforms)
        change = SchemaChange(
            path_pattern=path,
            version=version,
            transforms=chain,
            description=description,
        )
        self._changes[self._normalize_path(path)].append(change)
        # Keep sorted by version
        self._changes[self._normalize_path(path)].sort(key=lambda c: c.version)

    def transform_response(
        self,
        path: str,
        client_version: str | None,
        response_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform response data for a client's API version.

        If the client is on an older version, backward transforms are applied
        for each schema change between the client version and the current version.

        Args:
            path: The request path.
            client_version: The client's API version (from header or None).
            response_data: The response data to potentially transform.

        Returns:
            Transformed response data.
        """
        if client_version is None:
            return response_data

        norm_path = self._normalize_path(path)
        changes = self._find_matching_changes(norm_path)

        if not changes:
            return response_data

        # Apply backward transforms for changes introduced after client_version
        data = dict(response_data)  # shallow copy
        for change in reversed(changes):
            if change.version > client_version:
                data = change.transforms.backward(data)

        return data

    def transform_request(
        self,
        path: str,
        client_version: str | None,
        request_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform request data from an old client to current schema.

        Applies forward transforms for changes between client version and current.
        """
        if client_version is None:
            return request_data

        norm_path = self._normalize_path(path)
        changes = self._find_matching_changes(norm_path)

        if not changes:
            return request_data

        data = dict(request_data)
        for change in changes:
            if change.version > client_version:
                data = change.transforms.forward(data)

        return data

    def get_changes(self, path: str | None = None) -> list[SchemaChange]:
        """List registered schema changes, optionally filtered by path."""
        if path is not None:
            norm = self._normalize_path(path)
            return list(self._changes.get(norm, []))

        all_changes = []
        for changes in self._changes.values():
            all_changes.extend(changes)
        return sorted(all_changes, key=lambda c: c.version)

    def _find_matching_changes(self, norm_path: str) -> list[SchemaChange]:
        """Find changes matching a normalized path."""
        # Exact match first
        if norm_path in self._changes:
            return self._changes[norm_path]

        # Pattern match (path params replaced with {})
        for pattern, changes in self._changes.items():
            if self._path_matches(pattern, norm_path):
                return changes

        return []

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize path by replacing specific IDs with {param}."""
        # Replace path params like {id}, {user_id} with {}
        return re.sub(r"\{[^}]+\}", "{}", path)

    @staticmethod
    def _path_matches(pattern: str, path: str) -> bool:
        """Check if a path matches a pattern with {} wildcards."""
        # Convert {} to regex wildcard
        regex = "^" + re.escape(pattern).replace(r"\{\}", "[^/]+") + "$"
        return bool(re.match(regex, path))
