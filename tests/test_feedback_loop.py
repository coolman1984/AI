import pytest

from engines.learning.feedback import (
    VALID_VERDICTS,
    glossary_candidate_from_correction,
    record_output_feedback,
)
from mcp_server.server import dispatch


def test_verdict_values_are_limited_to_useful_corrected_wrong_or_needs_followup():
    assert VALID_VERDICTS == frozenset({"useful", "corrected", "wrong", "needs_followup"})

    with pytest.raises(ValueError, match="verdict must be one of"):
        record_output_feedback(
            output_id="brief-abc",
            output_type="decision_brief",
            verdict="maybe",
        )


def test_correction_links_to_output_id_and_evidence_citation_when_applicable(tmp_path):
    store_path = str(tmp_path / "output_feedback.json")
    record = record_output_feedback(
        output_id="brief-abc123",
        output_type="decision_brief",
        verdict="corrected",
        note="Scrap term was wrong.",
        correction={"source_term": "스크랩", "target_term": "Scrap loss", "reason": "owner correction"},
        citation={
            "source": "deck:hq_weekly_review.pptx",
            "locator": "slide 9",
            "method": "slide extract",
        },
        store_path=store_path,
    )

    assert record["output_id"] == "brief-abc123"
    assert record["citation"]["locator"] == "slide 9"
    assert record["correction"]["target_term"] == "Scrap loss"


def test_glossary_candidate_can_be_produced_without_auto_accepting(tmp_path):
    candidate = glossary_candidate_from_correction(
        {"source_term": "스크랩", "target_term": "Scrap loss", "reason": "owner correction"}
    )

    assert candidate is not None
    assert candidate["status"] == "candidate"
    assert candidate["auto_accepted"] is False

    record = record_output_feedback(
        output_id="brief-abc123",
        output_type="decision_brief",
        verdict="corrected",
        correction={"source_term": "스크랩", "target_term": "Scrap loss"},
        store_path=str(tmp_path / "output_feedback.json"),
    )
    assert record["glossary_candidate"]["auto_accepted"] is False


def test_record_output_feedback_mcp_tool(tmp_path):
    out = dispatch(
        "record_output_feedback",
        output_id="pack-xyz",
        output_type="meeting_pack",
        verdict="useful",
        note="Talking points were accurate.",
        store_path=str(tmp_path / "output_feedback.json"),
    )

    assert out["verdict"] == "useful"
    assert out["output_type"] == "meeting_pack"