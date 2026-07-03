"""Queryable open questions with resolution evidence (MASTER_PLAN C.4)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

VALID_STATUSES = frozenset({"open", "resolved"})


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class OpenQuestionsStore:
    """Stores open questions as first-class queryable items."""

    def __init__(self, path: str = ".brain/open_questions.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                self._data: list[dict] = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                corrupt_path = self.path.with_name(f"open_questions.json.corrupt-{ts}")
                self.path.rename(corrupt_path)
                self._data = []
        else:
            self._data = []

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))

    def add_question(
        self,
        *,
        text: str,
        source: str,
        owner: str,
        evidence: list[dict],
        workflow_ref: str | None = None,
        decision_outcome_id: str | None = None,
    ) -> dict:
        if not text.strip():
            raise ValueError("text is required")
        if not source.strip():
            raise ValueError("source is required")
        if not owner.strip():
            raise ValueError("owner is required")
        if not evidence:
            raise ValueError("evidence is required")

        record = {
            "id": f"oq-{uuid4().hex[:12]}",
            "text": text,
            "status": "open",
            "source": source,
            "owner": owner,
            "evidence": evidence,
            "resolver": None,
            "resolved_by_what": None,
            "workflow_ref": workflow_ref,
            "decision_outcome_id": decision_outcome_id,
            "created_at": _now_iso(),
            "resolved_at": None,
        }
        self._data.append(record)
        self._save()
        return dict(record)

    def resolve_question(
        self,
        question_id: str,
        *,
        resolver: str,
        resolved_by_what: dict,
    ) -> dict:
        if not resolver.strip():
            raise ValueError("resolver is required")
        if not resolved_by_what:
            raise ValueError("resolved_by_what evidence is required")

        for record in self._data:
            if record["id"] == question_id:
                if record["status"] == "resolved":
                    raise ValueError(f"question '{question_id}' is already resolved")
                record["status"] = "resolved"
                record["resolver"] = resolver
                record["resolved_by_what"] = resolved_by_what
                record["resolved_at"] = _now_iso()
                self._save()
                return dict(record)
        raise KeyError(f"open question '{question_id}' not found")

    def link_decision_outcome(self, question_id: str, decision_outcome_id: str) -> dict:
        for record in self._data:
            if record["id"] == question_id:
                record["decision_outcome_id"] = decision_outcome_id
                self._save()
                return dict(record)
        raise KeyError(f"open question '{question_id}' not found")

    def get(self, question_id: str) -> dict | None:
        for record in self._data:
            if record["id"] == question_id:
                return dict(record)
        return None

    def list_questions(
        self,
        *,
        status: str | None = None,
        owner: str | None = None,
        workflow_ref: str | None = None,
        include_resolved: bool = True,
    ) -> list[dict]:
        results = [dict(record) for record in self._data]
        if status is not None:
            if status not in VALID_STATUSES:
                raise ValueError(f"unknown status '{status}'")
            results = [r for r in results if r["status"] == status]
        elif not include_resolved:
            results = [r for r in results if r["status"] == "open"]
        if owner is not None:
            results = [r for r in results if r.get("owner") == owner]
        if workflow_ref is not None:
            results = [r for r in results if r.get("workflow_ref") == workflow_ref]
        return results


def get_open_questions_store(path: str = ".brain/open_questions.json") -> OpenQuestionsStore:
    return OpenQuestionsStore(path=path)