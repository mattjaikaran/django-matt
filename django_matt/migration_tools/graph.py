"""Migration dependency graph rendering and cycle detection."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("django_matt.migration_tools.graph")


@dataclass
class MigrationConflict:
    """Two leaf migrations in the same app — indicates a branch conflict."""

    app_label: str
    leaves: list[str]


class MigrationGraphRenderer:
    """Render migration dependency graphs in various formats.

    Usage::

        renderer = MigrationGraphRenderer()

        # From Django's migration loader
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        loader = MigrationLoader(connection)
        graph = loader.graph

        print(renderer.render_ascii(graph))
        print(renderer.render_dot(graph))
        cycles = renderer.detect_cycles(graph)
    """

    def get_nodes_and_edges(
        self,
        graph: Any,
        app_label: str | None = None,
    ) -> tuple[list[tuple[str, str]], list[tuple[tuple[str, str], tuple[str, str]]]]:
        """Extract nodes and edges from a Django MigrationGraph.

        Returns:
            (nodes, edges) where nodes are (app_label, migration_name) tuples
            and edges are (parent, child) pairs.
        """
        nodes: list[tuple[str, str]] = []
        edges: list[tuple[tuple[str, str], tuple[str, str]]] = []

        node_map = getattr(graph, "node_map", {})
        for key in sorted(node_map.keys()):
            al, mn = key
            if app_label and al != app_label:
                continue
            nodes.append(key)
            node = node_map[key]
            for parent in getattr(node, "parents", []):
                if app_label and parent[0] != app_label:
                    continue
                edges.append((parent, key))

        return nodes, edges

    def render_ascii(
        self,
        graph: Any,
        app_label: str | None = None,
    ) -> str:
        """Render the migration graph as ASCII art."""
        nodes, edges = self.get_nodes_and_edges(graph, app_label)
        if not nodes:
            return "(no migrations)"

        # Group by app
        apps: dict[str, list[str]] = defaultdict(list)
        for al, mn in nodes:
            apps[al].append(mn)

        # Build edge set for quick lookup
        edge_set = set(edges)

        lines: list[str] = []
        for al in sorted(apps.keys()):
            migrations = sorted(apps[al])
            lines.append(f"[{al}]")
            for i, mn in enumerate(migrations):
                is_last = i == len(migrations) - 1
                prefix = "  └── " if is_last else "  ├── "
                # Check for cross-app dependencies
                cross_deps = []
                node_map = getattr(graph, "node_map", {})
                node = node_map.get((al, mn))
                if node:
                    for parent in getattr(node, "parents", []):
                        if parent[0] != al:
                            cross_deps.append(f"{parent[0]}.{parent[1]}")

                suffix = ""
                if cross_deps:
                    suffix = f"  ← depends on: {', '.join(cross_deps)}"

                lines.append(f"{prefix}{mn}{suffix}")
            lines.append("")

        return "\n".join(lines).rstrip()

    def render_dot(
        self,
        graph: Any,
        app_label: str | None = None,
    ) -> str:
        """Render the migration graph as Graphviz DOT format."""
        nodes, edges = self.get_nodes_and_edges(graph, app_label)

        lines = ["digraph migrations {", "  rankdir=BT;", "  node [shape=box];", ""]

        # Group nodes by app with subgraph clusters
        apps: dict[str, list[str]] = defaultdict(list)
        for al, mn in nodes:
            apps[al].append(mn)

        for al in sorted(apps.keys()):
            lines.append(f"  subgraph cluster_{al} {{")
            lines.append(f'    label="{al}";')
            for mn in sorted(apps[al]):
                node_id = f"{al}__{mn}"
                lines.append(f'    {node_id} [label="{mn}"];')
            lines.append("  }")
            lines.append("")

        # Edges
        for parent, child in edges:
            p_id = f"{parent[0]}__{parent[1]}"
            c_id = f"{child[0]}__{child[1]}"
            lines.append(f"  {p_id} -> {c_id};")

        lines.append("}")
        return "\n".join(lines)

    def render_mermaid(
        self,
        graph: Any,
        app_label: str | None = None,
    ) -> str:
        """Render the migration graph as Mermaid diagram."""
        nodes, edges = self.get_nodes_and_edges(graph, app_label)

        lines = ["graph BT"]

        # Group by app
        apps: dict[str, list[str]] = defaultdict(list)
        for al, mn in nodes:
            apps[al].append(mn)

        for al in sorted(apps.keys()):
            lines.append(f"  subgraph {al}")
            for mn in sorted(apps[al]):
                node_id = f"{al}__{mn}"
                lines.append(f"    {node_id}[{mn}]")
            lines.append("  end")

        for parent, child in edges:
            p_id = f"{parent[0]}__{parent[1]}"
            c_id = f"{child[0]}__{child[1]}"
            lines.append(f"  {p_id} --> {c_id}")

        return "\n".join(lines)

    def detect_cycles(self, graph: Any) -> list[list[tuple[str, str]]]:
        """Detect cycles in the migration dependency graph.

        Returns a list of cycles, where each cycle is a list of
        (app_label, migration_name) tuples.
        """
        nodes, edges = self.get_nodes_and_edges(graph)

        # Build adjacency list
        adjacency: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
        for parent, child in edges:
            adjacency[parent].append(child)

        # DFS-based cycle detection
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[tuple[str, str], int] = dict.fromkeys(nodes, WHITE)
        parent_map: dict[tuple[str, str], tuple[str, str] | None] = {}
        cycles: list[list[tuple[str, str]]] = []

        def dfs(node: tuple[str, str]) -> None:
            color[node] = GRAY
            for neighbor in adjacency.get(node, []):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    # Found cycle — reconstruct
                    cycle = [neighbor]
                    current = node
                    while current != neighbor:
                        cycle.append(current)
                        current = parent_map.get(current, neighbor)
                    cycle.append(neighbor)
                    cycles.append(list(reversed(cycle)))
                elif color[neighbor] == WHITE:
                    parent_map[neighbor] = node
                    dfs(neighbor)
            color[node] = BLACK

        for node in nodes:
            if color[node] == WHITE:
                dfs(node)

        return cycles

    def find_conflicts(self, graph: Any) -> list[MigrationConflict]:
        """Find apps with multiple leaf migrations (branch conflicts)."""
        nodes, _ = self.get_nodes_and_edges(graph)

        # Build children lookup
        node_map = getattr(graph, "node_map", {})
        has_child: set[tuple[str, str]] = set()
        for key in node_map:
            node = node_map[key]
            for parent in getattr(node, "parents", []):
                has_child.add(parent)

        # Find leaves (nodes with no children)
        leaves_by_app: dict[str, list[str]] = defaultdict(list)
        for al, mn in nodes:
            if (al, mn) not in has_child:
                leaves_by_app[al].append(mn)

        conflicts = []
        for al, leaves in leaves_by_app.items():
            if len(leaves) > 1:
                conflicts.append(MigrationConflict(app_label=al, leaves=sorted(leaves)))

        return conflicts
