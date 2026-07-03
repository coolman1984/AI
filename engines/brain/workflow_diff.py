"""Deterministic workflow version diff with citations (MASTER_PLAN C.3)."""

from __future__ import annotations

from engines.brain.registry import DocumentRegistry
from engines.brain.workflow_family import WorkflowFamilyStore

_SCALAR_FIELDS = ("purpose",)
_LIST_FIELDS = ("steps", "roles", "kpis", "what_changed", "open_questions", "risks")


def _field_text(field: dict | None) -> str:
    if not field:
        return ""
    return field.get("translated_text", field.get("text", "")).strip()


def _field_citations(field: dict | None) -> list[dict]:
    if not field:
        return []
    return list(field.get("citations", []))


def _list_items(record: dict, field_name: str) -> list[dict]:
    return list(record.get(field_name, []))


def _index_by_text(items: list[dict]) -> dict[str, dict]:
    return {_field_text(item): item for item in items if _field_text(item)}


def diff_workflow_records(old_record: dict, new_record: dict) -> dict:
    added: list[dict] = []
    removed: list[dict] = []
    changed: list[dict] = []

    for field_name in _SCALAR_FIELDS:
        old_field = old_record.get(field_name)
        new_field = new_record.get(field_name)
        old_text = _field_text(old_field)
        new_text = _field_text(new_field)
        if old_text == new_text:
            if old_text and _field_citations(old_field) != _field_citations(new_field):
                changed.append(
                    {
                        "field": field_name,
                        "old_text": old_text,
                        "new_text": new_text,
                        "old_citations": _field_citations(old_field),
                        "new_citations": _field_citations(new_field),
                    }
                )
            continue
        if old_text and not new_text:
            removed.append(
                {
                    "field": field_name,
                    "text": old_text,
                    "old_citations": _field_citations(old_field),
                    "new_citations": [],
                }
            )
        elif new_text and not old_text:
            added.append(
                {
                    "field": field_name,
                    "text": new_text,
                    "old_citations": [],
                    "new_citations": _field_citations(new_field),
                }
            )
        else:
            changed.append(
                {
                    "field": field_name,
                    "old_text": old_text,
                    "new_text": new_text,
                    "old_citations": _field_citations(old_field),
                    "new_citations": _field_citations(new_field),
                }
            )

    for field_name in _LIST_FIELDS:
        old_items = _index_by_text(_list_items(old_record, field_name))
        new_items = _index_by_text(_list_items(new_record, field_name))
        for text, old_item in old_items.items():
            if text not in new_items:
                removed.append(
                    {
                        "field": field_name,
                        "text": text,
                        "old_citations": _field_citations(old_item),
                        "new_citations": [],
                    }
                )
            else:
                new_item = new_items[text]
                if _field_citations(old_item) != _field_citations(new_item):
                    changed.append(
                        {
                            "field": field_name,
                            "old_text": text,
                            "new_text": text,
                            "old_citations": _field_citations(old_item),
                            "new_citations": _field_citations(new_item),
                        }
                    )
        for text, new_item in new_items.items():
            if text not in old_items:
                added.append(
                    {
                        "field": field_name,
                        "text": text,
                        "old_citations": [],
                        "new_citations": _field_citations(new_item),
                    }
                )

    return {
        "old_title": old_record.get("title", ""),
        "new_title": new_record.get("title", ""),
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def diff_workflow_versions(
    *,
    family_id: str,
    old_version_id: str,
    new_version_id: str,
    store: WorkflowFamilyStore | None = None,
    families_path: str = ".brain/workflow_families.json",
    registry_path: str = ".brain/document_registry.json",
) -> dict:
    family_store = store or WorkflowFamilyStore(
        path=families_path,
        registry=DocumentRegistry(path=registry_path),
    )
    family = family_store.get_family(family_id)
    if family is None:
        raise KeyError(f"workflow family '{family_id}' not found")

    old_version = family_store.get_version(old_version_id)
    new_version = family_store.get_version(new_version_id)
    if old_version is None:
        raise KeyError(f"workflow version '{old_version_id}' not found")
    if new_version is None:
        raise KeyError(f"workflow version '{new_version_id}' not found")
    if old_version.get("family_id") != family_id or new_version.get("family_id") != family_id:
        raise ValueError("version ids must belong to the requested family")

    old_record = old_version.get("workflow_record") or {}
    new_record = new_version.get("workflow_record") or {}
    diff = diff_workflow_records(old_record, new_record)
    diff.update(
        {
            "family_id": family_id,
            "old_version_id": old_version_id,
            "new_version_id": new_version_id,
            "old_version_label": old_version.get("version_label"),
            "new_version_label": new_version.get("version_label"),
        }
    )
    return diff