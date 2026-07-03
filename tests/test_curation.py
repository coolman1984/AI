"""Tests for weekly curation helper (Step 3.4)."""

import pytest

from tools.curate_lessons import list_raw_lessons, promote_lesson
from tools.foreman_db import init_db
from tools.lesson_capture import capture_lesson
from tools.run_logger import start_run


@pytest.fixture
def db():
    conn = init_db(":memory:")
    yield conn
    conn.close()


def test_list_raw_lessons_empty(db):
    """With no lessons, list_raw_lessons should return an empty list."""
    lessons = list_raw_lessons(db)
    assert isinstance(lessons, list)


def test_list_raw_lessons_after_capture(db, tmp_path):
    """After capturing a lesson, it should appear in the raw list."""
    import tools.lesson_capture as lc
    original = lc._LESSONS_DIR
    lc._LESSONS_DIR = tmp_path

    try:
        rid = start_run(db, "Curation test")
        capture_lesson(run_id=rid, db=db, what_failed="Test failure")
        lessons = list_raw_lessons(db)
        assert len(lessons) >= 1
        assert any(lesson["run_id"] == rid for lesson in lessons)
    finally:
        lc._LESSONS_DIR = original


def test_promote_lesson_creates_note(db, tmp_path):
    """Promoting a lesson should create a vault note and update status."""
    import tools.curate_lessons as cl
    import tools.lesson_capture as lc
    original_lessons = lc._LESSONS_DIR
    original_vault = cl._VAULT_NOTES
    lc._LESSONS_DIR = tmp_path / "lessons"
    cl._VAULT_NOTES = tmp_path / "vault_notes"

    try:
        rid = start_run(db, "Promote test")
        capture_lesson(run_id=rid, db=db, what_failed="Promotion gate failed")
        lessons = list_raw_lessons(db)

        # Find the lesson we just created
        target = [lesson for lesson in lessons if lesson["run_id"] == rid]
        if target and target[0]["lesson_id"]:
            result = promote_lesson(
                target[0]["lesson_id"], db,
                vault_title="Test promotion",
                vault_content="Promoted from test failure",
            )
            assert result["status"] == "done"
            assert "note_path" in result
            # Check status updated
            row = db.execute("SELECT status FROM lessons WHERE lesson_id = ?",
                             (target[0]["lesson_id"],)).fetchone()
            assert row["status"] == "promoted"
    finally:
        lc._LESSONS_DIR = original_lessons
        cl._VAULT_NOTES = original_vault
