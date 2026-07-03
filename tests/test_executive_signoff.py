import pytest

from mcp_server.server import dispatch
from serving.decision_brief import build_decision_brief
from serving.open_design import export_executive_output, render_decision_brief_html
from serving.signoff import can_render_released, sign_off_output


def _citation() -> list[dict]:
    return [
        {
            "source": "deck:hq_weekly_review.pptx",
            "locator": "slide 6",
            "method": "slide extract",
        }
    ]


def _brief() -> dict:
    return build_decision_brief(
        question="Should HQ release the weekly cost brief?",
        evidence_items=[{"text": "Weekly review covers material variance.", "citations": _citation()}],
    ).to_dict()


def test_unsigned_brief_cannot_render_as_released():
    brief = _brief()

    assert not can_render_released(brief)
    html = render_decision_brief_html(brief)
    assert "DRAFT — NOT RELEASED" in html
    assert "signed off by" not in html


def test_failed_audit_cannot_be_signed_off_as_approved():
    brief = _brief()
    signed = sign_off_output(
        brief,
        output_type="decision_brief",
        approver="finance_controller",
        audit_state={"passed": False, "issues": ["unsupported claim"], "certainty": {"overall": 0.0}},
    )

    assert signed["signoff"]["approved"] is False
    assert signed["release_state"] == "draft"


def test_signoff_records_approver_timestamp_certainty_audit_state_and_note():
    brief = _brief()
    signed = sign_off_output(
        brief,
        output_type="decision_brief",
        approver="finance_controller",
        audit_state={"passed": True, "certainty": {"overall": 0.92}, "issues": []},
        note="Reviewed against deck slides.",
    )

    assert signed["signoff"]["approver"] == "finance_controller"
    assert signed["signoff"]["approved"] is True
    assert signed["signoff"]["certainty_at_approval"] == 0.92
    assert signed["signoff"]["audit_state"]["passed"] is True
    assert signed["signoff"]["note"] == "Reviewed against deck slides."
    assert signed["signoff"]["timestamp"]
    assert can_render_released(signed)


def test_sign_off_output_mcp_tool():
    brief = _brief()
    signed = dispatch(
        "sign_off_output",
        output=brief,
        output_type="decision_brief",
        approver="finance_controller",
        audit_state={"passed": True, "certainty": {"overall": 0.95}, "issues": []},
    )

    assert signed["release_state"] == "released"


def test_unsigned_export_is_watermarked_only(tmp_path):
    brief = _brief()
    exported = export_executive_output(brief, "decision_brief", out_dir=str(tmp_path))

    assert exported["watermarked"] is True
    assert "DRAFT — NOT RELEASED" in open(exported["html"]).read()