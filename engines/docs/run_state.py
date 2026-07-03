"""Resumable run state for long LLM-backed ingestion (MASTER_PLAN F.4)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class RunStateStore:
    """Persist chunk checkpoints without storing raw full document text."""

    def __init__(self, path: str = ".brain/run_state.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._data: dict[str, dict] = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._data = {}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def start_run(
        self,
        run_id: str,
        *,
        source_path: str,
        doc_id: str,
        chunk_ids: list[str],
    ) -> dict:
        record = {
            "run_id": run_id,
            "source_path": source_path,
            "doc_id": doc_id,
            "chunk_ids": list(chunk_ids),
            "completed_chunks": [],
            "chunk_summaries": {},
            "status": "in_progress",
            "started_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self._data[run_id] = record
        self._save()
        return record

    def get_run(self, run_id: str) -> dict | None:
        return self._data.get(run_id)

    def is_chunk_completed(self, run_id: str, chunk_id: str) -> bool:
        run = self._data.get(run_id)
        if not run:
            return False
        return chunk_id in run.get("completed_chunks", [])

    def complete_chunk(self, run_id: str, chunk_id: str, summary_text: str) -> dict:
        run = self._data.get(run_id)
        if run is None:
            raise KeyError(f"run_id '{run_id}' not found")
        if chunk_id not in run.get("chunk_ids", []):
            raise ValueError(f"unknown chunk_id '{chunk_id}' for run '{run_id}'")
        completed = run.setdefault("completed_chunks", [])
        if chunk_id not in completed:
            completed.append(chunk_id)
        summaries = run.setdefault("chunk_summaries", {})
        summaries[chunk_id] = summary_text
        run["updated_at"] = datetime.now(UTC).isoformat()
        if set(completed) >= set(run.get("chunk_ids", [])):
            run["status"] = "completed"
        self._save()
        return run

    def pending_chunks(self, run_id: str) -> list[str]:
        run = self._data.get(run_id)
        if not run:
            return []
        done = set(run.get("completed_chunks", []))
        return [chunk_id for chunk_id in run.get("chunk_ids", []) if chunk_id not in done]

    def assert_no_raw_document_text(self, run_id: str) -> None:
        """Guard that persisted state never stores full document bodies."""
        run = self._data.get(run_id)
        if not run:
            return
        forbidden = ("full_text", "raw_document", "document_text", "page_text")
        for key in forbidden:
            if key in run:
                raise ValueError(f"run state must not store raw document field '{key}'")
        for value in run.get("chunk_summaries", {}).values():
            if isinstance(value, str) and len(value) > 5000:
                raise ValueError("chunk summary in run state exceeds safe size")