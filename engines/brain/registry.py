"""Document registry — map of every ingested document (MASTER_PLAN C.1)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

VALID_STATUSES = frozenset({"registered", "ingesting", "ingested", "failed", "archived"})

VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    "registered": frozenset({"ingesting", "failed"}),
    "ingesting": frozenset({"ingested", "failed"}),
    "failed": frozenset({"registered", "archived"}),
    "ingested": frozenset({"archived"}),
    "archived": frozenset(),
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class DocumentRegistry:
    """Queryable registry of ingested documents with hash-based deduplication."""

    def __init__(self, path: str = ".brain/document_registry.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                self._data: list[dict] = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                corrupt_path = self.path.with_name(f"document_registry.json.corrupt-{ts}")
                self.path.rename(corrupt_path)
                self._data = []
        else:
            self._data = []

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))

    def _by_hash(self, source_hash: str) -> dict | None:
        for record in self._data:
            if record.get("source_hash") == source_hash and record.get("is_current", True):
                return record
        return None

    def _by_id(self, doc_id: str) -> dict | None:
        for record in self._data:
            if record.get("doc_id") == doc_id:
                return record
        return None

    def register_document(
        self,
        *,
        source_path: str,
        source_hash: str,
        tier: int,
        ingest_run_id: str,
        status: str = "registered",
        family_id: str | None = None,
        version_label: str | None = None,
    ) -> dict:
        if not source_hash.strip():
            raise ValueError("source_hash is required")
        if tier not in (1, 2):
            raise ValueError("tier must be 1 or 2")
        if status not in VALID_STATUSES:
            raise ValueError(f"unknown status '{status}'")

        existing = self._by_hash(source_hash)
        if existing is not None:
            existing["reconciled"] = True
            if family_id and not existing.get("family_id"):
                existing["family_id"] = family_id
            if version_label and not existing.get("version_label"):
                existing["version_label"] = version_label
            existing["updated_at"] = _now_iso()
            self._save()
            return dict(existing)

        now = _now_iso()
        record = {
            "doc_id": f"doc-{uuid4().hex[:12]}",
            "source_path": source_path,
            "source_hash": source_hash,
            "tier": tier,
            "status": status,
            "family_id": family_id,
            "version_label": version_label,
            "ingest_run_id": ingest_run_id,
            "is_current": True,
            "registered_at": now,
            "updated_at": now,
            "reconciled": False,
        }
        self._data.append(record)
        self._save()
        return dict(record)

    def update_status(self, doc_id: str, status: str) -> dict:
        if status not in VALID_STATUSES:
            raise ValueError(f"unknown status '{status}'")
        record = self._by_id(doc_id)
        if record is None:
            raise KeyError(f"document '{doc_id}' not found")
        current = record["status"]
        if status != current and status not in VALID_TRANSITIONS.get(current, frozenset()):
            raise ValueError(f"invalid status transition from '{current}' to '{status}'")
        record["status"] = status
        record["updated_at"] = _now_iso()
        self._save()
        return dict(record)

    def get(self, doc_id: str) -> dict | None:
        record = self._by_id(doc_id)
        return dict(record) if record is not None else None

    def all(self) -> list[dict]:
        return [dict(record) for record in self._data]

    def query(
        self,
        *,
        family_id: str | None = None,
        status: str | None = None,
        tier: int | None = None,
    ) -> list[dict]:
        results = self.all()
        if family_id is not None:
            results = [r for r in results if r.get("family_id") == family_id]
        if status is not None:
            if status not in VALID_STATUSES:
                raise ValueError(f"unknown status '{status}'")
            results = [r for r in results if r.get("status") == status]
        if tier is not None:
            results = [r for r in results if r.get("tier") == tier]
        return results


def get_document_registry(path: str = ".brain/document_registry.json") -> DocumentRegistry:
    return DocumentRegistry(path=path)