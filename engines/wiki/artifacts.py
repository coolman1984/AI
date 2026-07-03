"""Deterministic markdown knowledge artifacts (MASTER_PLAN C.5)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from engines.docs.provenance import source_hash_for


def artifact_path_for(
    *,
    source_hash: str,
    record_type: str,
    base_dir: str | Path = "knowledge",
) -> Path:
    safe_type = re.sub(r"[^a-zA-Z0-9_-]+", "-", record_type.strip().lower()) or "record"
    short_hash = source_hash[:12]
    return Path(base_dir) / safe_type / f"{short_hash}.md"


def _format_citations(citations: list[dict]) -> str:
    if not citations:
        return "- none"
    lines = []
    for citation in citations:
        locator = citation.get("locator", "")
        source = citation.get("source", "")
        lines.append(f"- `{source}` @ {locator}")
    return "\n".join(lines)


def _format_field_block(title: str, field: dict) -> str:
    text = field.get("translated_text", field.get("text", ""))
    citations = field.get("citations", [])
    return f"### {title}\n\n{text}\n\n{_format_citations(citations)}\n"


def render_workflow_artifact(record: dict) -> str:
    provenance = record.get("provenance", {})
    lines = [
        f"# {record.get('title', 'Workflow Record')}",
        "",
        "## Provenance",
        "",
        f"- source_hash: `{provenance.get('source_hash', '')}`",
        f"- source_id: `{provenance.get('source_id', '')}`",
        f"- ingest_run_id: `{provenance.get('ingest_run_id', '')}`",
        f"- model: `{provenance.get('model_name', '')}` `{provenance.get('model_version', '')}`",
        f"- prompt_version: `{provenance.get('prompt_version', '')}`",
        f"- timestamp: `{provenance.get('timestamp', '')}`",
        f"- confidence: `{provenance.get('confidence', '')}`",
        "",
        "## Purpose",
        "",
    ]
    lines.append(_format_field_block("Purpose", record.get("purpose", {})))

    for field_name in ("steps", "roles", "kpis", "what_changed", "open_questions", "risks"):
        items = record.get(field_name, [])
        if not items:
            continue
        lines.append(f"## {field_name.replace('_', ' ').title()}")
        lines.append("")
        for index, item in enumerate(items, start=1):
            lines.append(_format_field_block(f"{field_name[:-1].title()} {index}", item))

    return "\n".join(lines).strip() + "\n"


def write_knowledge_artifact(
    *,
    record: dict,
    record_type: str,
    base_dir: str | Path = "knowledge",
) -> dict:
    provenance = record.get("provenance", {})
    source_hash = provenance.get("source_hash")
    if not source_hash:
        source_material = json.dumps(record, sort_keys=True)
        source_hash = source_hash_for(source_material)

    path = artifact_path_for(
        source_hash=source_hash,
        record_type=record_type,
        base_dir=base_dir,
    )
    path.parent.mkdir(parents=True, exist_ok=True)

    content = render_workflow_artifact(record)
    reconciled = path.exists()
    path.write_text(content, encoding="utf-8")

    return {
        "path": str(path),
        "source_hash": source_hash,
        "record_type": record_type,
        "reconciled": reconciled,
        "bytes": len(content.encode("utf-8")),
    }