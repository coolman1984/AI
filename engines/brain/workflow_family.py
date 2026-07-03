"""Workflow families and versioning with valid-time vs ingest-time (MASTER_PLAN C.2)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from engines.brain.registry import DocumentRegistry


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_period(period: str) -> tuple[datetime, datetime]:
    """Parse '2025-Q2' or ISO date into (start, end) UTC range."""
    quarter_match = re.fullmatch(r"(\d{4})-Q([1-4])", period.strip())
    if quarter_match:
        year = int(quarter_match.group(1))
        quarter = int(quarter_match.group(2))
        start_month = (quarter - 1) * 3 + 1
        if quarter == 4:
            end = datetime(year, 12, 31, 23, 59, 59, tzinfo=UTC)
        else:
            end_month = start_month + 2
            if end_month == 6:
                end = datetime(year, 6, 30, 23, 59, 59, tzinfo=UTC)
            elif end_month == 9:
                end = datetime(year, 9, 30, 23, 59, 59, tzinfo=UTC)
            else:
                end = datetime(year, 3, 31, 23, 59, 59, tzinfo=UTC)
        start = datetime(year, start_month, 1, tzinfo=UTC)
        return start, end

    iso = datetime.fromisoformat(period.replace("Z", "+00:00"))
    if iso.tzinfo is None:
        iso = iso.replace(tzinfo=UTC)
    return iso, iso


def _overlaps(valid_from: str, valid_to: str | None, start: datetime, end: datetime) -> bool:
    vf = datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
    if vf.tzinfo is None:
        vf = vf.replace(tzinfo=UTC)
    vt = (
        datetime.fromisoformat(valid_to.replace("Z", "+00:00"))
        if valid_to
        else datetime(9999, 12, 31, 23, 59, 59, tzinfo=UTC)
    )
    if vt.tzinfo is None:
        vt = vt.replace(tzinfo=UTC)
    return vf <= end and vt >= start


class WorkflowFamilyStore:
    """Groups workflow record versions into families with bitemporal metadata."""

    def __init__(
        self,
        path: str = ".brain/workflow_families.json",
        registry: DocumentRegistry | None = None,
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.registry = registry or DocumentRegistry()
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                corrupt_path = self.path.with_name(f"workflow_families.json.corrupt-{ts}")
                self.path.rename(corrupt_path)
                payload = {"families": {}}
        else:
            payload = {"families": {}}
        self._families: dict[str, dict] = payload.get("families", {})

    def _save(self) -> None:
        self.path.write_text(json.dumps({"families": self._families}, indent=2))

    def _find_version_by_hash(self, source_hash: str) -> dict | None:
        for family in self._families.values():
            for version in family.get("versions", []):
                if version.get("source_hash") == source_hash:
                    return version
        return None

    def register_workflow_version(
        self,
        *,
        family_id: str,
        family_name: str,
        version_label: str,
        source_hash: str,
        source_path: str,
        valid_from: str,
        valid_to: str | None,
        ingest_run_id: str,
        workflow_record: dict | None = None,
        tier: int = 2,
    ) -> dict:
        if not family_id.strip():
            raise ValueError("family_id is required")
        if not version_label.strip():
            raise ValueError("version_label is required")
        if not source_hash.strip():
            raise ValueError("source_hash is required")

        existing = self._find_version_by_hash(source_hash)
        if existing is not None:
            existing["reconciled"] = True
            existing["ingest_time"] = _now_iso()
            self._save()
            return dict(existing)

        ingest_time = _now_iso()
        version = {
            "version_id": f"ver-{uuid4().hex[:12]}",
            "family_id": family_id,
            "version_label": version_label,
            "source_hash": source_hash,
            "source_path": source_path,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "ingest_time": ingest_time,
            "ingest_run_id": ingest_run_id,
            "workflow_record": workflow_record,
            "reconciled": False,
        }

        family = self._families.setdefault(
            family_id,
            {"family_id": family_id, "name": family_name, "versions": []},
        )
        if family_name:
            family["name"] = family_name
        family["versions"].append(version)

        self.registry.register_document(
            source_path=source_path,
            source_hash=source_hash,
            tier=tier,
            ingest_run_id=ingest_run_id,
            family_id=family_id,
            version_label=version_label,
            status="ingested",
        )
        self._save()
        return dict(version)

    def get_family(self, family_id: str) -> dict | None:
        family = self._families.get(family_id)
        return dict(family) if family is not None else None

    def all_families(self) -> list[dict]:
        return [dict(family) for family in self._families.values()]

    def versions_for_period(self, period: str, *, family_id: str | None = None) -> list[dict]:
        start, end = _parse_period(period)
        matches: list[dict] = []
        for family in self._families.values():
            if family_id is not None and family.get("family_id") != family_id:
                continue
            for version in family.get("versions", []):
                if _overlaps(version["valid_from"], version.get("valid_to"), start, end):
                    matches.append(dict(version))
        return matches

    def get_version(self, version_id: str) -> dict | None:
        for family in self._families.values():
            for version in family.get("versions", []):
                if version.get("version_id") == version_id:
                    return dict(version)
        return None


def get_workflow_family_store(
    path: str = ".brain/workflow_families.json",
    registry_path: str = ".brain/document_registry.json",
) -> WorkflowFamilyStore:
    return WorkflowFamilyStore(
        path=path,
        registry=DocumentRegistry(path=registry_path),
    )