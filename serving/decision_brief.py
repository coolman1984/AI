"""Minimal HQ deck brief assembly for the first Tier 2 deck gate."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from engines.audit.brief_audit import MappingExtractor, audit_brief_claims
from engines.docs.glossary import FactoryGlossary
from engines.docs.translation_check import check_translation_terms
from engines.docs.workflow_record import WorkflowField, extract_workflow_record


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
