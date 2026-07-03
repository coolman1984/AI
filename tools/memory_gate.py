"""Memory admission gate: enforces evidence requirement, duplicate check, sensitive-data routing.

Before a vault note is written, this gate must pass:
1. Evidence required — note must reference a run or source
2. Duplicate title/topic check — no existing note with same title
3. Sensitive-data → approval required
"""

import os
import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VAULT_DIR = _PROJECT_ROOT / "vault"

SENSITIVE_PATTERNS = [
    re.compile(r"salary|wage|pay\b", re.IGNORECASE),
    re.compile(r"personal\s*data", re.IGNORECASE),
    re.compile(r"confidential", re.IGNORECASE),
    re.compile(r"ssn|social.security", re.IGNORECASE),
    re.compile(r"bank.account", re.IGNORECASE),
]


def check_note_admission(
    title: str,
    content: str,
    evidence_run_id: int = None,
    author: str = "foreman",
    db=None,
) -> dict:
    """Check whether a note passes the admission gate.

    Returns dict with:
      - admitted: bool
      - reasons: list[str] — why it was rejected or flagged
      - needs_approval: bool
      - suggested_path: str — where the note should go
    """
    reasons = []
    needs_approval = False

    # 1. Evidence check
    if evidence_run_id is None:
        reasons.append("No evidence run ID provided. Notes must reference a run.")

    # 2. Duplicate title check (against DB)
    if db is not None:
        # Check vault notes table if it exists
        try:
            existing = db.execute(
                "SELECT note_id FROM memory_notes WHERE title = ? AND status = 'active'",
                (title,),
            ).fetchone()
            if existing:
                reasons.append(f"Duplicate title: '{title}' already exists in vault (note_id={existing[0]})")
        except Exception:
            # Table may not exist yet
            pass

    # 3. Sensitive data check
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(content) or pattern.search(title):
            needs_approval = True
            reasons.append(f"Sensitive content detected matching '{pattern.pattern}' — approval required")
            break

    # Suggest path
    suggested_path = str(_VAULT_DIR / "notes" / f"{title.lower().replace(' ', '-')[:50]}.md")

    admitted = len(reasons) == 0 or (len(reasons) == 1 and "evidence" in reasons[0] and needs_approval)

    return {
        "admitted": admitted,
        "reasons": reasons,
        "needs_approval": needs_approval,
        "suggested_path": suggested_path,
    }
