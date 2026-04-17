"""Dependency resolution and JSONPath interpolation for batch requests."""

from __future__ import annotations

import re
from typing import Any

from django_matt.batch.request import BatchRequest

# Pattern: {result=request_name:$.json.path}
_INTERPOLATION_RE = re.compile(r"\{result=([^:}]+):(\$[^}]*)\}")


class CyclicDependencyError(Exception):
    """Raised when batch requests form a dependency cycle."""

    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        super().__init__(f"Cyclic dependency detected: {' -> '.join(cycle)}")


class MissingDependencyError(Exception):
    """Raised when a depends_on references a non-existent named request."""

    def __init__(self, name: str, missing: str):
        self.name = name
        self.missing = missing
        super().__init__(f"Request '{name}' depends on unknown request '{missing}'")


def topological_sort(requests: list[BatchRequest]) -> list[list[int]]:
    """Sort batch requests into execution waves using Kahn's algorithm.

    Returns a list of waves. Each wave is a list of request indices that can
    execute in parallel. Waves execute sequentially (wave N+1 starts after
    wave N completes).

    Raises CyclicDependencyError if a cycle is detected.
    Raises MissingDependencyError if depends_on references an unknown name.
    """
    n = len(requests)
    name_to_idx: dict[str, int] = {}

    for i, req in enumerate(requests):
        if req.name:
            name_to_idx[req.name] = i

    # Build adjacency and in-degree
    in_degree = [0] * n
    dependents: list[list[int]] = [[] for _ in range(n)]

    for i, req in enumerate(requests):
        for dep_name in req.depends_on:
            if dep_name not in name_to_idx:
                request_name = req.name or f"index:{i}"
                raise MissingDependencyError(request_name, dep_name)
            dep_idx = name_to_idx[dep_name]
            dependents[dep_idx].append(i)
            in_degree[i] += 1

    # Kahn's — collect waves
    waves: list[list[int]] = []
    queue = [i for i in range(n) if in_degree[i] == 0]

    processed = 0
    while queue:
        waves.append(queue)
        processed += len(queue)
        next_queue: list[int] = []
        for idx in queue:
            for dep_idx in dependents[idx]:
                in_degree[dep_idx] -= 1
                if in_degree[dep_idx] == 0:
                    next_queue.append(dep_idx)
        queue = next_queue

    if processed != n:
        # Find cycle for error message
        remaining = [i for i in range(n) if in_degree[i] > 0]
        cycle_names = [requests[i].name or f"index:{i}" for i in remaining]
        raise CyclicDependencyError(cycle_names)

    return waves


def jsonpath_extract(data: Any, path: str) -> Any:
    """Extract a value from data using a simple JSONPath expression.

    Supports:
      $ — root
      $.key — object key access
      $.key.nested — nested access
      $.array[0] — array index access
      $.key[0].nested — chained access
    """
    if path == "$":
        return data

    if not path.startswith("$."):
        raise ValueError(f"JSONPath must start with '$.' or be '$', got: {path}")

    current = data
    # Split on '.' but handle array indices
    tokens = _tokenize_path(path[2:])

    for token in tokens:
        if isinstance(token, str):
            if isinstance(current, dict):
                if token not in current:
                    raise KeyError(f"Key '{token}' not found in {type(current).__name__}")
                current = current[token]
            else:
                raise TypeError(
                    f"Cannot access key '{token}' on {type(current).__name__}"
                )
        elif isinstance(token, int):
            if isinstance(current, (list, tuple)):
                try:
                    current = current[token]
                except IndexError:
                    raise IndexError(f"Index {token} out of range (length {len(current)})")
            else:
                raise TypeError(
                    f"Cannot index {type(current).__name__} with integer"
                )

    return current


def _tokenize_path(path: str) -> list[str | int]:
    """Tokenize a JSONPath expression after the '$.' prefix."""
    tokens: list[str | int] = []
    # Match key names and array indices
    _token_re = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*|\[\d+\])")
    for match in _token_re.finditer(path):
        part = match.group(1)
        if part.startswith("[") and part.endswith("]"):
            tokens.append(int(part[1:-1]))
        else:
            tokens.append(part)
    return tokens


def interpolate_value(value: Any, results: dict[str, Any]) -> Any:
    """Recursively interpolate {result=name:$.path} references in a value."""
    if isinstance(value, str):
        return _interpolate_string(value, results)
    elif isinstance(value, dict):
        return {k: interpolate_value(v, results) for k, v in value.items()}
    elif isinstance(value, list):
        return [interpolate_value(item, results) for item in value]
    return value


def _interpolate_string(value: str, results: dict[str, Any]) -> Any:
    """Interpolate a single string value.

    If the entire string is one interpolation expression, return the raw
    extracted value (preserving type). Otherwise, do string substitution.
    """
    # Check if the entire string is a single interpolation
    match = _INTERPOLATION_RE.fullmatch(value)
    if match:
        ref_name, json_path = match.group(1), match.group(2)
        if ref_name not in results:
            raise KeyError(f"Referenced request '{ref_name}' has no result")
        return jsonpath_extract(results[ref_name], json_path)

    # Partial interpolation — always returns string
    def _replace(m: re.Match) -> str:
        ref_name, json_path = m.group(1), m.group(2)
        if ref_name not in results:
            raise KeyError(f"Referenced request '{ref_name}' has no result")
        return str(jsonpath_extract(results[ref_name], json_path))

    return _INTERPOLATION_RE.sub(_replace, value)
