"""Lesson capture: after every run, write a lesson template to lessons/."""

import os
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LESSONS_DIR = _PROJECT_ROOT / "lessons"
_LESSON_TEMPLATE = _PROJECT_ROOT / "templates" / "LESSON.md"


def capture_lesson(
    run_id: int,
    db=None,
    what_worked: str = "standard",
    what_failed: str = None,
    owner_correction: str = None,
    edge_case: str = None,
    skill_to_change: str = None,
    tool_to_change: str = None,
    test_to_add: str = None,
    memory_to_create: str = None,
    old_note_wrong: str = None,
    noise_to_ignore: str = None,
) -> dict:
    """Write a lesson file to lessons/RUN-<id>.md and optionally persist to DB.

    Returns dict with status and path.
    """
    _LESSONS_DIR.mkdir(parents=True, exist_ok=True)

    if what_failed is None:
        what_failed = "nothing notable"
    if owner_correction is None:
        owner_correction = "n/a"
    if edge_case is None:
        edge_case = "n/a"
    if skill_to_change is None:
        skill_to_change = "n/a"
    if tool_to_change is None:
        tool_to_change = "n/a"
    if test_to_add is None:
        test_to_add = "n/a"
    if memory_to_create is None:
        memory_to_create = "n/a"
    if old_note_wrong is None:
        old_note_wrong = "n/a"
    if noise_to_ignore is None:
        noise_to_ignore = "n/a"

    lesson_content = f"""# Lesson: RUN-{run_id}

**Run:** {run_id}
**Date:** {datetime.now().strftime('%Y-%m-%d')}

---

## 1. What worked?
{what_worked}

## 2. What failed?
{what_failed}

## 3. What was corrected by the owner?
{owner_correction}

## 4. What was confusing to the owner?
(n/a is an acceptable answer)

## 5. What edge case appeared?
{edge_case}

## 6. Which skill should change?
{skill_to_change}

## 7. Which tool should change?
{tool_to_change}

## 8. Which validation test should be added?
{test_to_add}

## 9. Which memory note should be created?
{memory_to_create}

## 10. Which old note is now wrong?
{old_note_wrong}

## 11. What should be ignored?
{noise_to_ignore}

---

**Category:** { 'correction' if owner_correction and owner_correction != 'n/a' else 'pattern' if edge_case and edge_case != 'n/a' else 'failure' if what_failed and what_failed != 'nothing notable' else 'raw' }
**Status:** raw
"""
    lesson_path = _LESSONS_DIR / f"RUN-{run_id}.md"
    with open(lesson_path, "w") as f:
        f.write(lesson_content)

    # Record in DB if available
    if db is not None:
        # Determine category
        if owner_correction and owner_correction != "n/a":
            category = "correction"
        elif edge_case and edge_case != "n/a":
            category = "pattern"
        elif what_failed and what_failed not in ("nothing notable", "n/a"):
            category = "failure"
        else:
            category = "pattern"

        db.execute(
            "INSERT INTO lessons (run_id, category, description, evidence_run_ids, status) "
            "VALUES (?, ?, ?, ?, 'raw')",
            (run_id, category, what_failed or "nothing notable", str(run_id)),
        )
        db.commit()

    return {
        "status": "done",
        "path": str(lesson_path),
        "run_id": run_id,
    }
