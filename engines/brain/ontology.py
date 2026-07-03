"""Canonical entity IDs and alias resolution (MASTER_PLAN F.5)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def _normalize_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


class OntologyStore:
    """Flat-store ontology with alias resolution and conflict review."""

    def __init__(self, path: str = ".brain/ontology.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._data: dict = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._data = {"entities": {}, "aliases": {}, "conflicts": []}
        self._data.setdefault("entities", {})
        self._data.setdefault("aliases", {})
        self._data.setdefault("conflicts", [])

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def register_entity(
        self,
        *,
        canonical_name: str,
        entity_type: str,
        aliases: list[str] | None = None,
    ) -> dict:
        entity_id = f"ent-{uuid4().hex[:12]}"
        record = {
            "entity_id": entity_id,
            "canonical_name": canonical_name,
            "entity_type": entity_type,
            "aliases": list(aliases or []),
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._data["entities"][entity_id] = record
        for alias in [canonical_name, *(aliases or [])]:
            key = _normalize_alias(alias)
            existing = self._data["aliases"].get(key)
            if existing and existing != entity_id:
                self._data["conflicts"].append(
                    {
                        "alias": alias,
                        "existing_entity_id": existing,
                        "new_entity_id": entity_id,
                        "status": "needs_review",
                    }
                )
            else:
                self._data["aliases"][key] = entity_id
        self._save()
        return record

    def resolve_entity(self, alias: str) -> dict:
        key = _normalize_alias(alias)
        entity_id = self._data["aliases"].get(key)
        if not entity_id:
            return {"resolved": False, "alias": alias, "entity_id": None}
        conflict = next(
            (c for c in self._data["conflicts"] if _normalize_alias(c["alias"]) == key),
            None,
        )
        if conflict:
            return {
                "resolved": False,
                "alias": alias,
                "entity_id": entity_id,
                "needs_review": True,
                "conflict": conflict,
            }
        entity = self._data["entities"].get(entity_id, {})
        return {
            "resolved": True,
            "alias": alias,
            "entity_id": entity_id,
            "canonical_name": entity.get("canonical_name"),
            "entity_type": entity.get("entity_type"),
        }

    def get_entity(self, entity_id: str) -> dict | None:
        return self._data["entities"].get(entity_id)

    def list_conflicts(self) -> list[dict]:
        return list(self._data["conflicts"])