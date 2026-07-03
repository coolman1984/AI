"""Owner feedback loop for executive outputs (D.6)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

VALID_VERDICTS = frozenset({"useful", "corrected", "wrong", "needs_followup"})


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class FeedbackStore:
    """Structured owner verdicts on executive outputs."""

    def __init__(self, path: str = ".brain/output_feedback.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                self._data: list[dict] = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                corrupt_path = self.path.with_name(f"output_feedback.json.corrupt-{ts}")
                self.path.rename(corrupt_path)
                self._data = []
        else:
            self._data = []

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))

    def record_feedback(
        self,
        *,
        output_id: str,
        output_type: str,
        verdict: str,
        note: str = "",
        correction: dict | None = None,
        citation: dict | None = None,
    ) -> dict:
        if not output_id.strip():
            raise ValueError("output_id is required")
        if verdict not in VALID_VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(VALID_VERDICTS)}")

        record = {
            "id": f"feedback-{uuid4().hex[:12]}",
            "output_id": output_id,
            "output_type": output_type,
            "verdict": verdict,
            "note": note,
            "correction": correction,
            "citation": citation,
            "glossary_candidate": glossary_candidate_from_correction(correction),
            "recorded_at": _now_iso(),
        }
        self._data.append(record)
        self._save()
        return dict(record)

    def for_output(self, output_id: str) -> list[dict]:
        return [dict(item) for item in self._data if item.get("output_id") == output_id]

    def all(self) -> list[dict]:
        return [dict(item) for item in self._data]


def glossary_candidate_from_correction(correction: dict | None) -> dict | None:
    """Produce a glossary candidate without auto-accepting it."""
    if not correction:
        return None
    source_term = (correction.get("source_term") or "").strip()
    target_term = (correction.get("target_term") or "").strip()
    if not source_term or not target_term:
        return None
    return {
        "source_term": source_term,
        "target_term": target_term,
        "status": "candidate",
        "reason": correction.get("reason", "owner_correction"),
        "auto_accepted": False,
    }


def record_output_feedback(
    *,
    output_id: str,
    output_type: str,
    verdict: str,
    note: str = "",
    correction: dict | None = None,
    citation: dict | None = None,
    store_path: str = ".brain/output_feedback.json",
) -> dict:
    """Record structured owner feedback without overwriting trusted records."""
    return FeedbackStore(path=store_path).record_feedback(
        output_id=output_id,
        output_type=output_type,
        verdict=verdict,
        note=note,
        correction=correction,
        citation=citation,
    )