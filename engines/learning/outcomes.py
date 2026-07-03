"""Decision outcome linkage for workflow learning (MASTER_PLAN C.4)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class OutcomeStore:
    """Links workflow records to decision outcomes for traceable learning."""

    def __init__(self, path: str = ".brain/decision_outcomes.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                self._data: list[dict] = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                corrupt_path = self.path.with_name(f"decision_outcomes.json.corrupt-{ts}")
                self.path.rename(corrupt_path)
                self._data = []
        else:
            self._data = []

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))

    def link_decision_outcome(
        self,
        *,
        workflow_ref: str,
        decision_id: int | str,
        summary: str,
        outcome: str,
        evidence: list[dict] | None = None,
    ) -> dict:
        if not workflow_ref.strip():
            raise ValueError("workflow_ref is required")
        if not summary.strip():
            raise ValueError("summary is required")
        if not outcome.strip():
            raise ValueError("outcome is required")

        record = {
            "id": f"outcome-{uuid4().hex[:12]}",
            "workflow_ref": workflow_ref,
            "decision_id": decision_id,
            "summary": summary,
            "outcome": outcome,
            "evidence": evidence or [],
            "linked_at": _now_iso(),
        }
        self._data.append(record)
        self._save()
        return dict(record)

    def get(self, outcome_id: str) -> dict | None:
        for record in self._data:
            if record["id"] == outcome_id:
                return dict(record)
        return None

    def for_workflow(self, workflow_ref: str) -> list[dict]:
        return [dict(record) for record in self._data if record.get("workflow_ref") == workflow_ref]

    def all(self) -> list[dict]:
        return [dict(record) for record in self._data]


def get_outcome_store(path: str = ".brain/decision_outcomes.json") -> OutcomeStore:
    return OutcomeStore(path=path)