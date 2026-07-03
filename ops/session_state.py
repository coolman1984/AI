"""Session-state persistence for agent resume (MASTER_PLAN F.9)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

_FORBIDDEN_PATTERNS = (
    re.compile(r"\b\d{10,}\b"),  # long numeric sequences (SAP-scale rows)
    re.compile(r"password|secret|api[_-]?key", re.IGNORECASE),
)

_SESSION_TEMPLATE = """# Session State

> Auto-updated by `write_session_state`. Concise resume snapshot only.

| Field | Value |
|---|---|
| Updated | {updated_at} |
| Current phase | {current_phase} |
| Next action | {next_action} |

## Blockers

{blockers}

## Evidence pointers

{evidence_pointers}

## Notes

{notes}
"""


def _sanitize_text(value: str) -> str:
    text = value.strip()
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(text):
            raise ValueError("session state must not contain sensitive raw data")
    if len(text) > 2000:
        raise ValueError("session state field exceeds safe length")
    return text


def write_session_state(
    *,
    current_phase: str,
    next_action: str,
    blockers: list[str] | None = None,
    evidence_pointers: list[str] | None = None,
    notes: str = "",
    output_path: str | Path = "00_control/session_state.md",
) -> dict:
    blockers_text = "\n".join(f"- {_sanitize_text(item)}" for item in (blockers or [])) or "- none"
    evidence_text = (
        "\n".join(f"- {_sanitize_text(item)}" for item in (evidence_pointers or [])) or "- none"
    )
    payload = {
        "updated_at": datetime.now(UTC).isoformat(),
        "current_phase": _sanitize_text(current_phase),
        "next_action": _sanitize_text(next_action),
        "blockers": blockers or [],
        "evidence_pointers": evidence_pointers or [],
        "notes": _sanitize_text(notes) if notes else "Concise resume snapshot.",
    }
    content = _SESSION_TEMPLATE.format(
        updated_at=payload["updated_at"],
        current_phase=payload["current_phase"],
        next_action=payload["next_action"],
        blockers=blockers_text,
        evidence_pointers=evidence_text,
        notes=payload["notes"],
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return payload


def update_restart_notes(
    session_summary: dict,
    *,
    restart_notes_path: str | Path = "00_control/restart_notes.md",
    marker: str = "<!-- session-state:auto -->",
) -> str:
    """Append or replace auto session block without deleting manual restart notes."""
    path = Path(restart_notes_path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    auto_block = (
        f"\n{marker}\n"
        f"**Auto session ({session_summary.get('updated_at', '')}):** "
        f"phase={session_summary.get('current_phase', '')}; "
        f"next={session_summary.get('next_action', '')}\n"
    )
    if marker in existing:
        head, _, tail = existing.partition(marker)
        tail_lines = tail.splitlines()
        # drop previous auto block (until next numbered section or EOF)
        cleaned_tail = []
        skip = True
        for line in tail_lines:
            if skip and (line.startswith("**Auto session") or line.strip() == ""):
                continue
            skip = False
            cleaned_tail.append(line)
        updated = head.rstrip() + auto_block + "\n".join(cleaned_tail).lstrip()
    else:
        updated = existing.rstrip() + auto_block
    path.write_text(updated, encoding="utf-8")
    return updated