"""Labeled idea synthesis after claims/contradiction gates (MASTER_PLAN F.7)."""

from __future__ import annotations

_IDEA_LABEL = "AI-SUGGESTED IDEA"


def _has_citation(record: dict) -> bool:
    citation = record.get("citation", "")
    citations = record.get("citations", [])
    if isinstance(citations, list) and citations:
        return any(c.get("locator") or c.get("source") for c in citations if isinstance(c, dict))
    return bool(str(citation).strip())


def suggest_ideas(
    *,
    topic: str,
    input_records: list[dict],
    contradictions: list[dict] | None = None,
    signed_off: bool = False,
) -> dict:
    """Generate idea briefs labeled AI-SUGGESTED IDEA from cited inputs only."""
    if not topic.strip():
        raise ValueError("topic is required")

    cited_inputs: list[dict] = []
    missing_citation: list[dict] = []
    for record in input_records:
        if _has_citation(record):
            cited_inputs.append(record)
        else:
            missing_citation.append(record)

    if not cited_inputs:
        return {
            "status": "blocked",
            "reason": "no_cited_inputs",
            "label": _IDEA_LABEL,
            "ideas": [],
            "warnings": ["All inputs lack citations."],
        }

    contradiction_warnings: list[str] = []
    contradicted_refs: set[str] = set()
    for contradiction in contradictions or []:
        ref_a = contradiction.get("source_a", contradiction.get("entity", ""))
        ref_b = contradiction.get("source_b", "")
        contradicted_refs.add(str(ref_a))
        contradicted_refs.add(str(ref_b))
        contradiction_warnings.append(
            f"Contradiction requires human resolution: {contradiction.get('field', topic)} "
            f"({ref_a} vs {ref_b})"
        )

    ideas: list[dict] = []
    for index, record in enumerate(cited_inputs, start=1):
        text = record.get("text") or record.get("translated_text", "")
        locator = record.get("locator") or record.get("citation", "")
        if isinstance(record.get("citations"), list) and record["citations"]:
            locator = record["citations"][0].get("locator", locator)
        record_ref = record.get("entity", record.get("field", f"input-{index}"))
        warnings = list(contradiction_warnings) if str(record_ref) in contradicted_refs else []
        if warnings:
            warnings.append("Contradicted input cannot be hidden.")

        title = f"{_IDEA_LABEL}: {topic} — option {index}"
        body = (
            f"{_IDEA_LABEL}\n\n"
            f"Topic: {topic}\n"
            f"Based on cited record: {text}\n"
            f"Source: {locator}\n"
            f"This is a suggestion only — not a verified fact or decision."
        )
        ideas.append(
            {
                "title": title,
                "body": body,
                "label": _IDEA_LABEL,
                "citations": [locator] if locator else [],
                "warnings": warnings,
                "is_recommendation": False,
                "signed_off": signed_off,
                "can_render_as_recommendation": signed_off and not warnings,
            }
        )

    return {
        "status": "ok",
        "label": _IDEA_LABEL,
        "topic": topic,
        "ideas": ideas,
        "warnings": contradiction_warnings,
        "unsigned_blocks_recommendation": not signed_off,
    }