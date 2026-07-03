"""Weekly curation helper: list raw lessons, promote/merge/reject.

Helps the owner curate raw lessons into vault notes during the weekly 15-minute review.
"""

import shutil
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LESSONS_DIR = _PROJECT_ROOT / "lessons"
_VAULT_NOTES = _PROJECT_ROOT / "vault" / "notes"


def list_raw_lessons(db=None) -> list[dict]:
    """List all raw (uncurated) lessons. Returns list of dicts with lesson metadata."""
    results = []

    # From DB
    if db is not None:
        try:
            rows = db.execute(
                "SELECT * FROM lessons WHERE status = 'raw' ORDER BY lesson_id"
            ).fetchall()
            for row in rows:
                results.append({
                    "lesson_id": row["lesson_id"],
                    "run_id": row["run_id"],
                    "category": row["category"],
                    "description": row["description"][:100],
                    "status": row["status"],
                })
        except Exception:
            pass

    # From files (lessons dir)
    if _LESSONS_DIR.exists():
        for f in sorted(_LESSONS_DIR.glob("*.md")):
            existing = {r.get("run_id") for r in results}
            # Extract run_id from filename
            name = f.stem
            if name.startswith("RUN-"):
                try:
                    rid = int(name.split("-")[1])
                    if rid not in existing:
                        results.append({
                            "lesson_id": None,
                            "run_id": rid,
                            "category": "raw",
                            "description": f"File: {f.name}",
                            "status": "raw",
                            "file_path": str(f),
                        })
                except (ValueError, IndexError):
                    pass

    return results


def promote_lesson(
    lesson_id: int,
    db,
    vault_title: str,
    vault_content: str,
) -> dict:
    """Promote a raw lesson to a vault note. Updates status to 'promoted' and writes vault note."""
    row = db.execute("SELECT * FROM lessons WHERE lesson_id = ?", (lesson_id,)).fetchone()
    if not row:
        return {"status": "failed", "error": "Lesson not found"}

    # Write vault note
    _VAULT_NOTES.mkdir(parents=True, exist_ok=True)
    filename = f"lesson-{vault_title.lower().replace(' ', '-')[:40]}.md"
    note_path = _VAULT_NOTES / filename

    content = f"""---
type: lesson
title: {vault_title}
source_run: {row['run_id']}
category: {row['category']}
status: promoted
---

{vault_content}
"""
    with open(note_path, "w") as f:
        f.write(content)

    # Update DB
    db.execute(
        "UPDATE lessons SET status = 'promoted' WHERE lesson_id = ?",
        (lesson_id,),
    )
    db.commit()

    return {
        "status": "done",
        "note_path": str(note_path),
        "lesson_id": lesson_id,
    }
