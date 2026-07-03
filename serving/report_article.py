"""Management report and article generator from stored knowledge (D.3)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import uuid4

from engines.brain.registry import DocumentRegistry
from engines.brain.search import search_knowledge
from engines.brain.workflow_family import WorkflowFamilyStore
from shared.contracts.models import EvidenceRef, NumberFact

OUTPUT_TEMPLATES = {
    "management_report": {
        "title_prefix": "Management Report",
        "sections": ("summary", "evidence", "implications"),
    },
    "process_explainer": {
        "title_prefix": "Process Explainer",
        "sections": ("purpose", "steps", "owners"),
    },
    "rollout_summary": {
        "title_prefix": "Rollout Summary",
        "sections": ("what_changed", "risks", "next_steps"),
    },
}


@dataclass
class ReportArticle:
    output_id: str
    output_type: str
    title: str
    paragraphs: list[dict]
    rejected_paragraphs: list[dict]
    signoff_line: str
    signoff_status: str
    release_state: str

    def to_dict(self) -> dict:
        return asdict(self)


def _paragraph(text: str, citations: list[dict]) -> dict:
    return {"text": text, "citations": citations}


def _workflow_records(
    families_path: str,
    registry_path: str,
) -> dict[tuple[str, str], dict]:
    store = WorkflowFamilyStore(
        path=families_path,
        registry=DocumentRegistry(path=registry_path),
    )
    records: dict[tuple[str, str], dict] = {}
    for family in store.all_families():
        for version in family.get("versions", []):
            key = (family.get("family_id", ""), version.get("version_label", ""))
            record = version.get("workflow_record") or {}
            if record:
                records[key] = record
    return records


def _workflow_paragraph(version: dict, section: str, workflow_records: dict[tuple[str, str], dict]) -> dict | None:
    key = (version.get("family_id", ""), version.get("version_label", ""))
    record = workflow_records.get(key, {})
    if section == "purpose":
        text = (record.get("purpose") or {}).get("translated_text")
    elif section == "steps":
        steps = record.get("steps") or []
        text = steps[0].get("translated_text") if steps else None
    elif section == "owners":
        roles = record.get("roles") or []
        text = roles[0].get("translated_text") if roles else None
    elif section == "what_changed":
        changes = record.get("what_changed") or []
        text = changes[0].get("translated_text") if changes else None
    elif section == "risks":
        risks = record.get("risks") or []
        text = risks[0].get("translated_text") if risks else None
    elif section == "next_steps":
        questions = record.get("open_questions") or []
        text = questions[0].get("translated_text") if questions else None
    elif section == "summary":
        text = record.get("title") or version.get("title")
    elif section == "evidence":
        text = (record.get("purpose") or {}).get("translated_text")
    elif section == "implications":
        kpis = record.get("kpis") or []
        text = kpis[0].get("translated_text") if kpis else None
    else:
        text = None

    if not text:
        return None

    citations = _citations_for_section(record, section)
    if not citations:
        return None
    return _paragraph(text, citations)


def _field_items(record: dict, field_name: str) -> list[dict]:
    value = record.get(field_name)
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _citations_for_section(record: dict, section: str) -> list[dict]:
    section_fields = {
        "purpose": ("purpose",),
        "steps": ("steps",),
        "owners": ("roles",),
        "what_changed": ("what_changed",),
        "risks": ("risks",),
        "next_steps": ("open_questions",),
        "summary": ("purpose",),
        "evidence": ("purpose",),
        "implications": ("kpis",),
    }
    for field_name in section_fields.get(section, ("purpose",)):
        for item in _field_items(record, field_name):
            citations = item.get("citations") or []
            if citations:
                return list(citations)
    return []


def _number_paragraph(payload: dict) -> dict:
    evidence = EvidenceRef(
        source=payload.get("source", ""),
        locator=payload.get("locator", ""),
        method=payload.get("method", ""),
        value=payload.get("value"),
    )
    fact = NumberFact(
        label=payload.get("label", "metric"),
        value=float(payload["value"]),
        evidence=evidence,
    )
    if not evidence.resolves():
        raise ValueError("numeric paragraph requires resolving evidence")
    return _paragraph(
        f"{fact.label}: {fact.value:+,.0f} [{fact.tag}]",
        [
            {
                "source": fact.evidence.source,
                "locator": fact.evidence.locator,
                "method": fact.evidence.method,
            }
        ],
    )


def build_report_article(
    *,
    output_type: str,
    topic: str,
    numeric_evidence: list[dict] | None = None,
    registry_path: str = ".brain/document_registry.json",
    families_path: str = ".brain/workflow_families.json",
    claims_path: str = ".brain/claims.json",
    questions_path: str = ".brain/open_questions.json",
    signoff_line: str = "Pending owner sign-off",
) -> ReportArticle:
    """Produce a cited management report/article from stored knowledge."""
    if output_type not in OUTPUT_TEMPLATES:
        raise ValueError(f"unsupported output_type '{output_type}'")
    if not topic.strip():
        raise ValueError("topic is required")

    template = OUTPUT_TEMPLATES[output_type]
    workflow_records = _workflow_records(families_path, registry_path)
    knowledge = search_knowledge(
        topic,
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
        include_contradictions=False,
    )

    paragraphs: list[dict] = []
    rejected: list[dict] = []

    for section in template["sections"]:
        added = False
        for version in knowledge.get("workflow_versions", []):
            paragraph = _workflow_paragraph(version, section, workflow_records)
            if paragraph is None:
                continue
            paragraphs.append({**paragraph, "section": section})
            added = True
            break
        if not added:
            rejected.append({"section": section, "reason": "no_cited_workflow_content"})

    for payload in numeric_evidence or []:
        try:
            paragraphs.append({**_number_paragraph(payload), "section": "numeric_evidence"})
        except ValueError as exc:
            rejected.append({"section": "numeric_evidence", "reason": str(exc)})

    if not paragraphs:
        raise ValueError("report article requires at least one cited paragraph")

    return ReportArticle(
        output_id=f"article-{uuid4().hex[:12]}",
        output_type=output_type,
        title=f"{template['title_prefix']}: {topic.strip()}",
        paragraphs=paragraphs,
        rejected_paragraphs=rejected,
        signoff_line=signoff_line,
        signoff_status="pending",
        release_state="draft",
    )