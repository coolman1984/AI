"""Tests for labeled idea synthesis (F.7)."""

from __future__ import annotations

from engines.brain.idea_synthesis import suggest_ideas
from mcp_server.server import dispatch


def _cited_record(text: str, locator: str, entity: str = "kpi-1") -> dict:
    return {
        "entity": entity,
        "text": text,
        "citations": [{"source": "workflow:v1", "locator": locator}],
    }


def test_output_title_body_contains_ai_suggested_idea_label():
    result = suggest_ideas(
        topic="scrap reduction",
        input_records=[_cited_record("Reduce local scrap handling cost.", "slide 8")],
    )
    idea = result["ideas"][0]
    assert "AI-SUGGESTED IDEA" in idea["title"]
    assert "AI-SUGGESTED IDEA" in idea["body"]


def test_every_input_claim_has_citation():
    result = suggest_ideas(
        topic="scrap reduction",
        input_records=[
            _cited_record("Reduce local scrap handling cost.", "slide 8"),
            {"text": "missing citation"},
        ],
    )
    assert result["status"] == "ok"
    assert all(idea["citations"] for idea in result["ideas"])


def test_contradicted_inputs_create_warning_and_cannot_be_hidden():
    contradictions = [
        {
            "field": "scrap_rate",
            "source_a": "kpi-1",
            "source_b": "kpi-2",
        }
    ]
    result = suggest_ideas(
        topic="scrap reduction",
        input_records=[_cited_record("Reduce scrap.", "slide 8", entity="kpi-1")],
        contradictions=contradictions,
    )
    idea = result["ideas"][0]
    assert idea["warnings"]
    assert "Contradiction" in idea["warnings"][0]
    assert idea["can_render_as_recommendation"] is False


def test_unsigned_idea_cannot_render_as_recommendation():
    result = suggest_ideas(
        topic="scrap reduction",
        input_records=[_cited_record("Reduce local scrap handling cost.", "slide 8")],
        signed_off=False,
    )
    idea = result["ideas"][0]
    assert idea["is_recommendation"] is False
    assert idea["can_render_as_recommendation"] is False
    assert result["unsigned_blocks_recommendation"] is True


def test_dispatch_suggest_ideas():
    out = dispatch(
        "suggest_ideas",
        topic="scrap reduction",
        input_records=[_cited_record("Reduce local scrap handling cost.", "slide 8")],
    )
    assert out["label"] == "AI-SUGGESTED IDEA"