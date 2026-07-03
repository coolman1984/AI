import pytest

from mcp_server.server import dispatch
from serving.decision_brief import build_decision_brief


def _citation(locator: str = "slide 6") -> list[dict]:
    return [
        {
            "source": "deck:hq_weekly_review.pptx",
            "locator": locator,
            "method": "slide extract",
        }
    ]


def test_brief_refuses_evidence_free_claims():
    with pytest.raises(ValueError, match="requires at least one cited evidence"):
        build_decision_brief(
            question="Should HQ adopt Tuesday close?",
            evidence_items=[{"text": "Frame review moved to Tuesday.", "citations": []}],
        )


def test_numeric_evidence_renders_with_provenance_tags():
    brief = build_decision_brief(
        question="Should HQ release the weekly cost brief?",
        evidence_items=[
            {
                "label": "Material variance",
                "value": 125000.0,
                "evidence": {
                    "source": "duckdb:clean_actuals",
                    "locator": "period=2026-05",
                    "method": "SUM(amount)",
                },
            },
            {
                "text": "Frame review moved to Tuesday close.",
                "citations": _citation("slide 7"),
            },
        ],
        options=[{"text": "Approve Tuesday close.", "citations": _citation("slide 8")}],
        risks=[{"text": "Local scrap classification remains unresolved.", "citations": _citation("slide 9")}],
        recommendation={"text": "Approve Tuesday close after scrap review.", "citations": _citation("slide 8")},
    )

    assert brief.evidence[0]["tag"] == "AUDITED-FROM-QUERY"
    assert brief.evidence[0]["value"] == 125000.0
    assert brief.evidence[1]["citations"][0]["locator"] == "slide 7"


def test_brief_has_signoff_status_and_cannot_mark_itself_released():
    brief = build_decision_brief(
        question="Should HQ release the weekly cost brief?",
        evidence_items=[{"text": "Weekly review covers material variance.", "citations": _citation()}],
    )

    assert brief.signoff_line == "Pending owner sign-off"
    assert brief.signoff_status == "pending"
    assert brief.release_state == "draft"


def test_output_stays_within_one_page_budget_fields():
    with pytest.raises(ValueError, match="one-page evidence budget"):
        build_decision_brief(
            question="Budget test",
            evidence_items=[
                {"text": f"Evidence {index}.", "citations": _citation(f"slide {index}")}
                for index in range(9)
            ],
        )


def test_build_decision_brief_mcp_tool():
    out = dispatch(
        "build_decision_brief",
        question="Should HQ release the weekly cost brief?",
        evidence_items=[
            {
                "text": "Weekly review covers material variance.",
                "citations": _citation(),
            }
        ],
    )

    assert out["question"].startswith("Should HQ")
    assert out["release_state"] == "draft"
    assert out["signoff_status"] == "pending"