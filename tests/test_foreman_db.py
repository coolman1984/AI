"""Tests for foreman_db.py -- init_db idempotency and table creation."""

import os
import tempfile

import pytest

from tools.foreman_db import SCHEMA_VERSION, init_db


@pytest.fixture
def tmp_db():
    """Yield a temporary database path, clean up after."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = tmp.name
    tmp.close()
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_init_db_creates_tables(tmp_db):
    """After init_db, all 8 MVP tables exist."""
    conn = init_db(tmp_db)
    tables = set()
    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        tables.add(row[0])
    expected = {
        "runs", "run_steps", "evidence_items", "validation_results",
        "reports", "lessons", "approvals", "file_fingerprints", "_meta",
    }
    missing = expected - tables
    assert not missing, f"Missing tables: {missing}"
    conn.close()


def test_init_db_idempotent(tmp_db):
    """Calling init_db twice on the same path does not error."""
    conn1 = init_db(tmp_db)
    conn1.close()
    conn2 = init_db(tmp_db)
    tables = set()
    for row in conn2.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        tables.add(row[0])
    assert "runs" in tables
    conn2.close()


def test_schema_version_recorded(tmp_db):
    """Schema version meta row exists after init."""
    conn = init_db(tmp_db)
    row = conn.execute("SELECT value FROM _meta WHERE key='schema_version'").fetchone()
    assert row is not None
    assert int(row["value"]) == SCHEMA_VERSION
    conn.close()


def test_insert_run_and_steps(tmp_db):
    """Can insert a runs row and a linked run_steps row."""
    conn = init_db(tmp_db)
    conn.execute(
        "INSERT INTO runs (goal, status) VALUES (?, ?)",
        ("Test goal", "running"),
    )
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO run_steps (run_id, seq, tool_id, status) VALUES (?, ?, ?, ?)",
        (run_id, 1, "T-TEST-001", "done"),
    )
    # step_id intentionally unused -- only checking linkage
    conn.execute("SELECT last_insert_rowid()").fetchone()

    runs = list(conn.execute("SELECT * FROM runs"))
    steps = list(conn.execute("SELECT * FROM run_steps"))
    assert len(runs) == 1
    assert len(steps) == 1
    assert steps[0]["run_id"] == run_id
    conn.close()


def test_default_db_path_is_reasonable():
    """Default path should point under registry/."""
    from tools.foreman_db import DEFAULT_DB_PATH
    assert "registry" in DEFAULT_DB_PATH.replace("\\", "/")
    assert DEFAULT_DB_PATH.endswith("foreman.db")
