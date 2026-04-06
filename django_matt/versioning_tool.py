from __future__ import annotations

import re
import sys
from pathlib import Path

PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"
INIT_PATH = Path(__file__).resolve().parent / "__init__.py"

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
PYPROJECT_VERSION_RE = re.compile(r'^(version\s*=\s*")([^"]+)(")', re.MULTILINE)
INIT_VERSION_RE = re.compile(r'^(__version__\s*=\s*")([^"]+)(")', re.MULTILINE)


def current() -> str:
    text = PYPROJECT_PATH.read_text()
    m = PYPROJECT_VERSION_RE.search(text)
    if not m:
        raise RuntimeError("version not found in pyproject.toml")
    return m.group(2)


def _read_init_version() -> str:
    text = INIT_PATH.read_text()
    m = INIT_VERSION_RE.search(text)
    if not m:
        raise RuntimeError("__version__ not found in __init__.py")
    return m.group(2)


def validate() -> bool:
    return current() == _read_init_version()


def _parse(version: str) -> tuple[int, int, int]:
    m = VERSION_RE.match(version)
    if not m:
        raise ValueError(f"invalid semver: {version}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump(part: str) -> str:
    if part not in ("major", "minor", "patch"):
        raise ValueError(f"part must be major, minor, or patch, got: {part}")

    old = current()
    major, minor, patch = _parse(old)

    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1

    new = f"{major}.{minor}.{patch}"
    _write_version(new)
    return new


def _write_version(version: str) -> None:
    pyproject = PYPROJECT_PATH.read_text()
    new_pyproject = PYPROJECT_VERSION_RE.sub(rf"\g<1>{version}\3", pyproject)
    if new_pyproject == pyproject:
        raise RuntimeError("failed to update pyproject.toml version")
    PYPROJECT_PATH.write_text(new_pyproject)

    init = INIT_PATH.read_text()
    new_init = INIT_VERSION_RE.sub(rf"\g<1>{version}\3", init)
    if new_init == init:
        raise RuntimeError("failed to update __init__.py version")
    INIT_PATH.write_text(new_init)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <current|validate|bump> [major|minor|patch]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "current":
        print(current())
    elif cmd == "validate":
        if validate():
            print("versions match")
        else:
            print(f"MISMATCH: pyproject.toml={current()} __init__.py={_read_init_version()}")
            sys.exit(1)
    elif cmd == "bump":
        if len(sys.argv) < 3:
            print("usage: bump <major|minor|patch>")
            sys.exit(1)
        new = bump(sys.argv[2])
        print(f"bumped to {new}")
    else:
        print(f"unknown command: {cmd}")
        sys.exit(1)
