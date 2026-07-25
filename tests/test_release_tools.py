from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from django_matt.changelog_gen import (
    ChangelogEntries,
    _parse_commit,
    format_entries,
    update_changelog,
)
from django_matt.versioning_tool import (
    INIT_VERSION_RE,
    PYPROJECT_VERSION_RE,
    _parse,
    _write_version,
    bump,
    current,
    validate,
)

# ============================================================================
# versioning_tool tests
# ============================================================================


class TestVersionParsing:
    def test_parse_valid(self) -> None:
        assert _parse("0.8.0") == (0, 8, 0)
        assert _parse("1.0.0") == (1, 0, 0)
        assert _parse("12.34.56") == (12, 34, 56)

    def test_parse_invalid(self) -> None:
        with pytest.raises(ValueError, match="invalid semver"):
            _parse("1.0")
        with pytest.raises(ValueError, match="invalid semver"):
            _parse("v1.0.0")
        with pytest.raises(ValueError, match="invalid semver"):
            _parse("1.0.0-beta")


class TestCurrent:
    def test_reads_version_from_pyproject(self) -> None:
        v = current()
        assert re.match(r"^\d+\.\d+\.\d+$", v)


class TestValidate:
    def test_versions_match(self) -> None:
        assert validate() is True


class TestBump:
    def test_bump_invalid_part(self) -> None:
        with pytest.raises(ValueError, match="part must be"):
            bump("prerelease")

    def test_bump_patch(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('version = "1.2.3"\n')
        init = tmp_path / "__init__.py"
        init.write_text('__version__ = "1.2.3"\n')

        with (
            patch("django_matt.versioning_tool.PYPROJECT_PATH", pyproject),
            patch("django_matt.versioning_tool.INIT_PATH", init),
        ):
            new = bump("patch")

        assert new == "1.2.4"
        assert '"1.2.4"' in pyproject.read_text()
        assert '"1.2.4"' in init.read_text()

    def test_bump_minor(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('version = "1.2.3"\n')
        init = tmp_path / "__init__.py"
        init.write_text('__version__ = "1.2.3"\n')

        with (
            patch("django_matt.versioning_tool.PYPROJECT_PATH", pyproject),
            patch("django_matt.versioning_tool.INIT_PATH", init),
        ):
            new = bump("minor")

        assert new == "1.3.0"

    def test_bump_major(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('version = "1.2.3"\n')
        init = tmp_path / "__init__.py"
        init.write_text('__version__ = "1.2.3"\n')

        with (
            patch("django_matt.versioning_tool.PYPROJECT_PATH", pyproject),
            patch("django_matt.versioning_tool.INIT_PATH", init),
        ):
            new = bump("major")

        assert new == "2.0.0"


class TestWriteVersion:
    def test_atomic_update(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"\n')
        init = tmp_path / "__init__.py"
        init.write_text('__version__ = "0.1.0"\nother = "stuff"\n')

        with (
            patch("django_matt.versioning_tool.PYPROJECT_PATH", pyproject),
            patch("django_matt.versioning_tool.INIT_PATH", init),
        ):
            _write_version("0.2.0")

        assert 'version = "0.2.0"' in pyproject.read_text()
        assert '__version__ = "0.2.0"' in init.read_text()
        assert 'other = "stuff"' in init.read_text()


class TestRegexPatterns:
    def test_pyproject_re(self) -> None:
        text = '[project]\nversion = "0.8.0"\n'
        m = PYPROJECT_VERSION_RE.search(text)
        assert m and m.group(2) == "0.8.0"

    def test_init_re(self) -> None:
        text = '__version__ = "0.8.0"\n'
        m = INIT_VERSION_RE.search(text)
        assert m and m.group(2) == "0.8.0"


# ============================================================================
# changelog_gen tests
# ============================================================================


class TestParseCommit:
    def test_feat(self) -> None:
        entry = _parse_commit("abc123 feat: add user endpoint")
        assert entry is not None
        assert entry.type == "feat"
        assert entry.subject == "add user endpoint"
        assert entry.scope is None
        assert entry.breaking is False

    def test_fix_with_scope(self) -> None:
        entry = _parse_commit("abc123 fix(auth): token refresh bug")
        assert entry is not None
        assert entry.type == "fix"
        assert entry.scope == "auth"
        assert entry.subject == "token refresh bug"

    def test_breaking_bang(self) -> None:
        entry = _parse_commit("abc123 feat!: remove legacy api")
        assert entry is not None
        assert entry.breaking is True

    def test_breaking_body(self) -> None:
        entry = _parse_commit("abc123 feat: new auth\nBREAKING CHANGE: old tokens invalid")
        assert entry is not None
        assert entry.breaking is True

    def test_non_conventional(self) -> None:
        entry = _parse_commit("abc123 updated some stuff")
        assert entry is None

    def test_empty(self) -> None:
        entry = _parse_commit("")
        assert entry is None

    def test_chore(self) -> None:
        entry = _parse_commit("abc123 chore: update deps")
        assert entry is not None
        assert entry.type == "chore"

    def test_refactor(self) -> None:
        entry = _parse_commit("abc123 refactor(views): simplify dispatch")
        assert entry is not None
        assert entry.type == "refactor"
        assert entry.scope == "views"


class TestFormatEntries:
    def test_basic(self) -> None:
        entries = ChangelogEntries(
            sections={
                "Added": ["new feature", "another feature"],
                "Fixed": ["a bug"],
            }
        )
        result = format_entries("1.0.0", entries, date="2026-04-06")
        assert "## [1.0.0] - 2026-04-06" in result
        assert "### Added" in result
        assert "- new feature" in result
        assert "- another feature" in result
        assert "### Fixed" in result
        assert "- a bug" in result

    def test_breaking_changes(self) -> None:
        entries = ChangelogEntries(
            sections={"Added": ["breaking thing"]},
            breaking_changes=["removed old api"],
        )
        result = format_entries("2.0.0", entries, date="2026-04-06")
        assert "### BREAKING CHANGES" in result
        assert "- removed old api" in result

    def test_empty_entries(self) -> None:
        entries = ChangelogEntries()
        result = format_entries("1.0.0", entries, date="2026-04-06")
        assert "## [1.0.0] - 2026-04-06" in result

    def test_section_ordering(self) -> None:
        entries = ChangelogEntries(
            sections={
                "Chores": ["dep update"],
                "Added": ["feature"],
                "Fixed": ["bug"],
            }
        )
        result = format_entries("1.0.0", entries, date="2026-04-06")
        added_pos = result.index("### Added")
        fixed_pos = result.index("### Fixed")
        chores_pos = result.index("### Chores")
        assert added_pos < fixed_pos < chores_pos


class TestUpdateChangelog:
    def test_creates_new_file(self, tmp_path: Path) -> None:
        path = tmp_path / "CHANGELOG.md"
        entries = ChangelogEntries(sections={"Added": ["initial release"]})
        update_changelog("0.1.0", entries, path=path)

        content = path.read_text()
        assert "# Changelog" in content
        assert "## [0.1.0]" in content
        assert "- initial release" in content

    def test_inserts_after_unreleased(self, tmp_path: Path) -> None:
        path = tmp_path / "CHANGELOG.md"
        path.write_text(
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "## [0.1.0] - 2026-01-01\n\n"
            "### Added\n\n"
            "- old feature\n"
        )

        entries = ChangelogEntries(sections={"Fixed": ["a bug"]})
        update_changelog("0.2.0", entries, path=path)

        content = path.read_text()
        assert "## [Unreleased]" in content
        assert "## [0.2.0]" in content
        assert "## [0.1.0]" in content
        unreleased_pos = content.index("## [Unreleased]")
        new_pos = content.index("## [0.2.0]")
        old_pos = content.index("## [0.1.0]")
        assert unreleased_pos < new_pos < old_pos

    def test_idempotent(self, tmp_path: Path) -> None:
        path = tmp_path / "CHANGELOG.md"
        path.write_text("# Changelog\n\n## [Unreleased]\n\n")

        entries = ChangelogEntries(sections={"Added": ["feature"]})
        update_changelog("0.1.0", entries, path=path)
        content_first = path.read_text()

        update_changelog("0.1.0", entries, path=path)
        content_second = path.read_text()

        assert content_first == content_second

    def test_preserves_existing_content(self, tmp_path: Path) -> None:
        path = tmp_path / "CHANGELOG.md"
        original = (
            "# Changelog\n\n"
            "All notable changes to this project will be documented in this file.\n\n"
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),\n"
            "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n"
            "## [Unreleased]\n\n"
            "## [0.7.0] - 2026-03-01\n\n"
            "### Added\n\n"
            "- some old feature\n"
        )
        path.write_text(original)

        entries = ChangelogEntries(sections={"Added": ["new thing"]})
        update_changelog("0.8.0", entries, path=path)

        content = path.read_text()
        assert "- some old feature" in content
        assert "## [0.7.0]" in content
        assert "- new thing" in content


class TestGenerateIntegration:
    def test_generate_returns_entries(self) -> None:
        from django_matt.changelog_gen import generate

        entries = generate(from_tag="HEAD", to="HEAD")
        assert isinstance(entries, ChangelogEntries)
