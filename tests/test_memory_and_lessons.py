"""Tests for memory admission gate (Step 3.2) and lesson capture (Step 3.3)."""

import os
import tempfile
from pathlib import Path

import pytest

from tools.foreman_db import init_db
from tools.lesson_capture import capture_lesson
from tools.memory_gate import check_note_admission


@pytest.fixture
def db():
    conn = init_db(":memory:")
    # Create memory_notes table for duplicate check
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_notes (
            note_id INTEGER PRIMARY KEY AUTOINCREMENT,
            vault_path TEXT,
            note_type TEXT,
            title TEXT,
            status TEXT DEFAULT 'active'
        )
    """)
    conn.commit()
    yield conn
    conn.close()


# === Memory gate tests ===

def test_missing_evidence_rejected(db):
    """A note without evidence should be flagged."""
    result = check_note_admission("Test Note", "Some content", evidence_run_id=None, db=db)
    assert len(result["reasons"]) > 0
    assert any("evidence" in r.lower() for r in result["reasons"])


def test_with_evidence_passes(db):
    """A note with evidence and no sensitive content should be admitted."""
    result = check_note_admission("Test Note", "Some content", evidence_run_id=42, db=db)
    assert result["admitted"] is True


def test_sensitive_content_flagged(db):
    """Notes with salary or personal data patterns should need approval."""
    result = check_note_admission("Salary Data", "The salary for this role is 50000", evidence_run_id=42, db=db)
    assert result["needs_approval"] is True
    assert any("salary" in r.lower() for r in result["reasons"])


# === Lesson capture tests ===

def test_capture_lesson_creates_file(db):
    """capture_lesson should create a file in lessons/."""
    from tools.run_logger import start_run
    rid = start_run(db, "File lesson test")

    with tempfile.TemporaryDirectory() as tmp:
        import tools.lesson_capture as lc
        original = lc._LESSONS_DIR
        lc._LESSONS_DIR = Path(tmp)

        try:
            result = capture_lesson(run_id=rid, db=db, what_worked="Everything", what_failed="Nothing")
            assert result["status"] == "done"
            assert os.path.isfile(result["path"])
            content = open(result["path"]).read()
            assert f"RUN-{rid}" in content
            assert "Everything" in content
        finally:
            lc._LESSONS_DIR = original


def test_lesson_recorded_in_db(db):
    """capture_lesson with db should write a lessons row."""
    from tools.run_logger import start_run
    rid = start_run(db, "Lesson test run")

    with tempfile.TemporaryDirectory() as tmp:
        import tools.lesson_capture as lc
        original = lc._LESSONS_DIR
        lc._LESSONS_DIR = Path(tmp)

        try:
            capture_lesson(run_id=rid, db=db, what_failed="Conservation gate failed")
            row = db.execute("SELECT * FROM lessons WHERE run_id = ?", (rid,)).fetchone()
            assert row is not None
            assert row["category"] == "failure"
        finally:
            lc._LESSONS_DIR = original
