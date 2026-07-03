"""CFO/CEO meeting pack assembler from stored knowledge (D.2)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import uuid4

from engines.brain.open_questions import OpenQuestionsStore
from engines.brain.registry import DocumentRegistry
from engines.brain.search import search_knowledge
from engines.brain.workflow_family import WorkflowFamilyStore
from shared.contracts.models import EvidenceRef, NumberFact


@dataclass
class MeetingPack:
    output_id: str
    topic: str
    period: str
    audited_numbers: list[dict]
    workflow_knowledge: list[dict]
    risks: list[dict]
    open_questions: list[dict]
    talking_points: list[dict]
    signoff_line: str
    signoff_status: str
    release_state: str

    def to_dict(self) -> dict:
        return asdict(self)


def _render_audited_number(payload: dict | None) -> dict:
    if payload is None:
        return {"label": "missing", "status": "missing", "tag": None, "value": None}
    try:
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
            return {
                "label": payload.get("label", "metric"),
                "status": "missing",
                "tag": None,
                "value": None,
            }
        return {
            "label": fact.label,
            "value": fact.value,
            "tag": fact.tag,
            "status": "present",
            "citations": [
                {
                    "source": fact.evidence.source,
                    "locator": fact.evidence.locator,
                    "method": fact.evidence.method,
                }
            ],
        }
    except (KeyError, TypeError, ValueError):
        return {
            "label": payload.get("label", "metric") if payload else "missing",
            "status": "missing",
            "tag": None,
            "value": None,
        }


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


def _talking_point_from_workflow(version: dict, workflow_records: dict[tuple[str, str], dict]) -> dict | None:
    key = (version.get("family_id", ""), version.get("version_label", ""))
    record = workflow_records.get(key, {})
    purpose = record.get("purpose") or {}
    text = purpose.get("translated_text") or version.get("title") or version.get("family_name")
    if not text:
        return None
    citations = purpose.get("citations") or [
        {
            "source": f"workflow:{version.get('family_id')}",
            "locator": version.get("version_label", ""),
            "method": "stored workflow record",
        }
    ]
    return {"text": text, "citations": citations}


def build_meeting_pack(
    *,
    topic: str,
    period: str,
    audited_numbers: list[dict] | None = None,
    registry_path: str = ".brain/document_registry.json",
    families_path: str = ".brain/workflow_families.json",
    claims_path: str = ".brain/claims.json",
    questions_path: str = ".brain/open_questions.json",
    signoff_line: str = "Pending owner sign-off",
) -> MeetingPack:
    """Assemble a meeting pack from brain stores — never from prompt memory."""
    if not topic.strip():
        raise ValueError("topic is required")
    if not period.strip():
        raise ValueError("period is required")

    knowledge = search_knowledge(
        topic,
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
        include_contradictions=True,
    )

    numbers = [_render_audited_number(item) for item in (audited_numbers or [])]
    if not numbers:
        numbers = [{"label": "audited headline number", "status": "missing", "tag": None, "value": None}]

    workflow_knowledge = [
        {
            "family_id": version.get("family_id"),
            "version_label": version.get("version_label"),
            "title": version.get("title"),
            "valid_from": version.get("valid_from"),
            "valid_to": version.get("valid_to"),
        }
        for version in knowledge.get("workflow_versions", [])
    ]

    risks = [
        {
            "text": f"Unresolved contradiction on {item.get('entity')}",
            "citations": [
                {
                    "source": item.get("left", {}).get("source_doc", "claims"),
                    "locator": item.get("left", {}).get("citation", ""),
                    "method": "contradiction view",
                }
            ],
        }
        for item in knowledge.get("contradictions", [])
    ]

    questions_store = OpenQuestionsStore(path=questions_path)
    open_questions = [
        {
            "id": question.get("id"),
            "text": question.get("text"),
            "status": question.get("status"),
            "owner": question.get("owner"),
        }
        for question in questions_store.list_questions(include_resolved=True)
        if topic.lower() in (question.get("text") or "").lower()
        or topic.lower() in (question.get("source") or "").lower()
    ]
    if not open_questions:
        open_questions = [
            {
                "id": question.get("id"),
                "text": question.get("text"),
                "status": question.get("status"),
                "owner": question.get("owner"),
            }
            for question in knowledge.get("open_questions", [])
        ]

    workflow_records = _workflow_records(families_path, registry_path)
    talking_points: list[dict] = []
    for version in knowledge.get("workflow_versions", []):
        point = _talking_point_from_workflow(version, workflow_records)
        if point is not None:
            talking_points.append(point)
    for claim in knowledge.get("claims", []):
        talking_points.append(
            {
                "text": claim.get("text", ""),
                "citations": [
                    {
                        "source": claim.get("source_doc", ""),
                        "locator": claim.get("citation", ""),
                        "method": "stored claim",
                    }
                ],
                "label": claim.get("label"),
            }
        )

    if not talking_points:
        raise ValueError("meeting pack requires stored knowledge — no talking points found")

    return MeetingPack(
        output_id=f"pack-{uuid4().hex[:12]}",
        topic=topic.strip(),
        period=period.strip(),
        audited_numbers=numbers,
        workflow_knowledge=workflow_knowledge,
        risks=risks,
        open_questions=open_questions,
        talking_points=talking_points[:8],
        signoff_line=signoff_line,
        signoff_status="pending",
        release_state="draft",
    )