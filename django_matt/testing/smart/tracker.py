"""
Block-level test-to-source dependency tracking.

Uses coverage.py to record which source lines each test executes, then maps
those lines to AST blocks for stable tracking across cosmetic edits.

The workflow:
1. First full run (--matt-rebuild-deps): instrument every test, build .matttest.db
2. On changes (--matt-affected): diff changed files at AST block level, query DB
   for tests touching those blocks → run only those tests
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from django_matt.testing.smart.db import DEFAULT_DB_PATH, connect, ensure_schema, reset
from django_matt.testing.smart.differ import ASTBlockDiffer

logger = logging.getLogger("django_matt.testing.smart")


class TestDependencyTracker:
    """Block-level test→source dependency tracking backed by SQLite."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.conn = connect(db_path)
        ensure_schema(self.conn)
        self.differ = ASTBlockDiffer()

    def close(self) -> None:
        self.conn.close()

    def rebuild(self) -> None:
        """Clear all dependency data (triggers full re-record on next run)."""
        reset(self.conn)

    def has_data(self) -> bool:
        """Check if the DB has any dependency records."""
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM test_deps").fetchone()
        return row["cnt"] > 0

    # ------------------------------------------------------------------
    # Recording: called during instrumented test runs
    # ------------------------------------------------------------------

    def record_test_coverage(self, test_id: str, coverage_data: dict[str, set[int]]) -> None:
        """Record which source lines a test executed.

        Args:
            test_id: pytest node ID (e.g., "tests/test_auth.py::test_jwt_decode")
            coverage_data: {file_path: {line_numbers}} from coverage.py
        """
        # Delete old deps for this test
        self.conn.execute("DELETE FROM test_deps WHERE test_id = ?", (test_id,))

        for file_path, lines in coverage_data.items():
            if not lines:
                continue

            # Ensure blocks are recorded for this file
            self._ensure_blocks(file_path)

            # Map executed lines → blocks
            blocks = self.conn.execute(
                """
                SELECT DISTINCT start_line, end_line FROM source_blocks
                WHERE file = ?
                  AND start_line <= ?
                  AND end_line >= ?
                """,
                # We need to check each line — use a batched approach
                (file_path, max(lines), min(lines)),
            ).fetchall()

            for block in blocks:
                # Check if any executed line falls within this block
                if any(block["start_line"] <= ln <= block["end_line"] for ln in lines):
                    self.conn.execute(
                        """
                        INSERT OR IGNORE INTO test_deps (test_id, file, start_line, end_line)
                        VALUES (?, ?, ?, ?)
                        """,
                        (test_id, file_path, block["start_line"], block["end_line"]),
                    )

        self.conn.commit()

    def _ensure_blocks(self, file_path: str) -> None:
        """Parse and store AST blocks for a file if not already present."""
        existing = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM source_blocks WHERE file = ?",
            (file_path,),
        ).fetchone()

        if existing["cnt"] > 0:
            return

        try:
            source = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return

        blocks = self.differ.extract_blocks(source)
        for block in blocks:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO source_blocks
                    (file, start_line, end_line, block_hash, block_type, block_name)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    file_path,
                    block.start_line,
                    block.end_line,
                    block.content_hash,
                    block.block_type,
                    block.name,
                ),
            )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Querying: used by --matt-affected to find tests to run
    # ------------------------------------------------------------------

    def get_affected_tests(
        self,
        changed_files: list[Path] | None = None,
        base_ref: str = "HEAD",
    ) -> list[str]:
        """Return test IDs whose dependency blocks changed.

        If changed_files is None, auto-detect from git diff against base_ref.
        """
        if changed_files is None:
            changed_files = self._git_changed_files(base_ref)

        if not changed_files:
            return []

        affected: set[str] = set()

        for file_path in changed_files:
            file_str = str(file_path)

            # Check for settings file — invalidate all tests
            if self._is_settings_file(file_path):
                return self._all_test_ids()

            # Get old blocks from DB
            old_blocks_rows = self.conn.execute(
                "SELECT start_line, end_line, block_hash, block_type, block_name "
                "FROM source_blocks WHERE file = ?",
                (file_str,),
            ).fetchall()

            if not old_blocks_rows:
                # Unknown file — can't determine affected tests, skip
                continue

            # Read current source and extract blocks
            try:
                current_source = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                # File deleted — all tests depending on it are affected
                rows = self.conn.execute(
                    "SELECT DISTINCT test_id FROM test_deps WHERE file = ?",
                    (file_str,),
                ).fetchall()
                affected.update(r["test_id"] for r in rows)
                continue

            current_blocks = self.differ.extract_blocks(current_source)

            # Build lookup from DB blocks by (type, name) → hash
            old_by_name: dict[tuple[str, str], str] = {
                (r["block_type"], r["block_name"]): r["block_hash"] for r in old_blocks_rows
            }
            new_by_name: dict[tuple[str, str], str] = {
                (b.block_type, b.name): b.content_hash for b in current_blocks
            }

            # Find changed block line ranges (from DB perspective)
            changed_block_ranges: set[tuple[int, int]] = set()

            for key, old_hash in old_by_name.items():
                new_hash = new_by_name.get(key)
                if new_hash is None or new_hash != old_hash:
                    # Removed or modified — find the DB row's line range
                    for r in old_blocks_rows:
                        if (r["block_type"], r["block_name"]) == key:
                            changed_block_ranges.add((r["start_line"], r["end_line"]))

            # New blocks (added)
            for key in new_by_name:
                if key not in old_by_name:
                    # New block — all tests for this file might be affected
                    # Conservative: mark all tests touching this file
                    rows = self.conn.execute(
                        "SELECT DISTINCT test_id FROM test_deps WHERE file = ?",
                        (file_str,),
                    ).fetchall()
                    affected.update(r["test_id"] for r in rows)

            # Query tests depending on changed blocks
            for start, end in changed_block_ranges:
                rows = self.conn.execute(
                    """
                    SELECT DISTINCT test_id FROM test_deps
                    WHERE file = ? AND start_line = ? AND end_line = ?
                    """,
                    (file_str, start, end),
                ).fetchall()
                affected.update(r["test_id"] for r in rows)

        return sorted(affected)

    def invalidate_file(self, path: Path) -> None:
        """Remove all records for a file (forces full re-record)."""
        file_str = str(path)
        self.conn.execute("DELETE FROM test_deps WHERE file = ?", (file_str,))
        self.conn.execute("DELETE FROM source_blocks WHERE file = ?", (file_str,))
        self.conn.commit()

    def update_blocks(self, file_path: Path) -> None:
        """Re-parse and update stored blocks for a file."""
        self.invalidate_file(file_path)
        self._ensure_blocks(str(file_path))

    # ------------------------------------------------------------------
    # Failure tracking (1B)
    # ------------------------------------------------------------------

    def record_failure(self, test_id: str, exc_repr: str) -> None:
        """Record a test failure."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO failures (test_id, exc_repr)
            VALUES (?, ?)
            """,
            (test_id, exc_repr),
        )
        self.conn.commit()

    def record_pass(self, test_id: str) -> None:
        """Remove a test from failures (it passed)."""
        self.conn.execute("DELETE FROM failures WHERE test_id = ?", (test_id,))
        self.conn.commit()

    def get_failed_tests(self) -> list[str]:
        """Return test IDs that failed in the last run."""
        rows = self.conn.execute("SELECT test_id FROM failures").fetchall()
        return sorted(r["test_id"] for r in rows)

    def clear_failures(self) -> None:
        """Clear all recorded failures."""
        self.conn.execute("DELETE FROM failures")
        self.conn.commit()

    def get_failure_details(self) -> list[dict[str, str]]:
        """Return failures with exception details."""
        rows = self.conn.execute(
            "SELECT test_id, exc_repr, timestamp FROM failures ORDER BY timestamp DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Run metadata
    # ------------------------------------------------------------------

    def record_run(
        self,
        run_id: str,
        commit_sha: str | None,
        total: int,
        passed: int,
        failed: int,
    ) -> None:
        """Record run metadata."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO run_meta (run_id, commit_sha, total_tests, passed, failed)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, commit_sha, total, passed, failed),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _all_test_ids(self) -> list[str]:
        """Return all known test IDs."""
        rows = self.conn.execute("SELECT DISTINCT test_id FROM test_deps").fetchall()
        return sorted(r["test_id"] for r in rows)

    @staticmethod
    def _is_settings_file(path: Path) -> bool:
        """Check if a file is a Django settings file (global dependency)."""
        name = path.name
        return name == "settings.py" or name.startswith("settings_") or "conftest" in name

    @staticmethod
    def _git_changed_files(base_ref: str = "HEAD") -> list[Path]:
        """Get files changed since base_ref using git."""
        try:
            # Staged + unstaged changes
            result = subprocess.run(
                ["git", "diff", "--name-only", base_ref],
                capture_output=True,
                text=True,
                check=True,
            )
            files = result.stdout.strip().splitlines()

            # Also include untracked files
            result2 = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                capture_output=True,
                text=True,
                check=True,
            )
            files.extend(result2.stdout.strip().splitlines())

            return [Path(f) for f in set(files) if f.endswith(".py") and Path(f).exists()]
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("git not available — cannot detect changed files")
            return []
