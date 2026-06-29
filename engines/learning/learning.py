"""Learning engine (MASTER_PLAN Part P) — light but real.

Records mistakes/corrections and lets a skill be *proposed*. Skills are NOT auto-trusted:
they enter status 'proposed' and require human approval (risk-tiered). Anything derived
from untrusted documents must be quarantined before it is ever proposed (zombie-agent
defense) — enforced by callers passing trusted=True only for vetted sources.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class LearningStore:
    def __init__(self, path: str = ".brain/learning.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = (
            json.loads(self.path.read_text())
            if self.path.exists()
            else {"errors": [], "skills": [], "decisions": []}
        )
        self._data.setdefault("decisions", [])

    def _save(self):
        self.path.write_text(json.dumps(self._data, indent=2))

    def record_correction(self, symptom: str, root_cause: str, fix: str):
        self._data["errors"].append(
            {"symptom": symptom, "root_cause": root_cause, "fix": fix,
             "ts": datetime.now(UTC).isoformat()}
        )
        self._save()

    def propose_skill(self, name: str, when_to_use: str, body: str, trusted: bool):
        if not trusted:
            raise PermissionError("skill derived from untrusted input — quarantined (Part P)")
        self._data["skills"].append(
            {"name": name, "when_to_use": when_to_use, "body": body, "status": "proposed"}
        )
        self._save()
        return {"name": name, "status": "proposed", "needs": "human approval"}

    def record_decision(self, summary: str, variance: float, approver: str,
                        approved: bool, certainty: float, status: str) -> dict:
        rec = {
            "id": len(self._data["decisions"]) + 1,
            "summary": summary,
            "variance": variance,
            "approver": approver,
            "approved": approved,
            "certainty": certainty,
            "status": status,        # released | held | blocked
            "outcome": None,         # filled later by record_outcome (did the action work?)
            "ts": datetime.now(UTC).isoformat(),
        }
        self._data["decisions"].append(rec)
        self._save()
        return rec

    def record_outcome(self, decision_id: int, worked: bool, note: str = "") -> None:
        for d in self._data["decisions"]:
            if d["id"] == decision_id:
                d["outcome"] = {"worked": worked, "note": note,
                                "ts": datetime.now(UTC).isoformat()}
                self._save()
                return
        raise KeyError(f"decision {decision_id} not found")

    def errors(self):
        return self._data["errors"]

    def skills(self):
        return self._data["skills"]

    def decisions(self):
        return self._data["decisions"]
