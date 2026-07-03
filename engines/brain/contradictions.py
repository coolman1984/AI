"""Contradiction surfacing across claims and workflow records (MASTER_PLAN C.7)."""

from __future__ import annotations

import re

from engines.brain.claims import ClaimsStore
from engines.brain.workflow_family import WorkflowFamilyStore


def _normalize_entity(entity: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", entity.strip().lower()).strip("_")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _extract_numeric(text: str) -> str | None:
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", text.replace(",", ""))
    return match.group(0) if match else None


def _entity_from_text(text: str) -> str:
    match = re.match(r"^(.+?)\s+is\b", text.strip(), flags=re.IGNORECASE)
    if match:
        return _normalize_entity(match.group(1))
    words = _normalize_text(text).split()
    return words[0] if words else "unknown"


def _claim_key(entity: str, text: str) -> tuple[str, str]:
    resolved_entity = entity or _entity_from_text(text)
    numeric = _extract_numeric(text)
    key = numeric if numeric is not None else _normalize_text(text)
    return _normalize_entity(resolved_entity), key


def _claims_from_workflow_records(store: WorkflowFamilyStore) -> list[dict]:
    claims: list[dict] = []
    for family in store.all_families():
        for version in family.get("versions", []):
            record = version.get("workflow_record") or {}
            for kpi in record.get("kpis", []):
                text = kpi.get("translated_text", kpi.get("text", ""))
                if not text:
                    continue
                entity = _normalize_entity(text.split()[0]) or "kpi"
                claims.append(
                    {
                        "entity": entity,
                        "text": text,
                        "source": version.get("source_path", record.get("source_document", "")),
                        "citations": kpi.get("citations", []),
                        "kind": "workflow_kpi",
                        "version_id": version.get("version_id"),
                    }
                )
    return claims


def find_contradictions(
    *,
    claims_store: ClaimsStore | None = None,
    workflow_store: WorkflowFamilyStore | None = None,
    claims_path: str = ".brain/claims.json",
    families_path: str = ".brain/workflow_families.json",
    registry_path: str = ".brain/document_registry.json",
) -> list[dict]:
    """Surface conflicts without auto-resolving them."""
    from engines.brain.registry import DocumentRegistry

    cs = claims_store or ClaimsStore(path=claims_path)
    ws = workflow_store or WorkflowFamilyStore(
        path=families_path,
        registry=DocumentRegistry(path=registry_path),
    )

    indexed: dict[tuple[str, str], list[dict]] = {}

    for claim in cs.all():
        text = claim.get("text", "")
        entity = _entity_from_text(text)
        key = _claim_key(entity, text)
        indexed.setdefault(key, []).append(
            {
                "entity": entity,
                "text": text,
                "source": claim.get("source_doc", ""),
                "citations": [{"citation": claim.get("citation"), "page": claim.get("page")}],
                "kind": "claim",
            }
        )

    for claim in _claims_from_workflow_records(ws):
        key = _claim_key(claim["entity"], claim["text"])
        indexed.setdefault(key, []).append(claim)

    contradictions: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()

    all_items: list[dict] = []
    for entries in indexed.values():
        all_items.extend(entries)

    grouped: dict[str, list[dict]] = {}
    for item in all_items:
        entity = _normalize_entity(item.get("entity", "") or _entity_from_text(item.get("text", "")))
        grouped.setdefault(entity, []).append(item)

    for entity, entries in grouped.items():
        for index, left in enumerate(entries):
            for right in entries[index + 1 :]:
                if _normalize_text(left.get("text", "")) == _normalize_text(right.get("text", "")):
                    continue

                left_value = _extract_numeric(left.get("text", ""))
                right_value = _extract_numeric(right.get("text", ""))
                if left_value is None or right_value is None:
                    continue
                if left_value == right_value:
                    continue

                pair_key = tuple(sorted([str(left.get("source")), str(right.get("source"))]))
                dedupe_key = (entity, pair_key[0], pair_key[1])
                if dedupe_key in seen_pairs:
                    continue
                seen_pairs.add(dedupe_key)

                contradictions.append(
                    {
                        "entity": entity,
                        "left": {
                            "text": left.get("text"),
                            "source": left.get("source"),
                            "citations": left.get("citations", []),
                            "kind": left.get("kind"),
                        },
                        "right": {
                            "text": right.get("text"),
                            "source": right.get("source"),
                            "citations": right.get("citations", []),
                            "kind": right.get("kind"),
                        },
                        "requires_human_resolution": True,
                    }
                )

    return contradictions