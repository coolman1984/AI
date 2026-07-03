"""FOREMAN database: init_db creates 8 MVP tables idempotently."""

import os
import sqlite3

SCHEMA_VERSION = 1

# Path relative to project root; can be overridden
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "registry", "foreman.db")


def init_db(path: str = None) -> sqlite3.Connection:
    """Create/connect to the FOREMAN SQLite database.

    Creates all 8 MVP tables if they do not already exist.
    Idempotent -- safe to call multiple times.
    Returns the connection object.
    """
    if path is None:
        path = DEFAULT_DB_PATH

    # Ensure directory exists
    db_dir = os.path.dirname(path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    _create_tables(conn)
    _ensure_schema_version(conn)

    return conn


def _create_tables(conn: sqlite3.Connection):
    """Create 8 MVP tables with CREATE TABLE IF NOT EXISTS."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at      TEXT NOT NULL DEFAULT (datetime('now')),
            finished_at     TEXT,
            status          TEXT NOT NULL DEFAULT 'running'
                            CHECK(status IN ('running','done','blocked','failed')),
            goal            TEXT NOT NULL,
            skill_id        TEXT,
            contract_path   TEXT,
            privacy_tier    TEXT NOT NULL DEFAULT 'tier1'
                            CHECK(privacy_tier IN ('tier1','tier2')),
            model_calls_count INTEGER DEFAULT 0,
            est_tokens      INTEGER DEFAULT 0,
            outcome_summary TEXT
        );

        CREATE TABLE IF NOT EXISTS run_steps (
            step_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      INTEGER NOT NULL REFERENCES runs(run_id),
            seq         INTEGER NOT NULL,
            tool_id     TEXT NOT NULL,
            params_json TEXT,
            status      TEXT NOT NULL DEFAULT 'running'
                        CHECK(status IN ('running','done','failed')),
            started_at  TEXT NOT NULL DEFAULT (datetime('now')),
            finished_at TEXT,
            output_path TEXT
        );

        CREATE TABLE IF NOT EXISTS evidence_items (
            evidence_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id            INTEGER NOT NULL REFERENCES runs(run_id),
            step_id           INTEGER REFERENCES run_steps(step_id),
            source_fingerprint TEXT,
            source_path       TEXT,
            locator           TEXT,
            method            TEXT,
            value_or_summary  TEXT,
            created_at        TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS validation_results (
            validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id        INTEGER NOT NULL REFERENCES runs(run_id),
            gate_name     TEXT NOT NULL,
            rule_ref      TEXT,
            passed        INTEGER NOT NULL CHECK(passed IN (0,1)),
            expected      TEXT,
            actual        TEXT,
            message       TEXT
        );

        CREATE TABLE IF NOT EXISTS reports (
            report_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id        INTEGER NOT NULL REFERENCES runs(run_id),
            type          TEXT NOT NULL,
            audience      TEXT,
            file_path     TEXT,
            signed_off_by TEXT,
            signed_off_at TEXT
        );

        CREATE TABLE IF NOT EXISTS lessons (
            lesson_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           INTEGER NOT NULL REFERENCES runs(run_id),
            category         TEXT NOT NULL
                             CHECK(category IN ('failure','correction','pattern')),
            description      TEXT NOT NULL,
            evidence_run_ids TEXT,
            status           TEXT NOT NULL DEFAULT 'raw'
                             CHECK(status IN ('raw','curated','promoted','rejected'))
        );

        CREATE TABLE IF NOT EXISTS approvals (
            approval_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id       INTEGER REFERENCES runs(run_id),
            type         TEXT NOT NULL
                         CHECK(type IN ('external_send','skill_promotion','write_action','sensitive_memory')),
            request_path TEXT,
            decision     TEXT CHECK(decision IN ('approved','rejected')),
            decided_by   TEXT,
            decided_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS file_fingerprints (
            fingerprint_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            sha256           TEXT NOT NULL,
            original_path    TEXT NOT NULL,
            registered_path  TEXT,
            size_bytes       INTEGER,
            first_seen_at    TEXT NOT NULL DEFAULT (datetime('now')),
            source_note      TEXT
        );
    """)


def _ensure_schema_version(conn: sqlite3.Connection):
    """Record schema version in a meta table."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT OR IGNORE INTO _meta (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()
