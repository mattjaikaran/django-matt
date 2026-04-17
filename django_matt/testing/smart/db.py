"""
SQLite schema and connection management for smart testing.

Tables:
- source_blocks: AST block ranges per file (file, start_line, end_line, block_hash)
- test_deps: test→source block dependencies (test_id, file, start_line, end_line)
- failures: last-run test failures (test_id, exc_repr, timestamp)
- meta: key-value store for tracking state (last_run_id, schema_version)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(".matttest.db")

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_blocks (
    file TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    block_hash TEXT NOT NULL,
    block_type TEXT NOT NULL,
    block_name TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (file, start_line, end_line)
);

CREATE TABLE IF NOT EXISTS test_deps (
    test_id TEXT NOT NULL,
    file TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    FOREIGN KEY (file, start_line, end_line)
        REFERENCES source_blocks(file, start_line, end_line)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_test_deps_test ON test_deps(test_id);
CREATE INDEX IF NOT EXISTS idx_test_deps_file ON test_deps(file);

CREATE TABLE IF NOT EXISTS failures (
    test_id TEXT PRIMARY KEY,
    exc_repr TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_meta (
    run_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    commit_sha TEXT,
    total_tests INTEGER NOT NULL DEFAULT 0,
    passed INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0
);
"""


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a connection to the smart testing database."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist. Migrate if schema version changed."""
    conn.executescript(SCHEMA_SQL)
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()
    elif int(row["value"]) < SCHEMA_VERSION:
        _migrate(conn, int(row["value"]))


def _migrate(conn: sqlite3.Connection, from_version: int) -> None:
    """Run schema migrations. Currently no migrations needed."""
    conn.execute(
        "UPDATE meta SET value = ? WHERE key = 'schema_version'",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def reset(conn: sqlite3.Connection) -> None:
    """Drop all data (keeps schema). Used by --matt-rebuild-deps."""
    conn.execute("DELETE FROM test_deps")
    conn.execute("DELETE FROM source_blocks")
    conn.execute("DELETE FROM failures")
    conn.execute("DELETE FROM run_meta")
    conn.commit()
