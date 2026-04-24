"""Conventional-commit changelog generator.

Parses git log for conventional commits and produces Keep a Changelog formatted output.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

COMMIT_RE = re.compile(
    r"^(?P<type>[a-z]+)"
    r"(?:\((?P<scope>[^)]*)\))?"
    r"(?P<breaking>!)?"
    r":\s*(?P<subject>.+)$"
)

TYPE_TO_SECTION: dict[str, str] = {
    "feat": "Added",
    "fix": "Fixed",
    "refactor": "Changed",
    "docs": "Documentation",
    "test": "Testing",
    "chore": "Chores",
    "perf": "Performance",
    "ci": "CI",
    "build": "Build",
    "style": "Style",
}


@dataclass
class CommitEntry:
    """A parsed conventional commit with type, scope, subject, and metadata."""

    type: str
    scope: str | None
    subject: str
    breaking: bool
    hash: str
    body: str = ""


@dataclass
class ChangelogEntries:
    """Grouped changelog entries organized by section with breaking changes."""

    sections: dict[str, list[str]] = field(default_factory=dict)
    breaking_changes: list[str] = field(default_factory=list)


def _run_git(*args: str) -> str:
    """Run a git command and return stripped stdout."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _get_latest_tag() -> str | None:
    """Return the most recent git tag, or None if no tags exist."""
    try:
        return _run_git("describe", "--tags", "--abbrev=0")
    except subprocess.CalledProcessError:
        return None


def _parse_commit(log_entry: str) -> CommitEntry | None:
    """Parse a raw git log entry into a CommitEntry."""
    lines = log_entry.strip().split("\n")
    if not lines:
        return None

    first_line = lines[0]
    # format: hash subject
    parts = first_line.split(" ", 1)
    if len(parts) < 2:
        return None

    commit_hash = parts[0]
    subject_line = parts[1]
    body = "\n".join(lines[1:]).strip()

    m = COMMIT_RE.match(subject_line)
    if not m:
        return None

    breaking = bool(m.group("breaking"))
    if not breaking and "BREAKING CHANGE" in body:
        breaking = True

    return CommitEntry(
        type=m.group("type"),
        scope=m.group("scope"),
        subject=m.group("subject"),
        breaking=breaking,
        hash=commit_hash,
        body=body,
    )


def generate(from_tag: str | None = None, to: str = "HEAD") -> ChangelogEntries:
    """Generate changelog entries from git commits between two refs."""
    if from_tag is None:
        from_tag = _get_latest_tag()

    if from_tag:
        range_spec = f"{from_tag}..{to}"
    else:
        range_spec = to

    try:
        log_output = _run_git(
            "log", range_spec, "--format=%H %s%n%b%n---END---",
        )
    except subprocess.CalledProcessError:
        return ChangelogEntries()

    if not log_output.strip():
        return ChangelogEntries()

    entries = ChangelogEntries()
    raw_commits = log_output.split("---END---")

    for raw in raw_commits:
        raw = raw.strip()
        if not raw:
            continue

        commit = _parse_commit(raw)
        if commit is None:
            continue

        section = TYPE_TO_SECTION.get(commit.type)
        if section is None:
            continue

        if commit.scope:
            line = f"**{commit.scope}**: {commit.subject}"
        else:
            line = commit.subject

        if section not in entries.sections:
            entries.sections[section] = []
        entries.sections[section].append(line)

        if commit.breaking:
            breaking_desc = commit.subject
            if commit.body:
                for body_line in commit.body.split("\n"):
                    if body_line.startswith("BREAKING CHANGE:"):
                        breaking_desc = body_line[len("BREAKING CHANGE:"):].strip()
                        break
            entries.breaking_changes.append(breaking_desc)

    return entries


def format_entries(version: str, entries: ChangelogEntries, date: str | None = None) -> str:
    """Format changelog entries as Keep a Changelog markdown."""
    if date is None:
        date = datetime.now(UTC).strftime("%Y-%m-%d")

    lines: list[str] = []
    lines.append(f"## [{version}] - {date}")
    lines.append("")

    if entries.breaking_changes:
        lines.append("### BREAKING CHANGES")
        lines.append("")
        for change in entries.breaking_changes:
            lines.append(f"- {change}")
        lines.append("")

    section_order = [
        "Added", "Fixed", "Changed", "Performance",
        "Documentation", "Testing", "Chores", "CI", "Build", "Style",
    ]

    for section in section_order:
        items = entries.sections.get(section)
        if not items:
            continue
        lines.append(f"### {section}")
        lines.append("")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)


def update_changelog(version: str, entries: ChangelogEntries, path: Path | None = None) -> None:
    """Insert a new version block into the CHANGELOG.md file."""
    if path is None:
        path = CHANGELOG_PATH

    formatted = format_entries(version, entries)

    if not path.exists():
        content = (
            "# Changelog\n\n"
            "All notable changes to this project will be documented in this file.\n\n"
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),\n"
            "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n"
            f"## [Unreleased]\n\n{formatted}"
        )
        path.write_text(content)
        return

    existing = path.read_text()

    # Check for duplicate version entry
    if f"## [{version}]" in existing:
        return

    # Insert after [Unreleased] header
    unreleased_pattern = re.compile(r"(## \[Unreleased\]\s*\n)")
    m = unreleased_pattern.search(existing)
    if m:
        insert_pos = m.end()
        # Skip any content under Unreleased until next ## header
        rest = existing[insert_pos:]
        next_header = re.search(r"^## ", rest, re.MULTILINE)
        if next_header:
            # Clear unreleased content and insert new version before next header
            new_content = (
                existing[:insert_pos]
                + "\n"
                + formatted
                + rest[next_header.start():]
            )
        else:
            new_content = existing[:insert_pos] + "\n" + formatted + rest
    else:
        # No [Unreleased] header, insert at top after the header block
        header_end = existing.find("\n\n", existing.find("# Changelog"))
        if header_end == -1:
            header_end = 0
        else:
            header_end += 2
        new_content = (
            existing[:header_end]
            + "## [Unreleased]\n\n"
            + formatted
            + existing[header_end:]
        )

    path.write_text(new_content)
