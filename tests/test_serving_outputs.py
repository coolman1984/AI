import importlib.util

import pytest

from serving.decision_brief import build_decision_brief
from serving.meeting_pack import build_meeting_pack
from serving.open_design import (
    export_executive_output,
    render_decision_brief_html,
    render_meeting_pack_html,
)
from serving.signoff import sign_off_output


def _citation(locator: str = "slide 6") -> list[dict]:
    return [
        {
            "source": "deck:hq_weekly_review.pptx",
            "locator": locator,
            "method": "slide extract",
        }
    ]


def _signed_brief() -> dict:
    brief = build_decision_brief(
        question="Should HQ release the weekly cost brief?",
        evidence_items=[{"text": "Weekly review covers material variance.", "citations": _citation()}],
    ).to_dict()
    return sign_off_output(
        brief,
        output_type="decision_brief",
        approver="finance_controller",
        audit_state={"passed": True, "certainty": {"overall": 0.95}, "issues": []},
    )


def test_signed_decision_brief_renders_html():
    signed = _signed_brief()
    html = render_decision_brief_html(signed)

    assert "<!doctype html>" in html
    assert "signed off by finance_controller" in html
    assert "DRAFT — NOT RELEASED" not in html


def test_signed_meeting_pack_renders_html_and_pptx_when_available(tmp_path):
    from engines.brain.claims import ClaimsStore
    from engines.brain.registry import DocumentRegistry
    from engines.brain.workflow_family import WorkflowFamilyStore

    registry_path = str(tmp_path / "document_registry.json")
    families_path = str(tmp_path / "workflow_families.json")
    claims_path = str(tmp_path / "claims.json")
    questions_path = str(tmp_path / "open_questions.json")

    WorkflowFamilyStore(
        path=families_path,
        registry=DocumentRegistry(path=registry_path),
    ).register_workflow_version(
        family_id="wf-cost-review",
        family_name="HQ Cost Review",
        version_label="v1",
        source_hash="hash-v1",
        source_path="cost_review_v1.pptx",
        valid_from="2025-01-01",
        valid_to=None,
        ingest_run_id="ingest-1",
        workflow_record={
            "title": "HQ Cost Review Workflow",
            "purpose": {
                "translated_text": "Review weekly material costs.",
                "citations": _citation("slide 2"),
            },
        },
    )
    ClaimsStore(path=claims_path).add_claim(
        text="Material variance is 12%",
        source_doc="cost_review_v1.pptx",
        page=7,
        citation="cost_review_v1.pptx#page=7",
    )

    pack = build_meeting_pack(
        topic="cost review",
        period="2026-Q2",
        audited_numbers=[
            {
                "label": "Material variance",
                "value": 125000.0,
                "source": "duckdb:clean_actuals",
                "locator": "period=2026-05",
                "method": "SUM(amount)",
            }
        ],
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
    ).to_dict()
    signed = sign_off_output(
        pack,
        output_type="meeting_pack",
        approver="ceo_office",
        audit_state={"passed": True, "certainty": {"overall": 0.9}, "issues": []},
    )
    html = render_meeting_pack_html(signed)

    assert "signed off by ceo_office" in html
    assert "DRAFT — NOT RELEASED" not in html


def test_unsigned_output_produces_draft_watermarked_state_only():
    brief = build_decision_brief(
        question="Should HQ release the weekly cost brief?",
        evidence_items=[{"text": "Weekly review covers material variance.", "citations": _citation()}],
    ).to_dict()
    html = render_decision_brief_html(brief)

    assert "DRAFT" in html
    assert "pending owner sign-off" in html.lower()


def test_renderer_never_computes_numbers(tmp_path):
    signed = _signed_brief()
    exported = export_executive_output(signed, "decision_brief", out_dir=str(tmp_path))
    html = open(exported["html"]).read()

    assert "numbers are not computed here" in html
    assert exported["release_state"] == "released"


def test_signed_meeting_pack_pptx_export_when_python_pptx_available(tmp_path):
    if not importlib.util.find_spec("pptx"):
        pytest.skip("python-pptx not installed")

    from engines.brain.claims import ClaimsStore
    from engines.brain.registry import DocumentRegistry
    from engines.brain.workflow_family import WorkflowFamilyStore

    registry_path = str(tmp_path / "document_registry.json")
    families_path = str(tmp_path / "workflow_families.json")
    claims_path = str(tmp_path / "claims.json")
    questions_path = str(tmp_path / "open_questions.json")

    WorkflowFamilyStore(
        path=families_path,
        registry=DocumentRegistry(path=registry_path),
    ).register_workflow_version(
        family_id="wf-cost-review",
        family_name="HQ Cost Review",
        version_label="v1",
        source_hash="hash-v1",
        source_path="cost_review_v1.pptx",
        valid_from="2025-01-01",
        valid_to=None,
        ingest_run_id="ingest-1",
        workflow_record={
            "title": "HQ Cost Review Workflow",
            "purpose": {
                "translated_text": "Review weekly material costs.",
                "citations": _citation("slide 2"),
            },
        },
    )
    ClaimsStore(path=claims_path).add_claim(
        text="Material variance is 12%",
        source_doc="cost_review_v1.pptx",
        page=7,
        citation="cost_review_v1.pptx#page=7",
    )

    pack = build_meeting_pack(
        topic="cost review",
        period="2026-Q2",
        audited_numbers=[
            {
                "label": "Material variance",
                "value": 125000.0,
                "source": "duckdb:clean_actuals",
                "locator": "period=2026-05",
                "method": "SUM(amount)",
            }
        ],
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
    ).to_dict()
    signed = sign_off_output(
        pack,
        output_type="meeting_pack",
        approver="ceo_office",
        audit_state={"passed": True, "certainty": {"overall": 0.9}, "issues": []},
    )
    exported = export_executive_output(signed, "meeting_pack", out_dir=str(tmp_path))

    assert exported["pptx"]
    assert (tmp_path / "meeting_pack.pptx").stat().st_size > 0