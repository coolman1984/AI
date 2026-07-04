"""Approval queue: request approval for external_send, skill_promotion, write_action, sensitive_memory."""

from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Tests may monkeypatch this to tmp_path / "approvals"
_APPROVALS_ROOT = _PROJECT_ROOT / "workspace" / "approvals"

VALID_TYPES = {"external_send", "skill_promotion", "write_action", "sensitive_memory"}


def _pending_decided():
    return _APPROVALS_ROOT / "pending", _APPROVALS_ROOT / "decided"


def request_approval(
    db,
    run_id: int = None,
    approval_type: str = "write_action",
    request_md: str = "",
) -> int:
    """Request an approval: writes a file to approvals/pending/ and an approvals row.

    Returns approval_id.
    """
    if approval_type not in VALID_TYPES:
        raise ValueError(f"Invalid approval type: {approval_type}. Must be one of {VALID_TYPES}")

    pending_dir, _ = _pending_decided()
    pending_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{approval_type}_run{run_id or 'none'}.md"
    filepath = pending_dir / filename

    content = f"""# Approval Request: {approval_type}
**Date:** {datetime.now().isoformat()}
**Run ID:** {run_id or 'N/A'}
**Type:** {approval_type}

---

{request_md}

---

**Status:** pending
**Decision:**
**Decided by:**
**Decided at:**
"""
    with open(filepath, "w") as f:
        f.write(content)

    cur = db.execute(
        "INSERT INTO approvals (run_id, type, request_path) VALUES (?, ?, ?)",
        (run_id, approval_type, str(filepath)),
    )
    db.commit()
    return cur.lastrowid


def decide_approval(
    db,
    approval_id: int,
    decision: str,
    decided_by: str,
) -> dict:
    """Record an approval decision: move file to decided/, update DB row.

    Returns the updated approval record.
    """
    if decision not in ("approved", "rejected"):
        raise ValueError("Decision must be 'approved' or 'rejected'")

    row = db.execute(
        "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"Approval {approval_id} not found")

    _, decided_dir = _pending_decided()
    old_path = Path(row["request_path"])
    if old_path.exists():
        decided_dir.mkdir(parents=True, exist_ok=True)
        new_path = decided_dir / old_path.name
        old_path.rename(new_path)

    now = datetime.now().isoformat()
    db.execute(
        "UPDATE approvals SET decision = ?, decided_by = ?, decided_at = ? "
        "WHERE approval_id = ?",
        (decision, decided_by, now, approval_id),
    )
    db.commit()

    updated = db.execute(
        "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
    ).fetchone()
    return dict(updated)