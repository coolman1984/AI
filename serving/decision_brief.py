"""Executive decision brief assembly (D.1) and HQ deck brief gate (B.9)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import uuid4

from engines.audit.brief_audit import MappingExtractor, audit_brief_claims
from engines.docs.glossary import FactoryGlossary
from engines.docs.translation_check import check_translation_terms
from engines.docs.workflow_record import WorkflowField, extract_workflow_record
from shared.contracts.models import EvidenceRef, NumberFact

ONE_PAGE_LIMITS = {
    "max_evidence": 8,
    "max_options": 4,
    "max_risks": 5,
}


@dataclass
class BriefClaim:
    text: str
    locator: str
    field_name: str


@dataclass
class HqDeckBrief:
    title: str
    trusted_claims: list[BriefClaim]
    review_claims: list[dict]
    coverage_report: dict
    glossary_flags: list[dict]
    audit_status: dict
    signoff_placeholder: str = "Pending owner sign-off"

    def to_dict(self) -> dict:
        return asdict(self)


def _iter_fields(record) -> list[tuple[str, WorkflowField]]:
    fields = [("purpose", record.purpose)]
    for field_name in ("steps", "roles", "kpis", "what_changed", "open_questions", "risks"):
        for item in getattr(record, field_name):
            fields.append((field_name, item))
    return fields


def build_hq_deck_brief(
    payload: dict,
    *,
    stamp: dict,
    glossary_payload: dict | None,
    citations: dict[str, str],
    second_extractions: dict[str, str],
    coverage_report: dict,
    critical_terms: list[str] | None = None,
    back_translations: dict[str, str] | None = None,
    audit_cfg: dict | None = None,
) -> HqDeckBrief:
    record = extract_workflow_record(payload, stamp=stamp)
    glossary = FactoryGlossary.from_dict(glossary_payload)
    translation = check_translation_terms(
        record,
        glossary,
        critical_terms=critical_terms,
        back_translations=back_translations,
    )

    claims = []
    claim_lookup: dict[str, tuple[str, WorkflowField]] = {}
    for index, (field_name, item) in enumerate(_iter_fields(record), start=1):
        locator = item.citations[0].locator
        claim_id = f"{field_name}:{index}:{locator}"
        claims.append({"text": item.translated_text, "locator": locator, "claim_id": claim_id})
        claim_lookup[claim_id] = (field_name, item)

    audit = audit_brief_claims(
        [{"text": claim["text"], "locator": claim["locator"]} for claim in claims],
        citations,
        MappingExtractor(second_extractions),
        cfg=audit_cfg,
    )

    audit_claims = {
        item["locator"]: item
        for item in audit.recomputed["claims"]
    }
    trusted_claims: list[BriefClaim] = []
    review_claims: list[dict] = []

    for claim in claims:
        audit_item = audit_claims.get(claim["locator"], {})
        field_name, _ = claim_lookup[claim["claim_id"]]
        if not audit_item.get("supported", False) or audit_item.get("agreement", 1.0) < (
            audit_cfg or {}
        ).get("brief_disagreement_threshold", 0.45):
            review_claims.append(
                {
                    "text": claim["text"],
                    "locator": claim["locator"],
                    "field_name": field_name,
                    "reason": "unsupported_or_disputed",
                }
            )
            continue
        trusted_claims.append(
            BriefClaim(text=claim["text"], locator=claim["locator"], field_name=field_name)
        )

    audit_status = {
        "passed": audit.passed and not translation.blocked,
        "needs_human": audit.needs_human or translation.blocked,
        "issues": audit.issues,
        "glossary_blocked": translation.blocked,
    }
    return HqDeckBrief(
        title=record.title,
        trusted_claims=trusted_claims,
        review_claims=review_claims,
        coverage_report=coverage_report,
        glossary_flags=[flag.__dict__ for flag in translation.review_flags],
        audit_status=audit_status,
    )


@dataclass
class DecisionBrief:
    output_id: str
    question: str
    evidence: list[dict]
    options: list[dict]
    risks: list[dict]
    recommendation: dict | None
    signoff_line: str
    signoff_status: str
    release_state: str
    review_items: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _require_citation(item: dict, *, field: str) -> dict:
    citations = item.get("citations") or []
    if not citations:
        raise ValueError(f"{field} requires at least one citation — evidence-free claims refused")
    for citation in citations:
        if not citation.get("source") or not citation.get("locator") or not citation.get("method"):
            raise ValueError(f"{field} citation must include source, locator, and method")
    return item


def _number_fact_from_payload(payload: dict) -> NumberFact:
    evidence_payload = payload.get("evidence") or {}
    evidence = EvidenceRef(
        source=evidence_payload.get("source", ""),
        locator=evidence_payload.get("locator", ""),
        method=evidence_payload.get("method", ""),
        value=payload.get("value"),
    )
    fact = NumberFact(
        label=payload.get("label", "metric"),
        value=float(payload["value"]),
        evidence=evidence,
    )
    if not evidence.resolves():
        raise ValueError("numeric evidence requires resolving source, locator, and method")
    return fact


def _render_number_evidence(payload: dict) -> dict:
    fact = _number_fact_from_payload(payload)
    return {
        "text": f"{fact.label}: {fact.value:+,.0f}",
        "tag": fact.tag,
        "value": fact.value,
        "label": fact.label,
        "citations": [
            {
                "source": fact.evidence.source,
                "locator": fact.evidence.locator,
                "method": fact.evidence.method,
            }
        ],
    }


def _enforce_one_page_budget(*, evidence: list, options: list, risks: list) -> None:
    if len(evidence) > ONE_PAGE_LIMITS["max_evidence"]:
        raise ValueError("decision brief exceeds one-page evidence budget")
    if len(options) > ONE_PAGE_LIMITS["max_options"]:
        raise ValueError("decision brief exceeds one-page options budget")
    if len(risks) > ONE_PAGE_LIMITS["max_risks"]:
        raise ValueError("decision brief exceeds one-page risks budget")


def build_decision_brief(
    *,
    question: str,
    evidence_items: list[dict],
    options: list[dict] | None = None,
    risks: list[dict] | None = None,
    recommendation: dict | None = None,
    signoff_line: str = "Pending owner sign-off",
) -> DecisionBrief:
    """Build a one-page executive decision brief from stored evidence only."""
    if not question.strip():
        raise ValueError("question is required")
    if not signoff_line.strip():
        raise ValueError("signoff_line is mandatory")

    trusted_evidence: list[dict] = []
    review_items: list[dict] = []

    for item in evidence_items:
        try:
            if "value" in item:
                trusted_evidence.append(_render_number_evidence(item))
                continue
            text = (item.get("text") or "").strip()
            if not text:
                review_items.append({"text": "", "reason": "empty_evidence"})
                continue
            cited = _require_citation(item, field="evidence")
            trusted_evidence.append(
                {
                    "text": text,
                    "citations": cited["citations"],
                }
            )
        except ValueError as exc:
            review_items.append({"text": item.get("text", ""), "reason": str(exc)})

    trusted_options: list[dict] = []
    for option in options or []:
        text = (option.get("text") or "").strip()
        if not text:
            review_items.append({"text": "", "reason": "empty_option"})
            continue
        try:
            cited = _require_citation(option, field="option")
            trusted_options.append({"text": text, "citations": cited["citations"]})
        except ValueError as exc:
            review_items.append({"text": text, "reason": str(exc)})

    trusted_risks: list[dict] = []
    for risk in risks or []:
        text = (risk.get("text") or "").strip()
        if not text:
            review_items.append({"text": "", "reason": "empty_risk"})
            continue
        try:
            cited = _require_citation(risk, field="risk")
            trusted_risks.append({"text": text, "citations": cited["citations"]})
        except ValueError as exc:
            review_items.append({"text": text, "reason": str(exc)})

    trusted_recommendation = None
    if recommendation is not None:
        text = (recommendation.get("text") or "").strip()
        if not text:
            review_items.append({"text": "", "reason": "empty_recommendation"})
        else:
            try:
                cited = _require_citation(recommendation, field="recommendation")
                trusted_recommendation = {"text": text, "citations": cited["citations"]}
            except ValueError as exc:
                review_items.append({"text": text, "reason": str(exc)})

    if not trusted_evidence:
        raise ValueError("decision brief requires at least one cited evidence item")

    _enforce_one_page_budget(
        evidence=trusted_evidence,
        options=trusted_options,
        risks=trusted_risks,
    )

    return DecisionBrief(
        output_id=f"brief-{uuid4().hex[:12]}",
        question=question.strip(),
        evidence=trusted_evidence,
        options=trusted_options,
        risks=trusted_risks,
        recommendation=trusted_recommendation,
        signoff_line=signoff_line,
        signoff_status="pending",
        release_state="draft",
        review_items=review_items,
    )
