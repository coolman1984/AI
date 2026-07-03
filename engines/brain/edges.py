"""Typed cross-workflow edges (MASTER_PLAN F.5)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

VALID_EDGE_TYPES = frozenset(
    {"depends_on", "conflicts_with", "refines", "supersedes"}
)


class EdgeStore:
    """Flat-store typed edges between canonical entity/workflow ids."""

    def __init__(self, path: str = ".brain/edges.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._data: list[dict] = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._data = []

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def link_workflow_edge(
        self,
        *,
        source_id: str,
        target_id: str,
        edge_type: str,
        citation: str = "",
        metadata: dict | None = None,
    ) -> dict:
        if edge_type not in VALID_EDGE_TYPES:
            raise ValueError(
                f"edge_type must be one of {sorted(VALID_EDGE_TYPES)}, got '{edge_type}'"
            )
        if not source_id.strip() or not target_id.strip():
            raise ValueError("source_id and target_id are required")
        record = {
            "edge_id": f"edge-{uuid4().hex[:12]}",
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type,
            "citation": citation,
            "metadata": metadata or {},
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._data.append(record)
        self._save()
        return record

    def edges_for_entity(self, entity_id: str) -> list[dict]:
        return [
            edge
            for edge in self._data
            if edge.get("source_id") == entity_id or edge.get("target_id") == entity_id
        ]

    def all_edges(self) -> list[dict]:
        return list(self._data)